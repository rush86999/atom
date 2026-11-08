"""Eligibility and counter credit must share one configuration epoch.

The credit consumer decides whether a receipt is fresh (post-revocation) and
then inserts its consumption receipt. A peer verified regression may commit in
that gap. The counter CAS is bound to the exact raw configuration observed for
eligibility, so the stale decision cannot publish a receipt or credit old work.
"""
import uuid

from sqlalchemy import event

from core.capability_graduation_service import CapabilityGraduationService
from core.contribution_credit import CREDIT_RECEIPT_TYPE
from core.models import AgentRegistry, TaskOperationRecord
from tests.test_fleet_credit_receipt_integration import (
    _credit,
    _produce_verified_operation,
    _receipt_count,
    _restore_oracle_verifiers,
    _seed_fleet,
    _stats,
    fleet_world,
)


def _set_lifetime(world, action, *, verified=50):
    with world.Session() as db:
        agent = db.get(AgentRegistry, "ag-fleet")
        agent.configuration = {
            "capability_stats": {
                action: {
                    "success": verified,
                    "total": verified,
                    "verified_success": verified,
                }
            },
            "capability_maturities": {action: "autonomous"},
        }
        db.commit()


def _receipts(db):
    db.expire_all()
    return (
        db.query(TaskOperationRecord)
        .filter_by(operation_type=CREDIT_RECEIPT_TYPE)
        .all()
    )


def test_peer_regression_between_eligibility_and_credit_rolls_back_receipt(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    world = fleet_world
    action = "canvas.epoch_race." + uuid.uuid4().hex
    child = "child-old-proof"
    _produce_verified_operation(
        world, child_execution_id=child, action_name=action,
        operation_id="old-proof-operation")
    _seed_fleet(world, child_executions=[(child, action)])
    _set_lifetime(world, action, verified=50)

    armed = [True]

    def regress_before_credit_claim(conn, cursor, statement, params, ctx, many):
        if (armed[0]
                and statement.lstrip().upper().startswith(
                    "INSERT INTO TASK_OPERATION_RECORDS")):
            armed[0] = False
            with world.Session() as peer:
                assert CapabilityGraduationService(peer).record_usage(
                    "ag-fleet", action, False,
                    "failed_verification") is True

    event.listen(world.engine, "before_cursor_execute", regress_before_credit_claim)
    try:
        with world.Session() as db:
            assert _credit(db) is False
    finally:
        event.remove(
            world.engine, "before_cursor_execute", regress_before_credit_claim)

    assert armed == [False]
    with world.Session() as fresh:
        stats = _stats(fresh, action)
        assert stats["verified_success"] == 50
        assert stats["success"] == 50
        cfg = fresh.get(AgentRegistry, "ag-fleet").configuration
        assert cfg["autonomy_revocations"][action]["reentry_successes"] == 0
        # No receipt may be published without the counter write it claims.
        assert _receipt_count(fresh) == 0


def test_recovery_downgrades_old_work_and_replay_does_not_double_count(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    world = fleet_world
    action = "canvas.epoch_recovery." + uuid.uuid4().hex
    child = "child-old-proof"
    _produce_verified_operation(
        world, child_execution_id=child, action_name=action,
        operation_id="old-proof-operation")
    _seed_fleet(world, child_executions=[(child, action)])
    _set_lifetime(world, action, verified=50)

    armed = [True]

    def regress_before_credit_claim(conn, cursor, statement, params, ctx, many):
        if (armed[0]
                and statement.lstrip().upper().startswith(
                    "INSERT INTO TASK_OPERATION_RECORDS")):
            armed[0] = False
            with world.Session() as peer:
                assert CapabilityGraduationService(peer).record_usage(
                    "ag-fleet", action, False,
                    "failed_verification") is True

    event.listen(world.engine, "before_cursor_execute", regress_before_credit_claim)
    try:
        with world.Session() as db:
            assert _credit(db) is False
    finally:
        event.remove(
            world.engine, "before_cursor_execute", regress_before_credit_claim)

    # Recovery re-reads eligibility: the old receipt is now visibly
    # pre-revocation, so it may be recorded as unverified usage only.
    with world.Session() as recovery:
        assert _credit(recovery) is True
        stats = _stats(recovery, action)
        assert stats["verified_success"] == 50
        cfg = recovery.get(AgentRegistry, "ag-fleet").configuration
        assert cfg["autonomy_revocations"][action]["reentry_successes"] == 0
        receipts = _receipts(recovery)
        assert len(receipts) == 1
        assert receipts[0].status == "succeeded"
        assert receipts[0].result_json["verified"] is False

    # Replaying the same source outcome must not add a second receipt or credit.
    with world.Session() as replay:
        assert _credit(replay) is False
        assert _stats(replay, action)["verified_success"] == 50
        assert _receipt_count(replay) == 1


def test_legitimate_fresh_verified_credit_and_replay_stay_positive(
        fleet_world, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    world = fleet_world
    action = "canvas.epoch_positive." + uuid.uuid4().hex
    child = "child-fresh-proof"
    _produce_verified_operation(
        world, child_execution_id=child, action_name=action,
        operation_id="fresh-proof-operation")
    _seed_fleet(world, child_executions=[(child, action)])
    _set_lifetime(world, action, verified=50)

    with world.Session() as db:
        assert _credit(db) is True
        stats = _stats(db, action)
        # The new receipt is genuinely verified work: exactly one new success.
        assert stats["verified_success"] == 51
        receipts = _receipts(db)
        assert len(receipts) == 1
        assert receipts[0].result_json["verified"] is True

        assert _credit(db) is False
        assert _stats(db, action)["verified_success"] == 51
        assert _receipt_count(db) == 1

    with world.Session() as replay:
        assert _credit(replay) is False
        assert _stats(replay, action)["verified_success"] == 51
        assert _receipt_count(replay) == 1
