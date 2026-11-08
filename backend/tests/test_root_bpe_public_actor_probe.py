"""Root admitted-route actor probe; controlled reasoning, real tool and stores."""
import importlib
import json
import pytest
from core.models import User
from core.react_models import ReActStep, ToolCall
from tests.test_agent_run_outcome_join_contract import real_env, _run
from tests.test_agent_generic_information_wait import _seed_board, _install_model

@pytest.mark.parametrize("revoke", [False, True])
def test_public_note_respects_actor_revocation_at_tool_time(real_env, monkeypatch, tmp_path, revoke):
    import core.bpe.actions as actions
    import core.bpe.persistence as persistence
    from core.bpe.workspace import reset_registry
    importlib.reload(actions)
    root = tmp_path / 'public_bpe'
    monkeypatch.setenv('ATOM_BPE_WORKSPACE_ENABLED', 'true')
    monkeypatch.setattr(persistence, 'DATA_DIR', root)
    reset_registry()
    _seed_board(real_env)
    import core.generic_agent as generic
    import core.intervention_service as interventions
    from core.models import HITLAction
    with real_env.SessionLocal() as db:
        db.add(User(id='root-reviewer', email='root-reviewer@example.invalid', first_name='Root', last_name='Reviewer', role='team_lead', status='active', is_active=True, tenant_id='t1', workspace_id='ws1'))
        db.commit()
    monkeypatch.setattr(interventions, 'get_db_session', real_env.db_session)
    original_wait = generic.GenericAgent._wait_for_approval
    async def reviewed_then_real_wait(self, action_id):
        # The real service checks the real reviewer's policy; no approval
        # verdict or production polling consumer is replaced.
        result = await interventions.InterventionService().approve_intervention(action_id, 'root-reviewer')
        assert result.get('success') is True, result
        with real_env.SessionLocal() as db:
            row = db.get(HITLAction, action_id)
            assert row.status == 'approved' and row.reviewed_by == 'root-reviewer'
        return await original_wait(self, action_id)
    monkeypatch.setattr(generic.GenericAgent, '_wait_for_approval', reviewed_then_real_wait)
    trace = []
    original_call = generic.mcp_service.call_tool
    async def observed_call(*args, **kwargs):
        try:
            result = await original_call(*args, **kwargs)
            trace.append({'type': type(result).__name__, 'result': str(result)[:1200]})
            return result
        except Exception as exc:
            trace.append({'exception_class': type(exc).__name__})
            raise
    monkeypatch.setattr(generic.mcp_service, 'call_tool', observed_call)
    marker = 'root-public-note-authority-marker'
    def first(task_input, history, context):
        if revoke:
            with real_env.SessionLocal() as db:
                user = db.get(User, 'member-1')
                user.status = 'disabled'
                user.is_active = False
                db.commit()
        return ReActStep(thought='Record the admitted task fact', action=ToolCall(tool='workspace.note', params={'content': marker}))
    _install_model(monkeypatch, [first])
    response = _run(real_env, operation_id='root-public-note-'+str(revoke), parameters={'sync': True, 'task_input': 'Record a task fact'})
    records = [json.loads(p.read_text()) for p in root.glob('*.json')]
    wrote = marker in json.dumps(records)
    capture = {'revoked': revoke, 'http': response.status_code, 'persisted_marker': wrote, 'transport_trace': trace}
    try:
        assert wrote is (not revoke), capture
    finally:
        reset_registry()
