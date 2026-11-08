"""Independent exact JSON binding-type twins; actual persisted business writer."""
import asyncio,os
import pytest
from tests.test_employee_business_feedback import fresh_router,_insert_outcome_row,_row_by_id,_synthetic_result
if os.environ.get('ATOM_PRIVATE_PG_URL'):
    from test_root_postgres_feedback_interleaving import feedback_db
else:
    from tests.test_employee_business_feedback import feedback_db

@pytest.mark.parametrize('stored_workspace',[123,'123'],ids=['numeric-wrong-type','opaque-string-valid'])
def test_exact_workspace_material_type(feedback_db,fresh_router,stored_workspace):
    from core.employee_routing_feedback import record_attempt_evaluation
    generation='root-json-binding-'+type(stored_workspace).__name__
    rowid=_insert_outcome_row(feedback_db,generation,workspace=stored_workspace)
    before=_row_by_id(feedback_db,rowid).prompt_features.copy()
    result=asyncio.run(record_attempt_evaluation(_synthetic_result(generation),stage='employee_evidence_selection',evaluation='failed',failure_kind='wrong_evidence_selection',workspace_id='123',tenant_id='tenant-ctrl'))
    after=_row_by_id(feedback_db,rowid).prompt_features
    if isinstance(stored_workspace,str):
        assert result['status']=='annotated',result
        assert after.get('business_outcome')=='failed',after
    else:
        assert result['recorded'] is False,(result,after)
        assert after==before,(before,after)
