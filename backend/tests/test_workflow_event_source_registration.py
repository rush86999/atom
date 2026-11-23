"""Source preparation uses real scoped rows, encrypted state, and atomic audit."""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.models import User, UserConnection, TenantSetting, AuditLog
from core import workflow_event_source_registration as service
from core.connection_service import ConnectionService
from tests.test_workflow_event_reservation import event_db


@pytest.fixture
def source_world(event_db, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workflow_event_reservations.db'}")
    with Session(engine) as db:
        db.add(User(id='owner', email='owner@example.invalid', first_name='Synthetic', last_name='Owner',
                    tenant_id='tenant', workspace_id='workspace', role='workspace_admin', status='active', is_active=True))
        db.add(UserConnection(id='connection', user_id='owner', tenant_id='tenant', workspace_id='workspace',
                              integration_id='synthetic-source', connection_name='Synthetic', status='active', credentials={}))
        db.commit()
    factory = lambda: Session(engine)
    params = dict(actor_id='owner', connection_id='connection', source='synthetic-source',
                  event_types=['record.created'], callback_base_url='https://example.invalid/source/connection',
                  db_factory=factory)
    try:
        yield factory, params
    finally:
        engine.dispose()


def test_preparation_is_durable_replay_with_private_encrypted_receiver_state(source_world):
    factory, params = source_world
    first = service.prepare_source_registration(**params)
    second = service.prepare_source_registration(**params)
    assert first == second
    assert first['phase'] == 'prepared' and first['enabled'] is False
    assert first['operation_id'] in first['callback_url']
    secret = ConnectionService()._decrypt(first['receiver_state_ciphertext'])['client_state']
    assert secret and secret not in json.dumps(first)
    public = service.public_registration(first)
    assert not any(k in public for k in ('receiver_state_ciphertext', 'receiver_state_digest', 'identity', 'request_digest'))
    with factory() as db:
        assert db.query(TenantSetting).count() == 1
        audit = db.query(AuditLog).one()
        assert secret not in audit.metadata_json
        assert first['receiver_state_ciphertext'] not in audit.metadata_json
        assert first['receiver_state_digest'] not in audit.metadata_json
        assert json.loads(audit.metadata_json)['operation_id'] == first['operation_id']


def test_changed_material_does_not_overwrite_registration(source_world):
    factory, params = source_world
    before = service.prepare_source_registration(**params)
    with pytest.raises(service.SourceRegistrationError, match='SOURCE_REGISTRATION_CONFLICT'):
        service.prepare_source_registration(**dict(params, event_types=['record.updated']))
    assert service.prepare_source_registration(**params) == before
    with factory() as db:
        assert db.query(AuditLog).count() == 1


@pytest.mark.parametrize('case', ['foreign', 'revoked', 'inactive', 'moved', 'unmanaged'])
def test_unavailable_source_has_no_registration_or_audit(source_world, case):
    factory, params = source_world
    with factory() as db:
        if case == 'foreign': db.get(UserConnection, 'connection').user_id = 'other'
        elif case == 'revoked': db.get(UserConnection, 'connection').status = 'revoked'
        elif case == 'inactive': db.get(User, 'owner').is_active = False
        elif case == 'unmanaged': db.get(User, 'owner').role = 'member'
        else: db.get(User, 'owner').workspace_id = 'other'
        db.commit()
    with pytest.raises(service.SourceRegistrationError):
        service.prepare_source_registration(**params)
    with factory() as db:
        assert db.query(TenantSetting).count() == 0
        assert db.query(AuditLog).count() == 0


@pytest.mark.parametrize('case', ['actor', 'connection'])
def test_authority_change_between_read_and_claim_preserves_peer(source_world, monkeypatch, case):
    factory, params = source_world
    original = service._claim
    def changed(db, actor, connection):
        with factory() as peer:
            if case == 'actor': peer.get(User, 'owner').is_active = False
            else: peer.get(UserConnection, 'connection').workspace_id = 'peer-workspace'
            peer.commit()
        return original(db, actor, connection)
    monkeypatch.setattr(service, '_claim', changed)
    with pytest.raises(service.SourceRegistrationError, match='SOURCE_AUTHORITY_CHANGED'):
        service.prepare_source_registration(**params)
    with factory() as db:
        assert db.query(TenantSetting).count() == 0
        assert db.query(AuditLog).count() == 0
        if case == 'actor': assert db.get(User, 'owner').is_active is False
        else: assert db.get(UserConnection, 'connection').workspace_id == 'peer-workspace'


@pytest.mark.parametrize('case', ['duplicate_events', 'insecure_callback'])
def test_invalid_setup_refuses_before_write(source_world, case):
    factory, params = source_world
    if case == 'duplicate_events': params['event_types'] = ['record.created', 'record.created']
    else: params['callback_base_url'] = 'http://example.invalid/source'
    with pytest.raises(service.SourceRegistrationError):
        service.prepare_source_registration(**params)
    with factory() as db:
        assert db.query(TenantSetting).count() == 0
        assert db.query(AuditLog).count() == 0


def test_competing_preparations_reconcile_one_durable_registration(source_world, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    factory, params = source_world
    barrier, lock = Barrier(2), Lock()
    calls = 0
    original = service._claim
    def compete(db, actor, connection):
        nonlocal calls
        with lock:
            calls += 1
            initial = calls <= 2
        if initial:
            barrier.wait(timeout=5)
        return original(db, actor, connection)
    monkeypatch.setattr(service, '_claim', compete)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.prepare_source_registration, **params) for _ in range(2)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=20))
            except service.SourceRegistrationError as exc:
                # SQLite may refuse lock contention; a later safe retry reconciles it.
                assert exc.code == 'SOURCE_REGISTRATION_UNAVAILABLE'
    canonical = service.prepare_source_registration(**params)
    assert outcomes and all(item == canonical for item in outcomes)
    with factory() as db:
        assert db.query(TenantSetting).count() == 1
        assert db.query(AuditLog).count() == 1


