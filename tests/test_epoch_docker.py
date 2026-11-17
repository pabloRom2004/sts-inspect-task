"""Run the replay action profile through real Docker/X11 with scripted inference."""

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
            return state

        return setup

    task = first_combat()
    task.setup = display_fixture()
    trajectory = [
        ("screenshot", {"intent": "Inspect the display."}),
        ("left_click", {"intent": "Test a pixel click.", "x": 100, "y": 200}),
        ("mouse_move", {"intent": "Move to a known pixel.", "x": 600, "y": 300}),
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
