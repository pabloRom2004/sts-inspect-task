from inspect_ai.agent import AgentSubmit, as_solver, react
from inspect_ai.solver import Solver, solver
from inspect_ai.tool import ToolDef, bash, python, tool_with

from sts_hawk.compaction import ScreenshotCompaction
from sts_hawk.desktop import desktop_tool
from sts_hawk.inspect_compat import apply_hawk_image_counter_fix
from sts_hawk.run_config import default_run_config
from sts_hawk.tools import submit_floor

DEFAULTS = default_run_config()["solver"]["args"]


@solver
def visual_agent(
    max_screenshots: int | None = DEFAULTS["max_screenshots"],
    tool_timeout: int | None = DEFAULTS["tool_timeout"],
    compaction_threshold: float = DEFAULTS["compaction_threshold"],
) -> Solver:
    """Use stock ReAct with desktop, shell and Python tools."""
    apply_hawk_image_counter_fix()
    # Keep function calling on stateless Responses API providers.
    desktop = desktop_tool(max_screenshots=max_screenshots, timeout=tool_timeout)
    shell = bash(timeout=tool_timeout)
    shell = tool_with(
        shell,
        description=ToolDef(shell).description
        + "\nOffline Slay the Spire wiki: /opt/sts/wiki.md.",
    )
    return as_solver(
        react(
            tools=[
                desktop,
                shell,
                python(timeout=tool_timeout),
            ],
            submit=AgentSubmit(
                name="submit",
                tool=submit_floor(),
                answer_only=True,
                keep_in_messages=True,
            ),
            compaction=ScreenshotCompaction(desktop, threshold=compaction_threshold),
        )
    )
