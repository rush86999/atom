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
