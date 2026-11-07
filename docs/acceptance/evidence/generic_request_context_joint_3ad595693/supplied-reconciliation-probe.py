"""A successful effect readback is not a committed reconciliation transition."""
import asyncio
import uuid
import pytest
from tests.test_oracle_mini_app_host_mutations import host
from tests.test_generic_request_expectations import _enable_oracle, _claim_context
from tests.test_generic_oracle_mutation_contract import _agent
from core.action_registry import action_registry
from core.oracle import OracleResult, register_postcondition
from core import outbound_operation_claim as claims

@pytest.mark.parametrize("cas_result", ["refused", "peer_changed"])
def test_reconcile_cannot_report_committed_success_if_transition_loses(host, monkeypatch, cas_result):
    _enable_oracle(monkeypatch)
    monkeypatch.setattr("core.generic_agent.get_db_session", host.session)
    name="test.root.reconcile."+uuid.uuid4().hex
    operation="root-op-"+uuid.uuid4().hex
    calls=[]
    verdicts=[False,True]
    async def leaf(tool,args,context=None):
        calls.append(tool)
        return {"success":True,"status":"success","action_result":"applied"}
    async def verifier(ctx):
        return OracleResult(name,verdicts.pop(0),"controlled independent readback")
    action_registry.register(name,leaf,effects=[{"effect":"create","scope":"local"}])
    register_postcondition(name)(verifier)
    context=_claim_context(operation)
    first=asyncio.run(_agent(leaf)._step_act_unaudited(name,{"value":"one"},context=dict(context),pre_approved=True))
    assert first.get("status")=="uncertain",first
    original=claims.mark_status
    seen=[]
    def loses(record_id,status,**kwargs):
        if status==claims.SUCCEEDED:
            seen.append(record_id)
            if cas_result=="peer_changed":
                assert original(record_id,claims.FAILED_BEFORE_EFFECT,expected_status=claims.UNCERTAIN_EFFECT,db_factory=host.session)
            return False
        return original(record_id,status,**kwargs)
    monkeypatch.setattr(claims,"mark_status",loses)
    final=asyncio.run(_agent(leaf)._step_act_unaudited(name,{"value":"one"},context=dict(context),pre_approved=True))
    assert len(calls)==1, "must never resend"
    assert seen, "must exercise actual reconciliation persistence"
    rows=claims.generic_operations(context["workspace_id"],operation,db_factory=host.session,strict=True)
    assert rows and rows[0]["status"]!=claims.SUCCEEDED,rows
    assert final.get("reconciled") is not True and final.get("business_success") is not True, {"result":final,"durable_status":rows[0]["status"]}
