"""Coverage wave 38 — core/agent_world_model.py recall + skill paths (TDD, mocked db).

Drives the semantic episode recall (scoring, canvas/feedback boosts,
filters, sorting), detail-level experience recall (agent-id path, FULL
semantic, SUMMARY/STANDARD PostgreSQL), episode→experience formatting,
skill recommendation (recall → stats → ranking, missing agent / no
skill episodes), successful-skill sets and the hot-formula fallback in
recall_experiences — no LLM, zero spend.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent_world_model import DetailLevel, WorldModelService


def make_service(**kw):
    db = MagicMock()
    with patch("core.agent_world_model.get_lancedb_handler",
               return_value=db):
        svc = WorldModelService(workspace_id=kw.pop("workspace_id", "default"))
    svc.db = kw.pop("db", db)
    for k, v in kw.items():
        setattr(svc, k, v)
    return svc


def make_result(metadata=None, text="", score=0.5):
    return {"metadata": metadata or {}, "text": text, "score": score}


class TestRecallEpisodes:
    async def test_full_scoring_with_boosts(self):
        svc = make_service()
        svc.db.search.return_value = [
            make_result(
                metadata={"agent_role": "Finance", "agent_id": "ag-1",
                          "type": "episode", "episode_id": "ep-1",
                          "outcome": "success", "canvas_id": "cv-1",
                          "feedback_score": 0.8},
                text="Episode: Reconciled books\nOutcome: success\nLearnings: Use SOQL\n",
                score=0.7),
            make_result(
                metadata={"agent_role": "Finance", "agent_id": "ag-1",
                          "type": "episode", "episode_id": "ep-2",
                          "outcome": "failure", "canvas_id": "cv-9",
                          "feedback_score": -0.8},
                text="Episode: Other\nOutcome: failure",
                score=0.6),
            make_result(
                metadata={"agent_role": "Sales", "agent_id": "ag-1",
                          "type": "episode", "episode_id": "ep-3"},
                score=0.9),  # wrong role → filtered
            make_result(
                metadata={"agent_role": "Finance", "agent_id": "ag-2",
                          "type": "episode", "episode_id": "ep-4"},
                score=0.8),  # wrong agent → filtered
            make_result(
                metadata={"agent_role": "Finance", "agent_id": "ag-1",
                          "type": "formula", "episode_id": "ep-5"},
                score=0.8),  # wrong type → filtered
        ]
        episodes = await svc.recall_episodes(
            task_description="reconcile", agent_role="Finance",
            agent_id="ag-1", canvas_id="cv-1", limit=5)
        assert len(episodes) == 2
        ep1 = episodes[0]  # 0.7 + 0.3 + 0.2 = 1.2
        assert ep1["final_score"] == 1.2
        assert ep1["canvas_boost"] == 0.3
        assert ep1["feedback_boost"] == 0.2
        assert ep1["learnings"] == "Use SOQL"
        assert ep1["similarity_score"] == 0.7
        ep2 = episodes[1]  # 0.6 - 0.05 - 0.3 = 0.25
        assert ep2["final_score"] == pytest.approx(0.25)
        assert ep2["canvas_boost"] == -0.05
        assert ep2["feedback_boost"] == -0.3

    async def test_min_feedback_filter(self):
        svc = make_service()
        svc.db.search.return_value = [
            make_result(metadata={"agent_role": "F", "type": "episode",
                                  "episode_id": "e1", "feedback_score": 0.4}),
            make_result(metadata={"agent_role": "F", "type": "episode",
                                  "episode_id": "e2", "feedback_score": 0.9}),
            make_result(metadata={"agent_role": "F", "type": "episode",
                                  "episode_id": "e3"}),
        ]
        episodes = await svc.recall_episodes(
            task_description="t", agent_role="F", min_feedback_score=0.5,
            limit=5)
        assert [e["episode_id"] for e in episodes] == ["e2"]

    async def test_limit_applied_after_sort(self):
        svc = make_service()
        svc.db.search.return_value = [
            make_result(metadata={"agent_role": "F", "type": "episode",
                                  "episode_id": f"e{i}"}, score=0.1 * i)
            for i in range(6)
        ]
        episodes = await svc.recall_episodes(
            task_description="t", agent_role="F", limit=3)
        assert len(episodes) == 3

    async def test_no_learnings_key(self):
        svc = make_service()
        svc.db.search.return_value = [
            make_result(metadata={"agent_role": "F", "type": "episode",
                                  "episode_id": "e1"},
                        text="Episode: X\nOutcome: success")]  # no "Learnings:"
        episodes = await svc.recall_episodes(
            task_description="t", agent_role="F", limit=5)
        assert episodes[0]["learnings"] == ""

    async def test_exception_returns_empty(self):
        svc = make_service()
        svc.db.search.side_effect = RuntimeError("lancedb down")
        assert await svc.recall_episodes(
            task_description="t", agent_role="F", limit=5) == []


class TestRecallExperiencesWithDetail:
    async def test_agent_id_path(self):
        svc = make_service()
        ep_service = MagicMock()
        ep_service.recall_episodes_with_detail = AsyncMock(return_value=[
            {"id": "ep-1", "task_description": "Task", "presentation_summary": "S",
             "outcome": "success"}])
        with patch("core.episode_service.EpisodeService",
                   return_value=ep_service):
            experiences = await svc.recall_experiences_with_detail(
                "t-1", "Finance", "task", DetailLevel.SUMMARY,
                agent_id="ag-1", limit=3)
        assert experiences[0]["episode_id"] == "ep-1"
        assert experiences[0]["detail_level"] == "summary"

    async def test_full_detail_uses_semantic(self):
        svc = make_service()
        with patch.object(svc, "recall_episodes",
                          new=AsyncMock(return_value=[{"episode_id": "e1"}])) as rec:
            experiences = await svc.recall_experiences_with_detail(
                "t-1", "Finance", "task", DetailLevel.FULL, limit=3)
        assert experiences == [{"episode_id": "e1"}]
        rec.assert_called_once()

    async def test_summary_and_standard_pg(self):
        for level in [DetailLevel.SUMMARY, DetailLevel.STANDARD]:
            svc = make_service()
            row = SimpleNamespace(_mapping={
                "id": "ep-1", "agent_id": "ag-1", "task_description": "T",
                "canvas_type": None, "presentation_summary": "S",
                "outcome": "success", "success": True,
                "constitutional_score": 0.9, "started_at": "2026-01-01",
                "visual_elements": "[]", "critical_data_points": "[]"})
            result = MagicMock()
            result.fetchall.return_value = [row]
            pg = MagicMock()
            pg.execute.return_value = result
            pg.close = MagicMock()
            with patch("core.database.SessionLocal",
                       return_value=pg) as sl:
                experiences = await svc.recall_experiences_with_detail(
                    "t-1", "Finance", "task", level, limit=3)
            assert len(experiences) == 1
            assert experiences[0]["id"] == "ep-1"
            if level == DetailLevel.STANDARD:
                assert "visual_elements" in experiences[0]
            sl.assert_called_once()

    async def test_format_episodes(self):
        svc = make_service()
        episodes = [{"id": "e1", "task_description": "Task here",
                     "presentation_summary": "S", "outcome": "success",
                     "visual_elements": "v", "critical_data_points": "c",
                     "audit_trail": "a"}]
        summary = svc._format_episodes_as_experiences(episodes, DetailLevel.SUMMARY)
        assert summary[0]["task_type"] == "Task here"[:50]
        assert summary[0]["detail_level"] == "summary"
        standard = svc._format_episodes_as_experiences(episodes, DetailLevel.STANDARD)
        assert standard[0]["visual_elements"] == "v"
        full = svc._format_episodes_as_experiences(episodes, DetailLevel.FULL)
        assert full[0]["audit_trail"] == "a"


class TestRecommendSkills:
    def test_agent_not_found(self):
        svc = make_service()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.close = MagicMock()
        with patch("core.agent_world_model.SessionLocal", return_value=db):
            assert svc.recommend_skills_for_task("task", "ghost", "t-1") == []

    def test_no_skill_episodes(self):
        svc = make_service()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            category="Finance")
        db.close = MagicMock()
        with patch("core.agent_world_model.SessionLocal", return_value=db), \
             patch.object(svc, "recall_episodes",
                          new=AsyncMock(return_value=[
                              {"metadata": {"skill_type": "other"},
                               "episode_id": "e1"}])):
            assert svc.recommend_skills_for_task("task", "ag-1", "t-1") == []

    def test_full_recommendation(self):
        svc = make_service()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            category="Finance")
        episode_rows = [
            SimpleNamespace(success=True, completed_at=datetime.now(timezone.utc)),
            SimpleNamespace(success=False, completed_at=None),
        ]
        db.query.return_value.filter.return_value.all.return_value = episode_rows
        skill = SimpleNamespace(name="web_search")
        db.query.return_value.filter.return_value.first.side_effect = [SimpleNamespace(
            category="Finance"), skill]
        db.close = MagicMock()
        similar = [
            {"metadata": {"skill_type": "openclaw", "skill_id": "s1"},
             "episode_id": "e1", "outcome": "success",
             "final_score": 0.9},
            {"metadata": {"skill_type": "openclaw", "skill_id": "s1"},
             "episode_id": "e2", "outcome": "failure",
             "final_score": 0.5},
        ]
        with patch("core.agent_world_model.SessionLocal", return_value=db), \
             patch.object(svc, "recall_episodes",
                          new=AsyncMock(return_value=similar)):
            recommendations = svc.recommend_skills_for_task("task", "ag-1", "t-1")
        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.skill_id == "s1"
        assert rec.skill_name == "web_search"
        assert rec.success_rate == 0.5
        assert rec.execution_count == 2
        assert "similarity" in rec.reason

    def test_recall_failure_tolerated(self):
        svc = make_service()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            category="Finance")
        db.close = MagicMock()
        with patch("core.agent_world_model.SessionLocal", return_value=db), \
             patch.object(svc, "recall_episodes",
                          new=AsyncMock(side_effect=RuntimeError("recall down"))):
            assert svc.recommend_skills_for_task("task", "ag-1", "t-1") == []

    def test_outer_exception(self):
        svc = make_service()
        with patch("core.agent_world_model.SessionLocal",
                   side_effect=RuntimeError("db down")):
            assert svc.recommend_skills_for_task("task", "ag-1", "t-1") == []


class TestSuccessfulSkills:
    def test_returns_skill_ids(self):
        svc = make_service()
        db = MagicMock()
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(metadata_json={"skill_id": "s1"}),
            SimpleNamespace(metadata_json={"skill_id": "s2"}),
            SimpleNamespace(metadata_json={"skill_id": "s1"}),
            SimpleNamespace(metadata_json={}),
            SimpleNamespace(metadata_json=None),
        ]
        db.close = MagicMock()
        with patch("core.agent_world_model.SessionLocal", return_value=db):
            skills = svc.get_successful_skills_for_agent("ag-1", "t-1")
        assert skills == {"s1", "s2"}

    def test_exception(self):
        svc = make_service()
        with patch("core.agent_world_model.SessionLocal",
                   side_effect=RuntimeError("db down")):
            assert svc.get_successful_skills_for_agent("ag-1", "t-1") == set()


class TestHotFormulaFallback:
    async def test_hot_formulas_appended(self):
        svc = make_service()
        db = MagicMock()
        formula = SimpleNamespace(
            id="f1", name="Profit", expression="=A-B", domain="finance",
            description="d", parameters={})
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [formula]
        db.close = MagicMock()
        with patch("core.agent_world_model.SessionLocal", return_value=db):
            result = await svc.recall_experiences(
                agent=SimpleNamespace(id="ag-1", category="finance",
                                      llm_provider=None, llm_model=None),
                current_task_description="task",
                limit=10,
            )
        hot = [f for f in result.get("formulas", []) if f.get("type") == "formula_hot"]
        assert len(hot) == 1
        assert hot[0]["id"] == "f1"

    async def test_conversation_recall(self):
        svc = make_service()
        db = MagicMock()
        msg = SimpleNamespace(role="user", content="hello",
                              created_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [msg]
        db.close = MagicMock()
        with patch("core.agent_world_model.SessionLocal", return_value=db):
            result = await svc.recall_experiences(
                agent=SimpleNamespace(id="ag-1", category="finance",
                                      llm_provider=None, llm_model=None),
                current_task_description="task",
                limit=10,
            )
        assert len(result.get("conversations", [])) == 1
        assert result["conversations"][0]["content"] == "hello"
