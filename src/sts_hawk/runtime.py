"""Prepare the Linux runtime without a game-state bridge."""

import base64
import hashlib
import logging
import os
from pathlib import Path

from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

ASSETS = Path(__file__).parent / "assets"
logger = logging.getLogger(__name__)


async def checked_exec(command: list[str], timeout: int) -> str:
    """Run a setup command and keep infrastructure failures as errors."""
    result = await sandbox().exec(command, timeout=timeout)
    if not result.success:
        raise RuntimeError(
            f"Runtime setup failed (exit {result.returncode}): "
            f"{result.stderr[-4000:]} {result.stdout[-4000:]}"
        )
    return result.stdout


@solver
def prepare_game(
    setup_timeout: int,
    command_timeout: int,
    game: str = "sts1",
    frame_rate_limit: int | None = None,
    processor_count: int | None = None,
    renderer_threads: int | None = None,
    java_heap_mb: int | None = None,
) -> Solver:
    """Install the runtime and signal the game container to launch."""

    if game not in {"sts1", "sts2"}:
        raise ValueError(f"Unknown game: {game}")
    if (
        processor_count is None
        or processor_count <= 0
        or renderer_threads is None
        or renderer_threads <= 0
    ):
        raise ValueError(
            "Runtime setup requires positive processor and renderer thread counts."
        )
    if game == "sts1" and (java_heap_mb is None or java_heap_mb <= 0):
        raise ValueError("StS1 setup requires a positive Java heap limit.")
    runtime_assets = ASSETS if game == "sts1" else ASSETS / "sts2"

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Copy stock computer tools and launch the privately supplied game."""
        await checked_exec(
            ["mkdir", "-p", "/opt/sts", "/opt/inspect/tool"], command_timeout
        )
        await sandbox().write_file("/opt/sts/asset-url", os.environ["STS_ASSET_URL"])
        await sandbox().write_file("/opt/sts/processor-count", str(processor_count))
        await sandbox().write_file("/opt/sts/renderer-threads", str(renderer_threads))
        if game == "sts1":
            await sandbox().write_file("/opt/sts/java-heap-mb", str(java_heap_mb))
        if game == "sts2":
            if frame_rate_limit is None:
                raise ValueError("StS2 setup requires an explicit frame rate limit.")
            await sandbox().write_file(
                "/opt/sts/frame-rate-limit", str(frame_rate_limit)
            )
        if game == "sts2":
            for variable, filename, metadata_key in [
                ("STS_PROFILE_BASE64", "profile.tar.gz", "sts2_profile_sha256"),
                (
                    "STS_RUNTIME_OVERLAY_BASE64",
                    "runtime-overlay.tar.gz",
                    "sts2_runtime_overlay_sha256",
                ),
            ]:
                if encoded := os.environ.get(variable):
                    data = base64.b64decode(encoded, validate=True)
                    await sandbox().write_file(f"/opt/sts/{filename}", data)
                    state.metadata[metadata_key] = hashlib.sha256(data).hexdigest()
        for name in ["install.sh", "start.sh"]:
            await sandbox().write_file(
                f"/opt/sts/{name}", (runtime_assets / name).read_text()
            )
        if game == "sts1":
            await sandbox().write_file(
                "/opt/sts/wiki.md", (ASSETS / "wiki.md").read_text()
            )
        for source in (ASSETS / "computer").glob("*.py"):
            await sandbox().write_file(
                f"/opt/inspect/tool/{source.name}", source.read_text()
            )
        logger.info("Installing the runtime and private game archive")
        await checked_exec(["bash", "/opt/sts/install.sh"], setup_timeout)
        logger.info("Signaling the game container to start")
        await checked_exec(
            ["bash", "-lc", "touch /tmp/sts-runtime-ready; echo game-launch-triggered"],
            command_timeout,
        )
        logger.info(
            "Game launch triggered; the computer tool will wait for the display"
        )
        return state

    return solve
