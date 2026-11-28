"""Real registry/receipt/audit/authority with controlled native Graph wire."""
import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone
import pytest
from core import workflow_event_source_registration as registry
from core import workflow_event_source_renewal as renewal
from core import outbound_operation_claim as operations
from core.models import TenantSetting, AuditLog, TaskOperationRecord, User
from core.workflow_event_source_enrollment import enroll_source
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


def document(factory):
    with factory() as db:
        return json.loads(db.query(TenantSetting).one().setting_value)


@pytest.fixture
def due_world(enrollment_world, monkeypatch):
    factory, params, args, provider = enrollment_world
    first = asyncio.run(enroll_source(**args))
    assert first['status'] == 'registered'
    original = document(factory)
    at = datetime.fromisoformat(original['prepared_at']) + timedelta(hours=60)
    class ClockMeta(type):
        def __instancecheck__(cls, value):
            return isinstance(value, datetime)
    class Clock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)
    at = Clock.fromisoformat(at.isoformat())
    monkeypatch.setattr('core.workflow_event_source_adapters.datetime', Clock)
    call = dict(connection_id=params['connection_id'], registration_id=first['operation_id'],
                adapter=args['adapter'], db_factory=factory, now=at)
    return factory, args, provider, original, call


def count(provider, method):
    return sum(item[0] == method for item in provider['calls'])


def test_success_atomic_proof_and_enrollment_replay(due_world):
    factory, args, provider, original, call = due_world
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'renewed', result
    after = document(factory)
    for key, value in original.items():
        assert after[key] == value
    assert 'pending_lease' not in after
    assert registry.read_delivery_registration(call['connection_id'], call['registration_id'],
                                                db_factory=factory) == after
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_due'
    assert asyncio.run(enroll_source(**args))['status'] == 'already_applied'
    assert count(provider, 'PATCH') == count(provider, 'POST') == 1
    with factory() as db:
        assert db.query(AuditLog).count() == 4
        assert db.query(TaskOperationRecord).filter(TaskOperationRecord.status == operations.SUCCEEDED).count() == 2


def test_competing_callers_patch_once(due_world):
    _, _, provider, _, call = due_world
    async def scenario():
        return await asyncio.gather(renewal.renew_source(**call), renewal.renew_source(**call))
    results = asyncio.run(scenario())
    assert any(r['status'] in ('renewed', 'already_applied') for r in results), results
    assert count(provider, 'PATCH') == 1


def test_unknown_reconciles_original_intent_only(due_world):
    factory, _, provider, _, call = due_world
    provider['mode'] = 'timeout'
    first = asyncio.run(renewal.renew_source(**call))
    assert first['status'] == 'effect_unknown' and first['do_not_repeat'] is True
    pending = copy.deepcopy(document(factory)['pending_lease'])
    provider['mode'] = 'normal'
    result = asyncio.run(renewal.renew_source(**dict(call, now=call['now'] + timedelta(hours=1))))
    assert result['status'] == 'already_applied', result
    assert document(factory)['current_lease']['intent'] == pending
    assert count(provider, 'PATCH') == 1


@pytest.mark.parametrize('mismatch', ['resource', 'callback', 'moved_expiry', 'state', 'identity'])
def test_wrong_readback_never_certifies_or_repatches(due_world, mismatch):
    _, _, provider, _, call = due_world
    provider['wrong_after_patch'] = mismatch
    first = asyncio.run(renewal.renew_source(**call))
    assert first['status'] == 'effect_unknown'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'effect_unknown'
    provider['wrong_after_patch'] = False
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'already_applied'
    assert count(provider, 'PATCH') == 1


def test_audit_failure_rolls_back_receipt_and_lease_then_get_recovers(due_world, monkeypatch):
    factory, _, provider, _, call = due_world
    original = renewal._audit
    def fail(db, document, event, action):
        if event == 'workflow_event_source_renewed':
            raise RuntimeError('synthetic audit failure')
        return original(db, document, event, action)
    monkeypatch.setattr(renewal, '_audit', fail)
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'effect_unknown'
    with factory() as db:
        assert db.query(TaskOperationRecord).filter(TaskOperationRecord.status == operations.SUCCEEDED).count() == 1
        assert db.query(AuditLog).count() == 3
    assert 'current_lease' not in document(factory)
    monkeypatch.setattr(renewal, '_audit', original)
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'already_applied'
    assert count(provider, 'PATCH') == 1


