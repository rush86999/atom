"""Real scoped connection metadata and durable reservations, no provider calls."""
import asyncio
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core import workflow_endpoints
from core.models import User, UserConnection
from core.workflow_event_intake import admit_verified_source_event
from core.workflow_event_admission import EventAdmissionError, EventPayloadConflict, EventScopeConflict
from tests.test_workflow_event_reservation import event_db


@pytest.fixture
def intake_world(event_db, monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workflow_event_reservations.db'}")
    with Session(engine) as db:
        db.add(User(id='owner', email='source-owner@example.invalid', first_name='Synthetic',
                    last_name='Owner', role='workspace_admin', status='active', is_active=True,
                    tenant_id='tenant', workspace_id='workspace'))
        db.add(UserConnection(id='connection', user_id='owner', tenant_id='tenant', workspace_id='workspace',
                              integration_id='synthetic-source', connection_name='Synthetic', credentials={}, status='active'))
        db.commit()
    workflow = {'id': 'workflow', 'created_by': 'owner', 'tenant_id': 'tenant', 'workspace_id': 'workspace',
                'event_binding_version': 1, 'enabled': True, 'nodes': [], 'connections': [],
                'event_subscriptions': [{'id': 'trigger', 'connection_id': 'connection',
                    'source': 'synthetic-source', 'event_type': 'record.updated', 'enabled': True}]}
    catalog = tmp_path / 'workflows.json'
    catalog.write_text(json.dumps([workflow]))
    monkeypatch.setattr(workflow_endpoints, 'WORKFLOWS_FILE', str(catalog))
    try:
        yield engine, catalog, workflow
    finally:
        engine.dispose()


def test_verified_intake_reserves_once_and_replays_original_after_disable(intake_world):
    engine, catalog, workflow = intake_world
    async def scenario():
        with Session(engine) as db:
            kwargs = dict(connection_id='connection', source='synthetic-source', event_type='record.updated',
                          provider_event_id='provider-event', payload={'resource_id': 'record', 'owner_id': 'forged'})
            first = await admit_verified_source_event(db, **kwargs)
            assert len(first) == 1 and first[0]['status'] == 'admitted'
            workflow['enabled'] = False
            workflow['event_subscriptions'] = []
            catalog.write_text(json.dumps([workflow]))
            retry = await admit_verified_source_event(db, **kwargs)
            assert retry == [dict(first[0], status='already_applied')]
            with pytest.raises(EventPayloadConflict):
                await admit_verified_source_event(db, **dict(kwargs, payload={'different': True}))
            from core.execution_state_manager import get_state_manager, EXECUTION_SCOPE_KEY
            state = await get_state_manager().get_execution_state(first[0]['execution_id'])
            assert state['input_data'][EXECUTION_SCOPE_KEY]['user_id'] == 'owner'
            assert state['input_data']['event']['owner_id'] == 'owner'
            db.add(User(id='new-owner', email='new-owner@example.invalid', first_name='Synthetic',
                        last_name='Owner', role='workspace_admin', status='active', is_active=True,
                        tenant_id='tenant', workspace_id='workspace'))
            db.get(UserConnection, 'connection').user_id = 'new-owner'
            db.commit()
            workflow['created_by'] = 'new-owner'
            catalog.write_text(json.dumps([workflow]))
            with pytest.raises(EventScopeConflict):
                await admit_verified_source_event(db, **kwargs)
    asyncio.run(scenario())


@pytest.mark.parametrize('case', ['foreign_workflow_owner', 'foreign_workflow_scope', 'disabled', 'legacy', 'wrong_event'])
def test_unmatched_intake_does_not_reserve(intake_world, case):
    engine, catalog, workflow = intake_world
    if case == 'foreign_workflow_owner': workflow['created_by'] = 'other'
    elif case == 'foreign_workflow_scope': workflow['workspace_id'] = 'other'
    elif case == 'disabled': workflow['enabled'] = False
    elif case == 'legacy': workflow.pop('event_binding_version')
    else: workflow['event_subscriptions'][0]['event_type'] = 'other.event'
    catalog.write_text(json.dumps([workflow]))
    with Session(engine) as db:
        assert asyncio.run(admit_verified_source_event(db, connection_id='connection', source='synthetic-source',
            event_type='record.updated', provider_event_id='provider-event', payload={})) == []


@pytest.mark.parametrize('case', ['revoked', 'owner_disabled', 'owner_moved', 'missing_event_id'])
def test_unavailable_source_refuses_before_reservation(intake_world, case):
    engine, catalog, workflow = intake_world
    with Session(engine) as db:
        if case == 'revoked': db.get(UserConnection, 'connection').status = 'revoked'
        elif case == 'owner_disabled': db.get(User, 'owner').is_active = False
        elif case == 'owner_moved': db.get(User, 'owner').workspace_id = 'other'
        db.commit()
        with pytest.raises(EventAdmissionError):
            asyncio.run(admit_verified_source_event(db, connection_id='connection', source='synthetic-source',
                event_type='record.updated', provider_event_id='' if case == 'missing_event_id' else 'provider-event', payload={}))
