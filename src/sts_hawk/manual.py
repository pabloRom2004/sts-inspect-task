"""Expose a human-controlled desktop through Hawk's authenticated runner tunnel."""

import asyncio
import hashlib
import hmac
import ipaddress
import os
import tempfile
import urllib.request
from contextlib import suppress
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web
from inspect_ai import Task, task
from inspect_ai.log import transcript
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import SandboxEnvironment, sandbox

from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import logger
from sts_hawk.task import second_game

DEFAULTS = default_run_config()["manual_session"]
HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "upgrade"}


def desktop_proxy(
    environment: SandboxEnvironment,
    target: str,
    finished: asyncio.Event,
    access_token: str | None = None,
) -> web.Application:
    """Proxy noVNC and expose bounded diagnostics and a session-stop endpoint."""

    @web.middleware
    async def authenticate(request: web.Request, handler):
        """Protect a browser tunnel with a private link and an HTTP-only cookie."""
        if access_token is not None:
            if hmac.compare_digest(request.query.get("access_token", ""), access_token):
                response = web.HTTPFound("/vnc.html?autoconnect=1&resize=scale")
                response.set_cookie(
                    "sts_session",
                    access_token,
                    httponly=True,
                    secure=True,
                    samesite="Strict",
                )
                response.headers["Cache-Control"] = "no-store"
                raise response
            if not hmac.compare_digest(
                request.cookies.get("sts_session", ""), access_token
            ):
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


@solver
def manual_control(
    port: int = DEFAULTS["port"],
    session_seconds: int = DEFAULTS["session_seconds"],
    browser_tunnel_enabled: bool = DEFAULTS["browser_tunnel_enabled"],
    cloudflared_url: str = DEFAULTS["cloudflared_url"],
    cloudflared_sha256: str = DEFAULTS["cloudflared_sha256"],
) -> Solver:
    """Serve the sandbox desktop on a runner port without making model calls."""
    if not 1 <= port <= 65535 or session_seconds <= 0:
        raise ValueError("Use a valid TCP port and a positive session duration.")

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Start noVNC, wait for human play, and retain the final save and logs."""
        environment = sandbox()
        result = await environment.exec(
            [
                "bash",
                "-lc",
                "apt-get install -y --no-install-recommends novnc websockify >/tmp/sts-manual-install.log 2>&1",
            ],
            timeout=180,
        )
        if not result.success:
            raise RuntimeError(f"noVNC installation failed: {result.stderr}")
        result = await environment.exec(
            [
                "bash",
                "-lc",
                "nohup websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/tmp/sts-manual-vnc.log 2>&1 </dev/null & hostname -i",
            ],
            timeout=30,
        )
        if not result.success:
            raise RuntimeError(f"noVNC startup failed: {result.stderr}")
        address = str(ipaddress.ip_address(result.stdout.split()[0]))
        target = (
            f"http://[{address}]:6080" if ":" in address else f"http://{address}:6080"
        )
        finished = asyncio.Event()
        access_token = (
            os.environ.get("STS_MANUAL_ACCESS_TOKEN")
            if browser_tunnel_enabled
            else None
        )
        if browser_tunnel_enabled and (access_token is None or len(access_token) < 32):
            raise ValueError(
                "A browser tunnel requires a private STS_MANUAL_ACCESS_TOKEN of at least 32 characters."
            )
        runner = web.AppRunner(
            desktop_proxy(environment, target, finished, access_token), access_log=None
        )
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
        logger.info("Human desktop ready on runner port %s; no model calls", port)
        transcript().info(
            {"manual_session_port": port, "session_seconds": session_seconds}
        )
        tunnel = None
        tunnel_output = None
        try:
            if browser_tunnel_enabled:
                tunnel, tunnel_output = await browser_tunnel(
                    port, cloudflared_url, cloudflared_sha256
                )
            with suppress(TimeoutError):
                await asyncio.wait_for(finished.wait(), timeout=session_seconds)
        finally:
            if tunnel is not None and tunnel.returncode is None:
                tunnel.terminate()
                with suppress(TimeoutError):
                    await asyncio.wait_for(tunnel.wait(), timeout=10)
                if tunnel.returncode is None:
                    tunnel.kill()
                    await tunnel.wait()
            if tunnel_output is not None:
                await tunnel_output
            await runner.cleanup()
            result = await environment.exec(
                [
                    "bash",
                    "-lc",
                    "tail -n 200 /tmp/game.log /tmp/sts-manual-vnc.log; tar -C /root/.local/share/SlayTheSpire2 -czf /tmp/sts-manual-profile.tar.gz default",
                ],
                timeout=30,
            )
            transcript().info({"manual_session_diagnostics": result.stdout})
            if result.success:
                import base64

                profile = await environment.read_file(
                    "/tmp/sts-manual-profile.tar.gz", text=False
                )
                transcript().info(
                    {"profile_archive_base64": base64.b64encode(profile).decode()}
                )
        return state

    return solve


@task
def manual_session(
    port: int = DEFAULTS["port"],
    session_seconds: int = DEFAULTS["session_seconds"],
    browser_tunnel_enabled: bool = DEFAULTS["browser_tunnel_enabled"],
    cloudflared_url: str = DEFAULTS["cloudflared_url"],
    cloudflared_sha256: str = DEFAULTS["cloudflared_sha256"],
    **kwargs,
) -> Task:
    """Reuse the StS2 sandbox for interactive human debugging on Hawk."""
    result = second_game(**kwargs)
    return Task(
        name="sts2_manual_session",
        dataset=result.dataset,
        setup=result.setup,
        solver=manual_control(
            port=port,
            session_seconds=session_seconds,
            browser_tunnel_enabled=browser_tunnel_enabled,
            cloudflared_url=cloudflared_url,
            cloudflared_sha256=cloudflared_sha256,
        ),
        sandbox=result.sandbox,
        config=result.config,
        metadata={
            **result.metadata,
            "purpose": "Human desktop debugging; no model calls or benchmark score",
        },
        **default_run_config()["eval_config"],
    )
