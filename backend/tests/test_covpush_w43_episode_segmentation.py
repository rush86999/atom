"""Coverage wave 43 — core/episode_segmentation_service.py edge branches (TDD).

Picks up where the existing episode suites left off (87%, 586/672). Targets:
- _cosine_similarity numpy-failure fallback + zero-magnitude branches
- _keyword_similarity edge cases (empty tokens)
- _extract_entities (phones/URLs/metadata entities, execution task-desc,
  capitalized words, metadata_json)
- _extract_topics execution-description branch
- create_episode_from_session: too-small (non-forced) → None, forced creation
- _extract_canvas_context / _filter_canvas_context_detail branches
- _fetch_feedback_context / _calculate_feedback_score branches
- _archive_supervision_episode_to_lancedb missing-table + error paths
- _get_agent_maturity, _calculate_importance, _format_agent_actions edges
"""
import os
os.environ["TESTING"] = "1"

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.episode_segmentation_service import (
    EpisodeBoundaryDetector,
    EpisodeSegmentationService,
)


def _service(db=None, lancedb=None, **kwargs):
    return EpisodeSegmentationService(
        db=db or Mock(), lancedb=lancedb or Mock(), **kwargs)


def _msg(content, metadata=None):
    m = Mock()
    m.content = content
    m.metadata_json = metadata
    return m


def _execution(task_desc=None, metadata=None):
    e = Mock()
    e.task_description = task_desc
    e.input_summary = None
    e.result_summary = None
    e.metadata_json = metadata
    e.status = "completed"
    return e