@pytest.mark.parametrize('race', ['authority', 'target', 'enrollment_receipt'])
def test_dispatch_claim_refuses_peer_change(due_world, monkeypatch, race):
    factory, _, provider, _, call = due_world
    original = operations.mark_status
    def changed(record_id, status, **kwargs):
        if status != operations.DISPATCHING:
            return original(record_id, status, **kwargs)
        with factory() as peer:
            if race == 'authority':
                peer.get(User, 'owner').is_active = False
            elif race == 'enrollment_receipt':
                peer.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id == call['registration_id']).one().status = operations.FAILED_BEFORE_EFFECT
            else:
                row = peer.query(TenantSetting).one()
                value = json.loads(row.setting_value)
                value['provider_subscription_id'] = 'peer'
                row.setting_value = registry._json(value)
            peer.commit()
        return original(record_id, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', changed)
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'refused' and result['effect'] == 'none', result
    assert count(provider, 'PATCH') == 0


@pytest.mark.parametrize('corrupt', ['lease', 'receipt', 'audit', 'scope'])
def test_current_lease_requires_full_exact_proof(due_world, corrupt):
    factory, _, _, _, call = due_world
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'renewed'
    with factory() as db:
        row = db.query(TenantSetting).one()
        value = json.loads(row.setting_value)
        if corrupt == 'lease':
            value['current_lease']['receipt_digest'] = 'corrupt'
            row.setting_value = registry._json(value)
        elif corrupt == 'audit':
            db.query(AuditLog).filter(AuditLog.event_type == 'workflow_event_source_renewed').one().action = 'wrong'
        else:
            op = db.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id ==
                value['current_lease']['intent']['operation_id']).one()
            if corrupt == 'receipt': op.result_json = {'subscription_id': 'peer'}
            else: op.tenant_id = 'foreign'
        db.commit()
    with pytest.raises(registry.SourceRegistrationError):
        registry.read_delivery_registration(call['connection_id'], call['registration_id'], db_factory=factory)


def test_not_due_and_expired_never_patch(due_world):
    _, _, provider, original, call = due_world
    before = datetime.fromisoformat(original['prepared_at'])
    assert asyncio.run(renewal.renew_source(**dict(call, now=before)))['status'] == 'not_due'
    result = asyncio.run(renewal.renew_source(**dict(call, now=before + timedelta(hours=72))))
    assert result['reason'] == 'SOURCE_SUBSCRIPTION_EXPIRED'
    assert count(provider, 'PATCH') == 0


def test_confirmed_refusal_is_durable_no_effect(due_world):
    _, _, provider, _, call = due_world
    provider['mode'] = 'refused'
    first = asyncio.run(renewal.renew_source(**call))
    assert first['status'] == 'not_applied' and first['effect'] == 'none'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'not_applied'
    assert count(provider, 'PATCH') == 1


def test_unavailable_preflight_never_dispatches(due_world):
    _, args, provider, _, call = due_world
    original = args['adapter'].service._make_graph_request.side_effect
    async def wire(method, *rest):
        if method == 'GET': raise TimeoutError('synthetic read unavailable')
        return await original(method, *rest)
    args['adapter'].service._make_graph_request.side_effect = wire
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'readback_unavailable'
    assert count(provider, 'PATCH') == 0


def test_failed_fresh_proof_is_committed_unverified(due_world, monkeypatch):
    _, _, provider, _, call = due_world
    original_read = registry.read_delivery_registration
    original_finish = renewal._finish
    finished = []
    def effect(doc, intent):
        action = original_finish(doc, intent)
        def apply(db):
            action(db)
            finished.append(True)
        return apply
    def read(*a, **kw):
        if finished: raise registry.SourceRegistrationError('SYNTHETIC_UNAVAILABLE')
        return original_read(*a, **kw)
    monkeypatch.setattr(renewal, '_finish', effect)
    monkeypatch.setattr(registry, 'read_delivery_registration', read)
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'committed_unverified' and result['effect'] == 'committed'
    assert count(provider, 'PATCH') == 1


def test_unknown_with_changed_credentials_never_repatches(due_world):
    from core.connection_service import ConnectionService
    from core.models import UserConnection
    factory, _, provider, _, call = due_world
    provider['mode'] = 'timeout'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'effect_unknown'
    with factory() as db:
        db.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token': 'replacement'})
        db.commit()
    provider['expected_token'] = 'replacement'
    result = asyncio.run(renewal.renew_source(**call))
    assert result['status'] == 'effect_unknown' and result['effect'] == 'unknown'
    assert count(provider, 'PATCH') == 1


