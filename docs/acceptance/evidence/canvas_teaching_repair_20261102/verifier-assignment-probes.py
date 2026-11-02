from __future__ import annotations
import asyncio
import json
import uuid
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from core.assignment_executor import AssignmentExecutor
from core.auth import get_current_user
from core.canvas_capability_service import bind_dataset, current_revision, edit_operation, get_manifest, set_manifest
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.models import AgentRegistry, Canvas, HITLAction, HITLActionStatus, User
from core.task_lifecycle import TaskLifecycle

@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('TESTING', '1')
    monkeypatch.setenv('ATOM_ASSIGNMENT_OUTBOX', str(tmp_path / 'outbox.jsonl'))
    monkeypatch.setenv('ATOM_OFFICE_DIR', str(tmp_path))
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    user = User(id='canvas-user', email='canvas@example.invalid', hashed_password='x', first_name='C', last_name='U', role='workspace_admin', status='active', workspace_id='ws-canvas', tenant_id='tenant-canvas', is_active=True)
    db.add(user)
    agent = AgentRegistry(id='canvas-agent', name='Canvas Employee', category='operations', module_path='core.generic_agent', class_name='GenericAgent', status='intern', confidence_score=0.5, configuration={}, capabilities=[], workspace_id='ws-canvas', tenant_id='tenant-canvas')
    db.add(agent)
    db.commit()
    monkeypatch.setattr('core.database.get_db_session', factory)

    async def fake_request_intervention(**kwargs):
        action = HITLAction(id=f'hitl-{uuid.uuid4().hex[:8]}', workspace_id=kwargs.get('workspace_id'), tenant_id=kwargs.get('tenant_id'), action_type=kwargs.get('action_type'), platform=kwargs.get('platform'), params=kwargs.get('params') or {}, reason=kwargs.get('reason'), status=HITLActionStatus.PENDING.value, user_id=kwargs.get('user_id'))
        db.add(action)
        db.commit()
        db.refresh(action)
        return {'status': 'PAUSED', 'action_id': action.id}
    monkeypatch.setattr('core.intervention_service.intervention_service.request_intervention', fake_request_intervention)
    drafts = []

    class FakeOutlook:

        async def _get_access_token(self, user_id):
            return 'controlled-token'

        async def create_draft_email(self, **kwargs):
            drafts.append(dict(kwargs))
            return {'id': f'draft-{len(drafts)}', 'subject': kwargs.get('subject'), 'body': kwargs.get('body'), 'to': kwargs.get('to_recipients')}
    monkeypatch.setattr('integrations.outlook_service.OutlookService', lambda *args, **kwargs: FakeOutlook())
    import core.connected_actions
    from api.canvas_capability_routes import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_pilot_user] = lambda: user
    client = TestClient(app)
    try:
        yield {'db': db, 'factory': factory, 'user': user, 'client': client, 'drafts': drafts, 'agent_id': agent.id}
    finally:
        db.close()
        engine.dispose()

def _manifest(actions=True):
    manifest = {'schema_version': 2, 'base_component': 'table', 'operations': ['read', 'derive', 'edit', 'bind'], 'data_binding': {'subject_field': 'Item'}, 'teaching_binding': {'agent_id': 'canvas-agent', 'scope_id': 'canvas-task'}, 'fields': [{'id': 'item_id', 'label': 'Item', 'type': 'string', 'column': 'Item', 'required': True}, {'id': 'quantity', 'label': 'Quantity', 'type': 'decimal', 'column': 'Qty', 'unit': 'each', 'required': True, 'editable': True}, {'id': 'unit_price', 'label': 'Unit price', 'type': 'currency', 'column': 'Price', 'currency': 'USD', 'required': True, 'editable': True}, {'id': 'line_total', 'label': 'Line total', 'type': 'currency', 'column': 'Line Total', 'currency': 'USD', 'derived': 'quantity * unit_price', 'aggregate': 'sum', 'group_by': 'item_id'}], 'outputs': ['xlsx']}
    if actions:
        manifest['actions'] = [{'id': 'notify', 'operation': 'connected.outlook.create_draft', 'allowed_fields': ['item_id', 'quantity', 'unit_price', 'line_total'], 'target': 'buyer@example.invalid', 'authority': 'grant-canvas-draft-1', 'arguments': {'to': ['buyer@example.invalid'], 'subject': 'Canvas quote ${objective}', 'body': 'Total ${total} ${currency} (${row_count} rows)', 'authority_reference': 'grant-canvas-draft-1', 'operation_id': 'canvas-${receipt_digest}'}}]
    return manifest

def _canvas(env, *, canvas_id='canvas_assignment', actions=True):
    db = env['db']
    canvas = Canvas(id=canvas_id, tenant_id=env['user'].tenant_id, workspace_id=env['user'].workspace_id, created_by=env['user'].id, name='Assignment canvas', canvas_type='table', content={}, status='active')
    db.add(canvas)
    db.commit()
    set_manifest(db, canvas, env['user'], _manifest(actions=actions))
    bound = bind_dataset(db, canvas, env['user'], ['Item', 'Qty', 'Price'], [['A', '2', '100.00'], ['B', '3', '50.00']], source={'file_name': 'canvas-assignment.csv'})
    return (canvas, bound)

