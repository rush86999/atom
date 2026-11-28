"""Native mailbox binding at the real enrollment/receipt boundary."""
import asyncio
import copy
import json
import pytest
from core import workflow_event_source_registration as registry
from core.workflow_event_source_enrollment import enroll_source
from core.connection_service import ConnectionService
from core.models import TenantSetting, AuditLog, TaskOperationRecord, UserConnection
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


@pytest.fixture
def binding_world(enrollment_world):
    factory, params, args, provider = enrollment_world
    original = args['adapter'].service._make_graph_request.side_effect
    provider.update(mailbox='mailbox-one', folder='inbox-one', after_binding=None)
    async def wire(method, url, token, data=None):
        if url.endswith('/me?$select=id') or url.endswith('/me/mailFolders/Inbox?$select=id'):
            provider['calls'].append((method, url, None))
            value = provider['mailbox'] if url.endswith('/me?$select=id') else provider['folder']
            if url.endswith('/me/mailFolders/Inbox?$select=id') and provider['after_binding']:
                provider['after_binding']()
            return {'status':'success', 'data':{'id':value}}
        return await original(method, url, token, data)
    args['adapter'].service._make_graph_request.side_effect = wire
    return factory, params, args, provider


def saved(factory):
    with factory() as db:
        return json.loads(db.query(TenantSetting).one().setting_value)


def test_native_enrollment_pins_mailbox_and_folder_before_create(binding_world):
    factory, params, args, provider = binding_world
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'registered'
    document = saved(factory)
    assert document['provider_binding'] == {'user_id':'mailbox-one', 'folder_id':'inbox-one'}
    created = next(c[2] for c in provider['calls'] if c[0] == 'POST')
    assert created['resource'] == '/users/mailbox-one/mailFolders/inbox-one/messages'
    assert provider['calls'][0][1].endswith('/me?$select=id')
    assert 'provider_binding' not in result
    with factory() as db:
        assert db.query(AuditLog).count() == 2
        assert db.query(TaskOperationRecord).count() == 1


def test_reconnect_during_binding_cannot_create_for_old_snapshot(binding_world):
    factory, params, args, provider = binding_world
    def reconnect():
        with factory() as peer:
            peer.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'peer-grant'})
            peer.commit()
    provider['after_binding'] = reconnect
    with pytest.raises(registry.SourceRegistrationError):
        asyncio.run(enroll_source(**args))
    assert not any(c[0] == 'POST' for c in provider['calls'])
    with factory() as db:
        assert db.query(AuditLog).count() == db.query(TenantSetting).count() == db.query(TaskOperationRecord).count() == 0
        assert ConnectionService()._decrypt(db.get(UserConnection,'connection').credentials)['access_token'] == 'peer-grant'


def test_different_mailbox_replay_does_not_adopt_original_subscription(binding_world):
    factory, params, args, provider = binding_world
    first = asyncio.run(enroll_source(**args))
    original = saved(factory)
    provider['mailbox'] = 'different-mailbox'
    again = asyncio.run(enroll_source(**args))
    assert again['status'] == 'committed_unverified'
    assert again['effect'] == 'committed' and again['do_not_repeat'] is True
    assert again['operation_id'] == first['operation_id']
    assert saved(factory) == original
    assert sum(c[0]=='POST' for c in provider['calls']) == 1


@pytest.mark.parametrize('malformed', [None, '', '../foreign', 123])
def test_bad_provider_binding_refuses_without_durable_intent(binding_world, malformed):
    factory, params, args, provider = binding_world
    provider['mailbox'] = malformed
    with pytest.raises(registry.SourceRegistrationError):
        asyncio.run(enroll_source(**args))
    assert not any(c[0]=='POST' for c in provider['calls'])
    with factory() as db:
        assert db.query(AuditLog).count() == db.query(TenantSetting).count() == db.query(TaskOperationRecord).count() == 0


def test_legacy_prepared_material_is_not_silently_upgraded(binding_world):
    factory, params, args, provider = binding_world
    original = registry.prepare_source_registration(**params)
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'registered'
    assert result['operation_id'] == original['operation_id']
    document = saved(factory)
    assert 'provider_binding' not in document
    assert next(c[2] for c in provider['calls'] if c[0]=='POST')['resource'] == "/me/mailFolders('Inbox')/messages"
    assert not any('/me?$select=id' in c[1] for c in provider['calls'])


def test_authority_change_during_native_binding_preserves_peer(binding_world):
    from core.models import User
    factory, params, args, provider = binding_world
    def disable():
        with factory() as peer:
            peer.get(User, 'owner').is_active = False
            peer.commit()
    provider['after_binding'] = disable
    with pytest.raises(registry.SourceRegistrationError):
        asyncio.run(enroll_source(**args))
    assert not any(c[0] == 'POST' for c in provider['calls'])
    with factory() as db:
        assert db.get(User, 'owner').is_active is False
        assert db.query(TenantSetting).count() == db.query(AuditLog).count() == 0


def test_reconnect_after_preparation_cannot_dispatch_unchecked_new_grant(binding_world):
    factory, params, args, provider = binding_world
    calls = 0
    def reconnect():
        nonlocal calls
        calls += 1
        if calls == 2:
            with factory() as peer:
                peer.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'unchecked-peer'})
                peer.commit()
    provider['after_binding'] = reconnect
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'refused' and result['effect'] == 'none'
    assert not any(c[0] == 'POST' for c in provider['calls'])
    with factory() as db:
        assert db.query(TaskOperationRecord).one().status == 'claimed'
        assert db.query(AuditLog).count() == 1
        assert ConnectionService()._decrypt(db.get(UserConnection, 'connection').credentials)['access_token'] == 'unchecked-peer'


def test_bound_resource_rejects_forged_binding_shape(binding_world):
    factory, params, args, provider = binding_world
    asyncio.run(enroll_source(**args))
    document = saved(factory)
    for invalid in ({'user_id':'u'}, {'user_id':'u','folder_id':'f','scope':'other'},
                    {'user_id':'../peer','folder_id':'f'}, {'user_id':True,'folder_id':'f'}):
        with pytest.raises(ValueError):
            args['adapter'].material(dict(document, provider_binding=invalid))


def test_missing_credentials_does_not_create_unbound_native_intent(binding_world):
    factory, params, args, provider = binding_world
    with factory() as db:
        db.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({})
        db.commit()
    with pytest.raises(registry.SourceRegistrationError):
        asyncio.run(enroll_source(**args))
    assert provider['calls'] == []
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == db.query(AuditLog).count() == db.query(TenantSetting).count() == 0


def test_legacy_unknown_intent_is_never_replanned_for_new_mailbox(binding_world):
    factory, params, args, provider = binding_world
    registry.prepare_source_registration(**params)
    provider['mode'] = 'timeout'
    first = asyncio.run(enroll_source(**args))
    original = saved(factory)
    with factory() as db:
        operation = db.query(TaskOperationRecord).one()
        operation_material = (operation.id, operation.payload_sha256, operation.status, copy.deepcopy(operation.result_json))
    provider['mailbox'] = 'new-mailbox'
    again = asyncio.run(enroll_source(**args))
    assert first['status'] == again['status'] == 'effect_unknown'
    assert saved(factory) == original and 'provider_binding' not in original
    assert sum(c[0] == 'POST' for c in provider['calls']) == 1
    with factory() as db:
        operation = db.query(TaskOperationRecord).one()
        assert (operation.id, operation.payload_sha256, operation.status, operation.result_json) == operation_material
