"""Rate-limit handling + one-shot guard for ZohoWorkDriveService.

Zoho's per-DC throttle 429'd an unpaced full-tree walk into uselessness
(observed live 2026-09-02: every folder listing returned 429, the sync
ingested nothing, and the UI gave no feedback). _zoho_get now paces
requests and honors Retry-After, and full_sync refuses concurrent walks
per user.
"""
import asyncio
import time
from types import SimpleNamespace

import pytest

from integrations.zoho_workdrive_service import ZohoWorkDriveService


def _svc(min_interval: float = 0.0) -> ZohoWorkDriveService:
    svc = ZohoWorkDriveService()
    svc._MIN_API_INTERVAL_SECONDS = min_interval
    return svc


class _FakeClient:
    """Queues stubbed httpx responses; records every GET."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.urls = []

    async def get(self, url, headers=None, params=None):
        self.calls += 1
        self.urls.append(url)
        return self._responses.pop(0)


def _resp(status, retry_after=None, body=None):
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return SimpleNamespace(
        status_code=status, headers=headers, json=lambda: (body or {})
    )


@pytest.mark.asyncio
async def test_zoho_get_retries_429_then_succeeds():
    svc = _svc()
    svc.client = _FakeClient([
        _resp(429, retry_after="0"),
        _resp(429, retry_after="0"),
        _resp(200, body={"data": []}),
    ])

    response = await svc._zoho_get("https://workdrive.example/files", headers={})

    assert response.status_code == 200
    assert svc.client.calls == 3


@pytest.mark.asyncio
async def test_zoho_get_gives_up_after_max_retries():
    svc = _svc()
    responses = [_resp(429, retry_after="0") for _ in range(svc._MAX_429_RETRIES + 1)]
    svc.client = _FakeClient(responses)

    response = await svc._zoho_get("https://workdrive.example/files", headers={})

    # Initial attempt + _MAX_429_RETRIES retries, then the last 429 is
    # returned to the caller (list_files logs + skips the folder).
    assert svc.client.calls == svc._MAX_429_RETRIES + 1
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_zoho_get_exponential_backoff_when_retry_after_missing():
    svc = _svc()
    svc.client = _FakeClient([_resp(429), _resp(200, body={"data": []})])

    started = time.monotonic()
    response = await svc._zoho_get("https://workdrive.example/files", headers={})
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    # No Retry-After header → exponential fallback: first retry waits 2**0 s.
    assert elapsed >= 1.0


@pytest.mark.asyncio
async def test_zoho_get_paces_consecutive_requests():
    svc = _svc(min_interval=0.05)
    svc.client = _FakeClient([
        _resp(200, body={"data": []}),
        _resp(200, body={"data": []}),
    ])

    await svc._zoho_get("https://workdrive.example/a", headers={})
    started = time.monotonic()
    await svc._zoho_get("https://workdrive.example/b", headers={})
    elapsed = time.monotonic() - started

    # The second call must wait out the minimum interval (first call set
    # _last_zoho_request_at moments earlier).
    assert elapsed >= 0.04


@pytest.mark.asyncio
async def test_full_sync_refuses_concurrent_walk():
    svc = _svc()
    walk_started = asyncio.Event()
    release_walk = asyncio.Event()

    async def _slow_inner(*args, **kwargs):
        walk_started.set()
        await release_walk.wait()
        return {"success": True}

    svc._full_sync_inner = _slow_inner

    first = asyncio.create_task(svc.full_sync("u1"))
    await walk_started.wait()

    second = await svc.full_sync("u1")
    assert second == {"success": False, "error": "sync_already_running"}

    release_walk.set()
    result = await first
    assert result["success"] is True


@pytest.mark.asyncio
async def test_full_sync_releases_guard_when_walk_errors():
    svc = _svc()

    async def _boom_inner(*args, **kwargs):
        raise RuntimeError("boom")

    svc._full_sync_inner = _boom_inner

    with pytest.raises(RuntimeError):
        await svc.full_sync("u1")

    # The guard must not wedge: a later walk is allowed after a failure.
    assert svc.is_full_sync_running("u1") is False
