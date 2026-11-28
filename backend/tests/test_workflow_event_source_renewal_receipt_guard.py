"""Renewal may not dispatch or persist through a peer-moved operation row."""
import asyncio
import pytest
from core import workflow_event_source_renewal as renewal
from core.models import TaskOperationRecord, AuditLog
from tests.test_workflow_event_source_renewal import due_world, document, count
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db

_FIELDS = dict(tenant_id='peer-tenant', workspace_id='peer-workspace',
               operation_id='peer-operation', operation_type='generic:agent:peer-action',
               run_id='peer-run', idempotency_key='peer-key')


@pytest.mark.parametrize('field', list(_FIELDS))
@pytest.mark.parametrize('stage', ['preflight', 'normal', 'refused', 'timeout'])
def test_renewal_preserves_peer_operation_at_every_transition(due_world, field, stage):
    factory, args, provider, original_document, call = due_world
    provider['mode'] = 'normal' if stage == 'preflight' else stage
    original = args['adapter'].service._make_graph_request.side_effect
    peer_state = {}
    def move():
        with factory() as db:
            row = db.query(TaskOperationRecord).filter(
                TaskOperationRecord.operation_id != original_document['operation_id']).one()
            peer_state.update(record_id=row.id, original_id=row.operation_id, status=row.status)
            setattr(row, field, _FIELDS[field])
            db.commit()
    async def wire(method, url, token, data=None, **options):
        target = ((stage == 'preflight' and method == 'GET' and '/subscriptions/' in url)
                  or (stage != 'preflight' and method == 'PATCH'))
        try:
            result = await original(method, url, token, data, **options)
        except Exception:
            if target: move()
            raise
        if target: move()
        return result
    args['adapter'].service._make_graph_request.side_effect = wire
    result = asyncio.run(renewal.renew_source(**call))
    assert result['effect'] == 'unknown' and result['do_not_repeat'] is True, result
    assert result['renewal_operation_id'] == peer_state['original_id']
    assert count(provider, 'PATCH') == (0 if stage == 'preflight' else 1)
    with factory() as db:
        row = db.get(TaskOperationRecord, peer_state['record_id'])
        assert getattr(row, field) == _FIELDS[field]
        assert row.status == peer_state['status'] and row.result_json is None
        assert db.query(TaskOperationRecord).count() == 2
        assert db.query(AuditLog).count() == 3
    after = document(factory)
    assert 'current_lease' not in after
    assert after['pending_lease']['operation_id'] == peer_state['original_id']


def test_unchanged_renewal_receipt_twin(due_world):
    factory, _, provider, _, call = due_world
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'renewed' and result['effect'] == 'committed'
    assert count(provider, 'PATCH') == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 2
        assert db.query(AuditLog).count() == 4


@pytest.mark.parametrize('field', list(_FIELDS))
def test_replay_never_reallocates_moved_renewal_and_restore_only_reads(due_world, field):
    factory, _, provider, _, call = due_world
    provider['mode'] = 'timeout'
    first = asyncio.run(renewal.renew_source(**call))
    assert first['effect'] == 'unknown'
    pending = document(factory)
    operation_id = pending['pending_lease']['operation_id']
    with factory() as db:
        row = db.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id == operation_id).one()
        record_id, old = row.id, getattr(row, field)
        setattr(row, field, _FIELDS[field]); db.commit()
    provider['mode'] = 'normal'
    retry = asyncio.run(renewal.renew_source(**call))
    assert retry['effect'] == 'unknown' and retry['renewal_operation_id'] == operation_id
    assert document(factory) == pending and count(provider, 'PATCH') == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 2
        row = db.get(TaskOperationRecord, record_id)
        assert getattr(row, field) == _FIELDS[field] and row.status == 'uncertain_effect'
        setattr(row, field, old); db.commit()
    recovered = asyncio.run(renewal.renew_source(**call))
    assert recovered['status'] == 'already_applied' and recovered['effect'] == 'committed'
    assert recovered['renewal_operation_id'] == operation_id and count(provider, 'PATCH') == 1


@pytest.mark.parametrize('field', list(_FIELDS))
def test_supersession_cannot_retire_moved_original_row(due_world, monkeypatch, field):
    from core import outbound_operation_claim as operations
    from tests.test_workflow_event_source_resumption import pending_claim, change_input
    factory, args, provider, original_document, call = due_world
    pending, intent, claimed = pending_claim(factory, args, original_document, call)
    change_input(factory, provider, 'credential')
    mark = operations.mark_status
    def peer(record_id, status, **kwargs):
        if record_id == claimed['record_id'] and status == operations.FAILED_BEFORE_EFFECT:
            with factory() as db:
                setattr(db.get(TaskOperationRecord, record_id), field, _FIELDS[field]); db.commit()
        return mark(record_id, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', peer)
    result = asyncio.run(renewal.renew_source(**call))
    assert result['effect'] == 'unknown'
    assert document(factory) == pending and count(provider, 'PATCH') == 0
    with factory() as db:
        row = db.get(TaskOperationRecord, claimed['record_id'])
        assert getattr(row, field) == _FIELDS[field] and row.status == operations.CLAIMED
        assert db.query(TaskOperationRecord).count() == 2 and db.query(AuditLog).count() == 3


@pytest.mark.parametrize('field', ['workspace_id', 'operation_id'])
def test_move_between_inspection_and_claim_does_not_allocate_new_row(due_world, monkeypatch, field):
    from core import outbound_operation_claim as operations
    from tests.test_workflow_event_source_resumption import pending_claim
    factory, args, provider, original_document, call = due_world
    pending, intent, claimed = pending_claim(factory, args, original_document, call)
    claim = operations.claim_generic_operation
    moved = []
    def peer(**kwargs):
        if kwargs['operation_id'] == intent['operation_id'] and not moved:
            moved.append(True)
            with factory() as db:
                setattr(db.get(TaskOperationRecord, claimed['record_id']), field, _FIELDS[field]); db.commit()
        return claim(**kwargs)
    monkeypatch.setattr(operations, 'claim_generic_operation', peer)
    result = asyncio.run(renewal.renew_source(**call))
    assert result['effect'] == 'unknown' and result['renewal_operation_id'] == intent['operation_id']
    assert moved and document(factory) == pending and count(provider, 'PATCH') == 0
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 2
        row = db.get(TaskOperationRecord, claimed['record_id'])
        assert getattr(row, field) == _FIELDS[field] and row.status == operations.CLAIMED
