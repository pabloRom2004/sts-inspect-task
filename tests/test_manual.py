"""Verify private browser access and tunnel release integrity."""

import asyncio
import hashlib
import io

import pytest
from aiohttp.test_utils import TestClient, TestServer

from sts_hawk.manual_server import browser_tunnel, desktop_proxy


@pytest.mark.asyncio
@pytest.mark.parametrize("digest_only", [False, True])
async def test_private_desktop_requires_access_link(digest_only):
    """Reject anonymous access and exchange a valid private link for a secure cookie."""
    token = "transport-fixture-access-key-123456789"
    finished = asyncio.Event()
    async with TestClient(
        TestServer(
            desktop_proxy(
                None,
                "http://127.0.0.1:1",
                finished,
                access_token=None if digest_only else token,
                access_token_sha256=hashlib.sha256(token.encode()).hexdigest()
                if digest_only
                else None,
            )
        )
    ) as client:
        assert (await client.get("/api/health")).status == 403
        assert (await client.post("/api/finish")).status == 403
        assert not finished.is_set()
        response = await client.get("/?access_token=wrong", allow_redirects=False)
        assert response.status == 403
        response = await client.get("/?access_token=" + token, allow_redirects=False)
        assert response.status == 302
        cookie = response.cookies["sts_session"]
        assert cookie.value == token
        assert cookie["httponly"] and cookie["secure"]
        assert cookie["samesite"] == "Strict"
        headers = {"Cookie": "sts_session=" + cookie.value}
        response = await client.get("/api/health", headers=headers)
        assert response.status == 200
        assert (await response.json())["model_calls"] == 0
        assert (await client.post("/api/finish", headers=headers)).status == 200
        assert finished.is_set()


@pytest.mark.asyncio
async def test_tunnel_rejects_wrong_release_digest(monkeypatch):
    """Refuse to execute a downloaded tunnel binary whose checksum differs."""
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *args, **kwargs: io.BytesIO(b"fixture")
    )
    with pytest.raises(RuntimeError, match="checksum"):
        await browser_tunnel(6080, "https://example.invalid/fixture", "0" * 64)


@pytest.mark.asyncio
async def test_tunnel_runs_verified_executable(monkeypatch):
    """Launch a verified fixture and collect its output through the real process path."""
    binary = b"#!/bin/sh\n[ \"$1\" = tunnel ] || exit 2\nprintf 'fixture tunnel started\\n'\n"
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *args, **kwargs: io.BytesIO(binary)
    )
    process, output = await browser_tunnel(
        6080, "https://example.invalid/fixture", hashlib.sha256(binary).hexdigest()
    )
    assert await process.wait() == 0
    await output


@pytest.mark.parametrize("game", ["sts1", "sts2"])
def test_manual_game_selection_and_profile_export(monkeypatch, tmp_path, game):
    """Run the real manual solver and retain only the selected game's save data."""
    from inspect_ai import eval as inspect_eval
    from inspect_ai.util import ExecResult

    from sts_hawk import manual, runtime

    class Environment:
        """Capture manual lifecycle commands without launching a game or model."""

        def __init__(self):
            """Initialize the command history and prepared server files."""
            self.commands = []
            self.files = {}

        async def exec(self, cmd, **kwargs):
            """Complete startup and finish signals through the real solver path."""
            self.commands.append(cmd)
            return ExecResult(True, 0, "Sandbox desktop ready", "")

        async def write_file(self, path, content):
            """Capture files prepared for the desktop server."""
            self.files[path] = content

        async def read_file(self, path, text=True):
            """Return the fixture profile archive at the real export boundary."""
            assert path == "/tmp/sts-manual-profile.tar.gz" and not text
            return b"profile archive fixture"

    environment = Environment()
    monkeypatch.setattr(manual, "sandbox", lambda: environment)
    monkeypatch.setattr(runtime, "sandbox", lambda: environment)
    task = manual.manual_session(game=game)
    assert task.name == f"{game}_manual_session"
    assert task.metadata["manual_game"] == game
    task.setup = None
    task.sandbox = None
    result = inspect_eval(
        task, model="mockllm/model", log_dir=str(tmp_path), display="none"
    )[0]
    assert result.status == "success" and not result.samples[0].model_usage
    archive_command = environment.commands[-1][-1]
    if game == "sts1":
        assert "tar -C /game" in archive_command
        assert "preferences saves info.displayconfig" in archive_command
    else:
        assert "tar -C /root/.local/share/SlayTheSpire2" in archive_command
    assert any(
        event.event == "info"
        and isinstance(event.data, dict)
        and "profile_archive_base64" in event.data
        for event in result.samples[0].events
    )


def test_manual_rejects_unknown_game():
    """Reject an invalid game before preparing a sandbox."""
    from sts_hawk.manual import manual_session

    with pytest.raises(ValueError, match="Unknown game"):
        manual_session(game="unknown")
