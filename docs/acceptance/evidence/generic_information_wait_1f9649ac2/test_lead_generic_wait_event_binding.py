"""An old answer must not answer a different prerequisite on the same job."""
import pytest
from core.models import HITLAction
from core.react_models import ReActStep, InformationWaitRequest
from tests.test_agent_run_outcome_join_contract import real_env,_run,_job_payload
from tests.test_agent_generic_information_wait import _install_model,_wait_answer,_seed_board

@pytest.mark.parametrize('omit_event_identity',[False,True])
def test_redelivery_cannot_answer_the_next_wait(real_env,monkeypatch,omit_event_identity):
    _seed_board(real_env)
    def title(task,history,context):
        return ReActStep(thought='The task title is missing.',information_wait=InformationWaitRequest(question='What title?',missing_fact='title'))
    def priority(task,history,context):
        return ReActStep(thought='The title is available but priority is missing.',information_wait=InformationWaitRequest(question='What priority?',missing_fact='priority'))
    def wrongly_resumed(task,history,context):
        return ReActStep(thought='An old answer was delivered again.',final_answer='No actual priority was supplied.')
    calls=_install_model(monkeypatch,[title,priority,wrongly_resumed])
    start=_run(real_env,operation_id='root-repeated-wait-'+str(omit_event_identity),parameters={'sync':True,'task_input':'Create a task after obtaining its title and priority'})
    assert start.status_code==202,start.text
    data=start.json()['data'];job=data['job_id'];first=data['wait_receipt']
    answer=_wait_answer(real_env,job,'Closing task',correlation_id=None if omit_event_identity else first['correlation_id'])
    assert answer.status_code==202,answer.text
    second=answer.json()['data']['wait_receipt']
    assert second['hitl_action_id']!=first['hitl_action_id']
    before=len(calls)
    replay=_wait_answer(real_env,job,'Closing task',correlation_id=None if omit_event_identity else first['correlation_id'])
    with real_env.SessionLocal() as db:
        row=db.get(HITLAction,second['hitl_action_id'])
        assert row.status=='pending', 'redelivery of the title answer settled the NEW priority question'
    assert len(calls)==before,'old information triggered a second, different prerequisite'
    assert replay.status_code in (200,409,422),replay.text
