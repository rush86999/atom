"""Real source/operation/audit DB chain, native adapter, doubled HTTP transport."""
import asyncio
import copy
from unittest.mock import AsyncMock
import pytest
from core.connection_service import ConnectionService
from core.models import UserConnection, TaskOperationRecord, TenantSetting, AuditLog
from core.workflow_event_source_adapters import OutlookMailSourceAdapter
from core.workflow_event_source_enrollment import enroll_source
from core import workflow_event_source_registration as registrations
from core import outbound_operation_claim as operations
from integrations.microsoft365_service import Microsoft365Service
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


@pytest.fixture
def enrollment_world(source_world, monkeypatch):
    factory, params = source_world
    params['source'] = 'outlook'
    params['event_types'] = ['message.created']
    with factory() as db:
        row = db.get(UserConnection, 'connection')
        row.integration_id = 'outlook'
        row.credentials = ConnectionService()._encrypt({'access_token': 'synthetic'})
        db.commit()
    monkeypatch.setattr('core.connection_service.get_db_session', factory)
    service = Microsoft365Service(config={})
    provider = {'calls': [], 'record': None, 'mode': 'normal', 'wrong_read': False}
    async def transport(method, url, token, data=None, *, prefer_immutable_id=False):
        assert token == provider.get('expected_token', 'synthetic')
        provider['calls'].append((method, url, copy.deepcopy(data)))
        provider.setdefault('identity_preferences', []).append((method, url, prefer_immutable_id))
        await asyncio.sleep(0.01)
        if method == 'GET' and url.endswith('/me?$select=id'):
            return {'status': 'success', 'data': {'id': provider.get('mailbox', 'mailbox-one')}}
        if method == 'GET' and url.endswith('/me/mailFolders/Inbox?$select=id'):
            return {'status': 'success', 'data': {'id': provider.get('folder', 'inbox-one')}}
        if method == 'POST':
            if provider['mode'] == 'refused':
                return {'status': 'error', 'code': 403, 'message': 'synthetic refusal'}
            provider['record'] = dict(data, id='provider-subscription', clientState=None)
            if provider['mode'] == 'timeout':
                raise TimeoutError('synthetic lost confirmation')
            return {'status': 'success', 'data': copy.deepcopy(provider['record'])}
        if method == 'PATCH':
            if provider['mode'] == 'refused':
                return {'status': 'error', 'code': 403}
            provider['record']['expirationDateTime'] = data['expirationDateTime']
            provider['patched'] = True
            if provider['mode'] == 'timeout':
                raise TimeoutError('synthetic lost renewal confirmation')
            return {'status': 'success', 'data': copy.deepcopy(provider['record'])}
        record = copy.deepcopy(provider['record'])
        mismatch = provider.get('wrong_after_patch') if provider.get('patched') else provider['wrong_read']
        if mismatch == 'state': record['clientState'] = 'different-state'
        elif mismatch == 'callback': record['notificationUrl'] = 'https://example.invalid/other'
        elif mismatch == 'expiry': record['expirationDateTime'] = '2000-01-01T00:00:00Z'
        elif mismatch == 'moved_expiry': record['expirationDateTime'] = '2099-01-01T00:00:00Z'
        elif mismatch == 'identity': record['id'] = 'different-subscription'
        elif mismatch: record['resource'] = 'different-resource'
        return {'status': 'success', 'data': record}
    service._make_graph_request = AsyncMock(side_effect=transport)
    adapter = OutlookMailSourceAdapter(service=service)
    args = dict(actor_id=params['actor_id'], connection_id=params['connection_id'],
                callback_base_url=params['callback_base_url'], adapter=adapter, db_factory=factory)
    return factory, params, args, provider


def test_enroll_readback_activate_and_replay_never_create_twice(enrollment_world):
    factory, params, args, provider = enrollment_world
    async def scenario():
        first = await enroll_source(**args)
        assert first['status'] == 'registered', first
        assert first['phase'] == 'registered' and first['enabled'] is True
        retry = await enroll_source(**args)
        assert retry['status'] == 'already_applied', retry
        assert retry['operation_id'] == first['operation_id']
        assert retry['subscription_id'] == first['subscription_id']
    asyncio.run(scenario())
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1
    with factory() as db:
        assert db.query(TenantSetting).count() == 1
        assert db.query(AuditLog).count() == 2
        operation = db.query(TaskOperationRecord).one()
        assert operation.status == operations.SUCCEEDED
        receipt = operation.result_json
        assert receipt['subscription_id'] == 'provider-subscription'
        assert 'clientState' not in str(receipt) and 'access_token' not in str(receipt)


def test_lost_confirmation_is_durable_unknown_and_never_reenrolls(enrollment_world):
    factory, params, args, provider = enrollment_world
    provider['mode'] = 'timeout'
    async def scenario():
        first = await enroll_source(**args)
        assert first['status'] == 'effect_unknown' and first['do_not_repeat'] is True
        retry = await enroll_source(**args)
        assert retry['status'] == 'effect_unknown'
        assert retry['operation_id'] == first['operation_id']
    asyncio.run(scenario())
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).one().status == operations.UNCERTAIN_EFFECT
        assert db.query(AuditLog).count() == 1


def test_confirmed_refusal_reports_no_effect_without_another_provider_attempt(enrollment_world):
    factory, params, args, provider = enrollment_world
    provider['mode'] = 'refused'
    async def scenario():
        first = await enroll_source(**args)
        assert first['status'] == 'not_applied' and first['effect'] == 'none'
        assert (await enroll_source(**args))['status'] == 'not_applied'
    asyncio.run(scenario())
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).one().status == operations.FAILED_BEFORE_EFFECT


