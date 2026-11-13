import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.tool import ToolDef
from inspect_ai.util import ExecResult

from sts_hawk.runtime import ASSETS
from sts_hawk.task import first_combat, runtime_probe
from sts_hawk.tools import submit_floor


def test_wiki_titles() -> None:
    """Require real enemy articles and source attribution in the copied wiki."""
    text = (ASSETS / "wiki.md").read_text()
    articles = {chunk.split("\n", 1)[0]: chunk for chunk in text.split("\n# ")[1:]}
    assert len(articles) == 750
    for enemy in ["Cultist", "Jaw Worm", "Louses", "Acid Slime", "Spike Slime"]:
        assert enemy in articles
        assert "https://slay-the-spire.fandom.com" in articles[enemy]


@pytest.mark.parametrize("mode", ["agent", "beat_game", "probe", "setup_error"])
def test_real_setup_react_and_integer_submission(monkeypatch, tmp_path, mode) -> None:
    """Exercise setup, stock desktop/shell/Python tools and integer submission without a grader."""
    import inspect_ai.tool._tools._computer._common as computer_common
    import inspect_ai.tool._tools._execute as execute_tools

    from sts_hawk import runtime

    class TransportSandbox:
        """Replace external Linux execution while preserving the real tool protocol."""

        def __init__(self) -> None:
            """Track setup writes, executed commands and computer requests."""
            self.files = {}
            self.commands = []
            self.actions = 0

        async def write_file(self, path, content):
            """Capture installation assets passed to the sandbox."""
            self.files[path] = content

        async def exec(self, cmd, **kwargs):
            """Return setup status or a stock computer-tool JSON response."""
            command = cmd
            self.commands.append(command)
            if command == ["bash", "/opt/sts/install.sh"] and mode == "setup_error":
                return ExecResult(False, 1, "", "fixture installation failed")
            if command[:2] == ["python3", "/opt/inspect/tool/computer_tool.py"]:
                self.actions += 1
                return ExecResult(
                    True, 0, '{"output":"transport fixture","error":null}', ""
                )
            if command[:3] == ["bash", "--login", "-c"]:
                return ExecResult(True, 0, "Jaw Worm transport fixture", "")
            return ExecResult(True, 0, "game-launch-triggered", "")

    sb = TransportSandbox()

    async def computer_sandbox():
        """Bind the real stock computer parser to the transport fixture."""
        return sb

    monkeypatch.setenv("STS_ASSET_URL", "https://example.invalid/private-test-fixture")
    monkeypatch.setattr(runtime, "sandbox", lambda: sb)
    monkeypatch.setattr(execute_tools, "sandbox_env", lambda name=None: sb)
    monkeypatch.setattr(computer_common, "computer_sandbox", computer_sandbox)
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call(
                "mockllm/model", "desktop", {"action": "screenshot"}
            ),
            ModelOutput.for_tool_call(
                "mockllm/model",
                "bash",
                {"command": "grep -n '^# Jaw Worm' /opt/sts/wiki.md"},
            ),
            ModelOutput.for_tool_call(
                "mockllm/model",
                "python",
                {
                    "code": "from pathlib import Path; print(Path('/opt/sts/wiki.md').read_text()[:100])"
                },
            ),
            ModelOutput.for_tool_call("mockllm/model", "submit", {"max_floor": 1.5}),
            ModelOutput.for_tool_call("mockllm/model", "submit", {"max_floor": 1}),
            ModelOutput.from_content("mockllm/model", "UNREACHABLE EXTRA TURN"),
        ],
    )
    task = (
        runtime_probe()
        if mode == "probe"
        else first_combat(
            prompt_name="beat_game" if mode == "beat_game" else "first_combat"
        )
    )
    assert task.config.reasoning_effort == "max"
    expected_prompt = (
        "Try to beat Slay the Spire on Ascension 20 as Ironclad."
        if mode == "beat_game"
        else "play Slay the Spire for me as Ironclad"
    )
    assert task.dataset[0].input == expected_prompt
    task.sandbox = None
    log = inspect_eval(task, model=model, log_dir=str(tmp_path), display="none")[0]
    sample = log.samples[0]
    assert not sample.scores
    if mode == "setup_error":
        assert log.status == "error"
        assert "fixture installation failed" in sample.error.message
        assert sb.actions == 0
        return
    assert log.status == "success"
    if mode == "probe":
        assert sb.actions == 1
        assert not log.stats.model_usage
        return
    assert sample.input == expected_prompt
    assert sample.output.completion == "1"
    assert sb.actions == 1
    assert "UNREACHABLE EXTRA TURN" not in str(sample.messages)
    assert sb.files["/opt/sts/wiki.md"] == (ASSETS / "wiki.md").read_text()
    tool_names = [msg.function for msg in sample.messages if msg.role == "tool"]
    assert tool_names == ["desktop", "bash", "python", "submit", "submit"]
    assert sum(cmd[:3] == ["bash", "--login", "-c"] for cmd in sb.commands) == 2
    assert "/opt/inspect/tool/computer_tool.py" in sb.files
    assert any("/tmp/sts-runtime-ready" in str(cmd) for cmd in sb.commands)
    assert any(getattr(msg, "error", None) for msg in sample.messages)
    submission = ToolDef(submit_floor()).parameters
    assert submission.properties["max_floor"].type == "integer"
    assert submission.required == ["max_floor"]


