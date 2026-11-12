"""
P3 — Postcondition oracle + two-tier confidence (W2).

Two concerns:
1. Oracle: a mutating tool that lies ({verified:true} but the DB didn't change)
   is caught by the postcondition re-read (Postcept: never grade your own work).
2. Two-tier confidence: INTERNAL_HIGH is NOT credible; only EXTERNAL_VERIFIED is.
   coerce_match_level_for_storage defaults to AMBIGUOUS (RN3), and the new
   external tiers pass through unchanged.
"""
from contextlib import contextmanager
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Workflow, WorkflowExecution
from core.oracle.request_expectations import build_request_expectations
from core.workflow_engine import EXECUTION_SCOPE_KEY
from core.selector_confidence_service import (
    MatchConfidence, EXTERNAL_VERIFIED, EXTERNAL_REFUTED, NEEDS_EXTERNAL_VALIDATION,
    HIGH, PARTIAL, AMBIGUOUS, _VALID_LEVELS, coerce_match_level_for_storage,
)


@pytest.fixture()
def workflow_store():
    """Scratch SQLite store for trigger-workflow execution binding."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    Workflow.__table__.create(engine)
    WorkflowExecution.__table__.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    try:
        yield _session
    finally:
        engine.dispose()


def _trigger_expected(workflow_id="wf-1", input_data=None,
                      workspace_id="ws-1", tenant_id="tenant-1",
                      operation_id="exec-1"):
    return build_request_expectations(
        "trigger_workflow",
        {"workflow_id": workflow_id, "input_data": input_data or {}},
        operation_id=operation_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_id="user-1",
        agent_id="agent-1",
    )


def _seed_definition(db, workflow_id="wf-1", status="active"):
    row = Workflow(
        id=workflow_id, name=f"Workflow {workflow_id}",
        tenant_id="tenant-1", status=status)
    db.add(row)
    db.commit()
    return row


def _seed_execution(db, execution_id="exec-1", workflow_id="wf-1", *,
                    input_data=None, scope=None, status="RUNNING"):
    payload = dict(input_data or {})
    if scope is not None:
        payload[EXECUTION_SCOPE_KEY] = scope
    row = WorkflowExecution(
        execution_id=execution_id, workflow_id=workflow_id,
        status=status, input_data=json.dumps(payload))
    db.add(row)
    db.commit()
    return row


def _trigger_ctx(db, expected, execution_id="exec-1", workflow_id="wf-1"):
    return {
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "db": db,
        **expected,
    }


# ---------------------------------------------------------------------------
# Two-tier confidence (P3c)
# ---------------------------------------------------------------------------
def test_internal_high_is_not_credible():
    """The Stanford credibility gate: internal self-assessment ≠ trustworthy."""
    mc = MatchConfidence(level=HIGH, score=0.9, rationale="x", provenance="internal")
    assert mc.is_high is True
    assert mc.is_credible is False, "INTERNAL_HIGH must NOT be auto-proceed-trusted"
    assert mc.needs_external_validation is True


def test_external_verified_is_credible():
    mc = MatchConfidence(
        level=EXTERNAL_VERIFIED, score=0.9, rationale="oracle re-derived",
        provenance="oracle", external_score=0.95, external_evidence="DB read-back",
    )
    assert mc.is_credible is True
    assert mc.needs_external_validation is False


def test_external_tiers_are_valid_levels():
    """RN3: the new tiers must be in _VALID_LEVELS (else coerce silently mangles them)."""
    assert NEEDS_EXTERNAL_VALIDATION in _VALID_LEVELS
    assert EXTERNAL_VERIFIED in _VALID_LEVELS
    assert EXTERNAL_REFUTED in _VALID_LEVELS


def test_coerce_defaults_to_ambiguous_not_partial():
    """RN3: AMBIGUOUS (route-to-human) is the safe default, not PARTIAL."""
    assert coerce_match_level_for_storage(None) == AMBIGUOUS
    assert coerce_match_level_for_storage("garbage") == AMBIGUOUS


def test_coerce_passes_new_tiers_through():
    assert coerce_match_level_for_storage(EXTERNAL_VERIFIED) == EXTERNAL_VERIFIED
    assert coerce_match_level_for_storage(NEEDS_EXTERNAL_VALIDATION) == NEEDS_EXTERNAL_VALIDATION


# ---------------------------------------------------------------------------
# Postcondition oracle (P3a)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_oracle_catches_lying_tool(monkeypatch, workflow_store):
    """Experiment 1: an active definition without an execution is refuted."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.oracle import validate

    expected = _trigger_expected(workflow_id="wf-ghost",
                                 operation_id="exec-ghost")
    with workflow_store() as db:
        # The definition is active, but no execution row was committed.
        _seed_definition(db, workflow_id="wf-ghost")
        result = await validate(
            "trigger_workflow",
            _trigger_ctx(db, expected, execution_id="exec-ghost",
                         workflow_id="wf-ghost"))

    assert result is not None
    assert result.verified is False
    assert "not committed" in result.evidence


