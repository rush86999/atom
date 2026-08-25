"""Coverage wave 25 — core/agent_world_model remaining uncovered branches (TDD).

Picks up where wave 20 left off. This suite drives the methods that were still
uncovered after test_covpush_w20_world_model.py:

- record_formula_usage (text repr, metadata stamping, no-inputs)
- update_experience_feedback (found → re-add with blended confidence, not-found,
  exception → False)
- boost_experience_confidence (found → clamped confidence + boost_count,
  not-found, exception → False)
- get_experience_statistics (agent/role filters, empty, exception → error dict)
- record_business_fact side branches
- update_fact_verification (old-status capture + text replace, not-found,
  exception → False)
- get_relevant_business_facts (parse, exception → [])
- bulk_record_facts (all-ok, mixed, per-fact exception swallowed)
- list_all_facts (status/domain filters, parse-failure skip, limit, exception)
- delete_fact (soft delete via update_fact_verification)
- recall_integration_experiences (db=None gate, success, parse-failure skip,
  filter-str escaping)
- archive_session_to_cold_storage (no messages, success + soft-delete + ACU
  billing, commit error rollback, exception → False)
- recover_archived_session (no messages, success, exception → error dict)
- recall_experiences (scoping is_creator/is_role_match, failure+low-confidence
  skip, similarity ranking, knowledge + GraphRAG await, formula + hot fallback,
  conversation recall)
"""
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agent_world_model import BusinessFact, WorldModelService
from core.models import AgentRegistry, ChatMessage


@pytest.fixture
def mock_handler():
    handler = Mock()
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=["agent_experience", "business_facts"])
    handler.workspace_id = "test_workspace"
    handler.add_document = Mock(return_value=True)
    handler.search = Mock(return_value=[])
    handler.create_table = Mock()
    handler.get_table = Mock(return_value=None)
    return handler


@pytest.fixture
def svc(mock_handler):
    with patch("core.agent_world_model.get_lancedb_handler", return_value=mock_handler):
        return WorldModelService(workspace_id="test_workspace")


def _exp_result(
    experience_id="exp-1",
    text="Task: reconcile\nInput: Reconcile SKU-123\nOutcome: Success\nLearnings: fast",
    outcome="Success",
    confidence=0.9,
    agent_id="agent_1",
    agent_role="finance",
    created_at=None,
    score=0.85,
    feedback_score=None,
):
    return {
        "id": experience_id,
        "text": text,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "score": score,
        "metadata": {
            "agent_id": agent_id,
            "agent_role": agent_role,
            "task_type": "reconciliation",
            "outcome": outcome,
            "confidence_score": confidence,
            "feedback_score": feedback_score,
            "artifacts": ["r1.pdf"],
            "specialty": "accounting",
        },
    }


def _fact_meta(**overrides):
    meta = {
        "id": "fact-1",
        "fact": "Revenue is 50k MRR",
        "citations": ["doc-1"],
        "reason": "verified in docs",
        "source_agent_id": "agent_1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_verified": "2026-01-02T00:00:00+00:00",
        "verification_status": "verified",
        "domain": "finance",
    }
    meta.update(overrides)
    return meta


