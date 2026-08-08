"""Coverage push + bug hunt for the zero-coverage integration cluster:

- integrations.atom_zoom_integration
- integrations.bytewax_service
- integrations.slack_workflow_automation
- integrations.atom_chat_interface

TDD: tests that expose REAL bugs are marked BUG-<n>; they fail before the
minimal fix and pass after.
"""
import asyncio
import json
import queue as queue_mod
import time
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_chat_interface as chat_mod
import integrations.atom_zoom_integration as zoom_mod
import integrations.bytewax_service as bw_mod
import integrations.slack_workflow_automation as slack_mod
from integrations.atom_ingestion_pipeline import AtomRecordData

pytestmark = pytest.mark.asyncio


def _resp(status_code: int = 200, json_data: dict = None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    return r


def _slack_workflow(**kw):
    defaults = dict(
        id="wf1", name="Test Workflow", description="desc",
        triggers=[], actions=[], created_by="user1",
        created_at=datetime.now(timezone.utc), active=True,
        execution_count=0, last_executed=None,
    )
    defaults.update(kw)
    return slack_mod.SlackWorkflow(**defaults)


def _slack_action(action_type, **kw):
    defaults = dict(id="a1", type=action_type, parameters={}, delay_seconds=0,
                    retry_count=0, success_message=None)
    defaults.update(kw)
    return slack_mod.SlackWorkflowAction(**defaults)


def _slack_trigger(trigger_type, **kw):
    defaults = dict(id="t1", type=trigger_type, conditions={}, workspace_id="",
                    channel_ids=[], user_ids=[], keywords=[], active=True)
    defaults.update(kw)
    return slack_mod.SlackWorkflowTrigger(**defaults)


# ===========================================================================
# atom_zoom_integration
# ===========================================================================


class TestZoomBasics:
    def test_enums(self):
        assert zoom_mod.ZoomEventType.MEETING_STARTED.value == "meeting.started"
        assert zoom_mod.ZoomMeetingType.SCHEDULED.value == "scheduled"
        assert zoom_mod.ZoomUserType.LICENSED.value == "licensed"
        assert zoom_mod.ZoomCommandType.AUTOMATE.value == "automate"

    def test_global_instance(self):
        assert zoom_mod.atom_zoom_integration is not None
        assert zoom_mod.atom_zoom_integration.config.get("enable_enterprise_features") is True

    def test_construct_with_env_credentials(self, monkeypatch):
        monkeypatch.setenv("ZOOM_API_KEY", "k")
        monkeypatch.setenv("ZOOM_API_SECRET", "s")
        svc = zoom_mod.AtomZoomIntegration({})
        assert svc.zoom_config["api_key"] == "k"
        assert svc.zoom_config["api_secret"] == "s"
        assert svc.analytics_metrics["total_meetings"] == 0

    def test_construct_defaults(self):
        svc = zoom_mod.AtomZoomIntegration({})
        assert svc.zoom_config["max_participants"] == 1000
        assert svc.zoom_config["api_base_url"] == "https://api.zoom.us/v2"
        assert svc.db is None
        assert not svc.is_initialized

    def test_zoom_user_dataclass(self):
        user = zoom_mod.ZoomUser(
            user_id="u1", email="a@b.c", first_name="A", last_name="B",
            display_name="A B", user_type=zoom_mod.ZoomUserType.BASIC,
            role="member", timezone="UTC", is_active=True, permissions=[],
            security_level="standard", created_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc), metadata={},
        )
        assert user.user_id == "u1"


class TestZoomInitialize:
    async def _svc(self, monkeypatch):
        svc = zoom_mod.AtomZoomIntegration({
            "api_key": "k", "api_secret": "s",
            "webhook_url": "http://localhost/hook",
        })
        svc.http_session = MagicMock()
        svc.http_session.get = AsyncMock(return_value=_resp(200))
        svc.http_session.post = AsyncMock(return_value=_resp(201))
        return svc

    async def test_initialize_success(self, monkeypatch):
        svc = await self._svc(monkeypatch)
        svc.enterprise_security = MagicMock()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(
            return_value={"ok": True})
        ok = await svc.initialize()
        assert ok is True
        assert svc.is_initialized is True
        assert svc.security_policies
        assert svc.compliance_rules
        assert svc.automation_triggers
        assert svc.security_monitoring
        assert svc.compliance_monitoring
        assert svc.webhook_handlers
        assert hasattr(svc, "_start_time")

    async def test_initialize_missing_credentials(self, monkeypatch):
        for var in ("ZOOM_API_KEY", "ZOOM_API_SECRET", "ZOOM_CLIENT_ID",
                    "ZOOM_CLIENT_SECRET"):
            monkeypatch.delenv(var, raising=False)
        svc = zoom_mod.AtomZoomIntegration({})
        svc.http_session = MagicMock()
        ok = await svc.initialize()
        assert ok is False
        assert svc.is_initialized is False

    async def test_initialize_exception_path(self, monkeypatch):
        svc = await self._svc(monkeypatch)
        svc._test_api_connection = AsyncMock(side_effect=RuntimeError("boom"))
        ok = await svc.initialize()
        assert ok is False

    async def test_initialize_no_credentials_no_http(self, monkeypatch):
        """initialize() with no credentials must not attempt HTTP calls."""
        for var in ("ZOOM_API_KEY", "ZOOM_API_SECRET", "ZOOM_CLIENT_ID",
                    "ZOOM_CLIENT_SECRET"):
            monkeypatch.delenv(var, raising=False)
        svc = zoom_mod.AtomZoomIntegration({})
        svc.http_session = MagicMock()
        svc.http_session.get = AsyncMock()
        svc.http_session.post = AsyncMock()
        ok = await svc.initialize()
        assert ok is False
        svc.http_session.get.assert_not_awaited()

    async def test_initialize_client_credentials_flow(self, monkeypatch):
        svc = zoom_mod.AtomZoomIntegration({
            "client_id": "cid", "client_secret": "cs",
        })
        svc.http_session = MagicMock()
        svc.http_session.get = AsyncMock(return_value=_resp(200))
        svc.http_session.post = AsyncMock(return_value=_resp(201))
        ok = await svc.initialize()
        assert ok is True

    async def test_initialize_no_webhook_url(self, monkeypatch):
        svc = zoom_mod.AtomZoomIntegration({"api_key": "k", "api_secret": "s"})
        svc.http_session = MagicMock()
        svc.http_session.get = AsyncMock(return_value=_resp(200))
        ok = await svc.initialize()
        assert ok is True
        assert svc.is_initialized is True


