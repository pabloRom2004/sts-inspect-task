"""Run the replay action profile through real Docker/X11 with scripted inference."""

import json
import os

import pytest
import yaml
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentImage, ModelOutput, get_model
from inspect_ai.solver import solver
from inspect_ai.util import sandbox

from sts_hawk.runtime import ASSETS, checked_exec
from sts_hawk.task import first_combat


@pytest.mark.skipif(
    os.environ.get("STS_EPOCH_DOCKER_TEST") != "1",
    reason="Explicit bounded Docker transport check",
)
def test_epoch_docker_actions(tmp_path):
    """Exercise actual X11 inputs, screenshot capture, notes and terminal reporting."""
    compose = tmp_path / "compose.yaml"
    compose.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "default": {
                        "image": "local/sts-hawk-os:0.2.4",
                        "platform": "linux/amd64",
                        "entrypoint": ["/bin/bash", "-lc"],
                        "command": ["sleep infinity"],
                        "cpus": 1,
                        "mem_limit": "1g",
                        "environment": {
                            "DISPLAY": ":99",
                            "DISPLAY_NUM": "99",
                            "WIDTH": "1280",
                            "HEIGHT": "720",
                        },
                    }
                }
            }
        )
    )

    @solver
    def display_fixture():
        """Prepare a blank real X display without installing or launching the game."""

        async def setup(state, generate):
            """Install the production computer backend and start the bounded display."""
            await checked_exec(["mkdir", "-p", "/opt/inspect/tool"], 30)
            for source in (ASSETS / "computer").glob("*.py"):
                await sandbox().write_file(
                    f"/opt/inspect/tool/{source.name}", source.read_text()
                )
            await checked_exec(
                [
                    "bash",
                    "-lc",
                    "Xvnc :99 -geometry 1280x720 -depth 24 -SecurityTypes None >/tmp/xvnc.log 2>&1 &",
                ],
                30,
            )
            await checked_exec(
                [
                    "bash",
                    "-lc",
                    "for i in $(seq 1 40); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.25; done; xdpyinfo >/dev/null; touch /tmp/xfce_started",
                ],
                30,
            )
            await sandbox().write_file(
                "/tmp/observe_pointer.py",
                """import ctypes, json, time
from pathlib import Path
x = ctypes.CDLL('libX11.so.6')
x.XOpenDisplay.restype = ctypes.c_void_p
d = x.XOpenDisplay(None)
x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x.XDefaultRootWindow.restype = ctypes.c_ulong
root = x.XDefaultRootWindow(d)
x.XQueryPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_uint)]
root_return, child = ctypes.c_ulong(), ctypes.c_ulong()
rx, ry, wx, wy, mask = (ctypes.c_int(), ctypes.c_int(), ctypes.c_int(),
    ctypes.c_int(), ctypes.c_uint())
with open('/tmp/pointer_frames.jsonl', 'w', buffering=1) as out:
    Path('/tmp/pointer_monitor_ready').touch()
    while True:
        x.XQueryPointer(d, root, ctypes.byref(root_return), ctypes.byref(child),
            ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx),
            ctypes.byref(wy), ctypes.byref(mask))
        out.write(json.dumps([rx.value, ry.value, mask.value]) + '\\n')
        time.sleep(1 / 60)
""",
            )
            await checked_exec(
                [
                    "bash",
                    "-lc",
                    (
                        "python3 /tmp/observe_pointer.py >/tmp/pointer_monitor.log 2>&1 & "
                        "for i in $(seq 1 40); do [ -f /tmp/pointer_monitor_ready ] && exit 0; "
                        "sleep 0.1; done; cat /tmp/pointer_monitor.log; exit 1"
                    ),
                ],
                30,
            )
            return state

        return setup

    task = first_combat()
    task.setup = display_fixture()
    original_solver = task.solver

    @solver
    def verify_drag_frames():
        """Check frame-polled button state after the genuine agent tool loop."""

        async def solve(state, generate):
            """Require held input at both drag endpoints and a final release."""
            state = await original_solver(state, generate)
            frames = [
                json.loads(line)
                for line in (
                    await checked_exec(["cat", "/tmp/pointer_frames.jsonl"], 30)
                ).splitlines()
            ]
            pressed = {(x, y) for x, y, mask in frames if mask & 256}
            assert (500, 690) in pressed and (324, 495) in pressed
            assert not frames[-1][2] & 256
            return state

        return solve

    task.solver = verify_drag_frames()
    trajectory = [
        ("screenshot", {"intent": "Inspect the display."}),
        ("left_click", {"intent": "Test a pixel click.", "x": 100, "y": 200}),
        ("mouse_move", {"intent": "Move to a known pixel.", "x": 600, "y": 300}),
        (
            "left_click_drag",
            {
                "intent": "Drag with separately observable press and release.",
                "x1": 500,
                "y1": 690,
                "x2": 324,
                "y2": 495,
            },
        ),
        (
            "queue_actions",
            {
                "intent": "Test a key and fractional wait.",
                "steps": [
                    {"do": "key", "keys": "Return"},
                    {"do": "wait", "seconds": 0.5},
                ],
            },
        ),
        ("wait_for_change", {"intent": "Check a static display.", "timeout": 0}),
        ("memory", {"command": "view", "path": "/memories/notes.md"}),
        ("submit", {"max_floor": 0}),
    ]
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call("mockllm/model", name, args)
            for name, args in trajectory
        ],
    )
    [log] = inspect_eval(
        task,
        model=model,
        sandbox=("docker", str(compose)),
        log_dir=os.environ.get("STS_DOCKER_LOG_DIR", str(tmp_path)),
        display="none",
    )
    assert log.status == "success", log.samples[0].error
    sample = read_eval_log(log.location, resolve_attachments=True).samples[0]
    assert sample.output.completion == "0"
    assert not any(
        message.error for message in sample.messages if message.role == "tool"
    )
    assert any(
        isinstance(item, ContentImage)
        and item.image.startswith("data:image/png;base64,")
        for message in sample.messages
        if isinstance(message.content, list)
        for item in message.content
    )
