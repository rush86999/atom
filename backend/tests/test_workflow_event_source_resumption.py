"""Relevant-input resumption must never reset uncertain provider operations."""
import asyncio
import copy
from datetime import datetime, timedelta
import pytest
from core import workflow_event_source_renewal as renewal
from core import workflow_event_source_registration as registry
from core import outbound_operation_claim as operations
from core.connection_service import ConnectionService
from core.models import User, UserConnection, TaskOperationRecord, AuditLog
from tests.test_workflow_event_source_renewal import due_world, document, count
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


def change_input(factory, provider, kind):
    with factory() as db:
        if kind == 'credential':
            db.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token': 'new-synthetic'})
            provider['expected_token'] = 'new-synthetic'
        elif kind == 'role': db.get(User, 'owner').role = 'owner'
        elif kind == 'last_login': db.get(User, 'owner').last_login = datetime(2026, 1, 1)
        elif kind == 'tenant': db.get(User, 'owner').tenant_id = 'foreign'
        db.commit()


def operation(factory, operation_id):
    with factory() as db:
        row = db.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id == operation_id).one()
        return {k: getattr(row, k) for k in ('id', 'workspace_id', 'tenant_id', 'run_id',
            'operation_id', 'idempotency_key', 'payload_sha256', 'operation_type', 'status', 'result_json')}


def pending_claim(factory, args, original, call, status=operations.CLAIMED):
    pending = renewal._prepare(original, args['adapter'], call['now'], factory)
    intent = pending['pending_lease']
    identity = pending['identity']
    row = operations.claim_generic_operation(workspace_id=identity['workspace_id'],
        tenant_id=identity['tenant_id'], operation_id=intent['operation_id'], action=renewal._ACTION,
        payload_hash=renewal._hash(pending, intent), execution_id=intent['operation_id'], db_factory=factory)
    if status != operations.CLAIMED:
        assert operations.mark_status(row['record_id'], status, expected_status=operations.CLAIMED,
            expected_payload_sha256=renewal._hash(pending, intent), db_factory=factory,
            result=renewal._receipt(pending, intent) if status == operations.SUCCEEDED else None)
    return pending, intent, row


@pytest.mark.parametrize('kind', ['credential', 'role'])
def test_confirmed_refusal_resumes_only_after_relevant_input(due_world, kind):
    factory, args, provider, original, call = due_world
    provider['mode'] = 'refused'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_applied'
    refused = copy.deepcopy(document(factory)['pending_lease'])
    old = operation(factory, refused['operation_id'])
    provider['mode'] = 'normal'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_applied'
    change_input(factory, provider, 'last_login')
    assert asyncio.run(renewal.renew_source(**dict(call, now=call['now'] + timedelta(hours=1))))['status'] == 'not_applied'
    assert count(provider, 'PATCH') == 1
    change_input(factory, provider, kind)
    resumed = asyncio.run(renewal.renew_source(**call))
    assert resumed['status'] == 'renewed', resumed
    assert operation(factory, refused['operation_id']) == old
    current = document(factory)['current_lease']['intent']
    assert current['operation_id'] != refused['operation_id']
    assert current['supersedes'] == {'operation_id': refused['operation_id'], 'payload_sha256': old['payload_sha256']}
    assert count(provider, 'PATCH') == 2 and count(provider, 'POST') == 1
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_due'


@pytest.mark.parametrize('kind', ['credential', 'role'])
def test_never_dispatched_claim_is_retired_before_new_material_dispatch(due_world, kind):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call)
    old = operation(factory, intent['operation_id'])
    change_input(factory, provider, kind)
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'renewed', result
    retired = operation(factory, intent['operation_id'])
    assert retired['status'] == operations.FAILED_BEFORE_EFFECT
    assert {k:v for k,v in retired.items() if k != 'status'} == {k:v for k,v in old.items() if k != 'status'}
    assert document(factory)['current_lease']['intent']['operation_id'] != intent['operation_id']
    assert count(provider, 'PATCH') == 1


def test_real_unknown_after_patch_does_not_resume_with_new_grant(due_world):
    factory, args, provider, original, call = due_world
    provider['mode'] = 'timeout'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'effect_unknown'
    before = copy.deepcopy(document(factory))
    intent = before['pending_lease']; old = operation(factory, intent['operation_id'])
    change_input(factory, provider, 'credential')
    provider['mode'] = 'normal'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'effect_unknown'
    assert document(factory) == before and operation(factory, intent['operation_id']) == old
    assert count(provider, 'PATCH') == 1


@pytest.mark.parametrize('status', [operations.DISPATCHING, operations.UNCERTAIN_EFFECT, operations.SUCCEEDED])
def test_inflight_unknown_or_success_cannot_be_superseded(due_world, status):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call, status)
    old = operation(factory, intent['operation_id'])
    change_input(factory, provider, 'credential')
    result = asyncio.run(renewal.renew_source(**call))
    assert result['effect'] == 'unknown', result
    assert document(factory) == pending and operation(factory, intent['operation_id']) == old
    assert count(provider, 'PATCH') == 0


def test_scope_move_never_becomes_new_authority(due_world):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call)
    change_input(factory, provider, 'tenant')
    with pytest.raises(registry.SourceRegistrationError): asyncio.run(renewal.renew_source(**call))
    assert document(factory) == pending
    assert count(provider, 'PATCH') == 0
