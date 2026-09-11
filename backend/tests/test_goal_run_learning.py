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


# ===========================================================================
# Cross-feature contract: the chat teaching channel and the goal-run router
# share ONE lesson store.
# ===========================================================================

def test_lesson_taught_in_chat_reaches_the_next_goal_decision(
    db_session, monkeypatch
):
    """A rule taught in chat (/teach) shapes the very next goal-run decision.

    Nothing wires the two features together explicitly — that IS the point:
    `core/chat_teaching` writes and `GoalRunRouter._role_context` reads the
    same `AgentRegistry.configuration["learning"]["log"]`, so "long-running
    goals" get the same trained agent as chat, canvas edits and task runs.
    This test pins that shared-store contract so a future refactor of either
    side cannot silently fork the lesson store.
    """
    import contextlib
    import uuid as _uuid

    from core.chat_teaching import teach_from_chat
    from core.goals.goal_run_router import GoalRunRouter
    from core.models import AgentRegistry

    agent = AgentRegistry(
        id=f"goal-lesson-{_uuid.uuid4().hex[:8]}",
        name="Goal Runner", category="sales", description="t",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="student", confidence_score=0.1, configuration={},
        capabilities=["send_email"], workspace_id="default", tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()

    notice = teach_from_chat(
        db_session, agent_id=agent.id,
        lesson="Always confirm the price with the lead before quoting",
    )
    assert notice["status"] == "saved"

    # _role_context opens its own session; point it at this test's session so
    # the assertion is about the shared STORE, not two databases.
    monkeypatch.setattr(
        "core.database.get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )

    run = {"id": "run-1", "goal_id": "goal-1", "agent_id": agent.id,
           "tenant_id": "default"}
    advisory = GoalRunRouter(tenant_id="default")._role_context(run)

    assert "YOUR LESSONS" in advisory
    assert "Always confirm the price with the lead before quoting" in advisory


def test_goal_override_lesson_and_chat_lesson_land_in_the_same_journal(
    db_session, monkeypatch
):
    """A supervisor's goal-run override (the existing goal teaching channel)
    and a /teach lesson (the new chat channel) are the SAME kind of permanent
    guidance — both must be recalled at work time. Guards against either
    channel writing a shape `_is_permanent_lesson` does not recognise
    (the override passes source="human_correction", which the journal
    normalises to observation/human_correction)."""
    import uuid as _uuid

    from core.chat_teaching import teach_from_chat
    from core.goals.goal_run_learning import record_decision_override
    from core.models import AgentRegistry
    from core.student_learning_service import get_agent_lessons

    agent = AgentRegistry(
        id=f"goal-both-{_uuid.uuid4().hex[:8]}",
        name="Goal Runner", category="sales", description="t",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5, configuration={},
        capabilities=["send_email"], workspace_id="default", tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()

    teach_from_chat(db_session, agent_id=agent.id,
                    lesson="Quote in the client's currency")

    class _Svc:
        tenant_id = "default"

    monkeypatch.setattr(
        "core.database.get_db_session",
        lambda: __import__("contextlib").nullcontext(db_session),
    )
    record_decision_override(
        _Svc(),
        {"id": "run-1", "goal_id": "goal-1", "agent_id": agent.id,
         "tenant_id": "default"},
        {"decision": "ASK_HUMAN", "rationale": "unclear pricing"},
        guidance="check the FX rate before asking me",
    )

    db_session.refresh(agent)
    lessons = [l.get("lesson") or l.get("summary")
               for l in get_agent_lessons(db_session, agent.id, limit=20)]

    assert "Quote in the client's currency" in lessons           # chat channel
    assert any("check the FX rate before asking me" in (t or "")
               for t in lessons)                                  # override channel
