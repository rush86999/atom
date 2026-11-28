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


def test_peer_inflight_transition_wins_over_supersession(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call)
    old = operation(factory, intent['operation_id'])
    change_input(factory, provider, 'credential')
    mark = operations.mark_status; raced = []
    def peer(record_id, status, **kwargs):
        if record_id == old['id'] and status == operations.FAILED_BEFORE_EFFECT and not raced:
            raced.append(True)
            assert mark(record_id, operations.DISPATCHING, expected_status=operations.CLAIMED,
                expected_payload_sha256=old['payload_sha256'], db_factory=factory)
        return mark(record_id, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', peer)
    result = asyncio.run(renewal.renew_source(**call))
    assert raced and result['effect'] == 'unknown', result
    assert document(factory) == pending
    assert operation(factory, intent['operation_id'])['status'] == operations.DISPATCHING
    assert count(provider, 'PATCH') == 0


def test_supersession_audit_failure_rolls_back_old_status_and_source(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call)
    old = operation(factory, intent['operation_id'])
    change_input(factory, provider, 'credential')
    def fail(*a, **kw): raise RuntimeError('synthetic audit failure')
    monkeypatch.setattr(renewal, '_audit', fail)
    result = asyncio.run(renewal.renew_source(**call))
    assert result['effect'] == 'unknown', result
    assert document(factory) == pending and operation(factory, intent['operation_id']) == old
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 2
        assert db.query(AuditLog).count() == 3
    assert count(provider, 'PATCH') == 0


def test_fresh_grant_is_read_after_supersession_not_reused_from_stale_cache(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call)
    change_input(factory, provider, 'credential')
    mark = operations.mark_status; raced = []
    def newer_grant(record_id, status, **kwargs):
        if record_id == row['record_id'] and status == operations.FAILED_BEFORE_EFFECT and not raced:
            raced.append(True)
            with factory() as db:
                db.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token': 'third-synthetic'})
                db.commit()
            provider['expected_token'] = 'third-synthetic'
        return mark(record_id, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', newer_grant)
    result = asyncio.run(renewal.renew_source(**call))
    assert raced and result['status'] == 'renewed', result
    assert count(provider, 'PATCH') == 1


@pytest.mark.parametrize('corrupt', ['status', 'payload', 'scope', 'receipt'])
def test_superseded_ledger_remains_part_of_fresh_proof(due_world, corrupt):
    factory, args, provider, original, call = due_world
    provider['mode'] = 'refused'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_applied'
    old_id = document(factory)['pending_lease']['operation_id']
    change_input(factory, provider, 'credential'); provider['mode'] = 'normal'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'renewed'
    with factory() as db:
        row = db.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id == old_id).one()
        if corrupt == 'status': row.status = operations.DISPATCHING
        elif corrupt == 'payload': row.payload_sha256 = 'corrupt'
        elif corrupt == 'scope': row.tenant_id = 'foreign'
        else: row.result_json = {'subscription_id': 'unproved'}
        db.commit()
    with pytest.raises(registry.SourceRegistrationError):
        registry.read_delivery_registration(call['connection_id'], call['registration_id'], db_factory=factory)
    assert count(provider, 'PATCH') == 2


def test_contradictory_receipt_never_becomes_no_effect_or_new_attempt(due_world):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call, operations.FAILED_BEFORE_EFFECT)
    with factory() as db:
        db.get(TaskOperationRecord, row['record_id']).result_json = {'subscription_id': 'unproved'}; db.commit()
    change_input(factory, provider, 'credential')
    result = asyncio.run(renewal.renew_source(**call))
    assert result['effect'] == 'unknown', result
    assert document(factory) == pending and count(provider, 'PATCH') == 0


