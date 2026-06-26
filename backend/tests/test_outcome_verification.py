# -*- coding: utf-8 -*-
"""
TDD tests for the two Reddit-critique fixes:

C1 — episodic retrieval outcome prefilter:
  - EpisodeSegmentationService._derive_outcome computes outcome from execs
  - EpisodeRetrievalService.retrieve_semantic accepts outcome param and
    passes it as a native LanceDB prefilter (not a similarity decision)
  - retrieve_failed_similar convenience entrypoint for self-correction

C2 — verified-outcome contract (silent no-op defense):
  - parse_tool_outcome: dict / JSON-string / plain-string / tri-state verified
  - AgentReasoningStep persists verified + verification_evidence
  - CapabilityGraduationService.record_usage gates on verified='verified'
    so silent no-ops can't inflate capability stats
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base
from core.tool_outcome_verifier import (
    FAILED_VERIFICATION,
    UNVERIFIED,
    VERIFIED,
    VerifiedOutcome,
    coerce_verified_for_storage,
    parse_tool_outcome,
)


# ===========================================================================
# C1a — _derive_outcome
# ===========================================================================
def _exec(status):
    """Build a fake AgentExecution with a given status string."""
    e = MagicMock()
    e.status = status
    return e


class TestDeriveOutcome:
    def test_all_succeeded(self):
        from core.episode_segmentation_service import EpisodeSegmentationService

        svc = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        assert svc._derive_outcome([_exec("completed"), _exec("completed")]) == "success"

    def test_any_failure(self):
        from core.episode_segmentation_service import EpisodeSegmentationService

        svc = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        assert svc._derive_outcome([_exec("completed"), _exec("failed")]) == "failure"

    def test_partial_when_max_steps(self):
        from core.episode_segmentation_service import EpisodeSegmentationService

        svc = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        # max_steps_exceeded is neither completed nor failed → partial
        assert svc._derive_outcome([_exec("max_steps_exceeded")]) == "partial"

    def test_empty_is_unknown(self):
        from core.episode_segmentation_service import EpisodeSegmentationService

        svc = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        assert svc._derive_outcome([]) == "unknown"


# ===========================================================================
# C1b — outcome prefilter in retrieve_semantic
# ===========================================================================
class TestOutcomePrefilter:
    @pytest.mark.asyncio
    async def test_filter_str_includes_outcome_when_set(self):
        from core.episode_retrieval_service import EpisodeRetrievalService

        svc = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        svc.lancedb = MagicMock()
        svc.lancedb.search = MagicMock(return_value=[])
        svc.governance = MagicMock()
        svc.governance.can_perform_action = MagicMock(
            return_value={"allowed": True}
        )
        svc.db = MagicMock()
        svc._log_access = AsyncMock()
        svc._serialize_episode = MagicMock()

        await svc.retrieve_semantic(
            agent_id="ag-1", query="deploy failed", outcome="failure"
        )

        call_kwargs = svc.lancedb.search.call_args.kwargs
        assert "outcome == 'failure'" in call_kwargs["filter_str"]
        assert "agent_id == 'ag-1'" in call_kwargs["filter_str"]

    @pytest.mark.asyncio
    async def test_no_outcome_when_not_set(self):
        from core.episode_retrieval_service import EpisodeRetrievalService

        svc = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        svc.lancedb = MagicMock()
        svc.lancedb.search = MagicMock(return_value=[])
        svc.governance = MagicMock()
        svc.governance.can_perform_action = MagicMock(
            return_value={"allowed": True}
        )
        svc.db = MagicMock()
        svc._log_access = AsyncMock()
        svc._serialize_episode = MagicMock()

        await svc.retrieve_semantic(agent_id="ag-1", query="anything")

        call_kwargs = svc.lancedb.search.call_args.kwargs
        assert "outcome" not in call_kwargs["filter_str"]

    @pytest.mark.asyncio
    async def test_retrieve_failed_similar_prefilters_failure(self):
        from core.episode_retrieval_service import EpisodeRetrievalService

        svc = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        svc.lancedb = MagicMock()
        svc.lancedb.search = MagicMock(return_value=[])
        svc.governance = MagicMock()
        svc.governance.can_perform_action = MagicMock(
            return_value={"allowed": True}
        )
        svc.db = MagicMock()
        svc._log_access = AsyncMock()
        svc._serialize_episode = MagicMock()

        await svc.retrieve_failed_similar(agent_id="ag-1", query="invoice 42")

        call_kwargs = svc.lancedb.search.call_args.kwargs
        assert "outcome == 'failure'" in call_kwargs["filter_str"]


# ===========================================================================
# C2 — parse_tool_outcome (the verification envelope)
# ===========================================================================
class TestParseToolOutcome:
    def test_dict_with_verified_true(self):
        o = parse_tool_outcome({"success": True, "verified": True, "evidence": "row id 7"})
        assert o.kind == VERIFIED
        assert o.success is True
        assert o.evidence == "row id 7"

    def test_dict_with_verified_false(self):
        o = parse_tool_outcome({"success": True, "verified": False})
        # explicit negative verification
        assert o.kind == FAILED_VERIFICATION
        assert o.success is True  # tool still self-reported success

    def test_dict_without_verified_is_unverified(self):
        o = parse_tool_outcome({"success": True})
        assert o.kind == UNVERIFIED
        assert o.success is True

    def test_explicit_success_false(self):
        o = parse_tool_outcome({"success": False})
        assert o.success is False
        assert o.kind == UNVERIFIED

    def test_json_string_with_single_quotes(self):
        # Tools commonly return str(dict) which uses single quotes
        o = parse_tool_outcome("{'success': True, 'verified': True}")
        assert o.kind == VERIFIED
        assert o.success is True

    def test_json_string_proper(self):
        o = parse_tool_outcome('{"success": true, "verified": true, "evidence": "ok"}')
        assert o.kind == VERIFIED
        assert o.evidence == "ok"

    def test_plain_string_unverified(self):
        o = parse_tool_outcome("Email sent successfully")
        assert o.kind == UNVERIFIED
        assert o.success is True  # truthy

    def test_none_observation(self):
        o = parse_tool_outcome(None)
        assert o.kind == UNVERIFIED
        assert o.success is False

    def test_evidence_as_dict_serialized(self):
        o = parse_tool_outcome({"success": True, "verified": True, "evidence": {"path": "/x"}})
        assert isinstance(o.evidence, str)
        assert "/x" in o.evidence

    def test_silent_no_op_classified_unverified(self):
        """The core critique: a no-op return with success=true but no evidence."""
        o = parse_tool_outcome({"success": True, "message": "Done!"})
        assert o.kind == UNVERIFIED  # NOT verified — cannot graduate on this
        assert o.is_verified is False

    def test_never_raises_on_garbage(self):
        o = parse_tool_outcome(object())
        assert o.kind == UNVERIFIED


class TestCoerceVerified:
    def test_valid_passes_through(self):
        assert coerce_verified_for_storage("verified") == "verified"
        assert coerce_verified_for_storage("unverified") == "unverified"
        assert coerce_verified_for_storage("failed_verification") == "failed_verification"

    def test_invalid_defaults_unverified(self):
        assert coerce_verified_for_storage("bogus") == "unverified"
        assert coerce_verified_for_storage(None) == "unverified"


# ===========================================================================
# C2b — graduation gating on verified
# ===========================================================================
@pytest.fixture()
def grad_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield Session
    engine.dispose()


def _seed_agent(db_session):
    """Seed an AgentRegistry with capability bookkeeping initialized."""
    from core.models import AgentRegistry

    agent = AgentRegistry(
        id="ag-grad",
        name="grad-agent",
        category="test",
        module_path="test.module",
        class_name="TestClass",
    )
    # Graduation stores capability stats under the `configuration` JSON column.
    agent.configuration = {"capability_stats": {}, "capability_maturities": {}}
    db_session.add(agent)
    db_session.commit()
    return agent


class TestGraduationVerifiedGating:
    def test_verified_success_increments_verified_counter(self, grad_db):
        from core.capability_graduation_service import (
            CapabilityGraduationService,
            CapabilityMaturityLevel,
        )
        from core.models import AgentRegistry

        with grad_db() as db:
            _seed_agent(db)
            svc = CapabilityGraduationService(db)
            svc.record_usage("ag-grad", "cap1", success=True, verified="verified")
            stats = db.query(AgentRegistry).get("ag-grad").configuration["capability_stats"]["cap1"]
            assert stats["verified_success"] == 1
            assert stats["success"] == 1
            assert stats["total"] == 1

    def test_unverified_success_does_not_increment_verified(self, grad_db):
        from core.capability_graduation_service import CapabilityGraduationService
        from core.models import AgentRegistry

        with grad_db() as db:
            _seed_agent(db)
            svc = CapabilityGraduationService(db)
            svc.record_usage("ag-grad", "cap1", success=True, verified="unverified")
            stats = db.query(AgentRegistry).get("ag-grad").configuration["capability_stats"]["cap1"]
            # self-reported success counts, but NOT verified_success
            assert stats["success"] == 1
            assert stats.get("verified_success", 0) == 0

    def test_graduation_only_promotes_on_verified(self, grad_db):
        """5 unverified successes must NOT promote from STUDENT."""
        from core.capability_graduation_service import (
            CapabilityGraduationService,
            CapabilityMaturityLevel,
        )
        from core.models import AgentRegistry

        with grad_db() as db:
            _seed_agent(db)
            svc = CapabilityGraduationService(db)
            for _ in range(10):  # well past the 5-success threshold
                svc.record_usage("ag-grad", "cap1", success=True, verified="unverified")
            maturity = svc.get_maturity("ag-grad", "cap1")
            assert maturity == CapabilityMaturityLevel.STUDENT  # still stuck

    def test_graduation_promotes_on_5_verified(self, grad_db):
        from core.capability_graduation_service import (
            CapabilityGraduationService,
            CapabilityMaturityLevel,
        )

        with grad_db() as db:
            _seed_agent(db)
            svc = CapabilityGraduationService(db)
            for _ in range(5):
                svc.record_usage("ag-grad", "cap1", success=True, verified="verified")
            assert svc.get_maturity("ag-grad", "cap1") == CapabilityMaturityLevel.INTERN

    def test_mixed_verified_and_unverified(self, grad_db):
        """Only the verified ones count toward the threshold."""
        from core.capability_graduation_service import (
            CapabilityGraduationService,
            CapabilityMaturityLevel,
        )

        with grad_db() as db:
            _seed_agent(db)
            svc = CapabilityGraduationService(db)
            # 4 verified + 20 unverified — should NOT promote (need 5 verified)
            for _ in range(4):
                svc.record_usage("ag-grad", "cap1", success=True, verified="verified")
            for _ in range(20):
                svc.record_usage("ag-grad", "cap1", success=True, verified="unverified")
            assert svc.get_maturity("ag-grad", "cap1") == CapabilityMaturityLevel.STUDENT

    def test_failed_verification_does_not_increment_verified(self, grad_db):
        from core.capability_graduation_service import CapabilityGraduationService
        from core.models import AgentRegistry

        with grad_db() as db:
            _seed_agent(db)
            svc = CapabilityGraduationService(db)
            svc.record_usage(
                "ag-grad", "cap1",
                success=True,  # tool claimed success
                verified="failed_verification",  # but verify() rejected it
            )
            stats = db.query(AgentRegistry).get("ag-grad").configuration["capability_stats"]["cap1"]
            assert stats.get("verified_success", 0) == 0


# ===========================================================================
# AgentReasoningStep verified persistence (schema)
# ===========================================================================
class TestReasoningStepVerifiedColumn:
    def test_step_persists_verified_state(self, grad_db):
        from core.models import AgentReasoningStep, AgentExecution, ExecutionStatus

        with grad_db() as db:
            # AgentExecution FK is required
            exec_row = AgentExecution(
                id="exec-1",
                agent_id="ag-grad",
                status=ExecutionStatus.COMPLETED.value,
            )
            db.add(exec_row)
            db.commit()

            step = AgentReasoningStep(
                id="step-1",
                execution_id="exec-1",
                step_number=1,
                step_type="action",
                observation="done",
                verified="verified",
                verification_evidence="row id 42",
            )
            db.add(step)
            db.commit()

            row = db.get(AgentReasoningStep, "step-1")
            assert row.verified == "verified"
            assert row.verification_evidence == "row id 42"

    def test_step_defaults_unverified(self, grad_db):
        from core.models import AgentReasoningStep, AgentExecution, ExecutionStatus

        with grad_db() as db:
            exec_row = AgentExecution(
                id="exec-2",
                agent_id="ag-grad",
                status=ExecutionStatus.COMPLETED.value,
            )
            db.add(exec_row)
            db.commit()

            step = AgentReasoningStep(
                id="step-2",
                execution_id="exec-2",
                step_number=1,
                step_type="action",
                observation="x",
            )
            db.add(step)
            db.commit()

            row = db.get(AgentReasoningStep, "step-2")
            assert row.verified == "unverified"
