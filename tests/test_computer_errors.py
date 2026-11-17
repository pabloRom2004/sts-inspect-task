import importlib
import json
import logging
import runpy
import sys

import pytest

from sts_hawk.runtime import ASSETS


@pytest.fixture
def backend_main(monkeypatch):
    """Load the actual vendored backend without starting a desktop session."""
    monkeypatch.syspath_prepend(str(ASSETS / "computer"))

    def test_logger(level):
        """Replace the Linux PID 1 log sink during host-side unit tests."""
        return logging.getLogger("computer-backend-test")

    monkeypatch.setattr(importlib.import_module("_logger"), "setup_logger", test_logger)
    return runpy.run_path(ASSETS / "computer" / "computer_tool.py")["main"]


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (["wait", "--duration", "soon"], "duration"),
        (["wait", "--duration", "-1"], "non-negative"),
        (["wait", "--duration", "nan"], "finite"),
        (["hold_key", "--text", "Shift_L", "--duration", "inf"], "finite"),
        (["wait"], "--duration"),
        (["mouse_move", "--coordinate", "bad", "100"], "coordinate"),
        (["mouse_move", "--coordinate", "10"], "coordinate"),
        (
            ["scroll", "--scroll_amount", "1", "--scroll_direction", "diagonal"],
            "invalid choice",
        ),
        (["not_an_action"], "invalid choice"),
        (["screenshot", "--unexpected"], "unrecognized arguments"),
    ],
)
def test_argument_errors_return_json(
    backend_main, monkeypatch, capsys, arguments, expected
):
    """Return malformed action arguments as tool errors before invoking X11."""
    monkeypatch.setattr(sys, "argv", ["computer_tool", *arguments])

    async def unexpected_execution(args):
        """Fail if invalid input reaches desktop execution."""
        raise AssertionError("Invalid arguments reached X11")

    monkeypatch.setitem(
        backend_main.__globals__, "execute_action", unexpected_execution
    )
    backend_main()
    result = json.loads(capsys.readouterr().out)
    assert expected in result["error"]
    assert result["output"] is None and result["base64_image"] is None


@pytest.mark.parametrize("error_type", ["ComputerToolError", "X11CoordinateError"])
def test_action_input_errors_return_json(backend_main, monkeypatch, capsys, error_type):
    """Preserve recoverability for explicit action and coordinate errors."""
    monkeypatch.setattr(sys, "argv", ["computer_tool", "screenshot"])

    async def invalid_action(args):
        """Simulate a correctable error detected after parsing."""
        raise backend_main.__globals__[error_type]("correct the action")

    monkeypatch.setitem(backend_main.__globals__, "execute_action", invalid_action)
    backend_main()
    assert json.loads(capsys.readouterr().out)["error"] == "correct the action"


def test_unexpected_backend_failure_remains_fatal(backend_main, monkeypatch, capsys):
    """Keep infrastructure and programming failures distinct from model input errors."""
    monkeypatch.setattr(sys, "argv", ["computer_tool", "screenshot"])

    async def broken_backend(args):
        """Simulate an unexpected desktop backend failure."""
        raise RuntimeError("display connection lost")

    monkeypatch.setitem(backend_main.__globals__, "execute_action", broken_backend)
    with pytest.raises(SystemExit) as caught:
        backend_main()
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert not captured.out and "display connection lost" in captured.err


def test_backend_timeout_returns_recovery_guidance(backend_main, monkeypatch, capsys):
    """Report action timeouts without promising that input had no side effects."""
    monkeypatch.setattr(sys, "argv", ["computer_tool", "screenshot"])

    async def stalled_action(args):
        """Simulate a command exceeding the backend's deadline."""
        raise TimeoutError("command exceeded deadline")

    monkeypatch.setitem(backend_main.__globals__, "execute_action", stalled_action)
    backend_main()
    error = json.loads(capsys.readouterr().out)["error"]
    assert "timed out" in error and "take a screenshot before retrying" in error


@pytest.mark.asyncio
async def test_timeout_kills_child_commands(tmp_path):
    """A timed-out shell must not leave its action subprocess running afterward."""
    import asyncio
    import shlex

    run = runpy.run_path(ASSETS / "computer" / "_run.py")["run"]
    started = tmp_path / "started"
    leaked = tmp_path / "leaked"
    code = (
        "from pathlib import Path; import time; "
        f"Path({str(started)!r}).touch(); time.sleep(0.5); "
        f"Path({str(leaked)!r}).touch()"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}; true"
    with pytest.raises(TimeoutError, match="timed out"):
        await run(command, timeout=0.2)
    assert started.exists(), "The action must start before testing its cleanup"
    await asyncio.sleep(0.5)
    assert not leaked.exists()


@pytest.mark.asyncio
async def test_drag_releases_button_after_move_failure(monkeypatch):
    """A failed drag must release the mouse button before propagating the error."""
    monkeypatch.syspath_prepend(str(ASSETS / "computer"))
    backend = importlib.import_module("_x11_client")
    monkeypatch.setenv("WIDTH", "1280")
    monkeypatch.setenv("HEIGHT", "800")
    client = backend.X11Client()
    client._drag_step_delay = 0
    commands = []

    async def shell(command, take_screenshot=True):
        """Fail during held movement while recording the button cleanup."""
        commands.append(command)
        if "mousemove --sync 324 495" in command:
            raise RuntimeError("movement failed")
        return backend.ToolResult(output="", error="")

    monkeypatch.setattr(client, "_shell", shell)
    with pytest.raises(RuntimeError, match="movement failed"):
        await client.left_click_drag((500, 690), (324, 495))
    assert any("mousedown 1" in command for command in commands)
    assert commands[-1].endswith("mouseup 1")


@pytest.mark.asyncio
async def test_drag_validates_destination_before_press(monkeypatch):
    """An invalid drag destination must not leave a button pressed."""
    monkeypatch.syspath_prepend(str(ASSETS / "computer"))
    backend = importlib.import_module("_x11_client")
    monkeypatch.setenv("WIDTH", "1280")
    monkeypatch.setenv("HEIGHT", "800")
    client = backend.X11Client()

    async def unexpected_shell(command, take_screenshot=True):
        """Reject any input before coordinate validation completes."""
        raise AssertionError("Invalid coordinates reached X11")

    monkeypatch.setattr(client, "_shell", unexpected_shell)
    with pytest.raises(backend.X11CoordinateError):
        await client.left_click_drag((500, 690), (1280, 495))


@pytest.mark.asyncio
async def test_drag_preserves_intermediate_command_errors(monkeypatch):
    """Return movement errors even when releasing the mouse succeeds."""
    monkeypatch.syspath_prepend(str(ASSETS / "computer"))
    backend = importlib.import_module("_x11_client")
    monkeypatch.setenv("WIDTH", "1280")
    monkeypatch.setenv("HEIGHT", "800")
    client = backend.X11Client()
    client._drag_step_delay = 0

    async def shell(command, take_screenshot=True):
        """Return an error for held movement without raising an exception."""
        error = "movement failed" if "mousemove --sync 324 495" in command else ""
        return backend.ToolResult(output="", error=error)

    async def screenshot():
        """Avoid X11 while preserving the normal final screenshot contract."""
        return "test-image"

    monkeypatch.setattr(client, "_shell", shell)
    monkeypatch.setattr(client, "_take_screenshot_after_delay", screenshot)
    result = await client.left_click_drag((500, 690), (324, 495))
    assert result.error == "movement failed"
    assert result.base64_image == "test-image"
