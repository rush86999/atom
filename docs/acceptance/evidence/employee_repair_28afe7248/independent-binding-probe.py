from core.assignment_plan import new_step,new_assignment
from core.assignment_readiness import evaluate_step_readiness
from core.task_outcome_contract import sent_record_confirmed_evidence

def test_verified_status_without_any_identity_or_coverage_is_unknown():
    source=new_step(step_id='source',title='source',operation_type='retrieve',adapter='workbook.read',inputs={'resource_binding':{'resource_id':'file-1','source_version':'v1'}})
    source.update(status='applied',operation_id='op-1',result={'verification':{'status':'verified'}})
    child=new_step(step_id='use',title='use',operation_type='calculate',adapter='formula.calculate',inputs={},requires=[{'kind':'receipt','step_id':'source','require':'verified'}])
    a=new_assignment(objective='Use the verified workbook',steps=[source,child])
    assert evaluate_step_readiness(child,a)['eligible'] is False

def test_sent_items_presence_without_correlated_identity_is_unknown():
    step={'operation_id':'op-1'}; result={'provider_ref':'message-1','readback':{'sent_items':{'present':True}}}
    assert sent_record_confirmed_evidence(step,result) is None

def test_sent_items_matching_operation_does_not_override_wrong_message():
    step={'operation_id':'op-1'};result={'provider_ref':'message-1','readback':{'sent_items':{'present':True,'operation_id':'op-1','provider_ref':'message-foreign'}}}
    assert sent_record_confirmed_evidence(step,result) is False
