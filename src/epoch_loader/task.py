"""Load a hash-verified private task artifact supplied as a Hawk secret."""

import hashlib
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import zipfile

import httpx
import yaml
from inspect_ai import Task, task

_artifact_directory: str | None = None
_artifact_sha256: str | None = None
DEFAULTS = yaml.safe_load((Path(__file__).parent / 'run_configs/default.yaml').read_text())['task']['args']


def load_private_task(expected_sha256: str):
    """Verify the private wheel before importing any of its task code."""
    global _artifact_directory, _artifact_sha256
    if _artifact_sha256 is not None and _artifact_sha256 != expected_sha256:
        raise RuntimeError('Loaded artifact does not match the requested SHA256')
    if _artifact_directory is None:
        try:
            response = httpx.get(os.environ['EPOCH_SOURCE_URL'], timeout=90)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f'Private task download failed: {type(error).__name__}') from None
        payload = response.content
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise RuntimeError('Private task artifact SHA256 mismatch')
        _artifact_directory = tempfile.mkdtemp(prefix='epoch-task-')
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(_artifact_directory)
        sys.path.insert(0, _artifact_directory)
        _artifact_sha256 = expected_sha256
    return importlib.import_module('playpen_eval.generality_task')


@task
def first_combat(expected_sha256: str, game: str = DEFAULTS['game'], minutes: float = DEFAULTS['minutes'],
                 web: bool = DEFAULTS['web']) -> Task:
    """Delegate the bounded game smoke to the verified private task package."""
    return load_private_task(expected_sha256).first_combat(game, minutes, web)


@task
def luna_key_smoke(expected_sha256: str) -> Task:
    """Load the private task and run its one-request provider preflight."""
    return load_private_task(expected_sha256).luna_key_smoke()
