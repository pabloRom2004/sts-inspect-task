import pytest
from inspect_ai.tool import ToolDef, ToolError
from inspect_ai.util import ExecResult

from sts_hawk.desktop import desktop_tool


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments, expected",
    [
        ({}, "required"),
        ({"actions": []}, "non-empty"),
        ({"actions": [{"action": "zoom", "region": [0, 0, 100]}]}, "region"),
        ({"actions": [{"action": "mouse_move", "coordinate": 100}]}, "coordinate"),
        (
            {"actions": [{"action": "mouse_move", "coordinate": {"x": 10, "y": 20}}]},
            "coordinate",
        ),
        ({"actions": [{"action": "key", "text": ["Return"]}]}, "text"),
        ({"actions": [{"action": "hold_key", "text": "Shift"}]}, "duration"),
        ({"actions": [{"action": "wait", "duration": float("nan")}]}, "finite"),
        (
            {"actions": [{"action": "left_mouse_down", "coordinate": [10, 20]}]},
            "use mouse_move first",
        ),
        (
            {"action": "screenshot", "actions": [{"action": "screenshot"}]},
            "not both",
        ),
    ],
)
async def test_malformed_calls_are_recoverable(arguments, expected):
    """Validate model-controlled nested fields before reaching any sandbox code."""
    with pytest.raises(ToolError, match=expected):
        await desktop_tool(3, 180)(**arguments)


@pytest.mark.asyncio
async def test_invalid_later_action_prevents_partial_batch(monkeypatch):
    """Reject a malformed batch before executing its first, otherwise valid click."""
    import inspect_ai.tool._tools._computer._common as common

    async def unexpected_sandbox_access():
        """Fail if prevalidation allows any input through."""
        pytest.fail("A malformed batch executed an earlier action")

    monkeypatch.setattr(common, "computer_sandbox", unexpected_sandbox_access)
    with pytest.raises(ToolError, match="Action 2, region"):
        await desktop_tool(3, 180)(
            actions=[
                {"action": "left_click", "coordinate": [100, 100]},
                {"action": "zoom", "region": [0, 0, 100]},
            ]
        )


@pytest.mark.asyncio
async def test_valid_call_and_unexpected_failure_passthrough(monkeypatch):
    """Keep stock execution, image handling, and fatal infrastructure reporting."""
    from types import SimpleNamespace

    import inspect_ai.log._samples as samples
    import inspect_ai.tool._tools._computer._common as common

    monkeypatch.setattr(
        samples, "sample_active", lambda: SimpleNamespace(sample=SimpleNamespace(id=1))
    )

    commands = []

    class TransportSandbox:
        """Capture the stock backend protocol without desktop input."""

        async def exec(self, cmd, **kwargs):
            """Return success once, then an unexpected process failure."""
            commands.append(cmd)
            if len(commands) == 1:
                return ExecResult(True, 0, '{"output":"ok","error":null}', "")
            return ExecResult(False, 1, "", "display connection lost")

    sandbox = TransportSandbox()

    async def computer_sandbox():
        """Bind the stock transport to this test sandbox."""
        return sandbox

    monkeypatch.setattr(common, "computer_sandbox", computer_sandbox)
    tool = desktop_tool(3, 180)
    assert ToolDef(tool).name == "desktop"
    assert ToolDef(tool).model_input is not None
    await tool(actions=[{"action": "wait", "duration": 0.5}])
    assert commands[0][-3:] == ["wait", "--duration", "0.5"]
    with pytest.raises(RuntimeError, match="display connection lost"):
        await tool(action="screenshot")
