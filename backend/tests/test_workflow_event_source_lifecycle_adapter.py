"""Lifecycle transport is opt-in; legacy payloads and renewal leases stay unchanged."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
import pytest
from core.workflow_event_source_adapters import OutlookMailSourceAdapter
from integrations.microsoft365_service import Microsoft365Service

CALLBACK = 'https://example.invalid/workflow-events'
LIFECYCLE = ['reauthorizationRequired', 'missed', 'subscriptionRemoved']

def _document(*, lifecycle=False, prepared_at=None):
    document = {'prepared_at': (prepared_at or datetime.now(timezone.utc)).isoformat(),
                'callback_url': CALLBACK}
    if lifecycle:
        document['lifecycle_events'] = LIFECYCLE
    return document

def _service():
    service = Microsoft365Service(config={})
    service._make_graph_request = AsyncMock(return_value={'status': 'success', 'data': {'id': 'sub-1'}})
    return service

def test_legacy_material_and_create_payload_keep_exact_old_shape():
    service = _service()
    adapter = OutlookMailSourceAdapter(service=service)
    document = _document()
    material = adapter.material(document)
    assert set(material) == {'resource', 'change_type', 'callback_url', 'expires_at'}
    assert 'lifecycle_callback_url' not in adapter.material(dict(document, lifecycle_events=[]))
    asyncio.run(adapter.create(document, {'access_token': 'synthetic'}, 'receiver-state'))
    payload = service._make_graph_request.await_args.args[3]
    assert payload['notificationUrl'] == CALLBACK
    assert 'lifecycleNotificationUrl' not in payload

def test_lifecycle_material_and_create_payload_use_same_endpoint():
    service = _service()
    adapter = OutlookMailSourceAdapter(service=service)
    document = _document(lifecycle=True)
    material = adapter.material(document)
    assert material['lifecycle_callback_url'] == material['callback_url'] == CALLBACK
    asyncio.run(adapter.create(document, {'access_token': 'synthetic'}, 'receiver-state'))
    payload = service._make_graph_request.await_args.args[3]
    assert payload['lifecycleNotificationUrl'] == CALLBACK

@pytest.mark.parametrize('url', [
    'http://example.invalid/lifecycle',
    '/relative/lifecycle',
    'https://user:password@example.invalid/lifecycle',
    'https://example.invalid/lifecycle#fragment',
    'https://example.invalid/lifecycle#',
    '', True, [], 'https://example.invalid:bad/lifecycle',
    'https://example.invalid/life\ncycle',
])
def test_malformed_lifecycle_url_refuses_before_dispatch(url):
    service = _service()
    service._make_graph_request = AsyncMock()
    result = asyncio.run(service.create_subscription(
        'synthetic', '/me/messages', 'created', CALLBACK,
        '2026-11-25T00:00:00Z', client_state='state', lifecycle_notification_url=url))
    assert result['status'] == 'error'
    service._make_graph_request.assert_not_awaited()

def test_verify_requires_exact_lifecycle_url_readback():
    adapter = OutlookMailSourceAdapter(service=_service())
    document = _document(lifecycle=True)
    plan = adapter.material(document)
    receipt = {'subscription_id': 'sub-1'}
    observed = {'id': 'sub-1', 'resource': plan['resource'],
                'changeType': plan['change_type'], 'notificationUrl': CALLBACK,
                'expirationDateTime': plan['expires_at'],
                'lifecycleNotificationUrl': CALLBACK}
    assert adapter.verify(document, receipt, observed) is True
    missing = {key: value for key, value in observed.items()
               if key != 'lifecycleNotificationUrl'}
    assert adapter.verify(document, receipt, missing) is False
    wrong = dict(observed, lifecycleNotificationUrl='https://wrong.invalid/lifecycle')
    assert adapter.verify(document, receipt, wrong) is False

def test_renewal_material_preserves_lifecycle_and_patch_stays_expiry_only():
    service = _service()
    adapter = OutlookMailSourceAdapter(service=service)
    prepared = datetime.now(timezone.utc) - timedelta(hours=1)
    document = _document(lifecycle=True, prepared_at=prepared)
    document['provider_subscription_id'] = 'sub-1'
    original = adapter.material(document)
    renewal = adapter.renewal_material(document, now=datetime.now(timezone.utc))
    assert set(renewal) == set(original)
    assert renewal['lifecycle_callback_url'] == CALLBACK
    assert renewal['expires_at'] != original['expires_at']
    assert adapter._renewal_plan(document, renewal) == renewal
    asyncio.run(adapter.renew(document, {'access_token': 'synthetic'}, renewal))
    args = service._make_graph_request.await_args.args
    assert args[0] == 'PATCH'
    assert args[3] == {'expirationDateTime': renewal['expires_at']}
