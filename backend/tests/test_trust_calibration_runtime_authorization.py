"""ASK-03 — trust-calibration revocation is a runtime authorization input.

The consent-gated automation ledger used to be bookkeeping only: nothing in
the execution path read ``resolved_trust_enforce``. These tests drive the
real certification/automation loop, then ask the same autonomy gate a turn
would ask — across a fresh DB session (the restart/resume case) — and assert
a previously autonomous topic stops executing after a verified regression.
"""
from __future__ import annotations

import asyncio
import contextlib
import os

os.environ.setdefault("TESTING", "1")

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from core import autonomy_policy as ap
from core.models import (
    Base,
    HITLAction,
    TrustCalibrationAction,
    TrustCalibrationAssessment,
)


@pytest.fixture()
def world(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/ask03.db")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextlib.contextmanager
    def session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "auto")
    import core.trust_calibration.automation as auto

    monkeypatch.setattr(auto, "_mode", None)
    monkeypatch.setattr(auto, "_interval_min", None)
    yield {"session": session, "auto": auto, "engine": engine}
    engine.dispose()


def _gov():
    gov = MagicMock()
    gov.can_perform_action.return_value = {
        "allowed": True,
        "agent_status": "autonomous",
        "required_status": "intern",
        "reason": "ok",
    }
    return gov


def _gate(db):
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_gov(),
    ):
        return ap.gate_for_topic(db, "owner-1", "canvas_edit", "hire-1")


def _seed_certifiable_history(db, n_pairs=18):
    """Resolved approvals at the low corner / rejections at the high corner."""
    now = datetime.now()
    for i in range(n_pairs):
        good_ref = f"h-good-{i}"
        db.add(HITLAction(
            id=good_ref, action_type="search_contacts", platform="internal",
            params={}, status="approved", agent_id="hire-1",
            reviewed_at=now - timedelta(hours=i + 1),
            created_at=now - timedelta(hours=i + 1),
        ))
        db.add(TrustCalibrationAssessment(
            id=f"a-good-{i}", action_type="search_contacts",
            platform="internal", p_approve=0.9, uncertainty=0.05,
            recommendation="allow", source_path="hitl_step_act",
            decision_ref=good_ref,
            features_json={"tool": [0.25, 0.0, 0.0], "ctx": [0.33]},
            created_at=now - timedelta(hours=i + 1),
        ))
        bad_ref = f"h-bad-{i}"
        decided = now - timedelta(hours=1.5 * i + 3.0)
        db.add(HITLAction(
            id=bad_ref, action_type=f"bulk_delete_leads_{i}",
            platform="payment", params={}, status="rejected",
            agent_id="hire-1", reviewed_at=decided, created_at=decided,
        ))
        db.add(TrustCalibrationAssessment(
            id=f"a-bad-{i}", action_type=f"bulk_delete_leads_{i}",
            platform="payment", p_approve=0.1, uncertainty=0.05,
            recommendation="block", source_path="hitl_step_act",
            decision_ref=bad_ref,
            features_json={"tool": [1.0, 1.0, 1.0], "ctx": [0.33]},
            created_at=decided,
        ))
    db.commit()


def test_flag_off_keeps_legacy_gate_neutral(world, monkeypatch):
    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "false")
    with world["session"]() as db:
        ap.set_mode(db, "owner-1", "canvas_edit", ap.MODE_AUTO_IF_MATURE)
        gate = _gate(db)
    assert gate["calibration"]["enabled"] is False
    assert gate["outcome"] == ap.OUTCOME_EXECUTE


def test_enabled_without_certification_does_not_relax(world):
    with world["session"]() as db:
        ap.set_mode(db, "owner-1", "canvas_edit", ap.MODE_AUTO_IF_MATURE)
        gate = _gate(db)
    assert gate["calibration"]["enabled"] is True
    assert gate["calibration"]["resolved"] is False
    assert gate["outcome"] == ap.OUTCOME_PROPOSE
    assert "calibration" in gate["reason"].lower()


