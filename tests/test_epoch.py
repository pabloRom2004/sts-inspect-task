"""Verify replay-derived prompts and the real Inspect tool boundary."""

import base64
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentImage, ModelOutput, get_model
from inspect_ai.tool import ToolDef, ToolError
from inspect_ai.util import ExecResult

from sts_hawk.epoch_tools import SCHEMAS, STS1_SCHEMAS, epoch_tools
from sts_hawk.task import first_combat, second_game


def test_replay_prompt_and_schema_provenance():
    """Preserve captured message bytes and the reference tool schemas for each game."""
    root = Path(__file__).parents[1] / "src/sts_hawk/assets/epoch"
    expected = {
        "sts1-system.txt": "b2f7f470cdacf0fc1c961c7e4c68a3940d171d4767f4bed5a8759fd86c252101",
        "sts2-system.txt": "af10d9801ef8e49878a84d5cd5527b4e22a7d3ca01a5498043fb26ace4f19e31",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    for height in [720, 800]:
        defs = {
            ToolDef(tool).name: ToolDef(tool) for tool in epoch_tools(3, 180, height)
        }
        for expected_spec in STS1_SCHEMAS if height == 720 else SCHEMAS:
            original = expected_spec
            actual = defs[original["name"]]
            assert actual.description == expected_spec["description"]
            assert (
                actual.parameters.model_dump(exclude_none=True)
                == expected_spec["parameters"]
            )


@pytest.mark.parametrize("game", ["sts1", "sts2"])
@pytest.mark.parametrize("static_frames", [False, True])
@pytest.mark.parametrize("retained_images", [None, 3])
def test_epoch_task_loop(monkeypatch, tmp_path, game, static_frames, retained_images):
    """Run setup, replay tools, recoverable errors, wiki, notes and integer submission."""
    import inspect_ai.tool._tools._computer._common as common

    from sts_hawk import runtime, wiki_client

    class SandboxFixture:
        """Preserve real tool serialization while replacing external Linux execution."""

        def __init__(self):
            """Initialize per-sample action and installation evidence."""
            self.commands = []
            self.files = {}
            self.frame = 0

        async def write_file(self, path, content):
            """Capture installation files supplied by the actual task setup."""
            self.files[path] = content

        async def exec(self, cmd, **kwargs):
            """Serve unique images through the actual computer-tool JSON protocol."""
            self.commands.append(cmd)
            if cmd[:2] == ["python3", "/opt/inspect/tool/computer_tool.py"]:
                self.frame += 0 if static_frames else 1
                return ExecResult(
                    True,
                    0,
                    json.dumps(
                        {
                            "base64_image": base64.b64encode(
                                f"frame-{self.frame}".encode()
                            ).decode()
                        }
                    ),
                    "",
                )
            return ExecResult(True, 0, "setup fixture", "")

    sandbox = SandboxFixture()

    async def computer_sandbox():
        """Connect the stock computer parser to the transport fixture."""
        return sandbox

    wiki_requests = []

    def wiki_request(endpoint, body):
        """Return controlled wiki search results through the real formatting path."""
        wiki_requests.append((endpoint, body))
        return {
            "results": [
                {
                    "title": "Cultist",
                    "url": "https://slaythespire.wiki.gg/wiki/Cultist",
                    "content": "Gains Ritual.",
                },
                {
                    "title": "Outside result",
                    "url": "https://example.org/",
                    "content": "excluded",
                },
            ]
        }

    monkeypatch.setenv("STS_ASSET_URL", "https://example.invalid/private-fixture")
    monkeypatch.setattr(runtime, "sandbox", lambda: sandbox)
    monkeypatch.setattr(common, "computer_sandbox", computer_sandbox)
    monkeypatch.setattr(wiki_client, "tavily_request", wiki_request)
    monkeypatch.setattr(
        wiki_client,
        "build_opener",
        lambda *args: SimpleNamespace(
            open=lambda *args, **kwargs: io.BytesIO(
                b'<h1 id="firstHeading">Cultist</h1><div class="mw-parser-output"><h2>Pattern</h2><p>Gains 5 Ritual.</p></div>'
            )
        ),
    )
    task = first_combat() if game == "sts1" else second_game()
    from sts_hawk.agent import visual_agent

    task.solver = visual_agent(max_screenshots=retained_images)
    assert task.dataset[0].input[0].role == "system"
    assert "seed 1" in task.dataset[0].input[1].text
    assert ("Singleplayer, then Custom" in task.dataset[0].input[1].text) == (
        game == "sts2"
    )
    task.sandbox = None
    trajectory = [
        ("screenshot", {"intent": "Inspect the opening screen."}),
        ("screenshot", {"intent": "Check the same screen again."}),
        ("screenshot", {"intent": "Retain a third observation."}),
        ("screenshot", {"intent": "Check screenshot pruning."}),
        ("wiki_search", {"query": "Cultist"}),
        ("wiki_fetch", {"url": "https://slaythespire.wiki.gg/wiki/Cultist"}),
        ("wiki_fetch", {"url": "https://example.org/"}),
        ("memory", {"command": "view", "path": "/memories/notes.md"}),
        (
            "memory",
            {
                "command": "insert",
                "path": "/memories/notes.md",
                "insert_line": 0,
                "insert_text": "First enemy: Cultist.",
            },
        ),
        ("memory", {"command": "view", "path": "/memories/notes.md"}),
        (
            "queue_actions",
            {
                "intent": "Invalid queue should not touch the game.",
                "steps": [{"do": "left_click"}],
            },
        ),
        ("left_click", {"intent": "Select an option.", "x": 600, "y": 300}),
        ("mouse_move", {"intent": "Inspect an enemy.", "x": 500, "y": 300}),
        (
            "queue_actions",
            {
                "intent": "Perform a decided sequence.",
                "steps": [
                    {"do": "key", "keys": "Return"},
                    {"do": "wait", "seconds": 0.5},
                ],
            },
        ),
        ("wait_for_change", {"intent": "Check the transition.", "timeout": 0}),
        ("submit", {"max_floor": 2}),
    ]
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call("mockllm/model", name, args)
            for name, args in trajectory
        ],
    )
    [log] = inspect_eval(task, model=model, log_dir=str(tmp_path), display="none")
    saved = read_eval_log(log.location)
    assert saved.status == "success", saved.samples[0].error
    sample = saved.samples[0]
    assert sample.output.completion == "2" and not sample.scores
    assert any(
        "First enemy: Cultist." in str(m.content)
        for m in sample.messages
        if m.role == "tool" and m.function == "memory"
    )
    assert len(wiki_requests) == 1 and wiki_requests[0][1]["include_domains"] == [
        "slaythespire.wiki.gg"
    ]
    assert sum(bool(m.error) for m in sample.messages if m.role == "tool") == 2
    events = [e for e in sample.events if e.event == "model"]
    image_counts = [
        sum(
            isinstance(c, ContentImage)
            for m in e.input
            if isinstance(m.content, list)
            for c in m.content
        )
        for e in events
    ]
    if retained_images is None:
        assert max(image_counts) >= 4
    else:
        assert max(image_counts) <= retained_images
    names = {tool.name for tool in events[0].tools}
    assert "wiki_search" in names and "memory" in names and "queue_actions" in names
    assert not {"bash", "python", "desktop"} & names
    assert sample.messages[0].text == task.dataset[0].input[0].text


