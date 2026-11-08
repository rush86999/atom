"""Root actor-authority interleavings after real lifecycle preflight; mounted API."""
import importlib.util
import pytest
p='/private/tmp/atom-current-claim-audit-20261107/docs/engineering/probes/canvas_lifecycle_scope_root_2026_11_07.py'
spec=importlib.util.spec_from_file_location('canvas_root_fixture',p);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
probe=base.probe
app_client=base.app_client
local_broadcast_only=base.local_broadcast_only

@pytest.mark.parametrize('operation',['delete','undelete'])
@pytest.mark.parametrize('change',['workspace','inactive'])
def test_actor_change_after_preflight_refuses_effect(app_client,probe,monkeypatch,operation,change,local_broadcast_only):
    from core.models import User
    import core.canvas_write_service as service
    actor=base._prepare_operation(app_client,probe,operation)
    with probe.Session() as db:base._workspace(db,'ws-moved','tenant-owner')
    before=base._snapshot(probe.Session,'probe-canvas');calls_before=len(local_broadcast_only)
    original=service._lifecycle_preflight;done=[]
    def interleave(*args,**kwargs):
        frozen=original(*args,**kwargs)
        if not done:
            with probe.Session() as db:
                current=db.get(User,actor.id)
                if change=='workspace':current.workspace_id='ws-moved'
                else:current.is_active=False
                db.commit()
            done.append(True)
        return frozen
    monkeypatch.setattr(service,'_lifecycle_preflight',interleave)
    response=base._invoke(app_client.client,operation)
    assert done
    assert response.status_code in (403,404,409),(response.status_code,response.json())
    assert base._snapshot(probe.Session,'probe-canvas')==before
    assert len(local_broadcast_only)==calls_before
    with probe.Session() as db:
        current=db.get(User,actor.id)
        assert current.workspace_id=='ws-moved' if change=='workspace' else current.is_active is False

@pytest.mark.parametrize('operation',['delete','undelete'])
def test_unchanged_actor_valid_twin(app_client,probe,operation):
    base._prepare_operation(app_client,probe,operation)
    response=base._invoke(app_client.client,operation)
    assert response.status_code==200 and response.json().get('success') is True,response.text
