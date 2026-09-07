"""Storage change pushes — vendor-neutral webhook dispatcher.

One generic route (/api/webhooks/storage/{provider}) + per-provider payload
parsers turns any storage app's change push into a funnel refresh: WorkDrive
custom-app events, Microsoft Graph change notifications, Box event arrays,
and Google Drive/Dropbox pings (resync). Adding a business's storage app is
one parser + one spec row — never a per-business route.

Auth fails CLOSED: no provider secret configured -> 401 for everything.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.webhook_routes as wh
import integrations.storage_change_events as sce


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(wh.router)
    return TestClient(app)


# ---- auth: fail-closed ---------------------------------------------------

def test_auth_fails_closed_when_secret_unset(monkeypatch):
    monkeypatch.delenv("WORKDRIVE_WEBHOOK_SECRET", raising=False)
    r = _client().post("/api/webhooks/storage/zoho_workdrive?token=anything", json={})
    assert r.status_code == 401


def test_auth_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "right")
    r = _client().post("/api/webhooks/storage/zoho_workdrive?token=wrong", json={})
    assert r.status_code == 401
    r = _client().post(
        "/api/webhooks/storage/zoho_workdrive",
        headers={"Authorization": "Bearer wrong"}, json={})
    assert r.status_code == 401


def test_unknown_provider_is_404(monkeypatch):
    monkeypatch.setenv("DROPBOX_WEBHOOK_SECRET", "tok")
    r = _client().post("/api/webhooks/storage/not_a_cloud?token=tok", json={})
    assert r.status_code == 404


# ---- payload parsers (pure) ----------------------------------------------

def test_parse_workdrive_event_shapes():
    parse = sce.parse_workdrive_event
    assert parse({"file_ids": ["abc123def456789"]}, {}) == {"file_ids": ["abc123def456789"]}
    assert parse({"resource_id": "u8ai1e3a4ceb717574b5bbf2042"}, {}) == {
        "file_ids": ["u8ai1e3a4ceb717574b5bbf2042"]}
    assert parse({"events": [{"target": {"unique_id": "u8ai1e3a4ceb717574b5bbf2042"}}]}, {}) == {
        "file_ids": ["u8ai1e3a4ceb717574b5bbf2042"]}
    assert parse({"message": "nothing here"}, {}) == {}
    assert parse("not a dict", {}) == {}


def test_parse_onedrive_graph_notification():
    payload = {"value": [{
        "subscriptionId": "sub-1",
        "resourceData": {"id": "01ABC-driveItem-id-123456",
                         "@odata.type": "#Microsoft.Graph.driveItem"},
    }]}
    assert sce.parse_onedrive_event(payload, {}) == {
        "file_ids": ["01ABC-driveItem-id-123456"]}
    assert sce.parse_onedrive_event({"value": []}, {}) == {}


def test_parse_box_event_array():
    payload = [
        {"trigger": "FILE.UPLOADED", "source": {"id": "123456789", "type": "file"}},
        {"trigger": "FOLDER.CREATED", "source": {"id": "999", "type": "folder"}},
    ]
    assert sce.parse_box_event(payload, {}) == {"file_ids": ["123456789"]}


def test_parse_gdrive_and_dropbox_pings_are_resync():
    # Google Drive channels and Dropbox webhooks only ping — no file ids.
    assert sce.parse_resync_event({}, {"X-Goog-Resource-State": "update"}) == {"resync": True}
    assert sce.parse_resync_event({"list_folder": {"accounts": ["dbid:AAA"]}}, {}) == {"resync": True}


# ---- dispatch: valid events queue the right refresh -----------------------

def test_workdrive_event_dispatches_file_refresh(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "tok")
    mock_refresh = AsyncMock(return_value={"success": True, "refreshed": 1})
    with patch("integrations.storage_change_events.queue_provider_refresh", mock_refresh):
        r = _client().post(
            "/api/webhooks/storage/zoho_workdrive?token=tok",
            json={"resource_id": "u8ai1e3a4ceb717574b5bbf2042",
                  "event": "FILES_EDITED"})
    assert r.status_code == 202
    mock_refresh.assert_awaited_once()
    provider, event = mock_refresh.await_args.args
    assert provider == "zoho_workdrive"
    assert event == {"file_ids": ["u8ai1e3a4ceb717574b5bbf2042"]}


def test_legacy_workdrive_alias_route_still_works(monkeypatch):
    """Existing WorkDrive custom-app webhook URLs (configured before the
    generic route) must keep working."""
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "tok")
    mock_refresh = AsyncMock(return_value={"success": True})
    with patch("integrations.storage_change_events.queue_provider_refresh", mock_refresh):
        r = _client().post(
            "/api/webhooks/zoho-workdrive?token=tok",
            json={"resource_id": "u8ai1e3a4ceb717574b5bbf2042"})
    assert r.status_code == 202
    mock_refresh.assert_awaited_once()


def test_gdrive_ping_dispatches_resync(monkeypatch):
    monkeypatch.setenv("GDRIVE_WEBHOOK_SECRET", "tok")
    mock_refresh = AsyncMock(return_value={"success": True})
    with patch("integrations.storage_change_events.queue_provider_refresh", mock_refresh):
        r = _client().post(
            "/api/webhooks/storage/google_drive?token=tok",
            headers={"X-Goog-Resource-State": "update"},
            json={})
    assert r.status_code == 202
    provider, event = mock_refresh.await_args.args
    assert provider == "google_drive" and event == {"resync": True}


def test_noop_event_is_accepted(monkeypatch):
    monkeypatch.setenv("WORKDRIVE_WEBHOOK_SECRET", "tok")
    r = _client().post("/api/webhooks/storage/zoho_workdrive?token=tok",
                       json={"event": "FOLDER_VIEWED"})
    assert r.status_code == 202
    assert r.json()["message"]
