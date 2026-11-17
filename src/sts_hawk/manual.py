"""Run a human-controlled Linux desktop without a model or cross-pod display bridge."""

import hashlib
import json
import os
import re
from contextlib import suppress
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.log import transcript
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import checked_exec, logger
from sts_hawk.task import first_combat, second_game

DEFAULTS = default_run_config()["manual_session"]


@solver
def manual_control(
    game: str = DEFAULTS["game"],
    port: int = DEFAULTS["port"],
    session_seconds: int = DEFAULTS["session_seconds"],
    browser_tunnel_enabled: bool = DEFAULTS["browser_tunnel_enabled"],
    cloudflared_url: str = DEFAULTS["cloudflared_url"],
    cloudflared_sha256: str = DEFAULTS["cloudflared_sha256"],
) -> Solver:
    """Keep the authenticated browser tunnel next to the game in its Linux sandbox."""
    if not 1 <= port <= 65535 or session_seconds <= 0:
        raise ValueError("Use a valid TCP port and a positive session duration.")
    if game not in {"sts1", "sts2"}:
        raise ValueError(f"Unknown game: {game}")

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Start the sandbox-native desktop services and retain final diagnostics."""
        access_token = os.environ.get("STS_MANUAL_ACCESS_TOKEN")
        if browser_tunnel_enabled and (access_token is None or len(access_token) < 32):
            raise ValueError(
                "A browser tunnel requires a private access key of at least 32 characters."
            )
        environment = sandbox()
        backend_port = port + 1 if port < 65535 else port - 1
        config = {
            "port": port,
            "backend_port": backend_port,
            "session_seconds": session_seconds,
            "browser_tunnel_enabled": browser_tunnel_enabled,
            "cloudflared_url": cloudflared_url,
            "cloudflared_sha256": cloudflared_sha256,
            "access_token_sha256": hashlib.sha256(access_token.encode()).hexdigest()
            if browser_tunnel_enabled
            else None,
        }
        await checked_exec(
            [
                "bash",
                "-lc",
                "apt-get install -y --no-install-recommends novnc websockify python3-aiohttp >/tmp/sts-manual-install.log 2>&1",
            ],
            180,
        )
        await environment.write_file(
            "/opt/sts/manual_server.py",
            Path(__file__).with_name("manual_server.py").read_text(),
        )
        await environment.write_file("/opt/sts/manual-browser.json", json.dumps(config))
        await checked_exec(
            [
                "bash",
                "-lc",
                f"nohup websockify --web=/usr/share/novnc/ {backend_port} localhost:5900 >/tmp/sts-manual-vnc.log 2>&1 </dev/null &",
            ],
            30,
        )
        await checked_exec(
            [
                "bash",
                "-lc",
                "nohup python3 /opt/sts/manual_server.py /opt/sts/manual-browser.json >/tmp/sts-manual-proxy.log 2>&1 </dev/null & echo $! >/tmp/sts-manual-proxy.pid",
            ],
            30,
        )
        try:
            ready_pattern = (
                r"https://[-a-z0-9]+\.trycloudflare\.com"
                if browser_tunnel_enabled
                else "Sandbox desktop ready"
            )
            startup = await checked_exec(
                [
                    "bash",
                    "-lc",
                    (
                        "for attempt in $(seq 1 90); do "
                        f"if grep -qE '{ready_pattern}' /tmp/sts-manual-proxy.log; then "
                        "cat /tmp/sts-manual-proxy.log; exit 0; fi; "
                        "if [ -f /tmp/sts-manual-finished ]; then cat /tmp/sts-manual-proxy.log; exit 1; fi; "
                        "sleep 1; done; cat /tmp/sts-manual-proxy.log; exit 1"
                    ),
                ],
                100,
            )
            logger.info("Sandbox browser startup:\n%s", startup)
            urls = re.findall(r"https://[-a-z0-9]+\.trycloudflare\.com", startup)
            transcript().info(
                {
                    "manual_session_port": port,
                    "session_seconds": session_seconds,
                    "manual_session_url": urls[-1] if urls else None,
                }
            )
            with suppress(TimeoutError):
                await checked_exec(
                    [
                        "bash",
                        "-lc",
                        "while [ ! -f /tmp/sts-manual-finished ]; do sleep 2; done",
                    ],
                    session_seconds + 30,
                )
        finally:
            archive = (
                "mkdir -p /game/saves; tar -C /game -czf /tmp/sts-manual-profile.tar.gz preferences saves info.displayconfig"
                if game == "sts1"
                else "tar -C /root/.local/share/SlayTheSpire2 -czf /tmp/sts-manual-profile.tar.gz default"
            )
            result = await environment.exec(
                [
                    "bash",
                    "-lc",
                    "tail -n 200 /tmp/game.log /tmp/sts-manual-vnc.log /tmp/sts-manual-proxy.log; "
                    + archive,
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
    game: str = DEFAULTS["game"],
    port: int = DEFAULTS["port"],
    session_seconds: int = DEFAULTS["session_seconds"],
    browser_tunnel_enabled: bool = DEFAULTS["browser_tunnel_enabled"],
    cloudflared_url: str = DEFAULTS["cloudflared_url"],
    cloudflared_sha256: str = DEFAULTS["cloudflared_sha256"],
    **kwargs,
) -> Task:
    """Reuse either game's Linux sandbox for human debugging without model calls."""
    if game not in {"sts1", "sts2"}:
        raise ValueError(f"Unknown game: {game}")
    result = (first_combat if game == "sts1" else second_game)(**kwargs)
    return Task(
        name=f"{game}_manual_session",
        dataset=result.dataset,
        setup=result.setup,
        solver=manual_control(
            game=game,
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
            "manual_game": game,
            "purpose": "Human Linux desktop debugging; no model calls or benchmark score",
        },
        **default_run_config()["eval_config"],
    )
