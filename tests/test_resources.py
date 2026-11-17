"""Verify the shared game budget and explicit resource overrides."""

from pathlib import Path

import pytest
import yaml

from sts_hawk.manual import manual_session
from sts_hawk.task import first_combat, second_game


@pytest.mark.parametrize("factory", [first_combat, second_game, manual_session])
@pytest.mark.parametrize("override", [False, True])
def test_game_resource_configuration(factory, override):
    """Apply the same defaults and supported overrides to real sandbox configuration."""
    args = (
        {
            "sandbox_cpu": "3",
            "sandbox_memory": "8G",
            "processor_count": 3,
            "renderer_threads": 2,
        }
        if override
        else {}
    )
    task = factory(**args)
    config = yaml.safe_load(Path(task.sandbox.config).read_text())
    assert config["services"]["default"]["deploy"]["resources"]["limits"] == {
        "cpus": "3" if override else "6",
        "memory": "8G" if override else "12G",
    }
    assert task.metadata["processor_count"] == (3 if override else 6)
    assert task.metadata["renderer_threads"] == (2 if override else 3)
