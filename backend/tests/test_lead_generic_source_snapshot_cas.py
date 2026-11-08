"""A source answer must not overwrite a changed durable wait snapshot."""
import core.models
from core.models import HITLAction
from core.models_board import BoardTask
from core.react_models import InformationWaitRequest, ReActStep, ToolCall
from tests.test_generic_source_answer_contract import _source_fixture
from tests.test_agent_generic_information_wait import _install_model, _seed_board
from tests.test_agent_run_outcome_join_contract import real_env, _run, _client


def test_source_claim_preserves_peer_wait_material(real_env,tmp_path,monkeypatch):
    import api.agent_routes as routes
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
                rows=db.query(HITLAction).all()
                row=next(r for r in rows if (r.context_snapshot or {}).get('job_id')==data['job_id'])
                snap=dict(row.context_snapshot);snap['correlation_id']='peer-current-correlation';row.context_snapshot=snap
                changed.append(row.id);db.commit()
        return result
    monkeypatch.setattr(routes,'_load_generic_source_payload',peer_changes_after_source_read)
    result=_client(real_env).post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json={'answer':'source supplied','correlation_id':data['wait_receipt']['correlation_id'],'source':{'document_id':doc.id,'source_version':version}})
    assert result.status_code==409,('stale source claim overwrote changed wait snapshot',result.status_code,result.text,observed)
    assert observed==['wait'],observed
    with real_env.SessionLocal() as db:
        row=db.get(HITLAction,changed[0]);assert row.context_snapshot['correlation_id']=='peer-current-correlation'
        assert row.status=='pending'
        assert db.query(BoardTask).filter(BoardTask.title=='Peer snapshot task').count()==0