@pytest.mark.asyncio
async def test_oracle_confirms_real_effect(monkeypatch, workflow_store):
    """A committed execution bound to the request/scope → oracle confirms."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.oracle import validate

    expected = _trigger_expected()
    with workflow_store() as db:
        _seed_definition(db)
        _seed_execution(
            db, input_data={},
            scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"},
            status="COMPLETED")
        result = await validate("trigger_workflow", _trigger_ctx(db, expected))

    assert result is not None
    assert result.verified is True, result.evidence
    assert "exec-1" in result.evidence


@pytest.mark.asyncio
async def test_oracle_returns_none_for_unregistered_action():
    """Non-mutating actions have no postcondition → self-report stands."""
    from core.oracle import validate
    result = await validate("documents.search", {})
    assert result is None


# ---------------------------------------------------------------------------
# attach_tiebreak — stop promotion at INTERNAL_HIGH (P3c)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_attach_tiebreak_promotes_to_bridge_not_internal_high(monkeypatch):
    """An LLM pick is still internal self-assessment → bridge state, NOT HIGH.

    Promoting PARTIAL to plain INTERNAL_HIGH would launder credibility
    (plan H5) — the auto-proceed gate only trusts EXTERNAL_VERIFIED.
    """
    from core.selector_confidence_service import attach_tiebreak, MatchConfidence
    from types import SimpleNamespace

    partial = MatchConfidence(
        level=PARTIAL, score=0.72, rationale="2 matches",
        candidates=[], chosen_index=-1, provenance="internal",
    )
    fake_result = SimpleNamespace(used_llm=True, chosen_index=0, rationale="picked #2")

    async def _fake_break_tie(candidates, page_context, llm_service):
        return fake_result

    monkeypatch.setattr(
        "core.llm.match_confidence_tiebreaker.break_tie", _fake_break_tie
    )

    promoted = await attach_tiebreak(partial, {"url": "x"}, object())
    assert promoted.level == NEEDS_EXTERNAL_VALIDATION
    assert promoted.is_high is False, "promoted LLM pick must not read as HIGH"
    assert promoted.is_credible is False
    assert promoted.requires_review is True, "bridge state must route to review"
    assert promoted.provenance == "internal"
    assert promoted.chosen_index == 0


def test_bridge_state_routes_to_review():
    """NEEDS_EXTERNAL_VALIDATION is in the requires_review set (never auto-proceed)."""
    mc = MatchConfidence(
        level=NEEDS_EXTERNAL_VALIDATION, score=0.72, rationale="llm tiebreak",
        provenance="internal",
    )
    assert mc.requires_review is True
    assert mc.needs_external_validation is True
    assert mc.is_credible is False


# ---------------------------------------------------------------------------
# verify-before-retry (P3b, arXiv 2608.02645)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_verify_before_retry_flag_off_returns_false(monkeypatch):
    """Kill-switch parity: flag off → never blocks a retry."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "false")
    from core.oracle import verify_before_retry
    assert await verify_before_retry("trigger_workflow", {"workflow_id": "wf-1"}) is False


@pytest.mark.asyncio
async def test_verify_before_retry_effect_landed_blocks_retry(
        monkeypatch, workflow_store):
    """Timeout but a bound execution landed → do NOT retry (no duplicate)."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.oracle import verify_before_retry

    expected = _trigger_expected()
    with workflow_store() as db:
        _seed_definition(db)
        _seed_execution(
            db, input_data={},
            scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})
        landed = await verify_before_retry(
            "trigger_workflow", _trigger_ctx(db, expected))

    assert landed is True


@pytest.mark.asyncio
async def test_verify_before_retry_effect_missing_allows_retry(
        monkeypatch, workflow_store):
    """Timeout and no committed execution → retry is correct."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    import core.oracle.postcondition_verifiers  # noqa: F401
    from core.oracle import verify_before_retry

    expected = _trigger_expected(workflow_id="wf-ghost",
                                 operation_id="exec-missing")
    with workflow_store() as db:
        _seed_definition(db, workflow_id="wf-ghost")
        landed = await verify_before_retry(
            "trigger_workflow",
            _trigger_ctx(db, expected, execution_id="exec-missing",
                         workflow_id="wf-ghost"))

    assert landed is False


@pytest.mark.asyncio
async def test_verify_before_retry_unregistered_action_returns_false(monkeypatch):
    """Non-mutating action has no postcondition → retry allowed (self-report stands)."""
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    from core.oracle import verify_before_retry
    assert await verify_before_retry("documents.search", {}) is False


