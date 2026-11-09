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


def _form_agent(app_client, workspace='form-workspace'):
    from core.models import AgentRegistry
    with app_client.Session() as db:
        agent = AgentRegistry(id='form-agent', name='Form Agent', category='test', module_path='test.module', class_name='Agent', status='autonomous', enabled=True, workspace_id=workspace, tenant_id='form-tenant')
        db.add(agent)
        db.commit()
    return 'form-agent'


def test_form_governance_uses_current_actor_scope(app_client, broadcast_spy, monkeypatch):
    from tools.canvas_tool import present_form
    from core.agent_governance_service import AgentGovernanceService
    actor = _actor(app_client)
    agent_id = _form_agent(app_client)
    monkeypatch.setattr('tools.canvas_tool.FeatureFlags.should_enforce_governance', lambda *_: True)
    scopes = []
    def allowed(service, **kwargs):
        scopes.append((service.tenant_id, service.workspace_id))
        return {'allowed': True, 'requires_human_approval': False}
    monkeypatch.setattr(AgentGovernanceService, 'can_perform_action', allowed)
    result = asyncio.run(present_form(user_id=actor.id, form_schema={'fields': []}, agent_id=agent_id))
    assert result['success'] is True, result
    assert scopes and all(scope == ('form-tenant', 'form-workspace') for scope in scopes)


def test_form_foreign_agent_is_not_presentation_authority(app_client, broadcast_spy, monkeypatch):
    from tools.canvas_tool import present_form
    from core.agent_governance_service import AgentGovernanceService
    from tests.test_canvas_lifecycle_verified import _workspace
    actor = _actor(app_client)
    with app_client.Session() as db:
        _workspace(db, 'foreign-form-workspace', 'form-tenant')
    agent_id = _form_agent(app_client, workspace='foreign-form-workspace')
    monkeypatch.setattr('tools.canvas_tool.FeatureFlags.should_enforce_governance', lambda *_: True)
    monkeypatch.setattr(AgentGovernanceService, 'can_perform_action', lambda *args, **kwargs: {'allowed': True, 'requires_human_approval': False})
    result = asyncio.run(present_form(user_id=actor.id, form_schema={'fields': []}, agent_id=agent_id))
    assert result['success'] is False, result
    assert broadcast_spy == []
    with app_client.Session() as db:
        assert db.query(Canvas).count() == 0


def test_form_lost_commit_confirmation_preserves_identity(app_client, broadcast_spy, monkeypatch):
    from tools.canvas_tool import present_form
    actor = _actor(app_client)
    monkeypatch.setattr('tools.canvas_tool.FeatureFlags.should_enforce_governance', lambda *_: False)
    @contextlib.contextmanager
    def lost_confirmation():
        with app_client.Session() as db:
            actual_commit = db.commit
            def commit_then_lose():
                actual_commit()
                raise RuntimeError('Controlled confirmation loss')
            monkeypatch.setattr(db, 'commit', commit_then_lose)
            yield db
    monkeypatch.setattr('core.database.get_db_session', lost_confirmation)
    result = asyncio.run(present_form(user_id=actor.id, form_schema={'fields': []}))
    assert result['success'] is False
    assert result['status'] == 'effect_unknown'
    assert result['canvas_id'] and result['audit_id'] and result['operation_id']
    assert result['verification']['effect'] == 'unknown'
    assert result['verification']['replay'] == 'do_not_repeat'
    assert broadcast_spy == []
    with app_client.Session() as db:
        assert db.get(Canvas, result['canvas_id']) is not None