def test_new_process_resumes_confirmed_refusal_after_new_grant(due_world):
    import os
    import json
    import subprocess
    import sys
    factory, args, provider, original, call = due_world
    provider['mode'] = 'refused'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_applied'
    refused = document(factory)['pending_lease']; old = operation(factory, refused['operation_id'])
    change_input(factory, provider, 'credential')
    with factory() as db: database_url = str(db.get_bind().url)
    script = r'''
import asyncio,json,sys
from datetime import datetime as DateTime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core import connection_service
from core import workflow_event_source_renewal as renewal
from core import workflow_event_source_adapters as adapters
from integrations.microsoft365_service import Microsoft365Service
p=json.load(sys.stdin);at=DateTime.fromisoformat(p['now'])
class Meta(type):
    def __instancecheck__(cls,value):return isinstance(value,DateTime)
class Clock(DateTime,metaclass=Meta):
    @classmethod
    def now(cls,tz=None):return at.astimezone(tz) if tz else at.replace(tzinfo=None)
renewal.datetime=adapters.datetime=Clock
engine=create_engine(p['database_url']);factory=lambda:Session(engine)
connection_service.get_db_session=factory
service=Microsoft365Service(config={});calls=[];record=p['record']
async def wire(method,url,token,data=None):
    assert token=='new-synthetic';calls.append(method)
    assert method in ('GET','PATCH')
    if method=='PATCH':record['expirationDateTime']=data['expirationDateTime']
    return {'status':'success','data':record}
service._make_graph_request=wire
result=asyncio.run(renewal.renew_source('connection',p['registration_id'],
    adapters.OutlookMailSourceAdapter(service=service),factory,at))
print('RESUMPTION_RESULT='+json.dumps({'status':result['status'],'calls':calls,'record':record}))
engine.dispose()
'''
    child = subprocess.run([sys.executable, '-c', script], input=json.dumps({
        'database_url': database_url, 'registration_id': call['registration_id'],
        'now': call['now'].isoformat(), 'record': provider['record']}), text=True,
        capture_output=True, timeout=60, env={**os.environ, 'TESTING':'1', 'DATABASE_URL':database_url})
    assert child.returncode == 0, child.stderr[-2000:]
    summary = json.loads(next(l.split('=',1)[1] for l in child.stdout.splitlines() if l.startswith('RESUMPTION_RESULT=')))
    assert summary['status'] == 'renewed', summary
    assert summary['calls'].count('PATCH') == 1 and summary['calls'].count('GET') == 2
    provider['record'] = summary['record']
    assert operation(factory, refused['operation_id']) == old
    registry.read_delivery_registration(call['connection_id'], call['registration_id'], db_factory=factory)


def test_default_scope_alias_cannot_change_raw_authority_during_replacement(enrollment_world, monkeypatch):
    from core.workflow_event_source_enrollment import enroll_source
    from tests.test_workflow_event_source_lifecycle import advance
    factory, params, args, provider = enrollment_world
    with factory() as db:
        actor = db.get(User, 'owner'); actor.tenant_id = actor.workspace_id = 'default'
        connection = db.get(UserConnection, 'connection'); connection.tenant_id = connection.workspace_id = 'default'
        db.commit()
    first = asyncio.run(enroll_source(**args)); original = document(factory)
    at = advance(monkeypatch, original, minutes=60 * 60)
    call = dict(connection_id='connection', registration_id=first['operation_id'],
                adapter=args['adapter'], db_factory=factory, now=at)
    pending, intent, row = pending_claim(factory, args, original, call)
    old = operation(factory, intent['operation_id'])
    change_input(factory, provider, 'credential')
    mark = operations.mark_status; raced = []
    def alias(record_id, status, **kwargs):
        if record_id == old['id'] and status == operations.FAILED_BEFORE_EFFECT and not raced:
            raced.append(True)
            with factory() as db:
                actor = db.get(User, 'owner'); actor.tenant_id = actor.workspace_id = None
                connection = db.get(UserConnection, 'connection'); connection.tenant_id = connection.workspace_id = None
                db.commit()
        return mark(record_id, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', alias)
    result = asyncio.run(renewal.renew_source(**call))
    assert raced and result['effect'] == 'unknown', result
    assert operation(factory, intent['operation_id']) == old
    assert document(factory) == pending
    assert count(provider, 'PATCH') == 0


def test_competing_relevant_input_resumptions_prepare_one_successor(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    provider['mode'] = 'refused'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_applied'
    old_id = document(factory)['pending_lease']['operation_id']
    change_input(factory, provider, 'credential'); provider['mode'] = 'normal'
    real = renewal.source_credentials
    async def check():
        ready = asyncio.Event(); entered = []
        async def align(doc, adapter, db_factory):
            if doc.get('pending_lease', {}).get('operation_id') == old_id:
                entered.append(1)
                if len(entered) == 2: ready.set()
                await asyncio.wait_for(ready.wait(), timeout=2)
            return await real(doc, adapter, db_factory)
        monkeypatch.setattr(renewal, 'source_credentials', align)
        outcomes = await asyncio.gather(renewal.renew_source(**call), renewal.renew_source(**call))
        assert len(entered) == 2
        assert any(o['status'] in ('renewed', 'already_applied') for o in outcomes), outcomes
    asyncio.run(check())
    assert count(provider, 'PATCH') == 2
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 3
        assert db.query(TaskOperationRecord).filter(TaskOperationRecord.status == operations.SUCCEEDED).count() == 2


def test_pending_claim_waits_for_usable_credential_before_replacement(due_world):
    factory, args, provider, original, call = due_world
    pending, intent, row = pending_claim(factory, args, original, call)
    old = operation(factory, intent['operation_id'])
    with factory() as db:
        db.get(UserConnection, 'connection').credentials = None; db.commit()
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'credentials_unavailable'
    assert operation(factory, intent['operation_id']) == old and document(factory) == pending
    assert count(provider, 'PATCH') == 0
    change_input(factory, provider, 'credential')
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'renewed'
    assert count(provider, 'PATCH') == 1
