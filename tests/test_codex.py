"""Exercise the optional native Codex path without paid inference."""

import logging
import os

import pytest
import yaml
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageUser,
    ContentImage,
    ContentText,
    GenerateConfig,
    ModelOutput,
    ModelUsage,
    get_model,
)
from inspect_ai.solver import solver
from inspect_ai.util import sandbox

from sts_hawk.agent import visual_agent
from sts_hawk.native_codex import prune_images
from sts_hawk.run_config import default_run_config
from sts_hawk.runtime import ASSETS


def test_prune_images_preserves_text_and_original_history():
    """Keep the newest three images without changing reasoning or source messages."""
    messages = [ChatMessageAssistant(content="Keep the combat plan.")]
    for index in range(5):
        messages.append(
            ChatMessageUser(
                content=[
                    ContentText(text=f"screen {index}"),
                    ContentImage(image=f"https://example.invalid/{index}.png"),
                ]
            )
        )
    filtered = prune_images(messages, 3)
    images = [
        item.image
        for message in filtered
        if isinstance(message.content, list)
        for item in message.content
        if isinstance(item, ContentImage)
    ]
    assert images == [f"https://example.invalid/{i}.png" for i in [2, 3, 4]]
    assert filtered[0].text == "Keep the combat plan."
    assert all(f"screen {i}" in filtered[i + 1].text for i in range(5))
    assert all(
        isinstance(message.content[-1], ContentImage) for message in messages[1:]
    )
    assert prune_images(messages, None) is messages


@pytest.mark.parametrize("harness", ["unknown", "codex"])
def test_harness_selection_and_validation(harness):
    """Reject unknown harnesses while constructing Codex without invoking a model."""
    if harness == "unknown":
        with pytest.raises(ValueError, match="Unknown harness"):
            visual_agent(harness=harness)
    else:
        assert callable(visual_agent(harness=harness))


def test_codex_rejects_fractional_token_threshold():
    """Reject fractional native token thresholds rather than silently rounding to zero."""
    codex = dict(default_run_config()["solver"]["args"]["codex"])
    codex["compaction_threshold"] = 0.75
    with pytest.raises(ValueError, match="integer token count"):
        visual_agent(harness="codex", codex=codex)


@solver
def prepare_desktop_fixture():
    """Install task files and a blank X desktop without starting a game."""

    async def solve(state, generate):
        """Start the real computer backend against a bounded virtual display."""
        result = await sandbox().exec(["mkdir", "-p", "/opt/sts", "/opt/inspect/tool"])
        assert result.success
        await sandbox().write_file("/opt/sts/wiki.md", (ASSETS / "wiki.md").read_text())
        for source in (ASSETS / "computer").glob("*.py"):
            await sandbox().write_file(
                f"/opt/inspect/tool/{source.name}", source.read_text()
            )
        result = await sandbox().exec(
            [
                "bash",
                "-c",
                (
                    "Xvnc :99 -geometry 1280x720 -depth 24 -SecurityTypes None "
                    ">/tmp/codex-fixture-xvnc.log 2>&1 &"
                ),
            ]
        )
        assert result.success
        result = await sandbox().exec(
            [
                "bash",
                "-c",
                (
                    "for attempt in $(seq 1 40); do "
                    "if DISPLAY=:99 xdpyinfo >/dev/null 2>&1; then "
                    "touch /tmp/xfce_started; exit 0; fi; sleep 0.25; done; exit 1"
                ),
            ]
        )
        assert result.success
        return state

    return solve


