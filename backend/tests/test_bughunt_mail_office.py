"""
Bug-hunt tests (TDD RED->GREEN) for the mail/office integration modules:

- integrations/gmail_service.py
- integrations/outlook_service.py
- integrations/outlook_service_enhanced.py
- integrations/microsoft365_service.py
- integrations/atom_telegram_integration.py
- integrations/atom_google_chat_integration.py
- integrations/workspace_sync_service.py

Each test asserts the CORRECT behavior; run RED against the unfixed code,
then the source fix flips it GREEN.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_gmail():
    """GmailService instance without __init__ side effects (no auth)."""
    from integrations.gmail_service import GmailService

    svc = GmailService.__new__(GmailService)
    svc.tenant_id = "default"
    svc.config = {}
    svc.service = None
    return svc


# ============================================================================
# gmail_service.py
# ============================================================================

def test_gmail_fetch_recent_messages_ingests_without_typeerror():
    """fetch_recent_messages must not ``await`` the sync get_messages() list —
    awaiting a plain list raises TypeError and the hub sync silently dies."""
    from integrations import gmail_service as mod

    svc = make_gmail()
    msg = {"id": "1", "attachments": []}
    svc.get_messages = Mock(return_value=[msg])
    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"
    ) as gp:
        pipe = Mock()
        pipe.ingest_message = AsyncMock(return_value=True)
        gp.return_value = pipe
        result = asyncio.run(svc.fetch_recent_messages("u1", max_results=5))

    assert result == [msg]
    pipe.ingest_message.assert_called_once_with("google", msg)


def test_gmail_sync_calendar_events_runs_full_implementation():
    """sync_calendar_events must ingest events via the real pipeline (the old
    code imported a phantom core.collaboration_hub_service module and called a
    phantom pipeline.ingest_calendar_event method — the sync silently died)."""
    from integrations import gmail_service as mod

    svc = make_gmail()
    cal = Mock()
    cal.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "ev1",
                "start": {"dateTime": "2026-08-01T10:00:00Z"},
                "end": {"dateTime": "2026-08-01T11:00:00Z"},
                "summary": "S",
                "description": "D",
                "location": "L",
                "organizer": {"email": "o@x.com"},
                "attendees": [],
                "status": "confirmed",
            }
        ]
    }
    svc._get_calendar_service = Mock(return_value=cal)

    pipe = Mock()
    pipe.ingest_message = AsyncMock(return_value=True)
    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
        return_value=pipe,
    ):
        asyncio.run(svc.sync_calendar_events("u1", days_ahead=7))

    pipe.ingest_message.assert_called_once()
    app_type = pipe.ingest_message.call_args[0][0]
    payload = pipe.ingest_message.call_args[0][1]
    assert app_type == "google_calendar"
    assert payload["id"] == "ev1"
    assert payload["title"] == "S"


def test_gmail_execute_operation_404_maps_to_resource_not_found():
    """Error mapping must not crash: IntegrationErrorCode has no NOT_FOUND
    member — a 404 must map to RESOURCE_NOT_FOUND."""
    from integrations import gmail_service as mod

    svc = make_gmail()
    with patch.object(svc, "get_message", side_effect=Exception("404 not found")):
        result = asyncio.run(svc.execute_operation("get_message", {"message_id": "x"}))

    assert result["success"] is False
    assert result["error"] == "RESOURCE_NOT_FOUND"


def test_gmail_execute_operation_forbidden_maps_to_permission_denied():
    """403/permission errors must map to PERMISSION_DENIED (FORBIDDEN does not
    exist on IntegrationErrorCode)."""
    from integrations import gmail_service as mod

    svc = make_gmail()
    with patch.object(svc, "get_message", side_effect=Exception("forbidden")):
        result = asyncio.run(svc.execute_operation("get_message", {"message_id": "x"}))

    assert result["success"] is False
    assert result["error"] == "PERMISSION_DENIED"


def test_gmail_http_error_class_resolvable_when_google_libs_installed():
    """When google libs are installed the module must still resolve HttpError;
    otherwise `except HttpError` raises NameError and the pagination loop in
    get_messages/get_threads breaks instead of stopping cleanly."""
    from integrations import gmail_service as mod

    if mod.GOOGLE_APIS_AVAILABLE:
        from googleapiclient.errors import HttpError as ExpectedHttpError

        assert mod.HttpError is ExpectedHttpError
    else:
        assert issubclass(mod.HttpError, Exception)


def test_gmail_tenant_mismatch_rejected():
    """execute_operation must reject cross-tenant context instead of running."""
    from integrations import gmail_service as mod

    svc = make_gmail()
    result = asyncio.run(
        svc.execute_operation(
            "list_messages", {}, context={"tenant_id": "other-tenant"}
        )
    )
    assert result["success"] is False
    assert "Tenant ID mismatch" in result["error"]


# ============================================================================
# outlook_service.py
# ============================================================================

def test_outlook_is_token_expired_handles_float_timestamps():
    """_is_token_expired receives `expires_at.timestamp()` (a float) from
    _get_access_token — it must compare timestamps, not try str.replace() on
    a float (which raises AttributeError and always returns True)."""
    from integrations.outlook_service import OutlookService

    svc = OutlookService("default", {})
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()

    assert svc._is_token_expired({"expires_at": past}) is True
    assert svc._is_token_expired({"expires_at": future}) is False


def test_outlook_handle_response_accepts_202():
    """Microsoft Graph POST /me/sendMail returns 202 Accepted with no body —
    that is a SUCCESS, not an error."""
    from integrations.outlook_service import OutlookService

    svc = OutlookService("default", {})

    class FakeResp:
        status = 202

        async def json(self):
            return {}

        async def text(self):
            return ""

    result = asyncio.run(svc._handle_response(FakeResp()))
    assert result == {"success": True}


def test_outlook_send_email_success_after_202():
    """send_email must surface success for a 202 response (mail sent), i.e.
    execute_operation must not report failure for a sent mail."""
    from integrations.outlook_service import OutlookService

    svc = OutlookService("default", {})
    svc._make_graph_request = AsyncMock(return_value={"success": True})

    result = asyncio.run(
        svc.send_email("u1", ["a@b.c"], "Subj", "Body")
    )
    assert result == {"success": True}


# ============================================================================
# outlook_service_enhanced.py
# ============================================================================

def test_enhanced_handle_response_accepts_202():
    """Enhanced sendMail also returns 202 with an empty body — must be handled
    as success instead of failing on response.json()."""
    from integrations.outlook_service_enhanced import OutlookEnhancedService

    svc = OutlookEnhancedService()

    class FakeResp:
        status = 202
        headers = {}

        def raise_for_status(self):
            pass

        async def json(self):
            raise Exception("202 Accepted responses have no JSON body")

    result = asyncio.run(
        svc._handle_response(FakeResp(), "POST", "/me/sendMail", "u1", {}, None, False)
    )
    assert result == {"success": True}


# ============================================================================
# microsoft365_service.py
# ============================================================================

def test_ms365_get_service_status_exists():
    """get_service_status is referenced by the /services/status route but was
    never defined — the route 500s. It must exist and return a success dict."""
    from integrations.microsoft365_service import Microsoft365Service

    svc = Microsoft365Service("default", {})
    svc._make_graph_request = AsyncMock(
        return_value={"status": "success", "data": {"id": "u1", "displayName": "A"}}
    )
    result = asyncio.run(svc.get_service_status("tok"))
    assert result["status"] == "success"
    assert "data" in result


def test_ms365_services_status_route_returns_200():
    """The /services/status router handler must not blow up. The router now
    requires session auth at the router level (R38-40 anon sweep), so the
    test overrides get_current_user."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace

    from integrations.microsoft365_service import microsoft365_router
    from core.auth import get_current_user

    app = FastAPI()
    app.include_router(microsoft365_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1", role="member"
    )
    client = TestClient(app, raise_server_exceptions=False)

    with patch(
        "integrations.microsoft365_service.microsoft365_service._make_graph_request",
        new=AsyncMock(return_value={"status": "success", "data": {"id": "u1"}}),
    ):
        resp = client.get("/microsoft365/services/status?access_token=tok")
    assert resp.status_code == 200


