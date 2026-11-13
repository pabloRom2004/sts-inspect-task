import json

import pytest
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.util import Store
from inspect_ai.util._subprocess import ExecResult

from sts_hawk.agent import visual_agent
from sts_hawk.scorers import combat_and_wiki
from sts_hawk.state import RunState, observe, wiki_requirement
from sts_hawk.tools import wiki_articles


def combat(screen: str = "NONE", hp: int = 80, floor: int = 1) -> dict:
    """Make an explicit observer-protocol fixture for a first encounter."""
    return {
        "in_game": True,
        "game_state": {
            "floor": floor,
            "current_hp": hp,
            "screen_type": screen,
            "combat_state": {"monsters": [{"name": "Jaw Worm"}]},
        },
    }


def test_wiki_titles() -> None:
    """Require real enemy articles and their source attribution in the copied wiki."""
    articles = wiki_articles()
    assert len(articles) == 750
    for enemy in ["Cultist", "Jaw Worm", "Louses", "Acid Slime", "Spike Slime"]:
        assert enemy in articles
        assert "https://slay-the-spire.fandom.com" in articles[enemy]


def test_observer_errors_are_not_losses() -> None:
    """Keep broken infrastructure distinct from a legitimate lost encounter."""
    history = RunState(store=Store())
    with pytest.raises(RuntimeError, match="observer failed"):
        observe({"error": "timeout"}, history)
    with pytest.raises(ValueError, match="in_game"):
        observe({}, history)
    with pytest.raises(RuntimeError, match="without observing"):
        observe(combat(floor=2), history)


@pytest.mark.parametrize("read_wiki,expected", [(True, "C"), (False, "I")])
def test_real_react_tool_and_scorer_path(
    monkeypatch, tmp_path, read_wiki, expected
) -> None:
    """Exercise stock computer parsing, offline wiki, persisted grading, and auto-stop."""
    import inspect_ai.tool._tools._computer._common as computer_common

    from sts_hawk import runtime

    class ProtocolSandbox:
        """Replace only external game transport with deterministic protocol fixtures."""

        def __init__(self) -> None:
            """Begin with a live enemy and track actual computer invocations."""
            self.won = False
            self.actions = 0

        async def exec(self, command, **kwargs):
            """Return either a fresh game observation or the computer protocol response."""
            if command[1] == "/opt/sts/observer.py":
                raw = combat("COMBAT_REWARD" if self.won else "NONE")
                return ExecResult(
                    success=True, returncode=0, stdout=json.dumps(raw), stderr=""
                )
            assert command[:2] == ["python3", "/opt/inspect/tool/computer_tool.py"]
            self.actions += 1
            if command[2] == "left_click":
                self.won = True
            return ExecResult(
                success=True,
                returncode=0,
                stdout='{"output":"fixture","error":null}',
                stderr="",
            )

    sb = ProtocolSandbox()

    async def computer_sandbox():
        """Bind the stock computer tool to the protocol fixture for this test."""
        return sb

    monkeypatch.setattr(runtime, "sandbox", lambda: sb)
    monkeypatch.setattr(computer_common, "computer_sandbox", computer_sandbox)
    outputs = [
        ModelOutput.for_tool_call("mockllm/model", "computer", {"action": "screenshot"})
    ]
    if read_wiki:
        outputs.append(
            ModelOutput.for_tool_call("mockllm/model", "wiki", {"query": "Jaw Worm"})
        )
    outputs.append(
        ModelOutput.for_tool_call(
            "mockllm/model",
            "computer",
            {"action": "left_click", "coordinate": [600, 500]},
        )
    )
    outputs.append(ModelOutput.from_content("mockllm/model", "UNREACHABLE EXTRA TURN"))
    model = get_model("mockllm/model", custom_outputs=outputs)
    log = inspect_eval(
        Task(
            dataset=[Sample(id="fixture", input="Exercise tools")],
            solver=visual_agent(),
            scorer=combat_and_wiki(observer_timeout=30),
        ),
        model=model,
        log_dir=str(tmp_path),
        display="none",
    )[0]
    assert log.status == "success"
    sample = log.samples[0]
    assert sample.scores["combat_and_wiki"].value == expected
    assert sb.actions == 2
    assert "UNREACHABLE EXTRA TURN" not in str(sample.messages)
    history = RunState(store=Store(sample.store))
    assert history.won
    assert wiki_requirement(history) == read_wiki
    assert bool(history.wiki_reads) == read_wiki


def test_death_and_victory_are_distinct() -> None:
    """Record actual death without awarding a first-combat victory."""
    history = RunState(store=Store())
    observe(combat(hp=0, screen="DEATH"), history)
    assert history.died and not history.won


def test_provider_probe_is_one_generation(tmp_path) -> None:
    """Verify the vision probe reaches scoring after exactly one mock response."""
    from sts_hawk.task import provider_probe

    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", "white"),
        ],
    )
    log = inspect_eval(
        provider_probe(), model=model, log_dir=str(tmp_path), display="none"
    )[0]
    assert log.status == "success"
    assert log.samples[0].scores["includes"].value == "C"


def test_hawk_compose_conversion(tmp_path) -> None:
    """Reproduce Hawk's ruamel-to-PyYAML conversion with the real K8s converter."""
    from pathlib import Path

    import ruamel.yaml
    from k8s_sandbox.compose import convert_compose_to_helm_values

    from sts_hawk.task import first_combat

    original = Path(first_combat().sandbox.config)
    yaml = ruamel.yaml.YAML(typ="safe")
    data = yaml.load(original.read_text())
    assert data["services"]["default"].pop("platform") == "linux/amd64"
    sanitized = tmp_path / "sanitized-compose.yaml"
    with sanitized.open("w") as stream:
        yaml.dump(data, stream)
    result = convert_compose_to_helm_values(sanitized)
    assert result["services"]["default"]["image"] == "ubuntu:24.04"


def test_observer_pipe_handshake_and_fresh_state(tmp_path) -> None:
    """Exercise the real observer process and Unix socket against a game-protocol fixture."""
    import select
    import subprocess
    import sys
    import time
    import uuid
    from pathlib import Path

    from sts_hawk import runtime

    script = Path(runtime.__file__).parent / "assets/observer.py"
    address = "/tmp/sts-observer-" + uuid.uuid4().hex + ".sock"
    loader = (
        "import runpy; d=runpy.run_path(" + repr(str(script)) + "); "
        "d['Observer'].run.__globals__['SOCKET']=" + repr(address) + "; "
    )
    server = subprocess.Popen(
        [sys.executable, "-c", loader + "d['Observer']().run()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        assert select.select([server.stdout], [], [], 5)[0]
        assert server.stdout.readline().strip() == "ready"
        server.stdin.write(json.dumps({"in_game": False}) + "\n")
        server.stdin.flush()
        deadline = time.monotonic() + 5
        while not Path(address).exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        client = subprocess.Popen(
            [sys.executable, "-c", loader + "d['client']('STATE')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert select.select([server.stdout], [], [], 5)[0]
        assert server.stdout.readline().strip() == "STATE"
        server.stdin.write(json.dumps(combat()) + "\n")
        server.stdin.flush()
        output, error = client.communicate(timeout=5)
        assert client.returncode == 0, error
        assert json.loads(output)["game_state"]["floor"] == 1
    finally:
        server.terminate()
        server.communicate(timeout=5)
        Path(address).unlink(missing_ok=True)