# ---------------------------------------------------------------------------
# Provenance denormalization into BrowserAudit (P3c)
# ---------------------------------------------------------------------------
def test_browser_audit_denormalizes_confidence_provenance():
    """Audit rows carry match_level/provenance/score so INTERNAL_HIGH never
    reads as externally verified in audit/queries."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    import core.models  # noqa: F401  (register tables on Base.metadata)
    from core.audit_service import AuditService
    from core.models import BrowserAudit

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    aid = AuditService()._create_browser_audit_record(db, {
        "agent_id": "a1",
        "agent_execution_id": None,
        "user_id": "u1",
        "session_id": "s1",
        "action": "click",
        "metadata": {
            "match_confidence": {
                "level": NEEDS_EXTERNAL_VALIDATION,
                "provenance": "internal",
                "score": 0.72,
                "rationale": "llm tiebreak",
                "candidates": [],
                "chosen_index": 0,
                "external_score": None,
                "external_evidence": None,
            }
        },
    })

    row = db.query(BrowserAudit).filter(BrowserAudit.id == aid).first()
    assert row is not None
    assert row.match_level == NEEDS_EXTERNAL_VALIDATION
    assert row.match_confidence_provenance == "internal"
    assert row.match_confidence_score == 0.72
    assert row.external_validated_at is None


# ---------------------------------------------------------------------------
# Default-on oracle enforcement: _oracle_check stamps tool outcomes (W2)
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock
from types import SimpleNamespace


def _bare_agent():
    """A GenericAgent shell — _oracle_check only needs the class, not init."""
    from core.generic_agent import GenericAgent
    return GenericAgent.__new__(GenericAgent)


def _mock_db(first_value):
    """get_db_session()-style mock: `with m as db:` yields a configured db."""
    outer = MagicMock()
    inner = MagicMock()
    inner.query.return_value.filter.return_value.first.return_value = first_value
    outer.__enter__.return_value = inner
    outer.__exit__.return_value = False
    return outer


@pytest.mark.asyncio
async def test_oracle_check_stamps_refuted_string_result(
        monkeypatch, workflow_store):
    """Tool claims success but no execution committed → observation UNVERIFIED."""
    import core.oracle.postcondition_verifiers  # noqa: F401
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.delenv("ATOM_ORACLE_ENFORCE", raising=False)
    expected = _trigger_expected(workflow_id="wf-ghost",
                                 operation_id="exec-ghost")
    with workflow_store() as db:
        _seed_definition(db, workflow_id="wf-ghost")
    monkeypatch.setattr(ga, "get_db_session", workflow_store)

    agent = _bare_agent()
    out = await agent._oracle_check(
        "trigger_workflow",
        {"workflow_id": "wf-ghost", "execution_id": "exec-ghost"},
        "Workflow triggered OK", expected=expected,
    )
    assert "[ORACLE:UNVERIFIED" in out


@pytest.mark.asyncio
async def test_oracle_check_stamps_verified_dict_result(
        monkeypatch, workflow_store):
    """Committed execution in the DB → dict result gains oracle_verified=True."""
    import core.oracle.postcondition_verifiers  # noqa: F401
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.delenv("ATOM_ORACLE_ENFORCE", raising=False)
    expected = _trigger_expected()
    with workflow_store() as db:
        _seed_definition(db)
        _seed_execution(
            db, input_data={},
            scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})
    monkeypatch.setattr(ga, "get_db_session", workflow_store)

    agent = _bare_agent()
    out = await agent._oracle_check(
        "trigger_workflow",
        {"workflow_id": "wf-1", "input_data": {}},
        {"status": "ok", "execution_id": "exec-1"}, expected=expected,
    )
    assert out["oracle_verified"] is True
    assert out["oracle_evidence"]


@pytest.mark.asyncio
async def test_oracle_check_uses_result_fields_for_task_id(monkeypatch):
    """tasks.create: task_id lives in the RESULT, not the args — must be merged."""
    import core.oracle.postcondition_verifiers  # noqa: F401
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    db = _mock_db(SimpleNamespace(id="t-9", title="do it", board_id=None))
    monkeypatch.setattr(ga, "get_db_session", lambda: db)

    agent = _bare_agent()
    out = await agent._oracle_check(
        "tasks.create", {"title": "do it"}, {"task_id": "t-9", "created": True}
    )
    assert out["oracle_verified"] is True


@pytest.mark.asyncio
async def test_oracle_check_passthrough_for_unregistered_action():
    agent = _bare_agent()
    out = await agent._oracle_check("documents.search", {"q": "x"}, {"rows": []})
    assert out == {"rows": []}


@pytest.mark.asyncio
async def test_oracle_check_kill_switch(monkeypatch):
    """ATOM_ORACLE_ENFORCE=false reverts to pass-through even for registered actions."""
    import core.oracle.postcondition_verifiers  # noqa: F401
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "false")
    db = _mock_db(None)
    monkeypatch.setattr(ga, "get_db_session", lambda: db)

    agent = _bare_agent()
    out = await agent._oracle_check(
        "trigger_workflow", {"workflow_id": "wf-ghost"}, "Workflow triggered OK"
    )
    assert out == "Workflow triggered OK"


@pytest.mark.asyncio
async def test_oracle_check_never_blocks_on_error(monkeypatch):
    """DB blowing up must not corrupt the tool result."""
    import core.oracle.postcondition_verifiers  # noqa: F401
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")

    class _Boom:
        def __enter__(self):
            raise RuntimeError("db down")
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ga, "get_db_session", lambda: _Boom())
    agent = _bare_agent()
    out = await agent._oracle_check(
        "trigger_workflow", {"workflow_id": "wf-1"}, {"status": "ok"}
    )
    assert out == {"status": "ok"}