def test_certified_enable_executes_then_regression_revokes_across_restart(
        world, monkeypatch):
    auto = world["auto"]
    with world["session"]() as db:
        ap.set_mode(db, "owner-1", "canvas_edit", ap.MODE_AUTO_IF_MATURE)
        _seed_certifiable_history(db)

    with world["session"]() as db:
        applied = auto.run_automation_pass(db, force=True)
        assert applied["verdict"] == "enable" and applied["applied"]
        assert auto.resolved_trust_enforce(db) is True
        assert _gate(db)["outcome"] == ap.OUTCOME_EXECUTE

    # A fresh session stands in for the post-wait / post-restart worker:
    # the grant is read from the durable ledger, not from process state.
    with world["session"]() as db:
        assert _gate(db)["outcome"] == ap.OUTCOME_EXECUTE

    from core.trust_calibration.certify import CertificationResult

    failing = CertificationResult(
        certified=False,
        reasons=["holdout Brier 0.61 > baseline 0.25"],
        n_train=28, n_eval=10, brier_holdout=0.61,
        denial_coverage=0.1, ece_10bin=0.3,
    )
    monkeypatch.setattr(
        "core.trust_calibration.certify.certify", lambda resolved: failing)

    with world["session"]() as db:
        revoked = auto.run_automation_pass(db, force=True)
        assert revoked["verdict"] == "revoke" and revoked["revoked"]
        assert auto.resolved_trust_enforce(db) is False
        latest = (
            db.query(TrustCalibrationAction)
            .order_by(TrustCalibrationAction.created_at.desc())
            .first()
        )
        assert (latest.verdict, latest.state) == ("revoke", "revoked")
        assert _gate(db)["outcome"] == ap.OUTCOME_PROPOSE

    # Restart again: the revocation is durable, not an in-memory flag.
    with world["session"]() as db:
        assert auto.resolved_trust_enforce(db) is False
        gate = _gate(db)
    assert gate["outcome"] == ap.OUTCOME_PROPOSE
    assert gate["calibration"]["resolved"] is False


def test_assignment_dispatch_rechecks_revoked_calibration(world, monkeypatch):
    """The durable assignment executor uses the same gate before claiming an
    unapproved internal edit, including after a fresh worker starts."""
    from types import SimpleNamespace

    from core.assignment_executor import AssignmentExecutor

    auto = world["auto"]
    with world["session"]() as db:
        _seed_certifiable_history(db)
        auto.run_automation_pass(db, force=True)

    @contextlib.contextmanager
    def opening():
        with world["session"]() as db:
            yield db

    lifecycle = SimpleNamespace(
        runs=SimpleNamespace(_sessions=lambda: opening))
    executor = AssignmentExecutor(lifecycle)
    assignment = {
        "assignment_id": "a-1",
        "employee_id": "owner-1",
        "provenance": {"agent_id": "hire-1", "user_id": "owner-1"},
    }
    step = {
        "step_id": "edit-1",
        "operation_type": "edit",
        "adapter": "canvas.edit",
        "effect": "local",
    }
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_gov(),
    ):
        assert executor._autonomy_gate(assignment, step) is None

    from core.trust_calibration.certify import CertificationResult

    failing = CertificationResult(
        certified=False, reasons=["regression"], n_train=20, n_eval=8,
        brier_holdout=0.6, denial_coverage=0.1, ece_10bin=0.3,
    )
    monkeypatch.setattr(
        "core.trust_calibration.certify.certify", lambda resolved: failing)
    with world["session"]() as db:
        auto.run_automation_pass(db, force=True)

    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_gov(),
    ):
        denial = executor._autonomy_gate(assignment, step)
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert "calibration" in denial["reason"].lower()


