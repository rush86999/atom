"""
Coverage-push tests for core.agent_world_model (WorldModelService).

Mocks LanceDB handler and SQLAlchemy sessions. Targets >=70% line coverage.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

import pytest

from core.agent_world_model import (
    WorldModelService,
    AgentExperience,
    BusinessFact,
    DetailLevel,
)


def make_handler():
    handler = Mock()
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=[])
    handler.create_table = Mock()
    handler.add_document = Mock(return_value=True)
    handler.search = Mock(return_value=[])
    handler.get_table = Mock(return_value=None)
    handler.workspace_id = "test-ws"
    return handler


def make_service(handler=None):
    handler = handler or make_handler()
    with patch("core.agent_world_model.get_lancedb_handler", return_value=handler):
        service = WorldModelService(workspace_id="test-ws")
    return service, handler


def make_experience(**overrides):
    base = dict(
        id="exp-1",
        agent_id="agent-1",
        task_type="reconciliation",
        input_summary="Reconcile SKU-123",
        outcome="Success",
        learnings="Mismatch due to timing",
        confidence_score=0.8,
        feedback_score=None,
        artifacts=["a1"],
        step_efficiency=1.0,
        metadata_trace={},
        agent_role="Finance",
        specialty="ap",
        timestamp=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return AgentExperience(**base)


def make_fact(**overrides):
    now = datetime.now(timezone.utc)
    base = dict(
        id="fact-1",
        fact="Invoices > $500 need VP approval",
        citations=["policy.pdf:p4"],
        reason="Approval policy",
        source_agent_id="agent-1",
        created_at=now,
        last_verified=now,
        verification_status="unverified",
        metadata={},
    )
    base.update(overrides)
    return BusinessFact(**base)


class TestInitAndTables:
    def test_init_creates_tables(self):
        handler = make_handler()
        handler.db.table_names = Mock(side_effect=[[], ["agent_experience"]])
        service, _ = make_service(handler)
        assert service.table_name == "agent_experience"
        assert handler.create_table.call_count == 2

    def test_init_no_db(self):
        handler = make_handler()
        handler.db = None
        with patch("core.agent_world_model.get_lancedb_handler", return_value=handler):
            WorldModelService(workspace_id="test-ws")

    def test_init_no_tables_needed(self):
        handler = make_handler()
        handler.db.table_names = Mock(return_value=["agent_experience", "business_facts"])
        make_service(handler)


class TestRecordExperience:
    @pytest.mark.asyncio
    async def test_record_experience_success(self):
        service, handler = make_service()
        exp = make_experience(artifacts=None, metadata_trace={"plan": "x"})
        ok = await service.record_experience(exp)
        assert ok is True
        _, kwargs = handler.add_document.call_args
        assert kwargs["table_name"] == "agent_experience"
        assert kwargs["metadata"]["type"] == "experience"
        assert kwargs["metadata"]["artifacts"] == []
        assert "Task: reconciliation" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_record_experience_failure(self):
        service, handler = make_service()
        handler.add_document = Mock(return_value=False)
        ok = await service.record_experience(make_experience())
        assert ok is False


class TestRecordFormulaUsage:
    @pytest.mark.asyncio
    async def test_record_formula_usage_success(self):
        service, handler = make_service()
        ok = await service.record_formula_usage(
            agent_id="a1", agent_role="Finance", formula_id="f1",
            formula_name="sum", task_description="sum sales",
            inputs={"x": 1}, result=5, success=True, learnings="works",
        )
        assert ok is True
        meta = handler.add_document.call_args.kwargs["metadata"]
        assert meta["formula_id"] == "f1"
        assert meta["formula_inputs"] == '{"x": 1}'
        assert meta["outcome"] == "Success"

    @pytest.mark.asyncio
    async def test_record_formula_usage_failure_no_inputs(self):
        service, handler = make_service()
        ok = await service.record_formula_usage(
            agent_id="a1", agent_role="Ops", formula_id="f2",
            formula_name="avg", task_description="avg", inputs=None,
            result=None, success=False,
        )
        assert ok is True
        meta = handler.add_document.call_args.kwargs["metadata"]
        assert meta["outcome"] == "Failure"
        assert meta["formula_inputs"] == "{}"


class TestUpdateExperienceFeedback:
    @pytest.mark.asyncio
    async def test_update_found(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{
            "id": "exp-1",
            "text": "Task: t\nInput: i\nOutcome: Success\nLearnings: l",
            "source": "agent_1",
            "metadata": {"confidence_score": 0.5},
        }])
        ok = await service.update_experience_feedback("exp-1", 1.0, "great job")
        assert ok is True
        meta = handler.add_document.call_args.kwargs["metadata"]
        assert meta["confidence_score"] == pytest.approx(0.5 * 0.6 + 1.0 * 0.4)
        assert meta["feedback_score"] == 1.0
        assert "Feedback: great job" in handler.add_document.call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{"id": "other", "metadata": {}}])
        ok = await service.update_experience_feedback("exp-1", -0.5)
        assert ok is False

    @pytest.mark.asyncio
    async def test_update_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        ok = await service.update_experience_feedback("exp-1", 0.5)
        assert ok is False

    @pytest.mark.asyncio
    async def test_boost_experience_confidence(self):
        service, handler = make_service()
        handler.search = Mock(
            return_value=[{"id": "exp-1", "text": "t", "metadata": {"confidence_score": 0.5}}]
        )
        assert await service.boost_experience_confidence("exp-1", 0.2) is True


class TestGetExperienceStatistics:
    @pytest.mark.asyncio
    async def test_statistics_with_filters(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"metadata": {"agent_id": "a1", "agent_role": "Finance", "outcome": "Success", "confidence_score": 0.8, "feedback_score": 0.5}},
            {"metadata": {"agent_id": "a1", "agent_role": "finance", "outcome": "failed", "confidence_score": 0.4, "feedback_score": None}},
            {"metadata": {"agent_id": "a2", "agent_role": "Finance", "outcome": "success"}},
            {"metadata": {"agent_id": "a1", "agent_role": "Ops", "outcome": "Failure"}},
        ])
        stats = await service.get_experience_statistics(agent_id="a1", agent_role="finance")
        assert stats["total_experiences"] == 2
        assert stats["successes"] == 1
        assert stats["failures"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["feedback_coverage"] == 0.5

    @pytest.mark.asyncio
    async def test_statistics_empty(self):
        service, _ = make_service()
        stats = await service.get_experience_statistics()
        assert stats["total_experiences"] == 0
        assert stats["success_rate"] == 0
        assert stats["avg_confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_statistics_exception_returns_error(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("search down"))
        stats = await service.get_experience_statistics()
        assert stats["error"]


class TestBusinessFacts:
    @pytest.mark.asyncio
    async def test_record_business_fact(self):
        service, handler = make_service()
        ok = await service.record_business_fact(make_fact(metadata={"domain": "finance"}))
        assert ok is True
        _, kwargs = handler.add_document.call_args
        assert kwargs["table_name"] == "business_facts"
        assert kwargs["metadata"]["type"] == "business_fact"
        assert kwargs["metadata"]["domain"] == "finance"
        assert "Status: unverified" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_update_fact_verification_found(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{
            "text": "Fact: x\nCitations: c\nReason: r\nStatus: unverified",
            "source": "s",
            "metadata": {"id": "fact-1", "verification_status": "unverified"},
        }])
        ok = await service.update_fact_verification("fact-1", "verified")
        assert ok is True
        assert "Status: verified" in handler.add_document.call_args.kwargs["text"]
        assert handler.add_document.call_args.kwargs["metadata"]["verification_status"] == "verified"

    @pytest.mark.asyncio
    async def test_update_fact_verification_not_found(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{"metadata": {"id": "other"}}])
        ok = await service.update_fact_verification("fact-1", "verified")
        assert ok is False

    @pytest.mark.asyncio
    async def test_update_fact_verification_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        ok = await service.update_fact_verification("fact-1", "verified")
        assert ok is False

    @pytest.mark.asyncio
    async def test_delete_fact_delegates(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{"text": "Status: unverified", "metadata": {"id": "fact-1", "verification_status": "unverified"}}])
        ok = await service.delete_fact("fact-1")
        assert ok is True
        assert handler.add_document.call_args.kwargs["metadata"]["verification_status"] == "deleted"

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[{
            "metadata": {
                "id": "f1", "fact": "rule", "citations": ["a"],
                "reason": "why", "source_agent_id": "a1",
                "created_at": now, "last_verified": now,
                "verification_status": "verified",
            }
        }])
        facts = await service.get_relevant_business_facts("rule", limit=5)
        assert len(facts) == 1
        assert facts[0].fact == "rule"
        assert facts[0].verification_status == "verified"

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        assert await service.get_relevant_business_facts("q") == []

    @pytest.mark.asyncio
    async def test_get_business_fact_no_table(self):
        service, _ = make_service()
        assert await service.get_business_fact("f1") is None

    @pytest.mark.asyncio
    async def test_get_business_fact_found_string_metadata(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        table = Mock()
        results = Mock()
        results.empty = False
        results.iloc = {0: {
            "id": "f1",
            "metadata": json.dumps({
                "fact": "rule", "citations": [], "reason": "r",
                "source_agent_id": "a1", "created_at": now, "last_verified": now,
            }),
            "text": "Fact: rule\nCitations:\nReason: r\nStatus: verified",
        }}
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = results
        handler.get_table = Mock(return_value=table)
        fact = await service.get_business_fact("f1")
        assert fact is not None
        assert fact.id == "f1"

    @pytest.mark.asyncio
    async def test_get_business_fact_found_dict_metadata_no_verified(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        table = Mock()
        results = Mock()
        results.empty = False
        results.iloc = {0: {
            "id": "f2",
            "metadata": {"fact": "rule2", "reason": "r", "source_agent_id": "a1",
                         "created_at": now, "last_verified": None},
            "text": "Fact: rule2",
        }}
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = results
        handler.get_table = Mock(return_value=table)
        fact = await service.get_business_fact("f2")
        assert fact.fact == "rule2"
        assert fact.last_verified is not None

    @pytest.mark.asyncio
    async def test_get_business_fact_empty(self):
        service, handler = make_service()
        table = Mock()
        results = Mock()
        results.empty = True
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = results
        handler.get_table = Mock(return_value=table)
        assert await service.get_business_fact("nope") is None

    @pytest.mark.asyncio
    async def test_get_business_fact_other_metadata_type(self):
        service, handler = make_service()
        table = Mock()
        results = Mock()
        results.empty = False
        results.iloc = {0: {
            "id": "f3",
            "metadata": None,
            "text": "Fact: rule3",
        }}
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = results
        handler.get_table = Mock(return_value=table)
        fact = await service.get_business_fact("f3")
        # metadata None → treated as {} → fact still built from row text with
        # created_at/last_verified defaulted (no fromisoformat(None) crash)
        assert fact is not None
        assert fact.id == "f3"
        assert fact.fact == "rule3"
        assert fact.created_at is not None

    @pytest.mark.asyncio
    async def test_get_business_fact_exception(self):
        service, handler = make_service()
        handler.get_table = Mock(side_effect=RuntimeError("boom"))
        assert await service.get_business_fact("f1") is None

    @pytest.mark.asyncio
    async def test_bulk_record_facts(self):
        service, handler = make_service()
        handler.add_document = Mock(side_effect=[True, False, RuntimeError("boom")])
        count = await service.bulk_record_facts([make_fact(id="1"), make_fact(id="2"), make_fact(id="3")])
        assert count == 1

    @pytest.mark.asyncio
    async def test_list_all_facts(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[
            {"metadata": {"id": "f1", "fact": "a", "verification_status": "verified", "domain": "finance", "created_at": now, "last_verified": now}},
            {"metadata": {"id": "f2", "fact": "b", "verification_status": "unverified", "domain": "ops", "created_at": now}},
            {"metadata": {"id": "bad", "fact": "c", "verification_status": "verified", "created_at": "not-a-date"}},
        ])
        facts = await service.list_all_facts(status="verified", domain="finance", limit=10)
        assert [f.id for f in facts] == ["f1"]
        assert facts[0].metadata["domain"] == "finance"

    @pytest.mark.asyncio
    async def test_list_all_facts_limit(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[
            {"metadata": {"id": f"f{i}", "fact": f"x{i}", "created_at": now}}
            for i in range(3)
        ])
        facts = await service.list_all_facts(limit=2)
        assert len(facts) == 2

    @pytest.mark.asyncio
    async def test_list_all_facts_parse_failure(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"metadata": {"id": "bad", "fact": "c", "verification_status": "verified",
                          "created_at": "not-a-date", "last_verified": None}},
        ])
        facts = await service.list_all_facts(limit=10)
        assert facts == []

    @pytest.mark.asyncio
    async def test_list_all_facts_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        assert await service.list_all_facts() == []

    @pytest.mark.asyncio
    async def test_get_fact_by_id(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[
            {"metadata": {"id": "f1", "fact": "a", "created_at": now}},
            {"metadata": {"id": "f2", "fact": "b", "created_at": now}},
        ])
        fact = await service.get_fact_by_id("f2")
        assert fact.id == "f2"

    @pytest.mark.asyncio
    async def test_get_fact_by_id_missing(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{"metadata": {"id": "other"}}])
        assert await service.get_fact_by_id("nope") is None

    @pytest.mark.asyncio
    async def test_get_fact_by_id_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        assert await service.get_fact_by_id("f1") is None


class TestRecallIntegrationExperiences:
    @pytest.mark.asyncio
    async def test_no_db(self):
        service, handler = make_service()
        handler.db = None
        assert await service.recall_integration_experiences("Finance", "stripe", "sync") == []

    @pytest.mark.asyncio
    async def test_recall_success(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[{
            "id": "e1",
            "text": "Task: integration_stripe_sync\nInput: Sync invoices\nOutcome: Success\nLearnings: works",
            "created_at": now,
            "metadata": {"agent_id": "a1", "task_type": "integration_stripe_sync", "outcome": "Success", "confidence_score": 0.9, "specialty": "payments"},
        }])
        exps = await service.recall_integration_experiences("Finance", "stripe", "sync")
        assert len(exps) == 1
        assert exps[0].task_type == "integration_stripe_sync"
        filter_arg = handler.search.call_args.kwargs["filter_str"]
        assert "stripe" in filter_arg and "''" not in filter_arg

    @pytest.mark.asyncio
    async def test_recall_escapes_quotes(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[])
        await service.recall_integration_experiences("Fi'nance", "stri'pe", "sync")
        assert "''" in handler.search.call_args.kwargs["filter_str"]

    @pytest.mark.asyncio
    async def test_recall_parse_error_skipped(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[{
            "id": "bad",
            "text": "no newlines",
            "created_at": "not-a-date",
            "metadata": {},
        }])
        exps = await service.recall_integration_experiences("Finance", "stripe", "sync")
        assert exps == []


class TestArchiveSession:
    @pytest.mark.asyncio
    async def test_no_messages(self):
        service, handler = make_service()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert await service.archive_session_to_cold_storage("conv-1") is False

    @pytest.mark.asyncio
    async def test_archive_success(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg, msg]
        handler.add_document = Mock(return_value=True)
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert await service.archive_session_to_cold_storage("conv-1") is True
        assert msg.metadata_json["_archived"] is True
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_archive_lancedb_failure(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        handler.add_document = Mock(return_value=False)
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert await service.archive_session_to_cold_storage("conv-1") is False

    @pytest.mark.asyncio
    async def test_archive_billing_failure_ok(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert await service.archive_session_to_cold_storage("conv-1") is True

    @pytest.mark.asyncio
    async def test_archive_billing_success(self):
        import sys
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        billing = type(sys.modules[__name__])("core", "acu_billing_service")
        billing.ACUBillingService = Mock(return_value=Mock(record_system_consumption=Mock()))
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            with patch.dict("sys.modules", {"core.acu_billing_service": billing}):
                assert await service.archive_session_to_cold_storage("conv-1") is True

    @pytest.mark.asyncio
    async def test_archive_commit_failure(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        mock_db.commit = Mock(side_effect=RuntimeError("commit down"))
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert await service.archive_session_to_cold_storage("conv-1") is True
        mock_db.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_archive_exception(self):
        service, handler = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert await service.archive_session_to_cold_storage("conv-1") is False

    @pytest.mark.asyncio
    async def test_cleanup_no_messages(self):
        service, handler = make_service()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.archive_session_to_cold_storage_with_cleanup("conv-1")
        assert result["status"] == "failed"
        assert result["error"] == "No messages found"

    @pytest.mark.asyncio
    async def test_cleanup_lancedb_fail(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        handler.add_document = Mock(return_value=False)
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.archive_session_to_cold_storage_with_cleanup("conv-1")
        assert result["archived"] is False
        assert "Failed to archive" in result["error"]

    @pytest.mark.asyncio
    async def test_cleanup_verify_fail(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        handler.add_document = Mock(return_value=True)
        handler.search = Mock(return_value=[])
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.archive_session_to_cold_storage_with_cleanup("conv-1")
        assert result["archived"] is True
        assert "Verification failed" in result["error"]

    @pytest.mark.asyncio
    async def test_cleanup_success(self):
        service, handler = make_service()
        msg = Mock(role="user", content="hi", metadata_json=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg]
        handler.add_document = Mock(return_value=True)
        handler.search = Mock(return_value=[{"id": "x"}])
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.archive_session_to_cold_storage_with_cleanup(
                "conv-1", retention_days=7, verify_before_delete=True
            )
        assert result["status"] == "success"
        assert result["soft_deleted"] is True
        assert msg.metadata_json["_retention_until"]
        assert result["scheduled_for_hard_delete"]

    @pytest.mark.asyncio
    async def test_cleanup_exception(self):
        service, handler = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.archive_session_to_cold_storage_with_cleanup("conv-1")
        assert result["status"] == "failed"
        assert "boom" not in result["error"]

    @pytest.mark.asyncio
    async def test_recover_no_messages(self):
        service, handler = make_service()
        mock_db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = []
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.recover_archived_session("conv-1")
        assert result["status"] == "failed"
        assert "No archived messages" in result["error"]

    @pytest.mark.asyncio
    async def test_recover_success(self):
        service, handler = make_service()
        msg = Mock(metadata_json={"_archived": True})
        mock_db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = [msg]
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.recover_archived_session("conv-1")
        assert result["status"] == "success"
        assert result["recovered_count"] == 1
        assert msg.metadata_json["_recovered"] is True
        assert "_archived" not in msg.metadata_json

    @pytest.mark.asyncio
    async def test_recover_exception(self):
        service, handler = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.recover_archived_session("conv-1")
        assert result["status"] == "failed"
        assert "boom" not in result["error"]

    @pytest.mark.asyncio
    async def test_hard_delete_none_past_retention(self):
        service, handler = make_service()
        mock_db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = []
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.hard_delete_archived_sessions(older_than_days=30)
        assert result["status"] == "success"
        assert result["deleted_count"] == 0

    @pytest.mark.asyncio
    async def test_hard_delete_retention_past(self):
        service, handler = make_service()
        msg = Mock(conversation_id="c1", metadata_json={"_retention_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()})
        mock_db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = [msg]
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.hard_delete_archived_sessions(older_than_days=30)
        assert result["deleted_count"] == 1
        mock_db.delete.assert_called_with(msg)

    @pytest.mark.asyncio
    async def test_hard_delete_created_at_fallback(self):
        service, handler = make_service()
        msg = Mock(conversation_id="c1", created_at=datetime.now(timezone.utc) - timedelta(days=60), metadata_json={})
        mock_db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = [msg]
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.hard_delete_archived_sessions(older_than_days=30)
        assert result["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_hard_delete_exception(self):
        service, handler = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.hard_delete_archived_sessions()
        assert result["status"] == "failed"
        assert "boom" not in result["error"]


def exp_result(text, meta, score=0.5, created=None, exp_id="e1"):
    return {
        "id": exp_id,
        "text": text,
        "created_at": created or datetime.now(timezone.utc).isoformat(),
        "metadata": meta,
        "score": score,
    }


class TestRecallExperiences:
    @pytest.mark.asyncio
    async def test_recall_full(self):
        service, handler = make_service()
        agent = Mock(id="agent-1", category="Finance")
        now = datetime.now(timezone.utc).isoformat()
        exp_results = [
            exp_result(
                "Task: t\nInput: Reconcile\nOutcome: Success\nLearnings: use ledger",
                {"agent_id": "agent-1", "agent_role": "Finance", "outcome": "Success",
                 "confidence_score": 0.9, "task_type": "recon", "feedback_score": 0.5,
                 "artifacts": ["a"], "specialty": "ap", "created_at": now},
                score=0.9,
            ),
            exp_result(
                "Task: t\nInput: Skip me\nOutcome: failed\nLearnings: x",
                {"agent_id": "agent-9", "agent_role": "Finance", "outcome": "failed", "confidence_score": 0.2},
                score=0.8,
            ),
            exp_result(
                "Task: t\nInput: Other role\nOutcome: Success\nLearnings: y",
                {"agent_id": "agent-9", "agent_role": "Ops", "outcome": "Success"},
                score=0.7,
            ),
        ]
        handler.search = Mock(side_effect=[
            exp_results,                       # experiences
            [{"id": "doc1", "text": "doc"}],   # documents
            [],                                # business facts
        ])
        formula_manager = Mock()
        formula_manager.search_formulas = Mock(return_value=[])
        hot_formula = Mock(id="hf1", name="sum", expression="=SUM(A1)", domain="Finance", description="d", parameters=[])
        conv_msg = Mock(role="user", content="hi", created_at=datetime.now(timezone.utc))
        mock_db = Mock()
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.side_effect = [[hot_formula], [conv_msg]]
        mock_db.query.return_value = query_mock
        episode_service = Mock()
        episode_service.retrieve_contextual = AsyncMock(return_value={"episodes": [{"id": "ep1"}]})
        graphrag = Mock()
        graphrag.get_context_for_ai = AsyncMock(return_value="graph-ctx")

        with patch("core.agent_world_model.SessionLocal", return_value=mock_db), \
             patch("core.graphrag_engine.graphrag_engine", graphrag), \
             patch("core.formula_memory.get_formula_manager", return_value=formula_manager), \
             patch("core.episode_retrieval_service.EpisodeRetrievalService", return_value=episode_service):
            result = await service.recall_experiences(agent, "reconcile invoices", limit=5)

        assert len(result["experiences"]) == 1
        assert result["experiences"][0].id == "e1"
        assert result["knowledge"] == [{"id": "doc1", "text": "doc"}]
        assert result["knowledge_graph"] == "graph-ctx"
        assert result["formulas"] and result["formulas"][0]["type"] == "formula_hot"
        assert result["conversations"][0]["role"] == "user"
        assert result["business_facts"] == []
        assert result["episodes"] == [{"id": "ep1", "canvas_context": [], "feedback_context": []}]

    @pytest.mark.asyncio
    async def test_recall_formula_hot_fallback_failure(self):
        service, handler = make_service()
        agent = Mock(id="agent-1", category="Finance")
        handler.search = Mock(return_value=[])
        formula_manager = Mock()
        formula_manager.search_formulas = Mock(return_value=[])
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("hot down")
        with patch("core.formula_memory.get_formula_manager", return_value=formula_manager), \
             patch("core.graphrag_engine.graphrag_engine", Mock(get_context_for_ai=AsyncMock(return_value=""))), \
             patch("core.episode_retrieval_service.EpisodeRetrievalService", side_effect=RuntimeError("no")), \
             patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = await service.recall_experiences(agent, "q")
        assert result["formulas"] == []

    @pytest.mark.asyncio
    async def test_recall_errors_tolerated(self):
        service, handler = make_service()
        agent = Mock(id="agent-1", category="Finance")
        handler.search = Mock(return_value=[])
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db), \
             patch("core.graphrag_engine.graphrag_engine", Mock(get_context_for_ai=AsyncMock(side_effect=RuntimeError("g")))), \
             patch("core.formula_memory.get_formula_manager", side_effect=RuntimeError("f")), \
             patch("core.episode_retrieval_service.EpisodeRetrievalService", side_effect=RuntimeError("e")):
            result = await service.recall_experiences(agent, "q")
        assert result["experiences"] == []
        assert result["knowledge"] == []
        assert result["knowledge_graph"] == ""
        assert result["conversations"] == []

    @pytest.mark.asyncio
    async def test_recall_formula_results(self):
        service, handler = make_service()
        agent = Mock(id="agent-1", category="general")
        handler.search = Mock(return_value=[])
        formula_manager = Mock()
        formula_manager.search_formulas = Mock(return_value=[
            {"id": "f1", "name": "n", "expression": "e", "domain": "d", "use_case": "u", "parameters": []}
        ])
        with patch("core.formula_memory.get_formula_manager", return_value=formula_manager), \
             patch("core.graphrag_engine.graphrag_engine", Mock(get_context_for_ai=AsyncMock(return_value=""))), \
             patch("core.episode_retrieval_service.EpisodeRetrievalService", side_effect=RuntimeError("no")):
            result = await service.recall_experiences(agent, "q")
        assert result["formulas"][0]["type"] == "formula"


class TestEpisodes:
    @pytest.mark.asyncio
    async def test_record_episode(self):
        service, handler = make_service()
        ok = await service.record_episode(
            episode_id="ep1", agent_id="a1", tenant_id="t1", task_description="do it",
            outcome="success", learnings="l", agent_role="Finance",
            maturity_at_time="INTERN", constitutional_score=1.0,
            human_intervention_count=2, confidence_score=0.7, metadata={"canvas_id": "c1"},
        )
        assert ok is True
        _, kwargs = handler.add_document.call_args
        assert kwargs["table_name"] == "agent_episodes"
        assert kwargs["metadata"]["type"] == "episode"
        assert kwargs["metadata"]["canvas_id"] == "c1"
        assert "Constitutional Score: 1.00" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_sync_episode_to_lancedb(self):
        service, handler = make_service()
        ok = await service.sync_episode_to_lancedb(
            episode_id="ep1", agent_id="a1", tenant_id="t1", task_description="d",
            outcome="s", learnings="l", agent_role="r", maturity_at_time="m",
        )
        assert ok is True

    @pytest.mark.asyncio
    async def test_recall_episodes_basic(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[
            {
                "id": "e1", "score": 0.8,
                "text": "Episode: reconcile\nOutcome: success\nLearnings: use ledger\nMaturity: INTERN",
                "metadata": {
                    "agent_role": "Finance", "agent_id": "a1", "type": "episode",
                    "episode_id": "ep1", "outcome": "success", "maturity_at_time": "INTERN",
                    "constitutional_score": 1.0, "human_intervention_count": 0,
                    "confidence_score": 0.8, "canvas_id": "c1", "feedback_score": 0.9,
                },
            },
            {"id": "e2", "score": 0.6, "text": "Episode: x\nOutcome: y",
             "metadata": {"agent_role": "Ops", "type": "episode", "episode_id": "ep2"}},
            {"id": "e3", "score": 0.9, "text": "Episode: z",
             "metadata": {"agent_role": "Finance", "agent_id": "other", "type": "episode", "episode_id": "ep3"}},
            {"id": "e4", "score": 0.7, "text": "Episode: w",
             "metadata": {"agent_role": "Finance", "agent_id": "a1", "type": "not_episode", "episode_id": "ep4"}},
        ])
        episodes = await service.recall_episodes(
            "reconcile", "Finance", agent_id="a1", canvas_id="c1",
            min_feedback_score=0.5, limit=10,
        )
        assert len(episodes) == 1
        ep = episodes[0]
        assert ep["episode_id"] == "ep1"
        assert ep["canvas_boost"] == 0.3
        assert ep["feedback_boost"] == 0.2
        assert ep["final_score"] == pytest.approx(0.8 + 0.3 + 0.2)
        assert ep["task_description"] == "reconcile"

    @pytest.mark.asyncio
    async def test_recall_episodes_penalties(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"id": "e1", "score": 0.5, "text": "Episode: a\nLearnings: x",
             "metadata": {"agent_role": "Finance", "type": "episode", "episode_id": "ep1",
                          "canvas_id": "c2", "feedback_score": -0.9, "outcome": "fail"}},
            {"id": "e2", "score": 0.5, "text": "Episode: b",
             "metadata": {"agent_role": "Finance", "type": "episode", "episode_id": "ep2", "feedback_score": 0.0}},
        ])
        episodes = await service.recall_episodes("q", "Finance", canvas_id="c1", limit=10)
        by_id = {e["episode_id"]: e for e in episodes}
        assert len(episodes) == 2
        assert by_id["ep1"]["canvas_boost"] == -0.05
        assert by_id["ep1"]["feedback_boost"] == -0.3

    @pytest.mark.asyncio
    async def test_recall_episodes_min_feedback_filter(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"id": "e1", "score": 0.5, "text": "Episode: a",
             "metadata": {"agent_role": "Finance", "type": "episode", "episode_id": "ep1",
                          "feedback_score": 0.1, "outcome": "s"}},
        ])
        episodes = await service.recall_episodes("q", "Finance", min_feedback_score=0.5, limit=10)
        assert episodes == []

    @pytest.mark.asyncio
    async def test_recall_episodes_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        assert await service.recall_episodes("q", "Finance") == []


class TestRecallExperiencesWithDetail:
    @pytest.mark.asyncio
    async def test_agent_id_path(self):
        service, _ = make_service()
        episode_service = Mock()
        episode_service.recall_episodes_with_detail = AsyncMock(return_value=[
            {"id": "ep1", "task_description": "task", "presentation_summary": "p", "outcome": "success"}
        ])
        with patch("core.episode_service.EpisodeService", return_value=episode_service):
            result = await service.recall_experiences_with_detail(
                "t1", "Finance", "task", detail_level=DetailLevel.FULL, agent_id="a1", limit=5
            )
        assert result[0]["episode_id"] == "ep1"
        assert result[0]["detail_level"] == "full"

    @pytest.mark.asyncio
    async def test_full_semantic_path(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[])
        result = await service.recall_experiences_with_detail(
            "t1", "Finance", "task", detail_level=DetailLevel.FULL, limit=5
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_summary_sql_path(self):
        service, _ = make_service()
        row = Mock(_mapping={"id": "ep1", "task_description": "t", "outcome": "s", "success": True})
        session = Mock()
        session.execute.return_value.fetchall.return_value = [row]
        with patch("core.database.SessionLocal", return_value=session):
            result = await service.recall_experiences_with_detail(
                "t1", "Finance", "task", detail_level=DetailLevel.SUMMARY, limit=5
            )
        assert result[0]["id"] == "ep1"
        session.close.assert_called()

    @pytest.mark.asyncio
    async def test_standard_sql_path(self):
        service, _ = make_service()
        row = Mock(_mapping={"id": "ep1", "task_description": "t", "outcome": "s"})
        session = Mock()
        session.execute.return_value.fetchall.return_value = [row]
        with patch("core.database.SessionLocal", return_value=session):
            result = await service.recall_experiences_with_detail(
                "t1", "Finance", "task", detail_level=DetailLevel.STANDARD, limit=5
            )
        sql = session.execute.call_args.args[0].text
        assert "visual_elements" in sql

    def test_format_episodes(self):
        service, _ = make_service()
        episodes = [{"id": "e1", "task_description": "x" * 100, "presentation_summary": "p",
                     "outcome": "s", "visual_elements": "v", "audit_trail": "a"}]
        for level in [DetailLevel.SUMMARY, DetailLevel.STANDARD, DetailLevel.FULL]:
            out = service._format_episodes_as_experiences(episodes, level)
            assert out[0]["detail_level"] == level.value
            if level == DetailLevel.SUMMARY:
                assert "visual_elements" not in out[0]
            if level == DetailLevel.FULL:
                assert out[0]["audit_trail"] == "a"

    @pytest.mark.asyncio
    async def test_archive_episode_to_cold_storage(self):
        service, handler = make_service()
        handler.add_document = Mock(return_value=True)
        assert await service.archive_episode_to_cold_storage(
            episode_id="e1", agent_id="a1", tenant_id="t1", task_description="d",
            outcome="s", learnings="l", agent_role="r", maturity_at_time="m",
        ) is True

    @pytest.mark.asyncio
    async def test_archive_episode_failure(self):
        service, handler = make_service()
        handler.add_document = Mock(return_value=False)
        assert await service.archive_episode_to_cold_storage(
            episode_id="e1", agent_id="a1", tenant_id="t1", task_description="d",
            outcome="s", learnings="l", agent_role="r", maturity_at_time="m",
        ) is False

    @pytest.mark.asyncio
    async def test_archive_episode_exception(self):
        service, handler = make_service()
        handler.add_document = Mock(side_effect=RuntimeError("boom"))
        assert await service.archive_episode_to_cold_storage(
            episode_id="e1", agent_id="a1", tenant_id="t1", task_description="d",
            outcome="s", learnings="l", agent_role="r", maturity_at_time="m",
        ) is False


class TestRecentEpisodesAndFeedback:
    @pytest.mark.asyncio
    async def test_get_recent_episodes(self):
        service, _ = make_service()
        ep = Mock(id="ep1", task_description="t", outcome="success", success=True,
                  maturity_at_time="INTERN", constitutional_score=1.0,
                  human_intervention_count=0, confidence_score=0.8, step_efficiency=1.0,
                  started_at=datetime.now(timezone.utc), completed_at=None)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [ep]
        with patch("core.database.SessionLocal", return_value=mock_db):
            result = await service.get_recent_episodes("a1", "t1")
        assert result[0]["episode_id"] == "ep1"
        assert result[0]["completed_at"] is None

    @pytest.mark.asyncio
    async def test_get_recent_episodes_exception(self):
        service, _ = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.database.SessionLocal", return_value=mock_db):
            assert await service.get_recent_episodes("a1", "t1") == []

    @pytest.mark.asyncio
    async def test_get_episode_feedback_empty(self):
        service, _ = make_service()
        assert service.get_episode_feedback_for_decision([]) == {}

    @pytest.mark.asyncio
    async def test_get_episode_feedback(self):
        service, _ = make_service()
        fb = Mock(episode_id="ep1", id="fb1", feedback_score=0.9, feedback_notes="n",
                  feedback_category="c", provider_id="p1", provider_type="human",
                  provided_at=datetime.now(timezone.utc))
        fb2 = Mock(episode_id="ep1", id="fb2", feedback_score=0.2, feedback_notes=None,
                   feedback_category=None, provider_id="p2", provider_type="agent",
                   provided_at=datetime.now(timezone.utc))
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = [fb, fb2]
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            result = service.get_episode_feedback_for_decision(["ep1"])
        assert len(result["ep1"]) == 2

    @pytest.mark.asyncio
    async def test_get_episode_feedback_exception(self):
        service, _ = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert service.get_episode_feedback_for_decision(["ep1"]) == {}


class TestSkillRecommendation:
    def test_agent_not_found(self):
        service, _ = make_service()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert service.recommend_skills_for_task("task", "a1", "t1") == []

    def test_success_path(self):
        service, _ = make_service()
        agent = Mock(category="Finance")
        skill = Mock()
        skill.name = "Skill One"
        episode_result = {
            "episode_id": "ep1", "outcome": "success", "similarity_score": 0.9,
            "final_score": 0.9, "metadata": {"skill_type": "openclaw", "skill_id": "sk1"},
        }
        past_ep = Mock(success=True, completed_at=datetime.now(timezone.utc))
        past_ep2 = Mock(success=False, completed_at=None)
        q = Mock()
        q.filter.return_value = q
        q.first.side_effect = [agent, skill]
        q.all.return_value = [past_ep, past_ep2]
        mock_db = Mock()
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            with patch.object(service, "recall_episodes", new=AsyncMock(return_value=[episode_result])):
                recs = service.recommend_skills_for_task("task", "a1", "t1", limit=5)
        assert len(recs) == 1
        assert recs[0].skill_name == "Skill One"
        assert recs[0].execution_count == 2
        assert recs[0].success_rate == 0.5

    def test_no_skill_episodes(self):
        service, _ = make_service()
        agent = Mock(category="Finance")
        mock_db = Mock()
        mock_db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=agent)))),
        ]
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            with patch.object(service, "recall_episodes", new=AsyncMock(return_value=[])):
                assert service.recommend_skills_for_task("task", "a1", "t1") == []

    def test_exception(self):
        service, _ = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert service.recommend_skills_for_task("task", "a1", "t1") == []

    def test_recall_failure_path(self):
        service, _ = make_service()
        agent = Mock(category="Finance")
        q = Mock()
        q.filter.return_value = q
        q.first.return_value = agent
        q.all.return_value = []
        mock_db = Mock()
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            with patch.object(service, "recall_episodes", new=AsyncMock(side_effect=RuntimeError("recall down"))):
                assert service.recommend_skills_for_task("task", "a1", "t1") == []

    def test_new_event_loop_path(self):
        service, _ = make_service()
        agent = Mock(category="Finance")
        skill = Mock()
        skill.name = "Skill"
        q = Mock()
        q.filter.return_value = q
        q.first.side_effect = [agent, skill]
        q.all.return_value = [Mock(success=True, completed_at=datetime.now(timezone.utc))]
        mock_db = Mock()
        mock_db.query.return_value = q
        episode_result = {
            "episode_id": "ep1", "outcome": "success", "similarity_score": 0.9,
            "final_score": 0.9, "metadata": {"skill_type": "openclaw", "skill_id": "sk1"},
        }
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db), \
             patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")), \
             patch.object(service, "recall_episodes", new=AsyncMock(return_value=[episode_result])):
            recs = service.recommend_skills_for_task("task", "a1", "t1", limit=5)
        assert len(recs) == 1

    def test_get_successful_skills(self):
        service, _ = make_service()
        ep = Mock(metadata_json={"skill_type": "openclaw", "skill_id": "sk1"})
        ep2 = Mock(metadata_json={"skill_type": "openclaw"})
        ep3 = Mock(metadata_json=None)
        mock_db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.limit.return_value = q
        q.all.return_value = [ep, ep2, ep3]
        mock_db.query.return_value = q
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert service.get_successful_skills_for_agent("a1", "t1") == {"sk1"}

    def test_get_successful_skills_exception(self):
        service, _ = make_service()
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("boom")
        with patch("core.agent_world_model.SessionLocal", return_value=mock_db):
            assert service.get_successful_skills_for_agent("a1", "t1") == set()


class TestCanvasAware:
    @pytest.mark.asyncio
    async def test_recall_experiences_with_canvas(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[
            {"id": "e1", "metadata": {"agent_id": "a1", "task_type": "t", "input_summary": "i",
                                      "outcome": "Success", "learnings": "l", "confidence_score": 0.8,
                                      "feedback_score": 0.5, "artifacts": [], "step_efficiency": 1.0,
                                      "trace": {}, "agent_role": "Finance", "specialty": None,
                                      "canvas_types": ["sheets"], "timestamp": now}},
            {"id": "e2", "metadata": {"agent_id": "a1", "outcome": "Success", "canvas_types": ["docs"]}},
            {"id": "e3", "metadata": {"agent_id": "a2", "outcome": "Success", "canvas_types": ["sheets"]}},
            {"id": "e4", "metadata": {"agent_id": "a1", "outcome": "Failure", "canvas_types": ["sheets"]}},
        ])
        exps = await service.recall_experiences_with_canvas("a1", "task", preferred_canvas_type="sheets", limit=10)
        assert len(exps) == 1
        assert exps[0].id == "e1"

    @pytest.mark.asyncio
    async def test_recall_experiences_with_canvas_limit_and_exception(self):
        service, handler = make_service()
        now = datetime.now(timezone.utc).isoformat()
        handler.search = Mock(return_value=[
            {"id": f"e{i}", "metadata": {"agent_id": "a1", "outcome": "Success", "timestamp": now}}
            for i in range(5)
        ])
        exps = await service.recall_experiences_with_canvas("a1", "task", limit=2)
        assert len(exps) == 2
        handler.search = Mock(side_effect=RuntimeError("boom"))
        assert await service.recall_experiences_with_canvas("a1", "task") == []

    @pytest.mark.asyncio
    async def test_get_canvas_type_preferences(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"metadata": {"agent_id": "a1", "canvas_types": ["sheets", "charts"],
                          "outcome": "success", "feedback_score": 1.0, "engagement_time_seconds": 60.0}},
            {"metadata": {"agent_id": "a1", "canvas_types": ["sheets"],
                          "outcome": "failed", "feedback_score": 0.0, "engagement_time_seconds": 10.0}},
            {"metadata": {"agent_id": "a2", "canvas_types": ["sheets"], "outcome": "success"}},
        ])
        prefs = await service.get_canvas_type_preferences("a1", task_type="reporting")
        assert prefs["sheets"]["count"] == 2
        assert prefs["sheets"]["success_rate"] == 0.5
        assert prefs["charts"]["count"] == 1

    @pytest.mark.asyncio
    async def test_get_canvas_type_preferences_exception(self):
        service, handler = make_service()
        handler.search = Mock(side_effect=RuntimeError("boom"))
        assert await service.get_canvas_type_preferences("a1") == {}

    @pytest.mark.asyncio
    async def test_recommend_canvas_type_no_preferences(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[])
        rec = await service.recommend_canvas_type("a1", "reporting")
        assert rec["canvas_type"] == "generic"
        assert rec["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_recommend_canvas_type_insufficient(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"metadata": {"agent_id": "a1", "canvas_types": ["sheets"], "outcome": "success"}},
        ])
        rec = await service.recommend_canvas_type("a1", "reporting")
        assert rec["canvas_type"] == "generic"

    @pytest.mark.asyncio
    async def test_recommend_canvas_type_success(self):
        service, handler = make_service()
        handler.search = Mock(return_value=[
            {"metadata": {"agent_id": "a1", "canvas_types": ["sheets"], "outcome": "success",
                          "feedback_score": 1.0, "engagement_time_seconds": 100.0}},
            {"metadata": {"agent_id": "a1", "canvas_types": ["sheets"], "outcome": "success",
                          "feedback_score": 0.8, "engagement_time_seconds": 50.0}},
            {"metadata": {"agent_id": "a1", "canvas_types": ["sheets"], "outcome": "success",
                          "feedback_score": 0.6, "engagement_time_seconds": 40.0}},
            {"metadata": {"agent_id": "a1", "canvas_types": ["charts"], "outcome": "failed",
                          "feedback_score": -1.0, "engagement_time_seconds": 5.0}},
        ])
        rec = await service.recommend_canvas_type("a1", "reporting", "describe")
        assert rec["canvas_type"] == "sheets"
        assert rec["confidence"] <= 0.95
        assert rec["alternatives"] == []

    @pytest.mark.asyncio
    async def test_recommend_canvas_type_exception(self):
        service, _ = make_service()
        with patch.object(service, "get_canvas_type_preferences", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await service.recommend_canvas_type("a1", "reporting") is None

    @pytest.mark.asyncio
    async def test_record_canvas_outcome(self):
        service, handler = make_service()
        exp = make_experience(metadata_trace={}, feedback_score=None)
        ok = await service.record_canvas_outcome(exp, ["sheets", "charts"], 30.0, user_feedback=0.7)
        assert ok is True
        meta = handler.add_document.call_args.kwargs["metadata"]
        trace = meta["trace"]
        assert trace["canvas_types"] == ["sheets", "charts"]
        assert trace["canvas_count"] == 2
        assert trace["user_feedback"] == 0.7

    @pytest.mark.asyncio
    async def test_record_canvas_outcome_exception(self):
        service, handler = make_service()
        handler.add_document = Mock(side_effect=RuntimeError("boom"))
        ok = await service.record_canvas_outcome(make_experience(), ["sheets"])
        assert ok is False
