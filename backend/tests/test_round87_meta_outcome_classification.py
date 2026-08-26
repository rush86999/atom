"""R87 RED tests — meta-agent outcome classification must not poison learning.

Finding (atom_meta_agent._record_execution):
    success = result.get("status") == "success" or (
        result.get("final_output") is not None
        and "error" not in result.get("final_output").lower()
    )

Terminal failure statuses ("timeout", "budget_exceeded", "killed_sandbox",
"failed") carry canned final text with no literal "error" substring, so they
were recorded to AgentGovernanceService.record_outcome AND the
DomainExperienceLedger as SUCCESSES. A deployment that repeatedly hits budget
limits or sandbox kills EARNED super-mentor wins from its failures, and the
meta agent's governance confidence climbed on non-answers.
"""
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _run_record(result: dict, monkeypatch, db):
    """Drive AtomMetaAgent._record_execution with mocked collaborators and
    capture (governance_success, ledger_success)."""
    import core.atom_meta_agent as ama

    captured = {"gov_success": None, "ledger_success": None}

    class _FakeGov:
        def __init__(self, *_a, **_k):
            pass

        async def record_outcome(self, agent_id, success, **kwargs):
            captured["gov_success"] = success

    def _fake_ledger(db_, agent_id, domain, success, task_summary=None):
        captured["ledger_success"] = success

    monkeypatch.setattr(ama, "AgentGovernanceService", _FakeGov)
    monkeypatch.setattr(ama, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        "core.domain_attribution.build_domain_vocabulary", lambda db_: {}
    )
    monkeypatch.setattr(
        "core.domain_attribution.resolve_domain",
        lambda text, vocabulary=None: "sales",
    )
    monkeypatch.setattr(
        "core.domain_attribution.record_domain_outcome", _fake_ledger
    )

    agent = ama.AtomMetaAgent.__new__(ama.AtomMetaAgent)
    agent.world_model = MagicMock()
    agent.world_model.record_experience = AsyncMock()

    asyncio.run(
        agent._record_execution(
            "Follow up on the Acme deal",
            result,
            ama.AgentTriggerMode.MANUAL,
        )
    )
    return captured


# ---------------------------------------------------------------------------
# Pure classifier table
# ---------------------------------------------------------------------------

def test_classifier_timeout_is_failure():
    from core.atom_meta_agent import _execution_succeeded

    assert _execution_succeeded({
        "status": "timeout",
        "final_output": "Maximum reasoning steps reached. Please refine your request.",
    }) is False


def test_classifier_budget_exceeded_is_failure():
    from core.atom_meta_agent import _execution_succeeded

    assert _execution_succeeded({
        "status": "budget_exceeded",
        "final_output": "Budget limit reached — execution halted.",
    }) is False


def test_classifier_killed_sandbox_is_failure():
    from core.atom_meta_agent import _execution_succeeded

    assert _execution_succeeded({
        "status": "killed_sandbox",
        "final_output": "Agent run killed by sandbox: file write outside allowed root",
    }) is False


def test_classifier_failed_status_is_failure():
    from core.atom_meta_agent import _execution_succeeded

    assert _execution_succeeded({"status": "failed", "final_output": None}) is False


def test_classifier_success_still_true():
    from core.atom_meta_agent import _execution_succeeded

    assert _execution_succeeded({
        "status": "success",
        "final_output": "Done. The report was emailed.",
    }) is True


def test_classifier_legacy_no_status_keeps_heuristic():
    """Callers that never set status keep the old final_output heuristic."""
    from core.atom_meta_agent import _execution_succeeded

    assert _execution_succeeded({"final_output": "All set."}) is True
    assert _execution_succeeded({"final_output": "Error: could not reach CRM"}) is False
    assert _execution_succeeded({}) is False


# ---------------------------------------------------------------------------
# Wiring into governance + ledger
# ---------------------------------------------------------------------------

def test_timeout_not_recorded_as_learning_success(monkeypatch, db):
    captured = _run_record(
        {
            "status": "timeout",
            "final_output": "Maximum reasoning steps reached. Please refine your request.",
        },
        monkeypatch,
        db,
    )
    assert captured["gov_success"] is False
    assert captured["ledger_success"] is False


def test_budget_halt_not_recorded_as_learning_success(monkeypatch, db):
    captured = _run_record(
        {
            "status": "budget_exceeded",
            "final_output": "Budget limit reached — execution halted.",
        },
        monkeypatch,
        db,
    )
    assert captured["gov_success"] is False
    assert captured["ledger_success"] is False


def test_genuine_success_still_credits_governance(monkeypatch, db):
    captured = _run_record(
        {
            "status": "success",
            "final_output": "Pipeline updated and follow-up email sent.",
        },
        monkeypatch,
        db,
    )
    assert captured["gov_success"] is True
    assert captured["ledger_success"] is True
