from typing import Any, Literal

from inspect_ai.agent import AgentSubmit, as_solver, react
from inspect_ai.solver import Solver, solver
from inspect_ai.tool import ToolDef, bash, python, tool_with
from inspect_ai.util import store

from sts_hawk.compaction import ScreenshotCompaction, ScreenshotSummaryCompaction
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
    harness: Literal["react", "codex"] = DEFAULTS["harness"],
    codex: dict[str, Any] = DEFAULTS["codex"],
    wiki_path: str | None = DEFAULTS["wiki_path"],
    tool_profile: Literal["auto", "standard", "epoch"] = DEFAULTS["tool_profile"],
) -> Solver:
    """Select ReAct or native Codex while retaining the same game and submission."""
    if harness not in {"react", "codex"}:
        raise ValueError(f"Unknown harness: {harness!r}; expected react or codex.")
    if harness == "codex" and tool_profile != "epoch":
        from sts_hawk.native_codex import codex_solver

        native = codex_solver(
            max_screenshots=max_screenshots, tool_timeout=tool_timeout, **codex
        )

        async def legacy_codex(state, generate):
            """Keep the historical adapter from silently replacing replay-profile tools."""
            if state.metadata.get("epoch_prompt"):
                raise ValueError("The replay-based tool profile uses Inspect ReAct.")
            return await native(state, generate)

        return legacy_codex
    if tool_profile == "auto":

        async def dispatch(state, generate):
            """Choose tools from the task's prompt contract at sample execution."""
            selected = "epoch" if state.metadata.get("epoch_prompt") else "standard"
            return await visual_agent(
                max_screenshots=max_screenshots,
                tool_timeout=tool_timeout,
                compaction_threshold=compaction_threshold,
                harness=harness,
                codex=codex,
                wiki_path=wiki_path,
                tool_profile=selected,
            )(state, generate)

        return dispatch
    if tool_profile == "epoch":
        if harness != "react":
            raise ValueError("The replay-based tool profile uses Inspect ReAct.")
        from sts_hawk.epoch_tools import epoch_tools

        async def play_epoch(state, generate):
            """Run the captured game tool profile with per-sample notes and image history."""
            apply_hawk_image_counter_fix()
            tools = epoch_tools(
                max_screenshots, tool_timeout, state.metadata["desktop_height"]
            )

            async def continue_run(agent_state):
                """Stop immediately after the captured give_up tool is called."""
                return store().get("sts_give_up") is None

            return await as_solver(
                react(
                    prompt=None,
                    tools=tools,
                    on_continue=continue_run,
                    submit=AgentSubmit(
                        name="submit",
                        tool=submit_floor(),
                        answer_only=True,
                        keep_in_messages=True,
                    ),
                    compaction=ScreenshotSummaryCompaction(
                        tools, threshold=compaction_threshold
                    ),
                )
            )(state, generate)

        return play_epoch
    if tool_profile != "standard":
        raise ValueError(f"Unknown tool profile: {tool_profile}")
    apply_hawk_image_counter_fix()
    # Keep function calling on stateless Responses API providers.
    desktop = desktop_tool(max_screenshots=max_screenshots, timeout=tool_timeout)
    shell = bash(timeout=tool_timeout)
    if wiki_path is not None:
        shell = tool_with(
            shell,
            description=ToolDef(shell).description
            + f"\nOffline Slay the Spire wiki: {wiki_path}.",
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
