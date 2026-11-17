from pathlib import Path
from typing import Any

import yaml


def default_run_config() -> dict[str, Any]:
    """Read the packaged defaults for the replay-derived gameplay tasks."""
    return yaml.safe_load(
        (Path(__file__).parent / "run_configs/default.yaml").read_text()
    )
