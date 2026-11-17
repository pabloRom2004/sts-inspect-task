"""Check the replay action profile's image limit at the serialized API boundary."""

import pytest
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    ContentImage,
    GenerateConfig,
    get_model,
)
from inspect_ai.tool import ToolCall, ToolDef

from sts_hawk.epoch_tools import epoch_tools

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jfLQAAAAASUVORK5CYII="


@pytest.mark.asyncio
async def test_replay_profile_limits_real_request_to_49_images(monkeypatch):
    """Prune repeated screenshots across different action tools before Responses serialization."""
    import sts_hawk.epoch_tools as module

    async def backend(**arguments):
        """Return the same valid PNG to exercise distinct observations with identical pixels."""
        return [ContentImage(image=PNG)]

    monkeypatch.setattr(module, "desktop_tool", lambda **kwargs: backend)
    tools = epoch_tools(49, 180, 720)
    by_name = {ToolDef(tool).name: tool for tool in tools}
    messages = [ChatMessageUser(content="Inspect the test history.")]
    for index in range(60):
        name = "screenshot" if index % 2 == 0 else "queue_actions"
        arguments = {"intent": "Observe the test frame."}
        if name == "queue_actions":
            arguments["steps"] = [{"do": "mouse_move", "x": 1, "y": 1}]
        content = await by_name[name](**arguments)
        messages += [
            ChatMessageAssistant(
                content="",
                tool_calls=[
                    ToolCall(id=f"frame-{index}", function=name, arguments=arguments)
                ],
            ),
            ChatMessageTool(
                tool_call_id=f"frame-{index}", function=name, content=content
            ),
        ]

    class RequestCaptured(BaseException):
        """Stop before any external network request can occur."""

    model = get_model(
        "openrouter/openai/gpt-6-luna",
        api_key="fixture-only",
        responses_api=True,
        responses_store=False,
    )
    captured = {}

    async def capture_request(**arguments):
        """Capture exactly what the Responses SDK would send."""
        captured.update(arguments)
        raise RequestCaptured

    monkeypatch.setattr(model.api.client.responses, "create", capture_request)
    with pytest.raises(RequestCaptured):
        await model.generate(
            messages,
            tools=tools,
            config=GenerateConfig(max_tokens=128000, reasoning_effort="max"),
        )
    count = sum(
        block.get("type") == "input_image"
        for message in captured["input"]
        for block in message.get("content", [])
        if isinstance(block, dict)
    )
    assert count == 49
    assert captured["reasoning"]["effort"] == "max"
    assert captured["max_output_tokens"] == 128000
    assert captured["store"] is False
    assert (
        sum(
            isinstance(block, ContentImage)
            for message in messages
            if isinstance(message.content, list)
            for block in message.content
        )
        == 60
    )
    from inspect_ai.model import CompactionSummary

    from sts_hawk.compaction import ScreenshotSummaryCompaction

    compacted = {}
    sentinel = object()

    async def capture_compaction(self, model, messages, tools):
        """Inspect the image history immediately before the stock summary strategy."""
        compacted["messages"] = messages
        return sentinel

    monkeypatch.setattr(CompactionSummary, "compact_outcome", capture_compaction)
    policy = ScreenshotSummaryCompaction(tools, threshold=300000)
    assert await policy.compact_outcome(model, messages, []) is sentinel
    assert (
        sum(
            isinstance(block, ContentImage)
            for message in compacted["messages"]
            if isinstance(message.content, list)
            for block in message.content
        )
        == 49
    )
