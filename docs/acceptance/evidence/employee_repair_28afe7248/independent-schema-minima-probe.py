import pytest
from core.task_outcome_contract import sent_record_confirmed_evidence
from core.assignment_plan import new_assignment,new_step
from core.assignment_readiness import evaluate_step_readiness

@pytest.mark.parametrize('step,result',[
 ({'operation_id':'op-1'},{'readback':{'sent_items':{'present':True,'operation_id':'op-1'}}}),
 ({},{'provider_ref':'msg-1','readback':{'sent_items':{'present':True,'provider_ref':'msg-1'}}}),
])
def test_sent_items_requires_both_operation_correlation_and_observed_message(step,result):
 assert sent_record_confirmed_evidence(step,result) is None

@pytest.mark.parametrize('coverage',[
 {'complete':True,'known':'unknown','truncated':False},
 {'complete':True,'known':True,'truncated':'no'},
])
def test_malformed_observed_coverage_flags_cannot_verify(coverage):
 source=new_step(step_id='source',title='source',operation_type='retrieve',adapter='workbook.read',inputs={'resource_binding':{'resource_id':'r1','source_version':'v1'}})
 source.update(status='applied',operation_id='op1',result={'resource_id':'r1','source_version':'v1','verification':{'status':'verified'},'coverage':coverage})
 child=new_step(step_id='child',title='use source',operation_type='calculate',adapter='formula.calculate',inputs={},requires=[{'kind':'receipt','step_id':'source','require':'verified'}])
 a=new_assignment(objective='Use verified source',steps=[source,child]);assert evaluate_step_readiness(child,a)['eligible'] is False
