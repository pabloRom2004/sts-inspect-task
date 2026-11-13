"""Prepare the Linux runtime without a game-state bridge."""

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
def prepare_game(setup_timeout: int, command_timeout: int) -> Solver:
    """Install the runtime and signal the game container to launch."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Copy stock computer tools and launch the privately supplied game."""
        await checked_exec(
            ["mkdir", "-p", "/opt/sts", "/opt/inspect/tool"], command_timeout
        )
        await sandbox().write_file("/opt/sts/asset-url", os.environ["STS_ASSET_URL"])
        for name in ["install.sh", "start.sh"]:
            await sandbox().write_file(f"/opt/sts/{name}", (ASSETS / name).read_text())
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
