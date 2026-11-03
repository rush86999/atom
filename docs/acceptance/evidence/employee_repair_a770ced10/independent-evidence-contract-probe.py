import pytest
from core.assignment_readiness import evaluate_step_readiness,normalize_requirements
from core.assignment_plan import new_assignment,new_step
from core.task_outcome_contract import build_assignment_outcome

@pytest.mark.parametrize('result',[{}, {'verification':{'status':'conflict'}}, {'verification':{'status':'refuted'}}, {'verification':{'status':'verified','missing_fields':['currency'],'mismatches':[]}}, {'coverage':{'known':True,'truncated':True}}])
def test_verified_receipt_prerequisite_requires_material_proof(result):
    source=new_step(step_id='source',title='source',operation_type='retrieve',adapter='test.read',inputs={})
    source.update(status='applied',result=result)
    child=new_step(step_id='child',title='dependent',operation_type='calculate',adapter='test.calc',inputs={},requires=[{'kind':'receipt','step_id':'source','require':'verified'}])
    assignment=new_assignment(objective='Use verified evidence',steps=[source,child])
    verdict=evaluate_step_readiness(child,assignment)
    assert verdict['eligible'] is False,verdict

def test_provider_acceptance_does_not_establish_sent_record():
    step=new_step(step_id='send',title='send',operation_type='outbound',adapter='email.send_outlook',effect='external',inputs={})
    step.update(status='applied',result={'provider_state':'accepted','provider_ref':'accepted-1'})
    assignment=new_assignment(objective='Confirm Sent Items',steps=[step],completion_criteria=[{'criterion_id':'sent_record_confirmed:one','kind':'sent_record_confirmed','required':True}])
    verdict=build_assignment_outcome(assignment)
    assert verdict['verdict'] is not True,verdict
