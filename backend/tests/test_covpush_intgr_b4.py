"""Coverage push for integrations wave B - batch 4 (video/zoom/chat/slack-engine)."""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _video_request(task_type, **kw):
    import integrations.atom_video_ai_service as v
    return v.VideoRequest(
        request_id="r1", task_type=task_type, model_type=v.VideoModelType.YOLO,
        video_path=None, video_data=b"\x00" * 10, format=v.VideoFormat.MP4,
        resolution=v.VideoResolution.FHD_1080P, duration=10.0, fps=30.0,
        platform="test", user_id="u1", metadata=kw.pop("metadata", {}), **kw,
    )


# ============================================================================
# atom_video_ai_service
# ============================================================================



def _fake_cv2_module(video_capture=None):
    """cv2 stub: the installed cv2 is incompatible with numpy 2.x in this env."""
    import types
    mod = types.ModuleType("cv2")
    mod.VideoCapture = video_capture or MagicMock(name="VideoCapture")
    mod.CAP_PROP_FRAME_COUNT = 0
    mod.CAP_PROP_POS_FRAMES = 1
    mod.CAP_PROP_FPS = 2
    mod.CAP_PROP_FRAME_WIDTH = 3
    mod.CAP_PROP_FRAME_HEIGHT = 4
    mod.COLOR_BGR2RGB = 5
    mod.cvtColor = MagicMock(return_value="rgb")
    return mod

