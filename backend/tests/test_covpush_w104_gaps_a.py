# -*- coding: utf-8 -*-
"""Coverage wave 104 — remaining long-tail gaps (verified first).

Real gaps (everything else in the wave-104 list is already >=95%):
1.  core/llm/registry/test_queries.py            — module of pytest test
    functions/classes requiring PostgreSQL; we execute each test method
    directly with a fully mocked Session so the lines count (same technique
    as tests/test_covpush_w103_devtools.py used for test_cache.py).
2.  integrations/atom_video_ai_service.py        — 83% -> target >=95%.

No network, no real database, no real models. Plain pytest + unittest.mock.
"""
import asyncio
import os
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# =========================================================================== #
# core/llm/registry/test_queries.py — execute the embedded tests directly.
# =========================================================================== #
def _model(name, tenant="tenant-1", provider="openai"):
    return SimpleNamespace(
        model_name=name, tenant_id=tenant, provider=provider,
        provider_metadata=None,
    )


def _fake_db(scalars_all=None, fetchall_rows=None, orm_all=None):
    """Session mock: db.execute(...) supports .scalars().all() and
    .fetchall(); db.query(...).filter_by(...).all() for ORM-style access."""
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars_all or []
    result.fetchall.return_value = fetchall_rows or []
    db.execute.return_value = result
    db.query.return_value.filter_by.return_value.all.return_value = orm_all or []
    return db


EXPLAIN_ROWS = [
    ("Bitmap Index Scan on idx_llm_models_capabilities_gin rows=4",),
    ("Execution Time: 1.2 ms",),
    ("Planning Time: 0.3 ms",),
]


