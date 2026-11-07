"""Business action params cannot replace server-owned wait execution identity."""
import pytest
from tests.test_agent_run_outcome_join_contract import env, _run, _job_payload
from core.models import HITLAction

@pytest.mark.parametrize('mode',['exact','foreign_snapshot_shadowed','missing_snapshot_from_params'])
def test_action_parameters_do_not_authorize_a_task_wait(env,mode):
    def produce(context):
        exact={'job_id':context['job_id'],'execution_id':context['execution_id']}
        snapshot=exact if mode=='exact' else ({'job_id':'other-job','execution_id':'other-execution'} if mode=='foreign_snapshot_shadowed' else None)
        with env.db_session() as db:
            db.add(HITLAction(id='shadow-review',agent_id='a1',workspace_id='ws1',tenant_id='t1',user_id='member-1',action_type='missing_information',platform='internal',params={} if mode=='exact' else exact,context_snapshot=snapshot,status='pending'))
            db.commit()
        return {'status':'waiting','hitl_action_id':'shadow-review'}
    env.behavior=produce
    response=_run(env,operation_id='wait-shadow',parameters={'sync':True,'task_input':'work'})
    job,payload=_job_payload(env,env.executions[0]['context']['job_id'])
    if mode=='exact':assert response.status_code==202 and job.status=='waiting'
    else:assert job.status!='waiting',{'mode':mode,'status':job.status,'payload':payload}
