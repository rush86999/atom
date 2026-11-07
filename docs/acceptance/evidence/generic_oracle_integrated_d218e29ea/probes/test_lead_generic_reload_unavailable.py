"""Cold resume must distinguish an unreadable operation store from no claims."""
import asyncio,sqlite3,uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from tests.test_generic_oracle_mutation_contract import scratch_db,_agent,_claim_context,_build_execute_agent

def test_unavailable_claim_read_cannot_certify_cold_completion(scratch_db,monkeypatch):
    from core.action_registry import action_registry
    from core.react_models import ReActStep
    import core.generic_agent as ga
    name='lead.generic.reload.'+uuid.uuid4().hex
    async def leaf(tool,args,context=None):
        with sqlite3.connect(scratch_db['path']) as db:db.execute('insert into effects values (?,?)',('one','landed'))
        raise TimeoutError('confirmation unavailable')
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    ctx=_claim_context('reload-'+uuid.uuid4().hex)
    first=asyncio.run(_agent(leaf)._step_act_unaudited(name,{},context=dict(ctx),pre_approved=True))
    assert first.get('requires_reconciliation') is True,first
    with sqlite3.connect(scratch_db['path']) as db:
        assert db.execute('select status from task_operation_records').fetchone()[0]=='uncertain_effect'
    agent=_build_execute_agent(scratch_db,monkeypatch)
    agent.mcp=SimpleNamespace(call_tool=AsyncMock(),get_all_tools=AsyncMock(return_value=[]))
    agent._react_step=AsyncMock(return_value=ReActStep(thought='finished',final_answer='Everything done.'))
    @contextmanager
    def unavailable():
        raise RuntimeError('operation-store read unavailable')
        yield
    monkeypatch.setattr(ga,'get_db_session',unavailable)
    result=asyncio.run(agent.execute('continue original task',context=dict(ctx)))
    assert result.get('status') not in ['success','completed','objective_satisfied'],result
    agent.mcp.call_tool.assert_not_awaited()
