"""Controlled public setup/callback -> real workflow -> durable in-app effect.

Authenticated principal lookup and provider HTTP are doubled. The permission
checker, User/connection rows, source lifecycle, admission, worker, graph engine
and notification service are production implementations on scratch SQLite.
"""
import asyncio
import json
from urllib.parse import urlsplit
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from core import workflow_endpoints as workflows
from core import workflow_event_source_routes as routes
from core import security_dependencies
from core import workflow_event_worker as worker
from core.models import User, UserConnection, Tenant, Workspace, Notification, WorkflowExecution, TenantSetting
from core.execution_state_manager import ExecutionStateManager
from core.workflow_engine import WorkflowEngine
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


@pytest.fixture
def http_world(enrollment_world, monkeypatch, tmp_path):
    factory, params, args, provider = enrollment_world
    with factory() as db:
        db.add(Tenant(id='tenant', name='Synthetic', subdomain='synthetic', edition='personal', is_active=True))
        db.add(Workspace(id='workspace', name='Synthetic', tenant_id='tenant', status='active'))
        db.commit()
    monkeypatch.setattr(routes, '_database_factory', lambda: factory)
    monkeypatch.setattr(routes, 'source_adapter', lambda source: args['adapter'])
    monkeypatch.setattr(worker, '_open_db', factory)
    monkeypatch.setattr('core.workflow_engine.get_db_session', factory)
    monkeypatch.setattr('core.database.SessionLocal', factory)
    monkeypatch.setattr('core.workflow_engine.get_connection_manager', lambda: AsyncMock())
    monkeypatch.setattr('core.workflow_engine.notifier', AsyncMock())
    monkeypatch.setenv('ATOM_PUBLIC_WEBHOOK_BASE_URL', 'https://example.invalid')
    catalog = tmp_path / 'http-workflows.json'
    monkeypatch.setattr(workflows, 'WORKFLOWS_FILE', str(catalog))
    # Real native adapter, with only the Graph HTTP wire replaced.
    service = args['adapter'].service
    original = service._make_graph_request.side_effect
    provider['subject'] = 'invoice'
    provider['content_unavailable'] = False
    provider['after_content'] = None
    async def wire(method, url, token, data=None):
        if '/me/messages/' in url:
            provider['calls'].append((method, url, None))
            if provider['after_content'] is not None:
                provider['after_content']()
            if provider['content_unavailable']:
                return {'status': 'error', 'code': 503}
            return {'status': 'success', 'data': {
                'id': 'message-one', 'subject': provider['subject'],
                'body': {'contentType': 'text', 'content': 'Synthetic source text'},
                'receivedDateTime': '2026-11-23T12:00:00Z',
                'user_id': 'forged-recipient', 'workspace_id': 'foreign', 'isRead': False}}
        return await original(method, url, token, data)
    service._make_graph_request.side_effect = wire
    principal = {'signed_in': True}
    def signed_in():
        if not principal['signed_in']:
            raise HTTPException(401, 'Authentication required')
        with factory() as db:
            return db.get(User, 'owner')
    app = FastAPI()
    app.include_router(workflows.router, prefix='/api/v1/workflows')
    app.dependency_overrides[security_dependencies.get_current_user] = signed_in
    # Existing create/save route DB metadata lookup uses the same scratch world.
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[workflows.get_db] = database
    with TestClient(app) as client:
        yield client, factory, provider, principal, args['adapter']


def setup_source(client, provider):
    response = client.post('/api/v1/workflows/event-sources/connection/enroll', json={})
    assert response.status_code == 200, response.text
    result = response.json()
    created = next(call[2] for call in provider['calls'] if call[0] == 'POST')
    callback = urlsplit(created['notificationUrl'])
    item = {'subscriptionId': 'provider-subscription', 'clientState': created['clientState'],
            'changeType': 'created', 'resource': 'untrusted-resource-path-is-not-used',
            'resourceData': {'id': 'message-one'}}
    return result, callback.path + '?' + callback.query, item


