"""Direct submit is an event, not an ownership grant or unproved success."""
from __future__ import annotations
import contextlib
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
