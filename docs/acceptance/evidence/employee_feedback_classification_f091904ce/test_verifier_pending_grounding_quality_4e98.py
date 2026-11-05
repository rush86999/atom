import asyncio
from tests.test_employee_business_feedback import feedback_db, fresh_router, _insert_outcome_row, _synthetic_result

def test_grounding_check_cannot_certify_unresolved_employee_business_quality(feedback_db, fresh_router):
    from core.employee_routing_feedback import record_pending_business_evaluation
    from core.learning_llm_router import LearningBasedRouter, RoutingFeedback
    from core.llm.capability_profiles import get_profile, load_feedback_evidence, reset_capability_evidence_cache
    generation='pending-then-grounding'
    _insert_outcome_row(feedback_db, generation, profile='employee_wait_choice')
    result=_synthetic_result(generation, profile='employee_wait_choice')
    result['source']='model_wait_choice'
    pending=asyncio.run(record_pending_business_evaluation(result,stage='employee_wait_choice',workspace_id='ws-ctrl',tenant_id='tenant-ctrl'))
    assert pending['status']=='annotated'
    writer=LearningBasedRouter.__new__(LearningBasedRouter)
    status=writer._persist_feedback(RoutingFeedback(routing_result_id=generation,tenant_id='tenant-ctrl',model_id='llama3.1:8b',task_type='general',success=True,quality_satisfied=True,cost_within_budget=True,user_satisfaction=.9),{'verdict':'grounding_ok'})
    assert status=='annotated'
    reset_capability_evidence_cache()
    evidence=load_feedback_evidence(get_profile('employee_wait_choice'),workspace_id='ws-ctrl',tenant_id='tenant-ctrl')
    route=evidence.get('local_ctrl1234/llama3.1:8b',{})
    assert route.get('successes',0)==0,evidence
    assert route.get('quality_successes',0)==0,evidence