def _assign(env, canvas, bound):
    response = env['client'].post(f'/api/canvas/{canvas.id}/capability/assign', json={'objective': 'Quote assignment', 'agent_id': env['agent_id'], 'expected_revision': bound['revision'], 'manifest_revision': bound['manifest']['manifest_revision'], 'source_version': bound['source']['source_version'], 'action_ids': ['notify']})
    assert response.status_code == 200, response.text
    return response.json()

def _executor(env):
    runs = GoalRunService(workspace_id=env['user'].workspace_id, tenant_id=env['user'].tenant_id, session_factory=env['factory'])
    goals = GoalService(workspace_id=env['user'].workspace_id, tenant_id=env['user'].tenant_id, session_factory=env['factory'])
    return AssignmentExecutor(TaskLifecycle(runs, goals))

def _step(assignment, step_id):
    data = assignment.get('assignment') if isinstance(assignment, dict) and isinstance(assignment.get('assignment'), dict) else assignment
    return next((item for item in data['steps'] if item['step_id'] == step_id))

def _proposal(env,canvas,bound,agent_id=None):
    return env['client'].post(f'/api/canvas/{canvas.id}/capability/teaching/propose',json={'lesson':'Verifier source-bound rule','topic':'verification','agent_id':agent_id or env['agent_id'],'expected_revision':bound['revision'],'manifest_revision':bound['manifest']['manifest_revision'],'source_version':bound['source']['source_version']})

def _promotion(env,canvas,proposal_id):
    from core.canvas_capability_service import get_dataset
    return env['client'].post(f'/api/canvas/{canvas.id}/capability/teaching/{proposal_id}/promote',json={'approved':True,'expected_revision':current_revision(canvas),'manifest_revision':get_manifest(canvas)['manifest_revision'],'source_version':get_dataset(canvas)['source']['source_version']})

def test_stale_teaching_proposal_cannot_use_new_revision(env):
    canvas,bound=_canvas(env,actions=False)
    p=_proposal(env,canvas,bound).json()['proposal']
    edit_operation(env['db'],canvas,env['user'],[{'row':2,'column':'Qty','value':'5'}],expected_revision=bound['revision'])
    response=_promotion(env,canvas,p['id'])
    assert response.status_code==409,response.text

def test_foreign_employee_cannot_receive_canvas_teaching(env):
    from core.student_learning_service import list_agent_lessons
    foreign=AgentRegistry(id='foreign-agent',name='Foreign',category='operations',module_path='core.generic_agent',class_name='GenericAgent',status='intern',confidence_score=.5,configuration={},capabilities=[],workspace_id='foreign-ws',tenant_id='foreign-tenant')
    env['db'].add(foreign);env['db'].commit()
    canvas,bound=_canvas(env,actions=False)
    p=_proposal(env,canvas,bound,agent_id='foreign-agent')
    if p.status_code in (403,404):return
    promoted=_promotion(env,canvas,p.json()['proposal']['id'])
    assert promoted.status_code in (403,404),promoted.text

def test_promotion_cas_failure_leaves_journal_unchanged(env,monkeypatch):
    from core import canvas_capability_service as service
    from core.student_learning_service import list_agent_lessons
    canvas,bound=_canvas(env,actions=False)
    p=_proposal(env,canvas,bound).json()['proposal']
    original=service._commit_canvas_content_cas
    triggered=[]
    def race(db,c,content,**kwargs):
        if not triggered:
            triggered.append(True)
            writer=env['factory']()
            other=writer.query(Canvas).filter(Canvas.id==canvas.id).one()
            bind_dataset(writer,other,env['user'],['Item','Qty','Price'],[['B','2','1000']],source={'file_name':'b.csv'})
            writer.close()
        return original(db,c,content,**kwargs)
    monkeypatch.setattr(service,'_commit_canvas_content_cas',race)
    response=_promotion(env,canvas,p['id'])
    assert response.status_code==409,response.text
    env['db'].expire_all()
    lessons=list_agent_lessons(env['db'],env['agent_id'])
    assert not any('Verifier source-bound rule' in json.dumps(x) for x in lessons),json.dumps(lessons)

def test_promoted_global_lesson_is_available_to_ordinary_work(env):
    from core.student_learning_service import get_agent_lessons
    canvas,bound=_canvas(env,actions=False)
    p=_proposal(env,canvas,bound).json()['proposal']
    response=_promotion(env,canvas,p['id'])
    assert response.status_code==200,response.text
    lessons=get_agent_lessons(env['db'],env['agent_id'],workspace_id=env['user'].workspace_id,task_context={})
    assert any('Verifier source-bound rule' in json.dumps(x) for x in lessons),json.dumps(lessons)