def test_assignment_wait_resume_after_revocation_requires_new_approval(
        world, monkeypatch):
    """A durable wait outlives the autonomous grant: resume after revocation
    must pause for approval and must not dispatch the edit."""
    from sqlalchemy.orm import sessionmaker

    from core.assignment_executor import (
        AssignmentExecutor, WaitingForExternal, default_adapter_registry,
    )
    from core.assignment_plan import new_assignment, new_step
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    auto = world["auto"]
    with world["session"]() as db:
        _seed_certifiable_history(db)
        auto.run_automation_pass(db, force=True)
        assert auto.resolved_trust_enforce(db) is True

    Session = sessionmaker(bind=world["engine"], expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws-ask03", tenant_id="tenant-ask03",
        session_factory=Session)
    goals = GoalService(
        workspace_id="ws-ask03", tenant_id="tenant-ask03",
        session_factory=Session)
    lifecycle = TaskLifecycle(runs, goals)
    registry = default_adapter_registry.clone()
    calls = {"edit": 0}

    async def wait_for_reply(inputs, context):
        if (context.get("step") or {}).get("external_response"):
            return {"status": "applied", "summary": "reply received"}
        raise WaitingForExternal({
            "state": "waiting_for_person", "party": "owner",
            "correlation_id": "corr-ask03", "resume_on": "response",
            "detail": "reply needed",
        })

    async def do_edit(inputs, context):
        calls["edit"] += 1
        return {"status": "applied", "summary": "edited once"}

    registry.register("test.wait", wait_for_reply,
                      metadata={"effect": "read_only"})
    registry.register("test.edit", do_edit,
                      metadata={"effect": "local"})
    executor = AssignmentExecutor(lifecycle, adapters=registry)
    plan = new_assignment(
        objective="Wait, then edit",
        employee_id="owner-1",
        workspace_id="ws-ask03",
        tenant_id="tenant-ask03",
        authorized_actions=["retrieve", "edit"],
        steps=[
            new_step(step_id="wait", title="Wait", operation_type="retrieve",
                     adapter="test.wait", effect="read_only"),
            new_step(step_id="edit", title="Edit", operation_type="edit",
                     adapter="test.edit", depends_on=["wait"],
                     effect="local"),
        ],
    )
    plan["provenance"] = {
        **(plan.get("provenance") or {}),
        "agent_id": "hire-1",
        "user_id": "owner-1",
    }
    record = executor.create_assignment(
        "conv-ask03", "Wait, then edit", assignment=plan)
    run_id = record["run_id"]
    first = asyncio.run(executor.execute(run_id))
    assert first["assignment"]["status"] == "waiting"
    assert calls["edit"] == 0

    from core.trust_calibration.certify import CertificationResult

    failing = CertificationResult(
        certified=False, reasons=["regression"], n_train=20, n_eval=8,
        brier_holdout=0.6, denial_coverage=0.1, ece_10bin=0.3,
    )
    monkeypatch.setattr(
        "core.trust_calibration.certify.certify", lambda resolved: failing)
    with world["session"]() as db:
        auto.run_automation_pass(db, force=True)

    executor.record_external_response(
        run_id, "corr-ask03", response="received", source="owner")
    resumed = asyncio.run(AssignmentExecutor(
        lifecycle, adapters=registry).resume(run_id))
    assert resumed["assignment"]["status"] == "waiting"
    edit_step = next(
        item for item in resumed["assignment"]["steps"]
        if item["step_id"] == "edit")
    assert edit_step["status"] == "awaiting_approval"
    assert calls["edit"] == 0, "revoked autonomy must not dispatch the edit"

    executor.approve_step(run_id, "edit", approved_by="owner")
    approved = asyncio.run(AssignmentExecutor(
        lifecycle, adapters=registry).resume(run_id))
    assert calls["edit"] == 1, "explicit approval resumes the same step once"
    assert next(
        item for item in approved["assignment"]["steps"]
        if item["step_id"] == "edit")["status"] == "applied"


