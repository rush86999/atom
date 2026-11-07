"""Configured budget denial cannot be bypassed by proposing maturity review."""
import asyncio
import json
import uuid
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base,Tenant,Workspace,User,AgentRegistry,TenantSetting,TokenUsage
from core.agent_governance_service import AgentGovernanceService

@pytest.fixture(scope="module")
def ledger(tmp_path_factory):
    # One real schema, fresh opaque account/agent identities per case. No
    # cross-case aggregation, model transport, or repeated app startup.
    path=tmp_path_factory.mktemp("budget-decision-matrix")/"ledger.db"
    engine=create_engine("sqlite:///"+str(path))
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine,expire_on_commit=False)
    engine.dispose()

@pytest.mark.parametrize("caller",["async","sync","sync_in_async"])
@pytest.mark.parametrize("tier",["student","intern","supervised","autonomous"])
@pytest.mark.parametrize("mode",["hard_stop","soft_stop","approval","alert_only"])
@pytest.mark.parametrize("exhausted",[False,True])
def test_budget_and_maturity_decisions_compose(ledger,caller,tier,mode,exhausted):
    tenant,workspace,user,agent=[str(uuid.uuid4()) for _ in range(4)]
    with ledger() as db:
        db.add(Tenant(id=tenant,name="Operator",subdomain=tenant))
        db.add(Workspace(id=workspace,name="Operator workspace",tenant_id=tenant))
        db.add(User(id=user,email=user+"@example.test",first_name="Scratch",last_name="User",hashed_password="not-a-login-secret",role="member",status="active",is_active=True,tenant_id=tenant,workspace_id=workspace))
        db.add(AgentRegistry(id=agent,name="Decision actor",category="Operations",module_path="core.generic_agent",class_name="GenericAgent",user_id=user,workspace_id=workspace,tenant_id=tenant,status=tier,confidence_score={"student":.35,"intern":.6,"supervised":.8,"autonomous":.99}[tier]))
        db.add(TenantSetting(tenant_id=tenant,setting_key="billing",setting_value=json.dumps({"budget_limit_usd":1 if exhausted else 10,"enforcement":{"mode":mode}})))
        db.add(TokenUsage(agent_id=agent,workspace_id=workspace,tenant_id=tenant,model_name="controlled-no-provider",cost_usd=2,timestamp=datetime.now()))
        db.commit()
        service=AgentGovernanceService(db,workspace_id=workspace,tenant_id=tenant)
        if caller=="async":result=asyncio.run(service.can_perform_action_async(agent,"create_task"))
        elif caller=="sync":result=service.can_perform_action(agent,"create_task")
        else:
            async def route():return service.can_perform_action(agent,"create_task")
            result=asyncio.run(route())
        maturity_allowed=tier in ("supervised","autonomous")
        maturity_review=tier!="autonomous"
        if exhausted and mode!="alert_only":
            assert result["allowed"] is False,result
            assert bool(result.get("requires_human_approval")) is (mode=="approval"),result
        else:
            assert result["allowed"] is maturity_allowed,result
            assert bool(result.get("requires_human_approval")) is maturity_review,result
