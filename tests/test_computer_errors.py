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
