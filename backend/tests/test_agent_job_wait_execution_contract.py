"""A real pending review must belong to this execution, not just this agent."""
import pytest
from tests.test_agent_run_outcome_join_contract import env, _run, _job_payload
from core.models import HITLAction

@pytest.mark.parametrize('binding',['missing','foreign','exact'])
def test_pending_wait_is_bound_to_exact_execution(env,binding):
    def produce(context):
        material={} if binding=='missing' else {'job_id':context['job_id'],'execution_id':context['execution_id'] if binding=='exact' else 'another-execution'}
        with env.db_session() as db:
            db.add(HITLAction(id='real-review',agent_id='a1',workspace_id='ws1',tenant_id='t1',user_id='member-1',action_type='missing_information',platform='internal',params={},context_snapshot=material,status='pending'))
            db.commit()
        return {'status':'waiting','hitl_action_id':'real-review'}
    env.behavior=produce
    response=_run(env,operation_id='wait-binding-op',parameters={'sync':True,'task_input':'work'})
    job,payload=_job_payload(env,env.executions[0]['context']['job_id'])
    if binding=='exact':
        assert response.status_code==202 and job.status=='waiting',(response.text,job.status)
    else:
        assert job.status!='waiting',{'binding':binding,'status':job.status,'payload':payload}
