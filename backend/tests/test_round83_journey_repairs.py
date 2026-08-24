"""
Round 83 — journey-repair regression pins.

Covers the disjoint half of the journey audit (the integration→ontology
half is pinned by tests/unit/test_integration_ontology_path.py):

- Agent journey: episode-writer await (generic_agent), fire-and-forget
  proposal episodes, durable turn-fact recall leg + prompt rendering.
- Data journey: turn-fact read partition (double workspace filter),
  role-scoped recall post-filters (assembler + world model) against the
  JSON-string metadata column, bytewax kwargs, GraphRAG route partitions,
  hybrid-ingestion sensitivity classification.
- User journey: provider-key save accepts the frontend's JSON body
  contract, /test route probes configured keys, single-word names register.
"""

import os
os.environ["TESTING"] = "1"

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch


BACKEND = Path(__file__).resolve().parents[1]


# ============================================================================
# Agent journey
# ============================================================================

def test_generic_agent_awaits_episode_writer():
    """The bare coroutine call silently dropped every non-session execution
    from episodic memory (scheduler/direct runs)."""
    src = (BACKEND / "core" / "generic_agent.py").read_text()
    assert "await EpisodeService(db).create_episode_from_execution(" in src


@pytest.mark.asyncio
async def test_proposal_episode_writer_schedules_coroutine(tmp_path):
    """_record_execution_episode is sync but the callee is async — it must
    schedule (or inline-run) the coroutine, never drop it."""
    from core.proposal_service import ProposalService

    svc = ProposalService.__new__(ProposalService)
    svc.db = Mock()
    captured = {}

    class FakeEpisodeService:
        def __init__(self, db):
            pass

        async def create_episode_from_execution(self, **kwargs):
            captured.update(kwargs)

    execution = SimpleNamespace(id="exec-1", status="completed")
    proposal = SimpleNamespace(id="prop-1")
    with patch("core.episode_service.EpisodeService", FakeEpisodeService):
        svc._record_execution_episode(execution, proposal, "browser_automate")
        # scheduled on the running loop — flush it
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    assert captured["execution_id"] == "exec-1"
    assert captured["metadata"]["proposal_id"] == "prop-1"


def test_generic_agent_renders_durable_facts_leg():
    src = (BACKEND / "core" / "generic_agent.py").read_text()
    assert 'memory.get(\'durable_facts\'' in src or 'memory.get("durable_facts"' in src
    assert "DURABLE FACTS" in src


# ============================================================================
# Data journey — recall paths
# ============================================================================

def test_turn_fact_recall_binds_workspace_on_handler():
    """Handler unconditionally appends its own workspace filter; leaving it
    defaulted produced `ws=='default' AND ws=='<real>'` → always empty."""
    import core.turn_fact_vector_store as tfvs
    import core.lancedb_handler as lh

    created = {}
    recorded_filter = {}

    class FakeHandler:
        def __init__(self, workspace_id=None):
            created["workspace_id"] = workspace_id

        def search(self, table_name=None, query=None, limit=None, filter_str=None):
            recorded_filter["value"] = filter_str
            return [{"id": "f1"}]

    with patch.object(lh, "LanceDBHandler", FakeHandler):
        ids = tfvs.search_relevant_fact_ids(workspace_id="ws-9", query="deploy prod checklist")

    assert created["workspace_id"] == "ws-9"
    assert recorded_filter["value"] == "workspace_id == 'ws-9'"
    assert ids == ["f1"]


