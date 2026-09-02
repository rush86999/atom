"""WikiSkill W1 — the skill-impact ledger.

Pins: every UnifiedEvolutionPipeline outcome (accepted or rejected at any
gate) lands in skill_impact_entries, rollbacks flip the entry (skill rolls
back, knowledge persists), and the evolver prompts render the acceptance
history so a rejected intervention is never re-proposed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auto_dev.evolution_pipeline import (
    MutationRequest,
    UnifiedEvolutionPipeline,
)
from core.auto_dev.models import SkillImpactEntry
from core.auto_dev.skill_impact_ledger import (
    format_history_block,
    record_rollback,
    record_outcome,
    rejection_history,
    rejection_history as history,
    unified_diff,
)
from core.database import Base

TABLES = [SkillImpactEntry.__table__]


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def pipeline(db):
    return UnifiedEvolutionPipeline(db=db)


def _make_request(**kwargs):
    defaults = dict(
        agent_id="a1",
        tenant_id="t1",
        source="alpha_evolver",
        config_key="system_prompt",
        old_value="old prompt",
        new_value="new prompt",
    )
    defaults.update(kwargs)
    return MutationRequest(**defaults)


# ── ledger primitives ────────────────────────────────────────────────────────

def test_record_outcome_appends_row(db):
    row_id = record_outcome(
        db, tenant_id="t1", target="outlook.search_emails",
        source="alpha_evolver", status="rejected", stage="regression",
        reason="behavioral regression", agent_id="a1",
        proposal_summary="faster search", diff="-old\n+new",
    )
    assert row_id is not None
    rows = rejection_history(db, "t1")
    assert len(rows) == 1
    assert rows[0]["status"] == "rejected"
    assert rows[0]["stage"] == "regression"
    assert rows[0]["target"] == "outlook.search_emails"


def test_record_outcome_coerces_unknown_status_and_never_raises(db):
    row_id = record_outcome(db, tenant_id="t1", target="x", source="s",
                            status="bogus")
    assert row_id is not None
    assert rejection_history(db, "t1")[0]["status"] == "rejected"


def test_unified_diff_captures_change_and_caps():
    diff = unified_diff("a = 1\n", "a = 2\n")
    assert diff is not None and "-a = 1" in diff and "+a = 2" in diff
    assert unified_diff("same\n", "same\n") is None
    huge = unified_diff("x = 0\n" * 5000, "y = 0\n" * 5000)
    assert len(huge) <= 4000


def test_history_filters_by_target(db):
    record_outcome(db, tenant_id="t1", target="tool_a", source="memento",
                   status="rejected", stage="governance")
    record_outcome(db, tenant_id="t1", target="tool_b", source="memento",
                   status="accepted", stage="validated")
    assert [r["target"] for r in history(db, "t1", target="tool_a")] == ["tool_a"]


def test_format_history_block_instructs_non_reproposal(db):
    record_outcome(db, tenant_id="t1", target="tool_a", source="memento",
                   status="rejected", stage="governance",
                   reason="danger pattern", proposal_summary="delete all emails")
    block = format_history_block(rejection_history(db, "t1"))
    assert "Do NOT re-propose" in block
    assert "tool_a" in block and "danger pattern" in block
    assert format_history_block([]) == ""


# ── pipeline wiring: every outcome appends ──────────────────────────────────

@pytest.mark.asyncio
async def test_governance_rejection_writes_ledger_row(pipeline, db):
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=False),
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    assert result.passed is False
    rows = rejection_history(db, "t1")
    assert len(rows) == 1
    assert rows[0]["status"] == "rejected" and rows[0]["stage"] == "governance"
    assert rows[0]["mutation_id"] == result.mutation_id


@pytest.mark.asyncio
async def test_accepted_mutation_writes_ledger_row(pipeline, db):
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=True,
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    assert result.passed is True
    rows = rejection_history(db, "t1")
    assert rows[0]["status"] == "accepted"
    assert rows[0]["stage"] == "validated"
    assert rows[0]["mutation_id"] == result.mutation_id


@pytest.mark.asyncio
async def test_regression_rejection_records_diff(pipeline, db):
    regression = MagicMock()
    regression.passed = False
    regression.mismatches = [{"input": 1}]
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=True,
    ), patch(
        "core.auto_dev.regression_validator.RegressionValidator.validate_regression",
        new=AsyncMock(return_value=regression),
    ):
        result = await pipeline.submit_and_deploy(_make_request(
            parent_code="def f():\n    return 1\n",
            mutated_code="def f():\n    return 2\n",
            test_inputs=[{"x": 1}],
        ))
    assert result.passed is False and result.stage == "regression"
    rows = rejection_history(db, "t1")
    assert rows[0]["status"] == "rejected" and rows[0]["stage"] == "regression"


@pytest.mark.asyncio
async def test_rollback_flips_entry_not_deletes(pipeline, db):
    """WikiSkill: the skill rolls back, the wiki never does."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=True,
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    ok = record_rollback(db, result.mutation_id)
    assert ok is True
    row = db.query(SkillImpactEntry).first()
    assert row.status == "rolled_back"


# ── evolver prompt injection ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memento_prompt_carries_acceptance_history(db):
    record_outcome(db, tenant_id="t1", target="auto_skill_x",
                   source="memento", status="rejected", stage="regression",
                   reason="crashed on empty input")
    from core.auto_dev.memento_engine import MementoEngine

    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={"content": "def f():\n    pass"})
    engine = MementoEngine(db=db, llm_service=llm)
    code = await engine.propose_code_change({
        "task_description": "search emails",
        "error_trace": "boom",
        "tenant_id": "t1",
        "agent_id": "a1",
    })
    assert "def f()" in code
    user_prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
    assert "Do NOT re-propose" in user_prompt
    assert "crashed on empty input" in user_prompt


@pytest.mark.asyncio
async def test_alpha_prompt_carries_acceptance_history(db):
    record_outcome(db, tenant_id="t1", target="search_emails",
                   source="alpha_evolver", status="rolled_back",
                   reason="regressed latency")
    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={"content": "def g():\n    return 1"})
    engine = AlphaEvolverEngine(db=db, llm_service=llm)
    code = await engine.propose_code_change({
        "base_code": "def g():\n    return 0",
        "mutation_prompt": "be faster",
        "tenant_id": "t1",
        "target": "search_emails",
    })
    assert "return 1" in code
    user_prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
    assert "Do NOT re-propose" in user_prompt
    assert "regressed latency" in user_prompt


@pytest.mark.asyncio
async def test_no_history_means_clean_prompt(db):
    from core.auto_dev.memento_engine import MementoEngine

    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={"content": "def f():\n    pass"})
    engine = MementoEngine(db=db, llm_service=llm)
    await engine.propose_code_change({
        "task_description": "t", "error_trace": "", "tenant_id": "t1",
    })
    user_prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
    assert "ACCEPTANCE HISTORY" not in user_prompt
