"""Ordinary web Tasks/Projects boundary, isolated SQLite and real public router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from core.database import Base, get_db
from core.auth import get_current_user
from core.models import Tenant, User, Workspace
from api.nav_stub_routes import router
import service_delivery.models

@pytest.fixture
def world():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Tenant(id='web-tenant', name='Web tenant', subdomain='web-test', plan_type='free', edition='personal'))
        db.add(Workspace(id='web-workspace', name='Web workspace', tenant_id='web-tenant'))
        db.add(User(id='web-owner', email='web-owner@example.invalid', hashed_password='controlled', first_name='Web', last_name='Owner', role='member', status='active', is_active=True, tenant_id='web-tenant', workspace_id='web-workspace'))
        db.commit()
    def database():
        with sessions() as db:
            yield db
    def actor():
        with sessions() as db:
            return db.get(User, 'web-owner')
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = actor
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, sessions
    engine.dispose()

def test_project_create_edit_reload_uses_existing_durable_project(world):
    client, sessions = world
    created = client.post('/api/v1/projects', json={'name': 'Ordinary project', 'description': 'Reviewed work', 'color': '#123456'})
    assert created.status_code in (200, 201), created.text
    project = created.json()['project']
    assert project['name'] == 'Ordinary project'
    assert project['color'] == '#123456'
    assert client.put(f"/api/v1/projects/{project['id']}", json={'name': 'Revised project'}).status_code == 200
    rows = client.get('/api/v1/projects').json()['projects']
    assert [(p['id'], p['name']) for p in rows] == [(project['id'], 'Revised project')]
    with sessions() as db:
        from service_delivery.models import Project
        assert db.get(Project, project['id']).name == 'Revised project'

def test_task_rejects_foreign_or_unknown_project_reference(world):
    client, _ = world
    response = client.post('/api/v1/tasks', json={'title': 'Cannot bind foreign project', 'project': 'not-authorized-project'})
    assert response.status_code in (404, 422), response.text
    assert client.get('/api/v1/tasks').json()['tasks'] == []

def test_foreign_workspace_project_is_neither_listed_nor_editable(world):
    client, sessions = world
    with sessions() as db:
        from service_delivery.models import Project
        db.add(Workspace(id='other-web-workspace', name='Other workspace', tenant_id='web-tenant'))
        db.add(Project(id='foreign-project', name='Peer original', workspace_id='other-web-workspace'))
        db.commit()
    assert all(row['id'] != 'foreign-project' for row in client.get('/api/v1/projects').json()['projects'])
    result = client.put('/api/v1/projects/foreign-project', json={'name': 'Unauthorized change'})
    assert result.status_code == 404, result.text
    with sessions() as db:
        from service_delivery.models import Project
        assert db.get(Project, 'foreign-project').name == 'Peer original'

def test_anonymous_backend_task_and_project_access_is_refused(world):
    client, _ = world
    client.app.dependency_overrides.pop(get_current_user)
    for route in ['/api/v1/tasks', '/api/v1/projects']:
        assert client.get(route).status_code == 401

def test_project_identity_and_workspace_come_from_server_not_body(world):
    client, sessions = world
    response = client.post('/api/v1/projects', json={'name': 'Server-owned', 'id': 'forged-id', 'workspace_id': 'forged-workspace', 'tenant_id': 'forged-tenant', 'metadata': {'privileged': True}})
    assert response.status_code in (200, 201), response.text
    row = response.json()['project']
    assert row['id'] != 'forged-id'
    with sessions() as db:
        from service_delivery.models import Project
        stored = db.get(Project, row['id'])
        assert stored.workspace_id == 'web-workspace'
        assert not (stored.metadata_json or {}).get('privileged')

def test_project_edit_preserves_existing_financial_status_and_metadata(world):
    client, sessions = world
    with sessions() as db:
        from service_delivery.models import Project, ProjectStatus
        db.add(Project(id='preserved-project', workspace_id='web-workspace', name='Existing', status=ProjectStatus.ACTIVE, budget_amount=123.5, metadata_json={'color': '#000000', 'retained': 'existing data'}))
        db.commit()
    response = client.put('/api/v1/projects/preserved-project', json={'color': '#abcdef', 'budget_amount': 0, 'status': 'completed', 'metadata': {'retained': 'overwritten'}})
    assert response.status_code == 200, response.text
    with sessions() as db:
        from service_delivery.models import Project, ProjectStatus
        stored = db.get(Project, 'preserved-project')
        assert stored.budget_amount == 123.5
        assert stored.status == ProjectStatus.ACTIVE
        assert stored.metadata_json == {'color': '#abcdef', 'retained': 'existing data'}

def test_task_links_real_project_and_can_explicitly_unlink(world):
    client, _ = world
    project = client.post('/api/v1/projects', json={'name': 'Linked project'}).json()['project']
    response = client.post('/api/v1/tasks', json={'title': 'Linked task', 'project': project['id']})
    assert response.status_code == 200, response.text
    task = response.json()['task']; assert task['project'] == project['id']
    assert client.put(f"/api/v1/tasks/{task['id']}", json={'project': None}).json()['task']['project'] is None

@pytest.mark.parametrize('payload', [{'name': ''}, {'name': True}, {'name': 'Valid', 'color': 'url(unsafe)'}, {'name': 'Valid', 'description': []}])
def test_invalid_project_material_has_no_created_row(world, payload):
    client, _ = world
    assert client.post('/api/v1/projects', json=payload).status_code == 422
    assert client.get('/api/v1/projects').json()['projects'] == []

def test_database_failure_is_not_an_empty_success_or_raw_error(world, caplog):
    client, _ = world
    class BrokenDatabase:
        def query(self, *args, **kwargs): raise RuntimeError('controlled-sensitive-parameter')
        def rollback(self): pass
    client.app.dependency_overrides[get_db] = BrokenDatabase
    for route in ['/api/v1/tasks', '/api/v1/projects']:
        result = client.get(route)
        assert result.status_code == 500
        assert 'controlled-sensitive-parameter' not in result.text
    assert 'controlled-sensitive-parameter' not in caplog.text

@pytest.mark.parametrize('workspace', [None, 'default'])
def test_real_tenant_cannot_borrow_another_tenants_default_workspace(world, workspace):
    client, sessions = world
    with sessions() as db:
        from service_delivery.models import Project
        db.add(Tenant(id='default', name='Other default tenant', subdomain='other-default', plan_type='free', edition='personal'))
        db.add(Workspace(id='default', name='Other default workspace', tenant_id='default'))
        db.add(Project(id='default-private-project', workspace_id='default', name='Other tenant private project'))
        actor = db.get(User, 'web-owner'); actor.workspace_id = workspace
        db.commit()
    listed = client.get('/api/v1/projects')
    assert listed.status_code in (403, 404), listed.text
    assert 'Other tenant private project' not in listed.text

def test_missing_workspace_cannot_create_inside_foreign_default_tenant(world):
    client, sessions = world
    with sessions() as db:
        db.add(Tenant(id='default', name='Other tenant', subdomain='default-other', plan_type='free', edition='personal'))
        db.add(Workspace(id='default', name='Other workspace', tenant_id='default'))
        db.get(User, 'web-owner').workspace_id = None
        db.commit()
    response = client.post('/api/v1/projects', json={'name': 'Must not appear'})
    assert response.status_code in (403, 404), response.text
    with sessions() as db:
        from service_delivery.models import Project
        assert db.query(Project).count() == 0

@pytest.mark.parametrize('target_tenant', ['default', None])
def test_legacy_personal_null_scopes_still_resolve_to_matching_default(world, target_tenant):
    client, sessions = world
    with sessions() as db:
        db.add(Tenant(id='default', name='Personal default', subdomain='personal-default', plan_type='free', edition='personal'))
        db.add(Workspace(id='default', name='Personal workspace', tenant_id=target_tenant))
        actor = db.get(User, 'web-owner'); actor.tenant_id = None; actor.workspace_id = None
        db.commit()
    created = client.post('/api/v1/projects', json={'name': 'Legitimate personal project'})
    assert created.status_code in (200, 201), created.text
    assert [row['id'] for row in client.get('/api/v1/projects').json()['projects']] == [created.json()['project']['id']]

@pytest.mark.parametrize('operation', ['project_update', 'task_create', 'task_update'])
def test_inconsistent_workspace_scope_cannot_mutate_or_link_foreign_project(world, operation):
    client, sessions = world
    own_task = client.post('/api/v1/tasks', json={'title': 'Retained own task'}).json()['task']
    with sessions() as db:
        from service_delivery.models import Project
        db.add(Tenant(id='default', name='Foreign tenant', subdomain='foreign-default', plan_type='free', edition='personal'))
        db.add(Workspace(id='default', name='Foreign workspace', tenant_id='default'))
        db.add(Project(id='foreign-default-project', workspace_id='default', name='Retained peer project'))
        db.get(User, 'web-owner').workspace_id = None
        db.commit()
    if operation == 'project_update':
        response = client.put('/api/v1/projects/foreign-default-project', json={'name': 'Must not apply'})
    elif operation == 'task_create':
        response = client.post('/api/v1/tasks', json={'title': 'Must not create', 'project': 'foreign-default-project'})
    else:
        response = client.put(f"/api/v1/tasks/{own_task['id']}", json={'project': 'foreign-default-project'})
    assert response.status_code == 404, response.text
    with sessions() as db:
        from service_delivery.models import Project
        from core.models import UserTask
        assert db.get(Project, 'foreign-default-project').name == 'Retained peer project'
        assert db.query(UserTask).count() == 1
        assert db.get(UserTask, own_task['id']).project_id is None