# ============================================================================
# atom_telegram_integration.py
# ============================================================================

def test_telegram_callback_query_routes_to_action_handler():
    """handle_callback_query references an undefined `user_id` (only
    `from_user` is extracted) — every callback dies with NameError and the
    action is never executed. It must route to the action handler."""
    from integrations.atom_telegram_integration import AtomTelegramIntegration

    svc = AtomTelegramIntegration(
        {"bot_token": "x", "enable_enterprise_features": False}
    )
    svc.answer_callback_query = AsyncMock()

    asyncio.run(
        svc.handle_callback_query(
            {
                "id": "cq1",
                "data": "action_approve_request_123",
                "message": {},
                "from": {"id": 42},
            }
        )
    )

    texts = [c.kwargs.get("text") for c in svc.answer_callback_query.await_args_list]
    assert texts[-1] == "Request approved"


def test_telegram_callback_unknown_action_answered():
    """Unknown callback data must be answered with an alert, not crash."""
    from integrations.atom_telegram_integration import AtomTelegramIntegration

    svc = AtomTelegramIntegration(
        {"bot_token": "x", "enable_enterprise_features": False}
    )
    svc.answer_callback_query = AsyncMock()

    asyncio.run(
        svc.handle_callback_query(
            {"id": "cq2", "data": "nope_prefix", "message": {}, "from": {"id": 1}}
        )
    )
    texts = [c.kwargs.get("text") for c in svc.answer_callback_query.await_args_list]
    assert texts[-1] == "Unknown action"


