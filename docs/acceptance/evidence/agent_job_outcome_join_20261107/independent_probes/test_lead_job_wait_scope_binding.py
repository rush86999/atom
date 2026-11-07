"""A default/null legacy review cannot certify a new scoped wait."""
import pytest
from tests.test_agent_run_outcome_join_contract import env, _run, _job_payload
from core.models import HITLAction

@pytest.mark.parametrize('workspace,tenant',[('ws1','t1'),('default','t1'),(None,'t1'),('ws1',None)])
def test_scoped_wait_needs_exact_authoritative_scope(env,workspace,tenant):
    def produce(context):
        with env.db_session() as db:
            db.add(HITLAction(id='scoped-review',agent_id='a1',workspace_id=workspace,tenant_id=tenant,user_id='member-1',action_type='missing_information',platform='internal',params={},context_snapshot={'job_id':context['job_id'],'execution_id':context['execution_id']},status='pending'))
            db.commit()
        return {'status':'waiting','hitl_action_id':'scoped-review'}
    env.behavior=produce
    response=_run(env,operation_id='scope-wait',parameters={'sync':True,'task_input':'work'})
    job,payload=_job_payload(env,env.executions[0]['context']['job_id'])
    if workspace=='ws1' and tenant=='t1':
        assert response.status_code==202 and job.status=='waiting'
    else:
        assert job.status!='waiting',{'review_workspace':workspace,'review_tenant':tenant,'job_status':job.status,'payload':payload}
