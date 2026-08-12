"""Coverage wave 40 — core/episode_service.py canvas-metadata + edge paths (TDD).

Closes the remaining branches: canvas helpers (lazy init, workspace
guard), LanceDB connect-fail, canvas-metadata extraction (all paths:
no execution, session-audit fallbacks, canvas missing, full metadata
with artifacts/comments/audits/semantic summary, summary-failure
tolerance), episode creation from execution (not-found/agent-missing/
activity-publisher paths), step-efficiency cycle skips, feedback
capability-tracking success, and progressive recall agent check —
no LLM calls (summary service mocked), zero spend.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.episode_service import (
    DetailLevel,
    EpisodeService,
    _get_canvas_context_provider,
    _get_canvas_summary_service,
)


def make_service(**kw):
    db = MagicMock()
    for k, v in kw.pop("db_overrides", {}).items():
        setattr(db, k, v)
    return EpisodeService(db, **kw)


def make_execution(**kw):
    defaults = dict(
        id="ex-1", agent_id="ag-1", tenant_id="t-1",
        metadata_json=None, session_id=None,
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc) - __import__(
            "datetime").timedelta(minutes=5),
        completed_at=datetime.now(timezone.utc),
        human_intervention_count=1, step_efficiency=0.9,
        confidence_score=0.8)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestCanvasHelpers:
    def test_get_canvas_context_provider(self):
        from core.episode_service import _canvas_context_provider
        _canvas_context_provider = None
        provider = MagicMock()
        with patch("core.canvas_context_provider.get_canvas_provider",
                   return_value=provider):
            assert _get_canvas_context_provider() is provider
            assert _get_canvas_context_provider() is provider  # cached
        _canvas_context_provider = None

    def test_get_canvas_summary_service(self):
        from core.episode_service import _canvas_summary_service
        _canvas_summary_service = None
        svc = MagicMock()
        with patch("core.llm.canvas_summary_service.CanvasSummaryService",
                   return_value=svc):
            assert _get_canvas_summary_service("ws-1") is svc
            assert _get_canvas_summary_service("ws-1") is svc  # cached
        _canvas_summary_service = None

    def test_get_canvas_summary_service_rejects_default(self):
        with pytest.raises(ValueError, match="cannot be 'default'"):
            _get_canvas_summary_service("default")

    def test_get_lancedb_connect_fail(self):
        svc = make_service()
        lancedb = MagicMock()
        lancedb.connect.return_value = False
        with patch("core.episode_service.LanceDBService",
                   return_value=lancedb), \
             patch.object(svc, "_get_embedding_dimension",
                          return_value=384):
            result = svc._get_lancedb()
        assert result is None


class TestExtractCanvasMetadata:
    async def test_no_execution(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        assert await svc._extract_canvas_metadata("ghost") == {}

    async def test_no_metadata_session_fallback(self):
        db = MagicMock()
        execution = make_execution(metadata_json=None, session_id="s-1")
        db.query.return_value.filter.return_value.first.return_value = execution
        audit = SimpleNamespace(
            id="a1", canvas_id="cv-1", canvas_type="chart", action_type="submit",
            details_json={"form": 1}, created_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [audit, audit]
        svc = EpisodeService(db)
        meta = await svc._extract_canvas_metadata("ex-1")
        assert meta["canvas_action_ids"] == ["a1", "a1"]
        assert "Canvas interactions" in meta["presentation_summary"]

    async def test_no_metadata_no_session(self):
        db = MagicMock()
        execution = make_execution(metadata_json=None, session_id=None)
        db.query.return_value.filter.return_value.first.return_value = execution
        svc = EpisodeService(db)
        assert await svc._extract_canvas_metadata("ex-1") == {}

    async def test_canvas_id_missing_session_fallback(self):
        db = MagicMock()
        execution = make_execution(metadata_json={}, session_id="s-1")
        db.query.return_value.filter.return_value.first.return_value = execution
        audit = SimpleNamespace(
            id="a2", canvas_id="cv-9", canvas_type="markdown", action_type="create",
            details_json={}, created_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [audit]
        svc = EpisodeService(db)
        meta = await svc._extract_canvas_metadata("ex-1")
        assert meta["canvas_action_ids"] == ["a2"]

    async def test_canvas_not_found(self):
        db = MagicMock()
        execution = make_execution(metadata_json={"canvas_id": "cv-1"})
        db.query.return_value.filter.return_value.first.side_effect = [execution, None]
        svc = EpisodeService(db)
        meta = await svc._extract_canvas_metadata("ex-1")
        assert meta == {"canvas_id": "cv-1"}

    async def test_full_metadata(self):
        db = MagicMock()
        execution = make_execution(metadata_json={"canvas_id": "cv-1"})
        db.query.return_value.filter.return_value.first.side_effect = [execution, SimpleNamespace(
            id="cv-1", canvas_type="chart", tenant_id="t-1")]
        db.query.return_value.filter.return_value.count.return_value = 3
        audit = SimpleNamespace(id="a1", canvas_id="cv-1",
                                created_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [audit]
        provider = MagicMock()
        provider.get_canvas.return_value = SimpleNamespace(
            data={"nodes": []})
        summary_svc = MagicMock()
        summary_svc.generate_summary = AsyncMock(return_value="semantic summary")
        svc = EpisodeService(db)
        with patch("core.episode_service._get_canvas_context_provider",
                   return_value=provider), \
             patch("core.episode_service._get_canvas_summary_service",
                   return_value=summary_svc):
            meta = await svc._extract_canvas_metadata("ex-1", task_description="t")
        assert meta["canvas_id"] == "cv-1"
        assert meta["canvas_artifact_count"] == 3
        assert meta["canvas_type"] == "chart"
        assert meta["presentation_summary"] == "semantic summary"
        summary_svc.generate_summary.assert_called_once()

    async def test_semantic_summary_failure_tolerated(self):
        db = MagicMock()
        execution = make_execution(metadata_json={"canvas_id": "cv-1"})
        db.query.return_value.filter.return_value.first.side_effect = [execution, SimpleNamespace(
            id="cv-1", canvas_type="chart", tenant_id="t-1")]
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        provider = MagicMock()
        provider.get_canvas.return_value = SimpleNamespace(data={})
        summary_svc = MagicMock()
        summary_svc.generate_summary = AsyncMock(side_effect=RuntimeError("llm down"))
        svc = EpisodeService(db)
        with patch("core.episode_service._get_canvas_context_provider",
                   return_value=provider), \
             patch("core.episode_service._get_canvas_summary_service",
                   return_value=summary_svc):
            meta = await svc._extract_canvas_metadata("ex-1")
        assert meta["presentation_summary"] is None

    async def test_outer_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = EpisodeService(db)
        assert await svc._extract_canvas_metadata("ex-1") == {}


class TestCreateEpisodeFromExecution:
    async def test_execution_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.create_episode_from_execution("ghost", "t", "success", True)

    async def test_agent_not_found(self):
        db = MagicMock()
        execution = make_execution()
        db.query.return_value.filter.return_value.first.side_effect = [execution, None]
        svc = EpisodeService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.create_episode_from_execution("ex-1", "t", "success", True)

    async def test_activity_publisher_paths(self):
        db = MagicMock()
        execution = make_execution()
        agent = SimpleNamespace(id="ag-1", status="intern",
                                confidence_score=0.8)
        db.query.return_value.filter.return_value.first.side_effect = [execution, agent]
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        publisher = MagicMock()
        publisher.publish_episode_recording = MagicMock()
        episode = MagicMock(id="ep-1")
        svc = EpisodeService(db, activity_publisher=publisher)
        with patch.object(svc, "_extract_canvas_metadata",
                          new=AsyncMock(return_value={})), \
             patch("core.episode_service.AgentEpisode",
                   lambda **kw: episode), \
             patch.object(svc, "_calculate_constitutional_score",
                          return_value=1.0), \
             patch.object(svc, "_get_embedding_dimension",
                          return_value=384), \
             patch.object(svc, "_get_lancedb", return_value=None):
            result = await svc.create_episode_from_execution(
                "ex-1", "task", "success", True,
                constitutional_violations=[{"severity": "low"}])
        assert result is episode
        assert publisher.publish_episode_recording.call_count == 2

    async def test_activity_publisher_failure_tolerated(self):
        db = MagicMock()
        execution = make_execution()
        agent = SimpleNamespace(id="ag-1", status="intern",
                                confidence_score=0.8)
        db.query.return_value.filter.return_value.first.side_effect = [execution, agent]
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        publisher = MagicMock()
        publisher.publish_episode_recording.side_effect = RuntimeError("publisher down")
        episode = MagicMock(id="ep-1")
        svc = EpisodeService(db, activity_publisher=publisher)
        with patch.object(svc, "_extract_canvas_metadata",
                          new=AsyncMock(return_value={})), \
             patch("core.episode_service.AgentEpisode",
                   lambda **kw: episode), \
             patch.object(svc, "_calculate_constitutional_score",
                          return_value=1.0), \
             patch.object(svc, "_get_lancedb", return_value=None):
            result = await svc.create_episode_from_execution(
                "ex-1", "task", "success", True)
        assert result is episode


class TestStepEfficiencyCycles:
    def test_cycles_skipped(self):
        db = MagicMock()
        steps = [
            SimpleNamespace(step_type="thought"),
            SimpleNamespace(step_type="observation"),  # thought→observation skip
            SimpleNamespace(step_type="thought"),
            SimpleNamespace(step_type="action"),
            SimpleNamespace(step_type="observation"),  # thought→action→observation skip
        ]
        db.query.return_value.filter.return_value.all.return_value = steps
        svc = EpisodeService(db)
        assert svc._calculate_step_efficiency("ex-1") == 1.0


class TestFeedbackCapabilitySuccess:
    def test_capability_tracking_success(self):
        db = MagicMock()
        episode = SimpleNamespace(metadata_json={}, tenant_id="t-1",
                                  agent_id="ag-1")
        db.query.return_value.filter.return_value.first.return_value = episode
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        feedback = SimpleNamespace(id="fb-1")
        grad = MagicMock()
        grad.record_capability_usage = MagicMock()
        svc = EpisodeService(db)
        with patch("core.models.EpisodeFeedback", lambda **kw: feedback), \
             patch("core.capability_graduation_service.CapabilityGraduationService",
                   return_value=grad), \
             patch.object(svc, "_sync_feedback_to_lancedb", new=AsyncMock()):
            fb_id = svc.update_episode_feedback(
                "ep-1", 0.9, capability_domain="data_analysis",
                capability_name="analysis")
        assert fb_id == "fb-1"
        grad.record_capability_usage.assert_called_once()


class TestProgressiveRecallAgentCheck:
    async def test_agent_not_found(self):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        svc = EpisodeService(db)
        result = await svc.recall_episodes_with_detail(
            "ghost", "t-1", DetailLevel.SUMMARY)
        assert result == []

    async def test_agent_found_uses_progressive_queries(self):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = "ag-1"
        row = SimpleNamespace(_mapping={"id": "ep-1", "task_description": "T",
                                        "outcome": "success"})
        db.execute.return_value.fetchall.return_value = [row]
        svc = EpisodeService(db)
        result = await svc.recall_episodes_with_detail(
            "ag-1", "t-1", DetailLevel.SUMMARY)
        assert result[0]["id"] == "ep-1"