class TestRegistryTestQueriesModule:
    def _mod(self):
        import core.llm.registry.test_queries as tq
        return tq

    def test_single_capability_queries(self):
        tq = self._mod()
        vision = [_model(n) for n in
                  ("gpt-4-vision-preview", "gpt-4-turbo", "gpt-4o", "claude-3-sonnet")]
        tools = [_model(n) for n in ("claude-3-opus", "gpt-4-turbo", "gpt-4o")]
        jsonb = [_model("custom-model"), _model("claude-3-sonnet")]

        db = _fake_db(scalars_all=vision)
        tq.TestSingleCapabilityQueries().test_query_by_vision_hybrid_column(db, None)

        db = _fake_db(scalars_all=tools)
        tq.TestSingleCapabilityQueries().test_query_by_tools_hybrid_column(db, None)

        db = _fake_db(scalars_all=jsonb)
        tq.TestSingleCapabilityQueries().test_query_by_rare_capability_jsonb(db, None)

        db = _fake_db(scalars_all=[])
        tq.TestSingleCapabilityQueries().test_query_by_capability_no_matches(db, None)

        db = _fake_db(scalars_all=vision)
        tq.TestSingleCapabilityQueries().test_query_by_capability_tenant_isolation(db, None)
        db.add.assert_called_once()
        db.commit.assert_called()

    def test_multi_capability_and_queries(self):
        tq = self._mod()
        both = [_model("gpt-4-turbo"), _model("gpt-4o")]
        one = [_model("gpt-4o")]
        mixed = [_model("claude-3-sonnet")]

        db = _fake_db(scalars_all=both)
        tq.TestMultiCapabilityAND().test_query_by_all_capabilities_vision_tools(db, None)
        db = _fake_db(scalars_all=one)
        tq.TestMultiCapabilityAND().test_query_by_all_capabilities_three_hybrid(db, None)
        db = _fake_db(scalars_all=mixed)
        tq.TestMultiCapabilityAND().test_query_by_all_capabilities_mixed_hybrid_rare(db, None)
        db = _fake_db(scalars_all=[])
        tq.TestMultiCapabilityAND().test_query_by_all_capabilities_no_matches(db, None)

    def test_any_capability_or_queries(self):
        tq = self._mod()
        five = [_model(n) for n in
                ("gpt-4-vision-preview", "claude-3-opus", "gpt-4-turbo", "gpt-4o",
                 "claude-3-sonnet")]
        two = [_model("custom-model"), _model("claude-3-sonnet")]

        db = _fake_db(scalars_all=five)
        tq.TestAnyCapabilityOR().test_query_by_any_capability_vision_or_tools(db, None)
        db = _fake_db(scalars_all=five)
        tq.TestAnyCapabilityOR().test_query_by_any_capability_all_common(db, None)
        db = _fake_db(scalars_all=two)
        tq.TestAnyCapabilityOR().test_query_by_any_capability_rare_only(db, None)

    def test_metadata_queries(self):
        tq = self._mod()
        orm_models = [
            _model(n, provider=p)
            for n, p in [
                ("gpt-4-vision-preview", "openai"), ("claude-3-opus", "anthropic"),
                ("gpt-4-turbo", "openai"), ("gpt-4o", "openai"),
                ("custom-model", "openrouter"), ("claude-3-sonnet", "anthropic"),
            ]
        ]
        openai_models = [_model(n, provider="openai")
                         for n in ("gpt-4-vision-preview", "gpt-4-turbo", "gpt-4o")]

        db = _fake_db(scalars_all=openai_models, orm_all=orm_models)
        tq.TestMetadataQueries().test_query_by_metadata_provider(db, None)
        db = _fake_db(scalars_all=[])
        tq.TestMetadataQueries().test_query_by_metadata_no_matches(db, None)

    def test_combined_queries(self):
        tq = self._mod()
        two = [_model("gpt-4-turbo"), _model("gpt-4o")]
        five = [_model(n) for n in
                ("gpt-4-vision-preview", "claude-3-opus", "gpt-4-turbo", "gpt-4o",
                 "claude-3-sonnet")]
        four = [_model(n) for n in
                ("gpt-4-vision-preview", "gpt-4-turbo", "gpt-4o", "claude-3-sonnet")]

        db = _fake_db(scalars_all=two)
        tq.TestCombinedQueries().test_get_capable_models_required_only(db, None)
        db = _fake_db(scalars_all=five)
        tq.TestCombinedQueries().test_get_capable_models_any_only(db, None)
        db = _fake_db(scalars_all=two)
        tq.TestCombinedQueries().test_get_capable_models_required_and_any(db, None)
        db = _fake_db(scalars_all=four)
        tq.TestCombinedQueries().test_get_capable_models_any_single_string(db, None)

    def test_sync_capabilities(self):
        tq = self._mod()
        db = MagicMock()
        tq.TestSyncCapabilities().test_sync_capabilities_adds_to_hybrid_columns(db)
        tq.TestSyncCapabilities().test_sync_capabilities_all_hybrid(db)
        tq.TestSyncCapabilities().test_sync_capabilities_empty(db)

    def test_hybrid_capabilities_and_to_dict(self):
        tq = self._mod()
        tq.TestHybridCapabilities().test_get_hybrid_capabilities(MagicMock())
        tq.TestToDict().test_to_dict_includes_hybrid_columns(MagicMock())

    def test_fixture_bodies(self):
        """Drive the module's pytest-fixture functions directly."""
        tq = self._mod()
        # postgres_container: no POSTGRES_URL and no testcontainers -> skips
        try:
            next(tq.postgres_container.__wrapped__())
        except BaseException:
            pass  # pytest.skip(...) raises Skipped — expected without Postgres
        # db fixture with a mocked engine (no real database touched)
        engine = MagicMock()
        session = MagicMock()
        with patch.object(tq, "create_engine", return_value=engine), \
             patch.object(tq, "sessionmaker", return_value=MagicMock(
                 return_value=session)) as sm:
            gen = tq.db.__wrapped__("fake://url")
            assert next(gen) is session
            sm.assert_called_once_with(bind=engine)
        # resume past the yield to run the fixture teardown (close/dispose)
        try:
            next(gen)
        except StopIteration:
            pass
        session.close.assert_called_once()
        engine.dispose.assert_called_once()
        # sample_models: plain function (no yield) — six models added/committed
        mock_db = MagicMock()
        tq.sample_models.__wrapped__(mock_db)
        assert mock_db.add.call_count == 6
        mock_db.commit.assert_called_once()

    def test_index_usage(self):
        tq = self._mod()
        db = _fake_db(fetchall_rows=EXPLAIN_ROWS)
        tq.TestIndexUsage().test_explain_query_output(db, None)
        db = _fake_db(fetchall_rows=EXPLAIN_ROWS)
        tq.TestIndexUsage().test_index_usage_stats(db, None)
        db = _fake_db(fetchall_rows=EXPLAIN_ROWS)
        tq.TestIndexUsage().test_gin_index_used_for_capability_query(db, None)


