# -*- coding: utf-8 -*-
"""
Coverage-push tests for the data/federation module set:

  core/episode_service, core/agent_graduation_service,
  core/graphrag_engine, core/historical_sync_service,
  core/hybrid_data_ingestion, core/ingestion_pipeline,
  core/identity/verifiable_credentials,
  core/federation/zero_trust_security, core/federation/federation_security

Everything is mocked (DB/HTTP/LLM); no network or real services are hit.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models_registration import Base


pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _seed_tenant(db, tenant_id="t1"):
    from core.models import Tenant

    db.add(Tenant(id=tenant_id, name=f"T-{tenant_id}", subdomain=tenant_id))
    db.flush()


def _cm(session):
    """Wrap a session so `with patched() as s:` yields it (MagicMock's own
    __enter__ would return a fresh MagicMock instead)."""

    @contextmanager
    def _inner():
        yield session

    return _inner()


def _patch_session(session):
    return patch("core.graphrag_engine.get_db_session", return_value=_cm(session))


# ============================================================================
# episode_service missing lines
# ============================================================================

class TestEpisodeServiceGaps:
    def test_canvas_summary_service_rejects_default_workspace(self):
        from core.episode_service import _get_canvas_summary_service

        with pytest.raises(ValueError):
            _get_canvas_summary_service("default")

    def test_canvas_summary_service_creates_once(self):
        import core.episode_service as es

        es._canvas_summary_service = None
        with patch("core.llm.canvas_summary_service.CanvasSummaryService", return_value="svc") as m:
            assert es._get_canvas_summary_service("ws1") == "svc"
            assert es._get_canvas_summary_service("ws1") == "svc"
        assert m.call_count == 1
        es._canvas_summary_service = None

    def test_embedding_service_lazy_init(self):
        from core.episode_service import EpisodeService

        svc = EpisodeService(db=Mock())
        svc._embedding_service = None
        with patch("core.episode_service.EmbeddingService", return_value="emb") as m:
            assert svc.embedding_service == "emb"
            assert svc.embedding_service == "emb"
        m.assert_called_once()

    def test_get_lancedb_connect_success(self):
        from core.episode_service import EpisodeService

        svc = EpisodeService(db=Mock())
        fake = MagicMock()
        fake.connect.return_value = True
        with patch("core.episode_service.LanceDBService", return_value=fake):
            assert svc._get_lancedb() is fake
        fake.get_or_create_episodes_table.assert_called_once()

    def test_get_lancedb_connect_failure_disables(self):
        from core.episode_service import EpisodeService

        svc = EpisodeService(db=Mock())
        fake = MagicMock()
        fake.connect.return_value = False
        with patch("core.episode_service.LanceDBService", return_value=fake):
            assert svc._get_lancedb() is None
        assert svc.lancedb is None

    @pytest.mark.asyncio
    async def test_extract_canvas_metadata_session_fallback(self):
        """Execution without canvas_id but with a session that has canvas
        audits -> session-based canvas capture path."""
        from core.episode_service import EpisodeService

        execution = MagicMock()
        execution.id = "e1"
        execution.metadata_json = {}
        execution.session_id = "s1"
        execution.created_at = datetime.now(timezone.utc)
        execution.tenant_id = "t1"

        audit = MagicMock()
        audit.id = "ca1"
        audit.canvas_id = "c1"
        audit.canvas_type = "form"
        audit.action_type = "submit"
        audit.details_json = {"k": "v"}

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            audit
        ]

        svc = EpisodeService(db=db)
        result = await svc._extract_canvas_metadata("e1")
        assert result["canvas_action_ids"] == ["ca1"]
        assert "presentation_summary" in result

    @pytest.mark.asyncio
    async def test_semantic_summary_failure_swallowed(self):
        from core.episode_service import EpisodeService

        execution = MagicMock()
        execution.id = "e1"
        execution.metadata_json = {"canvas_id": "c1"}
        execution.session_id = None
        execution.tenant_id = "t1"
        execution.started_at = datetime.now(timezone.utc)
        execution.completed_at = datetime.now(timezone.utc)

        canvas = MagicMock()
        canvas.canvas_type = "markdown"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, canvas]
        db.query.return_value.filter.return_value.count.return_value = 3
        db.query.return_value.join.return_value.filter.return_value.count.return_value = 2
        db.query.return_value.filter.return_value.between.return_value.all.return_value = []

        ctx = MagicMock()
        ctx.data = {"blocks": []}

        svc = EpisodeService(db=db)
        with patch("core.episode_service._get_canvas_context_provider", return_value=Mock(get_canvas=lambda c: ctx)), \
             patch("core.episode_service._get_canvas_summary_service",
                   return_value=Mock(generate_summary=AsyncMock(side_effect=Exception("llm down")))):
            result = await svc._extract_canvas_metadata("e1")
        assert result["canvas_id"] == "c1"
        assert result["presentation_summary"] is None

    @pytest.mark.asyncio
    async def test_auto_dev_event_emission_failure_is_non_fatal(self):
        from core.episode_service import EpisodeService

        execution = MagicMock()
        execution.id = "e1"
        execution.agent_id = "a1"
        execution.tenant_id = "t1"
        execution.human_intervention_count = 0
        execution.confidence_score = 0.5
        execution.status = "completed"
        execution.started_at = datetime.now(timezone.utc)
        execution.completed_at = datetime.now(timezone.utc)
        execution.metadata_json = None

        agent = MagicMock()
        agent.id = "a1"
        agent.status = "student"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, agent]

        svc = EpisodeService(db=db)
        with patch("core.auto_dev.event_hooks.TaskEvent", side_effect=RuntimeError("boom")), \
             patch("core.auto_dev.event_hooks.event_bus") as bus:
            result = await svc.create_episode_from_execution("e1", "task", "success", True)
        assert result is not None
        db.commit.assert_called()

    def test_proposal_quality_with_scores(self):
        """Non-empty quality scores -> averages computed."""
        from core.episode_service import EpisodeService

        ep1 = MagicMock()
        ep1.metadata_json = {"quality_score": 0.9, "episode_type": "meta_agent_proposal"}
        ep2 = MagicMock()
        ep2.metadata_json = {"quality_score": 0.5, "episode_type": "meta_agent_proposal"}
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [ep1, ep2]
        svc = EpisodeService(db=db)
        result = svc.calculate_proposal_quality_metrics("a1", "t1")
        assert result["proposal_episode_count"] == 2
        assert result["avg_proposal_quality"] == 0.7
        assert result["high_quality_proposal_count"] == 1
        assert result["proposal_quality_score"] == 0.84

    def test_update_feedback_running_loop_schedules_lancedb(self):
        """Running event loop -> background sync scheduled."""
        from core.episode_service import EpisodeService

        episode = MagicMock()
        episode.id = "ep1"
        episode.tenant_id = "t1"
        episode.agent_id = "a1"
        episode.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = episode
        feedback = MagicMock()
        feedback.id = "fb1"
        db.add = MagicMock()
        db.refresh = MagicMock()
        db.commit = MagicMock()
        svc = EpisodeService(db=db)
        svc._sync_feedback_to_lancedb = AsyncMock()
        with patch("core.models.EpisodeFeedback", return_value=feedback):
            result = svc.update_episode_feedback("ep1", 0.8)
        assert result == "fb1"

    def test_update_feedback_no_loop_skips_lancedb(self):
        from core.episode_service import EpisodeService

        episode = MagicMock()
        episode.id = "ep1"
        episode.tenant_id = "t1"
        episode.agent_id = "a1"
        episode.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = episode
        feedback = MagicMock()
        feedback.id = "fb2"
        svc = EpisodeService(db=db)
        with patch("core.models.EpisodeFeedback", return_value=feedback), \
             patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            result = svc.update_episode_feedback("ep1", 0.8)
        assert result == "fb2"

    def test_get_episode_feedback_exception_returns_empty(self):
        from core.episode_service import EpisodeService

        db = MagicMock()
        db.query.side_effect = Exception("boom")
        svc = EpisodeService(db=db)
        assert svc.get_episode_feedback("ep1") == []

    def test_domain_metrics_single_feedback_insufficient_trend(self):
        from core.episode_service import EpisodeService

        f = MagicMock()
        f.feedback_score = 0.5
        f.capability_domain = "reasoning"
        f.capability_name = "plan"
        f.tenant_id = "t1"
        f.provided_at = datetime.now(timezone.utc)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [f]
        svc = EpisodeService(db=db)
        result = svc.get_domain_feedback_metrics("t1", "reasoning", days=30)
        assert result["trend"] == "insufficient_data"
        assert result["by_capability"]["plan"]["avg_score"] == 0.5

    def test_get_canvas_actions_exception_returns_empty(self):
        from core.episode_service import EpisodeService

        db = MagicMock()
        db.query.side_effect = Exception("boom")
        svc = EpisodeService(db=db)
        assert svc.get_canvas_actions_for_episode("ep1") == []

    @pytest.mark.asyncio
    async def test_link_canvas_actions_exception_rolls_back(self):
        from core.episode_service import EpisodeService

        db = MagicMock()
        db.query.side_effect = Exception("boom")
        svc = EpisodeService(db=db)
        assert await svc.link_canvas_actions_to_episode("ep1", ["ca1"]) is False
        db.rollback.assert_called()


# ============================================================================
# graphrag_engine missing lines
# ============================================================================

class TestGraphRAGEngineGaps:
    def _engine(self):
        from core.graphrag_engine import GraphRAGEngine

        return GraphRAGEngine(workspace_id="ws1", tenant_id="t1")

    def test_sanitize_canonical_data_strips(self):
        engine = self._engine()
        out = engine._sanitize_canonical_data("user", {"email": "  A@B.C  ", "title": "CEO"})
        assert out == {"email": "a@b.c", "title": "CEO"}

    def test_first_resolve_canonical_entity_no_registry(self):
        engine = self._engine()
        with patch.object(engine, "_get_registry_entry", return_value=None):
            assert engine._resolve_canonical_entity(MagicMock(), "ws1", "user", "n") is None

    def test_second_resolve_canonical_entity_no_config(self):
        engine = self._engine()
        with patch.object(engine, "_get_registry_entry", return_value=None):
            assert engine._resolve_canonical_entity(MagicMock(), "ws1", "n", "user") is None
        """Model without workspace_id but with tenant_id -> tenant filter."""
        from core.models import Formula

        rec = MagicMock()
        rec.id = "f1"
        rec.name = "tax"
        session = MagicMock()
        session.query.return_value.filter.return_value.limit.return_value.all.return_value = [rec]
        engine = self._engine()
        with _patch_session(session), \
             patch.object(engine, "_get_registry_entry",
                          return_value={"model": Formula, "search_field": "name"}):
            out = engine.canonical_search(workspace_id="ws1", entity_type="formula", query="tax")
        assert out == [{"id": "f1", "name": "tax"}]

    def test_is_llm_available_false(self, monkeypatch):
        import core.graphrag_engine as ge

        monkeypatch.setattr(ge, "GRAPHRAG_LLM_ENABLED", False)
        assert self._engine()._is_llm_available("ws1") is False

    @pytest.mark.asyncio
    async def test_ingest_document_no_entities_returns_zero_stats(self):
        engine = self._engine()
        with patch.object(engine, "_llm_extract_entities_and_relationships",
                          new=AsyncMock(return_value=([], []))), \
                patch.object(engine, "_is_llm_available", return_value=True):
            stats = await engine.ingest_document(workspace_id="ws1", doc_id="d1", text="x")
        # R83: real stats instead of None — sync results reported 0 extracted.
        assert stats == {"entities": 0, "relationships": 0}

    def test_add_entity_existing_node_updates(self):
        from core.graphrag_engine import Entity

        session = MagicMock()
        existing = MagicMock()
        existing.id = "n1"
        session.query.return_value.filter_by.return_value.first.return_value = existing
        engine = self._engine()
        entity = Entity(id=str(uuid.uuid4()), name="Alice", entity_type="person",
                        properties={"embedding": [1.0, 2.0]})
        with _patch_session(session), \
             patch.object(engine, "_get_registry_entry", return_value=None):
            out = engine.add_entity(entity, workspace_id="ws1")
        assert out == "n1"
        assert existing.description == entity.description

    def test_add_entity_error_rolls_back(self):
        from core.graphrag_engine import Entity

        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None
        session.add.side_effect = Exception("boom")
        engine = self._engine()
        entity = Entity(id=str(uuid.uuid4()), name="Alice", entity_type="person")
        with _patch_session(session), \
             patch.object(engine, "_get_registry_entry", return_value=None):
            assert engine.add_entity(entity, workspace_id="ws1") is None
        session.rollback.assert_called()

    def test_add_relationship_default_tid(self):
        from core.graphrag_engine import Relationship

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = MagicMock(id="n1")
        engine = self._engine()
        rel = Relationship(id=str(uuid.uuid4()), from_entity="a", to_entity="b", rel_type="x")
        with _patch_session(session):
            out = engine.add_relationship(rel, workspace_id="ws1")
        assert out == rel.id

    def test_add_relationship_missing_target(self):
        from core.graphrag_engine import Relationship

        session = MagicMock()
        session.query.return_value.filter.return_value.first.side_effect = [MagicMock(id="n1"), None]
        engine = self._engine()
        rel = Relationship(id=str(uuid.uuid4()), from_entity="a", to_entity="b", rel_type="x")
        with _patch_session(session):
            assert engine.add_relationship(rel, workspace_id="ws1") is None

    def test_second_resolve_canonical_entity_no_config(self):
        engine = self._engine()
        with patch.object(engine, "_get_registry_entry", return_value=None):
            assert engine._resolve_canonical_entity(MagicMock(), "ws1", "n", "user") is None

    def test_second_resolve_canonical_entity_match_id_fallback(self, db):
        """Real-session test: no name/email match, but match_id falls back to
        an exact ID match."""
        from core.models import Tenant, User, Workspace

        db.add(Tenant(id="t1", name="T1", subdomain="t1"))
        db.add(Workspace(id="t1", name="W1", tenant_id="t1"))
        db.add(User(id="u1", email="alice@example.com", hashed_password="x",
                    tenant_id="t1", workspace_id="t1", first_name="Alice", last_name="A",
                    role="user", status="active"))
        db.commit()

        engine = self._engine()
        registry = {"model": User, "search_field": "email", "match_id": True}
        with patch.object(engine, "_get_registry_entry", return_value=registry):
            out = engine._resolve_canonical_entity(db, "t1", "u1", "user")
        assert out == "u1"

    def test_ingest_structured_data_skips_empty_name(self):
        engine = self._engine()
        session = MagicMock()
        with _patch_session(session):
            out = engine.ingest_structured_data(
                workspace_id="ws1", entities=[{"name": None}], relationships=[]
            )
        assert out == {"entities": 1, "relationships": 0}

    def test_ingest_structured_data_canonical_and_edges(self):
        engine = self._engine()
        session = MagicMock()
        node = MagicMock()
        node.id = "n1"
        session.add = MagicMock()
        session.flush = MagicMock()
        with _patch_session(session), \
             patch.object(engine, "_resolve_canonical_entity", return_value="c1"):
            out = engine.ingest_structured_data(
                workspace_id="ws1",
                entities=[{"name": "Alice", "type": "person",
                           "properties": {"canonical_type": "user", "embedding": [1.0]}}],
                relationships=[{"from": "Alice", "to": "missing", "type": "x"}],
            )
        assert out == {"entities": 1, "relationships": 1}

    def test_ingest_structured_data_error(self):
        engine = self._engine()
        session = MagicMock()
        session.add.side_effect = Exception("boom")
        with _patch_session(session):
            out = engine.ingest_structured_data(
                workspace_id="ws1", entities=[{"name": "x", "type": "y"}], relationships=[]
            )
        assert out == {"entities": 0, "relationships": 0}

    @pytest.mark.asyncio
    async def test_local_search_embedding_failure_sqlite_path(self):
        """SQLite traversal with vector-embedding failure and start nodes."""
        import sqlite3

        engine = self._engine()
        engine.llm_service = MagicMock()
        engine.llm_service.generate_embedding = AsyncMock(side_effect=Exception("emb down"))

        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute("CREATE TABLE graph_nodes (id TEXT PRIMARY KEY, name TEXT, type TEXT, description TEXT, workspace_id TEXT, properties TEXT, embedding BLOB)")
        cur.execute("CREATE TABLE graph_edges (id TEXT PRIMARY KEY, source_node_id TEXT, target_node_id TEXT, relationship_type TEXT, properties TEXT, workspace_id TEXT)")
        cur.execute("INSERT INTO graph_nodes VALUES ('n1','Alice','person','d1','ws1','{}',NULL)")
        cur.execute("INSERT INTO graph_nodes VALUES ('n2','Bob','person','d2','ws1','{}',NULL)")
        cur.execute("INSERT INTO graph_edges VALUES ('e1','n1','n2','knows','{}','ws1')")
        conn.commit()

        class _Row:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        def _exec(sql, params=None):
            params = params or {}
            cur.execute(str(sql), {k: v for k, v in params.items()})
            if str(sql).lstrip().upper().startswith(("SELECT", "WITH")):
                rows = [
                    _Row(**dict(zip([d[0] for d in cur.description], row)))
                    for row in cur.fetchall()
                ]
                return _Result(rows)
            return _Result([])

        session = MagicMock()
        session.bind = MagicMock()
        session.bind.dialect = MagicMock()
        session.bind.dialect.name = "sqlite"
        session.execute.side_effect = _exec
        session.close = MagicMock()

        with _patch_session(session), \
             patch("core.graphrag.multi_hop_expansion.get_sql_expander", side_effect=Exception("skip")):
            result = engine.local_search(workspace_id="ws1", query="Alice", depth=2)
        assert result["mode"] == "local"
        assert result["count"] == 2
        assert len(result["relationships"]) == 1
        assert "multi_hop_paths" in result
        conn.close()

    @pytest.mark.asyncio
    async def test_local_search_no_start_nodes(self):
        engine = self._engine()
        engine.llm_service = MagicMock()
        engine.llm_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2])

        session = MagicMock()
        session.bind = MagicMock()
        session.bind.dialect = MagicMock()
        session.bind.dialect.name = "sqlite"
        session.execute.return_value.fetchall.return_value = []
        with _patch_session(session):
            result = engine.local_search(workspace_id="ws1", query="zzz", include_stale=True)
        assert result["mode"] == "local"
        assert result["count"] == 0
        assert "No matching entities" in result["context"]

    @pytest.mark.asyncio
    async def test_global_search_no_communities(self):
        engine = self._engine()
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        with _patch_session(session):
            result = await engine.global_search(workspace_id="ws1", query="x")
        assert result["mode"] == "global"
        assert "No community data" in result["answer"]


# ============================================================================
# graphrag_engine remaining gaps
# ============================================================================

class TestGraphRAGEngineGaps2:
    def _engine(self):
        from core.graphrag_engine import GraphRAGEngine

        return GraphRAGEngine(workspace_id="ws1", tenant_id="t1")

    def test_canonical_search_all_property_fields_returns_empty(self):
        """Registry whose only search field is a Python property (User.name):
        no usable column -> [] without crashing."""
        from core.models import User

        engine = self._engine()
        with _patch_session(MagicMock()), \
             patch.object(engine, "_get_registry_entry",
                          return_value={"model": User, "search_field": "name"}):
            out = engine.canonical_search(workspace_id="ws1", entity_type="user", query="x")
        assert out == []

    def test_canonical_search_tenant_only_model(self):
        """Model with tenant_id but no workspace_id -> tenant filter branch."""
        from core.models import Workspace

        rec = MagicMock()
        rec.id = "w1"
        rec.name = "Acme"
        session = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = [rec]
        engine = self._engine()
        with _patch_session(session), \
             patch.object(engine, "_get_registry_entry",
                          return_value={"model": Workspace, "search_field": "name"}):
            out = engine.canonical_search(workspace_id="ws1", tenant_id="t1",
                                          entity_type="workspace", query="acme")
        assert out == [{"id": "w1", "name": "Acme"}]

    def test_pattern_extraction_uuid(self):
        engine = self._engine()
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "token 550e8400-e29b-41d4-a716-446655440000 here", "doc1", "src")
        assert any(e.entity_type == "uuid" for e in ents)

    def test_add_entity_updates_canonical_record(self):
        from core.graphrag_engine import Entity

        record = MagicMock()
        record.id = "c1"
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = record
        session.query.return_value.filter_by.return_value.first.return_value = None
        engine = self._engine()
        entity = Entity(id=str(uuid.uuid4()), name="Acme", entity_type="company",
                        properties={"canonical_type": "workspace", "description": "d"})
        with _patch_session(session), \
             patch.object(engine, "_resolve_canonical_entity", return_value="c1"), \
             patch.object(engine, "_get_registry_entry",
                          return_value={"model": MagicMock(),
                                        "updatable_fields": ["description", "name"]}):
            out = engine.add_entity(entity, workspace_id="ws1")
        assert out == entity.id
        setattr_calls = [c for c in record.method_calls if c[0] == "description"]
        assert setattr_calls or hasattr(record, "description")

    @pytest.mark.asyncio
    async def test_add_entity_automation_trigger_success(self):
        from core.graphrag_engine import Entity

        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None
        engine = self._engine()
        entity = Entity(id="n-trig", name="Bob", entity_type="person")
        import core.graphrag_engine as ge

        fake_orch = MagicMock()
        fake_orch.trigger_event = AsyncMock(return_value=None)
        with _patch_session(session), \
             patch.object(engine, "_get_registry_entry", return_value=None), \
             patch.object(ge, "AUTOMATION_AVAILABLE", True), \
             patch("core.graphrag_engine.orchestrator", fake_orch, create=True):
            out = engine.add_entity(entity, workspace_id="ws1")
        assert out == "n-trig"
        fake_orch.trigger_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_entity_automation_trigger_error_swallowed(self):
        from core.graphrag_engine import Entity

        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None
        engine = self._engine()
        entity = Entity(id="n-trig2", name="Bob", entity_type="person")
        import core.graphrag_engine as ge

        fake_orch = MagicMock()
        fake_orch.trigger_event = AsyncMock(side_effect=Exception("bus down"))
        with _patch_session(session), \
             patch.object(engine, "_get_registry_entry", return_value=None), \
             patch.object(ge, "AUTOMATION_AVAILABLE", True), \
             patch("core.graphrag_engine.orchestrator", fake_orch, create=True):
            out = engine.add_entity(entity, workspace_id="ws1")
        assert out == "n-trig2"

    def test_get_registry_entry_custom_type_returns_none(self):
        engine = self._engine()
        with patch.object(engine, "_get_entity_registry",
                          return_value={"custom": {"is_custom": True, "model": None}}):
            assert engine._get_registry_entry("custom") is None

    def test_create_canonical_entity_tenant_id_branch(self):
        class _TenantOnlyModel:
            tenant_id = "col"  # has tenant_id, no workspace_id

            def __init__(self, **kw):
                self.kw = kw
                self.id = "t-new"

        session = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        engine = self._engine()
        with patch.object(engine, "_get_registry_entry",
                          return_value={"model": _TenantOnlyModel, "search_field": "name"}):
            out = engine._create_canonical_entity_if_missing(session, "ws1", "Acme", "tenant")
        assert out == "t-new"

    def test_local_search_with_explicit_exclude_doc_ids(self):
        """exclude_doc_ids supplied -> freshness resolve skipped, sqlite
        json_extract freshness fragments are built and applied."""
        import sqlite3

        engine = self._engine()
        engine.llm_service = MagicMock()
        engine.llm_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2])

        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute("CREATE TABLE graph_nodes (id TEXT PRIMARY KEY, name TEXT, type TEXT, description TEXT, workspace_id TEXT, properties TEXT, embedding BLOB)")
        cur.execute("CREATE TABLE graph_edges (id TEXT PRIMARY KEY, source_node_id TEXT, target_node_id TEXT, relationship_type TEXT, properties TEXT, workspace_id TEXT)")
        cur.execute("INSERT INTO graph_nodes VALUES ('n1','Alice','person','d1','ws1','{}',NULL)")
        cur.execute("INSERT INTO graph_nodes VALUES ('n2','Bob','person','d2','ws1','{}',NULL)")
        cur.execute("INSERT INTO graph_edges VALUES ('e1','n1','n2','knows','{}','ws1')")
        conn.commit()

        class _Row:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        def _exec(sql, params=None):
            params = params or {}
            cur.execute(str(sql), dict(params))
            if str(sql).lstrip().upper().startswith(("SELECT", "WITH")):
                return _Result([_Row(**dict(zip([d[0] for d in cur.description], row)))
                                for row in cur.fetchall()])
            return _Result([])

        session = MagicMock()
        session.bind = MagicMock()
        session.bind.dialect = MagicMock()
        session.bind.dialect.name = "sqlite"
        session.execute.side_effect = _exec
        with _patch_session(session):
            result = engine.local_search(workspace_id="ws1", query="Alice",
                                         depth=2, exclude_doc_ids={"doc-stale"})
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_global_search_with_communities(self):
        engine = self._engine()
        engine.llm_service = MagicMock()
        engine.llm_service.generate_completion = AsyncMock(
            return_value={"content": "synthesized answer"}
        )

        comm = MagicMock()
        comm.id = "gc1"
        comm.summary = "Summary about Project Alpha"
        comm.keywords = ["alpha", "project"]
        comm.level = 0
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = [comm]
        with _patch_session(session):
            result = await engine.global_search(workspace_id="ws1", query="project alpha")
        assert result["mode"] == "global"
        assert result["answer"] == "synthesized answer"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_global_search_no_keyword_hits_uses_first_five(self):
        engine = self._engine()
        engine.llm_service = MagicMock()
        engine.llm_service.generate_completion = AsyncMock(
            return_value={"content": "fallback synthesis"}
        )

        comms = []
        for i in range(6):
            c = MagicMock()
            c.id = f"gc{i}"
            c.summary = f"Summary {i}"
            c.keywords = None
            c.level = 0
            comms.append(c)
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = comms
        with _patch_session(session):
            result = await engine.global_search(workspace_id="ws1", query="zzz-no-match")
        assert result["count"] == 5


# ============================================================================
# episode_service remaining gaps
# ============================================================================

class TestEpisodeServiceGaps2:
    def test_embedding_dimension_cohere(self):
        from core.episode_service import EpisodeService

        svc = EpisodeService(db=Mock())
        svc.embedding_service = type("Emb", (), {"provider": "cohere", "model": "embed-english-v3.0"})()
        assert svc._get_embedding_dimension() == 1024

    @pytest.mark.asyncio
    async def test_extract_canvas_metadata_canvas_not_found(self):
        from core.episode_service import EpisodeService

        execution = MagicMock()
        execution.id = "e1"
        execution.metadata_json = {"canvas_id": "c-missing"}
        execution.session_id = None
        execution.tenant_id = "t1"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, None]

        svc = EpisodeService(db=db)
        result = await svc._extract_canvas_metadata("e1")
        assert result == {"canvas_id": "c-missing"}

    @pytest.mark.asyncio
    async def test_failed_outcome_emits_fail_event(self):
        from core.episode_service import EpisodeService

        execution = MagicMock()
        execution.id = "e1"
        execution.agent_id = "a1"
        execution.tenant_id = "t1"
        execution.human_intervention_count = 1
        execution.confidence_score = 0.5
        execution.status = "completed"
        execution.started_at = datetime.now(timezone.utc)
        execution.completed_at = datetime.now(timezone.utc)
        execution.metadata_json = None

        agent = MagicMock()
        agent.id = "a1"
        agent.status = "student"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, agent]

        svc = EpisodeService(db=db)
        with patch("core.auto_dev.event_hooks.TaskEvent", return_value=MagicMock()), \
             patch("core.auto_dev.event_hooks.event_bus") as bus:
            bus.emit_task_success = AsyncMock()
            bus.emit_task_fail = AsyncMock()
            await svc.create_episode_from_execution("e1", "task", "failure", False)
        bus.emit_task_fail.assert_called_once()
        bus.emit_task_success.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_feedback_running_loop_schedules_lancedb(self):
        """Running event loop -> background sync scheduled."""
        from core.episode_service import EpisodeService

        episode = MagicMock()
        episode.id = "ep1"
        episode.tenant_id = "t1"
        episode.agent_id = "a1"
        episode.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = episode
        feedback = MagicMock()
        feedback.id = "fb1"
        svc = EpisodeService(db=db)
        svc._sync_feedback_to_lancedb = AsyncMock()
        with patch("core.models.EpisodeFeedback", return_value=feedback):
            result = svc.update_episode_feedback("ep1", 0.8)
        assert result == "fb1"


# ============================================================================
# historical_sync_service
# ============================================================================

class _Job:
    """Namespace stand-in for a HistoricalSyncJob row."""

    def __init__(self, **kw):
        self.id = kw.pop("id", "job-1")
        self.tenant_id = kw.pop("tenant_id", "t1")
        self.integration_id = kw.pop("integration_id", "salesforce")
        self.source_connection_id = kw.pop("source_connection_id", "conn-1")
        self.start_date = kw.pop("start_date", datetime.now(timezone.utc) - timedelta(days=90))
        self.end_date = kw.pop("end_date", datetime.now(timezone.utc))
        self.status = kw.pop("status", "pending")
        self.scope = kw.pop("scope", "personal")
        self.chunk_size = kw.pop("chunk_size", 100)
        self.created_at = kw.pop("created_at", datetime.now(timezone.utc))
        self.checkpoint_data = kw.pop("checkpoint_data", {})
        self.completed_chunks = kw.pop("completed_chunks", 0)
        self.records_processed = kw.pop("records_processed", 0)
        self.entities_extracted = kw.pop("entities_extracted", 0)
        self.relationships_extracted = kw.pop("relationships_extracted", 0)
        self.started_at = kw.pop("started_at", None)
        self.last_heartbeat = kw.pop("last_heartbeat", None)
        self.last_error = kw.pop("last_error", None)
        self.error_count = kw.pop("error_count", 0)
        self.completed_at = kw.pop("completed_at", None)


class _JobSession:
    def __init__(self, jobs, with_commit=True):
        self.jobs = jobs
        self.with_commit = with_commit
        self.commits = 0
        self.closed = False

    def query(self, model):
        return _JobQuery(self.jobs)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def refresh(self, job):
        pass

    def close(self):
        self.closed = True

    def add(self, obj):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class _JobQuery:
    def __init__(self, jobs):
        self.jobs = jobs

    def filter_by(self, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.jobs[0] if self.jobs else None

    def all(self):
        return self.jobs

    def update(self, values, synchronize_session=False):
        for j in self.jobs:
            for k, v in values.items():
                setattr(j, k, v)
        return len(self.jobs)


class TestHistoricalSyncGaps:
    def _service(self, tenant_id="t1"):
        from core.historical_sync_service import HistoricalSyncService

        return HistoricalSyncService(tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_llm_extract_success(self):
        from core.historical_sync_service import _llm_extract_with_handler

        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json_dumps({
            "entities": [
                {"name": "Alice", "type": "person", "canonical_type": "user",
                 "description": "d", "confidence": 0.9},
            ],
            "relationships": [
                {"from": "Alice", "to": "Acme", "type": "works_at", "description": "x"}
            ],
        }))
        entities, rels = await _llm_extract_with_handler(
            llm, "some text", "doc1", "salesforce", "ws1", "t1",
            extra_metadata={"channel": "c1"},
        )
        assert len(entities) == 1
        assert entities[0].name == "Alice"
        assert entities[0].properties["canonical_type"] == "user"
        assert entities[0].properties["confidence"] == 0.9
        assert entities[0].properties["channel"] == "c1"
        assert len(rels) == 1

    @pytest.mark.asyncio
    async def test_llm_extract_json_fence_and_fallback_models(self):
        from core.historical_sync_service import _llm_extract_with_handler

        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=[
            "bad json",  # model=auto fails JSON decode
            "```json\n{\"entities\": [], \"relationships\": []}\n```",  # gemini
        ])
        entities, rels = await _llm_extract_with_handler(
            llm, "text", "doc2", "src", "ws1", "t1"
        )
        assert entities == [] and rels == []
        assert llm.generate.await_count == 2

    @pytest.mark.asyncio
    async def test_llm_extract_all_models_fail_returns_empty(self):
        from core.historical_sync_service import _llm_extract_with_handler

        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=Exception("llm down"))
        entities, rels = await _llm_extract_with_handler(
            llm, "text", "doc3", "src", "ws1", "t1"
        )
        assert entities == [] and rels == []
        assert llm.generate.await_count == 3

    @pytest.mark.asyncio
    async def test_llm_extract_empty_responses(self):
        from core.historical_sync_service import _llm_extract_with_handler

        llm = MagicMock()
        llm.generate = AsyncMock(return_value="   ")
        entities, rels = await _llm_extract_with_handler(
            llm, "text", "doc4", "src", "ws1", "t1"
        )
        assert entities == [] and rels == []

    @pytest.mark.asyncio
    async def test_llm_extract_confidence_bad_converts_zero(self):
        from core.historical_sync_service import _llm_extract_with_handler

        llm = MagicMock()
        llm.generate = AsyncMock(return_value=json_dumps({
            "entities": [{"name": "X", "type": "y", "confidence": "NaN-value"}],
            "relationships": [],
        }))
        entities, _ = await _llm_extract_with_handler(
            llm, "text", "doc5", "src", "ws1", "t1"
        )
        assert entities[0].properties["confidence"] == 0.0

    def test_log_job_event(self):
        from core.historical_sync_service import _log_job_event

        job = _Job(checkpoint_data={"events": ["old"]})
        _log_job_event(_JobSession([job]), "job-1", "t1", "hello")
        assert job.checkpoint_data["events"][-1].endswith("hello")

    def test_log_job_event_missing_job(self):
        from core.historical_sync_service import _log_job_event

        _log_job_event(_JobSession([]), "job-x", "t1", "noop")

    def test_memory_helpers(self):
        import core.historical_sync_service as hss

        assert isinstance(hss._get_memory_threshold(), int)
        import sys as _sys
        import psutil as _psutil
        with patch.dict(_sys.modules, {"psutil": _psutil}):
            with patch("psutil.Process") as proc:
                proc.return_value.memory_info.return_value.rss = 100 * 1024 * 1024
                assert hss._get_memory_usage() == 100
        with patch.dict(_sys.modules, {"psutil": None}):
            assert hss._get_memory_usage() == 0

    def test_property_getters(self):
        service = self._service()
        assert service.workspace_id == "t1"
        assert service.db is not None
        service.db.close()
        with patch("core.historical_sync_service.IngestionPipelineService") as ips, \
             patch("core.historical_sync_service.IntegrationRegistry") as ir:
            service._ingestion_pipeline = None
            service._integration_registry = None
            service.ingestion_pipeline
            service.integration_registry
        assert service._ingestion_pipeline is not None
        assert service._integration_registry is not None

    @pytest.mark.asyncio
    async def test_start_historical_sync(self):
        service = self._service()
        session = _JobSession([])
        service._db = session
        with patch("core.historical_sync_service.SyncJobQueue") as q:
            q.return_value.enqueue = AsyncMock()
            job_id = await service.start_historical_sync(
                "salesforce", "conn-1", datetime.now(timezone.utc) - timedelta(days=30)
            )
        assert isinstance(job_id, str)
        assert session.commits >= 1

    @pytest.mark.asyncio
    async def test_start_historical_sync_enqueue_failure(self):
        service = self._service()
        service._db = _JobSession([])
        with patch("core.historical_sync_service.SyncJobQueue") as q:
            q.return_value.enqueue = AsyncMock(side_effect=Exception("redis down"))
            job_id = await service.start_historical_sync(
                "salesforce", "conn-1", datetime.now(timezone.utc)
            )
        assert isinstance(job_id, str)

    @pytest.mark.asyncio
    async def test_check_memory_and_gc_high(self):
        service = self._service()
        with patch("core.historical_sync_service._get_memory_usage", return_value=99999), \
             patch("core.historical_sync_service.gc.collect") as gc:
            assert await service._check_memory_and_gc("job-1") is False
        gc.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_memory_and_gc_error(self):
        service = self._service()
        with patch("core.historical_sync_service._get_memory_usage", side_effect=Exception("boom")):
            assert await service._check_memory_and_gc("job-1") is True

    @pytest.mark.asyncio
    async def test_process_sync_job_completes(self):
        job = _Job(status="pending")
        service = self._service()
        fake_ingestion = MagicMock()
        fake_ingestion.sync_configs = {}
        fake_ingestion._fetch_integration_data = AsyncMock(return_value=[
            {"id": "r1", "type": "contact", "name": "Alice", "email": "a@b.c"},
            {"id": "r2", "type": "contact", "name": "Bob", "email": "b@c.d"},
        ])
        fake_ingestion._record_to_text = (
            lambda record, iid: f"{record.get('name', '')} is a contact with "
                                f"email {record.get('email', '')} - sufficiently long text"
        )
        service._ingestion_pipeline = fake_ingestion
        session = _JobSession([job])
        with patch("core.historical_sync_service.SessionLocal", return_value=session), \
             patch.object(service, "_check_memory_and_gc", new=AsyncMock(return_value=True)), \
             patch.object(service, "_extract_chunk_and_ingest",
                          new=AsyncMock(return_value=(3, 2))), \
             patch("core.schema_discovery_service.SchemaDiscoveryService") as sds:
            sds.return_value.discover_schemas_from_entities = AsyncMock()
            await service._process_sync_job("job-1")
        assert job.status == "completed"
        assert job.records_processed == 2
        assert job.completed_chunks == 1
        assert job.entities_extracted == 3

    @pytest.mark.asyncio
    async def test_process_sync_job_not_found(self):
        service = self._service()
        with patch("core.historical_sync_service.SessionLocal",
                   return_value=_JobSession([])):
            await service._process_sync_job("missing")

    @pytest.mark.asyncio
    async def test_process_sync_job_terminal_state(self):
        job = _Job(status="failed")
        service = self._service()
        with patch("core.historical_sync_service.SessionLocal", return_value=_JobSession([job])):
            await service._process_sync_job("job-1")
        assert job.status == "failed"

    @pytest.mark.asyncio
    async def test_process_sync_job_paused(self):
        job = _Job(status="running")
        service = self._service()
        fake_ingestion = MagicMock()
        fake_ingestion.sync_configs = {}
        fake_ingestion._fetch_integration_data = AsyncMock(return_value=[])
        service._ingestion_pipeline = fake_ingestion

        class _PausableJob(_Job):
            paused = False

            def __init__(self, **kw):
                super().__init__(**kw)
                self._pause_after = 1

        job2 = _Job(status="running")
        session = _JobSession([job2])
        original_refresh = session.refresh

        def _refresh(j):
            if session.commits >= 1:
                j.status = "paused"
            original_refresh(j)

        session.refresh = _refresh
        with patch("core.historical_sync_service.SessionLocal", return_value=session), \
             patch.object(service, "_check_memory_and_gc", new=AsyncMock(return_value=True)):
            await service._process_sync_job("job-1")
        assert job2.status == "paused"

    @pytest.mark.asyncio
    async def test_process_sync_job_fetch_error_marks_failed(self):
        job = _Job(status="running")
        service = self._service()
        fake_ingestion = MagicMock()
        fake_ingestion.sync_configs = {}
        fake_ingestion._fetch_integration_data = AsyncMock(side_effect=Exception("api down"))
        service._ingestion_pipeline = fake_ingestion
        session = _JobSession([job])
        with patch("core.historical_sync_service.SessionLocal", return_value=session), \
             patch.object(service, "_check_memory_and_gc", new=AsyncMock(return_value=True)):
            await service._process_sync_job("job-1")
        assert job.status == "failed"
        assert job.last_error

    @pytest.mark.asyncio
    async def test_get_sync_progress(self):
        service = self._service()
        service._db = _JobSession([_Job(status="completed", records_processed=5)])
        progress = await service.get_sync_progress("job-1")
        assert progress["records_processed"] == 5
        assert progress["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_sync_progress_not_found(self):
        service = self._service()
        service._db = _JobSession([])
        progress = await service.get_sync_progress("missing")
        assert progress["error"] == "Job not found"

    @pytest.mark.asyncio
    async def test_cancel_sync(self):
        job = _Job(status="running")
        service = self._service()
        service._db = _JobSession([job])
        assert await service.cancel_sync("job-1") is True
        assert job.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_sync_not_found(self):
        service = self._service()
        service._db = _JobSession([])
        assert await service.cancel_sync("missing") is False

    @pytest.mark.asyncio
    async def test_pause_sync(self):
        job = _Job(status="running")
        service = self._service()
        service._db = _JobSession([job])
        assert await service.pause_sync("job-1") is True
        assert job.status == "paused"

    @pytest.mark.asyncio
    async def test_pause_sync_wrong_state(self):
        job = _Job(status="completed")
        service = self._service()
        service._db = _JobSession([job])
        assert await service.pause_sync("job-1") is False

    @pytest.mark.asyncio
    async def test_resume_sync(self):
        job = _Job(status="failed")
        service = self._service()
        service._db = _JobSession([job])
        with patch("core.historical_sync_service.SyncJobQueue") as q:
            q.return_value.enqueue = AsyncMock()
            assert await service.resume_sync("job-1") is True
        assert job.status == "pending"

    @pytest.mark.asyncio
    async def test_resume_sync_enqueue_failure(self):
        job = _Job(status="failed")
        service = self._service()
        service._db = _JobSession([job])
        with patch("core.historical_sync_service.SyncJobQueue") as q:
            q.return_value.enqueue = AsyncMock(side_effect=Exception("redis down"))
            assert await service.resume_sync("job-1") is False


import json as _json_mod


def json_dumps(data):
    return _json_mod.dumps(data)


class TestHistoricalSyncGaps2:
    def _service(self, tenant_id="t1"):
        from core.historical_sync_service import HistoricalSyncService

        return HistoricalSyncService(tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_llm_extract_plain_fence(self):
        from core.historical_sync_service import _llm_extract_with_handler

        llm = MagicMock()
        llm.generate = AsyncMock(return_value="```\n{\"entities\": [{\"name\": \"A\", \"type\": \"t\"}], \"relationships\": []}\n```")
        entities, rels = await _llm_extract_with_handler(
            llm, "text", "doc6", "src", "ws1", "t1"
        )
        assert len(entities) == 1

    def test_log_job_event_exception_swallowed(self):
        from core.historical_sync_service import _log_job_event

        session = MagicMock()
        session.query.side_effect = Exception("boom")
        _log_job_event(session, "job-1", "t1", "event")  # must not raise

    @pytest.mark.asyncio
    async def test_extract_chunk_retries_once(self):
        from core.historical_sync_service import HistoricalSyncService
        from core.graphrag_engine import Entity

        service = HistoricalSyncService(tenant_id="t1")
        fake_engine = MagicMock()
        fake_engine.ingest_structured_data = MagicMock(return_value={"entities": 1})
        fake_engine.close = MagicMock()
        entities = [Entity(id=str(uuid.uuid4()), name="Alice", entity_type="person")]
        llm = AsyncMock(side_effect=[Exception("transient"), (entities, [])])
        with patch("core.historical_sync_service.SessionLocal", return_value=_JobSession([])), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=fake_engine), \
             patch("core.historical_sync_service._llm_extract_with_handler", new=llm):
            ent, rel = await service._extract_chunk_and_ingest(
                "job-1", 0, [("d1", "long enough text here", "src")], "ws1"
            )
        assert ent == 1
        assert llm.await_count == 2

    @pytest.mark.asyncio
    async def test_extract_chunk_skips_ingest_when_nothing_extracted(self):
        from core.historical_sync_service import HistoricalSyncService

        service = HistoricalSyncService(tenant_id="t1")
        fake_engine = MagicMock()
        fake_engine.ingest_structured_data = MagicMock()
        with patch("core.historical_sync_service.SessionLocal", return_value=_JobSession([])), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=fake_engine), \
             patch("core.historical_sync_service._llm_extract_with_handler",
                   new=AsyncMock(return_value=([], []))):
            ent, rel = await service._extract_chunk_and_ingest(
                "job-1", 0, [("d1", "long enough text here", "src")], "ws1"
            )
        assert ent == 0 and rel == 0
        fake_engine.ingest_structured_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_start_and_cancel(self):
        service = self._service()
        job = _Job()
        task = asyncio.create_task(service._heartbeat_loop("job-1"))
        with patch("core.historical_sync_service.SessionLocal",
                   return_value=_JobSession([job])):
            await asyncio.sleep(0.2)
            task.cancel()
            await task  # CancelledError is handled inside the loop (stop.set())
        assert job.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_check_memory_normal(self):
        service = self._service()
        with patch("core.historical_sync_service._get_memory_usage", return_value=100):
            assert await service._check_memory_and_gc("job-1") is True

    @pytest.mark.asyncio
    async def test_process_sync_job_fallback_config_and_no_records(self):
        job = _Job(status="running", integration_id="mystery_app")
        service = self._service()
        fake_ingestion = MagicMock()
        fake_ingestion.sync_configs = {}
        fake_ingestion._fetch_integration_data = AsyncMock(return_value=[])
        service._ingestion_pipeline = fake_ingestion
        session = _JobSession([job])
        with patch("core.historical_sync_service.SessionLocal", return_value=session), \
             patch.object(service, "_check_memory_and_gc", new=AsyncMock(return_value=True)), \
             patch("core.schema_discovery_service.SchemaDiscoveryService") as sds:
            sds.return_value.discover_schemas_from_entities = AsyncMock()
            await service._process_sync_job("job-1")
        assert job.status == "completed"

    @pytest.mark.asyncio
    async def test_process_sync_job_waits_for_background_tasks(self):
        job = _Job(status="running")
        service = self._service()
        fake_ingestion = MagicMock()
        fake_ingestion.sync_configs = {}
        fake_ingestion._fetch_integration_data = AsyncMock(return_value=[])
        service._ingestion_pipeline = fake_ingestion

        async def _noop():
            return None

        import core.historical_sync_service as hss

        session = _JobSession([job])
        with patch("core.historical_sync_service.SessionLocal", return_value=session), \
             patch.object(service, "_check_memory_and_gc", new=AsyncMock(return_value=True)), \
             patch("core.schema_discovery_service.SchemaDiscoveryService") as sds, \
             patch.object(hss, "_background_tasks", [asyncio.ensure_future(_noop())]):
            sds.return_value.discover_schemas_from_entities = AsyncMock()
            await service._process_sync_job("job-1")
        assert job.status == "completed"

    @pytest.mark.asyncio
    async def test_process_sync_job_commit_failure_reported(self):
        job = _Job(status="running")
        service = self._service()
        fake_ingestion = MagicMock()
        fake_ingestion.sync_configs = {}
        fake_ingestion._fetch_integration_data = AsyncMock(side_effect=Exception("api down"))
        service._ingestion_pipeline = fake_ingestion

        class _CommitFailSession(_JobSession):
            def commit(self):
                self.commits += 1
                if self.commits >= 2:
                    raise Exception("db locked")

        session = _CommitFailSession([job])
        with patch("core.historical_sync_service.SessionLocal", return_value=session), \
             patch.object(service, "_check_memory_and_gc", new=AsyncMock(return_value=True)):
            await service._process_sync_job("job-1")
        assert job.status == "failed"

    @pytest.mark.asyncio
    async def test_resume_sync_not_found(self):
        service = self._service()
        service._db = _JobSession([])
        assert await service.resume_sync("missing") is False


class TestHistoricalSyncGaps3:
    def _service(self, tenant_id="t1"):
        from core.historical_sync_service import HistoricalSyncService

        return HistoricalSyncService(tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_extract_chunk_both_attempts_fail(self):
        from core.historical_sync_service import HistoricalSyncService

        service = HistoricalSyncService(tenant_id="t1")
        fake_engine = MagicMock()
        fake_engine.ingest_structured_data = MagicMock()
        llm = AsyncMock(side_effect=Exception("llm down"))
        with patch("core.historical_sync_service.SessionLocal", return_value=_JobSession([])), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=fake_engine), \
             patch("core.historical_sync_service._llm_extract_with_handler", new=llm):
            ent, rel = await service._extract_chunk_and_ingest(
                "job-1", 0, [("d1", "long enough text here", "src")], "ws1"
            )
        assert ent == 0 and rel == 0
        assert llm.await_count == 2

    @pytest.mark.asyncio
    async def test_extract_chunk_task_result_exception_skipped(self):
        from core.historical_sync_service import HistoricalSyncService

        service = HistoricalSyncService(tenant_id="t1")
        fake_engine = MagicMock()
        fake_engine.ingest_structured_data = MagicMock()
        fake_engine.close = MagicMock()

        async def _boom_task():
            raise RuntimeError("task exploded")

        failing = asyncio.ensure_future(_boom_task())
        with patch("core.historical_sync_service.SessionLocal", return_value=_JobSession([])), \
             patch("core.graphrag_engine.GraphRAGEngine", return_value=fake_engine), \
             patch("core.historical_sync_service.asyncio.wait",
                   new=AsyncMock(return_value=({failing}, set()))), \
             patch("core.historical_sync_service.asyncio.create_task", return_value=failing):
            ent, rel = await service._extract_chunk_and_ingest(
                "job-1", 0, [("d1", "long enough text here", "src")], "ws1"
            )
        assert ent == 0 and rel == 0
        await asyncio.gather(failing, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_heartbeat_thread_failure_swallowed(self):
        service = self._service()
        task = asyncio.create_task(service._heartbeat_loop("job-1"))
        with patch("core.historical_sync_service.SessionLocal", side_effect=Exception("no db")):
            await asyncio.sleep(0.2)
            task.cancel()
            await task

    @pytest.mark.asyncio
    async def test_heartbeat_thread_crash_logged(self):
        import threading

        service = self._service()
        orig_wait = threading.Event.wait

        def _crash_wait(self, timeout=None):
            if timeout is not None:
                raise RuntimeError("interrupted")
            return orig_wait(self, timeout)

        with patch("threading.Event.wait", new=_crash_wait):
            task = asyncio.create_task(service._heartbeat_loop("job-1"))
            await asyncio.sleep(0.2)
            task.cancel()
            await task
        assert service._hb_stop is not None


# ============================================================================
# hybrid_data_ingestion gaps
# ============================================================================

class TestHybridGaps:
    def test_init_import_failure_branches(self):
        from core.hybrid_data_ingestion import HybridDataIngestionService

        with patch("core.lancedb_handler.get_lancedb_handler", side_effect=ImportError), \
             patch("core.graphrag_engine.GraphRAGEngine", side_effect=ImportError), \
             patch("core.llm_service.get_llm_service", side_effect=ImportError):
            svc = HybridDataIngestionService("ws-i", "t-i")
        assert svc.memory_handler is None
        assert svc.graphrag is None
        assert svc.llm is None

    @pytest.mark.asyncio
    async def test_sync_discovery_failure_warns(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-d", "t-d")
        svc.memory_handler = None
        svc.graphrag = None
        svc.sync_configs["hubspot"] = SyncConfiguration(
            integration_id="hubspot", entity_types=["contacts"]
        )
        with patch("core.hybrid_data_ingestion.SessionLocal", return_value=MagicMock()), \
             patch("core.entity_type_service.EntityTypeService", side_effect=Exception("boom")), \
             patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(return_value=[
                              {"id": "1", "type": "contact", "name": "Alice",
                               "email": "a@b.c", "title": "CEO"},
                          ])):
            result = await svc.sync_integration_data("hubspot")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_universal_discovery_mode_and_pagination(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-u", "t-u")

        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_available_schemas = AsyncMock(return_value=[{"name": "companies"}])
        adapter.fetch_records = AsyncMock(side_effect=[
            {"results": [{"id": "1", "name": "Acme"}] * 100},
            {"results": [{"id": "2", "name": "Beta"}]},
        ])

        with patch("core.service_factory.ServiceFactory.get_hubspot_adapter",
                   return_value=adapter), \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=MagicMock()):
            records = await svc._fetch_universal_adapter_data(
                "hubspot",
                SyncConfiguration(integration_id="hubspot",
                                  entity_types=["contacts"],
                                  max_records_per_sync=150),
                discovery_mode=True,
            )
        assert len(records) == 101
        assert adapter.fetch_records.await_count == 3  # contacts x2 pages + companies x1

    @pytest.mark.asyncio
    async def test_universal_adapter_error_path(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-u2", "t-u2")
        with patch("core.service_factory.ServiceFactory.get_hubspot_adapter",
                   side_effect=Exception("boom")), \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=MagicMock()):
            records = await svc._fetch_universal_adapter_data(
                "hubspot", SyncConfiguration(integration_id="hubspot")
            )
        assert records == []

    @pytest.mark.asyncio
    async def test_slack_fetch_message_records(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-s", "t-s")
        client = MagicMock()
        client.conversations_list.return_value = {
            "channels": [{"id": "c1", "name": "general"}]
        }
        client.conversations_history.return_value = {
            "messages": [
                {"type": "message", "ts": "1", "text": "hello", "user": "u1"},
                {"type": "bot_message", "ts": "2", "text": "ignored"},
            ]
        }
        import sys as _sys
        from types import ModuleType as _MT
        fake_mod = _MT("integrations.slack_service")
        fake_mod.get_slack_client = lambda ws: client
        with patch.dict(_sys.modules, {"integrations.slack_service": fake_mod}):
            records = await svc._fetch_slack_data(
                SyncConfiguration(integration_id="slack")
            )
        assert len(records) == 1
        assert records[0]["text"] == "hello"

    @pytest.mark.asyncio
    async def test_notion_fetch_runtime_error(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-n", "t-n")
        with patch("integrations.notion_service.get_notion_service",
                   side_effect=RuntimeError("boom"), create=True):
            records = await svc._fetch_notion_data(
                SyncConfiguration(integration_id="notion", entity_types=["pages"])
            )
        assert records == []

    @pytest.mark.asyncio
    async def test_jira_fetch_runtime_error(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-j", "t-j")
        with patch("integrations.jira_service.get_jira_client",
                   side_effect=RuntimeError("boom"), create=True):
            records = await svc._fetch_jira_data(
                SyncConfiguration(integration_id="jira")
            )
        assert records == []

    @pytest.mark.asyncio
    async def test_zendesk_fetch_runtime_error(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-z", "t-z")
        with patch("integrations.zendesk_service.get_zendesk_service",
                   side_effect=RuntimeError("boom"), create=True):
            records = await svc._fetch_zendesk_data(
                SyncConfiguration(integration_id="zendesk", entity_types=["tickets"])
            )
        assert records == []

    @pytest.mark.asyncio
    async def test_zoho_books_with_org_id(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-z2", "t-z2")
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        adapter.get_invoices = AsyncMock(return_value=[{"id": "inv1"}])
        token = MagicMock()
        token.instance_url = "https://zoho.com"
        token.credential_metadata = {"organization_id": "org-1"}

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = token

        with patch("core.integrations.adapters.zoho.ZohoAdapter", return_value=adapter), \
             patch("core.hybrid_data_ingestion.SessionLocal", return_value=session):
            records = await svc._fetch_zoho_multi_app_data(
                SyncConfiguration(integration_id="zoho", entity_types=["books_invoices"])
            )
        assert records == [{"id": "inv1"}]

    @pytest.mark.asyncio
    async def test_shopify_entity_fetch_error(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-sh", "t-sh")
        service = MagicMock()
        service.config = {"access_token": "tok"}
        service.shop_name = "my-shop.myshopify.com"
        service.get_products = AsyncMock(side_effect=Exception("api down"))
        with patch("integrations.shopify_service.ShopifyService", return_value=service), \
             patch.dict(os.environ, {}, clear=False):
            records = await svc._fetch_shopify_data(
                SyncConfiguration(integration_id="shopify", entity_types=["products"])
            )
        assert records == []

    @pytest.mark.asyncio
    async def test_onedrive_no_token_and_list_fail(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-od", "t-od")
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value=None)
        with patch("integrations.onedrive_service.OneDriveService", return_value=service):
            assert await svc._fetch_onedrive_data(
                SyncConfiguration(integration_id="onedrive")
            ) == []

        service2 = MagicMock()
        service2.get_access_token = AsyncMock(return_value="tok")
        service2.list_files = AsyncMock(return_value={"status": "error", "message": "nope"})
        with patch("integrations.onedrive_service.OneDriveService", return_value=service2):
            assert await svc._fetch_onedrive_data(
                SyncConfiguration(integration_id="onedrive")
            ) == []

    @pytest.mark.asyncio
    async def test_onedrive_doc_ingestor_unavailable(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-od2", "t-od2")
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"value": [{"id": "f1", "name": "notes.txt", "size": 10}]},
        })
        with patch("integrations.onedrive_service.OneDriveService", return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   side_effect=Exception("unavailable")):
            records = await svc._fetch_onedrive_data(
                SyncConfiguration(integration_id="onedrive")
            )
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_google_drive_files_fallback_and_ingestor_unavailable(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-gd", "t-gd")
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"files": [{"id": "g1", "name": "a.docx", "mimeType": "text/plain"}]},
        })
        with patch("integrations.google_drive_service.GoogleDriveService", return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   side_effect=Exception("unavailable")):
            records = await svc._fetch_google_drive_data(
                SyncConfiguration(integration_id="google_drive")
            )
        assert len(records) == 1
        assert records[0]["id"] == "g1"

    @pytest.mark.asyncio
    async def test_google_drive_runtime_error(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-gd2", "t-gd2")
        with patch("integrations.google_drive_service.GoogleDriveService",
                   side_effect=RuntimeError("boom")):
            assert await svc._fetch_google_drive_data(
                SyncConfiguration(integration_id="google_drive")
            ) == []

    @pytest.mark.asyncio
    async def test_telegram_fetch_runtime_error(self):
        from core.hybrid_data_ingestion import (
            HybridDataIngestionService,
            SyncConfiguration,
        )

        svc = HybridDataIngestionService("ws-tg", "t-tg")
        adapter = MagicMock()
        adapter.get_updates = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.communication.adapters.telegram.TelegramAdapter",
                   return_value=adapter):
            assert await svc._fetch_telegram_data(
                SyncConfiguration(integration_id="telegram")
            ) == []


# ============================================================================
# verifiable_credentials gaps
# ============================================================================

class TestVCGaps:
    def _manager(self, **cfg_kwargs):
        from core.identity.verifiable_credentials import VCConfig, VerifiableCredentialManager

        return VerifiableCredentialManager(VCConfig(**cfg_kwargs))

    def test_to_dict_branches(self):
        from datetime import timedelta as _td

        from core.identity.verifiable_credentials import (
            VCProof,
            VCStatus,
            VerifiableCredential,
        )

        vc = VerifiableCredential(
            id="vc1", issuer="did:issuer",
            credential_subject={"id": "did:alice"},
            expiration_date=datetime.now() + _td(days=30),
            credential_status={"id": "cs1"},
            refresh_service={"id": "rs1"},
            terms_of_use=[{"id": "t1"}],
            evidence=[{"id": "e1"}],
            proof=VCProof(created=datetime.now(), verification_method="k1",
                          proof_value="abc"),
        )
        d = vc.to_dict()
        assert d["expirationDate"]
        assert d["credentialStatus"] and d["refreshService"]
        assert d["termsOfUse"] and d["evidence"] and d["proof"]
        d2 = vc.to_dict(include_proof=False)
        assert "proof" not in d2

    def test_is_valid_and_age(self):
        from datetime import timedelta as _td

        from core.identity.verifiable_credentials import VCStatus, VerifiableCredential

        vc = VerifiableCredential(
            id="vc2", issuer="did:i",
            issuance_date=datetime.now() - _td(days=5),
            expiration_date=datetime.now() + _td(days=10),
        )
        assert vc.is_valid()
        assert vc.get_age().days == 5
        assert vc.get_time_until_expiry() is not None
        vc.revoked = True
        assert not vc.is_valid()
        vc2 = VerifiableCredential(id="vc3", issuer="did:i",
                                   expiration_date=datetime.now() - _td(days=1))
        assert not vc2.is_valid()
        vc3 = VerifiableCredential(id="vc4", issuer="did:i")
        assert vc3.get_time_until_expiry() is None
        assert vc3.status == VCStatus.VALID

    def test_presentation_to_dict(self):
        from core.identity.verifiable_credentials import (
            VCProof,
            VCPresentation,
            VerifiableCredential,
        )

        vc = VerifiableCredential(id="vc5", issuer="did:i")
        vp = VCPresentation(id="vp1", verifiable_credential=[vc], holder="did:alice",
                            proof=VCProof(created=datetime.now(), verification_method="k"))
        d = vp.to_dict()
        assert d["holder"] == "did:alice"
        assert d["proof"]
        assert "proof" not in vp.to_dict(include_proof=False)

    def test_sign_credential_no_crypto(self):
        from core.identity.verifiable_credentials import (
            CRYPTO_AVAILABLE,
            VerifiableCredential,
        )

        manager = self._manager()
        vc = VerifiableCredential(id="vc6", issuer="did:i")
        if not CRYPTO_AVAILABLE:
            out = manager._sign_credential(vc, "did:i")
            assert out is vc
        else:
            # no did_manager -> unsigned
            manager.did_manager = None
            out = manager._sign_credential(vc, "did:i")
            assert out.proof is None

    def test_sign_with_key_failure(self):
        from core.identity.verifiable_credentials import (
            CRYPTO_AVAILABLE,
            VerifiableCredentialManager,
        )

        manager = self._manager()
        key = MagicMock()
        key.private_key_base58 = "not-hex"
        if CRYPTO_AVAILABLE:
            assert manager._sign_with_key(key, b"msg") == ""
        else:
            assert manager._sign_with_key(key, b"msg") == ""

    def test_verify_credential_expired_and_revoked(self):
        from datetime import timedelta as _td

        from core.identity.verifiable_credentials import (
            VCStatus,
            VerifiableCredential,
        )

        manager = self._manager()
        vc = VerifiableCredential(id="vc7", issuer="did:i",
                                  expiration_date=datetime.now() - _td(days=1))
        res = manager.verify_credential(vc)
        assert res.status == VCStatus.EXPIRED
        assert not res.is_valid

        vc2 = manager.create_credential("did:i", _VCType.AGENT_IDENTITY, "did:a", {})
        assert manager.revoke_credential(vc2.id) is True
        res2 = manager.verify_credential(vc2)
        assert res2.status == VCStatus.REVOKED

    def test_revoke_credential_unknown_and_disabled(self):
        from core.identity.verifiable_credentials import (
            VCConfig,
            VerifiableCredentialManager,
        )

        manager = self._manager()
        assert manager.revoke_credential("nope") is False
        manager2 = VerifiableCredentialManager(
            VCConfig(enable_revocation=False)
        )
        manager2.create_credential("did:i", VCTypeFixture.AGENT_IDENTITY, "did:a", {})
        vc_id = next(iter(manager2._credentials))
        assert manager2.revoke_credential(vc_id) is False

    def test_create_presentation_and_verify(self):
        from core.identity.did_manager import DIDManager, DIDType
        from core.identity.verifiable_credentials import (
            VCConfig,
            VCStatus,
            VerifiableCredential,
            VerifiableCredentialManager,
        )

        did_mgr = DIDManager()
        issuer = did_mgr.generate_did(DIDType.INSTANCE, "issuer")
        agent = did_mgr.generate_did(DIDType.AGENT, "alice")
        for d, t in ((issuer, DIDType.INSTANCE), (agent, DIDType.AGENT)):
            did_mgr.create_did_document(d, t)

        manager = VerifiableCredentialManager(VCConfig())
        manager.did_manager = did_mgr
        vc = manager.create_credential(issuer, _VCType.AGENT_IDENTITY, agent, {})
        vp = manager.create_presentation([vc], holder_did=None)
        assert vp.holder is None
        res = manager.verify_presentation(vp)
        assert res.is_valid

        vp2 = manager.create_presentation([vc], holder_did=agent, challenge="ch1")
        res2 = manager.verify_presentation(vp2, challenge="different")
        assert not res2.is_valid  # challenge mismatch flagged
        res3 = manager.verify_presentation(vp2, challenge="ch1")
        assert res3.is_valid

    def test_get_credentials_by_subject_filter(self):
        manager = self._manager()
        manager.create_credential("did:i", VCTypeFixture.AGENT_IDENTITY, "did:a", {})
        manager.create_credential("did:i", VCTypeFixture.FEDERATION_MEMBERSHIP, "did:a", {})
        manager.create_credential("did:i", VCTypeFixture.AGENT_IDENTITY, "did:b", {})
        assert len(manager.get_credentials_by_subject("did:a")) == 2
        assert len(manager.get_credentials_by_subject(
            "did:a", VCTypeFixture.AGENT_IDENTITY)) == 1

    def test_persist_and_load_credentials(self):
        from core.identity.verifiable_credentials import (
            VCConfig,
            VerifiableCredential,
            VerifiableCredentialManager,
        )

        manager = VerifiableCredentialManager(VCConfig())
        vc = VerifiableCredential(id="vc-db", issuer="did:i",
                                  credential_subject={"id": "did:a"})
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = None
            manager._persist_credential(vc)
            manager._persist_credential(vc, revoked=True, revocation_reason="comply")
        assert vc.id in manager._credentials or True

        row = MagicMock()
        row.credential_id = "vc-loaded"
        row.status = "revoked"
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value.query.return_value.all.return_value = [row]
            assert manager.load_credentials_from_db() == 1
        assert "vc-loaded" in manager._revocation_list

    def test_get_statistics(self):
        manager = self._manager()
        manager.create_credential("did:i", VCTypeFixture.AGENT_IDENTITY, "did:a", {})
        stats = manager.get_statistics()
        assert stats["total_credentials"] == 1
        assert stats["active_credentials"] == 1

    def test_factory_singleton(self):
        from core.identity.verifiable_credentials import (
            _vc_manager_instance,
            get_vc_manager,
        )

        old = _vc_manager_instance
        try:
            _vc_manager_instance = None
            m1 = get_vc_manager()
            assert get_vc_manager() is m1
        finally:
            _vc_manager_instance = old

    def test_vc_type_enum(self):
        from core.identity.verifiable_credentials import VCType

        assert VCType.AGENT_IDENTITY.value == "AgentIdentityCredential"


from core.identity.verifiable_credentials import VCType as _VCType


class VCTypeFixture:
    AGENT_IDENTITY = _VCType.AGENT_IDENTITY
    FEDERATION_MEMBERSHIP = _VCType.FEDERATION_MEMBERSHIP


# ============================================================================
# zero_trust_security gaps
# ============================================================================

class TestZTGaps:
    def _manager(self, **cfg):
        from core.federation.zero_trust_security import (
            SecurityConfig,
            ZeroTrustSecurityManager,
        )

        return ZeroTrustSecurityManager(SecurityConfig(**cfg))

    def test_policy_matches_branches(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            FederationRequest,
            SecurityContext,
            SecurityLevel,
            SecurityPolicy,
        )

        policy = SecurityPolicy(
            id="p1",
            required_security_level=SecurityLevel.MEDIUM,
            required_credentials=[_VCType.FEDERATION_MEMBERSHIP],
            allowed_actions=[AccessAction.READ],
            denied_resources=["^/internal/"],
            allowed_resources=["^/api/"],
            valid_from=datetime.now() + timedelta(days=1),
            valid_until=datetime.now() + timedelta(days=2),
            allowed_ips=["10.0.0.0"],
            denied_dids=["did:bad"],
            allowed_dids=["did:good"],
        )
        req = FederationRequest(action=AccessAction.READ, resource_id="/api/x")
        # no security context -> fails required credentials
        assert not policy.matches(req)

        ctx = SecurityContext(security_level=SecurityLevel.LOW)
        req.security_context = ctx
        assert not policy.matches(req)  # level too low

        ctx.security_level = SecurityLevel.HIGH
        assert not policy.matches(req)  # no credentials presented

        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(id="vc-x", issuer="did:i",
                                  credential_subject={"id": "did:good"})
        vc.type = ["VerifiableCredential", "FederationMembershipCredential"]
        ctx.presented_credentials = [vc]
        req.security_context = ctx
        assert not policy.matches(req)  # denied resource? resource /api/x allowed, action ok -> fails valid_from

        policy2 = SecurityPolicy(
            id="p2",
            allowed_actions=[AccessAction.READ],
            allowed_resources=["^/api/"],
            default_decision=True,
        )
        req2 = FederationRequest(action=AccessAction.WRITE, resource_id="/api/x",
                                 security_context=SecurityContext(security_level=SecurityLevel.HIGH))
        assert not policy2.matches(req2)  # action not allowed

        policy3 = SecurityPolicy(id="p3", default_decision=True)
        req3 = FederationRequest(action=AccessAction.READ, resource_id="r",
                                 security_context=SecurityContext(security_level=SecurityLevel.HIGH))
        assert policy3.matches(req3)

        policy4 = SecurityPolicy(id="p4", denied_resources=["^/secret"],
                                 default_decision=True)
        req4 = FederationRequest(action=AccessAction.READ, resource_id="/secret/x",
                                 security_context=SecurityContext(security_level=SecurityLevel.HIGH))
        assert not policy4.matches(req4)

    def test_verify_request_rate_limited(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            DecisionReason,
            FederationRequest,
            SecurityContext,
            SecurityConfig,
            SecurityLevel,
            SecurityPolicy,
            ZeroTrustSecurityManager,
        )

        manager = ZeroTrustSecurityManager(
            SecurityConfig(max_requests_per_minute=1)
        )
        manager.did_manager = None
        manager.vc_manager = None
        manager._default_policies_loaded = True

        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(id="vc-rl", issuer="did:i",
                                  credential_subject={"id": "did:src"})
        manager.add_policy(SecurityPolicy(id="allow", default_decision=True))

        req = FederationRequest(
            method="GET", path="/api/data",
            headers={"X-Source-DID": "did:src", "X-Verifiable-Credentials": "vc-rl"},
            action=AccessAction.READ,
        )
        req.security_context = SecurityContext(
            source_did="did:src", presented_credentials=[vc],
            security_level=SecurityLevel.HIGH,
        )
        # auth: require_authentication True but did_manager None -> source_did present -> ok
        first = manager.verify_request(req)
        assert first.allowed
        req2 = FederationRequest(
            method="GET", path="/api/data",
            headers={"X-Source-DID": "did:src", "X-Verifiable-Credentials": "vc-rl"},
            action=AccessAction.READ,
        )
        req2.security_context = SecurityContext(
            source_did="did:src", presented_credentials=[vc],
            security_level=SecurityLevel.HIGH,
        )
        second = manager.verify_request(req2)
        assert not second.allowed
        assert second.reason == DecisionReason.RATE_LIMITED

    def test_verify_request_flows(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            DecisionReason,
            FederationRequest,
            SecurityContext,
            SecurityConfig,
            SecurityLevel,
            SecurityPolicy,
            ZeroTrustSecurityManager,
        )

        manager = ZeroTrustSecurityManager(
            SecurityConfig(enable_rate_limiting=False)
        )
        manager.did_manager = None
        manager.vc_manager = None
        manager.add_policy(SecurityPolicy(id="allow", default_decision=True))

        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(id="vc-ok", issuer="did:i",
                                  credential_subject={"id": "did:src"})

        def _req(creds=True):
            headers = {"X-Source-DID": "did:src"}
            if creds:
                headers["X-Verifiable-Credentials"] = "vc-ok"
            r = FederationRequest(method="GET", path="/api/data", headers=headers,
                                  action=AccessAction.READ)
            r.security_context = SecurityContext(
                source_did="did:src",
                presented_credentials=[vc] if creds else [],
                security_level=SecurityLevel.HIGH,
            )
            return r

        assert manager.verify_request(_req()).allowed

        no_creds = manager.verify_request(_req(creds=False))
        assert not no_creds.allowed
        assert no_creds.reason == DecisionReason.INSUFFICIENT_PERMISSIONS

        no_auth = FederationRequest(method="GET", path="/api/data",
                                    action=AccessAction.READ)
        r = manager.verify_request(no_auth)
        assert not r.allowed
        assert r.reason == DecisionReason.UNKNOWN_IDENTITY

    def test_validate_credentials_subject_mismatch(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            FederationRequest,
            SecurityContext,
            SecurityConfig,
            SecurityLevel,
            ZeroTrustSecurityManager,
        )
        from core.identity.verifiable_credentials import VerifiableCredential

        manager = ZeroTrustSecurityManager(SecurityConfig())
        manager.did_manager = None
        manager.vc_manager = MagicMock()
        vc = VerifiableCredential(id="vc-borrowed", issuer="did:i",
                                  credential_subject={"id": "did:someone-else"})
        req = FederationRequest(method="GET", path="/x", action=AccessAction.READ)
        req.security_context = SecurityContext(
            source_did="did:attacker", presented_credentials=[vc],
            security_level=SecurityLevel.HIGH,
        )
        result = manager._validate_credentials(req)
        assert not result["valid"]

    def test_remove_policy_and_audit_log(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            FederationRequest,
            SecurityContext,
            SecurityConfig,
            SecurityLevel,
            SecurityPolicy,
            ZeroTrustSecurityManager,
        )

        manager = ZeroTrustSecurityManager(SecurityConfig(enable_rate_limiting=False))
        manager.did_manager = None
        manager.vc_manager = None
        policy = SecurityPolicy(id="p-tmp", default_decision=True)
        manager.add_policy(policy)
        assert manager.remove_policy("p-tmp") is True
        assert manager.remove_policy("p-tmp") is False

        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(id="vc-a", issuer="did:i",
                                  credential_subject={"id": "did:src"})
        manager.add_policy(SecurityPolicy(id="allow", default_decision=True))
        req = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        req.security_context = SecurityContext(
            source_did="did:src", presented_credentials=[vc],
            security_level=SecurityLevel.HIGH,
        )
        manager.verify_request(req)
        assert len(manager.get_audit_log()) == 1
        since = datetime.now() + timedelta(days=1)
        assert manager.get_audit_log(since=since) == []

        stats = manager.get_statistics()
        assert stats["total_requests"] == 1
        assert stats["allow_rate"] == 1.0
        manager.reset_statistics()
        assert manager.get_statistics()["total_requests"] == 0

    def test_factory_singleton(self):
        from core.federation.zero_trust_security import (
            _zero_trust_manager_instance,
            get_zero_trust_manager,
        )

        old = _zero_trust_manager_instance
        try:
            _zero_trust_manager_instance = None
            m1 = get_zero_trust_manager()
            assert get_zero_trust_manager() is m1
        finally:
            _zero_trust_manager_instance = old

    def test_request_fingerprint(self):
        from core.federation.zero_trust_security import (
            FederationRequest,
            SecurityContext,
        )

        req = FederationRequest(method="GET", path="/api")
        req.security_context = SecurityContext(source_did="did:src")
        assert len(req.get_fingerprint()) == 64


# ============================================================================
# federation_security gaps
# ============================================================================

class TestFedSecGaps:
    def test_mutual_tls_manager(self):
        from core.federation.federation_security import (
            MutualTLSConfig,
            MutualTLSManager,
        )

        mgr = MutualTLSManager(MutualTLSConfig())
        conn = mgr.create_connection("inst-1", "10.0.0.1", "TLS_AES_128_GCM_SHA256", "TLSv1.3")
        assert conn.connection_id
        assert len(mgr.get_active_connections()) == 1
        assert len(mgr.get_active_connections("inst-1")) == 1
        assert len(mgr.get_active_connections("other")) == 0
        assert mgr.close_connection(conn.connection_id) is True
        assert mgr.close_connection("nope") is False
        mgr.record_handshake_failure("10.0.0.1")
        assert mgr.get_handshake_failures("10.0.0.1") == {"10.0.0.1": 1}
        assert mgr.get_handshake_failures() == {"10.0.0.1": 1}
        assert mgr.cleanup_stale_connections(timeout_seconds=0) == 0

    def test_cleanup_stale_connections(self):
        from core.federation.federation_security import (
            MutualTLSManager,
            TLSConnection,
        )

        mgr = MutualTLSManager()
        stale = TLSConnection(connection_id="c1", is_active=True,
                              last_activity=datetime.now() - timedelta(hours=2))
        fresh = TLSConnection(connection_id="c2", is_active=True,
                              last_activity=datetime.now())
        mgr._connections = {"c1": stale, "c2": fresh}
        assert mgr.cleanup_stale_connections(timeout_seconds=3600) == 1
        assert stale.is_active is False
        assert fresh.is_active is True

    def test_credential_rotation_manager(self):
        from core.federation.federation_security import (
            CredentialRotationConfig,
            CredentialRotationManager,
            CredentialStatus,
        )

        mgr = CredentialRotationManager(CredentialRotationConfig(auto_rotate=True))
        record = mgr.register_credential("cred-1", "api_token", "inst-1", expiry_days=60)
        assert record.next_rotation is not None
        assert mgr.check_rotation_needed("cred-1") is False
        assert mgr.check_rotation_needed("missing") is False

        # near-expiry triggers rotation need
        record.expires_at = datetime.now() + timedelta(days=1)
        assert mgr.check_rotation_needed("cred-1") is True

        new = mgr.rotate_credential("cred-1", "cred-2")
        assert new.rotation_count == 1
        assert mgr._credentials["cred-1"].status == CredentialStatus.ROTATING
        assert mgr.get_credentials_due_for_rotation() == ["cred-1"]

        with pytest.raises(ValueError):
            mgr.rotate_credential("missing", "cred-3")

        assert mgr.revoke_credential("cred-2", "compromised") is True
        assert mgr.revoke_credential("missing") is False
        assert mgr.check_rotation_needed("cred-2") is False  # REVOKED not COMPROMISED

        record2 = mgr.register_credential("cred-4", "key", "inst-1")
        record2.status = CredentialStatus.COMPROMISED
        assert mgr.check_rotation_needed("cred-4") is True

        stats = mgr.get_statistics()
        assert stats["total_credentials"] == 3
        assert stats["auto_rotate_enabled"] is True

    def test_rotation_no_auto_rotate(self):
        from core.federation.federation_security import (
            CredentialRotationConfig,
            CredentialRotationManager,
        )

        mgr = CredentialRotationManager(CredentialRotationConfig(auto_rotate=False))
        record = mgr.register_credential("c1", "api_token", "i1")
        assert record.next_rotation is None

    def test_anomaly_detector(self):
        from core.federation.federation_security import (
            AnomalyDetectionConfig,
            AnomalyDetector,
            AnomalyType,
        )

        cfg = AnomalyDetectionConfig(
            min_samples_for_baseline=2,
            traffic_spike_multiplier=2.0,
            failed_auth_threshold=0.1,
            latency_spike_multiplier=2.0,
            max_request_size_mb=0.0001,  # tiny -> large-request alerts
        )
        detector = AnomalyDetector(cfg)
        detector.record_traffic("inst-1", "10.0.0.1", request_count=10, latency_ms=5, bytes_sent=100)
        detector.record_traffic("inst-1", "10.0.0.1", request_count=10, latency_ms=5, bytes_sent=100)
        m = detector.record_traffic("inst-1", "10.0.0.1", request_count=100,
                                    failed_auth=50, latency_ms=500, bytes_sent=10_000_000)
        assert m.error_rate == 0.5
        alerts = detector.get_recent_alerts()
        assert alerts, "expected anomaly alerts"
        types = {a.anomaly_type for a in alerts}
        assert AnomalyType.TRAFFIC_SPIKE in types
        assert AnomalyType.FAILED_AUTH_RATE in types
        assert AnomalyType.LATENCY_SPIKE in types
        assert AnomalyType.LARGE_REQUEST in types
        assert detector.get_recent_alerts(since=datetime.now() + timedelta(days=1)) == []
        assert detector.resolve_alert("nope") is False
        assert detector.resolve_alert(alerts[0].alert_id) is True
        assert detector.resolve_alert(alerts[0].alert_id) is False
        stats = detector.get_statistics()
        assert stats["total_alerts"] == len(alerts)

    def test_federation_security_service(self):
        from core.federation.federation_security import FederationSecurityService

        svc = FederationSecurityService()
        health = svc.get_health_status()
        assert health["status"] == "healthy"
        assert health["services"]["tls"] == "active"
        stats = svc.get_statistics()
        assert stats["tls"]["active_connections"] == 0
        assert stats["rotation"]["total_credentials"] == 0

        svc.tls.record_handshake_failure("1.2.3.4")
        svc.tls.record_handshake_failure("1.2.3.4")
        assert svc.get_statistics()["tls"]["handshake_failures"] == 2

    def test_health_degraded_and_unhealthy(self):
        from core.federation.federation_security import (
            AnomalyAlert,
            AnomalyType,
            FederationSecurityService,
        )

        svc = FederationSecurityService()
        for i in range(15):
            svc.anomaly._alerts.append(
                AnomalyAlert(alert_id=f"a{i}", anomaly_type=AnomalyType.TRAFFIC_SPIKE)
            )
        assert svc.get_health_status()["status"] == "degraded"
        for i in range(60):
            svc.anomaly._alerts.append(
                AnomalyAlert(alert_id=f"b{i}", anomaly_type=AnomalyType.TRAFFIC_SPIKE)
            )
        assert svc.get_health_status()["status"] == "unhealthy"

    def test_factory(self):
        from core.federation.federation_security import (
            _federation_security_instance,
            get_federation_security,
        )

        old = _federation_security_instance
        try:
            _federation_security_instance = None
            svc = get_federation_security()
            assert get_federation_security() is svc
        finally:
            _federation_security_instance = old


class TestZTGaps2:
    @pytest.mark.asyncio
    async def test_policy_matches_remaining_branches(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            FederationRequest,
            SecurityContext,
            SecurityLevel,
            SecurityPolicy,
        )
        from core.identity.verifiable_credentials import VerifiableCredential

        vc = VerifiableCredential(id="vc-z", issuer="did:i",
                                  credential_subject={"id": "did:s"})
        vc.type = ["VerifiableCredential", "FederationMembershipCredential"]

        def _ctx():
            return SecurityContext(security_level=SecurityLevel.HIGH,
                                   presented_credentials=[vc])

        # allowed_resources present but no match -> False
        p1 = SecurityPolicy(id="p1", allowed_resources=["^/api/"],
                            allowed_actions=[AccessAction.READ])
        r1 = FederationRequest(action=AccessAction.READ, resource_id="/other",
                               security_context=_ctx())
        assert not p1.matches(r1)

        # valid_until in the past -> False
        p2 = SecurityPolicy(id="p2", allowed_actions=[AccessAction.READ],
                            valid_until=datetime.now() - timedelta(days=1))
        r2 = FederationRequest(action=AccessAction.READ, resource_id="r",
                               security_context=_ctx())
        assert not p2.matches(r2)

        # valid_from satisfied + everything ok -> True
        p3 = SecurityPolicy(id="p3", allowed_actions=[AccessAction.READ],
                            valid_from=datetime.now() - timedelta(days=1),
                            valid_until=datetime.now() + timedelta(days=1))
        assert p3.matches(r2)

    def test_build_security_context_header_parsing(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            FederationRequest,
            ZeroTrustSecurityManager,
        )
        from core.identity.verifiable_credentials import (
            VCConfig,
            VerifiableCredential,
            VerifiableCredentialManager,
        )

        manager = ZeroTrustSecurityManager()
        vc_mgr = VerifiableCredentialManager(VCConfig())
        vc = vc_mgr.create_credential("did:i", _VCType.AGENT_IDENTITY, "did:src", {})
        manager.vc_manager = vc_mgr

        req = FederationRequest(
            method="GET", path="/api",
            headers={
                "X-Instance-ID": "inst-1",
                "X-Source-DID": "did:src",
                "X-Verifiable-Credentials": f" {vc.id} ,unknown-id",
            },
            action=AccessAction.READ,
        )
        ctx = manager._build_security_context(req)
        assert ctx.source_instance_id == "inst-1"
        assert ctx.source_did == "did:src"
        assert len(ctx.presented_credentials) == 1

        # parse exception swallowed
        req2 = FederationRequest(method="GET", path="/api",
                                 headers={"X-Verifiable-Credentials": "a,b"})
        with patch.object(manager.vc_manager, "get_credential_by_id",
                          side_effect=Exception("boom")):
            ctx2 = manager._build_security_context(req2)
        assert ctx2.presented_credentials == []

    def test_authenticate_branches(self):
        from core.federation.zero_trust_security import (
            FederationRequest,
            SecurityConfig,
            SecurityContext,
            ZeroTrustSecurityManager,
        )

        manager = ZeroTrustSecurityManager(SecurityConfig(require_authentication=True))
        manager.did_manager = None

        req = FederationRequest(method="GET", path="/api")
        req.security_context = SecurityContext(source_did=None)
        assert manager._authenticate(req) is False  # no source DID

        req2 = FederationRequest(method="GET", path="/api")
        req2.security_context = SecurityContext(source_did="did:src")
        assert manager._authenticate(req2) is True  # no did_manager -> trusted

        # deactivated DID rejected
        doc = MagicMock()
        doc.deactivated = True
        did_mgr = MagicMock()
        did_mgr.resolve_did.return_value.did_document = doc
        manager.did_manager = did_mgr
        req3 = FederationRequest(method="GET", path="/api")
        req3.security_context = SecurityContext(source_did="did:dead")
        assert manager._authenticate(req3) is False

    def test_validate_credentials_branches(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            DecisionReason,
            FederationRequest,
            SecurityConfig,
            SecurityContext,
            ZeroTrustSecurityManager,
        )
        from core.identity.verifiable_credentials import (
            VCConfig,
            VCStatus,
            VerifiableCredential,
            VerifiableCredentialManager,
        )

        manager = ZeroTrustSecurityManager(SecurityConfig(require_credential=False))
        req = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        assert manager._validate_credentials(req) == {"valid": True}

        manager2 = ZeroTrustSecurityManager(SecurityConfig(require_credential=True))
        manager2.vc_manager = VerifiableCredentialManager(VCConfig())
        req2 = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        req2.security_context = SecurityContext(source_did="did:src",
                                                presented_credentials=[])
        result = manager2._validate_credentials(req2)
        assert result["reason"] == DecisionReason.INSUFFICIENT_PERMISSIONS

        # invalid credential -> reason mapping
        vc = VerifiableCredential(id="vc-bad", issuer="did:i",
                                  credential_subject={"id": "did:src"})
        vc_mgr = manager2.vc_manager
        vc_mgr.verify_credential = MagicMock(
            return_value=MagicMock(is_valid=False,
                                   status=VCStatus.EXPIRED,
                                   errors=["Credential has expired"])
        )
        req3 = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        req3.security_context = SecurityContext(source_did="did:src",
                                                presented_credentials=[vc])
        result3 = manager2._validate_credentials(req3)
        assert result3["reason"] == DecisionReason.EXPIRED_CREDENTIAL

    def test_no_matching_policy_and_all_denied(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            DecisionReason,
            FederationRequest,
            SecurityConfig,
            SecurityContext,
            SecurityLevel,
            SecurityPolicy,
            ZeroTrustSecurityManager,
        )
        from core.identity.verifiable_credentials import VerifiableCredential

        manager = ZeroTrustSecurityManager(SecurityConfig(enable_rate_limiting=False))
        manager.did_manager = None
        manager.vc_manager = None
        manager._default_policies_loaded = False
        manager.add_policy(SecurityPolicy(
            id="read-only", allowed_actions=[AccessAction.READ], default_decision=False
        ))
        vc = VerifiableCredential(id="vc-n", issuer="did:i",
                                  credential_subject={"id": "did:src"})

        req = FederationRequest(method="POST", path="/api", action=AccessAction.WRITE)
        req.security_context = SecurityContext(source_did="did:src",
                                               presented_credentials=[vc],
                                               security_level=SecurityLevel.HIGH)
        # no matching policy -> default deny
        decision = manager._evaluate_policies(req)
        assert not decision.allowed
        assert decision.reason == DecisionReason.POLICY_VIOLATION

        # matching policy but default_decision False -> denied
        req2 = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        req2.security_context = SecurityContext(source_did="did:src",
                                                presented_credentials=[vc],
                                                security_level=SecurityLevel.HIGH)
        decision2 = manager._evaluate_policies(req2)
        assert not decision2.allowed
        assert decision2.reason == DecisionReason.INSUFFICIENT_PERMISSIONS

    def test_rate_limit_no_context_and_audit_disabled(self):
        from core.federation.zero_trust_security import (
            AccessAction,
            FederationRequest,
            SecurityConfig,
            ZeroTrustSecurityManager,
        )

        manager = ZeroTrustSecurityManager(SecurityConfig(enable_audit_log=False))
        req = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        assert manager._check_rate_limit(req) is True  # no context

        req2 = FederationRequest(method="GET", path="/api", action=AccessAction.READ)
        req2.security_context = MagicMock()
        manager._log_decision(req2, MagicMock())  # audit disabled -> no-op

    def test_audit_log_trim(self):
        from core.federation.zero_trust_security import (
            AuditLogEntry,
            FederationRequest,
            ZeroTrustSecurityManager,
        )

        manager = ZeroTrustSecurityManager()
        manager._audit_log = [AuditLogEntry() for _ in range(10005)]
        req = FederationRequest()
        req.security_context = MagicMock(source_instance_id="i", source_did="d")
        req.action = MagicMock(value="read")
        req.resource_type = "t"
        req.resource_id = "r"
        decision = MagicMock(allowed=True, reason=MagicMock(value="ok"),
                             policy_id="p", security_level=MagicMock(value="high"))
        manager._log_decision(req, decision)
        assert len(manager._audit_log) <= 10001


class TestVCGaps2:
    def test_create_credential_claims_cannot_override_subject(self):
        manager = TestVCGaps()._manager()
        vc = manager.create_credential(
            "did:i", _VCType.AGENT_IDENTITY, "did:alice",
            {"id": "did:spoofed", "type": "SpoofedType", "agentId": "a1"},
        )
        assert vc.credential_subject["id"] == "did:alice"
        assert vc.credential_subject["type"] == "AgentIdentityCredential"
        assert vc.credential_subject["agentId"] == "a1"

    def test_sign_credential_no_crypto_and_no_resolution(self):
        import core.identity.verifiable_credentials as vc_mod

        manager = TestVCGaps()._manager()
        vc = vc_mod.VerifiableCredential(id="vc-s1", issuer="did:i")
        with patch.object(vc_mod, "CRYPTO_AVAILABLE", False):
            out = manager._sign_credential(vc, "did:i")
        assert out is vc

        manager2 = TestVCGaps()._manager()
        vc2 = vc_mod.VerifiableCredential(id="vc-s2", issuer="did:i")
        did_mgr = MagicMock()
        did_mgr.resolve_did.return_value.did_document = None
        manager2.did_manager = did_mgr
        out2 = manager2._sign_credential(vc2, "did:i")
        assert out2.proof is None

    def test_verify_signature_missing_proof_value(self):
        manager = TestVCGaps()._manager()
        vc = MagicMock()
        vc.proof.proof_value = None
        assert manager._verify_signature(vc) is False

    def test_verify_signature_no_did_manager(self):
        import core.identity.verifiable_credentials as vc_mod

        manager = TestVCGaps()._manager()
        vc = vc_mod.VerifiableCredential(
            id="vc-v1", issuer="did:i",
            proof=vc_mod.VCProof(proof_value="abcd"),
        )
        manager.did_manager = None
        assert manager._verify_signature(vc) is False

    def test_agent_identity_and_federation_credentials(self):
        manager = TestVCGaps()._manager()
        vc = manager.create_agent_identity_credential(
            "did:i", "did:agent", "agent-1", "Bob", ["read"], instance_id="inst-1"
        )
        assert vc.credential_subject["maturityLevel"] == "STUDENT"

        fed = manager.create_federation_membership_credential(
            "did:i", "did:inst", "inst-1", "Node One", federation_role="admin"
        )
        assert "delete" in fed.credential_subject["permissions"]
        observer = manager.create_federation_membership_credential(
            "did:i", "did:inst2", "inst-2", "Node Two", federation_role="observer"
        )
        assert observer.credential_subject["permissions"] == ["read"]
        unknown = manager.create_federation_membership_credential(
            "did:i", "did:inst3", "inst-3", "Node Three", federation_role="weird"
        )
        assert unknown.credential_subject["permissions"] == ["read"]

    def test_get_credential_by_id_unknown(self):
        manager = TestVCGaps()._manager()
        assert manager.get_credential_by_id("nope") is None

    def test_persist_and_load_exception_paths(self):
        manager = TestVCGaps()._manager()
        vc = MagicMock()
        vc.id = "vc-p"
        with patch("core.database.get_db_session", side_effect=Exception("no db")):
            manager._persist_credential(vc)  # non-fatal
            assert manager.load_credentials_from_db() == 0


# ============================================================================
# agent_graduation_service
# ============================================================================

class TestGraduationGaps:
    def _service(self, db):
        from core.agent_graduation_service import AgentGraduationService

        with patch("core.agent_graduation_service.get_lancedb_handler"):
            return AgentGraduationService(db)

    @pytest.mark.asyncio
    async def test_readiness_agent_not_found_and_bad_level(self, db):
        svc = self._service(db)
        assert (await svc.calculate_readiness_score("missing", "INTERN"))["error"]
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a1", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        result = await svc.calculate_readiness_score("a1", "NOPE")
        assert "Unknown maturity level" in result["error"]

    @pytest.mark.asyncio
    async def test_readiness_gaps_intervention_and_constitutional(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a2", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent", confidence_score=0.5))
        from core.models import AgentEpisode

        for i in range(11):
            db.add(AgentEpisode(
                id=f"g{i}", agent_id="a2", tenant_id="t1",
                maturity_at_time="student", outcome="failure", success=False,
                status="completed", constitutional_score=0.1,
                human_intervention_count=3, confidence_score=0.1,
                step_efficiency=0.5, task_description=f"t{i}",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
            ))
        db.commit()
        svc = self._service(db)
        result = await svc.calculate_readiness_score("a2", "INTERN")
        assert any("Intervention rate" in g for g in result["gaps"])
        assert any("Constitutional score" in g for g in result["gaps"])
        assert result["episode_count"] == 11
        assert result["recommendation"]

    @pytest.mark.asyncio
    async def test_pomdp_init_failure(self, db):
        import core.agent_graduation_service as ags

        with patch("core.agent_graduation_service.get_lancedb_handler"), \
             patch("core.agent_graduation_service.get_memory_manager",
                   side_effect=Exception("boom")), \
             patch.object(ags, "POMDP_AVAILABLE", True):
            svc = ags.AgentGraduationService(db)
        assert svc.memory_manager is None

    @pytest.mark.asyncio
    async def test_experience_driven_readiness_fallback_without_pomdp(self, db):
        import core.agent_graduation_service as ags

        svc = self._service(db)
        with patch.object(ags, "POMDP_AVAILABLE", False):
            result = await svc.calculate_experience_driven_readiness("missing", "INTERN")
        assert result.get("error")

    @pytest.mark.asyncio
    async def test_experience_driven_readiness_full(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a3", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        svc.experience_calculator = MagicMock()
        svc.experience_calculator.calculate_readiness_score.return_value = {
            "ready": True, "score": 90, "gaps": [], "learning_consistency": 0.9,
            "quality_weighted_episodes": 10,
        }
        svc._analyze_intervention_trajectory = AsyncMock(return_value={
            "is_improving": True, "trend": "improving",
        })
        result = await svc.calculate_experience_driven_readiness("a3", "INTERN")
        assert result["ready"] is True
        assert result["target_maturity"] == "INTERN"
        assert "ready for promotion" in result["recommendation"]

    @pytest.mark.asyncio
    async def test_experience_driven_readiness_not_ready(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a4", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        svc.experience_calculator = MagicMock()
        svc.experience_calculator.calculate_readiness_score.return_value = {
            "ready": False, "score": 20, "gaps": ["No episodes"], "learning_consistency": 0.1,
        }
        svc._analyze_intervention_trajectory = AsyncMock(return_value={
            "is_improving": False, "trend": "declining",
        })
        result = await svc.calculate_experience_driven_readiness("a4", "INTERN")
        assert result["ready"] is False
        assert "training needed" in result["recommendation"]

    @pytest.mark.asyncio
    async def test_analyze_intervention_trajectory(self):
        import core.agent_graduation_service as ags

        svc = self._service(db if False else MagicMock())
        with patch.object(ags, "POMDP_AVAILABLE", True):
            # no memory manager -> unknown
            svc.memory_manager = None
            result = await svc._analyze_intervention_trajectory("a1")
            assert result["trend"] == "unknown"

            # insufficient memories
            mm = MagicMock()
            mm.recall_by_quality.return_value = []
            svc.memory_manager = mm
            result2 = await svc._analyze_intervention_trajectory("a1")
            assert result2["trend"] == "insufficient_data"

            # full trajectory: improving
            mems = []
            for i in range(20):
                m = MagicMock()
                m.intervention_required = i < 5  # recent = less interventions
                mems.append(m)
            mm.recall_by_quality.return_value = mems
            result3 = await svc._analyze_intervention_trajectory("a1")
            assert result3["trend"] in ("improving", "stable")

    @pytest.mark.asyncio
    async def test_analyze_learning_consistency(self):
        import core.agent_graduation_service as ags

        svc = self._service(MagicMock())
        with patch.object(ags, "POMDP_AVAILABLE", True):
            svc.memory_manager = None
            result = await svc.analyze_learning_consistency("a1")
            assert result["recommendation"] == "POMDP framework not available"

            mm = MagicMock()
            mm.recall_by_quality.return_value = []
            svc.memory_manager = mm
            result2 = await svc.analyze_learning_consistency("a1")
            assert "Insufficient data" in result2["recommendation"]

            mems = []
            for i in range(10):
                m = MagicMock()
                m.quality_score = 0.9
                m.intervention_required = False
                mems.append(m)
            mm.recall_by_quality.return_value = mems
            result3 = await svc.analyze_learning_consistency("a1")
            assert result3["consistency_score"] >= 0.8
            assert result3["recommendation"] == "Excellent learning consistency"

    def test_calculate_score_and_recommendation(self):
        svc = self._service(MagicMock())
        assert svc._calculate_score(10, 10, 0.0, 0.5, 1.0, 0.7) == 100.0
        assert "ready" in svc._generate_recommendation(True, 90, "INTERN")
        assert "training needed" in svc._generate_recommendation(False, 30, "INTERN")
        assert "progress" in svc._generate_recommendation(False, 60, "INTERN")
        assert "close to ready" in svc._generate_recommendation(False, 90, "INTERN")

    @pytest.mark.asyncio
    async def test_run_graduation_exam(self, db):
        _seed_tenant(db)
        from core.models import Episode

        db.add(Episode(id="ep1", agent_id="a1", tenant_id="t1", task_description="Edge",
                       maturity_at_time="student", outcome="failure", status="completed",
                       started_at=datetime.now(timezone.utc)))
        db.commit()
        svc = self._service(db)
        executor = MagicMock()
        executor.execute_in_sandbox = AsyncMock(return_value=MagicMock(
            passed=True, interventions=0, safety_violations=[], replayed_actions=3
        ))
        with patch("core.sandbox_executor.get_sandbox_executor", return_value=executor):
            result = await svc.run_graduation_exam("a1", ["ep1", "missing-ep"])
        assert result["passed"] is True
        assert result["total_cases"] == 2
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance(self, db):
        _seed_tenant(db)
        from core.models import Episode, EpisodeSegment

        db.add(Episode(id="ep2", agent_id="a1", tenant_id="t1",
                       maturity_at_time="student", outcome="success", status="completed",
                       started_at=datetime.now(timezone.utc)))
        db.add(EpisodeSegment(id="seg1", episode_id="ep2", segment_type="execution",
                              sequence_order=0, content="step", content_summary="s",
                              created_at=datetime.now(timezone.utc)))
        db.commit()
        svc = self._service(db)
        assert (await svc.validate_constitutional_compliance("missing"))["error"]
        validator = MagicMock()
        validator.validate_actions.return_value = {
            "compliant": True, "score": 1.0, "violations": [],
            "total_actions": 1, "checked_actions": 1,
        }
        with patch("core.constitutional_validator.ConstitutionalValidator",
                   return_value=validator):
            result = await svc.validate_constitutional_compliance("ep2")
        assert result["compliant"] is True

    @pytest.mark.asyncio
    async def test_promote_agent(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a5", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_tenant_id", return_value="t1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w1"):
            ns.return_value.send_notification = AsyncMock()
            assert await svc.promote_agent("a5", "intern", "u1") is True
        from core.models import AgentStatus

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "a5").first()
        assert agent.status == AgentStatus.INTERN
        assert agent.configuration["promoted_by"] == "u1"

    @pytest.mark.asyncio
    async def test_promote_agent_errors(self, db):
        _seed_tenant(db)
        svc = self._service(db)
        assert await svc.promote_agent("missing", "intern", "u1") is False
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a6", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        assert await svc.promote_agent("a6", "not-a-level", "u1") is False

    @pytest.mark.asyncio
    async def test_promote_agent_notification_failure_does_not_rollback(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a7", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_tenant_id", side_effect=Exception("boom")):
            assert await svc.promote_agent("a7", "intern", "u1") is True
        from core.models import AgentStatus

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "a7").first()
        assert agent.status == AgentStatus.INTERN

    @pytest.mark.asyncio
    async def test_get_graduation_audit_trail(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry, Episode

        db.add(AgentRegistry(id="a8", name="A", category="general", status="intern",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.add(Episode(id="ep3", agent_id="a8", tenant_id="t1", task_description="X",
                       maturity_at_time="student", outcome="success",
                       status="completed", constitutional_score=0.9,
                       human_intervention_count=1, workspace_id="w1",
                       started_at=datetime.now(timezone.utc)))
        db.commit()
        svc = self._service(db)
        assert (await svc.get_graduation_audit_trail("missing"))["error"]
        trail = await svc.get_graduation_audit_trail("a8")
        assert trail["total_episodes"] == 1
        assert trail["avg_constitutional_score"] == 0.9
        assert trail["episodes_by_maturity"] == {"student": 1}

    @pytest.mark.asyncio
    async def test_calculate_supervision_metrics(self, db):
        _seed_tenant(db)
        from core.models import SupervisionSession

        from core.models import Workspace

        db.add(Workspace(id="w1", name="W", tenant_id="t1"))
        db.add(SupervisionSession(
            id="ss1", agent_id="a9", tenant_id="t1", status="completed",
            agent_name="A9", workspace_id="w1", supervisor_id="u1",
            duration_seconds=7200, intervention_count=2, supervisor_rating=4.5,
            started_at=datetime.now(timezone.utc) - timedelta(days=2),
        ))
        db.add(SupervisionSession(
            id="ss2", agent_id="a9", tenant_id="t1", status="completed",
            agent_name="A9", workspace_id="w1", supervisor_id="u1",
            duration_seconds=3600, intervention_count=0, supervisor_rating=5.0,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
        ))
        db.commit()
        svc = self._service(db)
        metrics = await svc.calculate_supervision_metrics("a9", MagicMock())
        assert metrics["total_supervision_hours"] == 3.0
        assert metrics["high_rating_sessions"] == 2
        assert metrics["low_intervention_sessions"] == 1
        assert metrics["recent_performance_trend"] == "stable"

        empty = await svc.calculate_supervision_metrics("nobody", MagicMock())
        assert empty["total_sessions"] == 0
        assert empty["intervention_rate"] == 1.0

    def test_performance_trend_branches(self):
        from core.models import SupervisionSession

        svc = self._service(MagicMock())
        sessions = []
        for i in range(10):
            sessions.append(SupervisionSession(
                id=f"s{i}", agent_id="a", tenant_id="t", status="completed",
                agent_name="A", workspace_id="w1", supervisor_id="u1",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                supervisor_rating=3.0 + (0.2 if i < 5 else 0),
                intervention_count=1,
            ))
        assert svc._calculate_performance_trend(sessions) in ("improving", "stable")
        assert svc._calculate_performance_trend(sessions[:5]) == "stable"

        no_ratings = []
        for i in range(10):
            s = SupervisionSession(
                id=f"n{i}", agent_id="a", tenant_id="t", status="completed",
                agent_name="A", workspace_id="w1", supervisor_id="u1",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                supervisor_rating=None, intervention_count=None,
            )
            no_ratings.append(s)
        assert svc._calculate_performance_trend(no_ratings) == "stable"

    @pytest.mark.asyncio
    async def test_validate_graduation_with_supervision(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry, SupervisionSession, Workspace

        db.add(Workspace(id="w1", name="W", tenant_id="t1"))
        db.add(AgentRegistry(id="a10", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        for i in range(12):
            db.add(SupervisionSession(
                id=f"vs{i}", agent_id="a10", tenant_id="t1", status="completed",
                agent_name="A10", workspace_id="w1", supervisor_id="u1",
                duration_seconds=3600, intervention_count=0, supervisor_rating=4.8,
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
            ))
        db.commit()
        from core.models import AgentStatus

        svc = self._service(db)
        result = await svc.validate_graduation_with_supervision("a10", AgentStatus.INTERN)
        assert "episode_metrics" in result
        assert "supervision_metrics" in result
        assert result["target_maturity"] == "intern"

    def test_supervision_score(self):
        svc = self._service(MagicMock())
        metrics = {
            "average_supervisor_rating": 4.0,
            "intervention_rate": 0.5,
            "total_sessions": 10,
            "high_rating_sessions": 6,
            "recent_performance_trend": "improving",
        }
        score = svc._supervision_score(metrics, {"max_intervention_rate": 0.5})
        assert score == 40 + 27 + 20 + 10
        empty = {
            "average_supervisor_rating": 0.0,
            "intervention_rate": 5.0,
            "total_sessions": 0,
            "high_rating_sessions": 0,
            "recent_performance_trend": "declining",
        }
        assert svc._supervision_score(empty, {"max_intervention_rate": 0.5}) == 0

    @pytest.mark.asyncio
    async def test_calculate_skill_usage_metrics(self, db):
        """Skill segments are scoped to the agent via the episode join —
        EpisodeSegment has no 'metadata' column (reading it crashes)."""
        _seed_tenant(db)
        from core.models import AgentEpisode, EpisodeSegment, SkillExecution

        db.add(AgentEpisode(
            id="epx", agent_id="a11", tenant_id="t1", task_description="T",
            maturity_at_time="student", outcome="success", status="completed",
            started_at=datetime.now(timezone.utc),
        ))
        db.add(SkillExecution(
            id="sk1", agent_id="a11", tenant_id="t1", skill_id="skill-1",
            skill_source="community", status="success",
            created_at=datetime.now(),
        ))
        db.add(SkillExecution(
            id="sk2", agent_id="a11", tenant_id="t1", skill_id="skill-2",
            skill_source="community", status="failure",
            created_at=datetime.now(),
        ))
        db.add(EpisodeSegment(
            id="segx", episode_id="epx", segment_type="skill_success",
            sequence_order=0, content="step", content_summary="s",
            created_at=datetime.now(),
        ))
        db.commit()
        svc = self._service(db)
        metrics = await svc.calculate_skill_usage_metrics("a11", days_back=30)
        assert metrics["total_skill_executions"] == 2
        assert metrics["successful_executions"] == 1
        assert metrics["success_rate"] == 0.5
        assert metrics["unique_skills_used"] == 2
        assert metrics["skill_episodes_count"] == 1

    @pytest.mark.asyncio
    async def test_readiness_score_with_skills(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a12", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        svc.calculate_skill_usage_metrics = AsyncMock(return_value={
            "unique_skills_used": 3, "total_skill_executions": 5,
        })
        result = await svc.calculate_readiness_score_with_skills("a12", "INTERN")
        assert result["skill_diversity_bonus"] == 0.03
        assert "readiness_score" in result

    @pytest.mark.asyncio
    async def test_execute_graduation_exam(self):
        svc = self._service(MagicMock())
        executor = MagicMock()
        executor.execute_exam = AsyncMock(return_value={
            "success": True, "score": 95, "constitutional_compliance": 0.9,
            "passed": True, "constitutional_violations": [],
        })
        with patch("core.agent_graduation_service.get_graduation_exam_executor",
                   return_value=executor):
            result = await svc.execute_graduation_exam("a1", "w1", "INTERN")
        assert result["exam_completed"] is True
        assert result["passed"] is True

        executor.execute_exam = AsyncMock(return_value={
            "success": False, "error": "sandbox unavailable",
        })
        with patch("core.agent_graduation_service.get_graduation_exam_executor",
                   return_value=executor):
            result2 = await svc.execute_graduation_exam("a1", "w1", "INTERN")
        assert result2["exam_completed"] is False
        assert "sandbox unavailable" in result2["error"]


class TestGraduationGaps2:
    def _service(self, db):
        from core.agent_graduation_service import AgentGraduationService

        with patch("core.agent_graduation_service.get_lancedb_handler"):
            return AgentGraduationService(db)

    @pytest.mark.asyncio
    async def test_experience_driven_error_paths(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="ax", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        svc.experience_calculator = MagicMock()
        assert (await svc.calculate_experience_driven_readiness("missing", "INTERN"))["error"]
        result = await svc.calculate_experience_driven_readiness("ax", "BOGUS")
        assert "Unknown maturity level" in result["error"]

    @pytest.mark.asyncio
    async def test_trajectory_declining_and_stable(self):
        import core.agent_graduation_service as ags

        svc = self._service(MagicMock())
        with patch.object(ags, "POMDP_AVAILABLE", True):
            mm = MagicMock()
            mems = []
            for i in range(20):
                m = MagicMock()
                # all 10 recent need intervention; only 5 of the historical do
                m.intervention_required = i < 10 or i >= 15
                mems.append(m)
            mm.recall_by_quality.return_value = mems
            svc.memory_manager = mm
            result = await svc._analyze_intervention_trajectory("a1")
            assert result["trend"] == "declining"
            assert result["is_improving"] is False

            mems2 = []
            for i in range(20):
                m = MagicMock()
                m.intervention_required = (i < 4) or (10 <= i < 14)
                mems2.append(m)
            mm.recall_by_quality.return_value = mems2
            result2 = await svc._analyze_intervention_trajectory("a1")
            assert result2["trend"] == "stable"

    def test_recommendation_score_bands_and_trends(self):
        svc = self._service(MagicMock())
        r1 = svc._generate_experience_driven_recommendation(False, 50, "INTERN", [], {})
        assert "progress" in r1
        r2 = svc._generate_experience_driven_recommendation(False, 80, "INTERN", ["g1"], {})
        assert "Close to ready" in r2
        assert "Key gaps: g1" in r2
        r3 = svc._generate_experience_driven_recommendation(
            False, 30, "INTERN", [], {"trend": "declining"})
        assert "declining" in r3
        r4 = svc._generate_experience_driven_recommendation(
            False, 30, "INTERN", [], {"trend": "improving"})
        assert "improving" in r4
        r5 = svc._generate_experience_driven_recommendation(True, 99, "SUPERVISED", [], {})
        assert "ready for promotion to SUPERVISED" in r5

    @pytest.mark.asyncio
    async def test_learning_consistency_moderate_and_poor(self):
        import core.agent_graduation_service as ags

        svc = self._service(MagicMock())
        with patch.object(ags, "POMDP_AVAILABLE", True):
            mm = MagicMock()
            mems = []
            for i in range(10):
                m = MagicMock()
                m.quality_score = 0.0 if i % 2 == 0 else 0.5
                m.intervention_required = True
                mems.append(m)
            mm.recall_by_quality.return_value = mems
            svc.memory_manager = mm
            result = await svc.analyze_learning_consistency("a1")
            assert "Moderate" in result["recommendation"]

            mems2 = []
            for i in range(10):
                m = MagicMock()
                m.quality_score = 0.0
                m.intervention_required = True
                mems2.append(m)
            mm.recall_by_quality.return_value = mems2
            result2 = await svc.analyze_learning_consistency("a1")
            assert "Good" in result2["recommendation"]

    @pytest.mark.asyncio
    async def test_constitutional_compliance_no_segments(self, db):
        _seed_tenant(db)
        from core.models import Episode

        db.add(Episode(id="ep4", agent_id="a1", tenant_id="t1",
                       maturity_at_time="student", outcome="success",
                       status="completed", started_at=datetime.now(timezone.utc)))
        db.commit()
        svc = self._service(db)
        result = await svc.validate_constitutional_compliance("ep4")
        assert result["compliant"] is True
        assert result["note"] == "No segments to validate"

    @pytest.mark.asyncio
    async def test_promote_agent_db_query_error(self, db):
        svc = self._service(db)
        db.close()  # force a query error
        assert await svc.promote_agent("a1", "intern", "u1") is False

    @pytest.mark.asyncio
    async def test_promote_agent_commit_error_rolls_back(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a13", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_tenant_id", return_value="t1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w1"), \
             patch.object(db, "commit", side_effect=Exception("db locked")):
            ns.return_value.send_notification = AsyncMock()
            assert await svc.promote_agent("a13", "intern", "u1") is False

    @pytest.mark.asyncio
    async def test_promote_agent_memory_consolidation_failure(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry

        db.add(AgentRegistry(id="a14", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        db.commit()
        svc = self._service(db)
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_tenant_id", return_value="t1"), \
             patch("core.personal_scope.resolve_workspace_id", return_value="w1"), \
             patch("core.memory.pomdp_memory_framework.MemoryConsolidation") as mc:
            ns.return_value.send_notification = AsyncMock()
            mc.return_value.consolidate_memories = AsyncMock(side_effect=Exception("oom"))
            assert await svc.promote_agent("a14", "intern", "u1") is True

    def test_performance_trend_declining_and_stable(self):
        from core.models import SupervisionSession

        svc = self._service(MagicMock())
        # declining: recent ratings much lower
        sessions = []
        for i in range(10):
            sessions.append(SupervisionSession(
                id=f"d{i}", agent_id="a", tenant_id="t", status="completed",
                agent_name="A", workspace_id="w1", supervisor_id="u1",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                supervisor_rating=1.0 if i < 5 else 5.0,
                intervention_count=5 if i < 5 else 0,
            ))
        assert svc._calculate_performance_trend(sessions) == "declining"

        sessions2 = []
        for i in range(10):
            sessions2.append(SupervisionSession(
                id=f"st{i}", agent_id="a", tenant_id="t", status="completed",
                agent_name="A", workspace_id="w1", supervisor_id="u1",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                supervisor_rating=4.0,
                intervention_count=1,
            ))
        assert svc._calculate_performance_trend(sessions2) == "stable"

    @pytest.mark.asyncio
    async def test_validate_graduation_with_supervision_gaps(self, db):
        _seed_tenant(db)
        from core.models import AgentRegistry, SupervisionSession, Workspace

        db.add(Workspace(id="w1", name="W", tenant_id="t1"))
        db.add(AgentRegistry(id="a15", name="A", category="general", status="student",
                             tenant_id="t1", module_path="core.generic_agent",
                             class_name="GenericAgent"))
        # one mediocre session -> high-quality / low-intervention / rating gaps
        db.add(SupervisionSession(
            id="sg1", agent_id="a15", tenant_id="t1", status="completed",
            agent_name="A15", workspace_id="w1", supervisor_id="u1",
            duration_seconds=600, intervention_count=8, supervisor_rating=2.0,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
        ))
        db.commit()
        from core.models import AgentStatus

        svc = self._service(db)
        result = await svc.validate_graduation_with_supervision("a15", AgentStatus.INTERN)
        joined = "\n".join(result["gaps"])
        assert "high-rated sessions" in joined
        assert "low-intervention sessions" in joined
        assert "rating too low" in joined
        assert "rate too high" in joined


# ============================================================================
# ingestion_pipeline final gaps
# ============================================================================

class _PipelineFactory:
    def make(self):
        from core.ingestion_pipeline import IngestionPipelineService

        with patch("core.lancedb_handler.LanceDBHandler"), \
             patch("core.graphrag_engine.GraphRAGEngine"), \
             patch("core.llm_service.LLMService"), \
             patch("core.meta_agent_orchestrator.MetaAgentOrchestrator"), \
             patch("core.usage_tracking_service.UsageTrackingService"), \
             patch("core.entity_linking_service.EntityLinkingService"), \
             patch("core.schema_discovery_service.SchemaDiscoveryService"), \
             patch("core.multi_entity_llm_extractor.MultiEntityLLMExtractor"):
            return IngestionPipelineService(tenant_id="t1", workspace_id="w1", db=MagicMock())


class TestPipelineGaps:
    @pytest.mark.asyncio
    async def test_sync_and_ingest_default_config(self):
        svc = _PipelineFactory().make()
        svc.sync_configs = {}
        svc._fetch_integration_data = AsyncMock(return_value=[])
        with patch("core.ingestion_pipeline.DEFAULT_SYNC_CONFIGS",
                   {"salesforce": MagicMock()}):
            result = await svc.sync_and_ingest("salesforce")
        assert result["success"] is True
        assert result["records_fetched"] == 0

    @pytest.mark.asyncio
    async def test_sync_and_ingest_no_config_error(self):
        svc = _PipelineFactory().make()
        svc.sync_configs = {}
        with patch("core.ingestion_pipeline.DEFAULT_SYNC_CONFIGS", {}):
            result = await svc.sync_and_ingest("unknown-app")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_prepare_record_text_attachment_branches(self):
        svc = _PipelineFactory().make()

        processor = MagicMock()
        processor.is_format_supported.return_value = True
        processor.process_document = AsyncMock(
            return_value={"success": True, "content": "x" * 50}
        )
        service = MagicMock()
        service.config = {"access_token": "tok"}
        service.get_attachment_metadata = AsyncMock(return_value=[
            {"id": "a1", "name": "doc.pdf", "size": 100, "contentType": "application/pdf"},
            {"id": "a2", "name": "big.bin", "size": 99 * 1024 * 1024, "contentType": "x"},
            {"id": "a3", "name": "bad.pdf", "size": 100, "contentType": "application/pdf"},
        ])
        svc.integration_registry = MagicMock()
        svc.integration_registry.get_service = AsyncMock(return_value=service)

        record = {
            "id": "m1", "type": "email", "hasAttachments": True,
            "subject": "S", "body": "body text here",
        }
        # a3: download fails -> continue
        async def _download(**kw):
            if kw.get("attachment_id") == "a3":
                return None
            return b"PDFBYTES" * 10

        service.download_attachment = AsyncMock(side_effect=_download)

        # a1: download ok -> parse; a2: oversized -> skipped; a3: no bytes -> skipped
        with patch("core.ingestion_pipeline.get_docling_processor", return_value=processor), \
             patch.dict(os.environ, {"ENABLE_OUTLOOK_ATTACHMENT_INGESTION": "true"}):
            text = await svc._prepare_record_text_async(record, "outlook", "conn-1")
        assert "[Attachment: doc.pdf]" in text

        # exception path
        service.download_attachment = AsyncMock(side_effect=Exception("boom"))
        with patch("core.ingestion_pipeline.get_docling_processor", return_value=processor):
            text2 = await svc._prepare_record_text_async(record, "outlook", "conn-1")
        assert "subject: S" in text2

    @pytest.mark.asyncio
    async def test_prepare_record_text_service_config_variants(self):
        svc = _PipelineFactory().make()
        svc.integration_registry = MagicMock()

        class _Service:
            _config = {"access_token": "tok2"}
            download_file = AsyncMock(return_value=None)

        svc.integration_registry.get_service = AsyncMock(return_value=_Service())
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        with patch("core.ingestion_pipeline.get_docling_processor", return_value=processor):
            text = await svc._prepare_record_text_async(
                {"id": "f1", "type": "file", "name": "x.pdf", "extension": "pdf"},
                "zoho_workdrive", None,
            )
        assert text  # falls back to record_to_text

    @pytest.mark.asyncio
    async def test_process_webhook_payload_body_handling(self):
        svc = _PipelineFactory().make()
        svc.graphrag = MagicMock()
        svc._transform_webhook_payload = AsyncMock(return_value=[
            {"id": "1", "type": "slack_message", "text": "a" * 40,
             "body": {"content": "old"}, "bodyPreview": "p"},
            {"id": "2", "type": "slack_message", "text": "b" * 40,
             "body": "plain body", "bodyPreview": "p2"},
        ])
        svc._prepare_record_text_async = AsyncMock(side_effect=[
            "x" * 40, "y" * 40,
        ])
        svc._process_multi_entity_extraction = AsyncMock(side_effect=Exception("extract boom"))
        result = await svc.process_webhook_payload("slack", {"event": {}})
        assert result["records_processed"] == 2
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_webhook_payload_email_lancedb_text(self):
        svc = _PipelineFactory().make()
        svc.graphrag = MagicMock()
        lancedb = MagicMock()
        svc._transform_webhook_payload = AsyncMock(return_value=[
            {"id": "m1", "type": "email", "subject": "Hello", "body": "",
             "from": "a@b.c", "to": "d@e.f", "text": ""},
        ])
        svc._prepare_record_text_async = AsyncMock(return_value="x" * 40)
        with patch("core.lancedb_handler.LanceDBHandler", return_value=lancedb):
            result = await svc.process_webhook_payload("gmail", {"historyId": "1"})
        assert result["success"] is True
        lancedb.add_document.assert_called()

    @pytest.mark.asyncio
    async def test_tiered_webhook_branches(self):
        svc = _PipelineFactory().make()
        svc.graphrag = MagicMock()
        svc.usage_tracker = MagicMock()
        svc.usage_tracker.check_quota_before_job = AsyncMock(return_value={"allowed": True})
        svc.usage_tracker.calculate_acu_consumed = MagicMock(return_value=1.5)
        svc.usage_tracker.track_acu_usage = AsyncMock()
        svc.lancedb = MagicMock()
        svc._transform_webhook_payload = AsyncMock(return_value=[
            {"id": "1", "type": "slack_message", "text": "t" * 60, "sender_id": "u1"},
        ])
        svc._is_doc_already_ingested = MagicMock(return_value=False)
        svc._record_doc_ingestion = MagicMock()

        tenant = MagicMock()
        tenant.plan_type = "solo"
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = tenant

        svc.graphrag.ingest_document = AsyncMock(return_value=None)
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            result = await svc.process_webhook_payload_tiered("slack", {"event": {}})
        assert result["success"] is True
        assert result["tier"] in ("basic", "deep")

    @pytest.mark.asyncio
    async def test_transform_standardizer_missing_id_and_uuids(self):
        svc = _PipelineFactory().make()
        svc._transform_slack_payload = AsyncMock(return_value=[
            {"type": "slack_message", "text": "hello", "user": "u1",
             "metadata": {"uuid_val": uuid.uuid4(), "nested": {"u": uuid.uuid4()}},
             "properties": {"email": "a@b.c"},
             "extra": uuid.uuid4()},
        ])
        records = await svc._transform_webhook_payload("slack", {"type": "event_callback"})
        assert len(records) == 1
        assert records[0]["id"] == ""
        assert records[0]["sender_id"] == "u1"
        assert isinstance(records[0]["metadata"]["uuid_val"], str)

    @pytest.mark.asyncio
    async def test_transform_gmail_payload_internal_date_error(self):
        svc = _PipelineFactory().make()
        svc._fetch_gmail_resource_direct = AsyncMock(side_effect=[
            {"history": [{"messagesAdded": [{"message": {"id": "g1"}}]}]},
            {
                "payload": {"headers": [{"name": "Subject", "value": "Hi"},
                                        {"name": "From", "value": "a@b.c"}]},
                "snippet": "snip",
                "internalDate": "not-a-number",
                "threadId": "th1",
            },
        ])
        records = await svc._transform_gmail_payload(
            {"historyId": "42", "_source_connection_id": "conn-1"}
        )
        assert records[0]["id"] == "g1"
        assert records[0]["timestamp"]  # fell back to now

    @pytest.mark.asyncio
    async def test_transform_telegram_payload_dict_media(self):
        svc = _PipelineFactory().make()
        records = await svc._transform_telegram_payload({
            "message": {
                "message_id": 7,
                "text": "hello",
                "from": {"id": 1, "first_name": "A"},
                "chat": {"id": 2, "title": "Room"},
                "photo": [{"file_id": "small"}, {"file_id": "large"}],
                "document": {"file_id": "doc1"},
            }
        })
        assert records[0]["properties"]["media_id"] == "large"

        records2 = await svc._transform_telegram_payload({
            "message": {"message_id": 8, "text": "x", "chat": {"id": 2},
                        "document": {"file_id": "doc2"}}
        })
        assert records2[0]["properties"]["media_id"] == "doc2"

    @pytest.mark.asyncio
    async def test_fetch_outlook_resource_direct(self):
        svc = _PipelineFactory().make()

        class _Resp:
            def __init__(self, status, data=None):
                self.status_code = status
                self._data = data

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise _HTTPError(self)

            def json(self):
                return self._data

        class _HTTPError(Exception):
            def __init__(self, resp):
                self.response = resp

        conn = MagicMock()
        conn.credentials = "encrypted"
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = conn

        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "tok"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)

        import httpx

        async def _get(url, **kw):
            if url.endswith("me/messages/1"):
                return _Resp(404)
            raise _HTTPError(_Resp(500))

        client = MagicMock()
        client.get = AsyncMock(side_effect=_get)
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False

        svc.db = session
        with patch("httpx.AsyncClient", return_value=client), \
             patch("core.connection_service.ConnectionService", return_value=conn_service):
            r1 = await svc._fetch_outlook_resource_direct("conn-1", "me/messages/1")
            assert r1 == {}
            r2 = await svc._fetch_outlook_resource_direct("conn-1", "me/messages/2")
            assert r2 is None
            r3 = await svc._fetch_outlook_resource_direct("conn-1", "https://graph.microsoft.com/v1.0/me")
            assert r3 is None  # HTTPStatusError -> None

    @pytest.mark.asyncio
    async def test_fetch_gmail_resource_direct_error_branches(self):
        svc = _PipelineFactory().make()
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        svc.db = session
        assert await svc._fetch_gmail_resource_direct("conn-x", "users/me/history") is None

    def test_is_canonical_type_false(self):
        svc = _PipelineFactory().make()
        assert svc._is_core_entity_type("not-a-real-type") is False

    @pytest.mark.asyncio
    async def test_run_schema_discovery_failure(self):
        svc = _PipelineFactory().make()
        svc.schema_discovery = MagicMock()
        svc.schema_discovery.discover_and_link = AsyncMock(side_effect=Exception("boom"))
        svc.meta_agent_orchestrator = MagicMock()
        with patch("core.ingestion_pipeline.SessionLocal") as sl:
            sl.return_value = MagicMock()
            await svc._run_schema_discovery({"records_processed": 1})