class TestFormulaAndFeedback:
    async def test_record_formula_usage_success(self, svc):
        result = await svc.record_formula_usage(
            formula_id="f-1",
            formula_name="Growth Rate",
            task_description="Compute growth",
            inputs={"revenue": 100},
            result="12%",
            success=True,
            agent_id="agent_1",
            agent_role="Finance",
        )
        assert result is True
        args = svc.db.add_document.call_args.kwargs
        assert args["table_name"] == svc.table_name
        assert "Growth Rate" in args["text"]
        assert "Outcome: Success" in args["text"]
        assert args["metadata"]["type"] == "experience"
        assert args["metadata"]["specialty"] == "formulas"
        assert json.loads(args["metadata"]["formula_inputs"]) == {"revenue": 100}
        assert args["metadata"]["formula_result"] == "12%"

    async def test_record_formula_usage_failure_no_inputs(self, svc):
        result = await svc.record_formula_usage(
            formula_id="f-2",
            formula_name="Churn",
            task_description="Compute churn",
            inputs=None,
            result="3%",
            success=False,
            agent_id="agent_2",
            agent_role="Sales",
        )
        assert result is True
        meta = svc.db.add_document.call_args.kwargs["metadata"]
        assert meta["outcome"] == "Failure"
        assert meta["formula_inputs"] == "{}"
        assert "Formula Churn used with inputs None" in svc.db.add_document.call_args.kwargs["text"]

    async def test_update_feedback_found(self, svc):
        old_meta = {"confidence_score": 0.5, "outcome": "Success"}
        svc.db.search.return_value = [
            {"id": "exp-1", "text": "Task: x\nInput: y", "metadata": old_meta, "source": "agent_1"}
        ]
        result = await svc.update_experience_feedback("exp-1", 0.5, "Good work")
        assert result is True
        doc = svc.db.add_document.call_args.kwargs
        assert doc["metadata"]["feedback_score"] == 0.5
        assert doc["metadata"]["feedback_notes"] == "Good work"
        assert "Feedback: Good work" in doc["text"]
        # old 0.5 * 0.6 + (0.5+1)/2 * 0.4 = 0.3 + 0.3 = 0.6
        assert abs(doc["metadata"]["confidence_score"] - 0.6) < 1e-9

    async def test_update_feedback_not_found(self, svc):
        svc.db.search.return_value = [{"id": "other", "metadata": {}}]
        result = await svc.update_experience_feedback("exp-1", 0.5)
        assert result is False
        svc.db.add_document.assert_not_called()

    async def test_update_feedback_exception(self, svc):
        svc.db.search.side_effect = RuntimeError("boom")
        result = await svc.update_experience_feedback("exp-1", 0.5)
        assert result is False

    async def test_boost_confidence_found_clamped(self, svc):
        svc.db.search.return_value = [
            {"id": "exp-1", "text": "Task: x", "metadata": {"confidence_score": 0.95}, "source": "s"}
        ]
        result = await svc.boost_experience_confidence("exp-1", 0.2)
        assert result is True
        meta = svc.db.add_document.call_args.kwargs["metadata"]
        assert meta["confidence_score"] == 1.0
        assert meta["boost_count"] == 1
        assert meta["last_boosted_at"]

    async def test_boost_confidence_negative_clamped_to_zero(self, svc):
        svc.db.search.return_value = [
            {"id": "exp-1", "text": "Task: x", "metadata": {"confidence_score": 0.1}, "source": "s"}
        ]
        result = await svc.boost_experience_confidence("exp-1", -0.5)
        assert result is True
        meta = svc.db.add_document.call_args.kwargs["metadata"]
        assert meta["confidence_score"] == 0.0
        assert meta["boost_count"] == 1

    async def test_boost_confidence_not_found(self, svc):
        svc.db.search.return_value = []
        result = await svc.boost_experience_confidence("exp-1", 0.1)
        assert result is False
        svc.db.add_document.assert_not_called()

    async def test_boost_confidence_exception(self, svc):
        svc.db.search.side_effect = RuntimeError("boom")
        result = await svc.boost_experience_confidence("exp-1", 0.1)
        assert result is False


class TestStatistics:
    def _stat_results(self):
        return [
            {
                "id": "e1",
                "metadata": {
                    "agent_id": "agent_1",
                    "agent_role": "Finance",
                    "outcome": "Success",
                    "confidence_score": 0.8,
                    "feedback_score": 0.5,
                },
            },
            {
                "id": "e2",
                "metadata": {
                    "agent_id": "agent_2",
                    "agent_role": "Sales",
                    "outcome": "failed",
                    "confidence_score": 0.4,
                },
            },
            {
                "id": "e3",
                "metadata": {
                    "agent_id": "agent_1",
                    "agent_role": "finance",
                    "outcome": "Failure",
                    "confidence_score": 0.6,
                },
            },
        ]

    async def test_statistics_all(self, svc):
        svc.db.search.return_value = self._stat_results()
        stats = await svc.get_experience_statistics()
        assert stats["total_experiences"] == 3
        assert stats["successes"] == 1
        assert stats["failures"] == 2
        assert stats["feedback_coverage"] == 1 / 3
        assert abs(stats["avg_confidence"] - 0.6) < 1e-9

    async def test_statistics_agent_filter(self, svc):
        svc.db.search.return_value = self._stat_results()
        stats = await svc.get_experience_statistics(agent_id="agent_1")
        assert stats["total_experiences"] == 2
        assert stats["successes"] == 1
        assert stats["failures"] == 1
        assert stats["agent_id"] == "agent_1"

    async def test_statistics_role_filter_case_insensitive(self, svc):
        svc.db.search.return_value = self._stat_results()
        stats = await svc.get_experience_statistics(agent_role="FINANCE")
        assert stats["total_experiences"] == 2
        assert stats["agent_role"] == "FINANCE"

    async def test_statistics_empty(self, svc):
        svc.db.search.return_value = []
        stats = await svc.get_experience_statistics()
        assert stats["total_experiences"] == 0
        assert stats["success_rate"] == 0
        assert stats["avg_confidence"] == 0.5

    async def test_statistics_exception(self, svc):
        svc.db.search.side_effect = RuntimeError("boom")
        stats = await svc.get_experience_statistics()
        assert "error" in stats