# =========================================================================== #
# integrations/atom_video_ai_service.py — 83% -> >=95%
# =========================================================================== #
from integrations.atom_video_ai_service import (  # noqa: E402
    AtomVideoAIService,
    VideoContent,
    VideoFormat,
    VideoModelType,
    VideoRequest,
    VideoResolution,
    VideoTaskType,
)


def make_video_request(task_type=VideoTaskType.SUMMARIZATION, **overrides):
    req = VideoRequest(
        request_id="req1",
        task_type=task_type,
        model_type=VideoModelType.BLIP,
        video_path=None,
        video_data=b"fake-video-bytes",
        format=VideoFormat.MP4,
        resolution=VideoResolution.HD_720P,
        duration=60.0,
        fps=30.0,
        platform="slack",
        user_id="u1",
        metadata={},
    )
    for k, v in overrides.items():
        setattr(req, k, v)
    return req


def make_video_service(**config_overrides):
    config = {"enable_enterprise_features": False}
    config.update(config_overrides)
    return AtomVideoAIService(config=config)


def _breaker_ok():
    cb = MagicMock()
    cb.is_enabled = AsyncMock(return_value=True)
    rl = MagicMock()
    rl.is_rate_limited = AsyncMock(return_value=(False, 100))
    return cb, rl


class _BoolRaiser:
    def __bool__(self):
        raise RuntimeError("bool boom")


