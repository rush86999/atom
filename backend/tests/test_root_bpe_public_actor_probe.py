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
    capture = {'revoked': revoke, 'http': response.status_code, 'persisted_marker': wrote}
    try:
        assert wrote is (not revoke), capture
    finally:
        reset_registry()
