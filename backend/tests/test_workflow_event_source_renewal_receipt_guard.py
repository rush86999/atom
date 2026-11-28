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
