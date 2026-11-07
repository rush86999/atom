"""A returned label/reference is not proof of an existing resumable wait."""
import pytest
from tests.test_agent_run_outcome_join_contract import env, _run, _job_payload

@pytest.mark.parametrize('result',[
    {'status':'waiting','wait_receipt':{'kind':'missing_information'}},
    {'status':'waiting','hitl_action_id':'does-not-exist'},
    {'status':'waiting','wait_receipt':{'id':'made-up','status':'pending','kind':'missing_information'}},
])
def test_unbacked_returned_wait_reference_cannot_be_durable_authority(env,result):
    env.result=result
    response=_run(env,operation_id='unbacked-wait-op',parameters={'sync':True,'task_input':'long task'})
    data=response.json()['data']
    job,payload=_job_payload(env,data['job_id'])
    assert job.status not in {'waiting','awaiting_information'}, {'http':response.status_code,'job_status':job.status,'payload':payload}
    assert payload.get('wait_receipt') is None

def test_normal_verified_completion_still_works(env):
    env.result={'status':'success','output':'completed work'}
    response=_run(env,operation_id='valid-completion',parameters={'sync':True,'task_input':'work'})
    assert response.status_code==200,response.text
    job,payload=_job_payload(env,response.json()['data']['job_id'])
    assert job.status=='success'
