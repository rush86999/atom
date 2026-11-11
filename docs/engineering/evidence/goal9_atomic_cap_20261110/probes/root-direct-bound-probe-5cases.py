import pytest
from tests.test_goal9_atomic_cap import host,_seed,TENANT,WORKSPACE

@pytest.mark.parametrize('bound',[-1.0,float('nan'),float('inf'),False,True])
def test_direct_invalid_reservation_bound_refuses_without_a_row(host,bound):
 from core.spend_aggregation_service import begin_llm_usage,BudgetReservationRefused
 from core.models import TokenUsage
 _seed(host,spend=90.0)
 with pytest.raises(BudgetReservationRefused):
  begin_llm_usage(provider_id='controlled-paid',model_name='controlled-model',workspace_id=WORKSPACE,tenant_id=TENANT,request_id='root-invalid-bound',attempt_id='root-invalid-bound',reserved_cost_usd=bound,enforce_budget=True)
 with host.Session() as db:
  assert db.query(TokenUsage).filter(TokenUsage.attempt_id=='root-invalid-bound').count()==0
