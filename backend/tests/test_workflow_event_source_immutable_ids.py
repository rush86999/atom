"""Native source identity must agree between subscription, content and delta."""
import asyncio
import copy
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from core.workflow_event_source_adapters import OutlookMailSourceAdapter
from core.workflow_event_source_enrollment import enroll_source
from tests.test_workflow_event_source_binding import binding_world, saved
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db
from integrations.microsoft365_service import Microsoft365Service


def native_document():
    return {'prepared_at': datetime.now(timezone.utc).isoformat(),
            'callback_url':'https://example.invalid/notifications',
            'provider_binding':{'user_id':'mailbox-one','folder_id':'inbox-one'},
            'source_options':{'message_id_type':'immutable'}}


def test_new_native_enrollment_freezes_and_sends_immutable_mode(binding_world):
    factory, params, args, provider = binding_world
    original = args['adapter'].service._make_graph_request.side_effect
    preferences = []
    async def wire(method, url, token, data=None, **options):
        if method == 'POST': preferences.append(options.get('prefer_immutable_id', False))
        return await original(method, url, token, data, **options)
    args['adapter'].service._make_graph_request.side_effect = wire
    result = asyncio.run(enroll_source(**args))
    assert result['status'] == 'registered', result
    document = saved(factory)
    assert document['source_options'] == {'message_id_type':'immutable'}
    assert args['adapter'].material(document)['message_id_type'] == 'immutable'
    assert preferences == [True]
    assert 'source_options' not in result


def test_content_read_uses_bound_mailbox_and_immutable_header():
    service = Microsoft365Service(config={})
    service._make_graph_request = AsyncMock(return_value={'status':'success','data':{'id':'message-one','subject':'First'}})
    adapter = OutlookMailSourceAdapter(service=service)
    document = native_document()
    event = asyncio.run(adapter.message_event({'resourceData':{'id':'message-one'}},
        {'access_token':'synthetic'}, document=document))
    args, options = service._make_graph_request.await_args
    assert args[0] == 'GET'
    assert args[1].startswith('https://graph.microsoft.com/v1.0/users/mailbox-one/messages/message-one?')
    assert options == {'prefer_immutable_id':True}
    assert event['provider_event_id'] == adapter.event_identity('message-one', document=document)


def test_delta_reads_always_request_immutable_ids():
    service = Microsoft365Service(config={})
    calls = []
    async def wire(method, url, token, **options):
        calls.append((url, options))
        if url.endswith('/me?$select=id'): data={'id':'mailbox-one'}
        elif url.endswith('/me/mailFolders/Inbox?$select=id'): data={'id':'inbox-one'}
        else: data={'value':[], '@odata.deltaLink':url.split('?')[0]+'?$deltatoken=opaque'}
        return {'status':'success', 'data':data}
    service._make_graph_request = wire
    result = asyncio.run(OutlookMailSourceAdapter(service=service).read_delta_page(
        native_document()['provider_binding'], {'access_token':'synthetic'}))
    assert result['complete'] is True
    assert calls[-1][1] == {'prefer_immutable_id':True}
    assert all(options == {} for _, options in calls[:-1])


@pytest.mark.parametrize('change', ['subject', 'folder', 'generation', 'mailbox'])
def test_created_event_identity_excludes_mutable_content_and_generation(change):
    adapter = OutlookMailSourceAdapter(service=object())
    document = native_document()
    original = adapter.event_identity('message-one', document=document)
    changed = copy.deepcopy(document)
    if change == 'mailbox': changed['provider_binding']['user_id']='another-mailbox'
    elif change == 'folder': changed['provider_binding']['folder_id']='replacement-inbox'
    elif change == 'generation': changed['operation_id']='new-source-generation'
    else: changed['subject']='Updated'
    current = adapter.event_identity('message-one', document=changed)
    assert (current != original) is (change == 'mailbox')


def test_legacy_document_keeps_original_plan_and_identity():
    service = Microsoft365Service(config={})
    service._make_graph_request = AsyncMock(return_value={'status':'success','data':{'id':'subscription'}})
    adapter = OutlookMailSourceAdapter(service=service)
    document=native_document();document.pop('source_options')
    assert 'message_id_type' not in adapter.material(document)
    asyncio.run(adapter.create(document, {'access_token':'synthetic'}, 'receiver-state'))
    assert service._make_graph_request.await_args.kwargs == {}
