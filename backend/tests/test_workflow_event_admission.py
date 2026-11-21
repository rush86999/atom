import asyncio
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.workflow_event_admission import (
    EVENT_ADMISSION_CONTEXT_KEY,
    EventAdmissionReceipt,
    EventPayloadConflict,
    EventReceiptKey,
    ReservationResult,
    WorkflowEvent,
    WorkflowEventAdmissionCoordinator,
    derive_event_id,
    payload_digest,
)


class _ReceiptStore:
    """In-memory stand-in for a durable receipt table."""

    def __init__(self):
        self.rows = {}

    async def lookup(self, key: EventReceiptKey):
        return self.rows.get(key)

    async def reserve(self, candidate: EventAdmissionReceipt):
        current = self.rows.get(candidate.receipt_key)
        if current is not None:
            return ReservationResult(current, created=False)
        self.rows[candidate.receipt_key] = candidate
        return ReservationResult(candidate, created=True)


class _EventIdUniqueReceiptStore:
    """Durable store whose insert constraint is the stable event_id.

    Both racing lookups are held until they have missed, then both callers are
    allowed to reach the insert boundary.  The winner is returned to the loser,
    mirroring a database unique constraint on the durable execution id.
    """

    def __init__(self):
        self.rows_by_key = {}
        self.rows_by_event_id = {}
        self._lookup_arrivals = 0
        self._both_lookups_done = asyncio.Event()

    async def lookup(self, key: EventReceiptKey):
        self._lookup_arrivals += 1
        if self._lookup_arrivals == 2:
            self._both_lookups_done.set()
        await self._both_lookups_done.wait()
        return self.rows_by_key.get(key)

    async def reserve(self, candidate: EventAdmissionReceipt):
        # Yield after each lookup has missed so both candidates reach the
        # insert boundary while still in flight.
        await asyncio.sleep(0)
        winner = self.rows_by_event_id.get(candidate.event_id)
        if winner is not None:
            return ReservationResult(winner, created=False)
        self.rows_by_event_id[candidate.event_id] = candidate
        self.rows_by_key[candidate.receipt_key] = candidate
        return ReservationResult(candidate, created=True)


def _workflow(
    *,
    workflow_id="wf_a",
    tenant="tenant_a",
    workspace="workspace_a",
    connection="conn_a",
    source="github",
    event_type="push",
    subscription_id="sub_a",
    enabled=True,
    workflow_enabled=True,
):
    return {
        "id": workflow_id,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "owner_id": "owner_a",
        "enabled": workflow_enabled,
        "revision": 1,
        "name": "original",
        "steps": [{"id": "step_1", "config": {"destination": "channel_a"}}],
        "event_subscriptions": [
            {
                "id": subscription_id,
                "connection_id": connection,
                "source": source,
                "event_type": event_type,
                "enabled": enabled,
            }
        ],
    }


def _event(
    *,
    tenant="tenant_a",
    workspace="workspace_a",
    owner="owner_a",
    connection="conn_a",
    source="github",
    event_type="push",
    provider_id="provider_event_1",
    payload=None,
):
    return WorkflowEvent(
        tenant_id=tenant,
        workspace_id=workspace,
        owner_id=owner,
        connection_id=connection,
        source=source,
        event_type=event_type,
        provider_event_id=provider_id,
        payload={"ref": "main"} if payload is None else payload,
    )


def test_two_domains_and_exact_connection_are_required():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow_a = _workflow(workflow_id="wf_a")
        workflow_b = _workflow(
            workflow_id="wf_b", tenant="tenant_b", workspace="workspace_b"
        )

        admitted_a = await coordinator.admit(_event(), workflow_a)
        admitted_b = await coordinator.admit(
            _event(tenant="tenant_b", workspace="workspace_b"), workflow_b
        )

        assert admitted_a is not None
        assert admitted_b is not None
        assert admitted_a.event_id.startswith("evt_")
        assert admitted_a.event_id != admitted_b.event_id
        assert admitted_a.workflow_snapshot == workflow_a
        assert admitted_a.context["workflow_snapshot"] == workflow_a
        assert admitted_a.context["payload_digest"] == payload_digest({"ref": "main"})
        assert admitted_a.event_inputs[EVENT_ADMISSION_CONTEXT_KEY][
            "workflow_snapshot"
        ] == workflow_a
        assert admitted_a.event_inputs["event"]["payload"] == {"ref": "main"}
        # Event inputs are separate from the workflow's destination config.
        assert "steps" not in admitted_a.event_inputs

        assert (
            await coordinator.admit(_event(connection="conn_other"), workflow_a)
            is None
        )
        assert (
            await coordinator.admit(
                _event(tenant="tenant_b", workspace="workspace_b"), workflow_a
            )
            is None
        )
        assert (
            await coordinator.admit(
                _event(tenant="tenant_a", workspace="workspace_b"), workflow_a
            )
            is None
        )

    asyncio.run(scenario())


