"""WorkDrive file-change push webhook — real-time pricing freshness.

A price-list edit at the source used to wait for the next hourly sync
before the agent could see it (and before the key-mismatch fix, forever).
The webhook closes that gap: WorkDrive custom-app events hit
/api/webhooks/zoho-workdrive and the touched files re-ingest immediately,
for every connected account. These tests pin:
  - auth fails CLOSED (401) when WORKDRIVE_WEBHOOK_SECRET is unset,
    on wrong token, and accepts the token as ?token= (WorkDrive custom
    apps put the key in the endpoint URL);
  - file-id extraction from the varying event payload shapes;
  - a valid event queues a refresh for each connected user, and unknown
    files respond 202 without work.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.webhook_routes as wh


def _client() -> TestClient:
    # NOTE: no importlib.reload here — reloading inside a test would rebind
    # module functions and defeat patch.object on wh._workdrive_connected_user_ids.
    app = FastAPI()
    app.include_router(wh.router)
    return TestClient(app)


def _mock_ingest(status="ingested"):
    """Patch the ingest call the background refresh makes."""
    svc = MagicMock()
    svc.ingest_file_to_memory = AsyncMock(return_value={
        "success": True, "result": {"status": status}})
    return svc


# ---- auth: fail-closed -------------------------------------------------

def test_auth_fails_closed_when_secret_unset(monkeypatch):
    monkeypatch.delenv("WORKDRIVE_WEBHOOK_SECRET", raising=False)
    r = _client().post("/api/webhooks/zoho-workdrive?token=anything", json={})
    assert r.status_code == 401


def test_auth_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "right")
    r = _client().post("/api/webhooks/zoho-workdrive?token=wrong", json={})
    assert r.status_code == 401
    r = _client().post(
        "/api/webhooks/zoho-workdrive",
        headers={"Authorization": "Bearer wrong"}, json={})
    assert r.status_code == 401


# ---- file-id extraction (pure) ------------------------------------------

def test_extract_file_ids_from_common_event_shapes():
    extract = wh._extract_workdrive_file_ids
    assert extract({"file_ids": ["abc123def456789"]}) == ["abc123def456789"]
    assert extract({"resource_id": "u8ai1e3a4ceb717574b5bbf2042"}) == ["u8ai1e3a4ceb717574b5bbf2042"]
    assert extract({"data": {"file_id": "9ef83433837cdf6b841b6b7604"}}) == ["9ef83433837cdf6b841b6b7604"]
    # scans for Zoho-id-shaped strings when the key is unrecognized
    assert extract({"events": [{"target": {"unique_id": "u8ai1e3a4ceb717574b5bbf2042"}}]}) == [
        "u8ai1e3a4ceb717574b5bbf2042"]
    assert extract({"message": "nothing here"}) == []
    assert extract("not a dict") == []


# ---- valid event queues refreshes ---------------------------------------

def test_valid_event_queues_refresh(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "tok")
    svc = _mock_ingest()
    with patch.object(wh, "_workdrive_connected_user_ids",
                      return_value=["user-1", "user-2"]), \
         patch("integrations.zoho_workdrive_service.ZohoWorkDriveService",
               return_value=svc):
        r = _client().post(
            "/api/webhooks/zoho-workdrive?token=tok",
            json={"resource_id": "u8ai1e3a4ceb717574b5bbf2042",
                  "event": "FILES_EDITED"})
    assert r.status_code == 202
    assert r.json()["files_matched"] == 1
    assert r.json()["users"] == 2
    # background refresh: one ingest per (user, file); TestClient runs it
    assert svc.ingest_file_to_memory.await_count == 2


def test_event_without_file_ids_is_accepted_noop(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "tok")
    with patch.object(wh, "_workdrive_connected_user_ids",
                      return_value=["user-1"]):
        r = _client().post("/api/webhooks/zoho-workdrive?token=tok",
                           json={"event": "FOLDER_VIEWED"})
    assert r.status_code == 202
    assert r.json()["files_matched"] == 0


def test_no_connected_account_is_accepted_noop(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "tok")
    with patch.object(wh, "_workdrive_connected_user_ids", return_value=[]):
        r = _client().post(
            "/api/webhooks/zoho-workdrive?token=tok",
            json={"resource_id": "u8ai1e3a4ceb717574b5bbf2042"})
    assert r.status_code == 202
    assert r.json()["users"] == 0
