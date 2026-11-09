"""A durable editable presentation must exist before its revision is published."""
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
from core.models import CanvasAudit
from tests.test_covpush_canvasroutes import _make_user


@pytest.fixture
def present_world(db_session, monkeypatch):
    import tools.canvas_tool as tool
    user = _make_user(db_session)
    @contextmanager
    def db():
        yield db_session
    monkeypatch.setattr('core.database.get_db_session', db)
    # Durability must not disappear when optional governance enforcement is off.
    monkeypatch.setattr(tool.FeatureFlags, 'should_enforce_governance', lambda _: False)
    return tool, user, db_session


async def invoke(tool, kind, user_id):
    if kind == 'markdown':
        return await tool.present_markdown(user_id, 'Current body', title='Draft')
    if kind == 'chart':
        return await tool.present_chart(user_id, 'bar_chart', [{'x':'A','y':2}], title='Draft')
    return await tool.present_specialized_canvas(user_id, 'docs', 'rich_editor', {'content':'Current body'}, title='Draft')


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['markdown','chart','specialized'])
async def test_present_publishes_only_a_committed_exact_revision(present_world, monkeypatch, kind):
    tool, user, db = present_world
    observed = []
    async def capture(channel, message):
        frame = message['data']
        row = db.query(CanvasAudit).filter(CanvasAudit.canvas_id == frame['canvas_id']).first()
        observed.append((frame, None if row is None else row.id))
    monkeypatch.setattr(tool.ws_manager, 'broadcast', capture)
    result = await invoke(tool, kind, user.id)
    assert result['success'] is True, result
    assert observed
    from tools.canvas_crud_tool import read_canvas
    durable = await read_canvas(user.id, result['canvas_id'])
    assert durable['success'] is True
    assert durable['revision_audit_id'] == result['audit_id']
    if kind == 'markdown':
        assert durable['canvas_type'] == 'markdown'
        assert durable['content'] == 'Current body'
    elif kind == 'chart':
        assert durable['canvas_type'] == 'bar_chart'
        assert durable['content'] == [{'x':'A','y':2}]
    else:
        assert durable['canvas_type'] == 'docs'
        assert durable['content'] == {'content':'Current body'}
    for frame, committed_id in observed:
        assert committed_id is not None, 'content published before durable audit'
        assert frame.get('revision_audit_id') == committed_id
        assert result.get('audit_id') == committed_id


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['markdown','chart','specialized'])
async def test_no_presentation_or_success_when_audit_cannot_be_persisted(present_world, monkeypatch, kind):
    tool, user, db = present_world
    monkeypatch.setattr(tool, '_create_canvas_audit', AsyncMock(return_value=None))
    broadcast = AsyncMock()
    monkeypatch.setattr(tool.ws_manager, 'broadcast', broadcast)
    result = await invoke(tool, kind, user.id)
    assert result['success'] is False
    assert result['status'] == 'not_applied'
    assert result['verification']['effect'] == 'none'
    broadcast.assert_not_awaited()
    assert db.query(CanvasAudit).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['markdown','chart','specialized'])
@pytest.mark.parametrize('seam', ['refresh','commit_confirmation'])
async def test_committed_or_unknown_presentation_keeps_original_identity(present_world, monkeypatch, caplog, kind, seam):
    tool, user, db = present_world
    broadcast = AsyncMock()
    monkeypatch.setattr(tool.ws_manager, 'broadcast', broadcast)
    secret = 'private-content-sentinel-not-for-logs'
    if seam == 'refresh':
        refresh = db.refresh
        def lose_readback(row, *args, **kwargs):
            if isinstance(row, CanvasAudit):
                raise RuntimeError(secret)
            return refresh(row, *args, **kwargs)
        monkeypatch.setattr(db, 'refresh', lose_readback)
    else:
        commit = db.commit
        def lose_confirmation():
            audit_pending = any(isinstance(row, CanvasAudit) for row in db.new)
            commit()
            if audit_pending:
                raise RuntimeError(secret)
        monkeypatch.setattr(db, 'commit', lose_confirmation)
    result = await invoke(tool, kind, user.id)
    rows = db.query(CanvasAudit).all()
    assert len(rows) == 1
    assert result['success'] is False
    assert result['status'] == ('committed_unverified' if seam == 'refresh' else 'effect_unknown')
    assert result['audit_id'] == rows[0].id
    assert result['canvas_id'] == rows[0].canvas_id
    assert result['replay'] == 'do_not_repeat'
    broadcast.assert_not_awaited()
    assert secret not in caplog.text
    assert secret not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['markdown','chart','specialized'])
async def test_broadcast_failure_never_loses_a_committed_receipt(present_world, monkeypatch, caplog, kind):
    tool, user, db = present_world
    secret = 'private-broadcast-sentinel-not-for-logs'
    monkeypatch.setattr(tool.ws_manager, 'broadcast', AsyncMock(side_effect=RuntimeError(secret)))
    result = await invoke(tool, kind, user.id)
    rows = db.query(CanvasAudit).all()
    assert len(rows) == 1
    assert result['success'] is False
    assert result['status'] == 'committed_unverified'
    assert result['audit_id'] == rows[0].id
    assert result['replay'] == 'do_not_repeat'
    assert secret not in caplog.text
    assert secret not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['markdown','chart','specialized'])
async def test_definite_no_effect_finishes_attempt_without_crediting_model_failure(present_world, monkeypatch, kind):
    from core.models import AgentExecution
    from tests.test_covpush_canvasroutes import _make_agent
    tool, user, db = present_world
    agent = _make_agent(db)
    monkeypatch.setattr(tool.FeatureFlags, 'should_enforce_governance', lambda _: True)
    monkeypatch.setattr(tool, '_create_canvas_audit', AsyncMock(return_value=None))
    if kind == 'markdown':
        result = await tool.present_markdown(user.id, 'Body', agent_id=agent.id)
    elif kind == 'chart':
        result = await tool.present_chart(user.id, 'bar_chart', [{'x':'A','y':2}], agent_id=agent.id)
    else:
        result = await tool.present_specialized_canvas(user.id, 'docs', 'rich_editor', {'content':'Body'}, agent_id=agent.id)
    assert result['success'] is False
    assert result['verification']['effect'] == 'none'
    db.expire_all()
    attempts = db.query(AgentExecution).filter(AgentExecution.agent_id == agent.id).all()
    assert len(attempts) == 1
    assert attempts[0].status == 'failed'
    assert attempts[0].completed_at is not None
    assert db.query(CanvasAudit).count() == 0
