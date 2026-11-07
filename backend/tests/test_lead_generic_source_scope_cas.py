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
    "field",
    [
        "workspace_id",
        "tenant_id",
        "user_id",
        "agent_id",
        "action_type",
        "params",
        "context_snapshot",
    ],
)
def test_source_claim_preserves_peer_scope_and_material(real_env,tmp_path,monkeypatch,field):
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
                if field=='params':
                    peer_value={**dict(row.params or {}), 'correlation_id':'peer-current-correlation'}
                elif field=='context_snapshot':
                    peer_value={**dict(row.context_snapshot or {}), 'correlation_id':'peer-current-correlation'}
                else:
                    peer_value='peer-current-'+field
                setattr(row,field,peer_value)
                changed.append(row.id);db.commit()
        return result
    monkeypatch.setattr(routes,'_load_generic_source_payload',peer_changes_after_source_read)
    result=_client(real_env).post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json={'answer':'source supplied','correlation_id':data['wait_receipt']['correlation_id'],'source':{'document_id':doc.id,'source_version':version}})
    assert result.status_code==409,('stale source claim overwrote changed wait snapshot',result.status_code,result.text,observed)
    assert observed==['wait'],observed
    with real_env.SessionLocal() as db:
        row=db.get(HITLAction,changed[0])
        if field=='params':
            assert (row.params or {}).get('correlation_id')=='peer-current-correlation'
        elif field=='context_snapshot':
            assert (row.context_snapshot or {}).get('correlation_id')=='peer-current-correlation'
        else:
            assert getattr(row,field)=='peer-current-'+field
        assert row.status=='pending'
        assert db.query(BoardTask).filter(BoardTask.title=='Peer snapshot task').count()==0


def test_lost_cas_refuses_foreign_approved_review_with_same_material(
        real_env,tmp_path,monkeypatch):
    """Digest equality alone must not replay a retargeted approved wait."""
    import api.agent_routes as routes
    board,column=_seed_board(real_env)
    doc,version=_source_fixture(real_env,tmp_path,monkeypatch)
    observed=[]
    def wait(task_input,history,context):
        observed.append('wait')
        return ReActStep(thought='Need authorized evidence.',information_wait=InformationWaitRequest(question='Which source?',missing_fact='source'))
    def resumed(task_input,history,context):
        observed.append('resumed')
        return ReActStep(thought='Use accepted fact.',action=ToolCall(tool='tasks.create',params={'board_id':board,'column_id':column,'title':'Foreign approved task','status':'backlog'}))
    def final(task_input,history,context):
        return ReActStep(thought='Verified.',final_answer='Created.')
    _install_model(monkeypatch,[wait,resumed,final])
    initial=_run(real_env,operation_id='lead-source-lost-cas',parameters={'sync':True,'task_input':'Create a task when source arrives.'})
    assert initial.status_code==202,initial.text
    data=initial.json()['data'];original=routes._load_generic_source_payload;armed=[True];changed=[]
    async def peer_approves_with_foreign_scope(*args,**kwargs):
        result=await original(*args,**kwargs)
        if armed[0]:
            armed[0]=False
            with real_env.SessionLocal() as db:
                rows=db.query(HITLAction).all()
                row=next(r for r in rows if (r.context_snapshot or {}).get('job_id')==data['job_id'])
                digest=routes._answer_material_digest('source supplied',result)
                snap={**dict(row.context_snapshot or {}),'accepted_answer':'source supplied','accepted_answer_sha256':digest,'information_source':result}
                row.context_snapshot=snap
                row.user_feedback='source supplied'
                row.status='approved'
                row.workspace_id='peer-current-workspace_id'
                changed.append(row.id);db.commit()
        return result
    monkeypatch.setattr(routes,'_load_generic_source_payload',peer_approves_with_foreign_scope)
    result=_client(real_env).post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json={'answer':'source supplied','correlation_id':data['wait_receipt']['correlation_id'],'source':{'document_id':doc.id,'source_version':version}})
    assert result.status_code==409,('foreign approved review was replayed',result.status_code,result.text,observed)
    assert observed==['wait'],observed
    with real_env.SessionLocal() as db:
        row=db.get(HITLAction,changed[0])
        assert row.workspace_id=='peer-current-workspace_id'
        assert row.status=='approved'
        assert db.query(BoardTask).filter(BoardTask.title=='Foreign approved task').count()==0


@pytest.mark.parametrize("kind", ["sql_null", "json_null", "object"])
def test_wait_cas_matches_each_physical_snapshot_null_kind(real_env,kind):
    """SQL NULL, JSON null and object material are distinct CAS inputs."""
    from sqlalchemy import text, update
    from api.agent_routes import (
        _load_wait_record,
        _wait_record_cas_conditions,
        _wait_record_material,
    )
    raw={"sql_null":None,"json_null":"null","object":'{"correlation_id": "c1"}'}[kind]
    action_id=f"physical-null-{kind}"
    with real_env.SessionLocal() as db:
        db.execute(text(
            "INSERT INTO hitl_actions (id, workspace_id, tenant_id, user_id, "
            "action_type, platform, params, status, context_snapshot) VALUES "
            "(:id, NULL, NULL, 'member-1', 'agent_information_request', "
            "'internal', '{}', 'pending', :snapshot)"),
            {"id":action_id,"snapshot":raw})
        db.commit()
        loaded=_load_wait_record(db,action_id)
        assert loaded is not None
        action,snapshot_sql_null,params_sql_null=loaded
        material=_wait_record_material(action,context_snapshot_sql_null=snapshot_sql_null,params_sql_null=params_sql_null)
        expected=("sql_null" if kind=="sql_null" else ("json_null" if kind=="json_null" else "object"))
        assert material['context_snapshot'].get('null_kind', 'object')==expected
        claimed=db.execute(update(HITLAction).where(*_wait_record_cas_conditions(material)).values(status='approved'))
        assert claimed.rowcount==1,kind
        db.rollback()
        # A peer material transition must not match the earlier physical kind.
        peer={"sql_null":"null","json_null":None,"object":None}[kind]
        db.execute(text("UPDATE hitl_actions SET context_snapshot = :snapshot WHERE id = :id"),{"snapshot":peer,"id":action_id})
        db.commit()
        stale=db.execute(update(HITLAction).where(*_wait_record_cas_conditions(material)).values(status='approved'))
        assert stale.rowcount==0,kind
        db.rollback()