def save_rule(client):
    def node(identifier, kind, config):
        return {'id': identifier, 'type': kind, 'title': identifier, 'description': 'Saved rule',
                'position': {'x': 0, 'y': 0}, 'config': config, 'connections': []}
    result = client.post('/api/v1/workflows/workflows', json={
        'id': 'mail-rule', 'name': 'Mail source rule', 'description': 'Notify caller for selected source content',
        'version': '1', 'enabled': True, 'triggers': ['event'],
        'nodes': [node('source-trigger', 'trigger', {'service': 'outlook', 'action': 'message.created',
                    'event_subscription': {'connection_id': 'connection', 'source': 'outlook',
                        'event_type': 'message.created', 'enabled': True}}),
                  node('notify', 'action', {'service': 'workflow_notification', 'action': 'notify_caller',
                    'parameters': {'title': 'Selected mail', 'message': '${input.event.payload.subject}',
                                   'user_id': 'forged-recipient', 'workspace_id': 'foreign'}})],
        'connections': [{'id': 'edge', 'source': 'source-trigger', 'target': 'notify',
                         'condition': "${input.event.payload.subject} == 'invoice'"}]})
    assert result.status_code == 200, result.text


def test_public_setup_callback_real_worker_and_real_notification_once(http_world):
    client, factory, provider, principal, adapter = http_world
    catalog = client.get('/api/v1/workflows/event-sources')
    assert catalog.status_code == 200
    assert catalog.json()['sources'][0]['connection_id'] == 'connection'
    setup, callback, item = setup_source(client, provider)
    save_rule(client)
    # Provider callbacks are anonymous; the registered receiver state is their proof.
    principal['signed_in'] = False
    first = client.post(callback, json={'value': [item]})
    assert first.status_code == 200 and first.json()['admitted'] == 1, first.text
    duplicate = client.post(callback, json={'value': [item]})
    assert duplicate.status_code == 200 and duplicate.json()['duplicates'] == 1, duplicate.text
    async def drain():
        engine = WorkflowEngine()
        engine.state_manager = ExecutionStateManager()
        with factory() as db:
            execution_id = db.query(WorkflowExecution.execution_id).scalar()
        state = await engine.state_manager.get_execution_state(execution_id)
        await worker.dispatch_preflight(execution_id, state, state['context']['_atom_event_admission']['workflow_snapshot'])
        assert await worker.process_pending_event_executions_once(engine=engine) == 1
        await asyncio.gather(*list(engine._background_tasks))
    asyncio.run(asyncio.wait_for(drain(), timeout=30))
    with factory() as db:
        execution = db.query(WorkflowExecution).one()
        assert execution.status == 'COMPLETED', execution.error
        notification = db.query(Notification).one()
        assert (notification.user_id, notification.tenant_id, notification.workspace_id) == ('owner', 'tenant', 'workspace')
        assert notification.title == 'Selected mail' and notification.message == 'invoice'
        assert db.query(WorkflowExecution).count() == 1
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1
    assert 'receiver_state' not in str(setup) and item['clientState'] not in str(setup)


@pytest.mark.parametrize('case', ['bad_state', 'wrong_subscription', 'wrong_registration'])
def test_unverified_callback_has_no_event_or_content_fetch(http_world, case):
    client, factory, provider, principal, adapter = http_world
    setup, callback, item = setup_source(client, provider)
    save_rule(client)
    if case == 'bad_state': item['clientState'] = 'different-state'
    elif case == 'wrong_subscription': item['subscriptionId'] = 'other-subscription'
    else: callback = callback.replace(setup['operation_id'], 'other-registration')
    before = len(provider['calls'])
    result = client.post(callback, json={'value': [item]})
    assert result.status_code in (401, 503), result.text
    assert len(provider['calls']) == before
    with factory() as db:
        assert db.query(WorkflowExecution).count() == 0 and db.query(Notification).count() == 0


def test_content_failure_is_retriable_not_a_false_accepted_delivery(http_world):
    client, factory, provider, principal, adapter = http_world
    setup, callback, item = setup_source(client, provider)
    save_rule(client)
    provider['content_unavailable'] = True
    assert client.post(callback, json={'value': [item]}).status_code == 503
    with factory() as db: assert db.query(WorkflowExecution).count() == 0
    provider['content_unavailable'] = False
    result = client.post(callback, json={'value': [item]})
    assert result.status_code == 200 and result.json()['admitted'] == 1


