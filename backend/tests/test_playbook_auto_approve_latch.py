"""Playbook evidence latch (Playbook Journey P5) — ATOM_PLAYBOOKS_AUTO_APPROVE.

Default OFF: the supervisor approve click stays the HITL contract. When
explicitly enabled, a `learned` draft promotes without a human click only
where autonomy already allows no-human-gating (the same contract that gates
the hires' own actions): the draft's trigger canvas type maps to autonomy
topics, and every topic must be auto-if-mature with ALL active hires
clearing the maturity×trust bar — plus the ORIGIN incident evals passing 3
consecutive nightly replays. An email-surface rule (human_always topics) or
one drafted while any hire still proposes is autonomy-blocked: the streak
freezes, and any replay with a failure — or nothing runnable — resets it.
taught/authored drafts never latch. The pass streak persists on the draft's
last_eval_result['auto_latch'] so the review surface can show progress.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, IncidentEval, Playbook
from core.exchange_memory_maintenance import _auto_approve_playbooks

TABLES = [Playbook.__table__, IncidentEval.__table__, AgentRegistry.__table__]


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_eval(db, eval_id):
    row = IncidentEval(
        id=eval_id, tenant_id="default", canvas_id="c-1", canvas_type="sheet",
        taxonomy="grounding", instruction="fix it",
        context_snapshot={"canvas_type": "sheet", "title": "t", "content": "x"},
        expected_property={"kind": "includes", "value": "template line"},
        source="correction", fingerprint=f"fp-{eval_id}",
    )
    db.add(row)
    db.commit()
    return row


def add_draft(db, playbook_id, *, source="learned", origin_ids=None):
    row = Playbook(
        id=playbook_id, tenant_id="default", name="Recurring correction",
        steps=["always do the thing"], source=source,
        approval_state="draft", origin_ids=origin_ids or [],
    )
    db.add(row)
    db.commit()
    return row


def get_row(db, playbook_id):
    return db.query(Playbook).filter(Playbook.id == playbook_id).first()


def fake_replay(ran=1, passed=0, failed=0, skipped=0):
    async def _run(db, tenant_id="default", limit=20, llm_service=None,
                  eval_ids=None):
        return {"ran": ran, "passed": passed, "failed": failed,
                "skipped": skipped, "results": []}
    return _run


def setting(value):
    return SimpleNamespace(value=value, source="db" if value else "default")


@pytest.fixture()
def latch_on(monkeypatch):
    monkeypatch.setattr("core.runtime_settings.resolve_setting",
                        lambda *a, **k: setting(True))


def add_hire(db, agent_id, status="intern", tenant_id="default"):
    db.add(AgentRegistry(
        id=agent_id, name=f"Hire {agent_id}", category="Ops",
        module_path="x.y", class_name="Z", tenant_id=tenant_id,
        status=status, enabled=True,
    ))
    db.commit()
    return agent_id


def _gov(allowed=True, agent_status="intern", required="intern"):
    gov = MagicMock()
    gov.can_perform_action.return_value = {
        "allowed": allowed,
        "agent_status": agent_status,
        "required_status": required,
        "reason": "ok" if allowed else "Maturity check failed.",
    }
    return gov


def gov_allows(allowed):
    """Patch the same seam the autonomy panel tests use — the gate reads
    governance through ServiceFactory, so the crew gate does too."""
    return patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_gov(allowed=allowed),
    )


# ── default: off ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_latch_off_by_default(db, monkeypatch):
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    called = {"n": 0}

    async def spy(*a, **k):
        called["n"] += 1

    monkeypatch.setattr("core.incident_eval_runner.run_evals", spy)
    summary = await _auto_approve_playbooks(db)
    assert summary["latched"] == 0
    assert called["n"] == 0
    assert "latch_off" in summary["reason"]
    assert get_row(db, "pb-1").approval_state == "draft"


# ── promotion: 3 consecutive clean replays ──────────────────────────────────

@pytest.mark.asyncio
async def test_latch_promotes_after_three_clean_replays(db, latch_on, monkeypatch):
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())

    for cycle in range(2):
        await _auto_approve_playbooks(db)
        assert get_row(db, "pb-1").approval_state == "draft"

    await _auto_approve_playbooks(db)
    row = get_row(db, "pb-1")
    assert row.approval_state == "approved"
    assert row.approved_by == "auto_latch:evidence"
    assert row.last_eval_result["auto_latch"]["passes"] == 3


@pytest.mark.asyncio
async def test_latch_streak_resets_on_failing_replay(db, latch_on, monkeypatch):
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())

    await _auto_approve_playbooks(db)
    await _auto_approve_playbooks(db)
    monkeypatch.setattr("core.incident_eval_runner.run_evals",
                        fake_replay(ran=1, passed=0, failed=1))
    await _auto_approve_playbooks(db)
    row = get_row(db, "pb-1")
    assert row.approval_state == "draft"
    assert row.last_eval_result["auto_latch"]["passes"] == 0


@pytest.mark.asyncio
async def test_latch_needs_runnable_evals(db, latch_on, monkeypatch):
    """All-skip replays are NOT clean passes — an unrunnable case is no
    evidence (same convention as the approval-time eval gate)."""
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals",
                        fake_replay(ran=0, skipped=1))

    for _ in range(3):
        await _auto_approve_playbooks(db)
    assert get_row(db, "pb-1").approval_state == "draft"


@pytest.mark.asyncio
async def test_latch_never_touches_taught_drafts(db, latch_on, monkeypatch):
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", source="taught", origin_ids=[ev.id])
    called = {"n": 0}

    async def spy(*a, **k):
        called["n"] += 1

    monkeypatch.setattr("core.incident_eval_runner.run_evals", spy)
    summary = await _auto_approve_playbooks(db)
    assert summary["replayed"] == 0 and called["n"] == 0
    assert get_row(db, "pb-1").approval_state == "draft"


@pytest.mark.asyncio
async def test_latch_skips_drafts_without_origin_evidence(db, latch_on, monkeypatch):
    add_draft(db, "pb-1", origin_ids=[])
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())
    summary = await _auto_approve_playbooks(db)
    assert summary["replayed"] == 0
    assert get_row(db, "pb-1").approval_state == "draft"


# ── autonomy gate: no-human-gating only where maturity allows it ────────────

@pytest.mark.asyncio
async def test_latch_never_promotes_email_surface_rules(db, latch_on, monkeypatch):
    """Email canvases map to send/CRM topics — human_always by default. Even
    an autonomous crew never executes external sends unattended, so a rule
    for that surface never auto-approves either (same blast-radius line the
    action gate draws)."""
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    row = get_row(db, "pb-1")
    row.trigger_canvas_type = "email"
    db.commit()
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())

    for _ in range(3):
        summary = await _auto_approve_playbooks(db)
        assert summary["replayed"] == 0
        assert summary["autonomy_blocked"] == 1
    row = get_row(db, "pb-1")
    assert row.approval_state == "draft"
    assert "human_always" in row.last_eval_result["auto_latch"]["blocked"]


@pytest.mark.asyncio
async def test_latch_waits_for_a_mature_crew(db, latch_on, monkeypatch):
    """A rule guides every hire in the tenant — while ANY hire still
    proposes the topic (below the maturity bar), the draft stays
    human-gated, exactly like that hire's own actions would."""
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    add_hire(db, "hire-student", status="student")
    add_hire(db, "hire-senior", status="supervised")
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())

    with gov_allows(allowed=False):
        summary = await _auto_approve_playbooks(db)
    assert summary["autonomy_blocked"] == 1 and summary["replayed"] == 0
    row = get_row(db, "pb-1")
    assert row.approval_state == "draft"
    assert row.last_eval_result["auto_latch"]["passes"] == 0
    assert "propose" in row.last_eval_result["auto_latch"]["blocked"]

    # The student graduates past the bar → the streak accrues and latches.
    with gov_allows(allowed=True):
        for _ in range(2):
            await _auto_approve_playbooks(db)
        await _auto_approve_playbooks(db)
    assert get_row(db, "pb-1").approval_state == "approved"


