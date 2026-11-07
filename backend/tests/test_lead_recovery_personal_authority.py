"""Independent personal-scope equivalence at the actual resume claim."""
import pytest
from tests.test_generic_information_wait_recovery_authority import world, _wait, _set_user, _resume_direct, _durable_state

@pytest.mark.parametrize('workspace', [None, '', 'default'])
def test_personal_actor_current_scope_matches_resolver_at_resume_claim(world, monkeypatch, workspace):
    target = _wait(world, actor_id='personal-admin', agent_id='personal-agent', workspace_id='default', tenant_id=None)
    _set_user(world, 'personal-admin', workspace_id=workspace)
    calls = []
    result = _resume_direct(world, target, monkeypatch, calls)
    assert result.get('resumed') is True, result
    assert len(calls) == 1
    assert calls[0]['context']['workspace_id'] == 'default'
    assert _durable_state(world, target)['job_status'] == 'success'


def test_missing_original_actor_is_not_replaced_by_answerer(world, monkeypatch):
    target = _wait(world, actor_id='')
    calls = []
    result = _resume_direct(world, target, monkeypatch, calls, reviewer_id='admin-1')
    assert result.get('resumed') is False, result
    assert calls == [], calls
    assert _durable_state(world, target)['job_status'] == 'waiting'
