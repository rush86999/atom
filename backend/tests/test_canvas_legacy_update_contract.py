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

@pytest.mark.asyncio
@pytest.mark.parametrize('patch',[{'color':'red'},{'content':'x','data':[]},{'user_id':'other','content':'x'}])
async def test_invalid_patch_never_partially_writes(present_world,monkeypatch,patch):
    tool,user,db=present_world
    frames=AsyncMock();monkeypatch.setattr(tool.ws_manager,'broadcast',frames)
    created=await invoke(tool,'markdown',user.id);frames.reset_mock()
    before=db.query(CanvasAudit).count()
    result=await tool.update_canvas(user.id,created['canvas_id'],patch,expected_prior_audit_id=created['audit_id'])
    assert result['success'] is False and result['error_code']=='INVALID_CANVAS_PATCH'
    assert db.query(CanvasAudit).count()==before
    frames.assert_not_awaited()

@pytest.mark.asyncio
async def test_stale_planned_revision_retains_current_user_edit(present_world,monkeypatch):
    tool,user,db=present_world
    frames=AsyncMock();monkeypatch.setattr(tool.ws_manager,'broadcast',frames)
    created=await invoke(tool,'markdown',user.id)
    first=await tool.update_canvas(user.id,created['canvas_id'],{'content':'User current'},expected_prior_audit_id=created['audit_id'])
    assert first['success'],first
    frames.reset_mock();before=db.query(CanvasAudit).count()
    stale=await tool.update_canvas(user.id,created['canvas_id'],{'content':'Stale plan'},expected_prior_audit_id=created['audit_id'])
    assert stale['success'] is False and stale.get('conflict'),stale
    from tools.canvas_crud_tool import read_canvas
    assert (await read_canvas(user.id,created['canvas_id']))['content']=='User current'
    assert db.query(CanvasAudit).count()==before
    frames.assert_not_awaited()

@pytest.mark.asyncio
async def test_foreign_owner_never_receives_or_writes_a_frame(present_world,monkeypatch):
    from tests.test_covpush_canvasroutes import _make_user
    tool,user,db=present_world
    frames=AsyncMock();monkeypatch.setattr(tool.ws_manager,'broadcast',frames)
    created=await invoke(tool,'markdown',user.id);frames.reset_mock()
    peer=_make_user(db);before=db.query(CanvasAudit).count()
    result=await tool.update_canvas(peer.id,created['canvas_id'],{'content':'Foreign'},expected_prior_audit_id=created['audit_id'])
    assert result['success'] is False,result
    assert db.query(CanvasAudit).count()==before
    frames.assert_not_awaited()

@pytest.mark.asyncio
async def test_unverified_commit_is_not_tool_success_and_keeps_receipt(present_world,monkeypatch):
    import core.canvas_write_service as service
    tool,user,db=present_world
    monkeypatch.setattr(tool.ws_manager,'broadcast',AsyncMock())
    created=await invoke(tool,'markdown',user.id)
    monkeypatch.setattr(service,'validate',AsyncMock(return_value=None))
    result=await tool.update_canvas(user.id,created['canvas_id'],{'content':'Committed'},expected_prior_audit_id=created['audit_id'],operation_id='uncertain-operation')
    assert result['success'] is False,result
    assert result['status']=='committed_unverified'
    assert result['operation_id']=='uncertain-operation' and result['audit_id']
    assert result['verification']['effect']=='committed'
    assert result['verification']['replay']=='do_not_repeat'
    assert db.query(CanvasAudit).filter_by(id=result['audit_id']).one().details_json['content']=='Committed'

@pytest.mark.asyncio
@pytest.mark.parametrize('has_revision',[True,False])
async def test_real_deep_link_update_threads_explicit_plan_revision(present_world,monkeypatch,has_revision):
    from core.deeplinks import DeepLink,execute_canvas_deep_link
    tool,user,db=present_world
    monkeypatch.setattr(tool.ws_manager,'broadcast',AsyncMock())
    created=await invoke(tool,'markdown',user.id)
    params={'action':'update','params':{'content':'Linked body'},'operation_id':'deep-link-operation'}
    if has_revision:params['expected_prior_audit_id']=created['audit_id']
    link=DeepLink('atom','canvas',created['canvas_id'],params,'atom://canvas/'+created['canvas_id'])
    result=await execute_canvas_deep_link(link,user.id,db)
    assert result['success'] is has_revision,result
    from tools.canvas_crud_tool import read_canvas
    assert (await read_canvas(user.id,created['canvas_id']))['content']==('Linked body' if has_revision else 'Current body')

@pytest.mark.asyncio
async def test_empty_title_is_an_exact_supported_edit(present_world,monkeypatch):
    tool,user,db=present_world
    monkeypatch.setattr(tool.ws_manager,'broadcast',AsyncMock())
    created=await invoke(tool,'markdown',user.id)
    result=await tool.update_canvas(user.id,created['canvas_id'],{'title':''},expected_prior_audit_id=created['audit_id'])
    assert result['success'] is True,result
    from tools.canvas_crud_tool import read_canvas
    current=await read_canvas(user.id,created['canvas_id'])
    assert current['title']=='' and current['content']=='Current body'

@pytest.mark.asyncio
async def test_same_operation_cannot_change_only_title(present_world,monkeypatch):
    tool,user,db=present_world
    monkeypatch.setattr(tool.ws_manager,'broadcast',AsyncMock())
    created=await invoke(tool,'markdown',user.id)
    first=await tool.update_canvas(user.id,created['canvas_id'],{'title':'First'},expected_prior_audit_id=created['audit_id'],operation_id='title-operation')
    assert first['success'] is True,first
    before=db.query(CanvasAudit).count()
    changed=await tool.update_canvas(user.id,created['canvas_id'],{'title':'Different'},expected_prior_audit_id=created['audit_id'],operation_id='title-operation')
    assert changed['success'] is False,changed
    assert db.query(CanvasAudit).count()==before

@pytest.mark.asyncio
async def test_correct_body_but_wrong_title_cannot_verify(present_world,monkeypatch):
    import core.canvas_write_service as service
    from core.models import Canvas
    tool,user,db=present_world
    monkeypatch.setattr(tool.ws_manager,'broadcast',AsyncMock())
    created=await invoke(tool,'markdown',user.id)
    write=service.update_canvas_content
    async def wrong_title(**kwargs):
        result=await write(**kwargs)
        db.query(Canvas).filter_by(id=created['canvas_id']).update({'name':'Wrong title'})
        db.commit()
        return result
    monkeypatch.setattr(service,'update_canvas_content',wrong_title)
    result=await tool.update_canvas(user.id,created['canvas_id'],{'title':'Authorized'},expected_prior_audit_id=created['audit_id'])
    assert result['success'] is False and result['status']=='committed_unverified',result
    assert result['verification']['effect']=='committed'


def test_real_registry_exposes_planned_revision_and_safe_usage():
    from tools.registry import ToolRegistry
    registry=ToolRegistry();registry._register_canvas_tools()
    metadata=registry.get('update_canvas')
    assert metadata.version=='2.0.0'
    assert 'expected_prior_audit_id' in metadata.to_dict()['parameters']
    assert 'revision_audit_id' in metadata.description
    assert 'expected_prior_audit_id' in metadata.examples[0]['code']
    simplified=next(t for t in registry.get_simplified_tools() if t['name']=='update_canvas')
    assert 'expected_prior_audit_id' in simplified['parameters']
    assert 'missing or stale revisions refuse' in simplified['description']
