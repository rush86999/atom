"""Direct submit is an event, not an ownership grant or unproved success."""
from __future__ import annotations
import contextlib
import pytest
from core.models import CanvasAudit
from tests.test_canvas_lifecycle_verified import probe, app_client, _user, _canvas  # noqa: F401


def _seed(app_client, *, shared=False, foreign=False):
    with app_client.Session() as db:
        actor = _user(db, user_id='submit-actor', tenant_id='submit-tenant', workspace_id='submit-workspace')
        owner = actor
        if shared or foreign:
            owner = _user(db, user_id='submit-owner', tenant_id='foreign-tenant' if foreign else 'submit-tenant', workspace_id='foreign-workspace' if foreign else 'submit-workspace')
        canvas = _canvas(db, canvas_id='submit-canvas', owner_id=owner.id, tenant_id=owner.tenant_id, workspace_id=owner.workspace_id, canvas_type='form', content={'fields': []})
    app_client.users['current'] = actor
    return canvas.id


def test_submit_commit_failure_is_not_success(app_client, monkeypatch):
    canvas_id = _seed(app_client)
    @contextlib.contextmanager
    def failing_session():
        with app_client.Session() as db:
            def fail_commit():
                raise RuntimeError('Controlled audit persistence unavailable')
            monkeypatch.setattr(db, 'commit', fail_commit)
            yield db
    monkeypatch.setattr('core.database.get_db_session', failing_session)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'quantity': 0}})
    assert response.status_code == 503, response.text
    assert response.json().get('success') is not True
    with app_client.Session() as db:
        assert db.query(CanvasAudit).filter_by(canvas_id=canvas_id, action_type='submit').count() == 0


def test_submit_success_requires_exact_durable_receipt(app_client):
    canvas_id = _seed(app_client)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'quantity': 0, 'approved': False}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['verification']['status'] == 'verified', body
    assert body['operation_id'], body
    assert body['audit_id'], body
    with app_client.Session() as db:
        audit = db.get(CanvasAudit, body['audit_id'])
        assert audit.canvas_id == canvas_id
        assert audit.user_id == 'submit-actor'
        assert audit.action_type == 'submit'
        assert audit.details_json['form_data'] == {'quantity': 0, 'approved': False}


def test_submit_foreign_scope_refuses_before_audit(app_client):
    canvas_id = _seed(app_client, foreign=True)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'observed': True}})
    assert response.status_code in (403, 404), response.text
    with app_client.Session() as db:
        assert db.query(CanvasAudit).filter_by(canvas_id=canvas_id, action_type='submit').count() == 0


def test_submit_same_scope_shared_form_remains_supported(app_client):
    canvas_id = _seed(app_client, shared=True)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'observed': True}})
    assert response.status_code == 200, response.text
    assert response.json()['success'] is True
    with app_client.Session() as db:
        rows = db.query(CanvasAudit).filter_by(canvas_id=canvas_id, action_type='submit').all()
        assert len(rows) == 1
        assert rows[0].user_id == 'submit-actor'


def test_submit_explicit_operation_replay_appends_once(app_client):
    canvas_id = _seed(app_client)
    payload = {'canvas_id': canvas_id, 'form_data': {'quantity': 0}, 'operation_id': 'submit-operation-001'}
    first = app_client.client.post('/api/canvas/submit', json=payload)
    second = app_client.client.post('/api/canvas/submit', json=payload)
    assert first.status_code == second.status_code == 200
    with app_client.Session() as db:
        rows = db.query(CanvasAudit).filter_by(canvas_id=canvas_id, action_type='submit').all()
        assert len(rows) == 1
    assert first.json()['audit_id'] == second.json()['audit_id']
    assert second.json()['operation_id'] == 'submit-operation-001'
    assert second.json()['already_applied'] is True


def test_submit_reused_operation_cannot_change_material(app_client):
    canvas_id = _seed(app_client)
    payload = {'canvas_id': canvas_id, 'form_data': {'quantity': 0}, 'operation_id': 'submit-operation-001'}
    first = app_client.client.post('/api/canvas/submit', json=payload)
    assert first.status_code == 200
    second = app_client.client.post('/api/canvas/submit', json={**payload, 'form_data': {'quantity': 1}})
    assert second.status_code == 409, second.text
    with app_client.Session() as db:
        rows = db.query(CanvasAudit).filter_by(canvas_id=canvas_id, action_type='submit').all()
        assert len(rows) == 1
        assert rows[0].details_json['form_data'] == {'quantity': 0}