@pytest.mark.parametrize('mismatch', ['resource', 'state', 'callback', 'expiry', 'moved_expiry', 'identity'])
def test_readback_mismatch_recovers_from_original_receipt_without_enrolling(enrollment_world, mismatch):
    factory, params, args, provider = enrollment_world
    provider['wrong_read'] = mismatch
    async def scenario():
        first = await enroll_source(**args)
        assert first['status'] == 'committed_unverified' and first['effect'] == 'committed'
        assert first['enabled'] is False
        provider['wrong_read'] = False
        recovered = await enroll_source(**args)
        assert recovered['status'] == 'already_applied' and recovered['enabled'] is True
    asyncio.run(scenario())
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1


def test_activation_failure_recovers_without_another_provider_effect(enrollment_world, monkeypatch):
    factory, params, args, provider = enrollment_world
    original = registrations.activate_source_registration
    def unavailable(*a, **kw):
        raise registrations.SourceRegistrationError('SOURCE_ACTIVATION_UNAVAILABLE')
    monkeypatch.setattr(registrations, 'activate_source_registration', unavailable)
    first = asyncio.run(enroll_source(**args))
    assert first['status'] == 'committed_unverified' and first['effect'] == 'committed'
    monkeypatch.setattr(registrations, 'activate_source_registration', original)
    assert asyncio.run(enroll_source(**args))['status'] == 'already_applied'
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1


def test_competing_enrollments_have_one_provider_create(enrollment_world):
    factory, params, args, provider = enrollment_world
    async def scenario():
        outcomes = await asyncio.gather(enroll_source(**args), enroll_source(**args))
        assert any(outcome['status'] == 'registered' for outcome in outcomes), outcomes
        assert all(outcome['status'] in ('registered', 'already_applied', 'effect_unknown') for outcome in outcomes)
    asyncio.run(scenario())
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 1
        assert db.query(AuditLog).count() == 2


def test_authority_change_before_dispatch_refuses_with_no_provider_effect(enrollment_world, monkeypatch):
    from core.models import User
    factory, params, args, provider = enrollment_world
    original, calls = registrations._claim, 0
    def changed(db, actor, connection):
        nonlocal calls
        calls += 1
        if calls == 2:
            with factory() as peer:
                peer.get(User, 'owner').is_active = False
                peer.commit()
        return original(db, actor, connection)
    monkeypatch.setattr(registrations, '_claim', changed)
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'refused' and result['effect'] == 'none'
    # Native mailbox binding is now read before intent preparation and again
    # against the dispatch grant. Refusal permits only those exact GETs.
    base = 'https://graph.microsoft.com/v1.0'
    assert provider['calls'] == [
        ('GET', base + '/me?$select=id', None),
        ('GET', base + '/me/mailFolders/Inbox?$select=id', None),
    ] * 2
    with factory() as db:
        assert db.get(User, 'owner').is_active is False
        assert db.query(TaskOperationRecord).one().status == operations.CLAIMED


def test_lost_receipt_persistence_never_creates_second_subscription(enrollment_world, monkeypatch):
    factory, params, args, provider = enrollment_world
    original = operations.mark_status
    def lost(record_id, status, **kwargs):
        if status == operations.SUCCEEDED:
            return False
        return original(record_id, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', lost)
    assert asyncio.run(enroll_source(**args))['status'] == 'effect_unknown'
    monkeypatch.setattr(operations, 'mark_status', original)
    assert asyncio.run(enroll_source(**args))['status'] == 'effect_unknown'
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).one().status == operations.DISPATCHING


def test_changed_adapter_material_conflicts_without_reissuing_original_effect(enrollment_world, monkeypatch):
    factory, params, args, provider = enrollment_world
    assert asyncio.run(enroll_source(**args))['status'] == 'registered'
    original = args['adapter'].material
    monkeypatch.setattr(args['adapter'], 'material', lambda document: dict(original(document), resource='/other'))
    changed = asyncio.run(enroll_source(**args))
    assert changed['status'] == 'operation_conflict' and changed['effect'] == 'unknown'
    assert changed['do_not_repeat'] is True
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1


def test_changed_receipt_shape_is_not_acknowledged_as_verified_replay(enrollment_world):
    factory, params, args, provider = enrollment_world
    assert asyncio.run(enroll_source(**args))['status'] == 'registered'
    with factory() as db:
        row = db.query(TaskOperationRecord).one()
        row.result_json = dict(row.result_json, additional_material='changed')
        db.commit()
    replay = asyncio.run(enroll_source(**args))
    assert replay['status'] == 'committed_unverified' and replay['effect'] == 'committed'
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1


@pytest.mark.parametrize('original', ['unknown', 'committed'])
def test_missing_credentials_cannot_relabel_original_enrollment_effect(enrollment_world, original):
    from datetime import datetime, timedelta, timezone
    factory, params, args, provider = enrollment_world
    if original == 'unknown': provider['mode'] = 'timeout'
    first = asyncio.run(enroll_source(**args))
    with factory() as db:
        db.get(UserConnection, 'connection').expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    calls = len(provider['calls'])
    again = asyncio.run(enroll_source(**args))
    assert again['operation_id'] == first['operation_id']
    assert again['effect'] == ('unknown' if original == 'unknown' else 'committed')
    assert again['status'] == ('effect_unknown' if original == 'unknown' else 'committed_unverified')
    assert again['do_not_repeat'] is True and len(provider['calls']) == calls