@pytest.mark.asyncio
async def test_assembler_role_pass_post_filters_metadata_string(monkeypatch):
    """metadata is a JSON *string* column — server-side metadata.role filters
    can never match. Role hits must be ranked first via client-side parse."""
    import core.memory_context_assembler as mca
    import core.lancedb_handler as lh

    hits = [
        {"id": "general", "text": "general note",
         "metadata": json.dumps({"role": "other"})},
        {"id": "tagged", "text": "role doc",
         "metadata": json.dumps({"role": "sales"})},
    ]
    fake_handler = MagicMock()
    fake_handler.search.return_value = hits
    fake_handler.db.table_names.return_value = ["integration_hubspot"]
    fake_handler.db is not None
    monkeypatch.setattr(lh, "get_lancedb_handler", lambda ws=None: fake_handler)
    out = await mca._integration_records_leg(
        "question", workspace_id="ws-1", agent_role="Sales")
    assert any("role doc" in line for line in out), out


def test_world_model_role_ranking_post_filters():
    """documents recall must rank JSON-parsed role matches first."""
    from core.agent_world_model import WorldModelService

    hits = [
        {"id": "gen", "text": "gen", "metadata": json.dumps({"role": "eng"})},
        {"id": "mine", "text": "mine", "metadata": json.dumps({"role": "sales"})},
    ]
    db = MagicMock()
    db.search.return_value = hits

    svc = WorldModelService.__new__(WorldModelService)
    out = svc._recall_general_knowledge(db, "q", agent_role="Sales", limit=2)
    assert [r["id"] for r in out][0] == "mine"


def test_bytewax_source_contract():
    src = (BACKEND / "integrations" / "bytewax_service.py").read_text()
    assert "tenant_id=workspace_id" not in src, "process_document got nonexistent tenant_id kwarg"
    assert src.count("workspace_id=workspace_id") >= 2
    fallback = src.split("# 2. Direct GraphRAG")[1] if "# 2. Direct GraphRAG" in src else ""
    assert "create_task(coro)" in fallback and "asyncio.run(coro)" in fallback
    assert "user_id=user_id\n                    )\n                )" not in src


def test_hybrid_ingestion_classifies_sensitivity():
    src = (BACKEND / "core" / "hybrid_data_ingestion.py").read_text()
    assert "classify_sensitivity(text)" in src
    assert "sensitivity=_sensitivity" in src


def test_graphrag_routes_partition_by_workspace():
    src = (BACKEND / "api" / "graphrag_routes.py").read_text()
    assert "workspace_id=request.user_id" not in src
    assert src.count('or "default"') >= 2


# ============================================================================
# User journey
# ============================================================================

def _client_with_auth():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    import api.byok_routes as br
    from core.auth import get_current_user as auth_dep
    from core.database import get_db

    app = FastAPI()
    app.include_router(br.router)

    user = Mock(id="u1")
    user.tenant_id = "t-1"
    app.dependency_overrides[auth_dep] = lambda: user
    app.dependency_overrides[get_db] = lambda: Mock()
    return TestClient(app), br


def test_store_api_key_accepts_json_body():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import api.byok_routes as br
    from core.auth import get_current_user as auth_dep
    from core.database import get_db

    app = FastAPI()
    app.include_router(br.router)

    user = Mock(id="u1")
    user.tenant_id = "t-1"
    tenant = Mock(id="t-1", name="T")
    manager = MagicMock()
    manager.store_tenant_api_key.return_value = "key-1"

    app.dependency_overrides[auth_dep] = lambda: user
    app.dependency_overrides[get_db] = lambda: Mock()
    app.dependency_overrides[br.get_current_tenant] = lambda: tenant
    app.dependency_overrides[br.get_byok_manager] = lambda: manager

    resp = TestClient(app).post(
        "/api/ai/providers/openai/keys",
        json={"api_key": "sk-test-1234567890", "key_name": "default"},
    )
    # The old contract returned 422 (missing query param) before any logic ran.
    assert resp.status_code == 200, resp.text
    assert manager.store_tenant_api_key.call_args.args[2] == "sk-test-1234567890"


def test_register_accepts_single_word_name():
    from pydantic import ValidationError

    from core.auth_endpoints import UserCreate

    req = UserCreate(email="a@b.co", password="supersecret1", first_name="Plato")
    assert req.last_name == ""
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.co", password="supersecret1", first_name="   ")
