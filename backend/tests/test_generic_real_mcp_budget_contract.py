"""Real MCP registry dispatch, governance and independent host receipt."""
import asyncio
import json
from datetime import datetime
import pytest
from tests.test_oracle_mini_app_host_mutations import host, USER, TENANT, WORKSPACE
from tests.test_generic_oracle_mutation_contract import _agent
from core.models import AgentRegistry, MiniApp, CanvasAudit, Tenant, Workspace, TenantSetting, TokenUsage
from integrations.mcp_service import mcp_service

@pytest.mark.parametrize("case",["allowed", "capability_denied", "hard_stop"])
def test_real_mcp_registry_context_and_capability_boundary(host,monkeypatch,case):
    allowed = case != "capability_denied"
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE","true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED","true")
    monkeypatch.setattr("core.generic_agent.get_db_session",host.session)
    with host.Session() as db:
        db.add(Tenant(id=TENANT, name="Local operator", subdomain="local-operator"))
        db.add(Workspace(id=WORKSPACE, name="Operator workspace", tenant_id=TENANT))
        db.add(AgentRegistry(id="scratch-agent",name="Actual MCP agent",category="Operations",module_path="core.generic_agent",class_name="GenericAgent",user_id=USER,workspace_id=WORKSPACE,tenant_id=TENANT,status="autonomous",confidence_score=0.99,capabilities=["mini_app_scaffold"] if allowed else ["canvas.list"]))
        if case == "hard_stop":
            db.add(TenantSetting(tenant_id=TENANT,setting_key="billing",setting_value=json.dumps({"budget_limit_usd":1,"enforcement":{"mode":"hard_stop"}})))
            db.add(TokenUsage(agent_id="scratch-agent",workspace_id=WORKSPACE,tenant_id=TENANT,model_name="controlled-no-provider",cost_usd=2,timestamp=datetime.now()))
        db.commit()
    if case == "hard_stop":
        from core.budget_enforcement_service import BudgetEnforcementService
        with host.Session() as db:
            direct=asyncio.run(BudgetEnforcementService(db).check_budget_before_action(tenant_id=TENANT,agent_id="scratch-agent",action="mini_app_scaffold"))
        assert direct["allowed"] is False,direct
    agent=_agent(mcp_service.call_tool);agent.mcp=mcp_service;agent.workspace_id=WORKSPACE;agent.tenant_id=TENANT
    context={"workspace_id":WORKSPACE,"tenant_id":TENANT,"user_id":USER,"actor_id":USER,"agent_id":agent.id,"execution_id":"real-mcp-execution","run_id":"real-mcp-execution","tier":"autonomous"}
    result=asyncio.run(agent._step_act_unaudited("mini_app_scaffold",{"name":"Actual MCP app","declared_scopes":["canvas_render"],"dependencies":[]},context=context,pre_approved=False))
    with host.Session() as db:
        effects=db.query(MiniApp).filter(MiniApp.name=="Actual MCP app").all()
        receipts=db.query(CanvasAudit).filter(CanvasAudit.action_type=="mini_app_scaffold").all()
    if case == "allowed":
        assert result.get("success") is True and result.get("oracle_verified") is True,result
        assert len(effects)==len(receipts)==1,result
        assert effects[0].created_by==USER
        assert receipts[0].details_json["workspace_id"]==WORKSPACE
        assert receipts[0].details_json["tenant_id"]==TENANT
        assert receipts[0].details_json["actor_id"]==USER
        assert receipts[0].details_json["operation_id"]==result["operation_id"]
    else:
        assert not effects and not receipts,result
        if isinstance(result, dict):
            assert result.get("success") is not True,result
        else:
            assert case == "hard_stop" and "budget" in result.lower(), result
        if case == "hard_stop":
            from core.models import HITLAction
            with host.Session() as db:
                assert db.query(HITLAction).filter(
                    HITLAction.agent_id == agent.id).count() == 0


@pytest.mark.parametrize("case", [
    "explicit", "agent_fallback", "workspace_fallback", "personal_null",
    "wrong_tenant", "wrong_workspace", "unconfigured",
])
def test_budget_scope_uses_existing_personal_account_resolution(host, case):
    from core.agent_governance_service import AgentGovernanceService
    personal = case == "personal_null"
    tenant = "default" if personal else TENANT
    workspace_id = "default" if personal else WORKSPACE
    agent_workspace = None if personal else WORKSPACE
    agent_tenant = None if case in ("personal_null", "workspace_fallback") else TENANT
    with host.Session() as db:
        db.add(Tenant(id=tenant, name="Operator", subdomain="budget-operator"))
        db.add(Workspace(id=workspace_id, name="Operator workspace", tenant_id=tenant))
        db.add(AgentRegistry(
            id="budget-agent", name="Budget actor", category="Operations",
            module_path="core.generic_agent", class_name="GenericAgent",
            user_id=USER, workspace_id=agent_workspace, tenant_id=agent_tenant,
            status="autonomous", confidence_score=0.99))
        if case != "unconfigured":
            db.add(TenantSetting(
                tenant_id=tenant, setting_key="billing",
                setting_value=json.dumps({"budget_limit_usd":1,
                    "enforcement":{"mode":"hard_stop"}})))
            db.add(TokenUsage(
                agent_id="budget-agent", workspace_id=agent_workspace,
                tenant_id=tenant, model_name="controlled-no-provider",
                cost_usd=2, timestamp=datetime.now()))
        db.commit()
        selected_tenant = TENANT if case in ("explicit", "unconfigured") else None
        if case == "wrong_tenant":
            selected_tenant = "different-account"
        selected_workspace = "different-workspace" if case == "wrong_workspace" else workspace_id
        service = AgentGovernanceService(
            db, workspace_id=selected_workspace, tenant_id=selected_tenant)
        result = asyncio.run(service._check_budget_async(
            "budget-agent", "mini_app_scaffold", None))
        if case == "unconfigured":
            assert result["allowed"] is True, result
        else:
            assert result["allowed"] is False, result
            if case in ("wrong_tenant", "wrong_workspace"):
                assert "scope" in result["reason"].lower(), result
            else:
                assert result["enforcement_mode"] == "hard_stop", result
                assert result["current_spend_usd"] == 2, result
