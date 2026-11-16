"""Verify the second game's setup and unscored integer-report contract."""

from pathlib import Path

import pytest
import yaml
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.util import ExecResult

from sts_hawk.task import runtime_probe, second_game


@pytest.mark.parametrize("mode", ["full", "smoke", "probe", "actions"])
def test_sts2_setup_and_submission(monkeypatch, tmp_path, mode):
    """Run the actual StS2 composition through mock inference and desktop transport."""
    import inspect_ai.tool._tools._computer._common as computer_common
    import inspect_ai.tool._tools._execute as execute_tools

    from sts_hawk import runtime

    class SandboxFixture:
        """Record setup assets while serving the stock desktop's JSON protocol."""

        def __init__(self):
            """Initialize per-sample setup and action evidence."""
            self.files = {}
            self.actions = 0
            self.commands = []

        async def write_file(self, path, content):
            """Capture the actual file delivered to the sandbox."""
            self.files[path] = content

        async def exec(self, cmd, **kwargs):
            """Simulate external execution while preserving real tool serialization."""
            if cmd[:2] == ["python3", "/opt/inspect/tool/computer_tool.py"]:
                self.actions += 1
                self.commands.append(cmd)
                return ExecResult(True, 0, '{"output":"StS2 fixture","error":null}', "")
            if "tar -C /root/.local/share/SlayTheSpire2" in " ".join(cmd):
                return ExecResult(True, 0, "cHJvZmlsZSBmaXh0dXJl", "")
            return ExecResult(True, 0, "setup or shell fixture", "")

    fixture = SandboxFixture()

    async def computer_sandbox():
        """Bind the real stock computer parser to this sample's transport."""
        return fixture

    monkeypatch.setenv("STS_ASSET_URL", "https://example.invalid/private-sts2-fixture")
    monkeypatch.setattr(runtime, "sandbox", lambda: fixture)
    monkeypatch.setattr(execute_tools, "sandbox_env", lambda name=None: fixture)
    monkeypatch.setattr(computer_common, "computer_sandbox", computer_sandbox)
    probe = mode in {"probe", "actions"}
    if probe:
        task = runtime_probe(
            game="sts2",
            wait_seconds=90,
            actions=[{"action": "screenshot"}] if mode == "actions" else None,
            capture_profile=mode == "actions",
        )
    else:
        task = second_game(
            prompt_name="first_combat_smoke_sts2"
            if mode == "smoke"
            else "beat_game_sts2"
        )
    assert task.name == (
        "sts2_first_combat_smoke" if mode == "smoke" else "sts2_beat_game"
    )
    assert task.dataset[0].id.startswith("sts2-ironclad-a10-")
    if mode == "smoke":
        assert "Play the first combat, then stop" in task.dataset[0].input
    else:
        assert "Complete all three Acts to win." in task.dataset[0].input
    assert "Enter seed 1" in task.dataset[0].input
    assert "Heart" not in task.dataset[0].input
    assert "wiki" not in task.dataset[0].input
    assert (
        yaml.safe_load(Path(task.sandbox.config).read_text())["services"]["default"][
            "environment"
        ]["HEIGHT"]
        == "800"
    )
    task.sandbox = None
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call(
                "mockllm/model", "desktop", {"action": "screenshot"}
            ),
            ModelOutput.for_tool_call("mockllm/model", "submit", {"max_floor": 2}),
        ],
    )
    log = inspect_eval(task, model=model, log_dir=str(tmp_path), display="none")[0]
    saved = read_eval_log(log.location)
    assert saved.status == "success"
    assert not saved.samples[0].scores
    assert fixture.actions == (2 if mode == "actions" else 1)
    assert "/opt/sts/wiki.md" not in fixture.files
    assert "v0.107.1" in fixture.files["/opt/sts/install.sh"]
    assert "--force-steam=off" in fixture.files["/opt/sts/start.sh"]
    if probe:
        assert not saved.stats.model_usage
        command = fixture.commands[0]
        assert float(command[command.index("--duration") + 1]) == 90
        if mode == "actions":
            assert any(
                event.event == "info"
                and isinstance(event.data, dict)
                and event.data.get("profile_archive_base64") == "cHJvZmlsZSBmaXh0dXJl"
                for event in saved.samples[0].events
            )
    else:
        assert saved.samples[0].output.completion == "2"


def test_sts2_rejects_unsupported_ascension():
    """Reject A20 rather than silently playing a different StS2 difficulty."""
    with pytest.raises(ValueError, match="Ascension 0 through 10"):
        second_game(ascension=20)