@pytest.mark.asyncio
async def test_latch_streak_freezes_while_blocked_not_resets(db, latch_on, monkeypatch):
    """Crew immaturity pauses the streak (it resumes); only a FAILING
    replay resets it — the two gates are independent failure modes."""
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    add_hire(db, "hire-1", status="intern")
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())

    with gov_allows(allowed=True):
        await _auto_approve_playbooks(db)
        await _auto_approve_playbooks(db)
    assert get_row(db, "pb-1").last_eval_result["auto_latch"]["passes"] == 2

    # A new STUDENT joins the tenant — eligibility pauses, streak freezes.
    add_hire(db, "hire-newbie", status="student")
    with gov_allows(allowed=False):
        await _auto_approve_playbooks(db)
    row = get_row(db, "pb-1")
    assert row.approval_state == "draft"
    assert row.last_eval_result["auto_latch"]["passes"] == 2
    assert "blocked" in row.last_eval_result["auto_latch"]

    with gov_allows(allowed=True):
        await _auto_approve_playbooks(db)
    assert get_row(db, "pb-1").approval_state == "approved"


@pytest.mark.asyncio
async def test_latch_gates_only_its_own_tenant(db, latch_on, monkeypatch):
    """A student in ANOTHER tenant doesn't hold this tenant's rule back."""
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    add_hire(db, "hire-foreign", status="student", tenant_id="other")
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay())

    for _ in range(3):
        await _auto_approve_playbooks(db)
    assert get_row(db, "pb-1").approval_state == "approved"
