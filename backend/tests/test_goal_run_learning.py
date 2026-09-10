"""Slice 6 tests — learning loop + lifecycle
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.6, §3.7, §7 slice 6).

The learning module is fault-isolated by design, so these tests verify the
happy paths (journal/distill/promotion evidence) and that failures degrade
to warnings rather than exceptions.
"""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import Base, GoalObjective, GoalRun, Playbook
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_run_learning import (
    distill_run_to_playbook_draft,
    evaluate_mode_promotion,
    record_decision_override,
    seed_plan_for_run,
)


@pytest.fixture()
def backend(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_learning_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Playbook.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    svc = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                         session_factory=factory)
    with factory() as session:
        session.add(GoalObjective(id="goal-1", workspace_id="ws_test",
                                  tenant_id="t_test",
                                  title="Prepare a quote for the Acme lead",
                                  status="active"))
        session.commit()

    def make_run():
        rid = svc.create_run("goal-1", agent_id="agent-1", role="sales",
                             plan=[{"id": "s1", "kind": "canvas_work",
                                    "title": "Research"}])["id"]
        return rid

    return svc, factory, make_run


def test_override_records_lesson_with_guidance(backend, monkeypatch):
    """The override lesson lands in the agent's registry learning log via
    journal_standing_lesson (monkeypatched — the real one needs the live
    AgentRegistry row)."""
    svc, _, make_run = backend
    rid = make_run()
    journaled = {}

    def fake_journal(db, agent_id, lesson, **kwargs):
        journaled["agent_id"] = agent_id
        journaled["lesson"] = lesson
        return True

    from core.goals import goal_run_learning
    monkeypatch.setattr(
        "core.student_learning_service.journal_standing_lesson",
        fake_journal)
    run = svc.get_run(rid)
    record_decision_override(svc, run,
                             {"decision": "REPLAN", "rationale": "pivot"},
                             guidance="confirm price with the lead first",
                             approved=False)
    assert journaled["agent_id"] == "agent-1"
    assert "confirm price" in journaled["lesson"]
    assert "REPLAN" in journaled["lesson"]


def test_override_without_agent_or_guidance_is_safe(backend):
    svc, _, make_run = backend
    rid = make_run()
    run = svc.get_run(rid)
    run["agent_id"] = None
    record_decision_override(svc, run, {"decision": "ADVANCE"},
                             guidance=None, approved=False)  # no raise


def test_distill_creates_deduped_playbook_draft(backend, monkeypatch):
    svc, factory, make_run = backend
    monkeypatch.setattr("core.database.get_db_session", lambda: factory())
    rid = make_run()
    for decision in ({"decision": "ADVANCE", "rationale": "research the lead"},
                     {"decision": "REVISE_CURRENT",
                      "rationale": "lead cited budget — revise"},
                     {"decision": "ADVANCE", "rationale": "resend quote"}):
        svc.append_decision(rid, {"kind": "decision", **decision})
    run = svc.get_run(rid)
    out = distill_run_to_playbook_draft(run, tenant_id="t_test",
                                        workspace_id="ws_test",
                                        goal_title="Prepare a quote")
    assert out and out["approval_state"] == "draft"
    assert len(out["steps"]) == 3
    with factory() as session:
        rows = session.query(Playbook).all()
        assert len(rows) == 1
        assert rows[0].source == "learned"
        assert rows[0].origin_ids == [rid]
    # Same shape again → deduped (no second draft)
    again = distill_run_to_playbook_draft(run, tenant_id="t_test",
                                          workspace_id="ws_test",
                                          goal_title="Prepare a quote")
    assert again is None
    with factory() as session:
        assert session.query(Playbook).count() == 1


def test_distill_skips_thin_runs(backend):
    svc, _, make_run = backend
    rid = make_run()
    svc.append_decision(rid, {"kind": "decision", "decision": "ADVANCE",
                              "rationale": "only one"})
    out = distill_run_to_playbook_draft(svc.get_run(rid),
                                        tenant_id="t_test",
                                        workspace_id="ws_test")
    assert out is None


def test_seeding_from_fallback_includes_checkpoint():
    out = seed_plan_for_run("Prepare a quote for the Acme lead",
                            role="sales", tenant_id="t_test")
    kinds = [s["kind"] for s in out["plan"]]
    assert out["source"] == "fallback"
    assert "human_checkpoint" in kinds
    assert all(s["id"] for s in out["plan"])


def test_promotion_evidence_thresholds(backend):
    svc, _, _ = backend
    runs = []
    for i in range(3):
        rid = svc.create_run("goal-1", agent_id="agent-prom", role="sales",
                             supervision_mode="training",
                             plan=[{"id": "s1", "kind": "canvas_work",
                                    "title": "x"}])["id"]
        svc.transition(rid, "active")
        svc.transition(rid, "achieved")
        runs.append(rid)
    out = evaluate_mode_promotion("agent-prom", workspace_id="ws_test",
                                  tenant_id="t_test",
                                  session_factory=svc._session_factory)
    assert out["recommendation"] == "shadow"   # 3/3 achieved training runs
    assert out["evidence"]["training"]["runs"] == 3
    assert out["evidence"]["training"]["achieved_ratio"] == 1.0
    # Fresh agent → stays training
    out2 = evaluate_mode_promotion("agent-fresh", workspace_id="ws_test",
                                   tenant_id="t_test",
                                   session_factory=svc._session_factory)
    assert out2["recommendation"] == "training"
