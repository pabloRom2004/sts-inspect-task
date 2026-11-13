from inspect_ai.agent import AgentState, as_solver, react
from inspect_ai.model import CompactionAuto
from inspect_ai.solver import Solver, solver
from inspect_ai.tool import computer

from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import observe_game
from sts_hawk.tools import wiki

DEFAULTS = default_run_config()["solver"]["args"]


@solver
def visual_agent(
    max_screenshots: int | None = DEFAULTS["max_screenshots"],
    tool_timeout: int | None = DEFAULTS["tool_timeout"],
    observer_timeout: int = DEFAULTS["observer_timeout"],
    compaction_threshold: float = DEFAULTS["compaction_threshold"],
) -> Solver:
    """Use stock Inspect ReAct and computer tools with an automatic combat stop."""

    async def continue_playing(state: AgentState) -> bool:
        """End before another generation after a first-combat win or death."""
        history = await observe_game(observer_timeout)
        return not (history.won or history.died)

    return as_solver(
        react(
            tools=[
                computer(max_screenshots=max_screenshots, timeout=tool_timeout),
                wiki(),
            ],
            compaction=CompactionAuto(threshold=compaction_threshold),
            on_continue=continue_playing,
        )
    )
