"""Provider transport is doubled; the emitted subscription request is inspected."""
import asyncio
from unittest.mock import AsyncMock
import pytest
from integrations.microsoft365_service import Microsoft365Service


def test_subscription_uses_explicit_receiver_state_in_emitted_payload():
    service = Microsoft365Service(config={})
    service._make_graph_request = AsyncMock(return_value={'status': 'success', 'data': {'id': 'subscription'}})
    state = 'synthetic-receiver-state'
    result = asyncio.run(service.create_subscription(
        'synthetic', '/me/messages', 'created', 'https://example.invalid/callback',
        '2026-11-25T00:00:00Z', client_state=state))
    assert result['status'] == 'success'
    args = service._make_graph_request.await_args.args
    assert args[0:3] == ('POST', 'https://graph.microsoft.com/v1.0/subscriptions', 'synthetic')
    assert args[3]['clientState'] == state
    assert args[3]['changeType'] == 'created,deleted'


@pytest.mark.parametrize('state', ['', '   ', True, 'x' * 129])
def test_invalid_receiver_state_refuses_before_provider_dispatch(state):
    service = Microsoft365Service(config={})
    service._make_graph_request = AsyncMock()
    result = asyncio.run(service.create_subscription(
        'synthetic', '/me/messages', 'created', 'https://example.invalid/callback',
        '2026-11-25T00:00:00Z', client_state=state))
    assert result['status'] == 'error'
    service._make_graph_request.assert_not_awaited()


def test_realtime_enrollment_and_receiver_share_the_exact_state(monkeypatch):
    from integrations import outlook_realtime as realtime_module
    from integrations.outlook_service import outlook_service
    monkeypatch.setattr(realtime_module, '_load_state', lambda: {})
    monkeypatch.setattr(realtime_module, '_save_state', lambda state: None)
    monkeypatch.setattr(realtime_module, '_public_base_url', lambda: 'https://example.invalid')
    monkeypatch.setattr(outlook_service, '_get_access_token', AsyncMock(return_value='synthetic'))
    transport = AsyncMock(return_value={'status': 'success', 'data': {
        'id': 'subscription', 'expirationDateTime': '2026-11-25T00:00:00Z'}})
    monkeypatch.setattr(Microsoft365Service, '_make_graph_request', transport)
    receiver = realtime_module.OutlookRealtimeManager()
    result = asyncio.run(receiver.ensure_subscription('synthetic-owner'))
    assert result['enabled'] is True
    emitted = transport.await_args.args[3]['clientState']
    assert receiver.verify_client_state(emitted) is True
    assert receiver.verify_client_state('different-state') is False
    assert receiver._state['user_id'] == 'synthetic-owner'
