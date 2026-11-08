"""The normal MCP dispatch path must not rely on a Generic-only replay claim."""
import asyncio
import pytest
from tests.test_oracle_radio_create_thread import env, _args, _context, _threads

@pytest.fixture(autouse=True)
def flags(monkeypatch):
    monkeypatch.setenv('ATOM_RADIO_ENABLED','true')
    monkeypatch.setenv('ATOM_ORACLE_ENFORCE','true')
    monkeypatch.setenv('ATOM_ORACLE_VERIFIER_ENABLED','true')

def call(args,ctx):
    from integrations.mcp_service import MCPService
    return asyncio.run(MCPService(tenant_id='tenant-1').call_tool('radio.create_thread',args,context=ctx))

def test_mcp_same_operation_reuses_exact_thread(env):
    op='lead-mcp-thread-replay';first=call(_args(op),_context(op))
    assert isinstance(first,dict) and first.get('success') is True,first
    second=call(_args(op),_context(op))
    assert len(_threads(env))==1,('MCP replay created a second thread',first,second)
    assert second.get('remote_id')==first.get('remote_id'),second

def test_mcp_same_operation_changed_material_has_zero_new_effect(env):
    op='lead-mcp-thread-changed';first=call(_args(op),_context(op))
    assert isinstance(first,dict) and first.get('success') is True,first
    second=call(_args(op,name='different name'),_context(op))
    assert len(_threads(env))==1,('same operation changed material created another thread',second)
    assert second.get('success') is False,second

def test_mcp_created_thread_always_carries_operation_identity(env):
    result=call(_args(''),_context(''))
    rows=_threads(env)
    if rows:
        operation=str(result.get('operation_id') or '')
        assert operation and (rows[0].metadata_json or {}).get('operation_id')==operation,('committed thread has no durable operation identity',result)
    else:
        assert result.get('success') is False and result.get('effect_possible') is False,result

def test_mcp_readback_uncertainty_reconciles_without_resend(env,monkeypatch):
    import core.agent_radio.radio_thread_mutations as mutations
    original=mutations.read_thread;armed=[True]
    def lose_readback(*args,**kwargs):
        if armed[0]:armed[0]=False;raise TimeoutError('controlled readback timeout')
        return original(*args,**kwargs)
    monkeypatch.setattr(mutations,'read_thread',lose_readback)
    op='lead-mcp-thread-lost-readback';first=call(_args(op),_context(op))
    assert first.get('action_result')=='uncertain' and first.get('remote_id'),first
    second=call(_args(op),_context(op))
    assert len(_threads(env))==1,('uncertainty recovery resent the original operation',first,second)
    assert second.get('remote_id')==first.get('remote_id'),second
