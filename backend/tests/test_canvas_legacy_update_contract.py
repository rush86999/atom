"""Legacy tool updates must join the existing durable verified writer."""
import pytest
from unittest.mock import AsyncMock
from core.models import CanvasAudit
from tests.test_canvas_present_revision_contract import present_world, invoke

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,patch,expected", [
    ("markdown", {"content":"Changed"}, "Changed"),
    ("chart", {"data":[]}, []),
    ("specialized", {"content":""}, {"content":""}),
])
async def test_update_is_durable_and_revision_guarded(present_world,monkeypatch,kind,patch,expected):
    tool,user,db=present_world
    monkeypatch.setattr(tool.ws_manager,"broadcast",AsyncMock())
    created=await invoke(tool,kind,user.id)
    result=await tool.update_canvas(user.id,created["canvas_id"],patch,expected_prior_audit_id=created["audit_id"],operation_id="legacy-update-"+kind)
    assert result["success"] is True,result
    assert result.get("audit_id") and result["audit_id"]!=created["audit_id"]
    from tools.canvas_crud_tool import read_canvas
    current=await read_canvas(user.id,created["canvas_id"])
    assert current["content"]==expected
    assert current["revision_audit_id"]==result["audit_id"]
    before=db.query(CanvasAudit).count()
    replay=await tool.update_canvas(user.id,created["canvas_id"],patch,expected_prior_audit_id=created["audit_id"],operation_id="legacy-update-"+kind)
    assert replay["success"] is True,replay
    assert db.query(CanvasAudit).count()==before

@pytest.mark.asyncio
async def test_missing_revision_refuses_without_frame_or_audit(present_world,monkeypatch):
    tool,user,db=present_world
    frames=AsyncMock();monkeypatch.setattr(tool.ws_manager,"broadcast",frames)
    created=await invoke(tool,"markdown",user.id);frames.reset_mock()
    before=db.query(CanvasAudit).count()
    result=await tool.update_canvas(user.id,created["canvas_id"],{"content":"Unsafe"})
    assert result["success"] is False,result
    assert result.get("error_code")=="CANVAS_REVISION_REQUIRED"
    assert db.query(CanvasAudit).count()==before
    frames.assert_not_awaited()

@pytest.mark.asyncio
async def test_unknown_target_has_no_update_frame(present_world,monkeypatch):
    tool,user,db=present_world
    frames=AsyncMock();monkeypatch.setattr(tool.ws_manager,"broadcast",frames)
    result=await tool.update_canvas(user.id,"does-not-exist",{"content":"Unsafe"})
    assert result["success"] is False,result
    frames.assert_not_awaited()

@pytest.mark.asyncio
async def test_authority_change_after_writer_read_refuses(present_world,monkeypatch):
    from core.models import User
    from sqlalchemy import update
    import tools.canvas_crud_tool as crud
    tool,user,db=present_world
    frames=AsyncMock();monkeypatch.setattr(tool.ws_manager,"broadcast",frames)
    created=await invoke(tool,"markdown",user.id);frames.reset_mock()
    read=crud.active_canvas_actor
    calls=0
    def raced(session,actor_id):
        nonlocal calls
        actor=read(session,actor_id);calls+=1
        if calls==2:
            session.execute(update(User).where(User.id==actor_id).values(is_active=False).execution_options(synchronize_session=False));session.commit()
        return actor
    monkeypatch.setattr(crud,"active_canvas_actor",raced)
    before=db.query(CanvasAudit).count()
    result=await tool.update_canvas(user.id,created["canvas_id"],{"content":"Unsafe"},expected_prior_audit_id=created["audit_id"])
    assert result["success"] is False,result
    db.expire_all();assert db.get(User,user.id).is_active is False
    assert db.query(CanvasAudit).count()==before
    frames.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("fail_projection",[False,True])
async def test_king_threads_revision_and_stops_projection_on_conflict(monkeypatch,fail_projection):
    from types import SimpleNamespace
    import core.agents.king_agent as king
    present=AsyncMock(return_value={"success":True,"canvas_id":"plan","audit_id":"revision-0"})
    updates=[]
    async def update(**kwargs):
        updates.append(kwargs)
        if fail_projection:return {"success":False,"error_code":"CONFLICT"}
        return {"success":True,"audit_id":"revision-"+str(len(updates))}
    monkeypatch.setattr(king,"present_markdown",present);monkeypatch.setattr(king,"update_canvas",update)
    fake=SimpleNamespace(queen=SimpleNamespace(generate_mermaid=lambda *_:"graph TD; A-->B"),_execute_node=AsyncMock(return_value={"value":"done"}))
    result=await king.KingAgent.execute_blueprint(fake,{"architecture_name":"Plan","nodes":[{"id":"A","name":"A","type":"agent","dependencies":[]}]},{"user_id":"owner","tenant_id":"t1"})
    assert updates[0]["expected_prior_audit_id"]=="revision-0"
    if fail_projection:
        assert len(updates)==1
        assert result["canvas_projection_error"]=="CONFLICT"
    else:
        assert len(updates)==2
        assert updates[1]["expected_prior_audit_id"]=="revision-1"
        assert result["canvas_projection_error"] is None