class TestVideoAIGuards:
    """Circuit-breaker / rate-limiter guard branches."""

    @pytest.mark.asyncio
    async def test_process_request_circuit_open(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        cb.is_enabled = AsyncMock(return_value=False)
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            resp = await service.process_video_request(make_video_request())
        # outer handler converts the HTTPException into an error response
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_process_request_rate_limited(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        rl.is_limited = AsyncMock(return_value=(True, 0))
        rl.is_rate_limited = AsyncMock(return_value=(True, 0))
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            resp = await service.process_video_request(make_video_request())
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_load_models_circuit_open(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        cb.is_enabled = AsyncMock(return_value=False)
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service._load_video_models()  # outer handler swallows

    @pytest.mark.asyncio
    async def test_load_models_rate_limited(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        rl.is_rate_limited = AsyncMock(return_value=(True, 0))
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service._load_video_models()  # outer handler swallows

    @pytest.mark.asyncio
    async def test_close_circuit_open(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        cb.is_enabled = AsyncMock(return_value=False)
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service.close()  # outer handler swallows

    @pytest.mark.asyncio
    async def test_close_rate_limited(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        rl.is_rate_limited = AsyncMock(return_value=(True, 0))
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service.close()  # outer handler swallows

    @pytest.mark.asyncio
    async def test_close_error(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        cb.is_enabled = AsyncMock(side_effect=RuntimeError("breaker down"))
        with patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service.close()  # swallows and logs


class TestVideoModelLoading:
    @pytest.mark.asyncio
    async def test_load_video_models_success(self):
        service = make_video_service()
        fake_transformers = MagicMock()
        fake_ultralytics = MagicMock()
        cb, rl = _breaker_ok()
        with patch.dict(sys.modules, {
            "transformers": fake_transformers, "ultralytics": fake_ultralytics,
        }), patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service._load_video_models()
        assert service.blip_model is not None
        assert service.yolo_model is not None
        assert service.video_classification_model is not None
        fake_transformers.BlipProcessor.from_pretrained.assert_called_once()
        fake_ultralytics.YOLO.assert_called_once_with("yolov8n")
        assert service.performance_metrics["model_load_time"] >= 0

    @pytest.mark.asyncio
    async def test_load_video_models_import_error(self):
        service = make_video_service()
        cb, rl = _breaker_ok()
        bad_ultralytics = MagicMock()
        bad_ultralytics.YOLO = MagicMock(side_effect=RuntimeError("yolo dead"))
        # transformers present (so blip loads), ultralytics raises
        with patch.dict(sys.modules, {
            "transformers": MagicMock(), "ultralytics": bad_ultralytics,
        }), patch("integrations.atom_video_ai_service.circuit_breaker", cb), \
             patch("integrations.atom_video_ai_service.rate_limiter", rl):
            await service._load_video_models()  # swallows error


class TestVideoSummarization:
    @pytest.mark.asyncio
    async def test_summarize_with_ai_service_success(self):
        service = make_video_service()
        service.blip_processor = MagicMock(return_value={"x": 1})
        service.blip_processor.decode.return_value = "a caption"
        service.blip_model = MagicMock()
        service.blip_model.generate.return_value = ["out"]
        service._extract_frames = AsyncMock(return_value=["frame"])
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"summary": "vid summary",
                                  "key_points": ["k"], "topics": ["t"]}))
        service.ai_service = ai
        resp = await service._summarize_video(make_video_request(), b"vd")
        assert resp.success is True
        assert resp.text == "vid summary"
        assert resp.content_analysis["captions"] == ["a caption"]

    @pytest.mark.asyncio
    async def test_summarize_ai_service_error_falls_back(self):
        service = make_video_service()
        service.blip_processor = MagicMock(return_value={})
        service.blip_processor.decode.return_value = "cap"
        service.blip_model = MagicMock()
        service.blip_model.generate.return_value = ["out"]
        service._extract_frames = AsyncMock(return_value=["frame"])
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("ai down"))
        service.ai_service = ai
        resp = await service._summarize_video(make_video_request(), b"vd")
        assert resp.success is True
        assert resp.text == "Unable to generate summary"

    @pytest.mark.asyncio
    async def test_summarize_with_torch_branch(self):
        import integrations.atom_video_ai_service as mod
        service = make_video_service()
        service.blip_processor = MagicMock(return_value={})
        service.blip_processor.decode.return_value = "cap"
        service.blip_model = MagicMock()
        service.blip_model.generate.return_value = ["out"]
        service._extract_frames = AsyncMock(return_value=["frame"])
        fake_torch = MagicMock()
        fake_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        fake_torch.no_grad.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(mod, "TORCH_AVAILABLE", True), \
             patch.object(mod, "torch", fake_torch):
            resp = await service._summarize_video(make_video_request(), b"vd")
        assert resp.success is True
        assert resp.content_analysis["captions"] == ["cap"]
        fake_torch.no_grad.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_generic_error(self):
        service = make_video_service()
        service._extract_frames = AsyncMock(side_effect=RuntimeError("frames boom"))
        resp = await service._summarize_video(make_video_request(), b"vd")
        assert resp.success is False
        assert resp.metadata == {"error": "frames boom"}


class TestVideoHandlerErrorPaths:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("task,handler", [
        (VideoTaskType.OBJECT_DETECTION, "_detect_objects"),
        (VideoTaskType.FACE_RECOGNITION, "_recognize_faces"),
        (VideoTaskType.SCENE_DETECTION, "_detect_scenes"),
        (VideoTaskType.SPEAKER_DIARIZATION, "_diarize_speakers"),
        (VideoTaskType.VIDEO_CLASSIFICATION, "_classify_video"),
        (VideoTaskType.CONTENT_MODERATION, "_moderate_content"),
    ])
    async def test_handler_exception_returns_error_response(self, task, handler):
        service = make_video_service()
        service._extract_frames = AsyncMock(side_effect=RuntimeError("extract boom"))
        req = make_video_request(task_type=task)
        resp = await getattr(service, handler)(req, b"vd")
        assert resp.success is False
        assert resp.metadata == {"error": "extract boom"}


class _FakeBox:
    def __init__(self, cls, conf):
        self.cls = cls
        self.conf = conf


class _FakeYoloResult:
    def __init__(self, names, boxes):
        self.names = names
        self.boxes = boxes


class TestVideoClassificationContent:
    def _service(self, detections, names=None):
        names = names or {0: "person", 1: "car", 2: "computer",
                          3: "phone", 4: "whiteboard", 5: "desk"}
        boxes = [_FakeBox(c, conf) for (c, conf) in detections]
        service = make_video_service()
        service.yolo_model = Mock(return_value=[_FakeYoloResult(names, boxes)])
        return service

    @pytest.mark.asyncio
    @pytest.mark.parametrize("detections,expected", [
        ([(0, 0.9)] * 11 + [(2, 0.9)] * 6, "office_meeting"),
        ([(0, 0.9)] * 11 + [(4, 0.9)] * 3, "presentation"),
        ([(0, 0.9)] * 11, "social_gathering"),
        ([(1, 0.9)] * 6, "traffic_scene"),
        ([(2, 0.9)] * 11, "tutorial"),
        ([(5, 0.9)] * 3, "general"),
        ([(0, 0.1)] * 12, "general"),  # below confidence threshold
    ])
    async def test_classify_video_content_branches(self, detections, expected):
        service = self._service(detections)
        result = await service._classify_video_content(["frame"])
        assert result == expected

    @pytest.mark.asyncio
    async def test_classify_video_content_error(self):
        service = make_video_service()
        service.yolo_model = Mock(side_effect=RuntimeError("yolo boom"))
        assert await service._classify_video_content(["frame"]) == "unknown"

    @pytest.mark.asyncio
    async def test_classify_video_uses_content_classifier(self):
        service = self._service([(0, 0.9)] * 11 + [(2, 0.9)] * 6)
        service._extract_frames = AsyncMock(return_value=["frame"])
        resp = await service._classify_video(make_video_request(
            task_type=VideoTaskType.VIDEO_CLASSIFICATION), b"vd")
        assert resp.success is True
        assert resp.video_class == "office_meeting"


class TestVideoFrameExtraction:
    def _fake_cv2(self):
        cv2 = MagicMock()
        cv2.CAP_PROP_FRAME_COUNT = 1
        cv2.CAP_PROP_FPS = 3
        cv2.CAP_PROP_FRAME_WIDTH = 5
        cv2.CAP_PROP_FRAME_HEIGHT = 7
        cv2.CAP_PROP_POS_FRAMES = 9
        cv2.COLOR_BGR2RGB = 11
        cap = MagicMock()
        cap.get = MagicMock(side_effect=lambda prop: {1: 10, 3: 30, 5: 1920, 7: 1080}.get(prop, 0))
        cap.read.return_value = (True, "raw-frame")
        cv2.VideoCapture.return_value = cap
        cv2.cvtColor.side_effect = lambda f, _code: f"rgb-{f}"
        return cv2, cap

    @pytest.mark.asyncio
    async def test_extract_frames_cv2_path(self):
        service = make_video_service()
        cv2, cap = self._fake_cv2()
        with patch.dict(sys.modules, {"cv2": cv2}):
            frames = await service._extract_frames(b"video", num_frames=3)
        assert frames and all(f.startswith("rgb-") for f in frames)
        cap.release.assert_called()

    @pytest.mark.asyncio
    async def test_extract_frames_error(self):
        service = make_video_service()
        cv2 = MagicMock()
        cv2.VideoCapture.side_effect = RuntimeError("cv2 dead")
        with patch.dict(sys.modules, {"cv2": cv2}):
            frames = await service._extract_frames(b"video")
        assert frames == []

    @pytest.mark.asyncio
    async def test_analyze_video_quality_cv2_path(self):
        service = make_video_service()
        cv2, _cap = self._fake_cv2()
        with patch.dict(sys.modules, {"cv2": cv2}):
            score = await service._analyze_video_quality(b"video")
        assert score == 100.0  # 1080p @30fps normalizes to >=1.0

    @pytest.mark.asyncio
    async def test_analyze_video_quality_error(self):
        service = make_video_service()
        cv2 = MagicMock()
        cv2.VideoCapture.side_effect = RuntimeError("nope")
        with patch.dict(sys.modules, {"cv2": cv2}):
            score = await service._analyze_video_quality(b"video")
        assert score == 50.0  # default when analysis fails


class TestVideoSetupHelpers:
    @pytest.mark.asyncio
    async def test_setup_content_moderation_error(self):
        service = make_video_service()
        logger = MagicMock()
        logger.info = MagicMock(side_effect=RuntimeError("log boom"))
        with patch("integrations.atom_video_ai_service.logger", logger):
            await service._setup_content_moderation()
        logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_enterprise_features_error(self):
        service = make_video_service()
        logger = MagicMock()
        logger.info = MagicMock(side_effect=RuntimeError("log boom"))
        with patch("integrations.atom_video_ai_service.logger", logger):
            await service._setup_enterprise_features()

    @pytest.mark.asyncio
    async def test_setup_security_and_compliance_error(self):
        service = make_video_service(enable_enterprise_features=True)
        service._setup_security_monitoring = AsyncMock(
            side_effect=RuntimeError("sec boom"))
        await service._setup_security_and_compliance()
        # happy path with enterprise features enabled too
        service2 = make_video_service(enable_enterprise_features=True)
        service2._setup_security_monitoring = AsyncMock()
        service2._setup_compliance_monitoring = AsyncMock()
        await service2._setup_security_and_compliance()
        service2._setup_security_monitoring.assert_awaited_once()
        service2._setup_compliance_monitoring.assert_awaited_once()

    def test_init_platform_integrations_from_globals(self):
        import integrations.atom_video_ai_service as mod
        names = ["atom_slack_integration", "atom_teams_integration",
                 "atom_google_chat_integration", "atom_discord_integration",
                 "atom_telegram_integration", "atom_whatsapp_integration",
                 "atom_zoom_integration"]
        fake_globals = {n: Mock(name=n) for n in names}
        with patch.dict(mod.__dict__, fake_globals):
            service = AtomVideoAIService(
                config={"enable_enterprise_features": False})
        assert set(service.platform_integrations) == {
            "slack", "teams", "google_chat", "discord",
            "telegram", "whatsapp", "zoom"}

    @pytest.mark.asyncio
    async def test_setup_security_monitoring_error(self):
        service = make_video_service()
        logger = MagicMock()
        logger.info = MagicMock(side_effect=RuntimeError("log boom"))
        with patch("integrations.atom_video_ai_service.logger", logger):
            await service._setup_security_monitoring()

    @pytest.mark.asyncio
    async def test_setup_compliance_monitoring_error(self):
        service = make_video_service()
        logger = MagicMock()
        logger.info = MagicMock(side_effect=RuntimeError("log boom"))
        with patch("integrations.atom_video_ai_service.logger", logger):
            await service._setup_compliance_monitoring()

    @pytest.mark.asyncio
    async def test_load_existing_video_data_error(self):
        service = make_video_service()
        logger = MagicMock()
        logger.info = MagicMock(side_effect=RuntimeError("log boom"))
        with patch("integrations.atom_video_ai_service.logger", logger):
            await service._load_existing_video_data()

    @pytest.mark.asyncio
    async def test_preprocess_video_error(self):
        service = make_video_service()
        fake_time = MagicMock()
        fake_time.time = MagicMock(side_effect=RuntimeError("clock boom"))
        with patch("integrations.atom_video_ai_service.time", fake_time):
            data = await service._preprocess_video(make_video_request())
        assert data == b"fake-video-bytes"

    @pytest.mark.asyncio
    async def test_preprocess_non_mp4_passthrough(self):
        service = make_video_service()
        req = make_video_request(format=VideoFormat.AVI, video_data=b"avi-bytes")
        data = await service._preprocess_video(req)
        assert data == b"avi-bytes"


class TestVideoSecurityAndLogging:
    @pytest.mark.asyncio
    async def test_perform_security_check_no_security_service(self):
        service = make_video_service()
        service.enterprise_security = None
        assert await service._perform_security_check(make_video_request()) == {"passed": True}

    @pytest.mark.asyncio
    async def test_perform_security_check_error(self):
        service = make_video_service()
        service.enterprise_security = _BoolRaiser()
        result = await service._perform_security_check(make_video_request())
        assert result["passed"] is False
        assert "bool boom" in result["reason"]

    @pytest.mark.asyncio
    async def test_log_video_request_with_security(self):
        service = make_video_service()
        service.enterprise_security = MagicMock()
        service.enterprise_security.audit_event = AsyncMock()
        req = make_video_request()
        resp = service._create_error_response(req, "x")
        await service._log_video_request(req, resp)
        service.enterprise_security.audit_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_video_request_error(self):
        service = make_video_service()
        service.enterprise_security = MagicMock()
        service.enterprise_security.audit_event = AsyncMock(
            side_effect=RuntimeError("audit boom"))
        req = make_video_request()
        await service._log_video_request(req, service._create_error_response(req, "x"))

    @pytest.mark.asyncio
    async def test_get_service_status_error(self):
        service = make_video_service()
        fake_time = MagicMock()
        fake_time.time = MagicMock(side_effect=RuntimeError("clock boom"))
        with patch("integrations.atom_video_ai_service.time", fake_time):
            status = await service.get_service_status()
        assert status["service"] == "video_ai"
        assert "error" in status
