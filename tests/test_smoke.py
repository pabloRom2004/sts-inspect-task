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


@pytest.mark.parametrize("mode", ["agent", "probe", "setup_error"])
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
    task = runtime_probe() if mode == "probe" else first_combat()
    assert task.config.reasoning_effort == "max"
    assert task.dataset[0].input == "play Slay the Spire for me"
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
    from inspect_ai.model import GenerateConfig
    from inspect_ai.tool import bash, computer, python, tool_with

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
        await model.generate(
            "Take a screenshot.",
            tools=[
                tool_with(computer(), name="desktop"),
                bash(),
                python(),
                submit_floor(),
            ],
            config=GenerateConfig(reasoning_effort="max", max_tokens=128000),
        )
    assert captured["store"] is False
    assert captured["reasoning"]["effort"] == "max"
    assert captured["max_output_tokens"] == 128000
    assert all(tool["type"] == "function" for tool in captured["tools"])
    desktop = next(tool for tool in captured["tools"] if tool["name"] == "desktop")
    assert desktop["strict"] is False
    assert "coordinate" in desktop["parameters"]["properties"]