def test_submit_stale_request_actor_cannot_bypass_deactivation(app_client):
    from core.models import User, UserStatus
    canvas_id = _seed(app_client)
    with app_client.Session() as db:
        db.query(User).filter(User.id == 'submit-actor').update({'status': UserStatus.SUSPENDED, 'is_active': False}, synchronize_session=False)
        db.commit()
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'observed': True}})
    assert response.status_code == 403, response.text
    with app_client.Session() as db:
        assert db.query(CanvasAudit).filter_by(canvas_id=canvas_id, action_type='submit').count() == 0


def test_submit_operation_namespace_preserves_opaque_components():
    from tools.canvas_crud_tool import deterministic_submit_audit_id
    left = deterministic_submit_audit_id('actor-001', 'canvas:segment', 'operation')
    right = deterministic_submit_audit_id('actor-001', 'canvas', 'segment:operation')
    assert left != right


def test_submit_distinct_canvas_and_operation_components_do_not_conflict(app_client):
    first_canvas = _seed(app_client)
    with app_client.Session() as db:
        second_canvas = _canvas(db, canvas_id='submit-canvas:segment', owner_id='submit-actor', tenant_id='submit-tenant', workspace_id='submit-workspace', canvas_type='form', content={'fields': []}).id
    first = app_client.client.post('/api/canvas/submit', json={'canvas_id': first_canvas, 'form_data': {'value': 0}, 'operation_id': 'segment:operation'})
    second = app_client.client.post('/api/canvas/submit', json={'canvas_id': second_canvas, 'form_data': {'value': 0}, 'operation_id': 'operation'})
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()['audit_id'] != second.json()['audit_id']


def test_submit_writer_cannot_rebind_frozen_request_operation(app_client, monkeypatch):
    import core.canvas_write_service as service
    canvas_id = _seed(app_client)
    real_writer = service.submit_canvas_event

    async def substitute_operation(*args, **kwargs):
        kwargs['operation_id'] = 'substituted-operation'
        return await real_writer(*args, **kwargs)

    monkeypatch.setattr(service, 'submit_canvas_event', substitute_operation)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'value': 0}, 'operation_id': 'requested-operation'})
    assert response.status_code == 503, response.text
    body = response.json()
    assert body['success'] is False
    assert body['operation_id'] == 'requested-operation'
    assert body['verification']['status'] != 'verified'
    assert body['verification']['replay'] == 'do_not_repeat'


def test_submit_raw_scope_move_after_commit_is_not_verified(app_client, monkeypatch):
    import core.canvas_write_service as service
    from core.models import Canvas
    from tests.test_canvas_lifecycle_verified import _workspace
    with app_client.Session() as db:
        actor = _user(db, user_id='submit-actor', tenant_id='submit-tenant', workspace_id=None)
        canvas_id = _canvas(db, canvas_id='submit-canvas', owner_id=actor.id, tenant_id='submit-tenant', workspace_id=None, canvas_type='form', content={'fields': []}).id
    app_client.users['current'] = actor
    real_writer = service.submit_canvas_event

    async def move_after_commit(*args, **kwargs):
        result = await real_writer(*args, **kwargs)
        with app_client.Session() as db:
            _workspace(db, '', 'submit-tenant')
            db.query(Canvas).filter(Canvas.id == canvas_id).update({'workspace_id': ''}, synchronize_session=False)
            db.commit()
        return result

    monkeypatch.setattr(service, 'submit_canvas_event', move_after_commit)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'value': 0}, 'operation_id': 'scope-operation'})
    assert response.status_code == 503, response.text
    body = response.json()
    assert body['status'] == 'committed_unverified'
    assert body['verification']['status'] != 'verified'
    assert body['verification']['effect'] == 'committed'
    with app_client.Session() as db:
        assert db.get(Canvas, canvas_id).workspace_id == ''


@pytest.mark.parametrize('missing_key', [
    '_oracle_expected_canvas_id', '_oracle_expected_operation_id',
    '_oracle_expected_material_sha256', '_oracle_expected_actor_id',
    '_oracle_expected_actor_tenant_id', '_oracle_expected_actor_workspace_id',
    '_oracle_expected_canvas_tenant_id', '_oracle_expected_canvas_workspace_id',
    '_oracle_expected_agent_id', '_oracle_expected_agent_execution_id',
])
def test_submit_missing_frozen_binding_never_certifies(app_client, monkeypatch, missing_key):
    import core.canvas_write_service as service
    canvas_id = _seed(app_client)
    real_validate = service.validate

    async def drop_frozen_field(action, context):
        context = dict(context)
        context.pop(missing_key, None)
        return await real_validate(action, context)

    monkeypatch.setattr(service, 'validate', drop_frozen_field)
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': canvas_id, 'form_data': {'value': 0}, 'operation_id': 'binding-operation'})
    assert response.status_code == 503, response.text
    assert response.json()['success'] is False
    assert response.json()['status'] == 'committed_unverified'
    assert response.json()['verification']['status'] != 'verified'
