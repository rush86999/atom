import re
import pytest
from sqlalchemy import event,func
from tests.api.test_agent_spawn_goal14 import world,_client,_token,_post
from core.models import User,AgentRegistry,AuditLog

@pytest.mark.parametrize('change',['deactivate','demote','scope'])
def test_current_authority_changes_at_actual_spawn_claim_refuse(world,change):
 fired=[]
 def race(conn,cursor,statement,parameters,context,executemany):
  normal=re.sub(r'\s+','',statement.lower()).replace('"','')
  if fired or not normal.startswith('updateuserssetupdated_at=users.updated_at'):return
  fired.append(True)
  with world['Session']() as peer:
   user=peer.get(User,'admin')
   if change=='deactivate':user.is_active=False;user.status='inactive'
   elif change=='demote':user.role='member'
   else:user.tenant_id='other';user.workspace_id='ws-b'
   peer.commit()
 event.listen(world['engine'],'before_cursor_execute',race)
 try:
  client=_client(world);token=_token(world,'admin')
  response=_post(client,token,{'template':'finance_analyst','persist':True},operation_id='root-spawn-'+change)
 finally:event.remove(world['engine'],'before_cursor_execute',race)
 assert len(fired)==1,'Decisive actual actor-claim SQL was not exercised'
 assert response.status_code==409,response.text
 assert response.json()['detail']['error']['code']=='AUTHORITY_CHANGED'
 with world['Session']() as db:
  assert db.query(func.count(AgentRegistry.id)).filter(AgentRegistry.name=='Finance Analyst').scalar()==0
  assert db.get(AuditLog,'agent:create:root-spawn-'+change) is None
  user=db.get(User,'admin')
  if change=='deactivate':assert user.is_active is False and user.status=='inactive'
  elif change=='demote':assert user.role=='member'
  else:assert user.tenant_id=='other' and user.workspace_id=='ws-b'
