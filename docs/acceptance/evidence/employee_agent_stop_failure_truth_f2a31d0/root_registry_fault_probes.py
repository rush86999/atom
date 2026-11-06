"""Controlled registry boundary failures; no live worker is touched."""
from tests.test_agent_stop_scope_contract import env, _stop, _audits


def test_unreadable_registry_is_not_a_verified_empty_task_set(env):
    def unreadable(_agent_id):
        raise RuntimeError('synthetic registry read failure')
    env.monkeypatch.setattr(env.fake, 'get_agent_tasks', unreadable)
    response = _stop(env, 'admin-1', 'a1', 'verifier-unreadable')
    assert response.status_code == 503, response.text
    detail = response.json()['detail']
    assert detail['verification']['effect'] == 'none'
    assert env.fake.cancel_calls == []
    assert len(env.fake.tasks['a1']) == 2
    assert _audits(env) == []


def test_cancellation_failure_after_partial_progress_is_not_effect_none(env):
    async def partial_then_raise(agent_id):
        env.fake.cancel_calls.append(agent_id)
        env.fake.tasks[agent_id].pop()
        raise RuntimeError('synthetic failure after one cancellation')
    env.monkeypatch.setattr(env.fake, 'cancel_agent_tasks', partial_then_raise)
    response = _stop(env, 'admin-1', 'a1', 'verifier-partial-cancel')
    assert len(env.fake.tasks['a1']) == 1
    assert response.status_code == 503, response.text
    detail = response.json()['detail']
    assert detail['verification']['effect'] == 'unknown'
    assert detail['verification']['replay'] == 'do_not_repeat'
    assert _audits(env) == []
