import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock
from tests.test_goal9_ci_execution_contract import host,ordinary_handler
from core.models import TokenUsage,Tenant,Workspace

def test_two_ordinary_calls_have_distinct_durable_attempts(host,ordinary_handler,monkeypatch):
 from core.llm import byok_handler
 with host.Session() as db:
  db.add(Tenant(id="root-budget",name="Root",subdomain="root-budget"));db.add(Workspace(id="root-budget-ws",name="Root",tenant_id="root-budget"));db.commit()
 ordinary_handler.workspace_id="root-budget-ws";ordinary_handler.tenant_id="root-budget"
 monkeypatch.setattr(byok_handler,"get_pricing_fetcher",lambda:SimpleNamespace(estimate_cost=lambda *a,**k:0.25))
 client=ordinary_handler.clients["opencode-go"]
 client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="independent ordinary",reasoning_content=None),finish_reason="stop")],usage=SimpleNamespace(prompt_tokens=10,completion_tokens=5,total_tokens=15))
 for prompt in ["First independent call","Second independent call"]:assert asyncio.run(ordinary_handler.generate_response(prompt))=="independent ordinary"
 assert client.chat.completions.create.call_count==2
 with host.Session() as db:
  rows=db.query(TokenUsage).filter(TokenUsage.tenant_id=="root-budget").all();assert len(rows)==2
  assert len({r.attempt_id for r in rows})==2 and len({r.request_id for r in rows})==2
  import json
  observed=[dict(attempt_id=r.attempt_id,request_id=r.request_id,execution_id=r.execution_id,workspace_id=r.workspace_id,tenant_id=r.tenant_id,billed=r.billed,cost_usd=r.cost_usd,pricing_status=r.pricing_status,prompt_tokens=r.prompt_tokens,completion_tokens=r.completion_tokens) for r in rows]
  from pathlib import Path
  Path("/private/tmp/root-goal9-ordinary-row-observation-20261110.json").write_text(json.dumps(observed,indent=2)+"\n")
  assert all(r.execution_id is None and r.workspace_id=="root-budget-ws" and r.billed and r.cost_usd==0.25 for r in rows),observed

def test_actual_intent_commit_failure_dispatches_no_provider(host,ordinary_handler,monkeypatch):
 from core import database,spend_aggregation_service
 # This test owns its scratch failure marker; restore it at teardown.
 monkeypatch.setattr(spend_aggregation_service,"_SETTLEMENT_FAILURE_REASON",None)
 factory=host.Session
 def broken_session():
  session=factory()
  def fail():raise RuntimeError("controlled commit failure")
  session.commit=fail;return session
 monkeypatch.setattr(database,"SessionLocal",broken_session)
 ordinary_handler.clients["openai"]=MagicMock()
 from core.llm.byok_handler import AwaitableResult
 ordinary_handler.get_ranked_providers=lambda *a,**k:AwaitableResult([("opencode-go","deepseek-v4-flash"),("openai","gpt-4o")])
 result=asyncio.run(ordinary_handler.generate_response("No dispatch without durable intent"))
 assert ordinary_handler.clients["opencode-go"].chat.completions.create.call_count==0
 assert ordinary_handler.clients["openai"].chat.completions.create.call_count==0
 with host.Session() as db:assert db.query(TokenUsage).filter(TokenUsage.attempt_id.isnot(None)).count()==0
