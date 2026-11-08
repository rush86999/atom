"""Current user scope must agree with the real workspace's tenant authority."""
import pytest
from tests.test_bpe_current_principal_scope import actors,_post_note


def test_current_actor_cannot_reenter_workspace_with_contradictory_tenant(actors):
    from core.models import Tenant,User
    first=_post_note(actors,{'content':'original workspace-owned insight'})
    assert first.json()['data']['buffered']==1,first.text
    with actors.Session() as db:
        db.add(Tenant(id='new-tenant',name='scratch-new',subdomain='new-tenant-probe'));db.commit()
        row=db.get(User,'bpe-user-a');row.tenant_id='new-tenant';db.commit()
    # User's old workspace still belongs to bpe-tenant. The fresh identity is
    # contradictory, not permission to enter the old workspace's namespace.
    response=_post_note(actors,{'content':'must not append to the old namespace'})
    assert response.json()['data'].get('success') is False,response.json()
    snap=actors.workspace.get_workspace_snapshot('bpe-ws-a','atom_main','user:bpe-user-a')
    assert snap['pending_notes']==['original workspace-owned insight'],snap


def test_matching_current_user_and_workspace_valid_twin(actors):
    from core.models import Tenant,User,Workspace
    with actors.Session() as db:
        db.add(Tenant(id='new-tenant',name='scratch-new',subdomain='new-tenant-probe'));db.commit()
        db.add(Workspace(id='new-ws',name='scratch-new',tenant_id='new-tenant'));db.commit()
        row=db.get(User,'bpe-user-a');row.tenant_id='new-tenant';row.workspace_id='new-ws';db.commit()
    response=_post_note(actors,{'content':'authorized matching current namespace'})
    assert response.status_code==200 and response.json()['data']['success'] is True,response.text
    assert response.json()['data']['buffered']==1,response.json()
