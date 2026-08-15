"""Coverage wave 64l — core/agent_world_model.py remaining 15 lines (98% → 100%,
TDD, mocked lancedb/SessionLocal — no network, no real DB writes).

Wave 38 (test_covpush_w38_world_model.py) + wave 20/25 suites left exactly these
uncovered: ``_ensure_tables`` when the handler exposes no underlying db
(``db.db is None``), ``get_business_fact`` dict/other-type metadata rows,
``get_fact_by_id`` exception, ``archive_episode_to_cold_storage`` exception,
``recommend_skills_for_task`` event-loop RuntimeError fallback, and the canvas
family edges (non-success outcome skip, limit break,
``get_canvas_type_preferences`` with a task_type filter).
"""
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pandas as pd
import pytest

from core.agent_world_model import WorldModelService


def make_service(**kw):
    handler = Mock()
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=["agent_experience", "business_facts"])
    handler.search = Mock(return_value=[])
    handler.get_table = Mock(return_value=None)
    with patch("core.agent_world_model.get_lancedb_handler", return_value=handler):
        svc = WorldModelService(workspace_id=kw.pop("workspace_id", "default"))
    svc.db = kw.pop("db", handler)
    for k, v in kw.items():
        setattr(svc, k, v)
    return svc


def make_result(metadata=None, text="", score=0.5):
    return {"metadata": metadata or {}, "text": text, "score": score}


def success_meta(agent_id="a1", **overrides):
    meta = {
        "agent_id": agent_id,
        "task_type": "analysis",
        "input_summary": "in",
        "outcome": "success",
        "learnings": "learned",
        "confidence_score": 0.8,
        "feedback_score": 0.7,
        "artifacts": [],
        "step_efficiency": 1.0,
        "trace": {},
        "agent_role": "Finance",
        "specialty": None,
        "timestamp": "2026-08-01T12:00:00+00:00",
    }
    meta.update(overrides)
    return meta


class TestEnsureTables:
    def test_db_none_returns_early(self):
        handler = Mock()
        handler.db = None
        with patch("core.agent_world_model.get_lancedb_handler", return_value=handler):
            svc = WorldModelService("w1")
        assert svc.table_name == "agent_experience"
        assert svc.facts_table_name == "business_facts"
        handler.create_table.assert_not_called()


class TestGetBusinessFactMetadataBranches:
    async def test_dict_metadata_row(self):
        svc = make_service()
        table = Mock()
        row = {
            "id": "fact-1",
            "text": "Fact: quarterly revenue",
            "metadata": {
                "fact": "quarterly revenue up",
                "citations": ["r1"],
                "reason": "audited",
                "source_agent_id": "a1",
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_verified": "2026-01-02T00:00:00+00:00",
                "verification_status": "verified",
                "extra": "kept",
            },
        }
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame([row])
        )
        svc.db.get_table = Mock(return_value=table)
        result = await svc.get_business_fact("fact-1")
        assert result is not None
        assert result.id == "fact-1"
        assert result.fact == "quarterly revenue up"
        assert result.verification_status == "verified"
        assert result.citations == ["r1"]
        assert result.metadata["extra"] == "kept"

    async def test_non_dict_non_str_metadata_uses_empty(self):
        svc = make_service()
        table = Mock()
        row = {
            "id": "fact-1",
            "text": "Fact: x",
            "metadata": None,  # pandas stores as NaN → neither dict nor str
        }
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame([row])
        )
        svc.db.get_table = Mock(return_value=table)
        result = await svc.get_business_fact("fact-1")
        # meta={} → fact built from row text; created_at/last_verified default
        # to now() instead of crashing fromisoformat(None) → returns the fact
        assert result is not None
        assert result.fact == "x"
        assert result.created_at is not None


class TestGetFactById:
    async def test_search_exception_returns_none(self):
        svc = make_service()
        svc.db.search.side_effect = RuntimeError("lancedb down")
        result = await svc.get_fact_by_id("f9")
        assert result is None


class TestArchiveEpisode:
    async def test_sync_exception_returns_false(self):
        svc = make_service()
        with patch.object(
            svc, "sync_episode_to_lancedb",
            new=AsyncMock(side_effect=RuntimeError("lancedb down")),
        ):
            result = await svc.archive_episode_to_cold_storage(
                episode_id="e9", agent_id="a1", tenant_id="t1",
                task_description="x", outcome="success", learnings="y",
                agent_role="Ops", maturity_at_time="INTERN",
            )
        assert result is False


class TestRecommendSkillsEventLoop:
    def test_get_event_loop_runtime_error_creates_new_loop(self):
        svc = make_service()
        db = Mock()
        db.close = Mock()
        agent = Mock()
        agent.category = "Finance"
        db.query.return_value.filter.return_value.first.return_value = agent
        try:
            with patch("core.agent_world_model.SessionLocal", return_value=db), \
                 patch.object(svc, "recall_episodes", new=AsyncMock(return_value=[])), \
                 patch("asyncio.get_event_loop",
                       side_effect=RuntimeError("no current loop")):
                result = svc.recommend_skills_for_task("task", "a1", "t1")
            assert result == []
            assert db.close.called
        finally:
            asyncio.set_event_loop(None)


class TestRecallExperiencesWithCanvas:
    async def test_skips_non_success_outcomes_and_breaks_at_limit(self):
        svc = make_service()
        svc.db.search.return_value = [
            make_result(metadata=success_meta(outcome="failed")),
            make_result(metadata=success_meta()),
            make_result(metadata=success_meta()),
            make_result(metadata=success_meta()),
        ]
        out = await svc.recall_experiences_with_canvas("a1", "task", limit=2)
        assert len(out) == 2
        assert all(e.outcome == "success" for e in out)
        assert svc.db.search.call_args[1]["limit"] == 4


class TestGetCanvasTypePreferences:
    async def test_task_type_appended_to_query(self):
        svc = make_service()
        docs_meta = success_meta(
            outcome="failure", canvas_types=["docs"], engagement_time_seconds=5.0)
        docs_meta.pop("feedback_score")  # no feedback recorded → key absent
        svc.db.search.return_value = [
            make_result(metadata=success_meta(
                canvas_types=["sheets"], engagement_time_seconds=10.0,
                feedback_score=0.8)),
            make_result(metadata=docs_meta),
            make_result(metadata=success_meta(agent_id="other", canvas_types=["email"])),
        ]
        prefs = await svc.get_canvas_type_preferences("a1", task_type="report")
        assert svc.db.search.call_args[1]["query"] == "agent_a1 report"
        assert prefs["sheets"]["count"] == 1
        assert prefs["sheets"]["success_rate"] == 1.0
        assert prefs["sheets"]["avg_engagement"] == 10.0
        assert prefs["sheets"]["avg_feedback_score"] == 0.8
        assert prefs["docs"]["success_rate"] == 0.0
        assert prefs["docs"]["avg_engagement"] == 5.0
        assert prefs["docs"]["avg_feedback_score"] == 0.0
        assert "email" not in prefs
