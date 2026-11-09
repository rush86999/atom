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
