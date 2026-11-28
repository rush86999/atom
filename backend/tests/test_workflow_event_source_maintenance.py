"""Real source lease effects and existing-worker ownership; Graph wire controlled."""
import asyncio
import copy
from datetime import datetime
import pytest
from core import workflow_event_worker as worker
from core import workflow_event_source_renewal as renewal
from core import workflow_event_source_registration as registry
from core import outbound_operation_claim as operations
from core.models import TenantSetting, TaskOperationRecord
from tests.test_workflow_event_source_renewal import due_world, document, count
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


def use_source_clock(monkeypatch):
    from core.workflow_event_source_adapters import datetime as Clock
    monkeypatch.setattr(renewal, 'datetime', Clock)


def test_real_due_source_renews_once_and_replays(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    use_source_clock(monkeypatch)
    async def check():
        first = await worker.maintain_source_leases_once(db_factory=factory,
            adapter_factory=lambda source: args['adapter'])
        assert first == {'scanned': 1, 'attempted': 1, 'after_id': None}
        assert 'current_lease' in document(factory)
        await worker.maintain_source_leases_once(db_factory=factory,
            adapter_factory=lambda source: args['adapter'])
    asyncio.run(check())
    assert count(provider, 'PATCH') == count(provider, 'POST') == 1


def test_bad_and_disabled_first_page_cannot_hide_later_source(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    use_source_clock(monkeypatch)
    with factory() as db:
        db.query(TenantSetting).one().id = 'z-ready'
        disabled = dict(original, connection_id='disabled', enabled=False)
        db.add_all([TenantSetting(id='a-broken', tenant_id='tenant',
            setting_key='workflow_event_source:broken', setting_value='{bad'),
            TenantSetting(id='b-disabled', tenant_id='tenant',
                setting_key=registry._key('disabled', 'outlook'), setting_value=registry._json(disabled))])
        db.commit()
    async def check():
        first = await worker.maintain_source_leases_once(limit=2, db_factory=factory,
            adapter_factory=lambda source: args['adapter'])
        assert first == {'scanned': 2, 'attempted': 0, 'after_id': 'b-disabled'}
        second = await worker.maintain_source_leases_once(after_id=first['after_id'], limit=2,
            db_factory=factory, adapter_factory=lambda source: args['adapter'])
        assert second == {'scanned': 1, 'attempted': 1, 'after_id': None}
    asyncio.run(check())
    assert count(provider, 'PATCH') == 1


def test_timeout_after_patch_is_reconciled_without_resend(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    use_source_clock(monkeypatch)
    monkeypatch.setattr(worker, 'SOURCE_LEASE_SOURCE_TIMEOUT_SECONDS', 0.2)
    original_wire = args['adapter'].service._make_graph_request.side_effect
    async def wire(method, *rest):
        result = await original_wire(method, *rest)
        if method == 'PATCH': await asyncio.Event().wait()
        return result
    args['adapter'].service._make_graph_request.side_effect = wire
    async def check():
        first = await worker.maintain_source_leases_once(db_factory=factory,
            adapter_factory=lambda source: args['adapter'])
        assert first['attempted'] == 1
        assert 'pending_lease' in document(factory)
        with factory() as db:
            assert db.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id ==
                document(factory)['pending_lease']['operation_id']).one().status == operations.DISPATCHING
        args['adapter'].service._make_graph_request.side_effect = original_wire
        await worker.maintain_source_leases_once(db_factory=factory,
            adapter_factory=lambda source: args['adapter'])
        assert 'current_lease' in document(factory)
    asyncio.run(check())
    assert count(provider, 'PATCH') == 1


def test_worker_polls_while_maintenance_pending_and_owns_shutdown(monkeypatch):
    async def check():
        started, polled, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
        ticks = []
        tasks = []
        async def tick():
            ticks.append(1)
            if len(ticks) >= 3: polled.set()
        async def maintenance(**kwargs):
            tasks.append(asyncio.current_task())
            started.set()
            try: await asyncio.Event().wait()
            finally: stopped.set()
        monkeypatch.setattr(worker, 'process_pending_event_executions_once', tick)
        monkeypatch.setattr(worker, 'maintain_source_leases_once', maintenance)
        monkeypatch.setattr(worker, 'EVENT_POLL_INTERVAL_SECONDS', 0.005)
        assert worker.start_workflow_event_worker()
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.wait_for(polled.wait(), 2)
            assert len(tasks) == 1 and not tasks[0].done()
        finally: await worker.stop_workflow_event_worker()
        assert stopped.is_set() and tasks[0].done()
        assert worker._maintenance_task is None and worker._worker_task is None
        started.clear()
        assert worker.start_workflow_event_worker()
        try:
            await asyncio.wait_for(started.wait(), 2)
            assert len(tasks) == 2
        finally: await worker.stop_workflow_event_worker()
        assert all(t.done() for t in tasks)
    asyncio.run(check())


def test_worker_advances_cursor_and_throttles_finished_pages(monkeypatch):
    async def check():
        seen, times = [], []
        second = asyncio.Event()
        async def tick(): pass
        async def maintenance(after_id=None):
            seen.append(after_id); times.append(asyncio.get_running_loop().time())
            if len(seen) == 2: second.set()
            return {'after_id': 'next' if after_id is None else None}
        monkeypatch.setattr(worker, 'process_pending_event_executions_once', tick)
        monkeypatch.setattr(worker, 'maintain_source_leases_once', maintenance)
        monkeypatch.setattr(worker, 'EVENT_POLL_INTERVAL_SECONDS', 0.005)
        monkeypatch.setattr(worker, 'SOURCE_LEASE_INTERVAL_SECONDS', 0.04)
        assert worker.start_workflow_event_worker()
        try: await asyncio.wait_for(second.wait(), 2)
        finally: await worker.stop_workflow_event_worker()
        assert seen[:2] == [None, 'next']
        assert times[1] - times[0] >= 0.04
    asyncio.run(check())


def test_slow_first_source_does_not_block_real_later_source(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    use_source_clock(monkeypatch)
    with factory() as db:
        db.query(TenantSetting).one().id = 'z-ready'
        slow = dict(original, connection_id='slow', operation_id='slow-operation')
        db.add(TenantSetting(id='a-slow', tenant_id='tenant',
            setting_key=registry._key('slow', 'outlook'), setting_value=registry._json(slow)))
        db.commit()
    real = renewal.renew_source
    async def first_slow(connection_id, *args, **kwargs):
        if connection_id == 'slow': await asyncio.Event().wait()
        return await real(connection_id, *args, **kwargs)
    monkeypatch.setattr(renewal, 'renew_source', first_slow)
    monkeypatch.setattr(worker, 'SOURCE_LEASE_SOURCE_TIMEOUT_SECONDS', 0.2)
    result = asyncio.run(worker.maintain_source_leases_once(db_factory=factory,
        adapter_factory=lambda source: args['adapter']))
    assert result == {'scanned': 2, 'attempted': 2, 'after_id': None}
    assert count(provider, 'PATCH') == 1
    with factory() as db:
        value = registry._read_document(db.get(TenantSetting, 'z-ready'))
        assert 'current_lease' in value


def test_direct_worker_cancellation_cleans_owned_maintenance(monkeypatch):
    async def check():
        started, cleaned = asyncio.Event(), asyncio.Event()
        tasks = []
        async def tick(): pass
        async def maintenance(**kwargs):
            tasks.append(asyncio.current_task()); started.set()
            try: await asyncio.Event().wait()
            finally: cleaned.set()
        monkeypatch.setattr(worker, 'process_pending_event_executions_once', tick)
        monkeypatch.setattr(worker, 'maintain_source_leases_once', maintenance)
        assert worker.start_workflow_event_worker()
        parent = worker._worker_task
        await asyncio.wait_for(started.wait(), 2)
        parent.cancel()
        with pytest.raises(asyncio.CancelledError): await parent
        assert cleaned.is_set() and tasks[0].done()
        assert worker._maintenance_task is None
        worker._worker_task = None
    asyncio.run(check())
