"""WikiSkill W5 — the incident-eval gate on playbook promotion.

WikiSkill accepts a skill change only on strict validation improvement; the
Atom analog: a learned draft playbook is replayed against the incident
evals it originated from at approval time. shadow (default) records the
replay and approves anyway; enforce blocks while any related eval FAILS
(skips never block — an unrunnable case is not evidence of regression).
The wiki stays intact on a block: the draft stays `draft`, origin evals
keep accumulating.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import IncidentEval, Playbook
from core.playbook_service import PlaybookService, eval_gate_mode

TABLES = [Playbook.__table__, IncidentEval.__table__]


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_eval(db, eval_id, *, taxonomy="grounding"):
    row = IncidentEval(
        id=eval_id, tenant_id="default", canvas_id="c-1", canvas_type="sheet",
        taxonomy=taxonomy, instruction="fix it",
        context_snapshot={"canvas_type": "sheet", "title": "t", "content": "x"},
        expected_property={"kind": "includes", "value": "template line"},
        source="correction", fingerprint=f"fp-{eval_id}",
    )
    db.add(row)
    db.commit()
    return row


def add_draft(db, playbook_id, origin_ids=None):
    row = Playbook(
        id=playbook_id, tenant_id="default", name="Recurring correction",
        steps=["always do the thing"], source="learned",
        approval_state="draft", origin_ids=origin_ids or [],
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def svc(db):
    return PlaybookService(db, tenant_id="default")


def fake_replay(ran=1, passed=0, failed=1, skipped=0):
    async def _run(db, tenant_id="default", limit=20, llm_service=None,
                  eval_ids=None):
        return {"ran": ran, "passed": passed, "failed": failed,
                "skipped": skipped,
                "results": [{"eval_id": (eval_ids or ["?"])[0],
                             "taxonomy": "grounding",
                             "status": "fail" if failed else "pass",
                             "detail": "d"}]}
    return _run


# ── mode resolution ─────────────────────────────────────────────────────────

def test_eval_gate_mode_defaults_to_shadow(monkeypatch):
    monkeypatch.delenv("ATOM_PLAYBOOK_EVAL_GATE", raising=False)
    assert eval_gate_mode(db=None) == "shadow"


def test_eval_gate_mode_env_override(monkeypatch):
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "enforce")
    assert eval_gate_mode(db=None) == "enforce"
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "garbage")
    assert eval_gate_mode(db=None) == "shadow"


# ── shadow: record and approve ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shadow_records_failing_replay_but_approves(db, svc, monkeypatch):
    monkeypatch.delenv("ATOM_PLAYBOOK_EVAL_GATE", raising=False)
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay(failed=1))

    result = await svc.approve("pb-1", actor="supervisor")
    assert result["approved"] is True
    assert result["eval_gate"]["failed"] == 1
    row = svc.get("pb-1")
    assert row.approval_state == "approved"
    assert row.last_eval_result["failed"] == 1


# ── enforce: block on fail, pass on clean, never on skip ────────────────────

@pytest.mark.asyncio
async def test_enforce_blocks_approval_on_failing_eval(db, svc, monkeypatch):
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "enforce")
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals", fake_replay(failed=1))

    result = await svc.approve("pb-1", actor="supervisor")
    assert result["approved"] is False
    row = svc.get("pb-1")
    assert row.approval_state == "draft"           # wiki intact, stays draft
    assert row.last_eval_result["failed"] == 1     # evidence persisted


@pytest.mark.asyncio
async def test_enforce_approves_clean_replay(db, svc, monkeypatch):
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "enforce")
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals",
                        fake_replay(ran=1, passed=1, failed=0))

    result = await svc.approve("pb-1")
    assert result["approved"] is True
    assert svc.get("pb-1").approval_state == "approved"


@pytest.mark.asyncio
async def test_enforce_skips_never_block(db, svc, monkeypatch):
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "enforce")
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    monkeypatch.setattr("core.incident_eval_runner.run_evals",
                        fake_replay(ran=1, failed=0, skipped=1))

    result = await svc.approve("pb-1")
    assert result["approved"] is True


# ── vacuous gate ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_origin_evals_approves_without_replay(db, svc, monkeypatch):
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "enforce")
    add_draft(db, "pb-1", origin_ids=[])
    called = {"n": 0}

    async def spy(*a, **k):
        called["n"] += 1
        return {"ran": 0, "passed": 0, "failed": 0, "skipped": 0, "results": []}

    monkeypatch.setattr("core.incident_eval_runner.run_evals", spy)
    result = await svc.approve("pb-1")
    assert result["approved"] is True
    assert result["eval_gate"] is None
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_gate_off_never_replays(db, svc, monkeypatch):
    monkeypatch.setenv("ATOM_PLAYBOOK_EVAL_GATE", "off")
    ev = add_eval(db, "eval-1")
    add_draft(db, "pb-1", origin_ids=[ev.id])
    called = {"n": 0}

    async def spy(*a, **k):
        called["n"] += 1

    monkeypatch.setattr("core.incident_eval_runner.run_evals", spy)
    result = await svc.approve("pb-1")
    assert result["approved"] is True
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_missing_playbook_returns_none(db, svc):
    assert await svc.approve("nope") is None


# ── runner filter: eval_ids restricts the replay ────────────────────────────

@pytest.mark.asyncio
async def test_run_evals_eval_ids_filter(db):
    from core.incident_eval_runner import run_evals

    add_eval(db, "eval-1")
    add_eval(db, "eval-2")
    summary = await run_evals(db, tenant_id="default", eval_ids=["eval-2"],
                              llm_service=None)
    # llm_service=None → each case is a skip, but ONLY the filtered one ran
    assert summary["ran"] == 1
    assert summary["results"][0]["eval_id"] == "eval-2"

    empty = await run_evals(db, tenant_id="default", eval_ids=[])
    assert empty["ran"] == 0
