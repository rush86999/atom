"""Guidance + notification tests (§6 "nothing silent").

The canonical path is NotificationService.send_notification — monkeypatched
here with a recorder. Fire-and-forget delivery from sync service calls is
exercised for real (no running loop → asyncio.run path).
"""

import asyncio
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import Base, Canvas, CanvasAudit, GoalObjective, GoalRun, HITLAction
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_run_executors import GoalRunExecutors


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    sent = []

    async def fake_send(self, user_id, notification_type, data):
        sent.append({"user_id": user_id, "type": notification_type,
                     "title": data.get("title"), "message": data.get("message"),
                     "action_url": data.get("action_url"),
                     "priority": data.get("priority")})
        return {"success": True, "notification_id": "n1", "emailed": False}

    monkeypatch.setattr(
        "core.notification_service.NotificationService.send_notification",
        fake_send)

    async def noop_outcome(service, run, outcome):
        return None

    monkeypatch.setattr(
        "core.goals.goal_run_learning.record_run_outcome", noop_outcome)

    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_notify_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__, HITLAction.__table__):
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
    return svc, factory, sent


PLAN = [
    {"id": "s1", "kind": "canvas_work", "title": "Research"},
    {"id": "s2", "kind": "human_checkpoint", "title": "Quote approval"},
]


def test_hold_notifies_with_guidance_and_action_url(backend):
    svc, _, sent = backend
    rid = svc.create_run("goal-1", plan=PLAN, created_by="sup-1")["id"]
    svc.transition(rid, "active")
    svc._hold_for_approval(rid, {"decision": "ADVANCE",
                                 "rationale": "research first"},
                           reason="training checkpoint")
    assert len(sent) == 1
    n = sent[0]
    assert n["user_id"] == "sup-1"
    assert n["type"] == "approval_needed"
    assert n["priority"] == "high"
    assert n["action_url"] == f"/goal-runs/{rid}"
    assert "ADVANCE" in n["message"]
    assert "override with guidance" in n["message"]   # the guidance


def test_no_creator_no_notification(backend):
    svc, _, sent = backend
    rid = svc.create_run("goal-1", plan=PLAN, created_by=None)["id"]
    svc.transition(rid, "active")
    svc._hold_for_approval(rid, {"decision": "ADVANCE"}, reason="x")
    assert sent == []


def test_wait_notifies_with_deadline(backend):
    svc, _, sent = backend
    rid = svc.create_run("goal-1", plan=PLAN, created_by="sup-1")["id"]
    svc.transition(rid, "active")
    svc.set_wait(rid, {"event": "email_reply", "match": {"from": "acme@x.com"},
                       "deadline": "2026-09-12T00:00:00Z"})
    assert len(sent) == 1
    n = sent[0]
    assert n["type"] == "goal_run_waiting"
    assert "email_reply" in n["message"]
    assert "2026-09-12" in n["message"]
    assert "Nothing to do" in n["message"]


def test_checkpoint_notifies_approval_needed(backend):
    svc, _, sent = backend
    rid = svc.create_run("goal-1", plan=[PLAN[1]], created_by="sup-1")["id"]
    svc.transition(rid, "active")
    ex = GoalRunExecutors(svc)
    asyncio.run(ex.execute(svc.get_run(rid),
                           {"decision": "ADVANCE", "rationale": "quote ready"}))
    assert len(sent) == 1   # set_wait's waiting notify suppressed for checkpoints
    n = sent[0]
    assert n["type"] == "approval_needed"
    assert "Quote approval" in n["title"]
    assert "cannot proceed without you" in n["message"]


def test_achieved_notifies_and_mentions_distill(backend):
    svc, _, sent = backend
    rid = svc.create_run("goal-1", plan=PLAN, created_by="sup-1")["id"]
    svc.transition(rid, "active")
    svc.transition(rid, "achieved")
    assert len(sent) == 1
    n = sent[0]
    assert n["type"] == "goal_run_achieved"
    assert "Distill" in n["message"]


def test_cancel_notifies_stopped(backend):
    svc, _, sent = backend
    rid = svc.create_run("goal-1", plan=PLAN, created_by="sup-1")["id"]
    svc.transition(rid, "active")
    svc.cancel(rid, reason="lead went dark")
    assert len(sent) == 1
    assert sent[0]["type"] == "goal_run_stopped"
    assert sent[0]["title"].startswith("Goal run cancelled")
