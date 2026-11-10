import pytest,json
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base,get_db
from core.auth import create_access_token
from core.models import User,Tenant,Workspace,AgentRegistry
from api.agent_onboarding_routes import router

@pytest.fixture
def world(tmp_path):
 engine=create_engine('sqlite:///'+str(tmp_path/'scope.db'),connect_args={'check_same_thread':False});Base.metadata.create_all(engine);Session=sessionmaker(bind=engine,expire_on_commit=False)
 with Session() as db:
  db.add_all([Tenant(id='rt-a',name='A',subdomain='root-a'),Tenant(id='rt-b',name='B',subdomain='root-b')]);db.flush()
  db.add_all([Workspace(id='rw-a',tenant_id='rt-a',name='A'),Workspace(id='rw-b',tenant_id='rt-a',name='B'),Workspace(id='rw-c',tenant_id='rt-b',name='C')]);db.flush()
  db.add(User(id='root-reader',email='reader@example.test',tenant_id='rt-a',workspace_id='rw-a',first_name='Root',last_name='Reader',role='member',status='active',is_active=True));db.flush()
  for aid,t,w,name in [('ra-own','rt-a','rw-a','Own student'),('ra-peer','rt-a','rw-b','Private peer'),('ra-foreign','rt-b','rw-c','Private foreign')]:
   db.add(AgentRegistry(id=aid,name=name,category='operations',module_path='agents.test',class_name='TestAgent',tenant_id=t,workspace_id=w,status='student',confidence_score=.41,enabled=True,configuration={'learning':{'log':[{'source':'teacher','lesson':'private teaching'}]}}))
  db.commit();user=db.query(User).filter(User.id=='root-reader').one();token=create_access_token({'sub':user.id},user=user)
 app=FastAPI();app.include_router(router)
 def session():
  with Session()as db:yield db
 app.dependency_overrides[get_db]=session
 yield SimpleNamespace(Session=Session,client=TestClient(app,raise_server_exceptions=False),token=token)
 engine.dispose()

@pytest.mark.parametrize('agent,expected',[('ra-own',200),('ra-peer',404),('ra-foreign',404)])
def test_guide_honors_actual_reader_scope(world,agent,expected):
 response=world.client.get('/api/agents/'+agent+'/maturity-guide',headers={'Authorization':'Bearer '+world.token})
 assert response.status_code==expected,response.text
 if expected==200:assert response.json()['data']['agent_name']=='Own student'
 else:assert 'private teaching' not in response.text and 'confidence' not in response.text

def test_token_from_old_workspace_cannot_read_after_authority_moves(world):
 with world.Session()as db:
  db.query(User).filter(User.id=='root-reader').update({'workspace_id':'rw-b'},synchronize_session=False);db.commit()
 response=world.client.get('/api/agents/ra-own/maturity-guide',headers={'Authorization':'Bearer '+world.token})
 assert response.status_code in (401,403,404),response.text
 assert 'private teaching' not in response.text
