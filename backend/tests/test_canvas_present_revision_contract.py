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
    broadcast.assert_not_awaited()
    assert db.query(CanvasAudit).count() == 0
