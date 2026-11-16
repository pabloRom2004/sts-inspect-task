"""Run native Codex inside the game sandbox through Inspect's model bridge."""

import json

from inspect_ai.agent import Agent, AgentState, BridgedToolsSpec, agent, as_solver
from inspect_ai.log import transcript
from inspect_ai.model import (
    ChatMessage,
    ContentImage,
    ContentText,
    GenerateConfig,
    GenerateInput,
    Model,
    ModelOutput,
    get_model,
)
from inspect_ai.model._generate_config import active_generate_config
from inspect_ai.solver import Solver
from inspect_ai.tool import Tool, ToolChoice, ToolInfo, tool
from inspect_ai.util import StoreModel, sandbox, store_as

from sts_hawk.desktop import desktop_tool
from sts_hawk.tools import submit_floor


class FloorSubmission(StoreModel):
    """Retain the model's unverified floor report across bridged calls."""

    max_floor: int | None = None
    native_exit_without_submit: bool = False


@tool(name="submit")
def codex_submit() -> Tool:
    """Record the same integer submission used by the ReAct harness."""
    submit = submit_floor()

    async def execute(max_floor: int) -> str:
        """Finish the run by reporting the maximum floor reached.

        Args:
            max_floor: The maximum floor number you reached during this run.
        """
        result = await submit(max_floor)
        store_as(FloorSubmission).max_floor = max_floor
        return result

    return execute


def prune_images(messages: list[ChatMessage], maximum: int | None) -> list[ChatMessage]:
    """Copy the request while replacing images older than the retained window."""
    if maximum is None:
        return messages
    remaining = maximum
    result = []
    for message in reversed(messages):
        if isinstance(message.content, str):
            result.append(message)
            continue
        content = []
        for item in reversed(message.content):
            if isinstance(item, ContentImage):
                if remaining > 0:
                    remaining -= 1
                else:
                    item = ContentText(text="[Earlier screenshot omitted.]")
            content.append(item)
        result.append(message.model_copy(update={"content": list(reversed(content))}))
    return list(reversed(result))


def codex_solver(
    *,
    version: str,
    model_config: str,
    context_window: int,
    cwd: str,
    home_dir: str,
    max_screenshots: int | None,
    tool_timeout: int | None,
    compaction_threshold: int,
) -> Solver:
    """Build a native Codex solver with explicit context and image retention."""
    if version in {"auto", "sandbox", "latest"} or not version:
        raise ValueError("Codex requires an exact version for reproducible runs.")
    if (
        not isinstance(compaction_threshold, int)
        or context_window <= 0
        or not 0 < compaction_threshold < context_window
    ):
        raise ValueError(
            "Codex compaction_threshold must be an integer token count within context_window."
        )
    if max_screenshots is not None and max_screenshots < 1:
        raise ValueError("max_screenshots must be positive or None.")

    async def filter_request(
        model: Model,
        messages: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice | None,
        config: GenerateConfig,
    ) -> GenerateInput | ModelOutput:
        """Retain recent images and end submitted runs without another paid request."""
        floor = store_as(FloorSubmission).max_floor
        if floor is not None:
            return ModelOutput.from_content(str(model.name), str(floor))
        return GenerateInput(
            prune_images(messages, max_screenshots), tools, tool_choice, config
        )

    @agent
    def native() -> Agent:
        """Defer native adapter construction until the effective model config exists."""

        async def execute(state: AgentState) -> AgentState:
            """Run Codex once with native shell tools and bridged desktop and submit."""
            try:
                from inspect_swe import codex_cli
            except ImportError as ex:
                raise RuntimeError(
                    "Install sts-hawk-smoke[codex] with Inspect >=0.3.289."
                ) from ex

            result = await sandbox().exec(["mkdir", "-p", cwd, home_dir])
            if not result.success:
                raise RuntimeError(f"Cannot prepare Codex workspace: {result.stderr}")
            config = get_model().config.merge(active_generate_config())
            overrides = {
                "model_context_window": str(context_window),
                "agents.enabled": "false",
                "features.multi_agent_v2": "false",
                "model_auto_compact_token_limit": str(int(compaction_threshold)),
                "model_auto_compact_token_limit_scope": '"total"',
            }
            if config.reasoning_effort is not None:
                overrides["model_reasoning_effort"] = json.dumps(
                    config.reasoning_effort
                )
            transcript().info(
                {
                    "harness": "codex",
                    "version": version,
                    "model": str(get_model()),
                    "model_config": model_config,
                    "config_overrides": overrides,
                    "max_tokens": config.max_tokens,
                    "max_screenshots": max_screenshots,
                },
                source="sts_hawk.native_codex",
            )
            codex = codex_cli(
                version=version,
                model_config=model_config,
                cwd=cwd,
                home_dir=home_dir,
                sandbox="default",
                bridged_tools=[
                    BridgedToolsSpec(
                        name="game",
                        tools=[
                            desktop_tool(max_screenshots=None, timeout=tool_timeout),
                            codex_submit(),
                        ],
                        # Luna's native Codex tools use code mode rather than
                        # individually proposed MCP function calls.
                        require_proposal=False,
                    )
                ],
                filter=filter_request,
                config_overrides=overrides,
                web_search="disabled",
                goals=False,
            )
            state = await codex(state)
            floor = store_as(FloorSubmission).max_floor
            if floor is None:
                store_as(FloorSubmission).native_exit_without_submit = True
                transcript().info(
                    {"submitted": False, "outcome": "native_exit_without_submit"},
                    source="sts_hawk.native_codex",
                )
            else:
                state.output = ModelOutput.from_content(
                    str(get_model().name), str(floor)
                )
            return state

        return execute

    return as_solver(native())
