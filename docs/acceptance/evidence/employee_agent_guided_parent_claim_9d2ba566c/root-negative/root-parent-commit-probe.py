import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location("guided_controls",Path("tests/api/test_agent_guided_create_goal14.py"));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
world=m.world

@pytest.mark.parametrize("change",["scope","maturity"])
def test_acting_agent_change_after_route_check_before_create_refuses(world,monkeypatch,change):
 from api import agent_onboarding_routes as route
 with world["Session"]() as db:
  a=db.get(m.AgentRegistry,"acting-agent");a.status="autonomous";a.confidence_score=0.99;db.commit()
 m._factory(monkeypatch);original=route._create_agent_decision
 def raced(db,**kwargs):
  with world["Session"]() as peer:
   a=peer.get(m.AgentRegistry,"acting-agent")
   if change=="scope":a.tenant_id="other";a.workspace_id="ws-b"
   else:a.status="student";a.confidence_score=0.1
   peer.commit()
  return original(db,**kwargs)
 monkeypatch.setattr(route,"_create_agent_decision",raced)
 response=m._post(m._client(world),m._token(world,"member"),{"goal":"Create with current acting authority","acting_agent_id":"acting-agent"},operation_id="root-parent-"+change)
 assert response.status_code in (202,403,404,409),response.text
 with world["Session"]() as db:
  assert db.query(m.AgentRegistry).filter(m.AgentRegistry.name==m.BLUEPRINT["name"]).count()==0
  assert db.get(m.AuditLog,"agent:create:root-parent-"+change) is None