class TestFacts:
    def _fact(self, fact_id="fact-1", fact="Revenue is 50k MRR", status="verified"):
        return BusinessFact(
            id=fact_id,
            fact=fact,
            citations=["doc-1"],
            reason="verified in docs",
            source_agent_id="agent_1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_verified=datetime(2026, 1, 2, tzinfo=timezone.utc),
            verification_status=status,
            metadata={"domain": "finance"},
        )

    async def test_update_fact_verification_success(self, svc):
        svc.db.search.return_value = [
            {
                "text": "Fact: Revenue is 50k MRR\nStatus: unverified",
                "source": "fact_agent_1",
                "metadata": _fact_meta(verification_status="unverified"),
            }
        ]
        result = await svc.update_fact_verification("fact-1", "verified")
        assert result is True
        doc = svc.db.add_document.call_args.kwargs
        assert doc["metadata"]["verification_status"] == "verified"
        assert "Status: verified" in doc["text"]
        assert "Status: unverified" not in doc["text"]

    async def test_update_fact_verification_not_found(self, svc):
        svc.db.search.return_value = [{"metadata": {"id": "other"}}]
        result = await svc.update_fact_verification("fact-1", "verified")
        assert result is False
        svc.db.add_document.assert_not_called()

    async def test_update_fact_verification_exception(self, svc):
        svc.db.search.side_effect = RuntimeError("boom")
        result = await svc.update_fact_verification("fact-1", "verified")
        assert result is False

    async def test_delete_fact_soft_delete(self, svc):
        svc.db.search.return_value = [
            {"text": "Fact: x\nStatus: verified", "source": "s", "metadata": _fact_meta()}
        ]
        result = await svc.delete_fact("fact-1")
        assert result is True
        assert svc.db.add_document.call_args.kwargs["metadata"]["verification_status"] == "deleted"

    async def test_relevant_facts_success(self, svc):
        svc.db.search.return_value = [{"metadata": _fact_meta()}]
        facts = await svc.get_relevant_business_facts("revenue", limit=3)
        assert len(facts) == 1
        assert facts[0].fact == "Revenue is 50k MRR"
        assert facts[0].verification_status == "verified"
        assert svc.db.search.call_args.kwargs["limit"] == 3

    async def test_relevant_facts_exception(self, svc):
        svc.db.search.side_effect = RuntimeError("boom")
        facts = await svc.get_relevant_business_facts("revenue")
        assert facts == []

    async def test_bulk_record_facts_all_ok(self, svc):
        svc.db.add_document.return_value = True
        count = await svc.bulk_record_facts([self._fact("f1"), self._fact("f2")])
        assert count == 2

    async def test_bulk_record_facts_mixed(self, svc):
        svc.db.add_document.return_value = True
        with patch.object(svc, "record_business_fact") as rbf:
            rbf.side_effect = [True, False, RuntimeError("boom")]
            count = await svc.bulk_record_facts(
                [self._fact("f1"), self._fact("f2"), self._fact("f3")]
            )
        assert count == 1

    async def test_bulk_record_facts_empty(self, svc):
        count = await svc.bulk_record_facts([])
        assert count == 0

    async def test_list_all_facts_filters(self, svc):
        svc.db.search.return_value = [
            {"metadata": _fact_meta(verification_status="verified", domain="finance")},
            {"metadata": _fact_meta(id="f2", verification_status="unverified", domain="finance")},
            {"metadata": _fact_meta(id="f3", verification_status="verified", domain="sales")},
        ]
        facts = await svc.list_all_facts(status="verified", domain="finance", limit=100)
        assert [f.id for f in facts] == ["fact-1"]
        assert facts[0].metadata == {"domain": "finance"}

    async def test_list_all_facts_parse_failure_skipped(self, svc):
        svc.db.search.return_value = [
            {"metadata": {**_fact_meta(), "created_at": "not-a-date"}},
            {"metadata": _fact_meta(id="f2", created_at=None, last_verified=None)},
        ]
        facts = await svc.list_all_facts(limit=10)
        assert [f.id for f in facts] == ["f2"]

    async def test_list_all_facts_limit(self, svc):
        svc.db.search.return_value = [
            {"metadata": _fact_meta(id=f"f{i}")} for i in range(5)
        ]
        facts = await svc.list_all_facts(limit=2)
        assert len(facts) == 2

    async def test_list_all_facts_exception(self, svc):
        svc.db.search.side_effect = RuntimeError("boom")
        assert await svc.list_all_facts() == []


