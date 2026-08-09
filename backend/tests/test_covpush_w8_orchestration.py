"""Coverage wave 8 — core.orchestration.event_bus + workflow_state_machine.

Hermetic: in-memory EventBus / WorkflowStateMachine instances; the delivery
thread is only used where explicitly needed and joined on teardown.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.orchestration.event_bus import (
    EventBus,
    EventBusConfig,
    EventDelivery,
    EventSubscription,
    EventType,
    WorkflowEvent,
    get_event_bus,
)
from core.orchestration.workflow_state_machine import (
    RollbackPlan,
    StateMachineConfig,
    StateSnapshot,
    StateTransition,
    StateTransitionType,
    TransitionLog,
    TransitionResult,
    WorkflowState,
    WorkflowStateMachine,
    get_state_machine,
)


# ===========================================================================
# event_bus
# ===========================================================================

class TestEventBusBasics:
    def test_event_type_values(self):
        assert EventType.WORKFLOW_CREATED.value == "workflow.created"
        assert EventType.STEP_RETRYING.value == "step.retrying"
        assert EventType.SYSTEM_SHUTDOWN.value == "system.shutdown"
        assert EventType.DATA_AVAILABLE.value == "data.available"

    def test_delivery_enum(self):
        assert EventDelivery.EXACTLY_ONCE.value == "exactly_once"

    def test_config_defaults(self):
        cfg = EventBusConfig()
        assert cfg.max_retry_attempts == 3
        assert cfg.event_buffer_size == 10000
        assert cfg.enable_replay is True

    def test_workflow_event_to_dict_and_fingerprint(self):
        evt = WorkflowEvent(
            event_id="e1",
            event_type=EventType.WORKFLOW_STARTED,
            source="wf-1",
            data={"a": 1},
            published_at=datetime(2026, 1, 1),
        )
        d = evt.to_dict()
        assert d["event_type"] == "workflow.started"
        assert d["published_at"] is not None
        assert d["expires_at"] is None
        assert evt.get_fingerprint()
        # Same data/source/type → same fingerprint (dedup contract)
        evt2 = WorkflowEvent(
            event_id="e2",
            event_type=EventType.WORKFLOW_STARTED,
            source="wf-1",
            data={"a": 1},
        )
        assert evt2.get_fingerprint() == evt.get_fingerprint()

    def test_event_fingerprint_differences(self):
        evt1 = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={"a": 1})
        evt2 = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={"a": 2})
        assert evt1.get_fingerprint() != evt2.get_fingerprint()

    def test_subscription_matches(self):
        sub = EventSubscription(
            subscriber_id="s1",
            event_types=[EventType.WORKFLOW_COMPLETED],
            source_filter=r"^wf-.*",
            data_filter={"ok": True},
        )
        evt = WorkflowEvent(
            event_type=EventType.WORKFLOW_COMPLETED,
            source="wf-9",
            data={"ok": True},
        )
        assert sub.matches(evt)
        # wrong type
        evt2 = WorkflowEvent(event_type=EventType.STEP_STARTED, source="wf-9", data={"ok": True})
        assert not sub.matches(evt2)
        # wrong source
        evt3 = WorkflowEvent(event_type=EventType.WORKFLOW_COMPLETED, source="other", data={"ok": True})
        assert not sub.matches(evt3)
        # wrong data
        evt4 = WorkflowEvent(event_type=EventType.WORKFLOW_COMPLETED, source="wf-9", data={"ok": False})
        assert not sub.matches(evt4)
        # inactive
        sub.active = False
        assert not sub.matches(evt)
        # empty event_types + no filters → match
        sub2 = EventSubscription(subscriber_id="s2", event_types=[])
        assert sub2.matches(WorkflowEvent(source="anything"))

    def test_publish_deduplicates(self):
        bus = EventBus()
        e1 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        e2 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        # BUG: duplicate publish returned a FRESH random id for an event that
        # was never stored — callers got an id that KeyErrors in _events.
        assert e1 == e2  # must return the stored event's id
        assert len(bus._events) == 1
        assert e1 in bus._events  # the returned id must actually exist
        # Different data → new event
        e3 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 2})
        assert e3 != e1
        assert len(bus._events) == 2

    def test_publish_delivery_semantic_override(self):
        bus = EventBus()
        bus.publish(
            EventType.WORKFLOW_STARTED, "wf-1", {},
            delivery_semantic=EventDelivery.FIRE_AND_FORGET,
            expires_at=datetime(2026, 1, 1),
        )
        evt = next(iter(bus._events.values()))
        assert evt.delivery_semantic == EventDelivery.FIRE_AND_FORGET
        assert evt.expires_at == datetime(2026, 1, 1)
        assert evt.published_at is not None

    def test_subscribe_unsubscribe(self):
        bus = EventBus()
        calls = []

        def handler(event):
            calls.append(event)

        sid = bus.subscribe("s1", [EventType.WORKFLOW_COMPLETED], handler, source_filter="wf")
        assert sid.startswith("sub_")
        assert bus.unsubscribe(sid) is True
        assert bus.unsubscribe(sid) is False  # already gone
        assert bus.get_subscriptions() == []
        # type index cleaned (empty list remains — defaultdict keeps the key)
        assert bus._type_index[EventType.WORKFLOW_COMPLETED] == []

    def test_unsubscribe_all(self):
        bus = EventBus()
        bus.subscribe("s1", [EventType.WORKFLOW_COMPLETED], lambda e: None)
        bus.subscribe("s1", [EventType.WORKFLOW_FAILED], lambda e: None)
        bus.subscribe("s2", [EventType.WORKFLOW_FAILED], lambda e: None)
        assert bus.unsubscribe_all("s1") == 2
        assert bus.unsubscribe_all("s1") == 0

    def test_start_stop(self):
        bus = EventBus()
        bus.start()
        bus.start()  # idempotent
        assert bus._running is True
        assert bus._delivery_thread is not None
        bus.stop()
        assert bus._running is False
        bus.stop()  # idempotent

    def test_delivery_thread_delivers(self):
        bus = EventBus()
        got = []
        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], lambda e: got.append(e.event_id))
        bus.start()
        try:
            eid = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
            deadline = time.time() + 5
            while not got and time.time() < deadline:
                time.sleep(0.02)
            assert got == [eid]
        finally:
            bus.stop()

    def test_delivery_loop_expired_event_skipped(self):
        bus = EventBus()
        bus.start()
        try:
            # Event already expired — the loop must skip it (no crash).
            eid = bus.publish(
                EventType.WORKFLOW_STARTED, "wf-1", {},
                expires_at=datetime.now() - timedelta(seconds=10),
            )
            time.sleep(0.5)
            # Event exists; nothing delivered because expired.
            assert eid in bus._events
        finally:
            bus.stop()

    def test_deliver_event_retry_after_failure(self):
        bus = EventBus()
        calls = {"n": 0}

        def flaky(event):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("first attempt fails")

        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], flaky)
        bus.subscribe("s2", [EventType.WORKFLOW_STARTED], lambda e: None)
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)
        assert calls["n"] == 1  # retry is async via the delivery queue
        assert evt.failed_deliveries["s1"] == 1
        # Pending retries are keyed by SUBSCRIPTION id (matching _type_index).
        s1_sub_id = next(
            s.subscription_id for s in bus._subscriptions.values() if s.subscriber_id == "s1"
        )
        assert s1_sub_id in evt._pending_retries  # marked for retry
        # s2 succeeded once — not in pending
        s2_sub_id = next(
            s.subscription_id for s in bus._subscriptions.values() if s.subscriber_id == "s2"
        )
        assert s2_sub_id not in evt._pending_retries
        assert evt.delivered_to == ["s2"]  # only the successful subscriber

    def test_deliver_event_retry_guard_stops(self):
        bus = EventBus()
        bus.config.max_retry_attempts = 1
        calls = {"n": 0}

        def always_fail(event):
            calls["n"] += 1
            raise RuntimeError("nope")

        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], always_fail)
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)
        assert calls["n"] == 1  # max_retry_attempts=1 → first failure, no requeue
        assert not hasattr(evt, "_pending_retries") or "s1" not in evt._pending_retries
        assert evt.failed_deliveries["s1"] == 1

    def test_deliver_event_retry_succeeds_on_second_delivery(self):
        """Pending-retry re-delivery must reach only the failing subscriber."""
        bus = EventBus()
        calls = {"n": 0}
        got = []

        def flaky(event):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("first fails")
            got.append(event)

        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], flaky)
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)
        # Now drain the retry queue — second attempt succeeds.
        retried = bus._delivery_queue.get(timeout=1)
        assert retried is evt
        bus._deliver_event(evt)
        assert calls["n"] == 2
        assert got == [evt]
        assert evt.delivered_to == ["s1"]
        assert "s1" not in evt._pending_retries

    def test_deliver_event_exactly_once_ack(self):
        bus = EventBus()
        got = []
        bus.subscribe(
            "s1",
            [EventType.WORKFLOW_STARTED],
            lambda e: got.append(e),
            delivery_semantic=EventDelivery.EXACTLY_ONCE,
        )
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)
        assert got
        ack = bus._ack_results[f"{evt.event_id}:s1"]
        assert ack.success is True
        assert ack.subscriber_id == "s1"

    def test_deliver_event_pending_retries_filter(self):
        """Retry redelivery must reach only the failing SUBSCRIPTION (the
        pending set is keyed by subscription id, matching _type_index)."""
        bus = EventBus()
        sub_id = bus.subscribe("s1", [EventType.WORKFLOW_STARTED], lambda e: None)
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        evt._pending_retries = {sub_id}
        # On retry delivery the pending subscription should receive the event.
        bus._deliver_event(evt)
        assert "s1" in evt.delivered_to
        # After the attempt the subscription is removed from pending.
        assert evt._pending_retries == set()

    def test_deliver_event_missing_subscription_skipped(self):
        bus = EventBus()
        bus._type_index[EventType.WORKFLOW_STARTED].append("ghost")
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)  # no crash
        assert evt.delivered_to == []

    def test_deliver_event_nonmatching_skipped(self):
        bus = EventBus()
        bus.subscribe("s1", [EventType.WORKFLOW_COMPLETED], lambda e: None)
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)
        assert evt.delivered_to == []

    def test_deliver_event_indexed_but_not_matching_skipped(self):
        """Subscriptions in the type index that fail matches() are skipped
        (covers the inner `continue` — no type-index entry for the event
        type skips the whole loop, so the per-sub continue needs a sub that
        is indexed but does not match)."""
        bus = EventBus()
        bus.subscribe(
            "s1", [EventType.WORKFLOW_STARTED], lambda e: None, source_filter=r"^wf-only-"
        )
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="other", data={})
        bus._deliver_event(evt)
        assert evt.delivered_to == []

    def test_get_events_filters(self):
        bus = EventBus()
        bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"n": 1})
        bus.publish(EventType.WORKFLOW_COMPLETED, "wf-1", {"n": 2})
        bus.publish(EventType.WORKFLOW_COMPLETED, "wf-2", {"n": 3})
        assert len(bus.get_events()) == 3
        assert len(bus.get_events(source="wf-1")) == 2
        assert len(bus.get_events(event_type=EventType.WORKFLOW_COMPLETED)) == 2
        assert len(bus.get_events(source="wf-2", event_type=EventType.WORKFLOW_COMPLETED)) == 1
        assert len(bus.get_events(limit=2)) == 2
        assert len(bus.get_events(since=datetime.now() + timedelta(days=1))) == 0

    def test_get_subscriptions_filter(self):
        bus = EventBus()
        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], lambda e: None)
        bus.subscribe("s2", [EventType.WORKFLOW_STARTED], lambda e: None)
        subs = bus.get_subscriptions(subscriber_id="s1")
        assert [s.subscriber_id for s in subs] == ["s1"]
        assert len(bus.get_subscriptions()) == 2

    @staticmethod
    def _drain(bus: EventBus) -> None:
        """Deliver everything currently queued (no delivery thread in tests)."""
        while not bus._delivery_queue.empty():
            bus._deliver_event(bus._delivery_queue.get())

    def test_create_workflow_trigger(self):
        bus = EventBus()
        sid = bus.create_workflow_trigger("wf-9", EventType.WEBHOOK_TRIGGER)
        assert sid.startswith("sub_")
        # Trigger a WEBHOOK_TRIGGER event → handler publishes WORKFLOW_STARTED.
        got = []
        bus.subscribe("wf-9", [EventType.WORKFLOW_STARTED], lambda e: got.append(e))
        bus.publish(EventType.WEBHOOK_TRIGGER, "anything", {"a": 1})
        self._drain(bus)
        assert got
        started = got[0]
        assert started.data["triggered_by"] == "webhook.trigger"

    def test_trigger_condition_false_skips(self):
        bus = EventBus()
        # Note: safe_eval blocks method calls, so conditions must use the
        # `data['key']` subscript syntax (the `data` binding is event.data).
        bus.create_workflow_trigger("wf-9", EventType.WEBHOOK_TRIGGER, condition="data['go'] == True")
        got = []
        bus.subscribe("wf-9", [EventType.WORKFLOW_STARTED], lambda e: got.append(e))

        def publish_and_drain(data):
            bus.publish(EventType.WEBHOOK_TRIGGER, "x", data)
            self._drain(bus)

        publish_and_drain({"go": False})
        assert got == []
        publish_and_drain({"go": True})
        assert len(got) == 1

    def test_trigger_condition_safe_eval_rejected(self):
        bus = EventBus()
        # Malicious condition — must fail LOUDLY at registration (R97-wave
        # footgun: unsafe conditions were accepted and then silently dropped
        # at every delivery). No code execution at any point.
        with pytest.raises(ValueError):
            bus.create_workflow_trigger(
                "wf-9", EventType.WEBHOOK_TRIGGER, condition="__import__('os').system('true')"
            )
        # And a benign condition on an unsafe-namespace still registers.
        bus.create_workflow_trigger(
            "wf-9", EventType.WEBHOOK_TRIGGER, condition="data['status'] == 'done'"
        )
        got = []
        bus.subscribe("wf-9", [EventType.WORKFLOW_STARTED], lambda e: got.append(e))
        bus.publish(EventType.WEBHOOK_TRIGGER, "x", {"status": "done"})
        self._drain(bus)
        assert len(got) == 1, "benign subscript condition must fire"

    def test_trigger_condition_exception_skips(self):
        bus = EventBus()
        with patch("core.safe_evaluator.safe_eval", side_effect=RuntimeError("boom")):
            bus.create_workflow_trigger(
                "wf-9", EventType.WEBHOOK_TRIGGER, condition="data['missing']"
            )
            got = []
            bus.subscribe("wf-9", [EventType.WORKFLOW_STARTED], lambda e: got.append(e))
            bus.publish(EventType.WEBHOOK_TRIGGER, "x", {})
            self._drain(bus)
            assert got == []

    def test_get_statistics(self):
        bus = EventBus()
        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], lambda e: None)
        bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {})
        stats = bus.get_statistics()
        assert stats["total_events"] == 1
        assert stats["buffer_size"] == 1
        assert stats["total_subscriptions"] == 1
        assert stats["active_subscriptions"] == 1
        assert stats["type_index_size"] == 1
        assert stats["running"] is False

    def test_delivery_loop_exception_swallowed(self):
        """_delivery_loop must survive a _deliver_event exception."""
        import threading
        import time as _time

        bus = EventBus()

        def boom(event):
            raise RuntimeError("delivery exploded")

        bus._deliver_event = boom  # type: ignore[assignment]
        bus._running = True
        bus._delivery_queue.put(WorkflowEvent(event_type=EventType.WORKFLOW_STARTED))
        t = threading.Thread(target=bus._delivery_loop, daemon=True)
        t.start()
        _time.sleep(0.3)
        bus._running = False
        t.join(timeout=5)
        assert not t.is_alive()  # loop exited cleanly, exception was swallowed

    def test_deliver_event_no_handler_skipped(self):
        bus = EventBus()
        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], handler=None)
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        bus._deliver_event(evt)
        assert evt.delivered_to == []

    def test_publish_dedup_fallback_phantom_id(self):
        """If the fingerprint is known but the event is gone from memory
        (e.g. buffer evicted), publish returns a fresh id rather than
        KeyError-ing on lookups."""
        bus = EventBus()
        e1 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        assert e1 in bus._events
        # Simulate memory eviction of the stored event.
        bus._events.clear()
        e2 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        assert e2 != e1
        assert e2 in bus._events  # a real (fresh) event was stored

    def test_deliver_event_retry_skips_non_pending(self):
        """On retry redelivery, subscriptions NOT in pending are skipped."""
        bus = EventBus()
        calls = {"s1": 0, "s2": 0}
        bus.subscribe("s1", [EventType.WORKFLOW_STARTED], lambda e: calls.__setitem__("s1", calls["s1"] + 1))
        s2_sub = bus.subscribe("s2", [EventType.WORKFLOW_STARTED], lambda e: calls.__setitem__("s2", calls["s2"] + 1))
        evt = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={})
        evt._pending_retries = {s2_sub}
        bus._deliver_event(evt)
        assert calls["s1"] == 0  # skipped — not in pending
        assert calls["s2"] == 1  # delivered — in pending

    def test_get_event_bus_singleton(self):
        with patch("core.orchestration.event_bus._event_bus_instance", None):
            bus1 = get_event_bus()
            bus2 = get_event_bus()
            assert bus1 is bus2
            bus1.stop()
            # reset for other tests
            from core.orchestration import event_bus as eb

            eb._event_bus_instance = None


# ===========================================================================
# workflow_state_machine
# ===========================================================================

class TestStateMachineBasics:
    def test_workflow_state_values(self):
        assert WorkflowState.CREATED.value == "created"
        assert WorkflowState.ROLLING_BACK.value == "rolling_back"
        assert WorkflowState.SUSPENDED.value == "suspended"

    def test_transition_result_enum(self):
        assert TransitionResult.BLOCKED.value == "blocked"

    def test_state_transition_can_execute(self):
        t = StateTransition()
        assert t.can_execute({}) is True
        t.guard_function = lambda ctx: ctx.get("ok", False)
        assert t.can_execute({"ok": True}) is True
        assert t.can_execute({"ok": False}) is False

    def test_rollback_plan_is_expired(self):
        plan = RollbackPlan(workflow_id="wf-1")
        assert plan.is_expired() is False
        plan.expires_at = datetime.now() - timedelta(seconds=1)
        assert plan.is_expired() is True

    def test_state_snapshot_to_dict(self):
        snap = StateSnapshot(
            snapshot_id="s1",
            workflow_id="wf-1",
            execution_id="ex-1",
            current_state=WorkflowState.RUNNING,
            step_states={"step1": "done"},
            context_data={"a": 1},
            output_data={"b": 2},
        )
        d = snap.to_dict()
        assert d["current_state"] == "running"
        assert d["step_states"] == {"step1": "done"}

    def test_transition_log_defaults(self):
        log = TransitionLog()
        assert log.triggered_by == "system"
        assert log.duration_ms == 0.0

    def test_initialize_and_get_state(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        assert sm.get_state("wf-1") == WorkflowState.CREATED
        assert sm.get_state("nope") is None
        assert len(sm.get_transition_history("wf-1")) == 1

    def test_can_transition(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        assert sm.can_transition("wf-1", WorkflowState.VALIDATED) is True
        assert sm.can_transition("wf-1", WorkflowState.COMPLETED) is False
        assert sm.can_transition("unknown", WorkflowState.VALIDATED) is False
        # allow_invalid_transitions
        sm2 = WorkflowStateMachine(config=StateMachineConfig(allow_invalid_transitions=True))
        sm2.initialize_state("wf-1", "ex-1")
        assert sm2.can_transition("wf-1", WorkflowState.COMPLETED) is True

    def test_transition_lifecycle(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED) == TransitionResult.SUCCESS
        assert sm.get_state("wf-1") == WorkflowState.VALIDATED
        assert sm.transition("wf-1", "ex-1", WorkflowState.QUEUED) == TransitionResult.SUCCESS
        assert sm.transition("wf-1", "ex-1", WorkflowState.RUNNING) == TransitionResult.SUCCESS
        assert sm.transition("wf-1", "ex-1", WorkflowState.COMPLETED) == TransitionResult.SUCCESS
        assert sm.get_state("wf-1") == WorkflowState.COMPLETED
        # Terminal: no further transitions
        assert sm.transition("wf-1", "ex-1", WorkflowState.FAILED) == TransitionResult.INVALID
        # History recorded
        hist = sm.get_transition_history("wf-1")
        assert len(hist) == 5  # init + 4 transitions

    def test_transition_unknown_workflow_failed(self):
        sm = WorkflowStateMachine()
        assert sm.transition("wf-x", "ex-x", WorkflowState.RUNNING) == TransitionResult.FAILED

    def test_transition_guard_blocked(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        sm.add_guard(WorkflowState.CREATED, WorkflowState.VALIDATED, lambda ctx: ctx.get("ok", False))
        assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED) == TransitionResult.BLOCKED
        assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED, context={"ok": True}) == TransitionResult.SUCCESS

    def test_transition_pre_action_failure(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")

        def bad_pre(wf_id, ctx):
            raise RuntimeError("pre failed")

        sm.add_pre_action(WorkflowState.CREATED, WorkflowState.VALIDATED, bad_pre)
        assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED) == TransitionResult.FAILED
        assert sm.get_state("wf-1") == WorkflowState.CREATED

    def test_transition_pre_post_actions(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        calls = []

        def pre(wf_id, ctx):
            calls.append(("pre", wf_id))

        def post(wf_id, ctx):
            calls.append(("post", wf_id))

        sm.add_pre_action(WorkflowState.CREATED, WorkflowState.VALIDATED, pre)
        sm.add_post_action(WorkflowState.CREATED, WorkflowState.VALIDATED, post)
        assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED) == TransitionResult.SUCCESS
        assert ("pre", "wf-1") in calls
        assert ("post", "wf-1") in calls

    def test_post_action_failure_does_not_revert(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")

        def bad_post(wf_id, ctx):
            raise RuntimeError("post failed")

        sm.add_post_action(WorkflowState.CREATED, WorkflowState.VALIDATED, bad_post)
        # State change still applied despite post-action error
        assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED) == TransitionResult.SUCCESS
        assert sm.get_state("wf-1") == WorkflowState.VALIDATED

    def test_persistence_disabled_no_snapshot(self):
        sm = WorkflowStateMachine(config=StateMachineConfig(enable_persistence=False))
        sm.initialize_state("wf-1", "ex-1")
        sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED)
        assert sm.get_snapshots("wf-1") == []

    def test_snapshots_created_and_capped(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        # Force >100 snapshots via direct call
        for _ in range(105):
            sm._create_snapshot("wf-1", "ex-1")
        snaps = sm.get_snapshots("wf-1")
        assert len(snaps) == 10  # default limit
        assert len(sm._snapshots["wf-1"]) == 100
        # limit param
        assert len(sm.get_snapshots("wf-1", limit=3)) == 3
        assert sm.get_snapshots("unknown") == []

    def test_create_snapshot_unknown_workflow(self):
        sm = WorkflowStateMachine()
        assert sm._create_snapshot("nope", "ex-1") is None

    def test_restore_from_snapshot(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED)
        sm.transition("wf-1", "ex-1", WorkflowState.QUEUED)
        sm.transition("wf-1", "ex-1", WorkflowState.RUNNING)
        # Last snapshot BEFORE the COMPLETED transition is RUNNING.
        snap = sm._snapshots["wf-1"][-1]
        assert snap.current_state == WorkflowState.RUNNING
        sm.transition("wf-1", "ex-1", WorkflowState.COMPLETED)
        assert sm.restore_from_snapshot("wf-1", snap) is True
        assert sm.get_state("wf-1") == WorkflowState.RUNNING

    def test_create_rollback_plan(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        plan = sm.create_rollback_plan("wf-1", "ex-1", ["refund", "cleanup"])
        assert plan.workflow_id == "wf-1"
        assert plan.compensation_actions == ["refund", "cleanup"]
        assert plan.target_state == WorkflowState.ROLLED_BACK
        assert plan.expires_at is not None

    def test_create_rollback_plan_unknown_workflow_raises(self):
        sm = WorkflowStateMachine()
        with pytest.raises(ValueError):
            sm.create_rollback_plan("nope", "ex-1", [])

    def test_execute_rollback_no_plan(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        # No rollback plan → execute_rollback FAILED (covered in async test)
        assert sm._rollback_plans.get("wf-1") is None

    def _to_running(self, sm):
        sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED)
        sm.transition("wf-1", "ex-1", WorkflowState.QUEUED)
        sm.transition("wf-1", "ex-1", WorkflowState.RUNNING)

    async def test_execute_rollback_success(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        self._to_running(sm)
        sm.create_rollback_plan("wf-1", "ex-1", ["comp1"])
        result = await sm.execute_rollback("wf-1", "ex-1")
        assert result == TransitionResult.SUCCESS
        assert sm.get_state("wf-1") == WorkflowState.ROLLED_BACK
        plan = sm._rollback_plans["wf-1"]
        assert plan.executed is True
        assert plan.result == "success"

    async     def test_execute_rollback_from_failed_state(self):
        """BUG: FAILED → ROLLING_BACK was not in VALID_TRANSITIONS, so a
        rollback of an already-failed workflow (the normal failure path)
        always returned INVALID — compensation never ran."""
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        self._to_running(sm)
        sm.transition("wf-1", "ex-1", WorkflowState.FAILED)
        sm.create_rollback_plan("wf-1", "ex-1", ["comp1"])
        result = await sm.execute_rollback("wf-1", "ex-1")
        assert result == TransitionResult.SUCCESS
        assert sm.get_state("wf-1") == WorkflowState.ROLLED_BACK

    def test_can_transition_rolling_back_reachable(self):
        """BUG: ROLLING_BACK was NOT in any state's target set — the whole
        rollback feature was unreachable (execute_rollback always INVALID).
        Both RUNNING and FAILED must allow entry into ROLLING_BACK."""
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        assert WorkflowState.ROLLING_BACK in sm.VALID_TRANSITIONS[WorkflowState.RUNNING]
        assert WorkflowState.ROLLING_BACK in sm.VALID_TRANSITIONS[WorkflowState.FAILED]
        self._to_running(sm)
        assert sm.can_transition("wf-1", WorkflowState.ROLLING_BACK) is True

    async def test_execute_rollback_no_plan_async(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        result = await sm.execute_rollback("wf-1", "ex-1")
        assert result == TransitionResult.FAILED

    async def test_execute_rollback_expired_plan(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        self._to_running(sm)
        plan = sm.create_rollback_plan("wf-1", "ex-1", ["comp1"])
        plan.expires_at = datetime.now() - timedelta(seconds=5)
        result = await sm.execute_rollback("wf-1", "ex-1")
        assert result == TransitionResult.FAILED

    async def test_execute_rollback_transition_failure(self):
        sm = WorkflowStateMachine()
        # State COMPLETED → ROLLING_BACK invalid → rollback fails
        sm.initialize_state("wf-1", "ex-1")
        sm.transition("wf-1", "ex-1", WorkflowState.COMPLETED)
        sm.create_rollback_plan("wf-1", "ex-1", ["comp1"])
        result = await sm.execute_rollback("wf-1", "ex-1")
        assert result == TransitionResult.INVALID

    def test_get_statistics(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        sm.initialize_state("wf-2", "ex-2")
        sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED)
        sm.transition("wf-1", "ex-1", WorkflowState.QUEUED)
        sm.transition("wf-1", "ex-1", WorkflowState.RUNNING)
        stats = sm.get_statistics()
        assert stats["total_workflows"] == 2
        assert stats["state_distribution"]["created"] == 1
        assert stats["state_distribution"]["running"] == 1
        assert stats["total_transitions"] == 5  # 2 inits + 3 transitions
        assert stats["rollback_plans"] == 0
        assert stats["total_snapshots"] >= 1

    def test_transition_state_vanishes_under_lock(self):
        """If a concurrent transition clears the workflow between the initial
        read and the lock acquisition, transition returns FAILED."""
        sm = WorkflowStateMachine()
        real_states = {"wf-1": WorkflowState.CREATED}

        def get_state(wf_id):
            if getattr(sm, "_first_read", True):
                sm._first_read = False
                return real_states.get(wf_id)
            return None  # vanished under the lock

        with patch.object(sm, "get_state", side_effect=get_state):
            assert sm.transition("wf-1", "ex-1", WorkflowState.VALIDATED) == TransitionResult.FAILED

    async def test_execute_rollback_compensation_failure(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        self._to_running(sm)
        plan = sm.create_rollback_plan("wf-1", "ex-1", ["comp1"])
        plan.max_attempts = 1  # first failure exhausts attempts
        with patch(
            "core.orchestration.workflow_state_machine.asyncio.sleep",
            side_effect=RuntimeError("compensation crashed"),
        ):
            result = await sm.execute_rollback("wf-1", "ex-1")
        assert result == TransitionResult.FAILED

    def test_restore_from_snapshot_failure(self):
        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        snap = sm.get_snapshots("wf-1")[0] if sm._snapshots.get("wf-1") else None
        if snap is None:
            sm._create_snapshot("wf-1", "ex-1")
            snap = sm._snapshots["wf-1"][-1]
        broken = MagicMock(spec=dict)
        broken.__setitem__ = MagicMock(side_effect=RuntimeError("state store down"))
        sm._workflow_states = broken
        assert sm.restore_from_snapshot("wf-1", snap) is False

    def test_get_state_machine_singleton(self):
        with patch("core.orchestration.workflow_state_machine._state_machine_instance", None):
            sm1 = get_state_machine()
            sm2 = get_state_machine()
            assert sm1 is sm2
            from core.orchestration import workflow_state_machine as wsm

            wsm._state_machine_instance = None

    def test_concurrent_transitions_serialize(self):
        """Two threads transitioning the same workflow must not corrupt state."""
        import threading

        sm = WorkflowStateMachine()
        sm.initialize_state("wf-1", "ex-1")
        errors = []

        def worker():
            try:
                for _ in range(20):
                    sm.transition("wf-1", "ex-1", WorkflowState.RUNNING)
                    sm.transition("wf-1", "ex-1", WorkflowState.PAUSED)
                    sm.transition("wf-1", "ex-1", WorkflowState.RUNNING)
                    sm.transition("wf-1", "ex-1", WorkflowState.PAUSED)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
