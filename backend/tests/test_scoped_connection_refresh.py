"""Scoped OAuth refresh: real encrypted rows/operation CAS, only HTTP doubled."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import httpx
import pytest
from core.connection_service import ConnectionService
from core.models import User, UserConnection, TaskOperationRecord, AuditLog
from core import outbound_operation_claim as operations
from core.oauth_handler import OAuthConfig, PROVIDER_CONFIGS
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db

@pytest.fixture
def refresh_world(source_world, monkeypatch):
    factory, params = source_world
    service = ConnectionService()
    old = {'access_token': 'synthetic-old-access', 'refresh_token': 'synthetic-old-refresh'}
    encrypted = service._encrypt(old)
    with factory() as db:
        row = db.get(UserConnection, 'connection'); row.credentials = encrypted
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1); db.commit()
    for key in ('CLIENT_ID','CLIENT_SECRET','REDIRECT_URI'):
        monkeypatch.setenv('TEST_REFRESH_' + key, 'synthetic-config-value')
    config = OAuthConfig(client_id_env='TEST_REFRESH_CLIENT_ID', client_secret_env='TEST_REFRESH_CLIENT_SECRET',
        redirect_uri_env='TEST_REFRESH_REDIRECT_URI', auth_url='https://provider.invalid/authorize',
        token_url='https://provider.invalid/token', scopes=[])
    monkeypatch.setitem(PROVIDER_CONFIGS, 'microsoft', config)
    wire = {'calls': 0, 'status': 200, 'after': None, 'timeout': False,
        'grant': {'access_token': 'synthetic-new-access', 'refresh_token': 'synthetic-new-refresh', 'expires_in': 3600}}
    async def post(client, url, *, data, headers):
        assert url == 'https://provider.invalid/token' and data['refresh_token'] == old['refresh_token']
        wire['calls'] += 1
        await asyncio.sleep(0.01)
        if wire['after']: wire['after']()
        if wire['timeout']: raise httpx.ReadTimeout('synthetic-private-provider-detail')
        return httpx.Response(wire['status'], json=wire['grant'])
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    args = dict(user_id='owner', tenant_id='tenant', workspace_id='workspace', connection_id='connection',
        integration_id='synthetic-source', provider='microsoft', db_factory=factory)
    return factory, service, args, wire, encrypted


def test_refresh_commit_readback_and_replay_create_one_attempt(refresh_world):
    factory, service, args, wire, old = refresh_world
    first = asyncio.run(service.ensure_scoped_connection_credentials(**args))
    assert first['access_token'] == 'synthetic-new-access'
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) == first
    with factory() as db:
        row = db.get(UserConnection, 'connection'); operation = db.query(TaskOperationRecord).one()
        assert row.credentials != old and service._decrypt(row.credentials) == first
        assert operation.status == operations.SUCCEEDED
        audit = db.query(AuditLog).one()
        assert audit.user_id == 'owner' and audit.resource == 'connection'
        assert audit.tenant_id == 'tenant' and audit.workspace_id == 'workspace'
        assert json.loads(audit.metadata_json)['result_digest'] == operation.result_json['result_digest']
        receipt = json.dumps(operation.result_json) + audit.metadata_json
        assert not any(value in receipt for value in first.values() if isinstance(value, str))
    assert wire['calls'] == 1


def test_competing_refreshes_have_one_provider_call(refresh_world):
    factory, service, args, wire, old = refresh_world
    async def race(): return await asyncio.gather(*(service.ensure_scoped_connection_credentials(**args) for _ in range(2)))
    outcomes = asyncio.run(race())
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert wire['calls'] == 1
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args))['access_token'] == 'synthetic-new-access'
    with factory() as db: assert db.query(TaskOperationRecord).count() == 1


@pytest.mark.parametrize('mode', ['timeout', 'malformed', 'lifetime', 'refused'])
def test_unknown_or_refused_refresh_never_resends_or_stores_private_failure(refresh_world, mode, caplog):
    factory, service, args, wire, old = refresh_world
    if mode == 'timeout': wire['timeout'] = True
    elif mode == 'malformed': wire['grant'] = {'unexpected': 'synthetic-private-provider-detail'}
    elif mode == 'lifetime': wire['grant']['expires_in'] = False
    else: wire.update(status=400, grant={'error': 'invalid_grant', 'detail': 'synthetic-private-provider-detail'})
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    assert asyncio.run(ConnectionService().ensure_scoped_connection_credentials(**args)) is None
    assert wire['calls'] == 1
    with factory() as db:
        assert db.get(UserConnection, 'connection').credentials == old
        operation = db.query(TaskOperationRecord).one()
        assert operation.status == (operations.FAILED_BEFORE_EFFECT if mode == 'refused' else operations.UNCERTAIN_EFFECT)
        assert operation.result_json is None
    assert 'synthetic-private-provider-detail' not in caplog.text


@pytest.mark.parametrize('peer', ['reconnect', 'disable', 'move', 'policy'])
def test_refresh_does_not_overwrite_peer_authority_or_reconnect(refresh_world, peer):
    factory, service, args, wire, old = refresh_world
    replacement = service._encrypt({'access_token': 'synthetic-peer-access'})
    def change():
        with factory() as db:
            if peer == 'reconnect':
                row = db.get(UserConnection, 'connection'); row.credentials = replacement
                row.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            elif peer == 'disable': db.get(User, 'owner').is_active = False
            elif peer == 'move': db.get(UserConnection, 'connection').workspace_id = 'peer-workspace'
            else: db.get(UserConnection, 'connection').scope = 'org'
            db.commit()
    wire['after'] = change
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    with factory() as db:
        row = db.get(UserConnection, 'connection')
        assert row.credentials == (replacement if peer == 'reconnect' else old)
        assert db.query(TaskOperationRecord).one().status == operations.UNCERTAIN_EFFECT
        if peer == 'disable': assert db.get(User, 'owner').is_active is False
        if peer == 'move': assert row.workspace_id == 'peer-workspace'
        if peer == 'policy': assert row.scope == 'org'
        assert db.query(AuditLog).count() == 0
    repeated = asyncio.run(ConnectionService().ensure_scoped_connection_credentials(**args))
    assert (repeated is not None) == (peer == 'reconnect')
    assert wire['calls'] == 1


def test_missing_refresh_material_has_no_operation_or_provider_effect(refresh_world):
    factory, service, args, wire, old = refresh_world
    with factory() as db:
        db.get(UserConnection, 'connection').credentials = service._encrypt({'access_token': 'synthetic-old-access'})
        db.commit()
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    assert wire['calls'] == 0
    with factory() as db: assert db.query(TaskOperationRecord).count() == 0


def test_lost_local_receipt_never_issues_a_second_refresh(refresh_world, monkeypatch):
    factory, service, args, wire, old = refresh_world
    original = operations.mark_status
    def lost(record, status, **kwargs):
        if status == operations.SUCCEEDED: return False
        return original(record, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', lost)
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    assert wire['calls'] == 1
    with factory() as db:
        assert db.get(UserConnection, 'connection').credentials == old
        assert db.query(TaskOperationRecord).one().status == operations.UNCERTAIN_EFFECT


def test_predispatch_authority_change_prevents_refresh(refresh_world, monkeypatch):
    factory, service, args, wire, old = refresh_world
    original = operations.mark_status
    def change(record, status, **kwargs):
        if status == operations.DISPATCHING:
            with factory() as db:
                db.get(User, 'owner').is_active = False; db.commit()
        return original(record, status, **kwargs)
    monkeypatch.setattr(operations, 'mark_status', change)
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    assert wire['calls'] == 0
    with factory() as db:
        assert db.get(User, 'owner').is_active is False
        assert db.get(UserConnection, 'connection').credentials == old
        assert db.query(AuditLog).count() == 0


def test_audit_failure_rolls_back_grant_and_receipt(refresh_world, monkeypatch):
    from sqlalchemy.orm import Session
    factory, service, args, wire, old = refresh_world
    original = Session.add
    def fail(db, value, *a, **kw):
        if isinstance(value, AuditLog): raise ValueError('synthetic-private-audit-detail')
        return original(db, value, *a, **kw)
    monkeypatch.setattr(Session, 'add', fail)
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    assert asyncio.run(ConnectionService().ensure_scoped_connection_credentials(**args)) is None
    assert wire['calls'] == 1
    with factory() as db:
        assert db.get(UserConnection, 'connection').credentials == old
        assert db.query(TaskOperationRecord).one().status == operations.UNCERTAIN_EFFECT
        assert db.query(AuditLog).count() == 0


def test_authorized_oauth_material_is_frozen_before_dispatch(refresh_world, monkeypatch):
    factory, service, args, wire, old = refresh_world
    original = operations.mark_status
    def change(record, status, **kwargs):
        result = original(record, status, **kwargs)
        if status == operations.DISPATCHING and result:
            monkeypatch.setenv('TEST_REFRESH_CLIENT_ID', 'peer-client')
            monkeypatch.setenv('TEST_REFRESH_CLIENT_SECRET', 'peer-secret')
            PROVIDER_CONFIGS['microsoft'].token_url = 'https://elsewhere.invalid/token'
        return result
    monkeypatch.setattr(operations, 'mark_status', change)
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args))['access_token'] == 'synthetic-new-access'
    assert wire['calls'] == 1


def test_scope_move_cannot_repeat_an_uncertain_credential_version(refresh_world):
    factory, service, args, wire, old = refresh_world
    wire['timeout'] = True
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    with factory() as db:
        db.get(User, 'owner').workspace_id = 'second-workspace'
        db.get(UserConnection, 'connection').workspace_id = 'second-workspace'
        db.commit()
    assert asyncio.run(ConnectionService().ensure_scoped_connection_credentials(**dict(args, workspace_id='second-workspace'))) is None
    assert wire['calls'] == 1
    with factory() as db:
        assert db.get(UserConnection, 'connection').credentials == old
        assert db.get(UserConnection, 'connection').workspace_id == 'second-workspace'
        assert db.query(AuditLog).count() == 0


def test_fresh_process_does_not_repeat_unknown_refresh(refresh_world):
    import os
    import subprocess
    import sys
    from pathlib import Path
    factory, service, args, wire, old = refresh_world
    wire['timeout'] = True
    assert asyncio.run(service.ensure_scoped_connection_credentials(**args)) is None
    with factory() as db: url = str(db.get_bind().url)
    script = '''
import asyncio, json, sys, httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.connection_service import ConnectionService
from core.oauth_handler import OAuthConfig, PROVIDER_CONFIGS
from core.models import UserConnection, TaskOperationRecord
engine = create_engine(sys.argv[1])
factory = lambda: Session(engine)
service = ConnectionService()
config = OAuthConfig(client_id_env='TEST_REFRESH_CLIENT_ID', client_secret_env='TEST_REFRESH_CLIENT_SECRET',
    redirect_uri_env='TEST_REFRESH_REDIRECT_URI', auth_url='https://provider.invalid/authorize',
    token_url='https://provider.invalid/token', scopes=[])
assert config.is_configured()
PROVIDER_CONFIGS['microsoft'] = config
calls = []
async def forbidden(*args, **kwargs):
    calls.append('attempt')
    raise RuntimeError('must not call transport after unknown outcome')
httpx.AsyncClient.post = forbidden
with factory() as db:
    assert service._decrypt(db.get(UserConnection, 'connection').credentials)['access_token'] == 'synthetic-old-access'
result = asyncio.run(service.ensure_scoped_connection_credentials(user_id='owner', tenant_id='tenant',
    workspace_id='workspace', connection_id='connection', integration_id='synthetic-source', provider='microsoft', db_factory=factory))
with factory() as db:
    rows = db.query(TaskOperationRecord).all()
    record = {'returned': result is not None, 'calls': len(calls), 'rows': len(rows), 'status': rows[0].status}
print('SCOPED_REFRESH_REPLAY:' + json.dumps(record))
engine.dispose()
'''
    keys = ['PATH', 'HOME', 'PYTHONPATH', 'SECRET_KEY', 'TEST_REFRESH_CLIENT_ID',
        'TEST_REFRESH_CLIENT_SECRET', 'TEST_REFRESH_REDIRECT_URI']
    env = {key: os.environ[key] for key in keys if key in os.environ}
    env.update(TESTING='1', DATABASE_URL=url)
    result = subprocess.run([sys.executable, '-c', script, url], cwd=Path(__file__).resolve().parents[1],
        env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, 'fresh-process credential replay did not complete'
    lines = [line for line in result.stdout.splitlines() if line.startswith('SCOPED_REFRESH_REPLAY:')]
    assert len(lines) == 1
    assert json.loads(lines[0].split(':', 1)[1]) == {
        'returned': False, 'calls': 0, 'rows': 1, 'status': operations.UNCERTAIN_EFFECT}
    assert wire['calls'] == 1
