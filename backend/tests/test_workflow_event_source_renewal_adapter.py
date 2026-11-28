"""Native renewal protocol: only the Graph wire is controlled.

Durable arbitration and maintenance-loop qualification are separate gates.
"""
import asyncio
import copy
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from core.workflow_event_source_adapters import OutlookMailSourceAdapter
from core.workflow_event_source_enrollment import EnrollmentRefused
from integrations.microsoft365_service import Microsoft365Service


@pytest.fixture
def native_lease():
    service = Microsoft365Service(config={})
    service._make_graph_request = AsyncMock(return_value={'status': 'success', 'data': {}})
    adapter = OutlookMailSourceAdapter(service=service)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    document = {'prepared_at': (now - timedelta(hours=60)).isoformat(),
                'callback_url': 'https://example.invalid/notifications?registration=original',
                'provider_subscription_id': 'original/id?opaque',
                'receiver_state_digest': hashlib.sha256(b'synthetic-state').hexdigest()}
    plan = adapter.renewal_material(document, now=now)
    observed = {'id': document['provider_subscription_id'], 'resource': plan['resource'],
                'changeType': plan['change_type'], 'notificationUrl': plan['callback_url'],
                'expirationDateTime': plan['expires_at'], 'clientState': None}
    return adapter, document, plan, observed


def test_renewal_uses_exact_escaped_original_id_and_only_expiry_patch(native_lease):
    adapter, document, plan, observed = native_lease
    before = copy.deepcopy(document)
    original_plan = adapter.material(document)
    result = asyncio.run(adapter.renew(document, {'access_token': 'synthetic'}, plan))
    assert result == {'subscription_id': document['provider_subscription_id']}
    adapter.service._make_graph_request.assert_awaited_once_with('PATCH',
        adapter.service.base_url + '/subscriptions/original%2Fid%3Fopaque', 'synthetic',
        {'expirationDateTime': plan['expires_at']})
    assert document == before and adapter.material(document) == original_plan
    assert adapter.verify_renewal(document, result, observed, plan) is True
    assert adapter.verify(document, result, observed) is False


@pytest.mark.parametrize('field,value', [('id', 'foreign'), ('resource', 'foreign'),
    ('changeType', 'created'), ('notificationUrl', 'https://example.invalid/foreign'),
    ('expirationDateTime', '2099-01-01T00:00:00Z'), ('clientState', 'foreign')])
def test_readback_requires_exact_new_lease_material(native_lease, field, value):
    adapter, document, plan, observed = native_lease
    observed[field] = value
    assert adapter.verify_renewal(document, {'subscription_id': document['provider_subscription_id']},
                                  observed, plan) is False


@pytest.mark.parametrize('code,refused', [(403, True), (404, True), (429, False),
                                         (500, False), (True, False)])
def test_only_confirmed_refusal_is_pre_effect(native_lease, code, refused):
    adapter, document, plan, _ = native_lease
    adapter.service._make_graph_request.return_value = {'status': 'error', 'code': code}
    with pytest.raises(EnrollmentRefused if refused else ValueError) as caught:
        asyncio.run(adapter.renew(document, {'access_token': 'synthetic'}, plan))
    assert isinstance(caught.value, EnrollmentRefused) is refused
    assert adapter.service._make_graph_request.await_count == 1


def test_transport_uncertainty_propagates_without_retry(native_lease):
    adapter, document, plan, _ = native_lease
    adapter.service._make_graph_request.side_effect = TimeoutError('synthetic timeout')
    with pytest.raises(TimeoutError):
        asyncio.run(adapter.renew(document, {'access_token': 'synthetic'}, plan))
    assert adapter.service._make_graph_request.await_count == 1


@pytest.mark.parametrize('change', ['callback', 'naive', 'expired', 'too_far', 'extra'])
def test_invalid_frozen_material_never_dispatches(native_lease, change):
    adapter, document, plan, observed = native_lease
    if change == 'callback': plan['callback_url'] = 'https://example.invalid/foreign'
    elif change == 'naive': plan['expires_at'] = '2099-01-01T00:00:00'
    elif change == 'expired': plan['expires_at'] = '2000-01-01T00:00:00Z'
    elif change == 'too_far': plan['expires_at'] = '2099-01-01T00:00:00Z'
    else: plan['unreviewed'] = True
    with pytest.raises(ValueError):
        asyncio.run(adapter.renew(document, {'access_token': 'synthetic'}, plan))
    adapter.service._make_graph_request.assert_not_awaited()


def test_missing_target_cannot_create_replacement(native_lease):
    adapter, document, plan, _ = native_lease
    document.pop('provider_subscription_id')
    with pytest.raises(ValueError):
        asyncio.run(adapter.renew(document, {'access_token': 'synthetic'}, plan))
    adapter.service._make_graph_request.assert_not_awaited()


@pytest.mark.parametrize('receipt', [None, [], {}, {'subscription_id': 'foreign'}])
def test_unproved_receipt_never_certifies_renewal(native_lease, receipt):
    adapter, document, plan, observed = native_lease
    assert adapter.verify_renewal(document, receipt, observed, plan) is False