@pytest.mark.skipif(
    os.environ.get("STS_CODEX_DOCKER_TEST") != "1",
    reason="Explicit Docker integration test; no game or paid model is used.",
)
@pytest.mark.parametrize("mode", ["transport", "early_exit", "compaction"])
def test_native_codex_docker(tmp_path, mode, caplog):
    """Run the real Codex executable, model proxy and desktop MCP bridge in Docker."""
    pytest.importorskip("inspect_swe")
    caplog.set_level(logging.WARNING)
    compose = tmp_path / "compose.yaml"
    compose.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "default": {
                        "image": "local/sts-hawk-os:0.2.4",
                        "platform": "linux/amd64",
                        "command": ["sleep", "infinity"],
                        "environment": {
                            "DISPLAY_NUM": "99",
                            "WIDTH": "1280",
                            "HEIGHT": "720",
                        },
                        "deploy": {
                            "resources": {"limits": {"cpus": "1", "memory": "1G"}}
                        },
                    }
                }
            }
        )
    )
    requests = []
    scripted_turns = 0

    def respond(messages, tools, tool_choice, config):
        """Capture the genuine native request before issuing a scripted response."""
        nonlocal scripted_turns
        requests.append(
            {
                "tools": [t.name for t in tools],
                "config": config.model_dump(),
                "images": sum(
                    isinstance(item, ContentImage)
                    for message in messages
                    if isinstance(message.content, list)
                    for item in message.content
                ),
                "text": "\n".join(message.text for message in messages)[-12000:],
            }
        )
        (tmp_path / "native-requests.yaml").write_text(yaml.safe_dump(requests))
        if mode == "early_exit":
            return ModelOutput.from_content("mockllm/model", "Scripted early stop.")
        if "CONTEXT CHECKPOINT COMPACTION" in messages[-1].text:
            requests[-1]["compaction"] = True
            return ModelOutput.from_content(
                "mockllm/model",
                "Fixture summary. Continue the test and submit floor 1.",
            )
        phase = scripted_turns
        scripted_turns += 1
        if phase == 0:
            code = """text(ALL_TOOLS.filter(t => /desktop|submit/.test(t.name)));
text(await tools.exec_command({cmd: "python3 -c \\\"from pathlib import Path; p=Path('/workspace/native-test.txt');p.write_text('native python works');assert p.read_text()=='native python works';assert '# Cultist' in Path('/opt/sts/wiki.md').read_text();print('WIKI_AND_PYTHON_OK')\\\""}));
const d=ALL_TOOLS.find(t => t.name.endsWith('__desktop'));
text(await tools[d.name]({action:'wait',duration:3000}));"""
        elif phase <= 5:
            code = """const d=ALL_TOOLS.find(t => t.name.endsWith('__desktop'));
const result=await tools[d.name]({action:'screenshot'});
for (const c of result.content ?? []) {if(c.type==='image') image(c);else if(c.type==='text') text(c.text);}"""
        elif phase == 6:
            code = """const s=ALL_TOOLS.find(t => t.name.endsWith('__submit'));
text(await tools[s.name]({max_floor:1.5}));"""
        elif phase == 7:
            code = """text(await tools.exec_command({cmd:"python3 -c \\\"import json;from pathlib import Path;events=[json.loads(line) for p in Path('/opt/sts/codex-home/sessions').rglob('*.jsonl') for line in p.read_text().splitlines()];print('NATIVE_CONTEXT',[(e['payload'].get('info') or {}).get('model_context_window') for e in events if e.get('type')=='event_msg' and e.get('payload',{}).get('type')=='token_count'])\\\""}));
const s=ALL_TOOLS.find(t => t.name.endsWith('__submit'));
text(await tools[s.name]({max_floor:1}));"""
        else:
            raise AssertionError("Submitted runs must not make another model call.")
        output = ModelOutput.for_tool_call("mockllm/model", "exec", {"input": code})
        output.message.tool_calls[0].type = "custom"
        if mode == "compaction" and phase == 5:
            output.usage = ModelUsage(
                input_tokens=200000, output_tokens=100, total_tokens=200100
            )
        return output

    args = dict(default_run_config()["solver"]["args"])
    args["harness"] = "codex"
    task = Task(
        dataset=[
            Sample(
                input="Test the desktop fixture, then submit the floor as an integer."
            )
        ],
        setup=prepare_desktop_fixture(),
        solver=visual_agent(**args),
        config=GenerateConfig(**default_run_config()["generate_config"]),
        sandbox=("docker", str(compose)),
        time_limit=180,
    )
    log = inspect_eval(
        task,
        model=get_model("mockllm/model", custom_outputs=respond),
        log_dir=str(tmp_path / "logs"),
        display="none",
    )[0]
    assert log.status == "success", log.samples[0].error
    if mode == "early_exit":
        assert log.samples[0].output.completion == "Scripted early stop."
        assert log.samples[0].store["FloorSubmission:native_exit_without_submit"]
        assert log.samples[0].store["FloorSubmission:max_floor"] is None
        return
    assert log.samples[0].output.completion == "1"
    if mode == "transport":
        assert [r["images"] for r in requests] == [0, 0, 1, 2, 3, 3, 3, 3]
    else:
        assert any(r.get("compaction") for r in requests)
        assert max(r["images"] for r in requests) <= 3
    assert all(r["config"]["max_tokens"] == 128000 for r in requests)
    assert all(r["config"]["reasoning_effort"] == "max" for r in requests)
    assert all("spawn_agent" not in r["tools"] for r in requests)
    assert any("WIKI_AND_PYTHON_OK" in r["text"] for r in requests)
    assert any("duration is in seconds" in r["text"] for r in requests)
    assert log.samples[0].store["FloorSubmission:max_floor"] == 1
    assert "NATIVE_CONTEXT [258400" in str(log.samples[0].messages)