def test_role_and_forged_setup_body_do_not_enroll(http_world):
    client, factory, provider, principal, adapter = http_world
    assert client.post('/api/v1/workflows/event-sources/connection/enroll',
                       json={'callback_base_url': 'https://elsewhere.invalid', 'actor_id': 'other'}).status_code == 422
    with factory() as db:
        db.get(User, 'owner').role = 'member'
        db.commit()
    assert client.post('/api/v1/workflows/event-sources/connection/enroll', json={}).status_code == 403
    assert provider['calls'] == []
    with factory() as db: assert db.query(TenantSetting).count() == 0


def test_missing_callback_configuration_has_no_setup_effect(http_world, monkeypatch):
    client, factory, provider, principal, adapter = http_world
    monkeypatch.delenv('ATOM_PUBLIC_WEBHOOK_BASE_URL', raising=False)
    monkeypatch.delenv('ATOM_GRAPH_WEBHOOK_BASE_URL', raising=False)
    assert client.post('/api/v1/workflows/event-sources/connection/enroll', json={}).status_code == 503
    assert provider['calls'] == []
    with factory() as db: assert db.query(TenantSetting).count() == 0


def test_verified_callback_reconciles_lost_enrollment_without_second_create(http_world):
    client, factory, provider, principal, adapter = http_world
    provider['mode'] = 'timeout'
    result = client.post('/api/v1/workflows/event-sources/connection/enroll', json={})
    assert result.status_code == 503 and result.json()['status'] == 'effect_unknown'
    created = next(call[2] for call in provider['calls'] if call[0] == 'POST')
    callback = urlsplit(created['notificationUrl'])
    save_rule(client)
    recovered = client.post(callback.path + '?' + callback.query, json={'value': [{
        'subscriptionId': 'provider-subscription', 'clientState': created['clientState'],
        'changeType': 'created', 'resourceData': {'id': 'message-one'}}]})
    assert recovered.status_code == 200 and recovered.json()['admitted'] == 1, recovered.text
    assert sum(call[0] == 'POST' for call in provider['calls']) == 1


@pytest.mark.parametrize('change', ['disable_owner', 'transfer_connection'])
def test_authority_change_during_content_fetch_cannot_admit(http_world, change):
    client, factory, provider, principal, adapter = http_world
    setup, callback, item = setup_source(client, provider)
    save_rule(client)
    def change_authority():
        with factory() as db:
            if change == 'disable_owner':
                db.get(User, 'owner').is_active = False
            else:
                db.get(UserConnection, 'connection').workspace_id = 'peer-workspace'
            db.commit()
    provider['after_content'] = change_authority
    response = client.post(callback, json={'value': [item]})
    assert response.status_code in (403, 503), response.text
    with factory() as db:
        assert db.query(WorkflowExecution).count() == 0
        assert db.query(Notification).count() == 0
        if change == 'disable_owner':
            assert db.get(User, 'owner').is_active is False
        else:
            assert db.get(UserConnection, 'connection').workspace_id == 'peer-workspace'


def test_registered_provider_validation_handshake(http_world):
    client, factory, provider, principal, adapter = http_world
    setup, callback, item = setup_source(client, provider)
    principal['signed_in'] = False
    response = client.post(callback + '&validationToken=synthetic-handshake')
    assert response.status_code == 200 and response.text == 'synthetic-handshake'
    with factory() as db:
        assert db.query(WorkflowExecution).count() == 0


def test_malformed_server_callback_configuration_is_unavailable(http_world, monkeypatch):
    client, factory, provider, principal, adapter = http_world
    monkeypatch.setenv('ATOM_PUBLIC_WEBHOOK_BASE_URL', 'https://[broken')
    assert client.get('/api/v1/workflows/event-sources').json()['callback_configured'] is False
    assert client.post('/api/v1/workflows/event-sources/connection/enroll', json={}).status_code == 503
    assert provider['calls'] == []
