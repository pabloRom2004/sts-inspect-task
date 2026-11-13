import asyncio
import json
import os
from pathlib import Path
from typing import Any

from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

from sts_hawk.state import RunState, observe

ASSETS = Path(__file__).parent / "assets"


async def checked_exec(command: list[str], timeout: int) -> str:
    """Run an infrastructure command, raising on failure instead of scoring zero."""
    result = await sandbox().exec(command, timeout=timeout)
    if not result.success:
        raise RuntimeError(
            f"Runtime command failed: {result.stderr[-4000:]} {result.stdout[-4000:]}"
        )
    return result.stdout


async def game_command(command: str, timeout: int) -> dict[str, Any]:
    """Query the host-only observer without exposing game state as a model tool."""
    response = await checked_exec(
        ["python3", "/opt/sts/observer.py", "client", command], timeout
    )
    result = json.loads(response)
    if result.get("error"):
        raise RuntimeError(f"Game observer failed: {result['error']}")
    return result


async def observe_game(timeout: int) -> RunState:
    """Refresh and persist the game's first-combat evidence."""
    history = RunState()
    observe(await game_command("STATE", timeout), history)
    return history


@solver
def prepare_game(
    character: str, ascension: int, seed: str, setup_timeout: int, observer_timeout: int
) -> Solver:
    """Install the Linux runtime and begin one seeded run before agent elicitation."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        """Prepare the sandbox and require an actual ready game before returning."""
        asset_url = os.environ["STS_ASSET_URL"]
        await checked_exec(
            ["mkdir", "-p", "/opt/sts", "/opt/inspect/tool"], observer_timeout
        )
        await sandbox().write_file("/opt/sts/asset-url", asset_url)
        for name in ["install.sh", "start.sh", "observer.py"]:
            await sandbox().write_file(f"/opt/sts/{name}", (ASSETS / name).read_text())
        for source in (ASSETS / "computer").glob("*.py"):
            await sandbox().write_file(
                f"/opt/inspect/tool/{source.name}", source.read_text()
            )
        await checked_exec(["bash", "/opt/sts/install.sh"], setup_timeout)
        await checked_exec(
            [
                "bash",
                "-lc",
                "nohup bash /opt/sts/start.sh >/tmp/sts-startup.log 2>&1 </dev/null &",
            ],
            observer_timeout,
        )
        async with asyncio.timeout(setup_timeout):
            while True:
                ready = await sandbox().exec(
                    ["test", "-S", "/tmp/sts-observer.sock"], timeout=observer_timeout
                )
                if ready.success:
                    break
                failed = await sandbox().exec(
                    ["test", "-f", "/tmp/sts-failed"], timeout=observer_timeout
                )
                if failed.success:
                    diagnostics = await checked_exec(
                        ["tail", "-60", "/tmp/game.log"], observer_timeout
                    )
                    raise RuntimeError(f"Game exited during startup: {diagnostics}")
                await asyncio.sleep(1)
        started = await game_command(
            f"START {character} {ascension} {seed}", observer_timeout
        )
        async with asyncio.timeout(observer_timeout):
            while not started.get("in_game") and not started.get("error"):
                await asyncio.sleep(0.25)
                started = await game_command("STATE", observer_timeout)
        if not started.get("in_game"):
            raise RuntimeError(f"Game failed to start: {started}")
        actual = started["game_state"].get("ascension_level")
        if actual != ascension:
            raise RuntimeError(f"Expected ascension {ascension}, observed {actual}")
        observe(started, RunState())
        return state

    return solve
