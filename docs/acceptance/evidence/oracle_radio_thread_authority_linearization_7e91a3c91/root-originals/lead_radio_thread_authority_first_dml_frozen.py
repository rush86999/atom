"""A peer authority change wins before thread creation's first write."""
import pytest
from tests.test_oracle_radio_create_thread import env, _agent, _args, _context, _call, _threads, _set_creator_state

@pytest.mark.parametrize('changed_agent', ['agent-a', 'agent-b'])
def test_authority_change_before_thread_write_has_zero_effect(env, monkeypatch, changed_agent):
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    armed=[True]
    seen=[]
    def peer_wins_before_first_dml(conn,cursor,statement,parameters,context,executemany):
        text=statement.lstrip().lower()
        target=(text.startswith('update agent_registry') or text.startswith('insert into agent_threads'))
        if armed[0] and target:
            armed[0]=False
            seen.append(text.split('where')[0])
            _set_creator_state(env,changed_agent,enabled=False)
    event.listen(Engine,'before_cursor_execute',peer_wins_before_first_dml)
    operation='lead-authority-before-write-'+changed_agent
    try:
        result=_call(_agent(),_args(operation),_context(operation))
    finally:
        event.remove(Engine,'before_cursor_execute',peer_wins_before_first_dml)
    assert seen, 'no authoritative claim or thread write was observed'
    assert not _threads(env), ('authority changed before first effect but thread was committed',result)
    with env['Session']() as db:
        from core.models import AgentRegistry
        assert db.get(AgentRegistry,changed_agent).enabled is False


def test_current_authority_thread_valid_twin(env):
    operation='lead-authority-current-positive'
    result=_call(_agent(),_args(operation),_context(operation))
    assert len(_threads(env))==1 and result.get('oracle_verified') is True,result
