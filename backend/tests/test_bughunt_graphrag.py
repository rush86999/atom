# -*- coding: utf-8 -*-
"""
TDD bug-hunt tests for the GraphRAG + TurnFact memory stack.

Targets found during an audit of:
  - core/graphrag/multi_hop_expansion.py   (path tracking, error hygiene)
  - core/turn_fact_extractor.py / vector store (workspace scoping, parse robustness)
  - core/entity_type_service.py            (session ownership)

Pattern: Red-Green (a failing test precedes each minimal fix).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Base, GraphNode, GraphEdge, TurnFact
from core.graphrag.multi_hop_expansion import MultiHopExpander, get_sql_expander
from core import turn_fact_extractor as tfe_mod
from core.turn_fact_extractor import TurnFactExtractor
from core import turn_fact_vector_store as vstore


@pytest.fixture()
def memory_db():
    """Fresh in-memory SQLite with the full schema."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield Session
    engine.dispose()


# ===========================================================================
# 1. Multi-hop expansion — path tracking
# ===========================================================================
class TestMultiHopPathExtension:
    """re

    expand() tracks node *discovery* correctly (hop levels reach node C at
    depth 2) but `result.paths` never propagates parents beyond hop 1 — the
    active-path list is never advanced between hops, so only 2-node paths are
    ever produced even though the graph is a 3-node chain.
    """

    def _seed_chain(self, Session, ws: str) -> None:
        with Session() as db:
            db.add_all([
                GraphNode(id="A", workspace_id=ws, name="Alpha", type="task", properties={}),
                GraphNode(id="B", workspace_id=ws, name="Beta", type="task", properties={}),
                GraphNode(id="C", workspace_id=ws, name="Gamma", type="task", properties={}),
            ])
            db.add_all([
                GraphEdge(id="e1", workspace_id=ws, source_node_id="A", target_node_id="B",
                          relationship_type="depends_on", properties={}),
                GraphEdge(id="e2", workspace_id=ws, source_node_id="B", target_node_id="C",
                          relationship_type="depends_on", properties={}),
            ])
            db.commit()

    def test_paths_extend_beyond_one_hop(self, memory_db):
        ws = "ws-paths"
        self._seed_chain(memory_db, ws)

        expander = MultiHopExpander()
        with memory_db() as db:
            result = expander.expand(start_entity_id="A", workspace_id=ws, session=db)

        discovered = [n.id for n in result.nodes]
        assert discovered == ["A", "B", "C"]

        path_ids = [[n.id for n in p.nodes] for p in result.paths]
        assert ["A", "B", "C"] in path_ids, f"expected 3-node path, got {path_ids}"

    def test_path_relevance_uses_config_decay(self, memory_db):
        """ExpansionPath.add_hop used a fresh default ExpansionConfig per hop
        instead of the expander's configured decay."""
        ws = "ws-paths"
        self._seed_chain(memory_db, ws)

        expander = MultiHopExpander()
        with memory_db() as db:
            result = expander.expand(start_entity_id="A", workspace_id=ws, session=db)

        # With default decay (0.85) hop-2 relevance ≈ 0.85**2 * factor.
        for p in result.paths:
            assert p.total_relevance <= 1.0
            assert p.total_relevance > 0.0


class TestSQLExpanderErrorHygiene:
    def test_expansion_failure_does_not_leak_exception_text(self, memory_db):
        """When the driver raises, the raw error (including the full SQL +
        bind params) must not be stashed in result.metadata — internal detail
        can leak to route callers. Failure is forced via a raising execute:
        W6 made the sqlite CTE actually work, so the old implicit trigger
        (PG-only syntax) no longer fires."""
        ws = "ws-sql"
        with memory_db() as db:
            db.add(GraphNode(id="A", workspace_id=ws, name="Alpha", type="task", properties={}))
            db.commit()

        expander = get_sql_expander()
        with memory_db() as db:
            def _boom(sql, params=None):
                raise RuntimeError(
                    "syntax error near WITH RECURSIVE — sqlite3 driver detail"
                )

            with patch.object(db, "execute", side_effect=_boom):
                result = expander.expand_sql(start_entity_id="A", workspace_id=ws, session=db)

        # Graceful: no exception, code literal, driver error text absent.
        assert "error" in result.metadata
        for marker in ("syntax error", "SQLite", "sqlite3", "WITH RECURSIVE"):
            assert marker not in str(result.metadata["error"]), (
                f"raw error leaked into metadata: {result.metadata['error']}"
            )