class TestVideoAIService:
    def _svc(self):
        import integrations.atom_video_ai_service as v
        return v.AtomVideoAIService(config={"enable_enterprise_features": True})

    async def test_initialize(self):
        svc = self._svc()
        with patch.object(svc, "_load_video_models", AsyncMock()), \
             patch.object(svc, "_setup_content_moderation", AsyncMock()), \
             patch.object(svc, "_setup_enterprise_features", AsyncMock()), \
             patch.object(svc, "_setup_security_and_compliance", AsyncMock()), \
             patch.object(svc, "_load_existing_video_data", AsyncMock()):
            assert await svc.initialize() is True
            assert svc.is_initialized
        svc2 = self._svc()
        with patch.object(svc2, "_load_video_models", AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc2.initialize() is False

    async def test_process_all_tasks(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        svc._preprocess_video = AsyncMock(return_value=b"data")
        svc._perform_security_check = AsyncMock(return_value={"passed": True})
        svc._extract_frames = AsyncMock(return_value=[])
        svc._classify_video_content = AsyncMock(return_value="general")
        svc._analyze_video_quality = AsyncMock(return_value=75.0)
        svc._summarize_video = AsyncMock(return_value=MagicMock(success=True))
        svc._analyze_video_content = AsyncMock(return_value=MagicMock(success=True))
        svc._detect_objects = AsyncMock(return_value=MagicMock(success=True))
        svc._recognize_faces = AsyncMock(return_value=MagicMock(success=True))
        svc._detect_scenes = AsyncMock(return_value=MagicMock(success=True))
        svc._diarize_speakers = AsyncMock(return_value=MagicMock(success=True))
        svc._classify_video = AsyncMock(return_value=MagicMock(success=True))
        svc._moderate_content = AsyncMock(return_value=MagicMock(success=True))
        for task in v.VideoTaskType:
            resp = await svc.process_video_request(_video_request(task))
            assert resp is not None
        # security failure
        svc._perform_security_check = AsyncMock(return_value={"passed": False, "reason": "nope"})
        resp = await svc.process_video_request(_video_request(v.VideoTaskType.SUMMARIZATION))
        assert resp.success is False
        # exception
        svc._preprocess_video = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc.process_video_request(_video_request(v.VideoTaskType.SUMMARIZATION))
        assert resp.success is False

    async def test_circuit_and_rate_paths(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        with patch.object(v.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            resp = await svc.process_video_request(_video_request(v.VideoTaskType.SUMMARIZATION))
            assert resp.success is False
            await svc._load_video_models()
        with patch.object(v.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            resp = await svc.process_video_request(_video_request(v.VideoTaskType.SUMMARIZATION))
            assert resp.success is False
            await svc._load_video_models()

    async def test_summarize_video(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        svc._extract_frames = AsyncMock(return_value=[MagicMock()])
        svc.blip_processor = MagicMock()
        svc.blip_processor.return_value = MagicMock()
        svc.blip_processor.decode.return_value = "a caption"
        svc.blip_model = MagicMock()
        svc.blip_model.generate.return_value = [MagicMock()]
        import integrations.atom_video_ai_service as v
        with patch.object(v, "torch", MagicMock()):
            pass
        # no ai service -> fallback summary
        resp = await svc._summarize_video(_video_request(v.VideoTaskType.SUMMARIZATION), b"x")
        assert resp.success is True
        assert resp.text == "Unable to generate summary"
        assert "video_summaries" in svc.__dict__
        svc._extract_frames = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._summarize_video(_video_request(v.VideoTaskType.SUMMARIZATION), b"x")
        assert resp.success is False

    async def test_analyze_video_content(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        frame = MagicMock()
        obj = MagicMock()
        obj.cls = 0
        obj.conf = 0.9
        obj.xyxy[0].tolist.return_value = [1, 2, 3, 4]
        result = MagicMock()
        result.boxes = [obj]
        result.names = {0: "person"}
        svc.yolo_model = MagicMock(return_value=[result])
        svc._extract_frames = AsyncMock(return_value=[frame])
        svc._classify_video_content = AsyncMock(return_value="office_meeting")
        svc._analyze_video_quality = AsyncMock(return_value=85.0)
        resp = await svc._analyze_video_content(_video_request(v.VideoTaskType.CONTENT_ANALYSIS), b"x")
        assert resp.success is True
        assert len(resp.objects_detected) == 1
        assert "video_analyses" in svc.__dict__
        svc._extract_frames = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._analyze_video_content(_video_request(v.VideoTaskType.CONTENT_ANALYSIS), b"x")
        assert resp.success is False

    async def test_detect_objects(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        frame = MagicMock()
        obj = MagicMock()
        obj.cls = 0
        obj.conf = 0.9
        obj.xyxy[0].tolist.return_value = [1, 2, 3, 4]
        result = MagicMock()
        result.boxes = [obj]
        result.names = {0: "person"}
        svc.yolo_model = MagicMock(return_value=[result])
        svc._extract_frames = AsyncMock(return_value=[frame])
        resp = await svc._detect_objects(_video_request(v.VideoTaskType.OBJECT_DETECTION), b"x")
        assert resp.success is True
        assert resp.content_analysis["most_common"] == "person"
        svc._extract_frames = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._detect_objects(_video_request(v.VideoTaskType.OBJECT_DETECTION), b"x")
        assert resp.success is False

    async def test_classify_video_content_and_quality(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        assert await svc._classify_video_content([]) == "general"
        assert await svc._classify_video_content(MagicMock()) == "general"
        assert svc._get_quality_category(95) == "excellent"
        assert svc._get_quality_category(85) == "very_good"
        assert svc._get_quality_category(75) == "good"
        assert svc._get_quality_category(65) == "fair"
        assert svc._get_quality_category(55) == "poor"
        assert svc._get_quality_category(10) == "very_poor"
        cap = MagicMock()
        cap.get.return_value = 0
        with patch.dict(sys.modules, {"cv2": _fake_cv2_module(video_capture=MagicMock(return_value=cap))}):
            assert await svc._analyze_video_quality(b"x") == 0.0

    async def test_new_handlers(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        svc._extract_frames = AsyncMock(return_value=[MagicMock()] * 3)
        svc.face_recognition_model = MagicMock()
        svc.face_recognition_model.detect.return_value = [{"bbox": [1], "confidence": 0.9, "identity": "x"}]
        resp = await svc._recognize_faces(_video_request(v.VideoTaskType.FACE_RECOGNITION), b"x")
        assert resp.success is True
        assert len(resp.faces_detected) == 3
        svc.face_recognition_model = None
        resp = await svc._recognize_faces(_video_request(v.VideoTaskType.FACE_RECOGNITION), b"x")
        assert resp.success is True and resp.faces_detected == []
        resp = await svc._detect_scenes(_video_request(v.VideoTaskType.SCENE_DETECTION), b"x")
        assert resp.success is True and len(resp.scenes_detected) >= 1
        resp = await svc._diarize_speakers(_video_request(v.VideoTaskType.SPEAKER_DIARIZATION), b"x")
        assert resp.success is True and len(resp.speakers_detected) == 2
        resp = await svc._diarize_speakers(_video_request(v.VideoTaskType.SPEAKER_DIARIZATION), b"x", )
        svc._extract_frames = AsyncMock(return_value=[])
        resp = await svc._diarize_speakers(_video_request(v.VideoTaskType.SPEAKER_DIARIZATION), b"x")
        assert resp.success is True and resp.speakers_detected == []
        svc._extract_frames = AsyncMock(return_value=[MagicMock()] * 3)
        svc._classify_video_content = AsyncMock(return_value="general")
        resp = await svc._classify_video(_video_request(v.VideoTaskType.VIDEO_CLASSIFICATION), b"x")
        assert resp.success is True and resp.video_class == "general"
        resp = await svc._moderate_content(_video_request(v.VideoTaskType.CONTENT_MODERATION), b"x")
        assert resp.success is True and resp.content_rating.value == "safe"
        svc.content_moderation_model = MagicMock(return_value={"unsafe": True})
        resp = await svc._moderate_content(_video_request(v.VideoTaskType.CONTENT_MODERATION), b"x")
        assert resp.content_rating.value == "unsafe"
        # error paths
        svc._extract_frames = AsyncMock(side_effect=RuntimeError("x"))
        for name in ("_recognize_faces", "_detect_scenes", "_diarize_speakers",
                     "_classify_video", "_moderate_content"):
            resp = await getattr(svc, name)(_video_request(v.VideoTaskType.SUMMARIZATION), b"x")
            assert resp.success is False

    async def test_setup_and_status(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        await svc._setup_content_moderation()
        assert "adult_content" in svc.content_moderation_policies
        await svc._setup_enterprise_features()
        assert svc.video_retention_policies["auto_delete"] is True
        await svc._setup_security_and_compliance()
        assert svc.video_security_policies is not None
        await svc._setup_security_monitoring()
        assert svc.security_monitoring is not None
        await svc._setup_compliance_monitoring()
        assert svc.compliance_monitoring is not None
        await svc._load_existing_video_data()
        await svc._setup_enterprise_features()
        svc.is_initialized = True
        status = await svc.get_service_status()
        assert status["service"] == "video_ai"
        assert status["status"] == "active"
        svc.is_initialized = False
        status = await svc.get_service_status()
        assert status["status"] == "inactive"
        await svc.close()

    async def test_security_log_preprocess(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        req = _video_request(v.VideoTaskType.SUMMARIZATION)
        check = await svc._perform_security_check(req)
        assert check["passed"] is True
        svc.enterprise_security = MagicMock()
        check = await svc._perform_security_check(req)
        assert check["passed"] is True
        svc.enterprise_security.audit_event = AsyncMock()
        await svc._log_video_request(req, MagicMock(success=True, processing_time=1.0))
        svc.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError("x"))
        await svc._log_video_request(req, MagicMock(success=True))
        # preprocess error fallback
        assert await svc._preprocess_video(req) == b"\x00" * 10
        req.video_path = "/tmp/nonexistent.mp4"
        assert await svc._preprocess_video(req) == b"\x00" * 10

    async def test_module_instance(self):
        import integrations.atom_video_ai_service as v
        status = await v.atom_video_ai_service.get_service_status()
        assert status["service"] == "video_ai"


# ============================================================================
# atom_zoom_integration
# ============================================================================


class TestZoomIntegration:
    def _svc(self, **kw):
        from integrations.atom_zoom_integration import AtomZoomIntegration
        cfg = {"api_key": "k", "api_secret": "s", "webhook_url": "https://wh",
               "enable_enterprise_features": True}
        cfg.update(kw)
        return AtomZoomIntegration(cfg)

    def _meeting(self, mid="m1", host="h1", status="started"):
        from integrations.atom_zoom_integration import ZoomMeeting, ZoomMeetingType
        return ZoomMeeting(
            meeting_id=mid, topic="Team Sync", meeting_type=ZoomMeetingType.SCHEDULED,
            host_id=host, start_time=datetime.now(timezone.utc), duration=30,
            timezone="UTC", agenda="Discuss roadmap", participants=["h1", "u2"],
            is_recorded=False, password=None, waiting_room=False,
            security_level="standard", created_at=datetime.now(timezone.utc),
            status=status, metadata={},
        )

    async def test_initialize(self):
        svc = self._svc()
        with patch.object(svc, "_test_api_connection", AsyncMock()), \
             patch.object(svc, "_setup_webhook", AsyncMock()), \
             patch.object(svc, "_setup_webhook_handlers", AsyncMock()), \
             patch.object(svc, "_setup_enterprise_features", AsyncMock()), \
             patch.object(svc, "_setup_security_and_compliance", AsyncMock()), \
             patch.object(svc, "_setup_automation", AsyncMock()), \
             patch.object(svc, "_setup_monitoring", AsyncMock()), \
             patch.object(svc, "_load_existing_data", AsyncMock()):
            assert await svc.initialize() is True
        svc2 = self._svc()
        assert await svc2.initialize() is True  # creds present, no webhook_url required
        with patch.dict(os.environ, {"ZOOM_API_KEY": "", "ZOOM_API_SECRET": "",
                                     "ZOOM_CLIENT_ID": "", "ZOOM_CLIENT_SECRET": "",
                                     "ZOOM_WEBHOOK_URL": ""}):
            svc3 = self._svc(api_key=None, api_secret=None, client_id=None, client_secret=None)
            assert not svc3.zoom_config["api_key"]
            assert await svc3.initialize() is False
        svc4 = self._svc()
        with patch.object(svc4, "_test_api_connection", AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc4.initialize() is False

    async def test_get_intelligent_workspaces_channels(self):
        svc = self._svc()
        svc.active_meetings = {"m1": self._meeting()}
        ws = await svc.get_intelligent_workspaces("h1")
        assert len(ws) == 1
        assert ws[0]["permissions"]["can_manage"] is True
        ch = await svc.get_intelligent_channels("m1", "u2")
        assert len(ch) == 1
        assert ch[0]["meeting_type"] == "scheduled"
        assert await svc.get_intelligent_channels("missing", "u2") == []
        svc.active_meetings = {}
        assert await svc.get_intelligent_workspaces("h1") == []

    async def test_send_message_and_search(self):
        svc = self._svc()
        svc.active_meetings = {"m1": self._meeting()}
        svc._send_chat_message = AsyncMock(return_value={"success": True, "message_id": "x"})
        svc._log_message_event = AsyncMock()
        result = await svc.send_intelligent_message("m1", "hi")
        assert result["success"] is True
        result = await svc.send_intelligent_message("missing", "hi")
        assert result["success"] is False
        svc._send_chat_message = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.send_intelligent_message("m1", "hi")
        assert result["success"] is False
        svc.zoom_config["enable_enterprise_features"] = False
        svc._send_chat_message = AsyncMock(return_value={"success": True})
        result = await svc.send_intelligent_message("m1", "hi")
        assert result["success"] is True
        svc.zoom_config["enable_enterprise_features"] = True
        # search
        svc.ai_service = None
        results = await svc.perform_intelligent_search("roadmap", "u1")
        assert len(results) == 1
        assert results[0]["relevance_score"] == 1.0
        results = await svc.perform_intelligent_search("roadmap", "u1", "other")
        assert results == []
        assert await svc.perform_intelligent_search("xyz", "u1") == []

    async def test_search_with_ai(self):
        svc = self._svc()
        svc.active_meetings = {"m1": self._meeting()}
        ai = MagicMock()
        ai.process_ai_request = AsyncMock()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = {"results": [{"id": "ai1"}]}
        ai.process_ai_request.return_value = resp
        svc.ai_service = ai
        import integrations.atom_zoom_integration as zm
        with patch.object(zm, "AIRequest", MagicMock(), create=True), \
             patch.object(zm, "AITaskType", MagicMock(), create=True), \
             patch.object(zm, "AIModelType", MagicMock(), create=True), \
             patch.object(zm, "AIServiceType", MagicMock(), create=True):
            results = await svc.perform_intelligent_search("roadmap", "u1")
        assert len(results) == 2
        ai.process_ai_request.return_value = MagicMock(ok=False, output_data=None)
        with patch.object(zm, "AIRequest", MagicMock(), create=True), \
             patch.object(zm, "AITaskType", MagicMock(), create=True), \
             patch.object(zm, "AIModelType", MagicMock(), create=True), \
             patch.object(zm, "AIServiceType", MagicMock(), create=True):
            assert await svc.perform_intelligent_search("roadmap", "u1") == [results[0]]
        ai.process_ai_request.side_effect = RuntimeError("x")
        with patch.object(zm, "AIRequest", MagicMock(), create=True), \
             patch.object(zm, "AITaskType", MagicMock(), create=True), \
             patch.object(zm, "AIModelType", MagicMock(), create=True), \
             patch.object(zm, "AIServiceType", MagicMock(), create=True):
            assert len(await svc.perform_intelligent_search("roadmap", "u1")) == 1

    async def test_conversation_history(self):
        from integrations.atom_zoom_integration import ZoomEvent, ZoomEventType
        svc = self._svc()
        event = ZoomEvent(event_id="e1", event_type=ZoomEventType.MEETING_STARTED,
                          meeting_id="m1", user_id="u1",
                          timestamp=datetime.now(timezone.utc), data={},
                          security_flags={}, compliance_flags={}, metadata={})
        svc.meeting_history = {"m1": [event]}
        hist = await svc.get_user_conversation_history("u1", "m1")
        assert len(hist) == 1
        assert hist[0]["channel_id"] == "m1"
        assert await svc.get_user_conversation_history("u9", "m1") == []

    async def test_oauth_and_api_connection(self):
        svc = self._svc()
        await svc._get_oauth_token()
        svc.oauth_token = "tok"
        svc.oauth_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await svc._get_oauth_token()  # cached, returns early
        resp = MagicMock()
        resp.status_code = 200
        svc.http_session.get = AsyncMock(return_value=resp)
        svc.oauth_token = "tok"
        await svc._test_api_connection()
        resp.status_code = 401
        await svc._test_api_connection()
        svc.oauth_token = None
        await svc._test_api_connection()
        svc.http_session.get = AsyncMock(side_effect=RuntimeError("x"))
        await svc._test_api_connection()
        svc.oauth_token = "tok"
        svc.oauth_token_expires = None
        await svc._get_oauth_token()

    async def test_setup_webhook(self):
        svc = self._svc()
        resp = MagicMock()
        resp.status_code = 201
        svc.http_session.post = AsyncMock(return_value=resp)
        await svc._setup_webhook()
        resp.status_code = 400
        await svc._setup_webhook()
        svc.http_session.post = AsyncMock(side_effect=RuntimeError("x"))
        await svc._setup_webhook()

    async def test_setup_handlers_and_enterprise(self):
        svc = self._svc()
        await svc._setup_webhook_handlers()
        assert len(svc.webhook_handlers) == 5
        await svc._setup_enterprise_features()  # no enterprise services
        svc.enterprise_security = MagicMock()
        svc.enterprise_automation = MagicMock()
        await svc._setup_enterprise_features()
        await svc._setup_security_policies()
        assert "meeting_access_control" in svc.security_policies
        await svc._setup_compliance_rules()
        assert "recording_compliance" in svc.compliance_rules
        await svc._setup_automation_triggers()
        assert "meeting_started" in svc.automation_triggers
        svc.enterprise_automation = None
        await svc._setup_automation()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": True})
        await svc._setup_automation()
        svc.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": False, "error": "e"})
        await svc._setup_automation()
        svc.enterprise_automation.create_integration_automation = AsyncMock(side_effect=RuntimeError("x"))
        await svc._setup_automation()
        await svc._setup_security_and_compliance()
        await svc._setup_security_monitoring()
        await svc._setup_compliance_monitoring()
        svc.zoom_config["enable_enterprise_features"] = False
        await svc._setup_security_and_compliance()
        await svc._setup_monitoring()
        await svc._load_existing_data()

    async def test_send_chat_message(self):
        svc = self._svc()
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {"message_id": "mid"}
        svc.http_session.post = AsyncMock(return_value=resp)
        result = await svc._send_chat_message("m1", "hi")
        assert result["success"] is True
        resp.status_code = 400
        resp.json.return_value = {"message": "bad"}
        result = await svc._send_chat_message("m1", "hi")
        assert result["success"] is False
        svc.http_session.post = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc._send_chat_message("m1", "hi")
        assert result["success"] is False

    async def test_log_message_event(self):
        svc = self._svc()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        await svc._log_message_event("chat", "m1", {})
        svc.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError("x"))
        await svc._log_message_event("chat", "m1", {})

    async def test_meeting_event_handlers(self):
        import integrations.atom_zoom_integration as zm
        svc = self._svc()
        svc.zoom_config["enable_enterprise_features"] = False
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record") as ingest:
            await svc._handle_meeting_started({"payload": {"object": {"id": "m1", "topic": "T", "host_id": "h"}}})
            assert "m1" in svc.active_meetings
            await svc._handle_meeting_ended({"payload": {"object": {"id": "m1"}}})
            assert svc.active_meetings["m1"].status == "ended"
            await svc._handle_meeting_ended({"payload": {"object": {"id": "nope"}}})
            await svc._handle_participant_joined({"payload": {"object": {"id": "m1", "participant": {"id": "u9", "user_name": "U"}}}})
            assert "u9" in svc.active_meetings["m1"].participants
            await svc._handle_participant_joined({"payload": {"object": {"id": "nope", "participant": {"id": "u1"}}}})
            await svc._handle_participant_left({"payload": {"object": {"id": "m1", "participant": {"id": "u9", "user_name": "U"}}}})
            assert "u9" not in svc.active_meetings["m1"].participants
            await svc._handle_participant_left({"payload": {"object": {"id": "nope", "participant": {"id": "u1"}}}})
            await svc._handle_recording_completed({"payload": {"object": {"id": "m1", "recording_files": [{"recording_length": 3600}]}}})
            assert svc.active_meetings["m1"].is_recorded is True
            assert svc.analytics_metrics["total_recording_hours"] > 0
            await svc._handle_recording_completed({"payload": {"object": {"id": "nope"}}})
        # with enterprise features -> automation trigger
        svc.zoom_config["enable_enterprise_features"] = True
        svc.enterprise_automation = MagicMock()
        await svc._setup_automation_triggers()
        svc.active_meetings = {}
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_meeting_started({"payload": {"object": {"id": "m2", "topic": "T", "host_id": "h"}}})
            assert svc.analytics_metrics["automations_triggered"] == 1

    async def test_trigger_automations(self):
        svc = self._svc()
        svc.enterprise_automation = None
        await svc._trigger_automations("meeting_started", self._meeting(), {})
        svc.enterprise_automation = MagicMock()
        svc.automation_triggers = {}
        await svc._trigger_automations("meeting_started", self._meeting(), {})
        assert svc.analytics_metrics["automations_triggered"] == 0

    async def test_close_and_status(self):
        svc = self._svc()
        status = await svc.get_service_status()
        assert status["platform"] == "zoom"
        svc.http_session = MagicMock()
        svc.http_session.aclose = AsyncMock()
        await svc.close()
        assert svc.http_session.aclose.called

    async def test_module_instance(self):
        from integrations.atom_zoom_integration import atom_zoom_integration
        status = await atom_zoom_integration.get_service_status()
        assert status["platform"] == "zoom"

    async def test_ai_search_direct(self):
        svc = self._svc()
        assert await svc._perform_ai_search("q") == []
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        svc.ai_service = ai
        assert await svc._perform_ai_search("q") == []


# ============================================================================
# atom_chat_interface
# ============================================================================


class TestChatInterface:
    def _svc(self):
        from integrations.atom_chat_interface import AtomChatInterface
        return AtomChatInterface({})

    def _msg(self, svc, text, **kw):
        from integrations.atom_chat_interface import ChatMessage
        return ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message=text,
            timestamp=datetime.now(timezone.utc), channel="default",
            context=kw.pop("context", {}), source="user", **kw,
        )

    async def test_process_message_command_and_regular(self):
        svc = self._svc()
        resp = await svc.process_message("/help", "u1", "Bob", context={})
        assert "Available commands" in resp
        resp = await svc.process_message("hello there", "u1", "Bob", context={})
        assert "help" in resp.lower() or "I'm here" in resp
        with patch.object(svc, "_save_context", AsyncMock(side_effect=RuntimeError("x"))):
            resp = await svc.process_message("/help", "u1", "Bob", context={})
            assert "error" in resp.lower()

    async def test_command_dispatch(self):
        svc = self._svc()
        svc.slack_connected = True
        svc.slack_service = MagicMock()
        svc.slack_service.list_channels = AsyncMock(return_value=[{"name": "general", "id": "C1", "num_members": 3}])
        svc.slack_service.post_message = AsyncMock(return_value={"ok": True})
        svc.slack_service.search_messages = AsyncMock(return_value={"ok": True, "messages": [{"user_name": "A", "channel_name": "c", "text": "t", "ts": "1"}]})
        ctx = {"conversation_id": "cv1", "user_id": "u1"}
        msg = self._msg(svc, "/slack-channels", context=ctx)
        resp = await svc._process_command(msg)
        assert "general" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-channels general", context=ctx))
        assert "Switched" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-channels missing", context=ctx))
        assert "not found" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-send #general hi", context=ctx))
        assert "Message sent" in resp
        svc.slack_service.post_message = AsyncMock(return_value={"ok": False, "error": "err"})
        resp = await svc._process_command(self._msg(svc, "/slack-send #general hi", context=ctx))
        assert "Failed" in resp
        svc.slack_service.list_channels = AsyncMock(return_value=[])
        resp = await svc._process_command(self._msg(svc, "/slack-send hi",
                                                    context={"conversation_id": "cvX", "user_id": "u1"}))
        assert "Channel not found" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-search hello", context=ctx))
        assert "Found 1 results" in resp
        svc.slack_service.search_messages = AsyncMock(return_value={"ok": True, "messages": []})
        resp = await svc._process_command(self._msg(svc, "/slack-search hello", context=ctx))
        assert "No messages" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-workflows list", context=ctx))
        assert "No workflows" in resp or "workflow" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-workflows run", context=ctx))
        assert "specify" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-workflows create wf", context=ctx))
        assert "list, run" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-workflows run wf1", context=ctx))
        assert "not found" in resp
        # unknown + permission denied
        resp = await svc._process_command(self._msg(svc, "/nope x"))
        assert "Unknown command" in resp
        svc.commands["help"].permission_level = "super_admin"
        resp = await svc._process_command(self._msg(svc, "/help"))
        assert "permission" in resp
        # slack-required gating
        svc.slack_connected = False
        resp = await svc._process_command(self._msg(svc, "/slack-channels"))
        assert "slack-connect" in resp

    async def test_slack_connect(self):
        svc = self._svc()
        svc.slack_service = None
        resp = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "not available" in resp
        svc.slack_service = MagicMock()
        svc.slack_service.test_connection = AsyncMock(return_value={"connected": True, "team": "Team"})
        resp = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"), "ws1")
        assert "Team" in resp
        resp = await svc._process_command(self._msg(svc, "/slack-connect ws1"))
        assert "Team" in resp
        svc.slack_service.test_connection = AsyncMock(return_value={"connected": False, "error": "no"})
        resp = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"), "ws1")
        assert "Failed" in resp
        ws = MagicMock()
        ws.name = "W"; ws.domain = "d"; ws.id = "w1"
        svc.slack_service.list_workspaces = AsyncMock(return_value=[ws])
        resp = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "Available workspaces" in resp
        svc.slack_service.list_workspaces = AsyncMock(return_value=[])
        resp = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "No workspaces" in resp
        svc.slack_service.list_workspaces = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_slack_connect(self._msg(svc, "/slack-connect"))
        assert "Error" in resp

    async def test_memory_commands(self):
        svc = self._svc()
        svc.memory_service = None
        resp = await svc._handle_remember(self._msg(svc, "/remember x"), "x")
        assert "not available" in resp
        resp = await svc._handle_recall(self._msg(svc, "/recall"), None)
        assert "not available" in resp
        svc.memory_service = MagicMock()
        svc.memory_service.store = AsyncMock()
        resp = await svc._handle_remember(self._msg(svc, "/remember x"), "x")
        assert "I'll remember" in resp
        svc.memory_service.store = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_remember(self._msg(svc, "/remember x"), "x")
        assert "Error" in resp
        svc.memory_service.search = AsyncMock(return_value=[{"content": "c", "timestamp": "t"}])
        resp = await svc._handle_recall(self._msg(svc, "/recall q"), "q")
        assert "Found memories" in resp
        svc.memory_service.search = AsyncMock(return_value=[])
        resp = await svc._handle_recall(self._msg(svc, "/recall q"), "q")
        assert "No memories" in resp
        svc.memory_service.get_recent = AsyncMock(return_value=[{"content": "c", "timestamp": "t"}])
        resp = await svc._handle_recall(self._msg(svc, "/recall"), None)
        assert "Recent memories" in resp
        svc.memory_service.get_recent = AsyncMock(return_value=[])
        resp = await svc._handle_recall(self._msg(svc, "/recall"), None)
        assert "No memories found" in resp
        svc.memory_service.search = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_recall(self._msg(svc, "/recall q"), "q")
        assert "Error" in resp

    async def test_search_command(self):
        svc = self._svc()
        svc.search_service = None
        resp = await svc._handle_search(self._msg(svc, "/search q"), "q")
        assert "not available" in resp
        svc.search_service = MagicMock()
        svc.search_service.search = AsyncMock(return_value=[{"title": "T", "source": "s", "snippet": "sn", "timestamp": "t"}])
        resp = await svc._handle_search(self._msg(svc, "/search q"), "q")
        assert "Found 1 results" in resp
        svc.search_service.search = AsyncMock(return_value=[])
        resp = await svc._handle_search(self._msg(svc, "/search q"), "q")
        assert "No results" in resp
        svc.search_service.search = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_search(self._msg(svc, "/search q"), "q")
        assert "Error" in resp

    async def test_help_and_context(self):
        svc = self._svc()
        resp = await svc._handle_help(self._msg(svc, "/help help"), "help")
        assert "Description" in resp
        resp = await svc._handle_help(self._msg(svc, "/help nope"), "nope")
        assert "Unknown command" in resp
        resp = await svc._handle_help(self._msg(svc, "/help"), None)
        assert "Available commands" in resp
        msg = self._msg(svc, "/context", context={"conversation_id": "cv1"})
        resp = await svc._handle_context(msg)
        assert "Conversation ID: cv1" in resp
        resp = await svc._handle_context(msg, "clear")
        assert "Context cleared" in resp
        resp = await svc._handle_context(msg, "set", "topic1")
        assert "topic set" in resp
        resp = await svc._handle_context(msg, "bogus")
        assert "show, clear, set" in resp
        resp = await svc._handle_context(self._msg(svc, "/context"), "show")
        assert "No conversation context" in resp

    async def test_intents_and_ai_response(self):
        svc = self._svc()
        intents, entities = await svc._extract_intents_entities("send this to #general")
        assert "send_message" in intents
        assert entities["channel"] == "general"
        intents, entities = await svc._extract_intents_entities("find stuff")
        assert "search" in intents
        intents, entities = await svc._extract_intents_entities("remember this")
        assert "remember" in intents
        intents, entities = await svc._extract_intents_entities("nothing")
        assert intents == [] and entities == {}
        msg = self._msg(svc, "hi", context={"slack_channel_id": "C1"})
        resp = await svc._generate_ai_response(msg, [], {})
        assert "slack" in resp
        resp = await svc._generate_ai_response(self._msg(svc, "hi"), ["search"], {})
        assert "search" in resp
        resp = await svc._generate_ai_response(self._msg(svc, "hi"), ["send_message"], {})
        assert "send" in resp
        for i in range(6):
            svc.contexts["cv"] = svc._get_context("cv", "u1")
            svc.contexts["cv"].messages.append(self._msg(svc, f"m{i}"))
        resp = await svc._generate_ai_response(self._msg(svc, "hi", context={"conversation_id": "cv"}), [], {})
        assert "tracking" in resp
        resp = await svc._generate_ai_response(self._msg(svc, "hi"), [], {})
        assert "I'm here to help" in resp

    async def test_context_permissions_callbacks(self):
        svc = self._svc()
        assert svc._get_user_permissions("u1") == ["user"]
        assert svc._check_permissions(["user"], "user") is True
        assert svc._check_permissions(["user"], "admin") is False
        assert svc._check_permissions(["super_admin"], "super_admin") is True
        assert svc._get_context_channel_workspace({}) is None
        svc.contexts["cv1"] = svc._get_context("cv1", "u1")
        svc.contexts["cv1"].slack_workspace_id = "ws"
        assert svc._get_context_channel_workspace({"conversation_id": "cv1", "user_id": "u1"}) == "ws"
        called = []

        async def cb(msg):
            called.append(msg)

        svc.add_message_callback(cb)
        svc.add_message_callback(lambda m: called.append("sync"))
        msg = self._msg(svc, "hi")
        await svc._notify_callbacks(msg)
        assert len(called) == 2
        svc.remove_message_callback(cb)
        svc.remove_message_callback(cb)
        assert len(svc.message_callbacks) == 1
        bad = MagicMock(side_effect=RuntimeError("x"))
        svc.add_message_callback(bad)
        await svc._notify_callbacks(msg)

    async def test_regular_message_context_update(self):
        svc = self._svc()
        msg = self._msg(svc, "hello", context={"conversation_id": "cv2", "user_id": "u1"})
        svc._extract_intents_entities = AsyncMock(return_value=(["search"], {"channel": "c"}))
        svc._generate_ai_response = AsyncMock(return_value="ok")
        resp = await svc._process_regular_message(msg)
        assert resp == "ok"
        assert svc.contexts["cv2"].intents == ["search"]
        svc._extract_intents_entities = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._process_regular_message(msg)
        assert "trouble" in resp

    async def test_save_context_and_history(self):
        svc = self._svc()
        memory = MagicMock()
        memory.store = AsyncMock()
        svc.memory_service = memory
        ctx = svc._get_context("cv", "u1")
        await svc._save_context(ctx)
        assert memory.store.called
        memory.store = AsyncMock(side_effect=RuntimeError("x"))
        await svc._save_context(ctx)
        svc.memory_service = None
        await svc._save_context(ctx)
        assert svc.get_conversation_history("missing") == []
        assert len(svc.get_conversation_history("cv")) == 0

    async def test_slack_content_indexing(self):
        svc = self._svc()
        await svc.index_slack_content()  # not connected
        svc.slack_connected = True
        await svc.index_slack_content()  # no search service
        svc.search_service = MagicMock()
        svc.search_service.index = AsyncMock()
        svc.slack_service = MagicMock()
        svc.slack_service.list_channels = AsyncMock(return_value=[{"id": "C1"}])
        svc.slack_service.get_channel_history = AsyncMock(return_value=[
            {"ts": "1", "text": "hi", "user": "u1", "reactions": [], "files": [], "thread_ts": None}])
        svc.slack_workspaces = [{"id": "ws1"}]
        await svc.index_slack_content()
        assert svc.search_service.index.called
        svc.slack_service.get_channel_history = AsyncMock(side_effect=RuntimeError("x"))
        await svc.index_slack_content()
        svc.slack_service.list_channels = AsyncMock(side_effect=RuntimeError("x"))
        await svc.index_slack_content()
        await svc.sync_with_slack()
        svc.slack_service.list_workspaces = AsyncMock(return_value=[{"id": "ws1"}])
        await svc.sync_with_slack()
        assert svc.slack_connected is True
        svc.slack_service.list_workspaces = AsyncMock(side_effect=RuntimeError("x"))
        await svc.sync_with_slack()

    async def test_module_instance(self):
        from integrations.atom_chat_interface import atom_chat_interface
        assert atom_chat_interface is not None
        resp = await atom_chat_interface.process_message("hi", "u1", "Bob", context={})
        assert resp


class TestVideoAIGaps:
    def _svc(self):
        import integrations.atom_video_ai_service as v
        return v.AtomVideoAIService(config={"enable_enterprise_features": True})

    async def test_platform_integrations_from_globals(self):
        import integrations.atom_video_ai_service as mod
        names = ["atom_slack_integration", "atom_teams_integration",
                 "atom_google_chat_integration", "atom_discord_integration",
                 "atom_telegram_integration", "atom_whatsapp_integration",
                 "atom_zoom_integration"]
        saved = {n: getattr(mod, n, None) for n in names}
        for n in names:
            setattr(mod, n, MagicMock())
        try:
            svc = mod.AtomVideoAIService(config={})
            assert len(svc.platform_integrations) == 7
        finally:
            for n in names:
                if saved[n] is None:
                    delattr(mod, n)
                else:
                    setattr(mod, n, saved[n])

    async def test_load_video_models_stubbed(self):
        import integrations.atom_video_ai_service as mod
        transformers = MagicMock()
        transformers.BlipForConditionalGeneration.from_pretrained.return_value = MagicMock()
        transformers.BlipProcessor.from_pretrained.return_value = MagicMock()
        transformers.AutoProcessor.from_pretrained.return_value = MagicMock()
        transformers.TimesformerForVideoClassification.from_pretrained.return_value = MagicMock()
        ultralytics = MagicMock()
        ultralytics.YOLO.return_value = MagicMock()
        svc = self._svc()
        with patch.dict(sys.modules, {"transformers": transformers, "ultralytics": ultralytics}):
            await svc._load_video_models()
        assert svc.blip_model is not None
        assert svc.yolo_model is not None
        assert svc.video_classification_model is not None

    async def test_summarize_torch_branch(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        svc._extract_frames = AsyncMock(return_value=[MagicMock()])
        svc.blip_processor = MagicMock()
        svc.blip_processor.decode.return_value = "cap"
        svc.blip_model = MagicMock()
        svc.blip_model.generate.return_value = [MagicMock()]
        fake_torch = MagicMock()
        with patch.object(v, "TORCH_AVAILABLE", True), patch.object(v, "torch", fake_torch):
            resp = await svc._summarize_video(_video_request(v.VideoTaskType.SUMMARIZATION), b"x")
        assert resp.success is True
        assert fake_torch.no_grad.called

    async def test_preprocess_error_branches(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        req = _video_request(v.VideoTaskType.SUMMARIZATION)
        req.video_path = "/tmp/nope.mp4"
        result = await svc._preprocess_video(req)
        assert result == b"\x00" * 10
        # error inside -> fallback to video_data
        with patch("os.path.exists", side_effect=RuntimeError("x")):
            result = await svc._preprocess_video(req)
            assert result == b"\x00" * 10

    async def test_setup_methods_error_branches(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        for method in ("_setup_content_moderation", "_setup_enterprise_features",
                       "_setup_security_and_compliance", "_setup_security_monitoring",
                       "_setup_compliance_monitoring", "_load_existing_video_data"):
            with patch.object(svc, method, side_effect=RuntimeError("x")):
                with patch("integrations.atom_video_ai_service.logger"):
                    with pytest.raises(RuntimeError):
                        await getattr(svc, method)()
        await svc._setup_content_moderation()
        await svc._setup_security_monitoring()
        await svc._setup_compliance_monitoring()

    async def test_status_close_error_branches(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()

        class Boom:
            def __getitem__(self, k):
                raise RuntimeError("boom")
        with patch.object(svc, "video_config", Boom()):
            status = await svc.get_service_status()
            assert "error" in status
        await svc.close()
        with patch.object(v.rate_limiter, "is_rate_limited", side_effect=RuntimeError("x")):
            await svc.close()
        with patch.object(v.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            await svc.close()

    async def test_security_check_error(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()

        class BoomBool:
            def __bool__(self):
                raise RuntimeError("x")
        svc.enterprise_security = BoomBool()
        check = await svc._perform_security_check(_video_request(v.VideoTaskType.SUMMARIZATION))
        assert check["passed"] is False

    async def test_analyze_video_quality_real_cv2(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        cap = MagicMock()
        cap.get.return_value = 0
        with patch.dict(sys.modules, {"cv2": _fake_cv2_module(video_capture=MagicMock(return_value=cap))}):
            assert await svc._analyze_video_quality(b"not a video") == 0.0

    async def test_extract_frames_error(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        with patch.dict(sys.modules, {"cv2": None}):
            assert await svc._extract_frames(b"x") == []
        fake_cv2 = _fake_cv2_module()
        fake_cv2.VideoCapture = MagicMock(side_effect=RuntimeError("x"))
        with patch.dict(sys.modules, {"cv2": fake_cv2}):
            assert await svc._extract_frames(b"x") == []


class TestZoomGaps:
    def _svc(self, **kw):
        from integrations.atom_zoom_integration import AtomZoomIntegration
        cfg = {"api_key": "k", "api_secret": "s", "enable_enterprise_features": False}
        cfg.update(kw)
        return AtomZoomIntegration(cfg)

    def _meeting(self, mid="m1", host="h1"):
        from integrations.atom_zoom_integration import ZoomMeeting, ZoomMeetingType
        return ZoomMeeting(
            meeting_id=mid, topic="T", meeting_type=ZoomMeetingType.INSTANT, host_id=host,
            start_time=datetime.now(timezone.utc), duration=0, timezone="UTC", agenda="a",
            participants=[host], is_recorded=False, password=None, waiting_room=False,
            security_level="s", created_at=datetime.now(timezone.utc), status="started",
            metadata={},
        )

    async def test_getter_error_branches(self):
        svc = self._svc()
        broken = MagicMock()
        broken.host_id = "h1"
        broken.start_time.isoformat.side_effect = RuntimeError("x")
        svc.active_meetings = {"m1": broken}
        assert await svc.get_intelligent_workspaces("h1") == []
        assert await svc.get_intelligent_channels("m1", "u1") == []
        broken2 = MagicMock()
        broken2.meeting_id = "m1"
        broken2.start_time.isoformat.side_effect = RuntimeError("x")
        svc.active_meetings = {"m1": broken2}
        assert await svc.perform_intelligent_search("q", "u1") == []
        ev = MagicMock()
        ev.user_id = "u1"
        ev.timestamp.isoformat.side_effect = RuntimeError("x")
        svc.meeting_history = {"m1": [ev]}
        assert await svc.get_user_conversation_history("u1", "m1") == []

    async def test_webhook_handlers_invoked(self):
        from integrations.atom_zoom_integration import ZoomEventType
        svc = self._svc()
        await svc._setup_webhook_handlers()
        assert len(svc.webhook_handlers) == 5
        event_data = {"payload": {"object": {"id": "m1", "topic": "T", "host_id": "h",
                                             "participant": {"id": "u1", "user_name": "U"},
                                             "recording_files": []}}}
        await svc.webhook_handlers[ZoomEventType.MEETING_STARTED](event_data)
        assert "m1" in svc.active_meetings
        await svc.webhook_handlers[ZoomEventType.MEETING_PARTICIPANT_JOINED](event_data)
        await svc.webhook_handlers[ZoomEventType.RECORDING_COMPLETED](event_data)
        await svc.webhook_handlers[ZoomEventType.MEETING_ENDED](event_data)
        await svc.webhook_handlers[ZoomEventType.MEETING_PARTICIPANT_LEFT](event_data)

    async def test_relevance_score_error(self):
        svc = self._svc()
        assert svc._calculate_relevance_score(12345, "x") == 0.0
        assert svc._calculate_relevance_score("", "") == 0.0
        assert svc._calculate_relevance_score("a b", "a c b") == 1.0

    async def test_oauth_token_refresh_branch(self):
        svc = self._svc()
        svc.oauth_token = "tok"
        svc.oauth_token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        await svc._get_oauth_token()

    async def test_event_handler_error_branches(self):
        import integrations.atom_zoom_integration as zm
        svc = self._svc()
        svc.enterprise_automation = MagicMock()
        await svc._setup_automation_triggers()
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_meeting_started({"payload": {"object": {"id": "m1", "topic": "T", "host_id": "h"}}})
            await svc._handle_meeting_ended({"payload": {"object": {"id": "m1"}}})
            await svc._handle_recording_completed({"payload": {"object": {"id": "m1", "recording_files": []}}})
        assert svc.analytics_metrics["automations_triggered"] == 0
        # broken event data -> except branch
        with patch.object(svc, "_handle_meeting_started", side_effect=RuntimeError("boom")):
            with patch("integrations.atom_zoom_integration.logger"):
                with pytest.raises(RuntimeError):
                    await svc._handle_meeting_started({"payload": {}})

    async def test_send_message_enterprise_off_logging(self):
        svc = self._svc()
        svc.active_meetings = {"m1": self._meeting()}
        svc._send_chat_message = AsyncMock(return_value={"success": True})
        svc.zoom_config["enable_enterprise_features"] = False
        result = await svc.send_intelligent_message("m1", "hi")
        assert result["success"] is True

    async def test_ai_search_direct_errors(self):
        svc = self._svc()
        ai = MagicMock()
        ai.process_ai_request = AsyncMock()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = {"results": [{"id": "r"}]}
        ai.process_ai_request.return_value = resp
        svc.ai_service = ai
        import integrations.atom_zoom_integration as zm
        with patch.object(zm, "AIRequest", MagicMock(), create=True), \
             patch.object(zm, "AITaskType", MagicMock(), create=True), \
             patch.object(zm, "AIModelType", MagicMock(), create=True), \
             patch.object(zm, "AIServiceType", MagicMock(), create=True):
            assert await svc._perform_ai_search("q") == [{"id": "r"}]


class TestChatInterfaceGaps:
    def _svc(self):
        from integrations.atom_chat_interface import AtomChatInterface
        return AtomChatInterface({})

    def _msg(self, svc, text, **kw):
        from integrations.atom_chat_interface import ChatMessage
        return ChatMessage(
            id="m1", user_id="u1", user_name="Bob", message=text,
            timestamp=datetime.now(timezone.utc), channel="default",
            context=kw.pop("context", {}), source="user", **kw,
        )

    async def test_command_execution_error_branch(self):
        svc = self._svc()

        async def bad_handler(message, *args):
            raise RuntimeError("boom")

        from integrations.atom_chat_interface import SlackCommand
        svc.commands["boom"] = SlackCommand(
            trigger="boom", pattern=r"/boom", handler=bad_handler,
            description="boom cmd")
        resp = await svc._process_command(self._msg(svc, "/boom"))
        assert "Error executing command" in resp

    async def test_slack_handler_error_branches(self):
        svc = self._svc()
        svc.slack_connected = True
        svc.slack_service = MagicMock()
        svc.slack_service.list_channels = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_slack_channels(self._msg(svc, "/slack-channels", context={"conversation_id": "cv1"}))
        assert "Error listing channels" in resp
        svc.slack_service.list_channels = AsyncMock(return_value=[{"name": "g", "id": "C1"}])
        svc.slack_service.post_message = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_slack_send(self._msg(svc, "/slack-send g hi", context={"conversation_id": "cv1"}), "g", "hi")
        assert "Error sending message" in resp
        svc.slack_service.search_messages = AsyncMock(side_effect=RuntimeError("x"))
        resp = await svc._handle_slack_search(self._msg(svc, "/slack-search q"), "q")
        assert "Error searching Slack" in resp
        svc.slack_connected = False
        resp = await svc._handle_slack_search(self._msg(svc, "/slack-search q"), "q")
        assert "slack-connect" in resp
        resp = await svc._handle_slack_send(self._msg(svc, "/slack-send g hi"), "g", "hi")
        assert "slack-connect" in resp

    async def test_slack_workflows_error(self):
        import integrations.atom_chat_interface as mod
        svc = self._svc()
        fake = MagicMock()
        fake.list_workflows.side_effect = RuntimeError("x")
        with patch.object(mod, "slack_workflow_automation", fake):
            resp = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows list"))
            assert "Error with workflows" in resp

    async def test_slack_workflows_run_execute(self):
        import integrations.atom_chat_interface as mod
        svc = self._svc()
        wf = MagicMock()
        wf.name = "wf1"
        wf.id = "wfid"
        wf.description = "desc"
        wf.active = True
        fake = MagicMock()
        fake.list_workflows.return_value = [wf]
        fake.execute_workflow = AsyncMock(return_value=MagicMock(id="exec1"))
        svc.slack_connected = True
        with patch.object(mod, "slack_workflow_automation", fake):
            resp = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows list"), "list")
            assert "wf1" in resp
            resp = await svc._handle_slack_workflows(self._msg(svc, "/slack-workflows run wf1"), "run", "wf1")
            assert "exec1" in resp
            resp = await svc._process_command(self._msg(svc, "/slack-workflows run wf1"))
            assert "exec1" in resp

    async def test_regular_message_no_context(self):
        svc = self._svc()
        svc._extract_intents_entities = AsyncMock(return_value=(["search"], {}))
        svc._generate_ai_response = AsyncMock(return_value="ok")
        resp = await svc._process_regular_message(self._msg(svc, "hello", context={}))
        assert resp == "ok"


class TestVideoAIFinalGaps:
    def _svc(self):
        import integrations.atom_video_ai_service as v
        return v.AtomVideoAIService(config={"enable_enterprise_features": True})

    async def test_summarize_with_ai_service(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        svc._extract_frames = AsyncMock(return_value=[MagicMock()])
        svc.blip_processor = MagicMock()
        svc.blip_processor.decode.return_value = "cap"
        svc.blip_model = MagicMock()
        svc.blip_model.generate.return_value = [MagicMock()]
        ai = MagicMock()
        resp = MagicMock()
        resp.ok = True
        resp.output_data = {"summary": "S", "key_points": ["k"], "topics": ["t"]}
        ai.process_ai_request = AsyncMock(return_value=resp)
        svc.ai_service = ai
        with patch.object(v, "AIRequest", MagicMock(), create=True), \
             patch.object(v, "AITaskType", MagicMock(), create=True), \
             patch.object(v, "AIModelType", MagicMock(), create=True), \
             patch.object(v, "AIServiceType", MagicMock(), create=True):
            r = await svc._summarize_video(_video_request(v.VideoTaskType.SUMMARIZATION), b"x")
        assert r.success is True and r.text == "S"
        # ai failure inside try
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(v, "AIRequest", MagicMock(), create=True), \
             patch.object(v, "AITaskType", MagicMock(), create=True), \
             patch.object(v, "AIModelType", MagicMock(), create=True), \
             patch.object(v, "AIServiceType", MagicMock(), create=True):
            r = await svc._summarize_video(_video_request(v.VideoTaskType.SUMMARIZATION), b"x")
        assert r.success is True and r.text == "Unable to generate summary"

    async def test_extract_frames_success_loop(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        fake_cap = MagicMock()
        fake_cap.get.return_value = 10
        fake_cap.read.return_value = (True, MagicMock())
        fake_cv2 = _fake_cv2_module(video_capture=MagicMock(return_value=fake_cap))
        with patch.dict(sys.modules, {"cv2": fake_cv2}):
            frames = await svc._extract_frames(b"data", num_frames=5)
        assert len(frames) == 5
        assert fake_cap.release.called

    async def test_classify_branches(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        obj = MagicMock()
        obj.cls = 0
        obj.conf = 0.9
        result = MagicMock()
        result.boxes = [obj]

        def make_classify(name, count):
            results = []
            for _ in range(count):
                r = MagicMock()
                r.boxes = [MagicMock()]
                r.boxes[0].cls = 0
                r.boxes[0].conf = 0.9
                r.names = {0: name}
                results.append(r)
            svc.yolo_model = MagicMock(return_value=results)
            return [MagicMock()] * count

        assert await svc._classify_video_content(make_classify("person", 12) and [MagicMock()] * 12) == "social_gathering"
        # office_meeting: person>10 and computer>5
        frames = [MagicMock()] * 12
        svc.yolo_model = MagicMock(return_value=[MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "person"})] * 12 + [MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "computer"})] * 6)
        assert await svc._classify_video_content(frames) == "office_meeting"
        svc.yolo_model = MagicMock(return_value=[MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "person"})] * 12 + [MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "whiteboard"})] * 3)
        assert await svc._classify_video_content(frames) == "presentation"
        svc.yolo_model = MagicMock(return_value=[MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "car"})] * 6)
        assert await svc._classify_video_content(frames) == "traffic_scene"
        svc.yolo_model = MagicMock(return_value=[MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "computer"})] * 11)
        assert await svc._classify_video_content(frames) == "tutorial"
        svc.yolo_model = MagicMock(return_value=[MagicMock(boxes=[MagicMock(cls=0, conf=0.9)], names={0: "desk"})])
        assert await svc._classify_video_content(frames) == "general"
        svc.yolo_model = MagicMock(return_value=[MagicMock(boxes=[MagicMock(cls=0, conf=0.3)], names={0: "person"})])
        assert await svc._classify_video_content(frames) == "general"
        svc.yolo_model = MagicMock(side_effect=RuntimeError("x"))
        assert await svc._classify_video_content(frames) == "unknown"

    async def test_security_and_log_branches(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        req = _video_request(v.VideoTaskType.SUMMARIZATION)
        await svc._log_video_request(req, MagicMock(success=True, processing_time=1.0, confidence=0.5))
        assert svc.enterprise_security.audit_event.called

    async def test_load_video_models_error_branch(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        with patch.object(v.rate_limiter, "is_rate_limited", side_effect=RuntimeError("x")):
            await svc._load_video_models()
        with patch.object(v.circuit_breaker, "is_enabled", new=AsyncMock(side_effect=RuntimeError("x"))):
            await svc._load_video_models()

    async def test_create_error_response_direct(self):
        import integrations.atom_video_ai_service as v
        svc = self._svc()
        req = _video_request(v.VideoTaskType.SUMMARIZATION)
        resp = svc._create_error_response(req, "boom")
        assert resp.success is False and resp.metadata["error"] == "boom"


class TestZoomExceptBranches:
    """Trigger the remaining except branches in atom_zoom_integration."""

    def _svc(self):
        from integrations.atom_zoom_integration import AtomZoomIntegration
        return AtomZoomIntegration({"api_key": "k", "api_secret": "s",
                                    "enable_enterprise_features": False})

    async def test_history_except(self):
        svc = self._svc()
        ev = MagicMock()
        ev.user_id = "u1"
        ev.timestamp.isoformat.side_effect = RuntimeError("x")
        svc.meeting_history = {"m1": [ev]}
        assert await svc.get_user_conversation_history("u1", "m1") == []

    async def test_status_except(self):
        svc = self._svc()

        class Boom:
            def __getitem__(self, k):
                raise RuntimeError("boom")
        with patch.object(svc, "zoom_config", Boom()):
            status = await svc.get_service_status()
            assert "error" in status

    async def test_api_connection_excepts(self):
        svc = self._svc()
        svc.http_session = MagicMock()
        svc.http_session.get = AsyncMock(side_effect=RuntimeError("x"))
        await svc._test_api_connection()
        with patch.object(svc, "_get_oauth_token", AsyncMock(side_effect=RuntimeError("y"))):
            await svc._test_api_connection()
        svc.http_session.post = AsyncMock(side_effect=RuntimeError("z"))
        await svc._setup_webhook()
        with patch.object(svc, "_get_oauth_token", AsyncMock(side_effect=RuntimeError("y"))):
            await svc._setup_webhook()
        await svc._get_oauth_token()

    async def test_setup_webhook_handlers_except(self):
        svc = self._svc()
        with patch.object(svc, "_handle_meeting_started", AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_zoom_integration.logger"):
                await svc._setup_webhook_handlers()

    async def test_enterprise_setup_excepts(self):
        svc = self._svc()
        for method in ("_setup_security_policies", "_setup_compliance_rules",
                       "_setup_automation_triggers"):
            with patch.object(svc, method, side_effect=RuntimeError("x")):
                with patch("integrations.atom_zoom_integration.logger"):
                    with pytest.raises(RuntimeError):
                        await getattr(svc, method)()
        with patch.object(svc, "_setup_security_policies", AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc, "enterprise_automation", MagicMock()), \
             patch.object(svc, "enterprise_security", MagicMock()):
            with patch("integrations.atom_zoom_integration.logger"):
                await svc._setup_enterprise_features()
        with patch.object(svc, "enterprise_automation", MagicMock()), \
             patch.object(svc, "enterprise_security", MagicMock()):
            await svc._setup_enterprise_features()

    async def test_automation_setup_except(self):
        svc = self._svc()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(side_effect=RuntimeError("x"))
        await svc._setup_automation()

    async def test_security_compliance_excepts(self):
        svc = self._svc()
        svc.zoom_config["enable_enterprise_features"] = True
        with patch.object(svc, "_setup_security_monitoring", AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_zoom_integration.logger"):
                await svc._setup_security_and_compliance()
        for method in ("_setup_security_monitoring", "_setup_compliance_monitoring",
                       "_setup_monitoring", "_load_existing_data"):
            with patch.object(svc, method, side_effect=RuntimeError("x")):
                with patch("integrations.atom_zoom_integration.logger"):
                    with pytest.raises(RuntimeError):
                        await getattr(svc, method)()

    async def test_event_handler_excepts(self):
        import integrations.atom_zoom_integration as zm
        svc = self._svc()
        svc.zoom_config["enable_enterprise_features"] = True
        svc.enterprise_automation = MagicMock()
        await svc._setup_automation_triggers()
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_meeting_started({"payload": {"object": {"id": "m1", "topic": "T", "host_id": "h"}}})
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_meeting_ended({"payload": {"object": {"id": "m1"}}})
            await svc._handle_recording_completed({"payload": {"object": {"id": "m1", "recording_files": []}}})
        await svc._handle_meeting_ended({"payload": {"object": {"id": "nope"}}})
        await svc._handle_recording_completed({"payload": {"object": {"id": "nope"}}})
        await svc._handle_participant_left({"payload": {"object": {"id": "nope", "participant": {"id": "u1"}}}})
        # trigger trigger_automations failure inside handlers
        with patch.object(svc, "_trigger_automations", AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_zoom_integration.logger"):
                await svc._handle_meeting_started({"payload": {"object": {"id": "m2", "topic": "T", "host_id": "h"}}})
                await svc._handle_meeting_ended({"payload": {"object": {"id": "m2"}}})
                await svc._handle_participant_joined({"payload": {"object": {"id": "m2", "participant": {"id": "u9", "user_name": "U"}}}})
                await svc._handle_recording_completed({"payload": {"object": {"id": "m2", "recording_files": []}}})
        # broken event_data -> outer except
        svc.active_meetings = {"m3": self._meeting("m3")}
        with patch("integrations.atom_zoom_integration.logger"):
            await svc._handle_meeting_started({"payload": {"object": {}}})

    def _meeting(self, mid="m1", host="h1"):
        from integrations.atom_zoom_integration import ZoomMeeting, ZoomMeetingType
        return ZoomMeeting(
            meeting_id=mid, topic="T", meeting_type=ZoomMeetingType.INSTANT, host_id=host,
            start_time=datetime.now(timezone.utc), duration=0, timezone="UTC", agenda="a",
            participants=[host], is_recorded=False, password=None, waiting_room=False,
            security_level="s", created_at=datetime.now(timezone.utc), status="started",
            metadata={},
        )

    async def test_close_except(self):
        import integrations.atom_zoom_integration as zm
        svc = self._svc()
        svc.http_session = MagicMock()
        svc.http_session.aclose = AsyncMock(side_effect=RuntimeError("x"))
        with patch("integrations.atom_zoom_integration.logger"):
            await svc.close()

    async def test_trigger_automations_inner_except(self):
        svc = self._svc()
        svc.enterprise_automation = MagicMock()
        svc.automation_triggers = {
            "meeting_started": {"enabled": True, "conditions": [], "actions": []},
        }
        with patch("integrations.atom_zoom_integration.logger"):
            await svc._trigger_automations("meeting_started", self._meeting(), {})


class TestZoomExceptBranches2:
    def _svc(self):
        from integrations.atom_zoom_integration import AtomZoomIntegration
        return AtomZoomIntegration({"api_key": "k", "api_secret": "s",
                                    "enable_enterprise_features": False})

    async def test_search_outer_except(self):
        svc = self._svc()
        svc.active_meetings = {"m1": MagicMock(topic=MagicMock())}
        assert await svc.perform_intelligent_search("q", "u1") == []

    async def test_oauth_except(self):
        svc = self._svc()
        svc.oauth_token = "tok"
        svc.oauth_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch("integrations.atom_zoom_integration.datetime") as dt:
            dt.now.side_effect = RuntimeError("x")
            await svc._get_oauth_token()

    async def test_event_ingest_excepts(self):
        import integrations.atom_zoom_integration as zm
        svc = self._svc()
        svc.zoom_config["enable_enterprise_features"] = False
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_meeting_started({"payload": {"object": {"id": "m1", "topic": "T", "host_id": "h"}}})
            await svc._handle_participant_joined({"payload": {"object": {"id": "m1", "participant": {"id": "u1", "user_name": "U"}}}})
            await svc._handle_participant_left({"payload": {"object": {"id": "m1", "participant": {"id": "u1", "user_name": "U"}}}})
        # participant_left outer except via broken meeting
        svc.active_meetings = {"m1": MagicMock(participants=MagicMock())}
        with patch("integrations.atom_zoom_integration.logger"):
            await svc._handle_participant_left({"payload": {"object": {"id": "m1", "participant": {"id": "u1", "user_name": "U"}}}})
        # recording inner except + outer
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_recording_completed({"payload": {"object": {"id": "m1", "recording_files": []}}})
        svc.active_meetings["m1"] = MagicMock(is_recorded=True, metadata=MagicMock())
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_recording_completed({"payload": {"object": {"id": "m1", "recording_files": []}}})
        # meeting_ended inner except
        with patch.object(zm.atom_ingestion_pipeline, "ingest_record", side_effect=RuntimeError("x")):
            await svc._handle_meeting_ended({"payload": {"object": {"id": "m1"}}})