def test_hawk_compose_conversion(tmp_path) -> None:
    """Reproduce Hawk's ruamel-to-PyYAML path using the real K8s converter."""
    import subprocess
    from pathlib import Path

    import ruamel.yaml
    from k8s_sandbox._helm import DEFAULT_CHART
    from k8s_sandbox.compose import convert_compose_to_helm_values

    original = Path(first_combat().sandbox.config)
    yaml = ruamel.yaml.YAML(typ="safe")
    data = yaml.load(original.read_text())
    assert data["services"]["default"].pop("platform") == "linux/amd64"
    sanitized = tmp_path / "sanitized-compose.yaml"
    with sanitized.open("w") as stream:
        yaml.dump(data, stream)
    result = convert_compose_to_helm_values(sanitized)
    assert result["services"]["default"]["image"] == "ubuntu:24.04"
    assert result["services"]["default"]["command"] == ["bash", "-lc"]
    values = tmp_path / "values.yaml"
    with values.open("w") as stream:
        yaml.dump(result, stream)
    rendered = subprocess.run(
        ["helm", "template", "sts-probe", str(DEFAULT_CHART), "-f", str(values)],
        capture_output=True,
        text=True,
        check=True,
    )
    manifests = yaml.load_all(rendered.stdout)
    stateful_set = next(doc for doc in manifests if doc["kind"] == "StatefulSet")
    container = stateful_set["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["bash", "-lc"]
    assert "/tmp/sts-runtime-ready" in container["args"][0]


@pytest.mark.asyncio
async def test_stateless_responses_request(monkeypatch) -> None:
    """Serialize the real computer schema without native tools or API storage."""
    from inspect_ai.model import (
        ChatMessageAssistant,
        ChatMessageTool,
        ChatMessageUser,
        ContentImage,
        GenerateConfig,
    )
    from inspect_ai.tool import ToolCall, bash, computer, python, tool_with

    from sts_hawk.agent import visual_agent
    from sts_hawk.run_config import default_run_config

    visual_agent()

    class RequestCaptured(BaseException):
        """Stop immediately before the SDK would send a request."""

    model = get_model(
        "openrouter/openai/gpt-6-luna",
        api_key="local-test-placeholder",
        responses_api=True,
        responses_store=False,
    )
    captured = {}

    async def capture_request(**kwargs):
        """Capture the completed provider payload without network access."""
        captured.update(kwargs)
        raise RequestCaptured

    monkeypatch.setattr(model.api.client.responses, "create", capture_request)
    with pytest.raises(RequestCaptured):
        image = ContentImage(
            image="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jfLQAAAAASUVORK5CYII="
        )
        messages = [ChatMessageUser(content="Inspect the screen and wiki.")]
        sequence = [
            ("c1", "desktop", {"action": "screenshot"}, [image]),
            ("c2", "bash", {"command": "cat /opt/sts/wiki.md"}, "wiki text"),
            ("c3", "desktop", {"action": "screenshot"}, [image]),
        ]
        sequence += [
            (f"desktop-{i}", "desktop", {"action": "screenshot"}, [image])
            for i in range(60)
        ]
        sequence[-1] = (
            "latest-desktop",
            "desktop",
            {"action": "screenshot"},
            [image.model_copy(update={"detail": "high"})],
        )
        sequence += [("python-last", "python", {"code": "print(1)"}, "1")]
        for call_id, function, arguments, content in sequence:
            messages.extend(
                [
                    ChatMessageAssistant(
                        content="",
                        tool_calls=[
                            ToolCall(id=call_id, function=function, arguments=arguments)
                        ],
                    ),
                    ChatMessageTool(
                        tool_call_id=call_id, function=function, content=content
                    ),
                ]
            )
        await model.generate(
            messages,
            tools=[
                tool_with(
                    computer(
                        max_screenshots=default_run_config()["solver"]["args"][
                            "max_screenshots"
                        ]
                    ),
                    name="desktop",
                ),
                bash(),
                python(),
                submit_floor(),
            ],
            config=GenerateConfig(reasoning_effort="max", max_tokens=128000),
        )
    assert (
        sum(
            block.get("type") == "input_image"
            for item in captured["input"]
            for block in item.get("content", [])
            if isinstance(block, dict)
        )
        == 1
    )
    retained = [
        block
        for item in captured["input"]
        for block in item.get("content", [])
        if isinstance(block, dict) and block.get("type") == "input_image"
    ]
    assert retained[0]["detail"] == "high"
    # Request pruning must preserve the original replay images.
    assert (
        sum(
            block.type == "image"
            for msg in messages
            if isinstance(msg.content, list)
            for block in msg.content
        )
        == 62
    )
    assert captured["store"] is False
    assert captured["reasoning"]["effort"] == "max"
    assert captured["max_output_tokens"] == 128000
    assert all(tool["type"] == "function" for tool in captured["tools"])
    desktop = next(tool for tool in captured["tools"] if tool["name"] == "desktop")
    assert desktop["strict"] is False
    assert "coordinate" in desktop["parameters"]["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["open_web_browser", "navigate"])
async def test_missing_browser_is_recoverable(monkeypatch, action) -> None:
    """Return an ordinary tool error without waiting for an absent browser window."""
    monkeypatch.syspath_prepend(str(ASSETS / "computer"))
    import _x11_client

    monkeypatch.setattr(_x11_client.shutil, "which", lambda name: None)
    monkeypatch.setenv("WIDTH", "1280")
    monkeypatch.setenv("HEIGHT", "720")
    client = _x11_client.X11Client()
    result = (
        await client.open_web_browser()
        if action == "open_web_browser"
        else await client.navigate("https://example.com")
    )
    assert result.error == "Firefox ESR is not installed in this sandbox."
