"""Budget verification must not commit caller-owned business edits."""
import asyncio
import pytest
from tests.test_oracle_mini_app_host_mutations import host,USER,TENANT,WORKSPACE
from core.models import User,Tenant,Workspace,AgentRegistry
from core.agent_governance_service import AgentGovernanceService

@pytest.mark.parametrize("flushed", [False,True])
@pytest.mark.parametrize("read_error", [False,True])
def test_budget_check_does_not_commit_the_callers_edit(host,monkeypatch,flushed,read_error):
    with host.Session() as setup:
        setup.add(Tenant(id=TENANT,name="Operator",subdomain="caller-txn"))
        setup.add(Workspace(id=WORKSPACE,name="Operator workspace",tenant_id=TENANT))
        setup.add(AgentRegistry(id="caller-budget-agent",name="Budget agent",category="Operations",module_path="core.generic_agent",class_name="GenericAgent",user_id=USER,workspace_id=WORKSPACE,tenant_id=TENANT,status="autonomous",confidence_score=0.99))
        setup.commit()
    if read_error:
        def unavailable(*args, **kwargs):
            raise RuntimeError("controlled spend read unavailable")
        monkeypatch.setattr(
            "core.spend_aggregation_service.SpendAggregationService.get_total_spend",
            unavailable)
    with host.Session() as owner:
        user=owner.get(User,USER);old=user.first_name;user.first_name="Uncommitted owner edit"
        if flushed:owner.flush()
        result=asyncio.run(AgentGovernanceService(owner,workspace_id=WORKSPACE,tenant_id=TENANT).can_perform_action_async("caller-budget-agent","mini_app_scaffold"))
        assert result["allowed"] is True,result
        with host.Session() as observer:
            assert observer.get(User,USER).first_name==old,"budget preflight committed someone else's edit"
        assert user.first_name=="Uncommitted owner edit"
        owner.commit()
    with host.Session() as observer:
        assert observer.get(User,USER).first_name=="Uncommitted owner edit"


def test_explicit_rollup_writer_still_persists_cache(host):
    from datetime import datetime
    from core.models import TokenUsage
    from core.spend_aggregation_service import SpendAggregationService
    with host.Session() as db:
        db.add(Tenant(id=TENANT,name="Operator",subdomain="explicit-rollup"))
        db.add(Workspace(id=WORKSPACE,name="Operator workspace",tenant_id=TENANT))
        db.add(AgentRegistry(id="rollup-agent",name="Rollup agent",category="Operations",module_path="core.generic_agent",class_name="GenericAgent",user_id=USER,workspace_id=WORKSPACE,tenant_id=TENANT,status="autonomous"))
        db.add(TokenUsage(agent_id="rollup-agent",workspace_id=WORKSPACE,tenant_id=TENANT,model_name="controlled-no-provider",cost_usd=2,timestamp=datetime.now()))
        db.commit()
        result=SpendAggregationService(db).update_tenant_spend(TENANT)
        assert result["current_spend_usd"]==2,result
    with host.Session() as observer:
        row=observer.get(Tenant,TENANT)
        assert row.current_spend_usd==2 and row.total_spend_usd==2
