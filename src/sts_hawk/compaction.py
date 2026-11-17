"""Keep the desktop screenshot budget during native or summary compaction."""

import inspect_ai.model._model as inspect_model
from inspect_ai.model import (
    ChatMessage,
    CompactionAuto,
    CompactionResult,
    CompactionSummary,
    Model,
)
from inspect_ai.tool import Tool, ToolDef, ToolInfo


class ScreenshotCompaction(CompactionAuto):
    """Apply the desktop tool's retention policy before stock automatic compaction."""

    def __init__(self, desktop: Tool, threshold: float) -> None:
        """Reuse the same desktop policy and context threshold as normal turns."""
        super().__init__(threshold=threshold)
        self._desktop = ToolDef(desktop)

    async def compact_outcome(
        self, model: Model, messages: list[ChatMessage], tools: list[ToolInfo]
    ) -> CompactionResult:
        """Prune replay images on a copy before either compaction request path."""
        messages = inspect_model.resolve_tool_model_input([self._desktop], messages, {})
        return await super().compact_outcome(model, messages, tools)


class ScreenshotSummaryCompaction(CompactionSummary):
    """Match the captured replay's summary policy while retaining the image budget."""

    def __init__(self, tools: list[Tool], threshold: float) -> None:
        """Use summary compaction and persistent per-run memory at the configured threshold."""
        super().__init__(threshold=threshold, memory=True)
        self._tools = [ToolDef(tool) for tool in tools]

    async def compact_outcome(
        self, model: Model, messages: list[ChatMessage], tools: list[ToolInfo]
    ) -> CompactionResult:
        """Apply all action tools' shared image filter before the summary request."""
        messages = inspect_model.resolve_tool_model_input(self._tools, messages, {})
        return await super().compact_outcome(model, messages, tools)
