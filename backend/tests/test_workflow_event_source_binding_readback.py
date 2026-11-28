"""Committed enrollment cannot certify a different reconnect at readback."""
import asyncio
import pytest
from core.connection_service import ConnectionService
from core.models import UserConnection, TaskOperationRecord
from core.workflow_event_source_enrollment import enroll_source
from core import workflow_event_source_registration as registry
from tests.test_workflow_event_source_binding import binding_world, saved
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


@pytest.mark.parametrize('stage', ['after_post', 'after_read', 'after_activation'])
def test_reconnect_during_confirmation_is_committed_unverified(binding_world, monkeypatch, stage):
    factory, params, args, provider = binding_world
    def reconnect():
        with factory() as peer:
            peer.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'new-mailbox-grant'})
            peer.commit()
        provider['mailbox'] = 'new-mailbox'
    original = args['adapter'].service._make_graph_request.side_effect
    async def wire(method, url, token, data=None, **request_options):
        result = await original(method, url, token, data, **request_options)
        if ((stage == 'after_post' and method == 'POST') or
                (stage == 'after_read' and method == 'GET' and '/subscriptions/' in url)):
            reconnect()
        return result
    args['adapter'].service._make_graph_request.side_effect = wire
    if stage == 'after_activation':
        activate = registry.activate_source_registration
        def moved(*a, **kw):
            result = activate(*a, **kw)
            reconnect()
            return result
        monkeypatch.setattr(registry, 'activate_source_registration', moved)
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'committed_unverified' and result['effect'] == 'committed'
    assert result['do_not_repeat'] is True
    assert sum(c[0] == 'POST' for c in provider['calls']) == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).one().status == 'succeeded'
        assert ConnectionService()._decrypt(db.get(UserConnection, 'connection').credentials)['access_token'] == 'new-mailbox-grant'
    assert saved(factory)['provider_binding']['user_id'] == 'mailbox-one'


def test_fresh_grant_for_same_mailbox_can_verify_committed_creation(binding_world):
    factory, params, args, provider = binding_world
    original = args['adapter'].service._make_graph_request.side_effect
    async def wire(method, url, token, data=None, **request_options):
        result = await original(method, url, token, data, **request_options)
        if method == 'POST':
            with factory() as peer:
                peer.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'same-mailbox-new-grant'})
                peer.commit()
            provider['expected_token'] = 'same-mailbox-new-grant'
        return result
    args['adapter'].service._make_graph_request.side_effect = wire
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'registered', result
    assert sum(c[0] == 'POST' for c in provider['calls']) == 1
    assert saved(factory)['provider_binding']['user_id'] == 'mailbox-one'


def test_restored_mailbox_reconciles_original_committed_receipt(binding_world):
    factory, params, args, provider = binding_world
    original = args['adapter'].service._make_graph_request.side_effect
    async def moved(method, url, token, data=None, **request_options):
        result = await original(method, url, token, data, **request_options)
        if method == 'POST':
            with factory() as peer:
                peer.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'different-mailbox-grant'})
                peer.commit()
            provider['mailbox'] = 'different-mailbox'
        return result
    args['adapter'].service._make_graph_request.side_effect = moved
    first = asyncio.run(enroll_source(**args))
    assert first['status'] == 'committed_unverified'
    with factory() as db:
        operation = db.query(TaskOperationRecord).one()
        proof = (operation.id, operation.payload_sha256, operation.result_json)
        db.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token':'synthetic'})
        db.commit()
    provider['mailbox'] = 'mailbox-one'
    args['adapter'].service._make_graph_request.side_effect = original
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'already_applied' and result['operation_id'] == first['operation_id']
    assert sum(c[0] == 'POST' for c in provider['calls']) == 1
    with factory() as db:
        operation = db.query(TaskOperationRecord).one()
        assert (operation.id, operation.payload_sha256, operation.result_json) == proof