# ============================================================================
# atom_google_chat_integration.py
# ============================================================================

def test_gchat_enhanced_service_available_at_import():
    """The module imports `google_chat_enhanced_service` which does not exist
    (the source module only defines the class) — the whole integration runs
    with service=None and every operation falls back to "simulated". The
    module must expose a live service instance."""
    from integrations import atom_google_chat_integration as mod

    assert mod.google_chat_enhanced_service is not None


def test_gchat_cross_platform_handlers_register():
    """_setup_cross_platform_handlers references GoogleChatEventType which is
    never imported — NameError kills initialize() when a service is present.
    Handlers must be registered on the service event bus."""
    from integrations import atom_google_chat_integration as mod
    from integrations.google_chat_enhanced_service import GoogleChatEventType

    svc = mod.AtomGoogleChatIntegration({})
    fake = Mock()
    fake.event_handlers = {t: [] for t in GoogleChatEventType}
    svc.google_chat_service = fake

    asyncio.run(svc._setup_cross_platform_handlers())

    assert len(fake.event_handlers[GoogleChatEventType.MESSAGE]) == 1
    assert len(fake.event_handlers[GoogleChatEventType.ADDED_TO_SPACE]) == 1


def test_gchat_oauth_callback_fails_closed_without_state():
    """OAuth callback "validates" state by only logging it (fail-open CSRF) —
    with no state at all it must refuse to exchange the code."""
    from integrations import atom_google_chat_integration as mod

    svc = mod.AtomGoogleChatIntegration({})
    with patch.dict(
        os.environ,
        {"GOOGLE_CHAT_CLIENT_ID": "cid", "GOOGLE_CHAT_CLIENT_SECRET": "csec"},
    ), patch("httpx.AsyncClient") as ac:
        post = AsyncMock(
            return_value=Mock(
                status_code=200,
                json=lambda: {"access_token": "t", "refresh_token": "r"},
            )
        )
        ac.return_value.__aenter__.return_value.post = post

        result = asyncio.run(svc.handle_oauth_callback(code="code123", state=None))

    assert result["success"] is False
    assert "state" in result.get("error", "").lower()


# ============================================================================
# workspace_sync_service.py
# ============================================================================

@pytest.fixture()
def sync_db():
    engine = create_engine("sqlite://")
    from core.models import UnifiedWorkspace, WorkspaceSyncLog

    UnifiedWorkspace.__table__.create(engine, checkfirst=True)
    WorkspaceSyncLog.__table__.create(engine, checkfirst=True)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()
    engine.dispose()


def test_workspace_sync_add_platform_to_workspace(sync_db):
    """add_platform_to_workspace calls workspace.get_platform_id()/add_platform()
    which don't exist on the UnifiedWorkspace model — every add raises
    AttributeError. It must update the platform column directly."""
    from integrations.workspace_sync_service import WorkspaceSyncService

    svc = WorkspaceSyncService(sync_db)
    ws = svc.create_unified_workspace(
        user_id="u1", name="W", slack_workspace_id="T1", google_chat_space_id="G1"
    )
    assert ws.platform_count == 2

    updated = svc.add_platform_to_workspace(ws.id, "discord", "D1")
    assert updated.discord_guild_id == "D1"
    assert updated.platform_count == 3


def test_workspace_sync_propagate_change_success(sync_db):
    """propagate_change routes to _apply_change_to_platform which calls the
    phantom model method get_platform_id() — every target fails with
    AttributeError and the sync always reports failure."""
    from integrations.workspace_sync_service import (
        ChangeType,
        WorkspaceSyncService,
    )

    svc = WorkspaceSyncService(sync_db)
    ws = svc.create_unified_workspace(
        user_id="u1",
        name="W",
        slack_workspace_id="T1",
        discord_guild_id="D1",
        teams_team_id="M1",
    )

    result = svc.propagate_change(
        ws.id,
        "google_chat",
        ChangeType.WORKSPACE_NAME_CHANGE,
        {"new_name": "W2"},
    )

    assert result["status"] == "success"
    assert set(result["successful_platforms"]) == {"slack", "discord", "teams"}
    assert result["failed_platforms"] == []


def test_workspace_sync_slack_propagation_service_resolvable(sync_db):
    """_apply_slack_change imports a phantom instance name — the module only
    defines SlackEnhancedService. The import must resolve so Slack changes
    propagate instead of returning "Slack service unavailable"."""
    from integrations.workspace_sync_service import (
        ChangeType,
        WorkspaceSyncService,
    )

    svc = WorkspaceSyncService(sync_db)
    ws = svc.create_unified_workspace(
        user_id="u1", name="W", slack_workspace_id="T1"
    )

    result = svc.propagate_change(
        ws.id,
        "discord",
        ChangeType.WORKSPACE_NAME_CHANGE,
        {"new_name": "W2"},
    )

    assert result["status"] == "success"
    assert result["successful_platforms"] == ["slack"]
