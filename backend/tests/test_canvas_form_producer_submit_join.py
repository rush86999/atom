"""The ordinary form producer must create the scope that submit verifies."""
from __future__ import annotations
import asyncio
import contextlib
import pytest
from core.models import Canvas
from tests.test_canvas_lifecycle_verified import probe, app_client, broadcast_spy, _user  # noqa: F401


def _actor(app_client):
    with app_client.Session() as db:
        actor = _user(db, user_id='form-actor', tenant_id='form-tenant', workspace_id='form-workspace')
    app_client.users['current'] = actor
    return actor


def test_ordinary_present_form_then_submit_has_durable_scope(app_client, broadcast_spy, monkeypatch):
    from tools.canvas_tool import present_form
    actor = _actor(app_client)
    monkeypatch.setattr('tools.canvas_tool.FeatureFlags.should_enforce_governance', lambda *_: False)
    schema = {'fields': [{'name': 'quantity', 'type': 'number', 'default': 0}, {'name': 'approved', 'type': 'boolean', 'default': False}]}
    presented = asyncio.run(present_form(user_id=actor.id, form_schema=schema, title='Observed form'))
    assert presented['success'] is True, presented
    with app_client.Session() as db:
        canvas = db.get(Canvas, presented['canvas_id'])
        assert canvas is not None, 'The normal form producer returned an unverifiable canvas id'
        assert canvas.tenant_id == 'form-tenant'
        assert canvas.workspace_id == 'form-workspace'
        assert canvas.created_by == actor.id
        assert canvas.content['schema'] == schema
    assert broadcast_spy
    response = app_client.client.post('/api/canvas/submit', json={'canvas_id': presented['canvas_id'], 'form_data': {'quantity': 0, 'approved': False}, 'operation_id': 'form-answer-operation'})
    assert response.status_code == 200, response.text
    assert response.json()['verification']['status'] == 'verified'


def test_form_producer_does_not_broadcast_unpersisted_success(app_client, broadcast_spy, monkeypatch):
    from tools.canvas_tool import present_form
    actor = _actor(app_client)
    monkeypatch.setattr('tools.canvas_tool.FeatureFlags.should_enforce_governance', lambda *_: False)

    @contextlib.contextmanager
    def failing_session():
        with app_client.Session() as db:
            def fail_commit():
                raise RuntimeError('Controlled form persistence unavailable')
            monkeypatch.setattr(db, 'commit', fail_commit)
            yield db

    monkeypatch.setattr('core.database.get_db_session', failing_session)
    presented = asyncio.run(present_form(user_id=actor.id, form_schema={'fields': []}, title='Observed form'))
    assert presented['success'] is False, presented
    assert broadcast_spy == []


@pytest.mark.parametrize("missing", [
    "_oracle_expected_actor_id", "_oracle_expected_title",
    "_oracle_expected_material",
])
def test_form_missing_frozen_identity_never_broadcasts(app_client, broadcast_spy, monkeypatch, missing):
    from tools.canvas_tool import present_form
    from core.oracle import validate as actual_validate
    actor = _actor(app_client)
    monkeypatch.setattr('tools.canvas_tool.FeatureFlags.should_enforce_governance', lambda *_: False)

    async def without_frozen_binding(action, context):
        context = dict(context)
        context.pop(missing, None)
        return await actual_validate(action, context)

    monkeypatch.setattr('core.oracle.validate', without_frozen_binding)
    presented = asyncio.run(present_form(user_id=actor.id, form_schema={'fields': []}, title='Frozen title'))
    assert presented['success'] is False, 'An audit cannot supply its own missing authorization binding'
    assert presented['verification']['effect'] == 'committed'
    assert broadcast_spy == []
