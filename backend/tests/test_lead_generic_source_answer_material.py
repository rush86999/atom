"""A replay may not replace accepted text while retaining the same source."""
import core.models  # register the shared model graph before models_board
from core.models_board import BoardTask
from core.react_models import InformationWaitRequest, ReActStep, ToolCall
from tests.test_generic_source_answer_contract import _source_fixture
from tests.test_agent_generic_information_wait import _install_model, _seed_board
from tests.test_agent_run_outcome_join_contract import real_env, _run, _client


def test_same_source_different_accepted_answer_cannot_resume(real_env,tmp_path,monkeypatch):
    import api.agent_routes as routes
    board,column=_seed_board(real_env)
    doc,version=_source_fixture(real_env,tmp_path,monkeypatch)
    observed=[]
    def wait(task_input,history,context):
        observed.append('wait')
        return ReActStep(thought='Need authorized evidence.',information_wait=InformationWaitRequest(question='Which source and priority?',missing_fact='source and priority'))
    def resumed(task_input,history,context):
        observed.append(context.get('information_answer'))
        return ReActStep(thought='Use accepted fact.',action=ToolCall(tool='tasks.create',params={'board_id':board,'column_id':column,'title':'Accepted answer '+str(context.get('information_answer')),'status':'backlog'}))
    def final(task_input,history,context):
        return ReActStep(thought='Verified.',final_answer='Created.')
    _install_model(monkeypatch,[wait,resumed,final])
    initial=_run(real_env,operation_id='lead-source-answer-material',parameters={'sync':True,'task_input':'Create a task from the answered information.'})
    assert initial.status_code==202,initial.text
    data=initial.json()['data'];url=f"/api/agents/a1/jobs/{data['job_id']}/answer"
    body={'answer':'priority high','correlation_id':data['wait_receipt']['correlation_id'],'source':{'document_id':doc.id,'source_version':version}}
    original=routes.resume_information_wait_action
    async def accepted_but_interrupted(*args,**kwargs):
        return {'handled':True,'resumed':False,'reason':'lead_interrupt_after_accept','status':'waiting'}
    monkeypatch.setattr(routes,'resume_information_wait_action',accepted_but_interrupted)
    first=_client(real_env).post(url,json=body)
    assert first.status_code==409,first.text
    monkeypatch.setattr(routes,'resume_information_wait_action',original)
    second=_client(real_env).post(url,json={**body,'answer':'priority low'})
    assert second.status_code==409,('changed answer resumed against unchanged accepted source',second.status_code,second.text,observed)
    assert observed==['wait'],observed
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(BoardTask.title.like('Accepted answer %')).count()==0
