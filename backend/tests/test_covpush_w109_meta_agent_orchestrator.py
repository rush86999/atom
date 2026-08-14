# -*- coding: utf-8 -*-
"""Coverage wave 109 — core/meta_agent_orchestrator.py (never-tested stub,
56% import baseline -> target 100%; fully mocked, no LLM, no network).

- MetaAgentOrchestrator: init with/without deps, orchestrate_ontology_management
  (default + explicit trigger_type), trigger_on_ingestion, close/context-manager.
- get_meta_agent_orchestrator: db passthrough (fresh instance), singleton reuse
  with no db, singleton reset between tests.
"""
import asyncio
from unittest.mock import MagicMock

from core.meta_agent_orchestrator import (
    MetaAgentOrchestrator,
    _default_orchestrator,
    get_meta_agent_orchestrator,
)


def _reset_singleton():
    global _default_orchestrator
    import core.meta_agent_orchestrator as m
    m._default_orchestrator = None


class TestOrchestratorStub:
    def test_init_no_deps(self):
        orch = MetaAgentOrchestrator()
        assert orch.db is None

    def test_init_with_deps(self):
        db = MagicMock()
        orch = MetaAgentOrchestrator(db=db, schema_ai_service="s", entity_type_service="e",
                                     entity_skill_service="k")
        assert orch.db is db

    def test_orchestrate_ontology_management_default_trigger(self):
        orch = MetaAgentOrchestrator()
        result = asyncio.get_event_loop().run_until_complete(
            orch.orchestrate_ontology_management("t1", {})
        )
        assert result["orchestration_id"] == "stub-id"
        assert result["status"] == "active"
        assert result["suggestions"] == []
        assert result["trigger_type"] == "manual"

    def test_orchestrate_ontology_management_explicit_trigger(self):
        orch = MetaAgentOrchestrator()
        result = asyncio.get_event_loop().run_until_complete(
            orch.orchestrate_ontology_management("t1", {"trigger_type": "ingestion"})
        )
        assert result["trigger_type"] == "ingestion"

    def test_trigger_on_ingestion(self):
        orch = MetaAgentOrchestrator()
        result = asyncio.get_event_loop().run_until_complete(
            orch.trigger_on_ingestion({"doc_id": "d1"})
        )
        assert result == {"patterns_detected": 0, "suggestions_created": 0,
                          "suggestions_stored": 0}

    def test_close_and_context_manager(self):
        orch = MetaAgentOrchestrator()
        assert orch.close() is None
        with MetaAgentOrchestrator() as cm:
            assert isinstance(cm, MetaAgentOrchestrator)
        assert cm.close() is None

    def test_context_manager_exit_calls_close(self):
        orch = MetaAgentOrchestrator()
        assert orch.__exit__(None, None, None) is None


class TestGetOrchestrator:
    def test_with_db_creates_fresh(self):
        _reset_singleton()
        db = MagicMock()
        orch = get_meta_agent_orchestrator(db=db)
        assert orch.db is db
        orch2 = get_meta_agent_orchestrator(db=MagicMock())
        assert orch2 is not orch

    def test_singleton_without_db(self):
        _reset_singleton()
        a = get_meta_agent_orchestrator()
        b = get_meta_agent_orchestrator()
        assert a is b
        _reset_singleton()
