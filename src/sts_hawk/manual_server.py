"""Run the private desktop proxy inside the Linux game sandbox."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import sys
import tempfile
import urllib.request
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

logger = logging.getLogger(__name__)
HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "upgrade"}


def desktop_proxy(
    environment: Any,
    target: str,
    finished: asyncio.Event,
    access_token: str | None = None,
    access_token_sha256: str | None = None,
) -> web.Application:
    """Proxy noVNC and expose bounded diagnostics and a session-stop endpoint."""
    expected = access_token_sha256 or (
        hashlib.sha256(access_token.encode()).hexdigest() if access_token else None
    )

    def authorized(value: str) -> bool:
        """Compare a link or cookie to the stored digest without retaining its secret."""
        return expected is not None and hmac.compare_digest(
            hashlib.sha256(value.encode()).hexdigest(), expected
        )

    @web.middleware
    async def authenticate(request: web.Request, handler):
        """Protect a browser tunnel with a private link and an HTTP-only cookie."""
        if expected is not None:
            if authorized(request.query.get("access_token", "")):
                response = web.HTTPFound("/vnc.html?autoconnect=1&resize=scale")
                response.set_cookie(
                    "sts_session",
                    request.query["access_token"],
                    httponly=True,
                    secure=True,
                    samesite="Strict",
                )
                response.headers["Cache-Control"] = "no-store"
                raise response
            if not authorized(request.cookies.get("sts_session", "")):
                raise web.HTTPForbidden(
                    text="Open the private session link to connect."
                )
        return await handler(request)

    app = web.Application(middlewares=[authenticate])
    client_key = web.AppKey("client", ClientSession)
    connections: set[web.WebSocketResponse] = set()

    async def close_connections(app: web.Application) -> None:
        """Close active desktop streams when the human session ends."""
        await asyncio.gather(
            *(
                connection.close(code=1001, message=b"Session ended")
                for connection in list(connections)
            )
        )

    async def session(app: web.Application):
        """Reuse one upstream HTTP client throughout the desktop session."""
        async with ClientSession(
            timeout=ClientTimeout(total=None, sock_connect=10), auto_decompress=False
        ) as client:
            app[client_key] = client
            yield

    async def health(request: web.Request) -> web.Response:
        """Confirm the tunnel endpoint is running without invoking a model."""
        return web.json_response({"ready": True, "model_calls": 0})

    async def status(request: web.Request) -> web.Response:
        """Read recent game logs and resource counters from the active sandbox."""
        result = await environment.exec(
            [
                "bash",
                "-lc",
                (
                    "tail -n 150 /tmp/game.log /tmp/sts-manual-vnc.log 2>/dev/null; "
                    "for f in memory.current memory.peak memory.events cpu.stat; do "
                    'printf "\\n%s\\n" "$f"; cat "/sys/fs/cgroup/$f"; done'
                ),
            ],
            timeout=30,
        )
        return web.json_response(
            {"success": result.success, "diagnostics": result.stdout}
        )

    async def finish(request: web.Request) -> web.Response:
        """End the human session and allow Inspect to clean up its sandbox."""
        finished.set()
        return web.json_response({"stopping": True})

    async def forward(request: web.Request) -> web.StreamResponse:
        """Forward HTTP assets or bidirectional VNC WebSocket messages."""
        if request.path == "/":
            raise web.HTTPFound("/vnc.html?autoconnect=1&resize=scale")
        client = app[client_key]
        url = target + request.path_qs
        if request.headers.get("Upgrade", "").lower() == "websocket":
            async with client.ws_connect(url, protocols=("binary",)) as upstream:
                downstream = web.WebSocketResponse(protocols=("binary",))
                await downstream.prepare(request)
                connections.add(downstream)

                async def relay(source, destination):
                    """Preserve binary desktop frames and browser input events."""
                    async for message in source:
                        if message.type == WSMsgType.BINARY:
                            await destination.send_bytes(message.data)
                        elif message.type == WSMsgType.TEXT:
                            await destination.send_str(message.data)
                        elif message.type == WSMsgType.ERROR:
                            break

                tasks = [
                    asyncio.create_task(relay(upstream, downstream)),
                    asyncio.create_task(relay(downstream, upstream)),
                ]
                try:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for running in tasks:
                        running.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    await downstream.close()
                    connections.discard(downstream)
                return downstream
        async with client.request(request.method, url) as response:
            return web.Response(
                status=response.status,
                headers={
                    name: value
                    for name, value in response.headers.items()
                    if name.lower() not in HOP_HEADERS
                },
                body=await response.read(),
            )

    app.cleanup_ctx.append(session)
    app.on_shutdown.append(close_connections)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/status", status)
    app.router.add_post("/api/finish", finish)
    app.router.add_route("*", "/{path:.*}", forward)
    return app


async def browser_tunnel(port: int, url: str, sha256: str):
    """Start a verified cloudflared binary and forward its diagnostics."""
    path = Path(tempfile.mkdtemp(prefix="sts-tunnel-")) / "cloudflared"

    def download() -> None:
        """Download the pinned official binary and verify its release digest."""
        with urllib.request.urlopen(url, timeout=60) as response:
            binary = response.read()
        if hashlib.sha256(binary).hexdigest() != sha256:
            raise RuntimeError("cloudflared release checksum does not match")
        path.write_bytes(binary)
        path.chmod(0o700)

    await asyncio.to_thread(download)
    process = await asyncio.create_subprocess_exec(
        str(path),
        "tunnel",
        "--no-autoupdate",
        "--protocol",
        "http2",
        "--url",
        f"http://127.0.0.1:{port}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "GOMAXPROCS": "1"},
    )

    async def output() -> None:
        """Record the public tunnel address without recording its private access key."""
        async for line in process.stdout:
            logger.info("Browser tunnel: %s", line.decode().strip())

    return process, asyncio.create_task(output())


class LocalEnvironment:
    """Provide fixed diagnostic commands within the same isolated game sandbox."""

    async def exec(self, cmd, timeout):
        """Capture a local diagnostic subprocess without model or cluster access."""
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return SimpleNamespace(success=process.returncode == 0, stdout=output.decode())


async def run_server(config: dict) -> None:
    """Keep authentication, noVNC forwarding and the outbound tunnel in one sandbox."""
    finished = asyncio.Event()
    app = desktop_proxy(
        LocalEnvironment(),
        f"http://127.0.0.1:{config['backend_port']}",
        finished,
        access_token_sha256=config.get("access_token_sha256"),
    )
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config["port"]).start()
    tunnel = None
    output = None
    try:
        if config["browser_tunnel_enabled"]:
            if not config.get("access_token_sha256"):
                raise ValueError("Browser access requires a private access-key digest.")
            tunnel, output = await browser_tunnel(
                config["port"], config["cloudflared_url"], config["cloudflared_sha256"]
            )
        logger.info("Sandbox desktop ready on port %s", config["port"])
        with suppress(TimeoutError):
            await asyncio.wait_for(finished.wait(), timeout=config["session_seconds"])
    finally:
        if tunnel is not None and tunnel.returncode is None:
            tunnel.terminate()
            with suppress(TimeoutError):
                await asyncio.wait_for(tunnel.wait(), timeout=10)
            if tunnel.returncode is None:
                tunnel.kill()
                await tunnel.wait()
        if output is not None:
            await output
        await runner.cleanup()
        Path("/tmp/sts-manual-finished").touch()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server(json.loads(Path(sys.argv[1]).read_text())))
