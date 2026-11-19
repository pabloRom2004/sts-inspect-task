"""Load maintained defaults from the standalone run configuration."""

from pathlib import Path

import yaml


def default_run_config() -> dict:
    """Read the complete maintained task configuration."""
    return yaml.safe_load(
        (Path(__file__).parent / "run_configs/default.yaml").read_text()
    )


DEFAULT_CONFIG = default_run_config()
DEFAULT_ARGS = DEFAULT_CONFIG["task"]["args"]