class TestBoundaryDetectorSimilarity:
    def test_cosine_numpy_fallback(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        vec1, vec2 = [1.0, 2.0, 3.0], [1.0, 0.0, 1.0]
        with patch("numpy.linalg.norm", side_effect=ValueError("numpy fail")):
            sim = detector._cosine_similarity(vec1, vec2)
        assert 0.0 <= sim <= 1.0

    def test_cosine_zero_magnitude(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        with patch("numpy.linalg.norm", side_effect=ValueError("numpy fail")):
            assert detector._cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_cosine_pure_python_exception(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        with patch("numpy.linalg.norm", side_effect=ValueError("numpy fail")):
            # Non-numeric vectors → inner sum raises TypeError → 0.0
            assert detector._cosine_similarity(["a"], ["b"]) == 0.0

    def test_keyword_similarity_empty_tokens(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        assert detector._keyword_similarity("", "hello world") == 0.0
        assert detector._keyword_similarity("hello world", "") == 0.0

    def test_keyword_similarity_overlap(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        assert detector._keyword_similarity("foo bar baz", "foo qux") > 0.0
        assert detector._keyword_similarity("foo", "foo") == 1.0


class TestExtractEntities:
    def test_extracts_phones_urls_and_metadata(self):
        service = _service()
        msgs = [
            _msg("Call 555-123-4567 or 555.123.4568"),
            _msg("See https://example.com/page for details"),
            _msg("no entities here"),
            _msg("meta value", metadata={"project_name": "alpha-42", "skip": 1}),
            None,
            _msg(""),
        ]
        entities = service._extract_entities(msgs, [])
        assert any("555" in e for e in entities)
        assert any("https://example.com" in e for e in entities)
        assert "alpha-42" in entities

    def test_extracts_from_executions(self):
        service = _service()
        execs = [
            _execution(task_desc="Improve the Dashboard Module performance"),
            _execution(task_desc=None, metadata={"ticket_ref": "TICKET-99"}),
            _execution(task_desc=""),
        ]
        entities = service._extract_entities([], execs)
        assert any(e == "Dashboard" or e == "Module" for e in entities)
        assert "TICKET-99" in entities


class TestExtractTopics:
    def test_topics_from_execution_descriptions(self):
        service = _service()
        topics = service._extract_topics([], [_execution(task_desc="Optimize database queries")])
        assert isinstance(topics, list)
        assert any("optimize" in t for t in topics)


class TestCreateEpisodeFromSessionEdges:
    def _mock_session_rows(self, service, messages=None, executions=None):
        def _query(model):
            q = Mock()
            if model.__name__ == "ChatSession":
                q.filter.return_value.first.return_value = SimpleNamespace(
                    id="sess-1", user_id="u-1",
                    created_at=datetime.now(timezone.utc))
            elif model.__name__ == "ChatMessage":
                q.filter.return_value.order_by.return_value.all.return_value = messages or []
            elif model.__name__ == "AgentExecution":
                q.filter.return_value.order_by.return_value.all.return_value = executions or []
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.all.return_value = []
            return q
        service.db.query = Mock(side_effect=_query)

    async def test_no_messages_and_no_executions(self):
        service = _service()
        self._mock_session_rows(service, messages=[], executions=[])
        with patch.object(service, "_extract_canvas_context_llm",
                          new=AsyncMock(return_value={})), \
             patch.object(service, "_fetch_feedback_context",
                          return_value=[]):
            result = await service.create_episode_from_session(
                "sess-1", "a-1")
        assert result is None

    async def test_too_small_not_forced(self):
        service = _service()
        self._mock_session_rows(service, messages=[_msg("only one")], executions=[])
        with patch.object(service, "_extract_canvas_context_llm",
                          new=AsyncMock(return_value={})), \
             patch.object(service, "_fetch_feedback_context",
                          return_value=[]):
            result = await service.create_episode_from_session(
                "sess-1", "a-1")
        assert result is None

    async def test_too_small_forced_creates(self):
        service = _service()
        self._mock_session_rows(service, messages=[_msg("only one")], executions=[])
        with patch.object(service, "_extract_canvas_context_llm",
                          new=AsyncMock(return_value={})), \
             patch.object(service, "_fetch_feedback_context",
                          return_value=[]), \
             patch.object(service, "_create_segments", new=AsyncMock()), \
             patch.object(service, "_archive_to_lancedb",
                          new=AsyncMock()):
            service.db.add = Mock()
            service.db.commit = Mock()
            result = await service.create_episode_from_session(
                "sess-1", "a-1", force_create=True)
        assert result is not None
        assert result["session_id"] == "sess-1"


class TestCanvasContextEdges:
    def test_extract_canvas_context_missing_fields(self):
        service = _service()
        canvas = Mock()
        canvas.details_json = {"canvas_type": "sheets"}
        canvas.action_type = "present"
        result = service._extract_canvas_context([canvas])
        assert isinstance(result, dict)
        assert result["canvas_type"] == "sheets"

    def test_extract_canvas_context_single_audit(self):
        service = _service()
        a = Mock()
        a.details_json = {"canvas_type": "sheets", "revenue": 100,
                          "component_name": "chart", "amount": 50}
        a.action_type = "submit"
        context = service._extract_canvas_context([a])
        assert context is not None
        assert context["canvas_type"] == "sheets"
        assert context["critical_data_points"]["revenue"] == 100
        assert context["user_interaction"] == "user submitted"
        assert context["visual_elements"] == ["chart"]

    def test_extract_canvas_context_empty_returns_empty_dict(self):
        service = _service()
        assert service._extract_canvas_context([]) == {}

    def test_extract_canvas_context_first_audit_wins(self):
        service = _service()

        def _audit(action, details):
            a = Mock()
            a.details_json = details
            a.action_type = action
            return a

        audits = [
            _audit("submit", {"canvas_type": "sheets", "revenue": 100,
                              "amount": 50, "component_name": "chart"}),
            _audit("approve", {"canvas_type": "sheets", "component_name": "table"}),
            _audit("execute", {"canvas_type": "terminal", "command": "ls",
                               "exit_code": 0}),
            _audit("custom", {"canvas_type": "orchestration",
                              "workflow_id": "wf-1",
                              "approval_status": "pending"}),
        ]
        context = service._extract_canvas_context(audits)
        assert context["canvas_type"] == "sheets"  # first audit wins
        assert context["visual_elements"] == ["chart"]
        assert context["user_interaction"] == "user submitted"
        assert context["critical_data_points"]["revenue"] == 100
        assert "workflow_id" not in context["critical_data_points"]

    def test_extract_canvas_context_single_type_no_visuals(self):
        service = _service()
        a = Mock()
        a.details_json = {"canvas_type": "document"}
        a.action_type = ""
        context = service._extract_canvas_context([a])
        assert context["canvas_type"] == "document"
        assert context["visual_elements"] == []
        assert context["user_interaction"] == ""
        assert context["critical_data_points"] == {}

    def test_filter_canvas_context_detail_levels(self):
        service = _service()
        context = {"canvas_type": "sheets", "critical_data_points": {"a": 1},
                   "full_data": {"x": 2}}
        for level in ("summary", "standard", "full", "bogus"):
            result = service._filter_canvas_context_detail(context, level)
            assert isinstance(result, dict)

    def test_extract_canvas_context_empty_returns_empty_dict(self):
        service = _service()
        assert service._extract_canvas_context([]) == {}

    def test_extract_canvas_context_first_audit_wins(self):
        service = _service()

        def _audit(action, details):
            a = Mock()
            a.details_json = details
            a.action_type = action
            return a

        audits = [
            _audit("submit", {"canvas_type": "sheets", "revenue": 100,
                              "amount": 50, "component_name": "chart"}),
            _audit("approve", {"canvas_type": "sheets", "component_name": "table"}),
            _audit("execute", {"canvas_type": "terminal", "command": "ls",
                               "exit_code": 0}),
            _audit("custom", {"canvas_type": "orchestration",
                              "workflow_id": "wf-1",
                              "approval_status": "pending"}),
        ]
        context = service._extract_canvas_context(audits)
        assert context["canvas_type"] == "sheets"  # first audit wins
        assert context["visual_elements"] == ["chart"]
        assert context["user_interaction"] == "user submitted"
        assert context["critical_data_points"]["revenue"] == 100
        assert "workflow_id" not in context["critical_data_points"]

    def test_extract_canvas_context_single_type_no_visuals(self):
        service = _service()
        a = Mock()
        a.details_json = {"canvas_type": "document"}
        a.action_type = ""
        context = service._extract_canvas_context([a])
        assert context["canvas_type"] == "document"
        assert context["visual_elements"] == []
        assert context["user_interaction"] == ""
        assert context["critical_data_points"] == {}

    def test_extract_canvas_context_exception(self):
        service = _service()
        a = Mock()
        a.details_json = Mock(side_effect=RuntimeError("boom"))
        a.action_type = None
        with patch("core.episode_segmentation_service.logger"):
            result = service._extract_canvas_context([a])
        assert result == {}


class TestFeedbackContextEdges:
    def test_fetch_feedback_context_empty_executions(self):
        service = _service()
        result = service._fetch_feedback_context("a-1", "sess-1", [])
        assert result == []

    def test_fetch_feedback_context_exception(self):
        service = _service()
        execs = [_execution(task_desc="t")]
        with patch.object(service.db, "query", side_effect=RuntimeError("db down")):
            result = service._fetch_feedback_context("a-1", "sess-1", execs)
        assert result == []

    def test_calculate_feedback_score_empty(self):
        service = _service()
        assert service._calculate_feedback_score([]) is None

    def test_calculate_feedback_score_thumbs_and_rating(self):
        service = _service()
        f1 = Mock(feedback_type="thumbs_up", thumbs_up_down=True, rating=None)
        f2 = Mock(feedback_type="thumbs_down", thumbs_up_down=False, rating=None)
        f3 = Mock(feedback_type="rating", thumbs_up_down=None, rating=5)
        f4 = Mock(feedback_type="other", thumbs_up_down=None, rating=None)
        score = service._calculate_feedback_score([f1, f2, f3, f4])
        assert score is not None
        assert -1.0 <= score <= 1.0

    def test_calculate_feedback_score_exception(self):
        service = _service()
        bad = Mock(feedback_type="rating", thumbs_up_down=None)
        bad.rating = object()  # not an int → comparison raises TypeError
        result = service._calculate_feedback_score([bad])
        assert result is None


class TestArchiveSupervisionEdges:
    def _episode(self, ep_id="ep-1"):
        return SimpleNamespace(
            id=ep_id, agent_id="a-1", user_id="u-1", task_description="t",
            outcome="success", success=True, maturity_at_time="supervised",
            created_at=datetime.now(timezone.utc), metadata_json={},
            title="T", description="D", summary="S", supervisor_rating=4,
            intervention_count=0, topics=[], status="completed",
            workspace_id="ws-1", human_intervention_count=0,
            constitutional_score=None, intervention_types=[])

    def _lancedb(self, tables):
        lancedb = MagicMock()
        db = MagicMock()
        db.table_names.return_value = tables
        lancedb.db = db
        return lancedb

    async def test_archive_missing_table_creates(self):
        lancedb = self._lancedb([])
        service = _service(lancedb=lancedb)
        with patch.object(service, "_ensure_episode_columns") as mock_ensure:
            await service._archive_supervision_episode_to_lancedb(self._episode())
        lancedb.add_document.assert_called_once()
        mock_ensure.assert_not_called()

    async def test_archive_existing_table_ensures_columns(self):
        lancedb = self._lancedb(["episodes"])
        service = _service(lancedb=lancedb)
        with patch.object(service, "_ensure_episode_columns") as mock_ensure:
            await service._archive_supervision_episode_to_lancedb(self._episode())
        mock_ensure.assert_called_once_with("episodes")
        lancedb.add_document.assert_called_once()

    async def test_archive_exception_swallowed(self):
        lancedb = self._lancedb([])
        lancedb.add_document = Mock(side_effect=RuntimeError("lancedb down"))
        service = _service(lancedb=lancedb)
        await service._archive_supervision_episode_to_lancedb(self._episode())

    async def test_archive_no_db_skips(self):
        lancedb = MagicMock()
        lancedb.db = None
        service = _service(lancedb=lancedb)
        await service._archive_supervision_episode_to_lancedb(self._episode())
        lancedb.add_document.assert_not_called()


class TestMiscEdges:
    def test_calculate_importance_high(self):
        service = _service()
        msgs = [_msg(f"m{i}") for i in range(12)]
        assert service._calculate_importance(msgs, []) > 0.6

    def test_calculate_importance_medium(self):
        service = _service()
        msgs = [_msg(f"m{i}") for i in range(7)]
        score = service._calculate_importance(msgs, [])
        assert 0.5 < score <= 0.7

    def test_calculate_importance_with_executions(self):
        service = _service()
        score = service._calculate_importance([], [_execution(task_desc="t")])
        assert score == 0.6

    def test_extract_topics_missing_content(self):
        service = _service()
        topics = service._extract_topics([None, _msg("")], [])
        assert isinstance(topics, list)

    def test_create_episode_forced_with_canvas_audits(self):
        service = _service()

        def _query(model):
            q = Mock()
            if model.__name__ == "ChatSession":
                q.filter.return_value.first.return_value = SimpleNamespace(
                    id="sess-2", user_id="u-1",
                    created_at=datetime.now(timezone.utc))
            elif model.__name__ == "ChatMessage":
                q.filter.return_value.order_by.return_value.all.return_value = [_msg("only one")]
            elif model.__name__ == "AgentExecution":
                q.filter.return_value.order_by.return_value.all.return_value = []
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.all.return_value = []
            return q
        service.db.query = Mock(side_effect=_query)

        audit = Mock()
        audit.id = "audit-1"
        audit.details_json = {"canvas_type": "form"}
        audit.action_type = "submit"
        canvas_audits = [audit]

        with patch.object(service, "_extract_canvas_context_llm",
                          new=AsyncMock(return_value={})), \
             patch.object(service, "_fetch_feedback_context",
                          return_value=[]), \
             patch.object(service, "_fetch_canvas_context",
                          return_value=canvas_audits), \
             patch.object(service, "_create_segments", new=AsyncMock()), \
             patch.object(service, "_archive_to_lancedb", new=AsyncMock()):
            service.db.add = Mock()
            service.db.commit = Mock()
            result = asyncio.run(service.create_episode_from_session(
                "sess-2", "a-1", force_create=True))
        assert result is not None
        assert result["canvas_ids"] == ["audit-1"]

    def test_get_agent_maturity_missing(self):
        service = _service()
        service.db.query.return_value.filter.return_value.first.return_value = None
        maturity = service._get_agent_maturity("ghost")
        assert maturity == "STUDENT"

    def test_get_agent_maturity_enum_status(self):
        service = _service()
        agent = Mock()
        agent.status = Mock()
        agent.status.value = "supervised"
        service.db.query.return_value.filter.return_value.first.return_value = agent
        assert service._get_agent_maturity("a-1") == "supervised"

    def test_get_agent_maturity_str_status(self):
        service = _service()
        agent = Mock()
        agent.status = "intern"
        service.db.query.return_value.filter.return_value.first.return_value = agent
        assert service._get_agent_maturity("a-1") == "intern"

    def test_ensure_episode_columns_table_none(self):
        service = _service()
        lancedb = Mock()
        lancedb.get_table.return_value = None
        service.lancedb = lancedb
        service._ensure_episode_columns("episodes")  # no-op

    def test_ensure_episode_columns_exception(self):
        service = _service()
        lancedb = Mock()
        lancedb.get_table.side_effect = RuntimeError("lancedb down")
        service.lancedb = lancedb
        service._ensure_episode_columns("episodes")  # swallowed

    def test_ensure_episode_columns_adds_missing(self):
        service = _service()
        lancedb = Mock()
        table = Mock()
        col = Mock()
        col.name = "id"
        table.schema = [col]  # missing outcome/agent_id
        lancedb.get_table.return_value = table
        service.lancedb = lancedb
        service._ensure_episode_columns("episodes")
        assert table.add_columns.call_count >= 2

    def test_filter_canvas_context_exception(self):
        service = _service()

        class _Boom(dict):
            def get(self, *a, **k):
                raise RuntimeError("boom")

        with patch("core.episode_segmentation_service.logger"):
            result = service._filter_canvas_context_detail(_Boom(), "summary")
        assert result == {}

    def test_extract_topics_execution_many_words(self):
        service = _service()
        execs = [_execution(task_desc="alpha beta gamma delta epsilon zeta"),
                 _execution(task_desc=None)]  # falsy → continue branch
        topics = service._extract_topics([], execs)
        assert isinstance(topics, list)
        assert len(topics) <= 5

    def test_create_episode_forced_with_feedback_links(self):
        service = _service()

        def _query(model):
            q = Mock()
            if model.__name__ == "ChatSession":
                q.filter.return_value.first.return_value = SimpleNamespace(
                    id="sess-3", user_id="u-1",
                    created_at=datetime.now(timezone.utc))
            elif model.__name__ == "ChatMessage":
                q.filter.return_value.order_by.return_value.all.return_value = [_msg("only one")]
            elif model.__name__ == "AgentExecution":
                q.filter.return_value.order_by.return_value.all.return_value = []
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.all.return_value = []
            return q
        service.db.query = Mock(side_effect=_query)

        feedback = Mock()
        feedback.id = "fb-1"
        with patch.object(service, "_extract_canvas_context_llm",
                          new=AsyncMock(return_value={})), \
             patch.object(service, "_fetch_feedback_context",
                          return_value=[feedback]), \
             patch.object(service, "_fetch_canvas_context",
                          return_value=[]), \
             patch.object(service, "_create_segments", new=AsyncMock()), \
             patch.object(service, "_archive_to_lancedb", new=AsyncMock()):
            service.db.add = Mock()
            service.db.commit = Mock()
            result = asyncio.run(service.create_episode_from_session(
                "sess-3", "a-1", force_create=True))
        assert result is not None
        assert result["feedback_ids"] == ["fb-1"]
        assert feedback.episode_id == result["id"]

    def test_format_agent_actions_with_input_summary(self):
        service = _service()
        execution = _execution(task_desc="Send report")
        execution.status = "completed"
        execution.input_summary = "input data"
        execution.result_summary = "done"
        result = service._format_agent_actions(
            [{"action": "send_email", "params": {"to": "x@y.z"}}], execution)
        assert isinstance(result, str)
        assert "Input: input data" in result
        assert "done" in result

    def test_keyword_similarity_none_input(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        # None tokens → attribute error caught → 0.0
        assert detector._keyword_similarity(None, "x") == 0.0  # type: ignore
