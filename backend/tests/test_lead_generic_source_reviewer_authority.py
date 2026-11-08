"""A source answer must not overwrite a changed durable wait snapshot."""
import pytest
import core.models
from core.models import HITLAction
from core.models_board import BoardTask
from core.react_models import InformationWaitRequest, ReActStep, ToolCall
from tests.test_generic_source_answer_contract import _source_fixture
from tests.test_agent_generic_information_wait import _install_model, _seed_board
from tests.test_agent_run_outcome_join_contract import real_env, _run, _client


@pytest.mark.parametrize(
    "change",
    ["unchanged", "demoted", "disabled", "moved", "tenant", "deleted"],
)
def test_proxy_reviewer_authority_at_claim(real_env,tmp_path,monkeypatch,change):
    import api.agent_routes as routes
    from core.models import User
    with real_env.SessionLocal() as db:
        actor=db.get(User,'admin-2');actor.tenant_id='t1';actor.workspace_id='ws1';db.commit()
        db.refresh(actor);db.expunge(actor);real_env.actors['admin-2']=actor
    board,column=_seed_board(real_env)
    doc,version=_source_fixture(real_env,tmp_path,monkeypatch)
    observed=[]
    def wait(task_input,history,context):
        observed.append('wait')
        return ReActStep(thought='Need authorized evidence.',information_wait=InformationWaitRequest(question='Which source?',missing_fact='source'))
    def resumed(task_input,history,context):
        observed.append('resumed')
        return ReActStep(thought='Use accepted fact.',action=ToolCall(tool='tasks.create',params={'board_id':board,'column_id':column,'title':'Peer snapshot task','status':'backlog'}))
    def final(task_input,history,context):
        return ReActStep(thought='Verified.',final_answer='Created.')
    _install_model(monkeypatch,[wait,resumed,final])
    initial=_run(real_env,operation_id='lead-source-snapshot-cas',parameters={'sync':True,'task_input':'Create a task when source arrives.'})
    assert initial.status_code==202,initial.text
    data=initial.json()['data'];original=routes._load_generic_source_payload;armed=[True];changed=[]
    async def peer_changes_after_source_read(*args,**kwargs):
        result=await original(*args,**kwargs)
        if armed[0]:
            armed[0]=False
            with real_env.SessionLocal() as db:
                actor=db.get(User,'admin-2')
                if change=='demoted': actor.role='member'
                elif change=='disabled': actor.is_active=False;actor.status='disabled'
                elif change=='moved': actor.workspace_id='ws2'
                elif change=='tenant': actor.tenant_id='t2'
                elif change=='deleted': db.delete(actor)
                db.commit()
        return result
    monkeypatch.setattr(routes,'_load_generic_source_payload',peer_changes_after_source_read)
    result=_client(real_env,'admin-2').post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json={'answer':'source supplied','correlation_id':data['wait_receipt']['correlation_id'],'source':{'document_id':doc.id,'source_version':version}})
    if change=='unchanged':
        assert result.status_code==200,(result.status_code,result.text,observed)
        assert observed==['wait','resumed']
    else:
        assert result.status_code in (403,404,409),(change,result.status_code,result.text,observed)
        assert observed==['wait'],observed
        with real_env.SessionLocal() as db:
            assert db.query(BoardTask).filter(BoardTask.title=='Peer snapshot task').count()==0
            assert db.query(HITLAction).filter(HITLAction.status=='pending').count()==1

def test_approved_source_replay_rechecks_current_reviewer(
        real_env,tmp_path,monkeypatch):
    """A demoted proxy cannot replay an already approved source answer."""
    import api.agent_routes as routes
    from core.models import User
    with real_env.SessionLocal() as db:
        actor=db.get(User,'admin-2');actor.tenant_id='t1';actor.workspace_id='ws1';db.commit()
        db.refresh(actor);db.expunge(actor);real_env.actors['admin-2']=actor
    board,column=_seed_board(real_env)
    doc,version=_source_fixture(real_env,tmp_path,monkeypatch)
    observed=[]
    def wait(task_input,history,context):
        observed.append('wait')
        return ReActStep(thought='Need authorized evidence.',information_wait=InformationWaitRequest(question='Which source?',missing_fact='source'))
    def resumed(task_input,history,context):
        observed.append('resumed')
        return ReActStep(thought='Use accepted fact.',action=ToolCall(tool='tasks.create',params={'board_id':board,'column_id':column,'title':'Reviewer replay task','status':'backlog'}))
    def final(task_input,history,context):
        observed.append('final')
        return ReActStep(thought='Verified.',final_answer='Created.')
    _install_model(monkeypatch,[wait,resumed,final])
    initial=_run(real_env,operation_id='lead-source-reviewer-replay',parameters={'sync':True,'task_input':'Create a task when source arrives.'})
    assert initial.status_code==202,initial.text
    data=initial.json()['data']
    body={'answer':'source supplied','correlation_id':data['wait_receipt']['correlation_id'],'source':{'document_id':doc.id,'source_version':version}}
    first=_client(real_env,'admin-2').post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json=body)
    assert first.status_code==200,first.text
    assert observed==['wait','resumed','final'],observed
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(BoardTask.title=='Reviewer replay task').count()==1
    original=routes._load_generic_source_payload; armed=[True]
    async def demote_after_read(*args,**kwargs):
        result=await original(*args,**kwargs)
        if armed[0]:
            armed[0]=False
            with real_env.SessionLocal() as db:
                actor=db.get(User,'admin-2');actor.role='member';db.commit()
        return result
    monkeypatch.setattr(routes,'_load_generic_source_payload',demote_after_read)
    replay=_client(real_env,'admin-2').post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json=body)
    assert replay.status_code in (403,404,409),(replay.status_code,replay.text,observed)
    assert observed==['wait','resumed','final'],observed
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(BoardTask.title=='Reviewer replay task').count()==1
