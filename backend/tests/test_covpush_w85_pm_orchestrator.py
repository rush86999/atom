# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/pm_orchestrator (never-wave-tested).

Covers the Sales -> Delivery orchestration:
- provision_from_deal: deal-not-found; pm-generation failure (rollback);
  success (contract + project + stakeholders, optional external sync) —
  including the RED test proving the passed workspace_id is used instead of
  the hardcoded "default".
- _identify_stakeholders: entity filtering (person/contact/user kept, others
  dropped) + GraphRAG failure fallback.
- notify_startup: per-stakeholder kickoff log.

get_db_session + pm_engine + graphrag_engine + external_pm_sync all mocked;
real in-memory SQLite schema (no network, zero LLM spend).
"""
import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from sales.models import Deal  # noqa: F401 (register models)
from service_delivery.models import Contract  # noqa: F401 (register models)
import core.pm_orchestrator as pmo


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


class _CtxManager:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *exc):
        self._session.close()
        return False


def _make_deal(db, deal_id="deal-1", name="Acme Onboarding", value=50000.0):
    deal = Deal(
        id=deal_id,
        workspace_id="ws-1",
        name=name,
        value=value,
        currency="USD",
    )
    db.add(deal)
    db.commit()
    return deal


def _patch_globals(db, *, pm_result=None, stakeholders=None, sync_result=None):
    pm = MagicMock()
    pm.generate_project_from_nl = AsyncMock(
        return_value=pm_result if pm_result is not None
        else {"status": "success", "project_id": "proj-1", "name": "Acme Plan"}
    )
    graph = MagicMock()
    graph.query = MagicMock(return_value={
        "entities": stakeholders if stakeholders is not None else [
            {"name": "Alice", "type": "person"},
            {"name": "Bob", "type": "contact"},
            {"name": "Contract.pdf", "type": "document"},
        ],
    })
    sync = MagicMock()
    sync.sync_project_to_external = AsyncMock(return_value=sync_result or {"platform": "asana"})
    ctx = _CtxManager(db)
    return [
        patch.object(pmo, "get_db_session", return_value=ctx),
        patch.object(pmo, "pm_engine", pm),
        patch.object(pmo, "graphrag_engine", graph),
        patch.object(pmo, "external_pm_sync", sync),
    ], pm, graph, sync


class TestProvisionFromDeal:
    def test_deal_not_found(self, db):
        patches, _, _, _ = _patch_globals(db)
        with _Combined(patches):
            result = asyncio.run(pmo.PMOrchestrator().provision_from_deal("nope", "user-1"))
        assert result == {"status": "error", "message": "Deal not found"}

    def test_project_generation_failure_rolls_back(self, db):
        _make_deal(db)
        patches, pm, _, _ = _patch_globals(
            db, pm_result={"status": "error", "error": "llm exploded"}
        )
        with _Combined(patches):
            result = asyncio.run(pmo.PMOrchestrator().provision_from_deal("deal-1", "user-1"))
        assert result == {"status": "error",
                          "message": "Project generation failed: llm exploded"}
        assert db.query(Contract).count() == 0

    def test_success_default_workspace(self, db):
        _make_deal(db)
        patches, pm, graph, _ = _patch_globals(db)
        with _Combined(patches):
            result = asyncio.run(pmo.PMOrchestrator().provision_from_deal("deal-1", "user-1"))
        assert result["status"] == "success"
        assert result["project_id"] == "proj-1"
        assert result["project_name"] == "Acme Plan"
        assert result["stakeholders_identified"] == ["Alice", "Bob"]
        assert result["external_sync"] is None
        contract = db.query(Contract).filter(Contract.deal_id == "deal-1").first()
        assert contract is not None
        assert contract.name == "Contract for Acme Onboarding"
        assert contract.total_amount == 50000.0
        assert contract.currency == "USD"
        assert contract.type.value == "fixed_fee"
        assert contract.workspace_id == "default"
        pm.generate_project_from_nl.assert_awaited_once()
        prompt = pm.generate_project_from_nl.await_args.kwargs["prompt"]
        assert "Acme Onboarding" in prompt and "50000.0" in prompt
        graph.query.assert_called_once()
        assert graph.query.call_args.args[0] == "user-1"

    def test_uses_passed_workspace_id_not_hardcoded_default(self, db):
        # RED (TDD): workspace_id="ws-custom" was silently ignored — contract,
        # PM engine and external sync all received the hardcoded "default".
        _make_deal(db)
        patches, pm, _, sync = _patch_globals(db)
        with _Combined(patches):
            result = asyncio.run(pmo.PMOrchestrator().provision_from_deal(
                "deal-1", "user-1", workspace_id="ws-custom",
                external_platform="asana"
            ))
        assert result["status"] == "success"
        assert result["external_sync"] == {"platform": "asana"}
        contract = db.query(Contract).filter(Contract.deal_id == "deal-1").first()
        assert contract.workspace_id == "ws-custom"
        assert pm.generate_project_from_nl.await_args.kwargs["workspace_id"] == "ws-custom"
        sync.sync_project_to_external.assert_awaited_once_with(
            project_id="proj-1", platform="asana", workspace_id="ws-custom"
        )

    def test_external_sync_default_workspace(self, db):
        _make_deal(db)
        patches, _, _, sync = _patch_globals(db)
        with _Combined(patches):
            asyncio.run(pmo.PMOrchestrator().provision_from_deal(
                "deal-1", "user-1", external_platform="asana"
            ))
        sync.sync_project_to_external.assert_awaited_once_with(
            project_id="proj-1", platform="asana", workspace_id="default"
        )


class TestIdentifyStakeholders:
    def test_filters_entities_by_type(self, db):
        patches, _, graph, _ = _patch_globals(db)
        with _Combined(patches):
            stakeholders = asyncio.run(
                pmo.PMOrchestrator()._identify_stakeholders("Acme", "user-1")
            )
        assert stakeholders == ["Alice", "Bob"]
        assert "Acme" in graph.query.call_args.args[1]

    def test_no_matching_types_returns_empty(self, db):
        patches, _, graph, _ = _patch_globals(
            db, stakeholders=[{"name": "Report", "type": "document"}]
        )
        with _Combined(patches):
            stakeholders = asyncio.run(
                pmo.PMOrchestrator()._identify_stakeholders("Acme", "user-1")
            )
        assert stakeholders == []

    def test_graphrag_failure_returns_empty(self, db):
        patches, _, graph, _ = _patch_globals(db)
        graph.query.side_effect = RuntimeError("rag down")
        with _Combined(patches):
            stakeholders = asyncio.run(
                pmo.PMOrchestrator()._identify_stakeholders("Acme", "user-1")
            )
        assert stakeholders == []


class TestNotifyStartup:
    def test_logs_welcome_per_stakeholder(self, db, caplog):
        with caplog.at_level(logging.INFO, logger="core.pm_orchestrator"):
            asyncio.run(pmo.PMOrchestrator().notify_startup("proj-1", ["Alice", "Bob"]))
        messages = [r.message for r in caplog.records if r.name == "core.pm_orchestrator"]
        assert any("proj-1" in m and "Alice" in m for m in messages)
        assert any("proj-1" in m and "Bob" in m for m in messages)


class _Combined:
    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False
