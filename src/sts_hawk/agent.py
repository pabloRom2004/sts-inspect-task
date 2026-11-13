from inspect_ai.agent import AgentSubmit, as_solver, react
from inspect_ai.model import CompactionAuto
from inspect_ai.solver import Solver, solver
from inspect_ai.tool import computer

from sts_hawk.run_config import default_run_config
from sts_hawk.tools import submit_floor, wiki

DEFAULTS = default_run_config()["solver"]["args"]


@solver
def visual_agent(
    max_screenshots: int | None = DEFAULTS["max_screenshots"],
    tool_timeout: int | None = DEFAULTS["tool_timeout"],
    compaction_threshold: float = DEFAULTS["compaction_threshold"],
) -> Solver:
    """Use stock Inspect ReAct with computer input and the offline wiki."""
    return as_solver(
        react(
            tools=[
                computer(max_screenshots=max_screenshots, timeout=tool_timeout),
                wiki(),
            ],
            submit=AgentSubmit(
                name="submit",
                tool=submit_floor(),
                answer_only=True,
                keep_in_messages=True,
            ),
            compaction=CompactionAuto(threshold=compaction_threshold),
        )
    )