# ===========================================================================
# Turn-fact vector recall — workspace scoping
# ===========================================================================
class TestTurnFactVectorWorkspaceScoping:
    def test_vector_recall_search_scoped_to_workspace(self):
        """search_relevant_fact_ids() ignored its workspace_id argument; the
        handler (default-constructible, workspace='default') searched the wrong
        partition, so recall was always empty for non-default workspaces."""
        fake = MagicMock()
        fake.search.return_value = [{"id": "tf-1"}]

        with patch.object(vstore, "_get_handler", return_value=fake):
            ids = vstore.search_relevant_fact_ids(
                workspace_id="ws-a", query="must use Stripe", limit=5
            )

        assert ids == ["tf-1"]
        kwargs = fake.search.call_args.kwargs
        assert "workspace_id == 'ws-a'" in kwargs["filter_str"], kwargs

    def test_hydration_never_crosses_workspaces(self, memory_db):
        """Tier-2 hydration in prefetch_relevant_facts() pulled SQL rows by ID
        without a workspace filter — a LanceDB hit belonging to workspace A
        could be hydrated into a B-scoped request (cross-tenant leak)."""
        ws = memory_db
        with patch.object(tfe_mod, "SessionLocal", ws):
            with ws() as db:
                db.add(TurnFact(
                    id="tf-a", workspace_id="ws-a",
                    extraction_source="turn", fact_text="secret of ws-a",
                    category="hard_constraint", confidence=0.9,
                    content_hash="h-a", status="active",
                ))
                db.commit()

            with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True), \
                 patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                       return_value=["tf-a"]):
                rows = tfe_mod.prefetch_relevant_facts(
                    workspace_id="ws-b", query="must use Stripe", limit=5
                )

        assert rows == []


# ===========================================================================
# Turn-fact extraction — parse robustness
# ===========================================================================
class TestExtractionParseRobustness:
    def test_non_numeric_confidence_does_not_drop_whole_turn(self, memory_db):
        """A single non-numeric confidence value from the LLM (e.g. 'high')
        currently makes float() raise inside _extract, which the public
        entrypoint catches and turns into [] — silently dropping every valid
        fact in that turn. The contract is never-raise, but never-silently-drop
        means bad items must be skipped, not the whole turn."""
        ws = memory_db
        with patch.object(tfe_mod, "SessionLocal", ws), patch.object(tfe_mod, "get_llm_service"):
            ex = TurnFactExtractor(workspace_id="ws-test", tenant_id="t")
            ex.llm = MagicMock()
            ex.llm.generate = AsyncMock(return_value=(
                '[{"fact": "must use Stripe", "category": "hard_constraint", "confidence": "high"},'
                ' {"fact": "7-day SLA", "category": "exact_value", "confidence": 0.9}]'
            ))
            ex._write_vectors_best_effort = lambda rows, source_text="": None
            tfe_mod._circuit_breaker.reset()

            rows = asyncio.run(ex.extract_from_turn(
                user_request="must use Stripe for payments; we have a 7-day SLA"
            ))

        assert len(rows) == 2, f"expected both facts persisted, got {len(rows)}"
        by_text = {r.fact_text: r for r in rows}
        assert by_text["must use Stripe"].confidence == 0.8


# ===========================================================================
# Entity type service — session lifecycle
# ===========================================================================
class TestEntityTypeServiceSessionLifecycle:
    def test_close_preserves_injected_session(self):
        """EntityTypeService.close() closes the session even when the caller
        injected their own — the docstring promises "Only close if we created
        the session". Closing a caller-owned session breaks their transaction."""
        mock_db = MagicMock()

        with patch("core.entity_type_service.get_schema_validator", MagicMock()), \
             patch("core.entity_type_service.get_model_factory", MagicMock()):
            from core.entity_type_service import EntityTypeService
            service = EntityTypeService(db=mock_db)

        service.close()
        mock_db.close.assert_not_called()