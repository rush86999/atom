"""Normal Generic tool args must reach the same verified host writer as assignment args.

Governance is bypassed explicitly to isolate the existing outcome/expectation
consumer. MCP transport delegates to the real registry/producer; no model, guest
or provider call is used. The assignment case is the otherwise-identical control.
"""
import asyncio
import json
from pathlib import Path
import pytest
from tests.test_oracle_mini_app_host_mutations import host, _adapter, USER,TENANT,WORKSPACE
from tests.test_generic_oracle_mutation_contract import _agent
from core.action_registry import action_registry
from core.models import MiniApp,CanvasAudit

@pytest.mark.parametrize('consumer',['generic','assignment'])
def test_plain_authorized_host_request_completes_with_real_receipt(host,monkeypatch,consumer):
    monkeypatch.setenv('ATOM_ORACLE_ENFORCE','true')
    monkeypatch.setenv('ATOM_ORACLE_VERIFIER_ENABLED','true')
    monkeypatch.setattr('core.generic_agent.get_db_session',host.session)
    args={'name':'Normal consumer app','declared_scopes':['canvas_render'],'dependencies':[]}
    if consumer=='assignment':
        result=_adapter('mini_app_scaffold',args,'normal-assignment-operation')
        success=result.get('_adapter_status')=='applied'
    else:
        async def leaf(name,arguments,context=None):
            return await action_registry.execute_action(name,arguments,context or {})
        agent=_agent(leaf);agent.workspace_id=WORKSPACE;agent.tenant_id=TENANT
        result=asyncio.run(agent._step_act_unaudited('mini_app_scaffold',args,context={'workspace_id':WORKSPACE,'tenant_id':TENANT,'user_id':USER,'actor_id':USER,'execution_id':'normal-generic-execution','run_id':'normal-generic-execution','tier':'autonomous'},pre_approved=True))
        success=result.get('oracle_verified') is True and result.get('success') is True
    with host.Session() as db:
        assert db.query(MiniApp).filter(MiniApp.name==args['name']).count()==1,result
        assert db.query(CanvasAudit).filter(CanvasAudit.action_type=='mini_app_scaffold').count()==1,result
    Path('/private/tmp/root-generic-mini-'+consumer+'-result.json').write_text(json.dumps(result,default=str,indent=2)+'\n')
    assert success,{'consumer':consumer,'result':result}
