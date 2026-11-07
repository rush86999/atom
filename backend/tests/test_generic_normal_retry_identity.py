"""A model retry must not evade a prior uncertain effect via irrelevant args."""
import asyncio,sqlite3,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
from tests.test_generic_oracle_mutation_contract import scratch_db,_build_execute_agent

def test_normal_loop_changed_retry_cannot_repeat_uncertain_intent(scratch_db,monkeypatch):
    from core.action_registry import action_registry
    from core.react_models import ReActStep,ToolCall
    name='lead.generic.retry-material.'+uuid.uuid4().hex
    calls=[]
    async def leaf(tool,args,context=None):
        calls.append(dict(args))
        with sqlite3.connect(scratch_db['path']) as db:db.execute('insert into effects values (?,?)',(uuid.uuid4().hex,args['value']))
        raise TimeoutError('confirmation unavailable after accepted append')
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    agent=_build_execute_agent(scratch_db,monkeypatch)
    agent.mcp=SimpleNamespace(call_tool=leaf,get_all_tools=AsyncMock(return_value=[]))
    agent._react_step=AsyncMock(side_effect=[
        ReActStep(thought='append requested record',action=ToolCall(tool=name,params={'value':'one requested record'})),
        ReActStep(thought='retry the same append',action=ToolCall(tool=name,params={'value':'one requested record','retry_note':'confirmation retry'})),
        ReActStep(thought='done',final_answer='Created the requested record.')])
    result=asyncio.run(agent.execute('Append exactly one record once',context={'workspace_id':'w','tenant_id':'t','user_id':'u','execution_id':'one-record-exec'}))
    with sqlite3.connect(scratch_db['path']) as db: count=db.execute('select count(*) from effects').fetchone()[0]
    assert len(calls)==1 and count==1,(calls,count,result)
    assert result.get('status') not in ['success','completed','objective_satisfied'],result


def test_late_peer_claim_keeps_normal_run_unresolved(scratch_db,monkeypatch):
    from core.action_registry import action_registry
    from core.react_models import ReActStep,ToolCall
    name='lead.generic.peer-claim.'+uuid.uuid4().hex
    agent=_build_execute_agent(scratch_db,monkeypatch)
    agent.mcp=SimpleNamespace(call_tool=AsyncMock(),get_all_tools=AsyncMock(return_value=[]))
    action_registry.register(name,lambda *a,**k:None,effects=[{'effect':'create','scope':'local'}])
    context={'workspace_id':'w','tenant_id':'t','user_id':'u','execution_id':'peer-claim-exec'}
    args={'value':'pending'}
    decisions=[]
    async def decide(*unused,**ignored):
        if not decisions:
            decisions.append('claimed')
            op=agent._server_operation_id(name,args,context)
            claim=agent._claim_mutation_operation(name,args,context,op)
            assert claim.get('won') is True,claim
            return ReActStep(thought='requested write',action=ToolCall(tool=name,params=args))
        return ReActStep(thought='done',final_answer='Finished.')
    agent._react_step=AsyncMock(side_effect=decide)
    result=asyncio.run(agent.execute('Perform the requested write',context=context))
    agent.mcp.call_tool.assert_not_awaited()
    assert result.get('status')=='uncertain' and result.get('requires_reconciliation') is True,result