def test_event_id_is_deterministic_across_revision_owner_and_payload():
    async def scenario():
        first_workflow = _workflow()
        changed_workflow = _workflow()
        changed_workflow["revision"] = 99
        changed_workflow["name"] = "renamed"
        changed_workflow["steps"] = [
            {"id": "step_9", "config": {"destination": "channel_b"}}
        ]

        first_store = _ReceiptStore()
        first_coordinator = WorkflowEventAdmissionCoordinator(
            first_store.lookup, first_store.reserve
        )
        second_store = _ReceiptStore()
        second_coordinator = WorkflowEventAdmissionCoordinator(
            second_store.lookup, second_store.reserve
        )

        first = await first_coordinator.admit(
            _event(owner="owner_a", payload={"n": 1}), first_workflow
        )
        second = await second_coordinator.admit(
            _event(owner="owner_b", payload={"n": 2}), changed_workflow
        )

        assert first is not None and second is not None
        assert first.event_id == second.event_id
        assert first.event_id == derive_event_id(
            tenant_id="tenant_a",
            workspace_id="workspace_a",
            workflow_id="wf_a",
            connection_id="conn_a",
            source="github",
            event_type="push",
            provider_event_id="provider_event_1",
        )

    asyncio.run(scenario())


def test_concurrent_subscription_replacement_reserves_one_execution():
    async def scenario():
        store = _EventIdUniqueReceiptStore()
        original_workflow = _workflow(subscription_id="sub_original")
        replacement_workflow = _workflow(subscription_id="sub_replacement")
        event = _event(provider_id="provider_event_race")
        original = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        replacement = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)

        before, after = await asyncio.gather(
            original.admit(event, original_workflow),
            replacement.admit(event, replacement_workflow),
        )

        assert before is not None and after is not None
        assert before.event_id == after.event_id
        assert before.receipt.receipt_key == after.receipt.receipt_key
        assert before.event_id == before.receipt.receipt_key.event_id
        assert before.event_id == derive_event_id(
            tenant_id="tenant_a",
            workspace_id="workspace_a",
            workflow_id="wf_a",
            connection_id="conn_a",
            source="github",
            event_type="push",
            provider_event_id="provider_event_race",
        )
        assert len(store.rows_by_event_id) == 1

        winner = store.rows_by_event_id[before.event_id]
        created = [
            admission
            for admission in (before, after)
            if admission.duplicate is False
        ]
        duplicate = [
            admission
            for admission in (before, after)
            if admission.duplicate is True
        ]
        assert len(created) == 1
        assert len(duplicate) == 1
        assert created[0].receipt.subscription_id == winner.subscription_id
        assert duplicate[0].receipt.subscription_id == winner.subscription_id
        assert before.receipt.subscription_id == winner.subscription_id
        assert after.receipt.subscription_id == winner.subscription_id
        assert duplicate[0].receipt == winner

    asyncio.run(scenario())


def test_disabled_subscription_blocks_new_work_but_replays_prior_receipt():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow = _workflow()

        first = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert first is not None

        workflow["event_subscriptions"][0]["enabled"] = False

        replay = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert replay is not None
        assert replay.duplicate is True
        assert replay.event_id == first.event_id
        assert replay.workflow_snapshot == first.workflow_snapshot
        assert replay.context["workflow_snapshot"] == first.workflow_snapshot

        assert (
            await coordinator.admit(_event(provider_id="provider_event_2"), workflow)
            is None
        )
        assert len(store.rows) == 1

    asyncio.run(scenario())


def test_workflow_mutation_preserves_admitted_snapshot_and_replay():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow = _workflow()
        original = copy.deepcopy(workflow)

        first = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert first is not None

        workflow["revision"] = 2
        workflow["name"] = "renamed"
        workflow["steps"][0]["config"]["destination"] = "channel_b"
        workflow["event_subscriptions"][0]["event_type"] = "issues"

        assert first.workflow_snapshot == original

        replay = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert replay is not None
        assert replay.duplicate is True
        assert replay.event_id == first.event_id
        assert replay.receipt.event_type == "push"
        assert replay.workflow_snapshot == original
        assert replay.context["workflow_snapshot"] == original

        # A genuinely new event follows the changed rule and gets a new id.
        new_event = await coordinator.admit(
            _event(provider_id="provider_event_2", event_type="issues"), workflow
        )
        assert new_event is not None
        assert new_event.event_id != first.event_id

    asyncio.run(scenario())