class TestIntegrationRecall:
    async def test_recall_integration_db_none(self, svc):
        svc.db.db = None
        result = await svc.recall_integration_experiences("finance", "stripe", "sync")
        assert result == []

    async def test_recall_integration_success(self, svc):
        svc.db.db = Mock()
        svc.db.search.return_value = [_exp_result(text="Task: x\nInput: Reconcile SKU\nLearnings: retry")]
        result = await svc.recall_integration_experiences("finance", "stripe", "sync")
        assert len(result) == 1
        assert result[0].input_summary == "Reconcile SKU"
        assert result[0].learnings == " retry"
        filter_str = svc.db.search.call_args.kwargs["filter_str"]
        assert "integration_stripe_sync" in filter_str
        assert "finance" in filter_str

    async def test_recall_integration_escapes_quotes(self, svc):
        svc.db.db = Mock()
        svc.db.search.return_value = []
        await svc.recall_integration_experiences("fi'nance", "stri'pe", "sync")
        filter_str = svc.db.search.call_args.kwargs["filter_str"]
        assert "integration_stri''pe_sync" in filter_str
        assert "agent_role = 'fi''nance'" in filter_str

    async def test_recall_integration_parse_failure_skipped(self, svc):
        svc.db.db = Mock()
        svc.db.search.return_value = [
            {"id": "bad", "text": "x", "created_at": "not-a-date", "metadata": {}},
            _exp_result(experience_id="good"),
        ]
        result = await svc.recall_integration_experiences("finance", "stripe", "sync")
        assert [r.id for r in result] == ["good"]


