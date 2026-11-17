"""Verify GPU scheduling configuration and device-probe failure accounting."""

from pathlib import Path

import pytest
import yaml
from inspect_ai import eval as inspect_eval
from inspect_ai.util import ExecResult
from k8s_sandbox.compose._converter import convert_compose_to_helm_values

from sts_hawk.task import first_combat, gpu_probe, second_game


@pytest.mark.parametrize("factory", [first_combat, second_game, gpu_probe])
def test_game_node_selector_survives_kubernetes_conversion(factory, tmp_path):
    """Retain explicit GPU instance placement and the independently requested limits."""
    selector = {"karpenter.k8s.aws/instance-family": "g4dn"}
    task = factory(gpu_count=1, sandbox_node_selector=selector)
    assert task.sandbox.type == "k8s"
    values = yaml.safe_load(Path(task.sandbox.config).read_text())["services"][
        "default"
    ]
    assert values["nodeSelector"] == {**selector, "kubernetes.io/arch": "amd64"}
    assert values["resources"]["requests"]["nvidia.com/gpu"] == 1
    assert values["resources"]["requests"]["cpu"] == "6"
    assert values["resources"]["requests"]["memory"] == "12Gi"
    assert task.metadata["sandbox_node_selector"] == selector


@pytest.mark.parametrize("factory", [gpu_probe, second_game])
def test_gpu_resources_survive_kubernetes_conversion(factory, tmp_path):
    """Request an NVIDIA device and graphics libraries through the real converter."""
    task = factory(gpu_count=1)
    compose = yaml.safe_load(Path(task.sandbox.config).read_text())
    # Hawk consumes the architecture pin before calling this converter.
    assert compose["services"]["default"].pop("platform") == "linux/amd64"
    path = tmp_path / "compose.yaml"
    path.write_text(yaml.safe_dump(compose))
    values = convert_compose_to_helm_values(path)
    service = values["services"]["default"]
    assert service["resources"]["requests"] == {
        "cpu": "6",
        "memory": "12Gi",
        "nvidia.com/gpu": 1,
    }
    assert service["resources"]["limits"] == service["resources"]["requests"]
    assert {
        "name": "NVIDIA_DRIVER_CAPABILITIES",
        "value": "compute,utility,graphics,display",
    } in service["env"]


@pytest.mark.parametrize("available", [True, False])
def test_gpu_probe_records_device_or_infrastructure_failure(
    monkeypatch, tmp_path, available
):
    """Run the actual Inspect probe without model calls and retain device failures."""
    import sts_hawk.task as task_module

    class Environment:
        """Return the selected device response at the real sandbox boundary."""

        async def exec(self, cmd, **kwargs):
            """Preserve the nvidia-smi request and return controlled device evidence."""
            assert "nvidia-smi" in cmd[-1]
            return ExecResult(
                available,
                0 if available else 127,
                "fixture GPU" if available else "",
                "" if available else "nvidia-smi: command not found",
            )

    monkeypatch.setattr(task_module, "sandbox", lambda: Environment())
    selector = {"karpenter.k8s.aws/instance-family": "g4dn"}
    task = gpu_probe(sandbox_node_selector=selector)
    task.sandbox = None
    result = inspect_eval(
        task,
        model="mockllm/model",
        log_dir=str(tmp_path),
        display="none",
        fail_on_error=False,
    )[0]
    sample = result.samples[0]
    assert result.eval.metadata["sandbox_node_selector"] == selector
    assert not sample.model_usage and not sample.scores
    assert (sample.error is None) is available
    info = next(
        event.data
        for event in sample.events
        if event.event == "info" and isinstance(event.data, dict)
    )
    assert info["success"] is available
    assert ("fixture GPU" in info["gpu_diagnostics"]) is available