class TestZoomWorkspaces:
    def _svc_with_meeting(self):
        svc = zoom_mod.AtomZoomIntegration({"api_key": "k", "api_secret": "s"})
        meeting = zoom_mod.ZoomMeeting(
            meeting_id="m1", topic="Sales Sync", meeting_type=zoom_mod.ZoomMeetingType.INSTANT,
            host_id="host1", start_time=datetime.now(timezone.utc), duration=30,
            timezone="UTC", agenda="Discuss Q3", participants=["host1", "user2"],
            is_recorded=False, password=None, waiting_room=True,
            security_level="standard", created_at=datetime.now(timezone.utc),
            status="started", metadata={},
        )
        svc.active_meetings["m1"] = meeting
        return svc, meeting

    async def test_get_intelligent_workspaces(self):
        svc, meeting = self._svc_with_meeting()
        workspaces = await svc.get_intelligent_workspaces("host1")
        assert len(workspaces) == 1
        ws = workspaces[0]
        assert ws["id"] == "m1" and ws["is_active"] is True
        assert ws["permissions"]["can_join"] is True
        assert ws["permissions"]["can_start"] is True

    async def test_get_intelligent_workspaces_other_host(self):
        svc, meeting = self._svc_with_meeting()
        assert await svc.get_intelligent_workspaces("nobody") == []

    async def test_get_intelligent_channels(self):
        svc, meeting = self._svc_with_meeting()
        channels = await svc.get_intelligent_channels("m1", "host1")
        assert len(channels) == 1
        assert channels[0]["meeting_type"] == "instant"
        assert channels[0]["participants"] == ["host1", "user2"]

    async def test_get_intelligent_channels_missing(self):
        svc, meeting = self._svc_with_meeting()
        assert await svc.get_intelligent_channels("nope", "host1") == []

    async def test_send_intelligent_message_success(self, monkeypatch):
        svc, meeting = self._svc_with_meeting()
        svc.zoom_config["enable_enterprise_features"] = True
        svc._send_chat_message = AsyncMock(return_value={"success": True, "message_id": "mid"})
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        result = await svc.send_intelligent_message("m1", "hello")
        assert result["success"] is True
        svc.enterprise_security.audit_event.assert_awaited_once()

    async def test_send_intelligent_message_no_meeting(self):
        svc = zoom_mod.AtomZoomIntegration({})
        result = await svc.send_intelligent_message("m1", "hello")
        assert result["success"] is False
        assert result["error"] == "Meeting not found"

    async def test_send_intelligent_message_exception(self):
        svc = zoom_mod.AtomZoomIntegration({})
        svc.active_meetings["m1"] = MagicMock()
        svc._send_chat_message = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.send_intelligent_message("m1", "hello")
        assert result["success"] is False
        assert "boom" not in result.get("error", "")

    async def test_perform_intelligent_search(self):
        svc, meeting = self._svc_with_meeting()
        svc.ai_service = None
        results = await svc.perform_intelligent_search("sales", "host1")
        assert len(results) == 1
        assert results[0]["title"] == "Sales Sync"

    async def test_perform_intelligent_search_workspace_filter(self):
        svc, meeting = self._svc_with_meeting()
        results = await svc.perform_intelligent_search("sales", "host1", workspace_id="other")
        assert results == []

    async def test_perform_intelligent_search_no_agenda(self):
        svc = zoom_mod.AtomZoomIntegration({})
        meeting = zoom_mod.ZoomMeeting(
            meeting_id="m2", topic="Standup", meeting_type=zoom_mod.ZoomMeetingType.INSTANT,
            host_id="h", start_time=datetime.now(timezone.utc), duration=10,
            timezone="UTC", agenda=None, participants=[], is_recorded=False,
            password=None, waiting_room=False, security_level="standard",
            created_at=datetime.now(timezone.utc), status="ended", metadata={},
        )
        svc.active_meetings["m2"] = meeting
        results = await svc.perform_intelligent_search("standup", "h")
        assert results[0]["snippet"] == "No agenda"

    async def test_perform_intelligent_search_ai_extends(self, monkeypatch):
        svc, meeting = self._svc_with_meeting()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = {"results": [{"id": "ai1"}]}
        svc.ai_service = MagicMock()
        svc.ai_service.process_ai_request = AsyncMock(return_value=resp)
        monkeypatch.setattr(zoom_mod, "AIRequest", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AITaskType", type("T", (), {"SEARCH_QUERY": "s"}), raising=False)
        monkeypatch.setattr(zoom_mod, "AIModelType", type("M", (), {"GPT_4": "g"}), raising=False)
        monkeypatch.setattr(zoom_mod, "AIServiceType", type("S", (), {"OPENAI": "o"}), raising=False)
        results = await svc.perform_intelligent_search("sales", "host1")
        assert any(r.get("id") == "ai1" for r in results)

    async def test_get_user_conversation_history(self):
        svc = zoom_mod.AtomZoomIntegration({})
        event = zoom_mod.ZoomEvent(
            event_id="e1", event_type=zoom_mod.ZoomEventType.MEETING_STARTED,
            meeting_id="m1", user_id="host1", timestamp=datetime.now(timezone.utc),
            data={"x": 1}, security_flags={}, compliance_flags={}, metadata={"k": "v"},
        )
        svc.meeting_history["m1"] = [event]
        history = await svc.get_user_conversation_history("host1", "m1", limit=10)
        assert len(history) == 1
        assert history[0]["metadata"] == {"k": "v"}

    async def test_get_user_conversation_history_limit(self):
        svc = zoom_mod.AtomZoomIntegration({})
        events = [
            zoom_mod.ZoomEvent(
                event_id=f"e{i}", event_type=zoom_mod.ZoomEventType.MEETING_STARTED,
                meeting_id="m1", user_id="u", timestamp=datetime.now(timezone.utc),
                data={}, security_flags={}, compliance_flags={}, metadata={},
            ) for i in range(5)
        ]
        svc.meeting_history["m1"] = events
        assert len(await svc.get_user_conversation_history("u", "m1", limit=2)) == 2

    async def test_get_service_status(self):
        svc = zoom_mod.AtomZoomIntegration({})
        svc.is_initialized = True
        svc._start_time = time.time() - 5
        svc.analytics_metrics["total_meetings"] = 5
        status = await svc.get_service_status()
        assert status["status"] == "active"
        assert status["total_meetings"] == 5
        assert status["uptime"] >= 0


class TestZoomPrivateHelpers:
    async def _svc(self):
        svc = zoom_mod.AtomZoomIntegration({"api_key": "k", "api_secret": "s"})
        svc.http_session = MagicMock()
        return svc

    async def test_test_api_connection_ok(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.get = AsyncMock(return_value=_resp(200))
        await svc._test_api_connection()
        svc.http_session.get.assert_awaited_once()

    async def test_test_api_connection_non_200(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.get = AsyncMock(return_value=_resp(500))
        await svc._test_api_connection()

    async def test_test_api_connection_no_token(self):
        svc = await self._svc()
        svc.oauth_token = None
        await svc._test_api_connection()
        svc.http_session.get.assert_not_called()

    async def test_test_api_connection_exception(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.get = AsyncMock(side_effect=RuntimeError("boom"))
        await svc._test_api_connection()

    async def test_get_oauth_token_cached(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.oauth_token_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
        await svc._get_oauth_token()
        assert svc.oauth_token == "tok"

    async def test_get_oauth_token_expired(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.oauth_token_expires = datetime.now(timezone.utc) - timedelta(minutes=5)
        await svc._get_oauth_token()

    async def test_setup_webhook_ok(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.zoom_config["webhook_url"] = "http://h"
        svc.http_session.post = AsyncMock(return_value=_resp(201))
        await svc._setup_webhook()
        svc.http_session.post.assert_awaited_once()

    async def test_setup_webhook_failure(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.post = AsyncMock(return_value=_resp(400))
        await svc._setup_webhook()

    async def test_setup_webhook_exception(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.post = AsyncMock(side_effect=RuntimeError("boom"))
        await svc._setup_webhook()

    async def test_setup_webhook_handlers(self):
        svc = await self._svc()
        await svc._setup_webhook_handlers()
        assert set(svc.webhook_handlers) == {
            zoom_mod.ZoomEventType.MEETING_STARTED,
            zoom_mod.ZoomEventType.MEETING_ENDED,
            zoom_mod.ZoomEventType.MEETING_PARTICIPANT_JOINED,
            zoom_mod.ZoomEventType.MEETING_PARTICIPANT_LEFT,
            zoom_mod.ZoomEventType.RECORDING_COMPLETED,
        }

    async def test_setup_enterprise_features_unavailable(self):
        svc = await self._svc()
        svc.enterprise_security = None
        svc.enterprise_automation = None
        await svc._setup_enterprise_features()
        assert svc.security_policies == {}

    async def test_setup_enterprise_features_ok(self):
        svc = await self._svc()
        svc.enterprise_security = MagicMock()
        svc.enterprise_automation = MagicMock()
        await svc._setup_enterprise_features()
        assert svc.security_policies
        assert svc.compliance_rules
        assert svc.automation_triggers

    async def test_setup_security_policies(self):
        svc = await self._svc()
        await svc._setup_security_policies()
        assert "meeting_access_control" in svc.security_policies

    async def test_setup_compliance_rules(self):
        svc = await self._svc()
        await svc._setup_compliance_rules()
        assert "recording_compliance" in svc.compliance_rules

    async def test_setup_automation_triggers(self):
        svc = await self._svc()
        await svc._setup_automation_triggers()
        assert "meeting_started" in svc.automation_triggers

    async def test_setup_automation_no_service(self):
        svc = await self._svc()
        svc.enterprise_automation = None
        await svc._setup_automation()

    async def test_setup_automation_ok(self):
        svc = await self._svc()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": True})
        await svc._setup_automation()

    async def test_setup_automation_failure(self):
        svc = await self._svc()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(
            return_value={"ok": False, "error": "nope"})
        await svc._setup_automation()

    async def test_setup_automation_exception(self):
        svc = await self._svc()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(
            side_effect=RuntimeError("boom"))
        await svc._setup_automation()

    async def test_setup_security_and_compliance_enabled(self):
        svc = await self._svc()
        svc.zoom_config["enable_enterprise_features"] = True
        await svc._setup_security_and_compliance()
        assert svc.security_monitoring
        assert svc.compliance_monitoring

    async def test_setup_security_and_compliance_disabled(self):
        svc = await self._svc()
        svc.zoom_config["enable_enterprise_features"] = False
        await svc._setup_security_and_compliance()
        assert not hasattr(svc, "security_monitoring")

    async def test_setup_monitoring(self):
        svc = await self._svc()
        await svc._setup_monitoring()
        assert svc.performance_metrics["meeting_start_time"] == 0.0
        assert hasattr(svc, "_start_time")

    async def test_load_existing_data(self):
        svc = await self._svc()
        await svc._load_existing_data()

    async def test_send_chat_message_ok(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.post = AsyncMock(return_value=_resp(201, {"message_id": "mid"}))
        result = await svc._send_chat_message("m1", "hi")
        assert result["success"] is True
        assert result["message_id"] == "mid"

    async def test_send_chat_message_error(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.post = AsyncMock(return_value=_resp(400, {"message": "bad"}))
        result = await svc._send_chat_message("m1", "hi")
        assert result["success"] is False

    async def test_send_chat_message_exception(self):
        svc = await self._svc()
        svc.oauth_token = "tok"
        svc.http_session.post = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc._send_chat_message("m1", "hi")
        assert result["success"] is False
        assert "boom" not in result.get("error", "")

    def test_calculate_relevance_score(self):
        svc = zoom_mod.AtomZoomIntegration({})
        assert svc._calculate_relevance_score("sales sync", "Sales Sync meeting") == 1.0
        assert svc._calculate_relevance_score("", "anything") == 0.0
        assert svc._calculate_relevance_score("xyz", "abc") == 0.0

    async def test_perform_ai_search_no_service(self):
        svc = await self._svc()
        svc.ai_service = None
        assert await svc._perform_ai_search("q") == []

    async def test_perform_ai_search_no_output(self, monkeypatch):
        svc = await self._svc()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = None
        svc.ai_service = MagicMock()
        svc.ai_service.process_ai_request = AsyncMock(return_value=resp)
        monkeypatch.setattr(zoom_mod, "AIRequest", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AITaskType", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AIModelType", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AIServiceType", MagicMock, raising=False)
        assert await svc._perform_ai_search("q") == []

    async def test_perform_ai_search_exception(self, monkeypatch):
        svc = await self._svc()
        svc.ai_service = MagicMock()
        svc.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(zoom_mod, "AIRequest", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AITaskType", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AIModelType", MagicMock, raising=False)
        monkeypatch.setattr(zoom_mod, "AIServiceType", MagicMock, raising=False)
        assert await svc._perform_ai_search("q") == []

    async def test_log_message_event_with_security(self):
        svc = await self._svc()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        await svc._log_message_event("chat_message_sent", "m1", {"user_id": "u1"})
        svc.enterprise_security.audit_event.assert_awaited_once()

    async def test_log_message_event_without_security(self):
        svc = await self._svc()
        svc.enterprise_security = None
        await svc._log_message_event("t", "m1", {})

    async def test_log_message_event_exception(self):
        svc = await self._svc()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError("boom"))
        await svc._log_message_event("t", "m1", {})

    async def test_close(self):
        svc = await self._svc()
        svc.http_session.aclose = AsyncMock()
        await svc.close()
        svc.http_session.aclose.assert_awaited_once()


class TestZoomWebhookHandlers:
    @staticmethod
    def _event(event_type, **object_kw):
        obj = {
            "id": "m1", "topic": "Sync", "host_id": "host1",
            "participant": {"id": "p1", "user_name": "Pat"},
            "recording_files": [{"recording_length": 3600}],
            "recording_length": 3600,
        }
        obj.update(object_kw)
        return {"payload": {"object": obj}}

    def _svc(self, monkeypatch):
        svc = zoom_mod.AtomZoomIntegration({"api_key": "k", "api_secret": "s"})
        svc.http_session = MagicMock()
        monkeypatch.setattr(zoom_mod, "atom_ingestion_pipeline", MagicMock())
        return svc

    async def test_meeting_started(self, monkeypatch):
        svc = self._svc(monkeypatch)
        svc.zoom_config["enable_enterprise_features"] = False
        await svc._handle_meeting_started(self._event("meeting.started"))
        assert svc.analytics_metrics["total_meetings"] == 1
        assert svc.analytics_metrics["meetings_today"] == 1
        assert svc.analytics_metrics["active_meetings"] == 1
        meeting = svc.active_meetings["m1"]
        assert meeting.status == "started"
        assert meeting.participants == ["host1"]
        zoom_mod.atom_ingestion_pipeline.ingest_record.assert_called_once()

    async def test_meeting_started_ingestion_failure(self, monkeypatch):
        svc = self._svc(monkeypatch)
        zoom_mod.atom_ingestion_pipeline.ingest_record.side_effect = RuntimeError("boom")
        await svc._handle_meeting_started(self._event("meeting.started"))
        assert svc.analytics_metrics["total_meetings"] == 1

    async def test_meeting_started_triggers_automation(self, monkeypatch):
        svc = self._svc(monkeypatch)
        svc.zoom_config["enable_enterprise_features"] = True
        svc.enterprise_automation = MagicMock()
        svc.automation_triggers = {
            "meeting_started": {"enabled": True},
            "meeting_ended": {"enabled": True},
        }
        await svc._handle_meeting_started(self._event("meeting.started"))
        assert svc.analytics_metrics["automations_triggered"] == 1

    async def test_meeting_ended(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_meeting_started(self._event("meeting.started"))
        await svc._handle_meeting_ended(self._event("meeting.ended"))
        assert svc.active_meetings["m1"].status == "ended"
        assert svc.active_meetings["m1"].duration >= 0
        assert svc.analytics_metrics["active_meetings"] == 0

    async def test_meeting_ended_unknown_meeting(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_meeting_ended(self._event("meeting.ended"))
        assert svc.analytics_metrics["active_meetings"] == 0

    async def test_participant_joined(self, monkeypatch):
        svc = self._svc(monkeypatch)
        svc.zoom_config["enable_enterprise_features"] = False
        await svc._handle_meeting_started(self._event("meeting.started"))
        await svc._handle_participant_joined(self._event("meeting.participant_joined"))
        assert "p1" in svc.active_meetings["m1"].participants
        assert svc.analytics_metrics["total_participants"] == 1

    async def test_participant_joined_dedup(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_meeting_started(self._event("meeting.started"))
        await svc._handle_participant_joined(self._event("meeting.participant_joined"))
        await svc._handle_participant_joined(self._event("meeting.participant_joined"))
        assert svc.active_meetings["m1"].participants.count("p1") == 1
        assert svc.analytics_metrics["total_participants"] == 2

    async def test_participant_joined_unknown_meeting(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_participant_joined(self._event("meeting.participant_joined"))
        assert svc.analytics_metrics["total_participants"] == 1

    async def test_participant_left(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_meeting_started(self._event("meeting.started"))
        await svc._handle_participant_joined(self._event("meeting.participant_joined"))
        await svc._handle_participant_left(self._event("meeting.participant_left"))
        assert "p1" not in svc.active_meetings["m1"].participants

    async def test_participant_left_absent(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_meeting_started(self._event("meeting.started"))
        await svc._handle_participant_left(self._event("meeting.participant_left"))
        assert svc.active_meetings["m1"].participants == ["host1"]

    async def test_recording_completed(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_meeting_started(self._event("meeting.started"))
        svc.zoom_config["enable_enterprise_features"] = False
        await svc._handle_recording_completed(self._event("recording.completed"))
        assert svc.analytics_metrics["total_recording_hours"] == 1.0
        assert svc.active_meetings["m1"].is_recorded is True
        assert svc.active_meetings["m1"].metadata["recording_files"]

    async def test_recording_completed_unknown_meeting(self, monkeypatch):
        svc = self._svc(monkeypatch)
        await svc._handle_recording_completed(self._event("recording.completed"))
        assert svc.analytics_metrics["total_recording_hours"] == 1.0

    async def test_trigger_automations_no_service(self, monkeypatch):
        svc = self._svc(monkeypatch)
        svc.enterprise_automation = None
        meeting = MagicMock()
        await svc._trigger_automations("meeting_started", meeting, {})
        assert svc.analytics_metrics["automations_triggered"] == 0

    async def test_trigger_automations_no_match(self, monkeypatch):
        svc = self._svc(monkeypatch)
        svc.enterprise_automation = MagicMock()
        svc.automation_triggers = {"meeting_started": {"enabled": True}}
        meeting = MagicMock()
        await svc._trigger_automations("meeting_ended", meeting, {})
        assert svc.analytics_metrics["automations_triggered"] == 0

    async def test_trigger_automations_disabled(self, monkeypatch):
        svc = self._svc(monkeypatch)
        svc.enterprise_automation = MagicMock()
        svc.automation_triggers = {"meeting_started": {"enabled": False}}
        meeting = MagicMock()
        await svc._trigger_automations("meeting_started", meeting, {})
        assert svc.analytics_metrics["automations_triggered"] == 0


# ===========================================================================
# bytewax_service
# ===========================================================================


class TestBytewaxDocumentParsing:
    def test_workspace_id_default_env(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_WORKSPACE_ID", "ws_env")
        op = bw_mod.DocumentParsingOperator()
        assert op.workspace_id == "ws_env"

    def test_get_service_unavailable(self, monkeypatch):
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", False)
        op = bw_mod.DocumentParsingOperator("ws1")
        assert op._get_service() is None

    async def test_parse_document_no_service(self, monkeypatch):
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", False)
        op = bw_mod.DocumentParsingOperator("ws1")
        assert await op.parse_document("/tmp/f.docx", "docx") == []

    async def test_parse_document_packets(self, monkeypatch):
        service = MagicMock()
        service.ingest_document = AsyncMock(return_value={"snippets_extracted": 2})
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", True)
        monkeypatch.setattr(bw_mod, "DocumentLogicService", lambda: service)
        op = bw_mod.DocumentParsingOperator("ws1")
        packets = await op.parse_document("/tmp/f.docx", "docx")
        assert len(packets) == 2
        assert packets[0]["operation"] == "CREATE"
        service.ingest_document.assert_awaited_once()

    async def test_parse_document_exception(self, monkeypatch):
        service = MagicMock()
        service.ingest_document = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", True)
        monkeypatch.setattr(bw_mod, "DocumentLogicService", lambda: service)
        op = bw_mod.DocumentParsingOperator("ws1")
        assert await op.parse_document("/tmp/f.docx", "docx") == []

    def test_extract_text_sync(self, monkeypatch):
        service = MagicMock()
        service._extract_text = MagicMock(return_value="text")
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", True)
        monkeypatch.setattr(bw_mod, "DocumentLogicService", lambda: service)
        op = bw_mod.DocumentParsingOperator("ws1")
        assert op.extract_text_sync("/tmp/f.docx", "docx") == "text"

    def test_extract_text_sync_no_service(self, monkeypatch):
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", False)
        op = bw_mod.DocumentParsingOperator("ws1")
        assert op.extract_text_sync("/tmp/f.docx", "docx") is None

    def test_extract_text_sync_exception(self, monkeypatch):
        service = MagicMock()
        service._extract_text = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(bw_mod, "DOCUMENT_SERVICE_AVAILABLE", True)
        monkeypatch.setattr(bw_mod, "DocumentLogicService", lambda: service)
        op = bw_mod.DocumentParsingOperator("ws1")
        assert op.extract_text_sync("/tmp/f.docx", "docx") is None


class TestBytewaxSecretsRedaction:
    @staticmethod
    def _record(content="hello world", metadata=None):
        return AtomRecordData(
            id="r1", app_type="slack", record_type="document",
            content=content, metadata=metadata or {},
        )

    def _fake_redactor(self, has_secrets=True):
        result = MagicMock()
        result.has_secrets = has_secrets
        result.redacted_text = "REDACTED"
        result.redactions = [{"type": "api_key"}]
        redactor = MagicMock()
        redactor.redact = MagicMock(return_value=result)
        return redactor

    def test_redact_with_secrets(self, monkeypatch):
        redactor = self._fake_redactor(True)
        monkeypatch.setattr(
            "core.secrets_redactor.get_secrets_redactor", lambda: redactor)
        op = bw_mod.SecretsRedactionOperator()
        record = op.redact(self._record("my api key = sk-123"))
        assert record.content == "REDACTED"
        assert record.metadata["_redacted_types"] == ["api_key"]
        assert record.metadata["_redaction_count"] == 1

    def test_redact_no_secrets(self, monkeypatch):
        redactor = self._fake_redactor(False)
        monkeypatch.setattr(
            "core.secrets_redactor.get_secrets_redactor", lambda: redactor)
        op = bw_mod.SecretsRedactionOperator()
        record = op.redact(self._record("plain text"))
        assert record.content == "plain text"
        assert "_redacted_types" not in record.metadata

    def test_redact_no_content(self, monkeypatch):
        redactor = self._fake_redactor(True)
        monkeypatch.setattr(
            "core.secrets_redactor.get_secrets_redactor", lambda: redactor)
        op = bw_mod.SecretsRedactionOperator()
        record = op.redact(self._record(content=None, metadata=None))
        assert record is not None

    def test_redact_import_error(self, monkeypatch):
        op = bw_mod.SecretsRedactionOperator()
        with patch.dict(sys.modules, {"core.secrets_redactor": None}):
            assert op._get_redactor() is None
        record = op.redact(self._record("some content"))
        assert record.content == "some content"

    def test_redact_exception(self, monkeypatch):
        redactor = MagicMock()
        redactor.redact = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(
            "core.secrets_redactor.get_secrets_redactor", lambda: redactor)
        op = bw_mod.SecretsRedactionOperator()
        record = op.redact(self._record("content"))
        assert record.content == "content"


class TestBytewaxKnowledgeExtraction:
    @staticmethod
    def _record(content="A sufficiently long document body to pass the length guard.",
                 metadata=None, operation="CREATE"):
        record = AtomRecordData(
            id="r1", app_type="google_doc", record_type="document",
            content=content, metadata=metadata or {},
        )
        record.operation = operation
        return record

    def test_extraction_disabled(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = False
        record = op.extract_knowledge(self._record())
        assert "_knowledge_extracted" not in record.metadata

    def test_extraction_short_content(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        record = op.extract_knowledge(self._record(content="short"))
        assert "_knowledge_extracted" not in record.metadata

    def test_extraction_delete_operation(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        record = op.extract_knowledge(self._record(operation="DELETE"))
        assert "_knowledge_extracted" not in record.metadata

    def test_extraction_metadata_string_json(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = True
        record = self._record(metadata={"workspace_id": "ws9", "user_id": "u1"})
        record.metadata = json.dumps(record.metadata)
        op.knowledge_manager = MagicMock()
        op.knowledge_manager.process_document = MagicMock()
        result = op.extract_knowledge(record)
        assert op.knowledge_manager.process_document.call_count == 1

    def test_extraction_metadata_bad_json(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = True
        record = self._record(metadata="not-json{")
        op.knowledge_manager = MagicMock()
        op.knowledge_manager.process_document = MagicMock()
        result = op.extract_knowledge(record)
        assert result is record

    def test_extraction_running_loop_schedules_task(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = True
        op.knowledge_manager = MagicMock()
        op.knowledge_manager.process_document = MagicMock(return_value=MagicMock())
        record = op.extract_knowledge(self._record())
        assert record.metadata["_knowledge_extracted"] is True
        assert op.knowledge_manager.process_document.call_count == 1

    def test_extraction_knowledge_manager_exception(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = True
        op.knowledge_manager = MagicMock()
        op.knowledge_manager.process_document = MagicMock(side_effect=RuntimeError("boom"))
        record = op.extract_knowledge(self._record())
        assert record.metadata["_knowledge_extracted"] is True

    def test_extraction_graphrag_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_ingestion.get_knowledge_ingestion",
            MagicMock(side_effect=ImportError("no knowledge ingestion")))
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = True
        op.knowledge_manager = None
        op.graphrag_engine = MagicMock()
        op.graphrag_engine.ingest_document = MagicMock(return_value={"edges": 2})
        record = op.extract_knowledge(self._record())
        assert record.metadata["_knowledge_extracted"] is True
        op.graphrag_engine.ingest_document.assert_called_once()

    def test_extraction_graphrag_failure(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_ingestion.get_knowledge_ingestion",
            MagicMock(side_effect=ImportError("no knowledge ingestion")))
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        op.automation_settings = MagicMock()
        op.automation_settings.is_extraction_enabled.return_value = True
        op.knowledge_manager = None
        op.graphrag_engine = MagicMock()
        op.graphrag_engine.ingest_document = MagicMock(side_effect=RuntimeError("boom"))
        record = op.extract_knowledge(self._record())
        assert record.metadata["_knowledge_extracted"] is True

    def test_is_extraction_enabled_default(self):
        op = bw_mod.KnowledgeExtractionOperator("ws1")
        assert op._is_extraction_enabled() is True


class TestBytewaxFormulaExtraction:
    @staticmethod
    def _record(record_type="document", metadata=None):
        return AtomRecordData(
            id="r1", app_type="google_doc", record_type=record_type,
            content="=SUM(A1:A3)", metadata=metadata or {},
        )

    def test_skip_non_document(self):
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record(record_type="communication"))
        assert "_formulas_extracted" not in record.metadata

    def test_skip_no_file_path(self):
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record())
        assert "_formulas_extracted" not in record.metadata

    def test_skip_unsupported_format(self):
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record(metadata={"file_path": "/tmp/f.txt"}))
        assert "_formulas_extracted" not in record.metadata

    def test_metadata_string_invalid(self):
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = self._record(metadata="junk{")
        record.metadata = "junk{"
        result = op.extract(record)
        assert result is record

    def test_extract_formulas(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract_from_file = MagicMock(return_value=[
            {"type": "sum"}, {"type": "sum"}, {"type": "if"},
        ])
        monkeypatch.setattr(
            "core.formula_extractor.FormulaExtractor", lambda **kw: extractor)
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record(metadata={"file_path": "/tmp/f.xlsx", "user_id": "u"}))
        assert record.metadata["_formulas_extracted"] == 3
        assert set(record.metadata["_formula_types"]) == {"sum", "if"}

    def test_extract_no_extractor(self):
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record(metadata={"file_path": "/tmp/f.xlsx"}))
        assert "_formulas_extracted" not in record.metadata

    def test_extract_exception(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract_from_file = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(
            "core.formula_extractor.FormulaExtractor", lambda **kw: extractor)
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record(metadata={"path": "/tmp/f.csv"}))
        assert "_formulas_extracted" not in record.metadata

    def test_extract_formulas_path_key(self, monkeypatch):
        extractor = MagicMock()
        extractor.extract_from_file = MagicMock(return_value=[])
        monkeypatch.setattr(
            "core.formula_extractor.FormulaExtractor", lambda **kw: extractor)
        op = bw_mod.FormulaExtractionOperator("ws1")
        record = op.extract(self._record(metadata={"path": "/tmp/f.ods"}))
        assert record is not None


class TestBytewaxNormalization:
    def _op(self):
        return bw_mod.UnifiedNormalizationOperator()

    def test_tuple_input(self):
        record = self._op().normalize(("src1", {
            "app_type": "hubspot", "record_type": "contact", "id": "c1",
            "properties": {"firstname": "A", "lastname": "B", "email": "a@b.c"},
        }))
        assert record.id == "c1"
        assert record.content == "Contact: A B (a@b.c)"

    def test_hubspot_campaign(self):
        record = self._op().normalize({
            "app_type": "hubspot", "record_type": "campaign",
            "name": "Camp", "description": "Desc",
        })
        assert record.content == "Campaign: Camp - Desc"

    def test_salesforce_lead(self):
        record = self._op().normalize({
            "app_type": "salesforce", "record_type": "lead",
            "FirstName": "J", "LastName": "Doe", "Company": "Acme",
        })
        assert record.content == "Lead: J Doe at Acme"

    def test_salesforce_deal(self):
        record = self._op().normalize({
            "app_type": "salesforce", "record_type": "deal",
            "Name": "Deal1", "StageName": "Prospecting",
        })
        assert record.content == "Opportunity: Deal1 (Stage: Prospecting)"

    def test_whatsapp_communication(self):
        record = self._op().normalize({
            "app_type": "whatsapp", "record_type": "communication", "text": "hi",
        })
        assert record.content == "Message (whatsapp): hi"

    def test_meta_ad_performance(self):
        record = self._op().normalize({
            "app_type": "meta_business", "record_type": "ad_performance",
            "spend": 10, "conversions": 2,
        })
        assert record.content == "Meta Ad Performance: 10 spend, 2 conv"

    def test_shopify_order(self):
        record = self._op().normalize({
            "app_type": "shopify", "record_type": "order",
            "id": "o1", "total_price": "$5", "email": "x@y.z",
        })
        assert "Order o1" in record.content

    def test_etsy_inventory(self):
        record = self._op().normalize({
            "app_type": "etsy", "record_type": "inventory",
            "sku": "s1", "quantity": 4,
        })
        assert record.content == "Inventory Update: s1 -> 4"

    def test_document_record(self):
        record = self._op().normalize({
            "app_type": "google_doc", "record_type": "document",
            "logic_snippet": "=SUM()", "file_path": "/tmp/f",
        })
        assert record.content == "Business Logic Snippet: =SUM()"
        assert record.metadata["file_path"] == "/tmp/f"

    def test_fallback_content(self):
        data = {"app_type": "slack", "record_type": "generic", "raw": "data"}
        record = self._op().normalize(data)
        assert record.content == str(data)

    def test_generated_id(self):
        record = self._op().normalize({
            "app_type": "slack", "record_type": "generic",
        })
        assert record.id.startswith("slack_generic_")

    def test_non_dict_data(self):
        assert self._op().normalize("not-a-dict") is None
        assert self._op().normalize(("k", ["not-a-dict"])) is None

    def test_invalid_record_type(self):
        assert self._op().normalize({
            "app_type": "slack", "record_type": "bogus_type",
        }) is None

    def test_operation_default(self):
        record = self._op().normalize({"app_type": "slack", "record_type": "generic"})
        assert record.operation == "CREATE"

    def test_explicit_operation(self):
        record = self._op().normalize({
            "app_type": "slack", "record_type": "generic", "operation": "UPDATE",
        })
        assert record.operation == "UPDATE"


class TestBytewaxFastEmbed:
    @staticmethod
    def _record(content="some text"):
        return AtomRecordData(
            id="r1", app_type="doc", record_type="document",
            content=content, metadata={},
        )

    def test_compute_embedding(self, monkeypatch):
        import numpy as np
        model = MagicMock()
        model.embed = MagicMock(return_value=iter([np.array([0.1, 0.2])]))
        monkeypatch.setattr(bw_mod, "TextEmbedding", lambda **kw: model)
        op = bw_mod.FastEmbedOperator()
        record = op.compute_embedding(self._record())
        assert record.vector_embedding == [0.1, 0.2]

    def test_compute_embedding_no_content(self, monkeypatch):
        model = MagicMock()
        monkeypatch.setattr(bw_mod, "TextEmbedding", lambda **kw: model)
        op = bw_mod.FastEmbedOperator()
        record = op.compute_embedding(self._record(content=None))
        assert record.vector_embedding is None

    def test_compute_embedding_no_model(self, monkeypatch):
        monkeypatch.setattr(bw_mod, "TextEmbedding", None)
        op = bw_mod.FastEmbedOperator()
        record = op.compute_embedding(self._record())
        assert record.vector_embedding is None

    def test_compute_embedding_exception(self, monkeypatch):
        model = MagicMock()
        model.embed = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(bw_mod, "TextEmbedding", lambda **kw: model)
        op = bw_mod.FastEmbedOperator()
        record = op.compute_embedding(self._record())
        assert record.vector_embedding is None

    def test_compute_embedding_empty(self, monkeypatch):
        model = MagicMock()
        model.embed = MagicMock(return_value=iter([]))
        monkeypatch.setattr(bw_mod, "TextEmbedding", lambda **kw: model)
        op = bw_mod.FastEmbedOperator()
        record = op.compute_embedding(self._record())
        assert record.vector_embedding is None


class TestBytewaxSink:
    @staticmethod
    def _record(op_type="CREATE", content="text", metadata=None):
        record = AtomRecordData(
            id="doc1", app_type="slack", record_type="document",
            content=content, metadata=metadata or {},
        )
        record.operation = op_type
        return record

    @staticmethod
    def _partition(monkeypatch):
        import core.lancedb_handler as lh
        handler = MagicMock()
        handler.add_document = MagicMock(return_value=True)
        table = MagicMock()
        handler.get_table = MagicMock(return_value=table)
        monkeypatch.setattr(lh, "LanceDBHandler", lambda: handler)
        import advanced_workflow_orchestrator as awo
        orchestrator = MagicMock()
        orchestrator.trigger_event = AsyncMock()
        monkeypatch.setattr(awo, "get_orchestrator", lambda: orchestrator)
        import core.ai_trigger_coordinator as atc
        monkeypatch.setattr(atc, "on_data_ingested", AsyncMock())
        return bw_mod.LanceDBStatelessSinkPartition(), handler, table

    async def test_write_create(self, monkeypatch):
        partition, handler, table = self._partition(monkeypatch)
        partition.write_batch([self._record()])
        handler.add_document.assert_called_once()
        await asyncio.sleep(0)
        from core.ai_trigger_coordinator import on_data_ingested
        assert on_data_ingested.await_count >= 1

    async def test_write_create_with_hooks(self, monkeypatch):
        partition, handler, table = self._partition(monkeypatch)
        partition.write_batch([self._record(metadata={"user_id": "u1", "channel": "c"})])
        await asyncio.sleep(0)
        import advanced_workflow_orchestrator as awo
        awo.get_orchestrator().trigger_event.assert_awaited_once()

    async def test_write_create_metadata_string(self, monkeypatch):
        partition, handler, table = self._partition(monkeypatch)
        record = self._record(metadata={"user_id": "u1"})
        record.metadata = json.dumps(record.metadata)
        partition.write_batch([record])
        await asyncio.sleep(0)
        handler.add_document.assert_called_once()

    async def test_write_create_failure_skips_hooks(self, monkeypatch):
        import core.lancedb_handler as lh
        handler = MagicMock()
        handler.add_document = MagicMock(return_value=False)
        monkeypatch.setattr(lh, "LanceDBHandler", lambda: handler)
        partition = bw_mod.LanceDBStatelessSinkPartition()
        partition.write_batch([self._record()])
        assert handler.add_document.called

    async def test_write_update_success(self, monkeypatch):
        """BUG-1: UPDATE used phantom LanceDBHandler.update_document which
        does not exist -> AttributeError, UPDATEs never persisted."""
        partition, handler, table = self._partition(monkeypatch)
        partition.write_batch([self._record(op_type="UPDATE", content="new text")])
        handler.add_document.assert_called_once()
        kwargs = handler.add_document.call_args.kwargs
        assert kwargs["doc_id"] == "doc1"

    async def test_write_delete_success(self, monkeypatch):
        """BUG-2: DELETE used phantom LanceDBHandler.delete_document which
        does not exist -> AttributeError, DELETEs never applied."""
        partition, handler, table = self._partition(monkeypatch)
        partition.write_batch([self._record(op_type="DELETE")])
        table.delete.assert_called_once()

    def test_write_unknown_op(self, monkeypatch):
        partition, handler, table = self._partition(monkeypatch)
        partition.write_batch([self._record(op_type="EXPLODE")])

    def test_write_exception(self, monkeypatch):
        import core.lancedb_handler as lh
        handler = MagicMock()
        handler.add_document = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(lh, "LanceDBHandler", lambda: handler)
        partition = bw_mod.LanceDBStatelessSinkPartition()
        partition.write_batch([self._record()])

    def test_hooks_sync_fallback(self, monkeypatch):
        """Cover the no-running-loop fallback (sync asyncio.run paths)."""
        partition, handler, table = self._partition(monkeypatch)
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            partition._trigger_post_ingestion_hooks(self._record(), "doc1")
        import advanced_workflow_orchestrator as awo
        assert awo.get_orchestrator().trigger_event.called

    def test_hooks_sync_fallback_errors(self, monkeypatch):
        """BUG-3: advanced_workflow_orchestrator exposes get_orchestrator(),
        not a module-level `orchestrator`; the old import never resolved, so
        workflow triggers silently never fired."""
        partition, handler, table = self._partition(monkeypatch)
        import core.ai_trigger_coordinator as atc
        atc.on_data_ingested = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            partition._trigger_post_ingestion_hooks(self._record(), "doc1")

    def test_sink_build(self, monkeypatch):
        import core.lancedb_handler as lh
        monkeypatch.setattr(lh, "LanceDBHandler", lambda: MagicMock())
        sink = bw_mod.LanceDBSink()
        partition = sink.build()
        assert isinstance(partition, bw_mod.LanceDBStatelessSinkPartition)


class TestBytewaxDataflow:
    def test_create_dataflow_without_bytewax(self):
        with pytest.raises(RuntimeError):
            bw_mod.BytewaxIngestionService.create_dataflow(MagicMock())

    def test_create_dataflow_with_bytewax(self, monkeypatch):
        monkeypatch.setattr(bw_mod, "BYTEWAX_AVAILABLE", True)
        op = MagicMock()
        monkeypatch.setattr(bw_mod, "op", op)
        source = MagicMock()
        flow = bw_mod.BytewaxIngestionService.create_dataflow(source, workspace_id="ws1")
        assert flow is not None
        assert op.input.call_count == 1
        step_names = [c.args[0] for c in op.map.call_args_list] + \
            [c.args[0] for c in op.filter.call_args_list]
        assert "normalize" in step_names
        assert "redact_secrets" in step_names
        assert "vectorize" in step_names
        assert "extract_knowledge" in step_names
        assert "extract_formulas" in step_names
        op.output.assert_called_once()


class TestBytewaxQueue:
    def test_get_queue_shared(self):
        assert bw_mod.get_bytewax_queue() is bw_mod._bytewax_queue

    def test_next_batch_drains(self, monkeypatch):
        q = queue_mod.Queue()
        for i in range(3):
            q.put(i)
        monkeypatch.setattr(bw_mod, "_bytewax_queue", q)
        partition = bw_mod.BytewaxQueuePartition(max_batch_size=100)
        assert partition.next_batch() == [0, 1, 2]
        assert partition.next_batch() == []

    def test_next_batch_caps_size(self, monkeypatch):
        q = queue_mod.Queue()
        for i in range(10):
            q.put(i)
        monkeypatch.setattr(bw_mod, "_bytewax_queue", q)
        partition = bw_mod.BytewaxQueuePartition(max_batch_size=3)
        assert partition.next_batch() == [0, 1, 2]
        assert partition.next_batch() == [3, 4, 5]

    def test_queue_source_build(self):
        partition = bw_mod.BytewaxQueueSource().build()
        assert isinstance(partition, bw_mod.BytewaxQueuePartition)


# ===========================================================================
# slack_workflow_automation
# ===========================================================================


class TestSlackWorkflowRegistry:
    def _svc(self):
        return slack_mod.SlackWorkflowAutomation({})

    def test_register(self):
        svc = self._svc()
        wf = _slack_workflow()
        assert svc.register_workflow(wf) is True
        assert svc.workflows["wf1"] is wf

    def test_register_with_memory(self):
        svc = self._svc()
        svc.memory_service = MagicMock()
        assert svc.register_workflow(_slack_workflow()) is True
        svc.memory_service.store.assert_called_once()

    def test_register_exception(self):
        svc = self._svc()
        svc.memory_service = MagicMock()
        svc.memory_service.store.side_effect = RuntimeError("boom")
        assert svc.register_workflow(_slack_workflow()) is False

    def test_unregister(self):
        svc = self._svc()
        svc.register_workflow(_slack_workflow())
        assert svc.unregister_workflow("wf1") is True
        assert "wf1" not in svc.workflows

    def test_unregister_with_memory(self):
        svc = self._svc()
        svc.memory_service = MagicMock()
        svc.register_workflow(_slack_workflow())
        assert svc.unregister_workflow("wf1") is True
        svc.memory_service.delete.assert_called_once_with("slack_workflow:wf1")

    def test_unregister_missing(self):
        svc = self._svc()
        assert svc.unregister_workflow("nope") is False

    def test_unregister_exception(self):
        svc = self._svc()
        svc.memory_service = MagicMock()
        svc.memory_service.delete.side_effect = RuntimeError("boom")
        svc.register_workflow(_slack_workflow())
        assert svc.unregister_workflow("wf1") is False

    def test_get_workflow(self):
        svc = self._svc()
        wf = _slack_workflow()
        svc.register_workflow(wf)
        assert svc.get_workflow("wf1") is wf
        assert svc.get_workflow("nope") is None

    def test_list_workflows_filters(self):
        svc = self._svc()
        wf1 = _slack_workflow(id="wf1", name="A",
                              triggers=[_slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE,
                                                       workspace_id="ws1")])
        wf2 = _slack_workflow(id="wf2", name="B", active=False,
                              triggers=[_slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE,
                                                       workspace_id="ws2")])
        wf3 = _slack_workflow(id="wf3", name="C",
                              triggers=[_slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE,
                                                       workspace_id="ws1")],
                              created_at=datetime.now(timezone.utc) + timedelta(hours=1))
        svc.register_workflow(wf1)
        svc.register_workflow(wf2)
        svc.register_workflow(wf3)
        all_active = svc.list_workflows()
        assert len(all_active) == 2
        assert all_active[0].id == "wf3"
        ws1_all = svc.list_workflows(workspace_id="ws1", active_only=False)
        assert len(ws1_all) == 2
        assert len(svc.list_workflows(workspace_id="ws2")) == 0


class TestSlackWorkflowExecution:
    def _svc(self):
        svc = slack_mod.SlackWorkflowAutomation({})
        fake_client = MagicMock()
        fake_client.chat_postMessage = MagicMock(return_value={"ts": "123.45"})
        svc._get_slack_client = lambda ws: fake_client
        return svc, fake_client

    async def test_execute_not_found(self):
        svc = slack_mod.SlackWorkflowAutomation({})
        with pytest.raises(ValueError):
            await svc.execute_workflow("nope", {})

    async def test_execute_success(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"})
        svc.register_workflow(_slack_workflow(actions=[action]))
        execution = await svc.execute_workflow("wf1", {"workspace_id": "ws1"})
        assert execution.status == "completed"
        assert execution.action_results[0]["status"] == "success"
        assert svc.workflows["wf1"].execution_count == 1
        assert svc.workflows["wf1"].last_executed is not None
        client.chat_postMessage.assert_called_once_with(channel="C1", text="hi", blocks=None)

    async def test_execute_delay(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"}, delay_seconds=1)
        svc.register_workflow(_slack_workflow(actions=[action]))
        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            execution = await svc.execute_workflow("wf1", {"workspace_id": "ws1"})
        assert execution.status == "completed"
        sleep_mock.assert_awaited_once_with(1)

    async def test_execute_with_memory(self):
        svc, client = self._svc()
        svc.memory_service = MagicMock()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"})
        svc.register_workflow(_slack_workflow(actions=[action]))
        execution = await svc.execute_workflow("wf1", {"workspace_id": "ws1"})
        assert execution.status == "completed"
        assert svc.memory_service.store.called

    async def test_execute_action_failure_no_retry(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"})
        client.chat_postMessage = MagicMock(side_effect=RuntimeError("boom"))
        svc.register_workflow(_slack_workflow(actions=[action]))
        execution = await svc.execute_workflow("wf1", {"workspace_id": "ws1"})
        assert execution.status == "failed"
        assert execution.error_message is not None

    async def test_execute_retry_then_success(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"}, retry_count=1)
        client.chat_postMessage = MagicMock(
            side_effect=[RuntimeError("boom"), {"ts": "1.0"}])
        svc.register_workflow(_slack_workflow(actions=[action]))
        with patch("asyncio.sleep", new=AsyncMock()):
            execution = await svc.execute_workflow("wf1", {"workspace_id": "ws1"})
        assert execution.status == "completed"
        assert svc.workflows["wf1"].execution_count == 2
        assert action.retry_count == 0


class TestSlackActions:
    def _svc(self, client=None):
        svc = slack_mod.SlackWorkflowAutomation({})
        if client is None:
            client = MagicMock()
            client.chat_postMessage = MagicMock(return_value={"ts": "1.1"})
            client.conversations_create = MagicMock(return_value={"channel": {"id": "C2"}})
            client.conversations_invite = MagicMock(return_value={})
            client.files_upload_v2 = MagicMock(return_value={"file": {"id": "F1", "name": "n.txt"}})
            client.users_profile_set = MagicMock(return_value={})
        svc._get_slack_client = lambda ws: client
        return svc, client

    async def test_execute_unknown_action(self):
        svc, client = self._svc()
        action = _slack_action("bogus_type")
        result = await svc.execute_action(action, {})
        assert result["status"] == "failed"

    async def test_execute_action_exception(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"})
        svc._get_slack_client = lambda ws: (_ for _ in ()).throw(RuntimeError("boom"))
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "failed"

    async def test_send_message_missing_client(self):
        svc, client = self._svc()
        svc._get_slack_client = lambda ws: None
        action = _slack_action(slack_mod.WorkflowActionType.SEND_MESSAGE,
                               parameters={"channel": "C1", "message": "hi"})
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "failed"

    async def test_create_channel(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.CREATE_CHANNEL,
                               parameters={"name": "new-channel", "is_private": True})
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "success"
        assert result["channel_id"] == "C2"
        assert result["is_private"] is True

    async def test_invite_user(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.INVITE_USER,
                               parameters={"channel": "C1", "user": "U1"})
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "success"
        client.conversations_invite.assert_called_once_with(channel="C1", users="U1")

    async def test_upload_file(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.UPLOAD_FILE,
                               parameters={"channel": "C1", "file_path": "/tmp/f"})
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "success"
        assert result["file_id"] == "F1"

    async def test_update_status(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.UPDATE_STATUS,
                               parameters={"status": "busy", "emoji": ":busy:"})
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "success"
        client.users_profile_set.assert_called_once()

    async def test_create_task(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.CREATE_TASK,
                               parameters={"title": "T", "description": "D"})
        result = await svc.execute_action(action, {})
        assert result["status"] == "success"
        assert result["created"] is True

    async def test_send_email(self):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.SEND_EMAIL,
                               parameters={"to": "a@b.c", "subject": "S", "body": "B"})
        result = await svc.execute_action(action, {})
        assert result["status"] == "success"
        assert result["sent"] is True

    async def test_make_api_call_json(self, monkeypatch):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.API_CALL,
                               parameters={"url": "http://x", "method": "POST",
                                           "headers": {"a": "b"}, "data": {"k": "v"}})
        resp = MagicMock()
        resp.status_code = 200
        resp.content_type = "application/json"
        resp.json.return_value = {"ok": True}
        client_mock = MagicMock()
        client_mock.request = AsyncMock(return_value=resp)
        client_mock.__aenter__.return_value = client_mock
        client_mock.__aexit__.return_value = False
        monkeypatch.setattr(slack_mod.httpx, "AsyncClient", lambda: client_mock)
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["status"] == "success"
        assert result["status_code"] == 200

    async def test_make_api_call_text(self, monkeypatch):
        svc, client = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.API_CALL,
                               parameters={"url": "http://x", "method": "GET"})
        resp = MagicMock()
        resp.status_code = 500
        resp.content_type = "text/plain"
        resp.text = "oops"
        client_mock = MagicMock()
        client_mock.request = AsyncMock(return_value=resp)
        client_mock.__aenter__.return_value = client_mock
        client_mock.__aexit__.return_value = False
        monkeypatch.setattr(slack_mod.httpx, "AsyncClient", lambda: client_mock)
        result = await svc.execute_action(action, {"workspace_id": "ws1"})
        assert result["response"] == "oops"

    async def test_action_logged_to_communication_service(self):
        svc, client = self._svc()
        svc.communication_service = MagicMock()
        svc.communication_service.log_event = MagicMock()
        action = _slack_action(slack_mod.WorkflowActionType.CREATE_TASK, parameters={})
        result = await svc.execute_action(action, {"workflow_id": "wf1"})
        assert result["status"] == "success"
        svc.communication_service.log_event.assert_called_once()

    def test_resolve_parameter_template(self):
        svc = slack_mod.SlackWorkflowAutomation({})
        data = {"user": "u1", "items": [1, 2]}
        assert svc._resolve_parameter("Hello {user}", data) == "Hello u1"
        assert svc._resolve_parameter("Items {items}", data) == "Items [1, 2]"
        assert svc._resolve_parameter("plain", data) == "plain"
        assert svc._resolve_parameter(42, data) == 42

    def test_get_slack_client(self, monkeypatch):
        monkeypatch.setenv("SLACK_TOKEN_ws1", "xoxb-token")
        svc = slack_mod.SlackWorkflowAutomation({})
        client = svc._get_slack_client("ws1")
        assert client is not None
        assert svc._get_slack_client("ws1") is client

    def test_get_slack_client_no_token(self, monkeypatch):
        monkeypatch.delenv("SLACK_TOKEN_ws1", raising=False)
        svc = slack_mod.SlackWorkflowAutomation({})
        assert svc._get_slack_client("ws1") is None


class TestSlackEvents:
    def _svc(self):
        return slack_mod.SlackWorkflowAutomation({})

    async def test_evaluate_trigger_type_mismatch(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE)
        assert await svc._evaluate_trigger(trigger, {"type": "file_shared"}) is False

    async def test_evaluate_trigger_file_upload(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.FILE_UPLOAD)
        assert await svc._evaluate_trigger(trigger, {"type": "file_shared"}) is True
        assert await svc._evaluate_trigger(trigger, {"type": "message"}) is False

    async def test_evaluate_trigger_channel_created(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.CHANNEL_CREATED)
        assert await svc._evaluate_trigger(trigger, {"type": "channel_created"}) is True

    async def test_evaluate_trigger_user_join(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.USER_JOIN)
        assert await svc._evaluate_trigger(trigger, {"type": "team_join"}) is True

    async def test_evaluate_trigger_mention_no_text(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.MENTION)
        assert await svc._evaluate_trigger(trigger, {"type": "message"}) is False

    async def test_evaluate_trigger_workspace_mismatch(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE, workspace_id="ws1")
        assert await svc._evaluate_trigger(trigger, {"type": "message", "team_id": "ws2"}) is False

    async def test_evaluate_trigger_channel_filter(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE, channel_ids=["C1"])
        assert await svc._evaluate_trigger(trigger, {"type": "message", "channel": "C2"}) is False
        assert await svc._evaluate_trigger(trigger, {"type": "message", "channel": "C1"}) is True

    async def test_evaluate_trigger_user_filter(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE, user_ids=["U1"])
        assert await svc._evaluate_trigger(trigger, {"type": "message", "user": "U2"}) is False

    async def test_evaluate_trigger_keywords(self):
        svc = self._svc()
        trigger = _slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE, keywords=["deploy"])
        assert await svc._evaluate_trigger(trigger, {"type": "message", "text": "please deploy"}) is True
        assert await svc._evaluate_trigger(trigger, {"type": "message", "text": "hello"}) is False

    async def test_evaluate_trigger_time_range_ok(self):
        svc = self._svc()
        trigger = _slack_trigger(
            slack_mod.WorkflowTriggerType.MESSAGE,
            conditions={"time_range": {"start": 0, "end": 23}})
        assert await svc._evaluate_trigger(trigger, {"type": "message"}) is True

    async def test_evaluate_trigger_extra_condition(self):
        svc = self._svc()
        trigger = _slack_trigger(
            slack_mod.WorkflowTriggerType.MESSAGE, conditions={"channel_type": "channel"})
        assert await svc._evaluate_trigger(trigger, {"type": "message", "channel_type": "im"}) is False
        assert await svc._evaluate_trigger(trigger, {"type": "message", "channel_type": "channel"}) is True

    async def test_evaluate_trigger_exception(self):
        svc = self._svc()
        trigger = MagicMock()
        trigger.type = slack_mod.WorkflowTriggerType.MESSAGE
        trigger.workspace_id = "ws1"
        trigger.channel_ids = None
        trigger.user_ids = None
        trigger.keywords = None
        trigger.conditions = None
        assert await svc._evaluate_trigger(trigger, {"type": "message", "team_id": "ws1"}) is False

    async def test_handle_event_matching(self):
        svc = self._svc()
        action = _slack_action(slack_mod.WorkflowActionType.CREATE_TASK, parameters={})
        svc.register_workflow(_slack_workflow(
            actions=[action],
            triggers=[_slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE,
                                     workspace_id="ws1")]))
        executions = await svc.handle_slack_event({
            "type": "message", "team_id": "ws1", "channel": "C1",
            "user": "U1", "text": "hi",
        })
        assert len(executions) == 1
        assert executions[0].status == "completed"

    async def test_handle_event_no_match(self):
        svc = self._svc()
        svc.register_workflow(_slack_workflow(
            triggers=[_slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE,
                                     workspace_id="ws9")]))
        executions = await svc.handle_slack_event({
            "type": "message", "team_id": "ws1",
        })
        assert executions == []

    async def test_handle_event_indexes_message(self):
        svc = self._svc()
        svc.search_service = MagicMock()
        svc.search_service.index = AsyncMock()
        await svc.handle_slack_event({"type": "message", "text": "hello", "event_ts": "1.0"})
        svc.search_service.index.assert_awaited_once()

    async def test_handle_event_no_index_for_other_types(self):
        svc = self._svc()
        svc.search_service = MagicMock()
        svc.search_service.index = AsyncMock()
        await svc.handle_slack_event({"type": "reaction_added"})
        svc.search_service.index.assert_not_called()

    async def test_handle_event_exception(self):
        svc = self._svc()
        svc.execute_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        svc.register_workflow(_slack_workflow(
            triggers=[_slack_trigger(slack_mod.WorkflowTriggerType.MESSAGE)]))
        executions = await svc.handle_slack_event({"type": "message"})
        assert executions == []

    async def test_index_slack_content(self):
        svc = self._svc()
        svc.search_service = MagicMock()
        svc.search_service.index = AsyncMock()
        await svc._index_slack_content({"type": "message", "ts": "1.1", "text": "hi"})
        svc.search_service.index.assert_awaited_once()

    async def test_index_slack_content_no_service(self):
        svc = self._svc()
        await svc._index_slack_content({"type": "message"})

    async def test_index_slack_content_exception(self):
        svc = self._svc()
        svc.search_service = MagicMock()
        svc.search_service.index = AsyncMock(side_effect=RuntimeError("boom"))
        await svc._index_slack_content({"type": "message"})

    def test_get_execution(self):
        svc = self._svc()
        execution = slack_mod.WorkflowExecution(
            id="e1", workflow_id="wf1", trigger_data={}, status="running",
            started_at=datetime.now(timezone.utc), action_results=[])
        svc.executions["e1"] = execution
        assert svc.get_workflow_execution("e1") is execution
        assert svc.get_workflow_execution("nope") is None

    def test_list_executions(self):
        svc = self._svc()
        base = datetime.now(timezone.utc)
        for i, status in enumerate(["completed", "failed", "running"]):
            svc.executions[f"e{i}"] = slack_mod.WorkflowExecution(
                id=f"e{i}", workflow_id="wf1", trigger_data={}, status=status,
                started_at=base + timedelta(hours=i), action_results=[])
        svc.executions["other"] = slack_mod.WorkflowExecution(
            id="other", workflow_id="wf2", trigger_data={}, status="completed",
            started_at=base, action_results=[])
        listed = svc.list_workflow_executions("wf1", limit=2)
        assert len(listed) == 2
        assert listed[0].id == "e2"
        assert len(svc.list_workflow_executions()) == 4

    def test_workflow_stats_empty(self):
        svc = self._svc()
        assert svc.get_workflow_stats("nope") == {}

    def test_workflow_stats(self):
        svc = self._svc()
        svc.register_workflow(_slack_workflow())
        base = datetime.now(timezone.utc)
        svc.executions["e1"] = slack_mod.WorkflowExecution(
            id="e1", workflow_id="wf1", trigger_data={}, status="completed",
            started_at=base, completed_at=base + timedelta(seconds=10), action_results=[])
        svc.executions["e2"] = slack_mod.WorkflowExecution(
            id="e2", workflow_id="wf1", trigger_data={}, status="failed",
            started_at=base, completed_at=base + timedelta(seconds=5), action_results=[])
        stats = svc.get_workflow_stats("wf1")
        assert stats["total_executions"] == 2
        assert stats["success_rate"] == 50.0
        assert stats["average_duration"] == 10.0


# ===========================================================================
# atom_chat_interface
# ===========================================================================


class TestChatBasics:
    def _svc(self):
        return chat_mod.AtomChatInterface({})

    def test_commands_registered(self):
        svc = self._svc()
        assert set(svc.commands) == {
            "slack-connect", "slack-channels", "slack-send", "slack-search",
            "slack-workflows", "remember", "recall", "search", "help", "context",
        }

    def test_get_context_create(self):
        svc = self._svc()
        ctx = svc._get_context("c1", "u1")
        assert ctx.conversation_id == "c1"
        assert svc._get_context("c1", "u1") is ctx

    def test_user_permissions(self):
        svc = self._svc()
        assert svc._get_user_permissions("u1") == ["user"]

    def test_check_permissions(self):
        svc = self._svc()
        assert svc._check_permissions(["user"], "user") is True
        assert svc._check_permissions(["user"], "admin") is False
        assert svc._check_permissions(["admin"], "super_admin") is False
        assert svc._check_permissions(["super_admin"], "admin") is True

    def test_context_channel_workspace(self):
        svc = self._svc()
        assert svc._get_context_channel_workspace({}) is None
        assert svc._get_context_channel_workspace(None) is None
        ctx = svc._get_context("c1", "u1")
        ctx.slack_workspace_id = "ws1"
        assert svc._get_context_channel_workspace(
            {"conversation_id": "c1", "user_id": "u1"}) == "ws1"

    async def test_process_message_without_context(self):
        """BUG-4: process_message(context=None) — the default — crashed with
        AttributeError on context.get(); the default must produce a normal
        response."""
        svc = self._svc()
        response = await svc.process_message("hello there", "u1", "Bob")
        assert response
        assert "error" not in response.lower()

    async def test_process_message_regular(self):
        svc = self._svc()
        response = await svc.process_message(
            "hello there", "u1", "Bob", context={"conversation_id": "c1"})
        assert "I'm here to help" in response
        assert len(svc.contexts["c1"].messages) == 1

    async def test_process_message_command(self):
        svc = self._svc()
        response = await svc.process_message(
            "/help", "u1", "Bob", context={"conversation_id": "c1"})
        assert "Available commands" in response

    async def test_process_message_exception(self):
        svc = self._svc()
        svc._process_regular_message = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc.process_message("hello", "u1", "Bob")
        assert "error" in response.lower()
        assert "boom" not in response

    async def test_process_message_notifies_callbacks(self):
        svc = self._svc()
        seen = []

        async def cb(msg):
            seen.append(msg.message)

        svc.add_message_callback(cb)
        await svc.process_message("hi", "u1", "Bob")
        assert seen == ["hi"]

    def test_get_conversation_history(self):
        svc = self._svc()
        assert svc.get_conversation_history("c1") == []
        ctx = svc._get_context("c1", "u1")
        msg = chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="hi",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={}, source="user")
        ctx.messages.append(msg)
        assert svc.get_conversation_history("c1") == [msg]

    async def test_save_context(self):
        svc = self._svc()
        svc.memory_service = AsyncMock()
        await svc._save_context(svc._get_context("c1", "u1"))
        svc.memory_service.store.assert_awaited_once()

    async def test_save_context_exception(self):
        svc = self._svc()
        svc.memory_service = AsyncMock()
        svc.memory_service.store = AsyncMock(side_effect=RuntimeError("boom"))
        await svc._save_context(svc._get_context("c1", "u1"))

    async def test_extract_intents_entities(self):
        svc = self._svc()
        intents, entities = await svc._extract_intents_entities("please search #general")
        assert "search" in intents
        assert entities == {"channel": "general"}

    async def test_extract_remember_intent(self):
        svc = self._svc()
        intents, _ = await svc._extract_intents_entities("remember this")
        assert "remember" in intents

    async def test_generate_ai_response_slack_context(self):
        svc = self._svc()
        msg = chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="hey",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={"slack_channel_id": "C1", "conversation_id": "c1"}, source="user")
        response = await svc._generate_ai_response(msg, [], {})
        assert response.startswith(("I can help", "Need to send", "Looking for"))

    async def test_generate_ai_response_search_intent(self):
        svc = self._svc()
        msg = chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="find x",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={"conversation_id": "c1"}, source="user")
        response = await svc._generate_ai_response(msg, ["search"], {})
        assert "search" in response

    async def test_generate_ai_response_send_intent(self):
        svc = self._svc()
        msg = chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="send x",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={"conversation_id": "c1"}, source="user")
        response = await svc._generate_ai_response(msg, ["send_message"], {})
        assert "/slack-send" in response

    async def test_generate_ai_response_long_conversation(self):
        svc = self._svc()
        ctx = svc._get_context("c1", "u1")
        for i in range(6):
            ctx.messages.append(chat_mod.ChatMessage(
                id=f"m{i}", user_id="u1", user_name="Bob", message=str(i),
                timestamp=datetime.now(timezone.utc), channel="default",
                context={}, source="user"))
        msg = chat_mod.ChatMessage(
            id="m9", user_id="u1", user_name="Bob", message="hi",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={"conversation_id": "c1"}, source="user")
        response = await svc._generate_ai_response(msg, [], {})
        assert "tracking our conversation" in response

    async def test_generate_ai_response_default(self):
        svc = self._svc()
        msg = chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="hi",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={"conversation_id": "c1"}, source="user")
        response = await svc._generate_ai_response(msg, [], {})
        assert "I'm here to help" in response

    async def test_notify_callbacks_sync_and_error(self):
        svc = self._svc()
        calls = []

        def sync_cb(msg):
            calls.append(msg.message)

        async def async_cb(msg):
            calls.append(msg.message)

        async def bad_cb(msg):
            raise RuntimeError("boom")

        svc.add_message_callback(sync_cb)
        svc.add_message_callback(async_cb)
        svc.add_message_callback(bad_cb)
        msg = chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="hi",
            timestamp=datetime.now(timezone.utc), channel="default",
            context={}, source="user")
        await svc._notify_callbacks(msg)
        assert calls.count("hi") == 2

    def test_remove_message_callback(self):
        svc = self._svc()

        def cb(msg):
            pass

        svc.add_message_callback(cb)
        svc.remove_message_callback(cb)
        svc.remove_message_callback(cb)
        assert svc.message_callbacks == []


class TestChatCommands:
    def _svc(self):
        svc = chat_mod.AtomChatInterface({})
        slack = MagicMock()
        svc.slack_service = slack
        svc.memory_service = AsyncMock()
        svc.search_service = AsyncMock()
        return svc, slack

    @staticmethod
    def _msg(svc, text, conversation_id="c1"):
        return chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message=text,
            timestamp=datetime.now(timezone.utc), channel="default",
            context={"conversation_id": conversation_id}, source="user")

    async def test_help_all(self):
        svc, _ = self._svc()
        response = await svc._process_command(self._msg(svc, "/help"))
        assert "Available commands" in response

    async def test_help_specific(self):
        svc, _ = self._svc()
        response = await svc._process_command(self._msg(svc, "/help search"))
        assert "Search all indexed content" in response

    async def test_help_unknown(self):
        svc, _ = self._svc()
        response = await svc._process_command(self._msg(svc, "/help nope"))
        assert "Unknown command" in response

    async def test_unknown_command(self):
        svc, _ = self._svc()
        response = await svc._process_command(self._msg(svc, "/nope"))
        assert "Unknown command" in response

    async def test_command_requires_slack_not_connected(self):
        svc, _ = self._svc()
        response = await svc._process_command(self._msg(svc, "/slack-channels"))
        assert "requires Slack" in response

    async def test_command_syntax_error(self):
        svc, _ = self._svc()
        svc.slack_connected = True
        response = await svc._process_command(self._msg(svc, "/slack-search"))
        assert "syntax" in response

    async def test_command_exception(self):
        svc, _ = self._svc()
        svc.commands["remember"] = chat_mod.SlackCommand(
            trigger="remember", pattern=r"/remember\s+(.+)",
            handler=MagicMock(side_effect=RuntimeError("boom")),
            description="d")
        response = await svc._process_command(self._msg(svc, "/remember x"))
        assert "Error executing command" in response
        assert "boom" not in response

    async def test_slack_connect_lists_workspaces(self):
        svc, slack = self._svc()
        ws = MagicMock()
        ws.name = "Acme"
        ws.domain = "acme"
        ws.id = "ws1"
        slack.list_workspaces = AsyncMock(return_value=[ws])
        response = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "Available workspaces" in response

    async def test_slack_connect_none(self):
        svc, slack = self._svc()
        slack.list_workspaces = AsyncMock(return_value=[])
        response = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "No workspaces available" in response

    async def test_slack_connect_specific(self):
        svc, slack = self._svc()
        slack.test_connection = AsyncMock(return_value={"connected": True, "team": "Acme"})
        response = await svc._handle_slack_connect(self._msg(svc, "/slack-connect ws1"), "ws1")
        assert "Successfully connected" in response
        assert svc.slack_connected is True

    async def test_slack_connect_failed(self):
        svc, slack = self._svc()
        slack.test_connection = AsyncMock(return_value={"connected": False, "error": "denied"})
        response = await svc._handle_slack_connect(self._msg(svc, "/slack-connect ws1"), "ws1")
        assert "Failed to connect" in response

    async def test_slack_connect_no_service(self):
        svc = chat_mod.AtomChatInterface({})
        svc.slack_service = None
        response = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "not available" in response

    async def test_slack_connect_exception(self):
        svc, slack = self._svc()
        slack.list_workspaces = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "Error connecting" in response
        assert "boom" not in response

    async def test_slack_channels_list(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.list_channels = AsyncMock(return_value=[
            {"name": "general", "num_members": 3, "id": "C1"}])
        response = await svc._handle_slack_channels(self._msg(svc, "/slack-channels"))
        assert "#general" in response

    async def test_slack_channels_switch(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.list_channels = AsyncMock(return_value=[
            {"name": "general", "num_members": 3, "id": "C1"}])
        response = await svc._handle_slack_channels(self._msg(svc, "/slack-channels general"), "general")
        assert "Switched to" in response
        assert svc.contexts["c1"].slack_channel_id == "C1"

    async def test_slack_channels_not_found(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.list_channels = AsyncMock(return_value=[])
        response = await svc._handle_slack_channels(self._msg(svc, "/slack-channels nope"), "nope")
        assert "not found" in response

    async def test_slack_channels_not_connected(self):
        svc, slack = self._svc()
        response = await svc._handle_slack_channels(self._msg(svc, "/slack-channels"))
        assert "connect" in response.lower()

    async def test_slack_channels_exception(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.list_channels = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_slack_channels(self._msg(svc, "/slack-channels"))
        assert "Error listing channels" in response
        assert "boom" not in response

    async def test_slack_send_with_channel(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.list_channels = AsyncMock(return_value=[{"name": "general", "id": "C1"}])
        slack.post_message = AsyncMock(return_value={"ok": True})
        response = await svc._handle_slack_send(
            self._msg(svc, "/slack-send #general hi"), "general", "hi")
        assert "Message sent" in response

    async def test_slack_send_use_context_channel(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        svc._get_context("c1", "u1").slack_channel_id = "C1"
        slack.post_message = AsyncMock(return_value={"ok": True})
        response = await svc._handle_slack_send(self._msg(svc, "/slack-send hi"), None, "hi")
        assert "Message sent" in response

    async def test_slack_send_channel_not_found(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.list_channels = AsyncMock(return_value=[])
        response = await svc._handle_slack_send(
            self._msg(svc, "/slack-send #nope hi"), "nope", "hi")
        assert "Channel not found" in response

    async def test_slack_send_not_connected(self):
        svc, slack = self._svc()
        response = await svc._handle_slack_send(self._msg(svc, "/slack-send hi"), None, "hi")
        assert "connect" in response.lower()

    async def test_slack_send_failure(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        svc._get_context("c1", "u1").slack_channel_id = "C1"
        slack.post_message = AsyncMock(return_value={"ok": False, "error": "denied"})
        response = await svc._handle_slack_send(self._msg(svc, "/slack-send hi"), None, "hi")
        assert "Failed to send message" in response

    async def test_slack_send_exception(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        svc._get_context("c1", "u1").slack_channel_id = "C1"
        slack.post_message = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_slack_send(self._msg(svc, "/slack-send hi"), None, "hi")
        assert "Error sending message" in response
        assert "boom" not in response

    async def test_slack_search(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.search_messages = AsyncMock(return_value={
            "ok": True,
            "messages": [{"user_name": "Bob", "channel_name": "general",
                          "text": "hello world", "ts": "1.1"}],
        })
        response = await svc._handle_slack_search(self._msg(svc, "/slack-search hi"), "hi")
        assert "Found 1 results" in response

    async def test_slack_search_no_results(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.search_messages = AsyncMock(return_value={"ok": True, "messages": []})
        response = await svc._handle_slack_search(self._msg(svc, "/slack-search hi"), "hi")
        assert "No messages found" in response

    async def test_slack_search_not_connected(self):
        svc, slack = self._svc()
        response = await svc._handle_slack_search(self._msg(svc, "/slack-search hi"), "hi")
        assert "connect" in response.lower()

    async def test_slack_search_exception(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        slack.search_messages = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_slack_search(self._msg(svc, "/slack-search hi"), "hi")
        assert "Error searching Slack" in response
        assert "boom" not in response

    async def test_slack_workflows_list(self):
        """BUG-5: _handle_slack_workflows called the non-existent
        SlackWorkflowAutomation.list_workspaces() (it is list_workflows) so
        /slack-workflows list always errored."""
        svc, slack = self._svc()
        automation = MagicMock()
        wf = slack_mod.SlackWorkflow(id="wf1", name="WF", description="d",
                                     triggers=[], actions=[], created_by="u",
                                     created_at=datetime.now(timezone.utc))
        automation.list_workflows.return_value = [wf]
        monkeypatch_patch = patch.object(chat_mod, "slack_workflow_automation", automation)
        with monkeypatch_patch:
            response = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows list"), "list", "")
        assert "Available workflows" in response
        assert "WF" in response

    async def test_slack_workflows_list_empty(self):
        svc, slack = self._svc()
        automation = MagicMock()
        automation.list_workflows.return_value = []
        with patch.object(chat_mod, "slack_workflow_automation", automation):
            response = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows list"), "list", "")
        assert "No workflows configured" in response

    async def test_slack_workflows_list_no_automation(self):
        svc, slack = self._svc()
        with patch.object(chat_mod, "slack_workflow_automation", None):
            response = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows list"), "list", "")
        assert "No workflows configured" in response

    async def test_slack_workflows_run_no_params(self):
        svc, slack = self._svc()
        with patch.object(chat_mod, "slack_workflow_automation", MagicMock()):
            response = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows run"), "run", "")
        assert "Please specify a workflow" in response

    async def test_slack_workflows_run(self):
        svc, slack = self._svc()
        automation = MagicMock()
        wf = slack_mod.SlackWorkflow(id="wf1", name="WF", description="d",
                                     triggers=[], actions=[], created_by="u",
                                     created_at=datetime.now(timezone.utc))
        automation.list_workflows.return_value = [wf]
        execution = MagicMock()
        execution.id = "exec1"
        automation.execute_workflow = AsyncMock(return_value=execution)
        with patch.object(chat_mod, "slack_workflow_automation", automation):
            response = await svc._handle_slack_workflows(
                self._msg(svc, "/slack-workflows run wf1"), "run", "wf1")
        assert "Workflow 'WF' started" in response
        automation.execute_workflow.assert_awaited_once()

    async def test_slack_workflows_run_not_found(self):
        svc, slack = self._svc()
        automation = MagicMock()
        automation.list_workflows.return_value = []
        with patch.object(chat_mod, "slack_workflow_automation", automation):
            response = await svc._handle_slack_workflows(
                self._msg(svc, "/slack-workflows run nope"), "run", "nope")
        assert "not found" in response

    async def test_slack_workflows_other_action(self):
        svc, slack = self._svc()
        with patch.object(chat_mod, "slack_workflow_automation", MagicMock()):
            response = await svc._handle_slack_workflows(
                self._msg(svc, "/slack-workflows create"), "create", "")
        assert "Available workflow actions" in response

    async def test_slack_workflows_exception(self):
        svc, slack = self._svc()
        automation = MagicMock()
        automation.list_workflows.side_effect = RuntimeError("boom")
        with patch.object(chat_mod, "slack_workflow_automation", automation):
            response = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows list"), "list", "")
        assert "Error with workflows" in response
        assert "boom" not in response

    async def test_remember(self):
        svc, slack = self._svc()
        response = await svc._handle_remember(self._msg(svc, "/remember buy milk"), "buy milk")
        assert "I'll remember" in response
        svc.memory_service.store.assert_awaited_once()

    async def test_remember_no_memory(self):
        svc = chat_mod.AtomChatInterface({})
        svc.memory_service = None
        response = await svc._handle_remember(self._msg(svc, "/remember x"), "x")
        assert "not available" in response

    async def test_remember_exception(self):
        svc, slack = self._svc()
        svc.memory_service.store = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_remember(self._msg(svc, "/remember x"), "x")
        assert "Error storing information" in response
        assert "boom" not in response

    async def test_recall_with_query(self):
        svc, slack = self._svc()
        svc.memory_service.search = AsyncMock(return_value=[
            {"content": "milk", "timestamp": "t1"}])
        response = await svc._handle_recall(self._msg(svc, "/recall milk"), "milk")
        assert "Found memories" in response

    async def test_recall_no_results(self):
        svc, slack = self._svc()
        svc.memory_service.search = AsyncMock(return_value=[])
        response = await svc._handle_recall(self._msg(svc, "/recall milk"), "milk")
        assert "No memories found" in response

    async def test_recall_recent(self):
        svc, slack = self._svc()
        svc.memory_service.get_recent = AsyncMock(return_value=[
            {"content": "milk", "timestamp": "t1"}])
        response = await svc._handle_recall(self._msg(svc, "/recall"), None)
        assert "Recent memories" in response

    async def test_recall_recent_empty(self):
        svc, slack = self._svc()
        svc.memory_service.get_recent = AsyncMock(return_value=[])
        response = await svc._handle_recall(self._msg(svc, "/recall"), None)
        assert "No memories found" in response

    async def test_recall_no_memory(self):
        svc = chat_mod.AtomChatInterface({})
        svc.memory_service = None
        response = await svc._handle_recall(self._msg(svc, "/recall"), None)
        assert "not available" in response

    async def test_recall_exception(self):
        svc, slack = self._svc()
        svc.memory_service.search = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_recall(self._msg(svc, "/recall x"), "x")
        assert "Error recalling" in response
        assert "boom" not in response

    async def test_search_command(self):
        svc, slack = self._svc()
        svc.search_service.search = AsyncMock(return_value=[
            {"title": "Doc", "source": "slack", "snippet": "snip", "timestamp": "t1"}])
        response = await svc._handle_search(self._msg(svc, "/search doc"), "doc")
        assert "Found 1 results" in response

    async def test_search_command_no_results(self):
        svc, slack = self._svc()
        svc.search_service.search = AsyncMock(return_value=[])
        response = await svc._handle_search(self._msg(svc, "/search doc"), "doc")
        assert "No results found" in response

    async def test_search_command_no_service(self):
        svc = chat_mod.AtomChatInterface({})
        svc.search_service = None
        response = await svc._handle_search(self._msg(svc, "/search doc"), "doc")
        assert "not available" in response

    async def test_search_command_exception(self):
        svc, slack = self._svc()
        svc.search_service.search = AsyncMock(side_effect=RuntimeError("boom"))
        response = await svc._handle_search(self._msg(svc, "/search doc"), "doc")
        assert "Error searching" in response
        assert "boom" not in response

    async def test_context_show_no_conversation(self):
        svc, slack = self._svc()
        msg = self._msg(svc, "/context show", conversation_id=None)
        response = await svc._handle_context(msg, "show", "")
        assert "No conversation context" in response

    async def test_context_show(self):
        svc, slack = self._svc()
        response = await svc._handle_context(self._msg(svc, "/context show"), "show", "")
        assert "Conversation ID: c1" in response

    async def test_context_set(self):
        svc, slack = self._svc()
        response = await svc._handle_context(self._msg(svc, "/context set finance"), "set", "finance")
        assert "topic set to: finance" in response
        assert svc.contexts["c1"].current_topic == "finance"

    async def test_context_clear(self):
        svc, slack = self._svc()
        ctx = svc._get_context("c1", "u1")
        ctx.messages.append(chat_mod.ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message="x",
            timestamp=datetime.now(timezone.utc), channel="default", context={}, source="user"))
        response = await svc._handle_context(self._msg(svc, "/context clear"), "clear", "")
        assert "Context cleared" in response
        assert ctx.messages == []

    async def test_context_invalid_action(self):
        svc, slack = self._svc()
        response = await svc._handle_context(self._msg(svc, "/context bad"), "bad", "")
        assert "Available context actions" in response


class TestChatSync:
    def _svc(self):
        svc = chat_mod.AtomChatInterface({})
        slack = MagicMock()
        svc.slack_service = slack
        svc.search_service = AsyncMock()
        return svc, slack

    async def test_index_slack_content_not_connected(self):
        svc, slack = self._svc()
        await svc.index_slack_content()
        slack.list_channels.assert_not_called()

    async def test_index_slack_content(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        svc.slack_workspaces = [{"id": "ws1"}]
        slack.list_channels = AsyncMock(return_value=[{"id": "C1"}])
        slack.get_channel_history = AsyncMock(return_value=[{"ts": "1.1", "text": "hi", "user": "u1"}])
        await svc.index_slack_content()
        slack.get_channel_history.assert_awaited_once()
        svc.search_service.index.assert_awaited_once()

    async def test_index_slack_content_exception(self):
        svc, slack = self._svc()
        svc.slack_connected = True
        svc.slack_workspaces = [{"id": "ws1"}]
        slack.list_channels = AsyncMock(side_effect=RuntimeError("boom"))
        await svc.index_slack_content()

    async def test_sync_with_slack(self):
        svc, slack = self._svc()
        slack.list_workspaces = AsyncMock(return_value=[{"id": "ws1"}])
        slack.list_channels = AsyncMock(return_value=[])
        await svc.sync_with_slack()
        assert svc.slack_workspaces == [{"id": "ws1"}]
        assert svc.slack_connected is True

    async def test_sync_with_slack_exception(self):
        svc, slack = self._svc()
        slack.list_workspaces = AsyncMock(side_effect=RuntimeError("boom"))
        await svc.sync_with_slack()
        assert svc.slack_connected is False

    async def test_sync_with_slack_no_service(self):
        svc = chat_mod.AtomChatInterface({})
        svc.slack_service = None
        await svc.sync_with_slack()
        assert svc.slack_workspaces == []
