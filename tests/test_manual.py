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