def test_audit_write_failure_rolls_back_preparation_and_returns_safe_error(source_world):
    from sqlalchemy import event
    factory, params = source_world
    def refuse_audit(mapper, connection, target):
        raise RuntimeError('synthetic audit write failure')
    event.listen(AuditLog, 'before_insert', refuse_audit)
    try:
        with pytest.raises(service.SourceRegistrationError, match='SOURCE_REGISTRATION_UNAVAILABLE') as exc:
            service.prepare_source_registration(**params)
        assert 'synthetic audit' not in str(exc.value)
    finally:
        event.remove(AuditLog, 'before_insert', refuse_audit)
    with factory() as db:
        assert db.query(TenantSetting).count() == 0
        assert db.query(AuditLog).count() == 0
        assert db.get(User, 'owner').is_active is True
        assert db.get(UserConnection, 'connection').status == 'active'


@pytest.mark.parametrize('field', ['identity', 'operation_id', 'receiver_state_ciphertext', 'enabled', 'audit_action'])
def test_corrupted_prepared_material_is_not_recertified_by_its_request_digest(source_world, field):
    factory, params = source_world
    service.prepare_source_registration(**params)
    with factory() as db:
        row = db.query(TenantSetting).one()
        material = json.loads(row.setting_value)
        if field == 'audit_action':
            db.query(AuditLog).one().action = 'different-action'
        else:
            material[field] = {'user_id': 'other'} if field == 'identity' else (True if field == 'enabled' else 'changed')
            row.setting_value = json.dumps(material)
        db.commit()
    with pytest.raises(service.SourceRegistrationError, match='SOURCE_REGISTRATION_UNVERIFIED'):
        service.prepare_source_registration(**params)
    with factory() as db:
        assert db.query(AuditLog).count() == 1
