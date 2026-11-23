"""Controlled public HTTP registration with real scratch connection metadata."""
import inspect
import json
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest
from core import workflow_endpoints as routes
from core.models import UserConnection


@pytest.fixture
def world(monkeypatch, tmp_path):
    catalog = tmp_path / 'workflows.json'
    monkeypatch.setattr(routes, 'WORKFLOWS_FILE', str(catalog))
    actor = SimpleNamespace(id='owner', tenant_id='tenant', workspace_id='workspace', role='workspace_admin')
    db_engine = create_engine(f"sqlite:///{tmp_path / 'connections.db'}", connect_args={'check_same_thread': False})
    UserConnection.__table__.create(db_engine)
    with Session(db_engine) as db:
        db.add(UserConnection(id='connection-one', user_id=actor.id, tenant_id=actor.tenant_id,
                              workspace_id=actor.workspace_id, integration_id='synthetic-mail',
                              connection_name='Synthetic source', credentials={}, status='active'))
        db.commit()
    app = FastAPI()
    app.include_router(routes.router)
    for endpoint in [routes.create_workflow, routes.get_workflow, routes.save_structured_workflow]:
        app.dependency_overrides[inspect.signature(endpoint).parameters['user'].default.dependency] = lambda: actor
    def database():
        with Session(db_engine) as db:
            yield db
    app.dependency_overrides[routes.get_db] = database
    subscription = {'id': 'trigger-one', 'connection_id': 'connection-one',
                    'source': 'synthetic-mail', 'event_type': 'message.created', 'enabled': True}
    payload = {'id': 'workflow-one', 'name': 'Invoice routing', 'description': 'Route invoice events',
               'version': '1', 'nodes': [], 'connections': [], 'triggers': ['event'],
               'enabled': True, 'event_subscriptions': [subscription],
               'tenant_id': 'forged', 'workspace_id': 'forged', 'created_by': 'forged'}
    with TestClient(app) as client:
        yield client, catalog, actor, db_engine, subscription, payload


def test_public_create_and_fresh_read_preserve_bound_registration(world):
    client, catalog, actor, db, subscription, payload = world
    result = client.post('/workflows', json=payload)
    assert result.status_code == 200, result.text
    stored = json.loads(catalog.read_text())[0]
    assert stored['event_subscriptions'] == [subscription]
    assert (stored['created_by'], stored['tenant_id'], stored['workspace_id']) == (actor.id, actor.tenant_id, actor.workspace_id)
    fresh = client.get('/workflows/workflow-one')
    assert fresh.status_code == 200
    assert fresh.json()['event_subscriptions'] == [subscription]
    assert fresh.json()['created_by'] == actor.id


@pytest.mark.parametrize('case', ['missing', 'wrong_owner', 'wrong_workspace', 'wrong_tenant', 'revoked', 'wrong_source', 'duplicate_id', 'duplicate_binding', 'invalid_enabled'])
def test_invalid_registration_refuses_before_catalog_write(world, case):
    client, catalog, actor, db_engine, sub, payload = world
    if case in ['wrong_owner', 'wrong_workspace', 'wrong_tenant', 'revoked']:
        with Session(db_engine) as db:
            row = db.get(UserConnection, 'connection-one')
            setattr(row, {'wrong_owner': 'user_id', 'wrong_workspace': 'workspace_id',
                          'wrong_tenant': 'tenant_id', 'revoked': 'status'}[case], 'other')
            db.commit()
    elif case == 'missing':
        sub['connection_id'] = 'missing'
    elif case == 'wrong_source':
        sub['source'] = 'other-provider'
    elif case == 'invalid_enabled':
        sub['enabled'] = 'true'
    else:
        extra = dict(sub)
        if case == 'duplicate_id':
            extra['event_type'] = 'other.event'
        else:
            extra['id'] = 'another-id'
        payload['event_subscriptions'].append(extra)
    result = client.post('/workflows', json=payload)
    assert result.status_code == 400, result.text
    assert not catalog.exists()


def test_revision_save_omission_clear_and_stale_preserve_history(world):
    client, catalog, actor, db, subscription, payload = world
    created = client.post('/workflows', json=payload)
    assert created.status_code == 200
    revision = created.json()['revision']
    changed = client.put('/workflows/workflow-one', json={
        'revision': revision, 'reason': 'Rename workflow', 'name': 'Updated name'})
    assert changed.status_code == 200, changed.text
    assert changed.json()['event_subscriptions'] == [subscription]
    stale = client.put('/workflows/workflow-one', json={
        'revision': revision, 'reason': 'Stale clear', 'event_subscriptions': []})
    assert stale.status_code == 409
    assert json.loads(catalog.read_text())[0]['event_subscriptions'] == [subscription]
    cleared = client.put('/workflows/workflow-one', json={
        'revision': changed.json()['revision'], 'reason': 'Disable source', 'event_subscriptions': []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()['event_subscriptions'] == []
    assert len(json.loads(catalog.read_text())[0]['corrections']) == 2
    actor.id = 'foreign-owner'
    assert client.get('/workflows/workflow-one').status_code == 404


def test_legacy_post_cannot_bypass_subscription_revision(world):
    client, catalog, actor, db, sub, payload = world
    assert client.post('/workflows', json=payload).status_code == 200
    before = catalog.read_bytes()
    payload['event_subscriptions'][0]['event_type'] = 'different.event'
    assert client.post('/workflows', json=payload).status_code == 409
    assert catalog.read_bytes() == before


@pytest.mark.parametrize('matching_null', [True, False])
def test_raw_nullable_connection_scope_is_compared_exactly(world, matching_null):
    client, catalog, actor, db_engine, sub, payload = world
    actor.workspace_id = None
    with Session(db_engine) as db:
        row = db.get(UserConnection, 'connection-one')
        row.workspace_id = None if matching_null else ''
        db.commit()
    result = client.post('/workflows', json=payload)
    assert result.status_code == (200 if matching_null else 400), result.text
    assert catalog.exists() == matching_null


def test_omitting_subscriptions_cannot_bypass_owned_revision_save(world):
    client, catalog, actor, db, sub, payload = world
    assert client.post('/workflows', json=payload).status_code == 200
    before = catalog.read_bytes()
    payload.pop('event_subscriptions')
    payload['name'] = 'Unversioned replacement'
    assert client.post('/workflows', json=payload).status_code == 409
    assert catalog.read_bytes() == before


def test_saved_registration_survives_fresh_process(world):
    import os
    import subprocess
    import sys
    client, catalog, actor, db, sub, payload = world
    assert client.post('/workflows', json=payload).status_code == 200
    script = '''
import asyncio, json, sys
from types import SimpleNamespace
from fastapi import Response
from core import workflow_endpoints as routes
routes.WORKFLOWS_FILE = sys.argv[1]
actor = SimpleNamespace(id="owner", tenant_id="tenant", workspace_id="workspace")
result = asyncio.run(routes.get_workflow("workflow-one", Response(), user=actor))
print("REGISTRATION_READBACK:" + json.dumps({"subscriptions": result["event_subscriptions"], "owner": result["created_by"]}))
'''
    result = subprocess.run([sys.executable, '-c', script, str(catalog)],
                            env=os.environ.copy(), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, 'Fresh process readback failed'
    lines = [s for s in result.stdout.splitlines() if s.startswith('REGISTRATION_READBACK:')]
    assert len(lines) == 1
    assert json.loads(lines[0].split(':', 1)[1]) == {'subscriptions': [sub], 'owner': actor.id}
