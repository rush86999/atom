import importlib.util,sys,pytest,io
from docx import Document
from core.models import User,Tenant,Workspace,Canvas
s=importlib.util.spec_from_file_location("root_office_original_boundary","/private/tmp/root-canvas-office-independent-20261110.py");f=importlib.util.module_from_spec(s);sys.modules[s.name]=f;s.loader.exec_module(f)
world=f.world
@pytest.mark.parametrize("target",["default","foreign_tenant","foreign_workspace"])
def test_null_personal_actor_default_only_document_download(world,target):
 old_tenant,old_ws=world.tenant,world.ws
 with world.Session() as db:
  db.add(Tenant(id="default",name="Default",subdomain="root-office-null",edition="personal",is_active=True));db.add(Workspace(id="default",name="Default",tenant_id="default"))
  user=db.get(User,world.user);user.tenant_id=None;user.workspace_id=None;db.commit()
 world.tenant="default" if target!="foreign_tenant" else old_tenant
 world.ws="default" if target!="foreign_workspace" else old_ws
 cid,aid=world.create_canvas(content="# Actual result\n\nControlled total 61.25 USD.\n")
 response=f.export(world,cid,aid)
 if target=="default":
  assert response.status_code==200,{"status":response.status_code}
  assert "Controlled total 61.25 USD." in [p.text for p in Document(io.BytesIO(response.content)).paragraphs]
 else:
  assert response.status_code in (403,404),{"status":response.status_code,"target":target}
  assert response.headers.get("content-disposition") is None
 with world.Session() as db:
  user=db.get(User,world.user);assert user.tenant_id is None and user.workspace_id is None