class TestSessionArchival:
    def _chat_msg(self, conversation_id, content="hello", role="user"):
        m = Mock(spec=ChatMessage)
        m.conversation_id = conversation_id
        m.tenant_id = "test_workspace"
        m.role = role
        m.content = content
        m.created_at = datetime.now(timezone.utc)
        m.metadata_json = {}
        return m

    async def test_archive_session_no_messages(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            result = await svc.archive_session_to_cold_storage("conv-x")
        assert result is False
        svc.db.add_document.assert_not_called()

    async def test_archive_session_success_with_billing(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            msgs = [self._chat_msg("conv-x"), self._chat_msg("conv-x", "bye", "assistant")]
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = msgs
            with patch("core.usage_tracking_service.UsageTrackingService") as billing_cls:
                billing = Mock()
                billing_cls.return_value = billing
                result = await svc.archive_session_to_cold_storage("conv-x")
        assert result is True
        doc = svc.db.add_document.call_args.kwargs
        assert doc["table_name"] == "archived_memories"
        assert doc["metadata"]["msg_count"] == 2
        assert doc["metadata"]["conversation_id"] == "conv-x"
        assert db.commit.called
        assert all(m.metadata_json["_archived"] is True for m in msgs)
        billing.track_acu_usage.assert_called_once()

    async def test_archive_session_billing_error_swallowed(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                self._chat_msg("conv-x")
            ]
            with patch("core.usage_tracking_service.UsageTrackingService", side_effect=RuntimeError("billing down")):
                result = await svc.archive_session_to_cold_storage("conv-x")
        assert result is True

    async def test_archive_session_commit_error_rollback(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                self._chat_msg("conv-x")
            ]
            db.commit.side_effect = RuntimeError("commit boom")
            result = await svc.archive_session_to_cold_storage("conv-x")
        assert result is True
        assert db.rollback.called

    async def test_archive_session_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            sl.side_effect = RuntimeError("db down")
            result = await svc.archive_session_to_cold_storage("conv-x")
        assert result is False

    async def test_recover_session_no_messages(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.all.return_value = []
            result = await svc.recover_archived_session("conv-x")
        assert result["status"] == "failed"
        assert result["error"] == "No archived messages found"

    async def test_recover_session_success(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            msg = self._chat_msg("conv-x")
            msg.metadata_json = {"_archived": True}
            db.query.return_value.filter.return_value.all.return_value = [msg]
            result = await svc.recover_archived_session("conv-x")
        assert result["status"] == "success"
        assert result["recovered_count"] == 1
        assert msg.metadata_json["_recovered"] is True
        assert "_archived" not in msg.metadata_json
        assert db.commit.called

    async def test_recover_session_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = await svc.recover_archived_session("conv-x")
        assert result["status"] == "failed"
        assert result["error"] == "Session recovery failed"
        assert db.rollback.called


class TestRecallExperiences:
    def _agent(self, agent_id="agent_1", category="Finance"):
        return AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category=category,
            status="SUPERVISED",
        )

    async def test_recall_scoping_and_filters(self, svc):
        svc.db.search.side_effect = [
            # Experience table results
            [
                _exp_result(experience_id="own", agent_id="agent_1", agent_role="marketing", score=0.9),
                _exp_result(experience_id="role", agent_id="other", agent_role="finance", score=0.7),
                _exp_result(experience_id="failed-low", agent_id="agent_1", agent_role="marketing", outcome="Failed", confidence=0.5, score=0.99),
                _exp_result(experience_id="failed-high", agent_id="agent_1", agent_role="marketing", outcome="failed", confidence=0.9, score=0.8),
                _exp_result(experience_id="outside", agent_id="other", agent_role="sales", score=0.6),
            ],
            # knowledge leg, call 1: role LIKE filter — no role-tagged hits
            [],
            # knowledge leg, call 2: untagged top-up — returns the general doc
            [{"id": "doc-1", "text": "General knowledge", "metadata": {}}],
            # remaining legs (business facts, episode mirror, canonical episodes)
            [], [], [],
        ]
        agent = self._agent(category="Finance")
        with patch("core.graphrag_engine.graphrag_engine") as ge:
            ge.get_context_for_ai = AsyncMock(return_value="graph ctx")
            result = await svc.recall_experiences(agent, "reconcile SKU", limit=5)
        experiences = result["experiences"]
        ids = [e.id for e in experiences]
        assert "own" in ids
        assert "role" in ids
        assert "failed-low" not in ids
        assert "failed-high" in ids
        assert "outside" not in ids
        # ranked by similarity score: own (0.9) before failed-high (0.8)
        assert ids.index("own") < ids.index("failed-high")
        assert result["knowledge"] == [{"id": "doc-1", "text": "General knowledge", "metadata": {}}]

    async def test_recall_experiences_graphrag_failure_swallowed(self, svc):
        svc.db.search.side_effect = [
            [_exp_result(experience_id="own", agent_id="agent_1", agent_role="finance")],
            # knowledge LIKE + top-up, then facts / episode legs
            [], [], [], [], [],
        ]
        agent = self._agent()
        with patch("core.graphrag_engine.graphrag_engine") as ge:
            ge.get_context_for_ai = AsyncMock(side_effect=RuntimeError("graph down"))
            result = await svc.recall_experiences(agent, "reconcile", limit=5)
        assert len(result["experiences"]) == 1

    async def test_recall_experiences_formula_and_conversation(self, svc):
        svc.db.search.side_effect = [
            [_exp_result(experience_id="own", agent_id="agent_1", agent_role="finance")],
            # knowledge LIKE + top-up, then facts / episode legs
            [], [], [], [], [],
        ]
        agent = self._agent()
        formula_manager = Mock()
        formula_manager.search_formulas.return_value = [
            {"id": "fm-1", "name": "Growth", "expression": "a/b", "domain": "finance", "use_case": "x", "parameters": []}
        ]
        with patch("core.graphrag_engine.graphrag_engine") as ge:
            ge.get_context_for_ai = AsyncMock(return_value="ctx")
            with patch("core.formula_memory.get_formula_manager", return_value=formula_manager):
                with patch("core.agent_world_model.SessionLocal") as sl:
                    db = Mock()
                    sl.return_value = db
                    # hot formula fallback returns nothing new
                    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
                    # conversation recall
                    conv_row = SimpleNamespace(
                        conversation_id="c1",
                        role="user",
                        content="hello",
                        created_at=datetime.now(timezone.utc),
                    )
                    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
                        [],  # hot formulas
                        [conv_row],  # conversations
                    ]
                    result = await svc.recall_experiences(agent, "reconcile", limit=5)
        assert len(result["formulas"]) == 1
        assert result["formulas"][0]["type"] == "formula"
        assert result["formulas"][0]["name"] == "Growth"
        assert len(result["conversations"]) >= 1