def test_disabled_workflow_blocks_new_work_but_replays_prior_receipt():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow = _workflow()

        first = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert first is not None

        workflow["enabled"] = False

        replay = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert replay is not None
        assert replay.duplicate is True
        assert replay.event_id == first.event_id
        assert replay.context["workflow_snapshot"] == first.workflow_snapshot

        assert (
            await coordinator.admit(_event(provider_id="provider_event_2"), workflow)
            is None
        )
        assert len(store.rows) == 1

    asyncio.run(scenario())


def test_event_type_twins_from_one_resource_keep_distinct_receipts():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow = _workflow(event_type="push")
        workflow["event_subscriptions"].append(
            {
                "id": "sub_b",
                "connection_id": "conn_a",
                "source": "github",
                "event_type": "issues",
                "enabled": True,
            }
        )

        push = await coordinator.admit(_event(event_type="push"), workflow)
        issues = await coordinator.admit(_event(event_type="issues"), workflow)

        assert push is not None and issues is not None
        assert push.event_id != issues.event_id
        assert push.receipt.event_type == "push"
        assert issues.receipt.event_type == "issues"
        assert len(store.rows) == 2
        assert push.receipt.receipt_key != issues.receipt.receipt_key

        push_replay = await coordinator.admit(_event(event_type="push"), workflow)
        issues_replay = await coordinator.admit(_event(event_type="issues"), workflow)
        assert push_replay.duplicate is True
        assert issues_replay.duplicate is True
        assert push_replay.event_id == push.event_id
        assert issues_replay.event_id == issues.event_id

    asyncio.run(scenario())


def test_new_admission_requires_explicit_saved_tenant_and_workspace():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)

        missing_tenant = _workflow()
        missing_tenant.pop("tenant_id")
        assert await coordinator.admit(_event(), missing_tenant) is None

        missing_workspace = _workflow()
        missing_workspace.pop("workspace_id")
        assert await coordinator.admit(_event(), missing_workspace) is None

        assert (
            await coordinator.admit(_event(), _workflow(tenant="tenant_b")) is None
        )
        assert (
            await coordinator.admit(_event(), _workflow(workspace="workspace_b"))
            is None
        )
        assert len(store.rows) == 0

        workflow = _workflow()
        first = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert first is not None

        workflow.pop("tenant_id")
        replay = await coordinator.admit(
            _event(provider_id="provider_event_1"), workflow
        )
        assert replay is not None
        assert replay.duplicate is True
        assert replay.event_id == first.event_id

    asyncio.run(scenario())


def test_reservation_persists_inputs_for_restart_and_recovery_claim():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow = _workflow()
        payload = {"n": 1, "items": [1, 2]}

        first = await coordinator.admit(
            _event(provider_id="provider_event_1", payload=payload), workflow
        )
        assert first is not None

        row = store.rows[first.receipt.receipt_key]
        context = row.input_data[EVENT_ADMISSION_CONTEXT_KEY]
        assert context["execution_id"] == row.event_id == first.event_id
        assert context["workflow_snapshot"] == workflow
        assert row.input_data["event"]["payload"] == payload
        assert "steps" not in row.input_data
        assert row.workflow_snapshot["steps"] == workflow["steps"]
        assert first.receipt.input_data == row.input_data

        # A restarted dispatcher reads the persisted row and resumes with the
        # same normalized inputs instead of relying on the in-memory event.
        restarted = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        replay = await restarted.admit(
            _event(provider_id="provider_event_1", payload=payload), workflow
        )
        assert replay is not None
        assert replay.duplicate is True
        assert replay.event_inputs == row.input_data
        assert replay.context["execution_id"] == row.event_id

    asyncio.run(scenario())


def test_conflicting_payload_for_same_event_is_a_typed_conflict():
    async def scenario():
        store = _ReceiptStore()
        coordinator = WorkflowEventAdmissionCoordinator(store.lookup, store.reserve)
        workflow = _workflow()

        first = await coordinator.admit(
            _event(provider_id="provider_event_1", payload={"n": 1, "items": [1, 2]}),
            workflow,
        )
        assert first is not None

        equivalent = await coordinator.admit(
            _event(provider_id="provider_event_1", payload={"items": [1, 2], "n": 1}),
            workflow,
        )
        assert equivalent is not None
        assert equivalent.duplicate is True
        assert equivalent.event_id == first.event_id

        with pytest.raises(EventPayloadConflict):
            await coordinator.admit(
                _event(
                    provider_id="provider_event_1",
                    payload={"n": 2, "items": [1, 2]},
                ),
                workflow,
            )

    asyncio.run(scenario())