def test_give_up_ends_without_extra_model_call(tmp_path):
    """End a voluntary give-up with its reason and no fabricated integer result."""
    task = first_combat()
    task.setup = None
    task.sandbox = None
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call(
                "mockllm/model",
                "give_up",
                {"reason": "Transport fixture is intentionally stopped."},
            ),
            ModelOutput.from_content("mockllm/model", "UNREACHABLE"),
        ],
    )
    [log] = inspect_eval(task, model=model, log_dir=str(tmp_path), display="none")
    assert log.status == "success"
    sample = log.samples[0]
    assert (
        sample.store["sts_give_up"]["reason"]
        == "Transport fixture is intentionally stopped."
    )
    assert len([event for event in sample.events if event.event == "model"]) == 1
    assert sample.output.completion != "0" and "UNREACHABLE" not in str(sample.messages)


@pytest.mark.asyncio
async def test_queue_stops_and_returns_final_image(monkeypatch):
    """Stop a queue on a missed input while preserving its last visible changed frame."""
    import sts_hawk.epoch_tools as module

    calls = []
    images = iter(["initial", "changed", "changed"])

    async def backend(**arguments):
        """Return a changed frame followed by a deliberately missed click."""
        calls.append(arguments)
        return [ContentImage(image=next(images))]

    monkeypatch.setattr(module, "desktop_tool", lambda **kwargs: backend)
    tools = {ToolDef(tool).name: tool for tool in epoch_tools(3, 180, 720)}
    await tools["screenshot"](intent="Observe first.")
    result = await tools["queue_actions"](
        intent="Decided sequence.",
        steps=[
            {"do": "left_click", "x": 10, "y": 10},
            {"do": "key", "keys": "Return"},
            {"do": "key", "keys": "Escape"},
        ],
    )
    assert len(calls) == 3
    assert "skipped 1" in str(result)
    assert sum(isinstance(item, ContentImage) for item in result) == 1
    assert result[-1].image == "changed"
    before = len(calls)
    with pytest.raises(ToolError):
        await tools["queue_actions"](
            intent="Malformed batch.",
            steps=[{"do": "left_click", "x": 4, "y": 4}, {"do": "wait", "seconds": -1}],
        )
    assert len(calls) == before
