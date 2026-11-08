"""Real mounted RPC + real actors; auth dependency injected, not login qualification."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def rpc(tmp_path,monkeypatch):
    import core.models
    from core.models_registration import Base
    from core.models import Tenant,Workspace,User
    from core.bpe import workspace,persistence
    from api.rpc_routes import router
    from core.auth import get_current_user
    from core.database import get_db
    monkeypatch.setattr(persistence,'DATA_DIR',tmp_path/'bpe')
    workspace.reset_registry()
    engine=create_engine('sqlite:///'+str(tmp_path/'actors.db'),connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def fks(connection,_):connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine);S=sessionmaker(bind=engine,expire_on_commit=False)
    with S() as s:
        s.add(Tenant(id='rpc-tenant',name='scratch',subdomain='rpc-scratch'));s.commit()
        for i in ['a','b']:
            s.add(Workspace(id='rpc-ws-'+i,name='scratch-'+i,tenant_id='rpc-tenant'))
        s.commit()
        for i in ['a','b']:
            s.add(User(id='rpc-user-'+i,email=i+'@rpc.example.invalid',first_name='Probe',last_name=i,role='member',status='active',is_active=True,tenant_id='rpc-tenant',workspace_id='rpc-ws-'+i))
        s.commit()
    actor={'id':'rpc-user-a'}
    def current():
        with S() as s:return s.get(User,actor['id'])
    def db():
        with S() as s:yield s
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_current_user]=current;app.dependency_overrides[get_db]=db
    with TestClient(app) as c:yield c,actor
    workspace.reset_registry();engine.dispose()

def test_same_actor_can_buffer_two_local_notes(rpc):
    c,actor=rpc
    one=c.post('/api/rpc/workspace.note',json={'params':{'content':'first owned note'}})
    two=c.post('/api/rpc/workspace.note',json={'params':{'content':'second owned note'}})
    assert one.status_code==two.status_code==200,(one.text,two.text)
    assert one.json()['data']['buffered']==1 and two.json()['data']['buffered']==2,(one.json(),two.json())

def test_different_current_workspace_cannot_append_peer_buffer(rpc):
    c,actor=rpc
    a=c.post('/api/rpc/workspace.note',json={'params':{'content':'workspace A private insight'}})
    assert a.status_code==200 and a.json().get('success') is True,a.text
    actor['id']='rpc-user-b'
    b=c.post('/api/rpc/workspace.note',json={'params':{'content':'workspace B private insight'}})
    assert b.status_code==200 and b.json().get('success') is True,b.text
    # An independent workspace's first accepted note must not see/append A's buffer.
    assert b.json()['data']['buffered']==1,b.json()
