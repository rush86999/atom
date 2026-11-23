"""Real scratch SQLite pending-event pagination and refusal controls."""
import asyncio
import pytest
from core.execution_state_manager import ExecutionStateManager
from test_workflow_event_reservation import IDENTITY, event_db


async def reserve(manager, name):
    state, created = await manager.reserve_event_execution(
        "workflow", {}, execution_id=name, identity=IDENTITY,
        admission={"execution_id": name, "workflow_id": "workflow"})
    assert created
    return state


def test_cursor_reaches_event_after_deferred_page(event_db):
    async def check():
        manager = ExecutionStateManager()
        ids = ["evt_a_deferred", "evt_b_deferred", "evt_c_ready"]
        for name in ids:
            await reserve(manager, name)
        first = await manager.list_admitted_event_executions(limit=2)
        assert [r["execution_id"] for r in first] == ids[:2]
        second = await manager.list_admitted_event_executions(
            limit=2, after_execution_id=first[-1]["execution_id"])
        assert [r["execution_id"] for r in second] == ids[2:]
        assert not await manager.list_admitted_event_executions(
            limit=2, after_execution_id=second[-1]["execution_id"])
        assert (await manager.list_admitted_event_executions(limit=1))[0]["execution_id"] == ids[0]
    asyncio.run(check())


def test_refusal_is_durable_and_not_replayed(event_db):
    async def check():
        manager = ExecutionStateManager()
        state = await reserve(manager, "evt_refused")
        assert await manager.refuse_pending_event_execution(
            "evt_refused", expected_version=state["version"], failure_code="owner_inactive")
        fresh = await ExecutionStateManager().get_execution_state("evt_refused")
        assert fresh["status"] == "FAILED"
        assert fresh["error"] == "owner_inactive"
        assert fresh["version"] == state["version"] + 1
        assert not await manager.refuse_pending_event_execution(
            "evt_refused", expected_version=state["version"], failure_code="other")
        assert not await manager.list_admitted_event_executions()
    asyncio.run(check())


@pytest.mark.parametrize("peer_status", ["RUNNING", "CANCELLED", "PAUSED"])
def test_stale_refusal_preserves_peer_state(event_db, peer_status):
    async def check():
        manager = ExecutionStateManager()
        state = await reserve(manager, "evt_peer")
        if peer_status == "RUNNING":
            assert await manager.claim_event_execution("evt_peer")
        else:
            assert await manager.update_execution_status("evt_peer", peer_status)
        assert not await manager.refuse_pending_event_execution(
            "evt_peer", expected_version=state["version"], failure_code="stale_refusal")
        fresh = await manager.get_execution_state("evt_peer")
        assert fresh["status"] == peer_status
        assert fresh.get("error") != "stale_refusal"
    asyncio.run(check())


def test_unreceipted_and_wrong_version_refuse_nothing(event_db):
    async def check():
        manager = ExecutionStateManager()
        state = await reserve(manager, "evt_valid")
        for name, version in [("manual_one", 1), ("evt_missing", 1),
                              ("evt_valid", state["version"]+1), ("evt_valid", True)]:
            assert not await manager.refuse_pending_event_execution(
                name, expected_version=version, failure_code="refused")
        assert (await manager.get_execution_state("evt_valid"))["status"] == "PENDING"
    asyncio.run(check())


def test_existing_event_without_admission_receipt_is_untouched(event_db):
    from sqlalchemy import update
    from core.models import WorkflowExecution
    async def check():
        manager = ExecutionStateManager()
        state = await reserve(manager, "evt_no_receipt")
        async with event_db() as db:
            await db.execute(update(WorkflowExecution).where(
                WorkflowExecution.execution_id == "evt_no_receipt").values(context="{}"))
            await db.commit()
        assert not await manager.refuse_pending_event_execution(
            "evt_no_receipt", expected_version=state["version"], failure_code="refused")
        fresh = await manager.get_execution_state("evt_no_receipt")
        assert fresh["status"] == "PENDING"
        assert fresh["version"] == state["version"]
    asyncio.run(check())