def test_renewed_callback_still_admits_one_real_workflow(http_world, monkeypatch):
    from tests.test_workflow_event_source_http import setup_source, save_rule
    from core.models import WorkflowExecution, Notification
    from core.workflow_engine import WorkflowEngine
    from core.execution_state_manager import ExecutionStateManager
    from core import workflow_event_worker as worker
    client, factory, provider, principal, adapter = http_world
    first, callback, item = setup_source(client, provider)
    save_rule(client)
    original = document(factory)
    at = datetime.fromisoformat(original['prepared_at']) + timedelta(hours=60)
    class ClockMeta(type):
        def __instancecheck__(cls, value): return isinstance(value, datetime)
    class Clock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None): return at.astimezone(tz) if tz else at.replace(tzinfo=None)
    monkeypatch.setattr('core.workflow_event_source_adapters.datetime', Clock)
    result = asyncio.run(renewal.renew_source('connection', first['operation_id'], adapter, factory, at))
    assert result['status'] == 'renewed', result
    principal['signed_in'] = False
    delivered = client.post(callback, json={'value': [item]})
    assert delivered.status_code == 200 and delivered.json()['admitted'] == 1, delivered.text
    assert client.post(callback, json={'value': [item]}).json()['duplicates'] == 1
    async def drain():
        engine = WorkflowEngine()
        engine.state_manager = ExecutionStateManager()
        assert await worker.process_pending_event_executions_once(engine=engine) == 1
        await asyncio.gather(*list(engine._background_tasks))
    asyncio.run(asyncio.wait_for(drain(), timeout=30))
    with factory() as db:
        execution = db.query(WorkflowExecution).one()
        assert execution.status == 'COMPLETED', execution.error
        notification = db.query(Notification).one()
        assert (notification.user_id, notification.tenant_id, notification.workspace_id) == ('owner', 'tenant', 'workspace')
    assert count(provider, 'PATCH') == count(provider, 'POST') == 1


from tests.test_workflow_event_source_http import http_world


def test_new_os_process_reconciles_unknown_by_get_without_patch(due_world):
    import os
    import subprocess
    import sys
    factory, _, provider, _, call = due_world
    provider['mode'] = 'timeout'
    assert asyncio.run(renewal.renew_source(**call))['status'] == 'effect_unknown'
    with factory() as db:
        database_url = str(db.get_bind().url)
    script = r'''
import asyncio,json,sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core import connection_service
from core.workflow_event_source_adapters import OutlookMailSourceAdapter
from core.workflow_event_source_renewal import renew_source
from integrations.microsoft365_service import Microsoft365Service
payload=json.load(sys.stdin)
engine=create_engine(payload['database_url'])
factory=lambda: Session(engine)
connection_service.get_db_session=factory
service=Microsoft365Service(config={})
calls=[]
async def transport(method,url,token,data=None):
    calls.append(method)
    assert method=='GET', 'Reconciliation must not mutate the provider'
    return {'status':'success','data':payload['record']}
service._make_graph_request=transport
result=asyncio.run(renew_source('connection',payload['registration_id'],
    OutlookMailSourceAdapter(service=service), factory, datetime.fromisoformat(payload['now'])))
print('RENEWAL_RESULT='+json.dumps({'status':result['status'],'calls':calls}))
engine.dispose()
'''
    result = subprocess.run([sys.executable, '-c', script], input=json.dumps({
        'database_url': database_url, 'registration_id': call['registration_id'],
        'record': provider['record'], 'now': call['now'].isoformat()}),
        text=True, capture_output=True, timeout=60, env={**os.environ, 'TESTING': '1',
            'DATABASE_URL': database_url})
    assert result.returncode == 0, result.stderr[-2500:]
    summary = json.loads(next(line.split('=', 1)[1] for line in result.stdout.splitlines()
                              if line.startswith('RENEWAL_RESULT=')))
    assert summary == {'status': 'already_applied', 'calls': ['GET']}
    assert 'current_lease' in document(factory)
    assert count(provider, 'PATCH') == 1


@pytest.mark.parametrize('invalid', [0, 'bad', datetime(2026, 1, 1)])
def test_invalid_server_clock_refuses_before_provider_read(due_world, invalid):
    _, _, provider, _, call = due_world
    before = len(provider['calls'])
    with pytest.raises(registry.SourceRegistrationError, match='SOURCE_LEASE_TIME_INVALID'):
        asyncio.run(renewal.renew_source(**dict(call, now=invalid)))
    assert len(provider['calls']) == before


def test_multiple_lease_generations_preserve_original_identity(due_world, monkeypatch):
    factory, args, provider, original, call = due_world
    base = datetime.fromisoformat(original['prepared_at'])
    operation_ids = set()
    for hours in (60, 120, 180):
        at = base + timedelta(hours=hours)
        class ClockMeta(type):
            def __instancecheck__(cls, value): return isinstance(value, datetime)
        class Clock(datetime, metaclass=ClockMeta):
            @classmethod
            def now(cls, tz=None): return at.astimezone(tz) if tz else at.replace(tzinfo=None)
        monkeypatch.setattr('core.workflow_event_source_adapters.datetime', Clock)
        result = asyncio.run(renewal.renew_source(**dict(call, now=at)))
        assert result['status'] == 'renewed', result
        current = registry.read_delivery_registration(call['connection_id'], call['registration_id'], db_factory=factory)
        operation_ids.add(current['current_lease']['intent']['operation_id'])
        for key, value in original.items(): assert current[key] == value
        assert asyncio.run(enroll_source(**args))['status'] == 'already_applied'
    assert len(operation_ids) == 3
    assert count(provider, 'PATCH') == 3 and count(provider, 'POST') == 1
    with factory() as db:
        assert db.query(AuditLog).count() == 8
        assert db.query(TaskOperationRecord).filter(TaskOperationRecord.status == operations.SUCCEEDED).count() == 4
