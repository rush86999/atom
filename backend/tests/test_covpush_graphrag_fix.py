"""
Coverage-push + bug-hunt tests for core.graphrag_engine (R88 wave).

Closes the last uncovered lines (baseline 98%, misses at 34-35, 192-196,
205-206, 454-455):

1. 34-35    — import-time automation availability: the try block is only
              reachable when core.atom_meta_agent is already importable;
              first import in this process hits the circular-import ImportError
              and silently degrades to AUTOMATION_AVAILABLE=False. Re-executing
              the module body with the dependency pre-imported must succeed.
2. 192-196  — canonical_search with property-only search fields (User.name is
              a Python property, not a column): must skip property filters and
              fall back to the singular search_field; if that is also a
              property, return [] instead of crashing.
3. 194      — canonical_search fallback: singular search_field that IS a real
              column must produce a working filter (works when the plural
              search_fields list is all-property).
4. 205-206  — canonical_search tenant_id-only isolation branch (Workspace has
              tenant_id but no workspace_id).
5. 454-455  — pattern extraction must degrade to empty on regex failure
              (never raise).

The wave's duplicate-method report does NOT apply to HEAD: only one definition
of _resolve_canonical_entity / _sanitize_canonical_data /
_create_canonical_entity_if_missing exists (verified by grep). The
canonical_search ValueError-on-long-query and the canonical-user auto-create
failure are *intended* behavior enshrined in test_covpush_graphrag_engine.py
(test_search_too_long_raises, test_create_canonical_user_fails_gracefully) —
see report.
"""

import uuid
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.graphrag_engine import GraphRAGEngine
from core.models import User, Workspace


@pytest.fixture(scope="module")
def db_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.models_registration import Base

    Base.metadata.create_all(eng, tables=[User.__table__, Workspace.__table__])
    yield eng
    eng.dispose()


@pytest.fixture
def session(db_engine):
    Session = sessionmaker(bind=db_engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def engine(session):
    """Engine with a stubbed LLM service (no network)."""
    eng = GraphRAGEngine(workspace_id="ws-1", tenant_id="t-1", db=session)
    eng.llm_service = None
    return eng


# ============================ 1. automation import path ============================


class TestAutomationImportPath:
    def test_automation_available_flag_not_silently_disabled(self):
        """AUTOMATION_AVAILABLE must be True when the orchestrator module is
        importable. It was permanently False: the module-level import asked
        for a name ('orchestrator') that advanced_workflow_orchestrator does
        not export (the real factory is get_orchestrator), the ImportError was
        swallowed, and graph_entity_upsert events never fired."""
        import core.graphrag_engine as ge

        assert ge.AUTOMATION_AVAILABLE is True

    def test_automation_fallback_when_orchestrator_unimportable(self):
        """If advanced_workflow_orchestrator cannot be imported at all, the
        fail-safe AUTOMATION_AVAILABLE=False must engage without raising."""
        import sys
        import importlib.util
        import core.graphrag_engine as ge

        spec = importlib.util.spec_from_file_location(
            "graphrag_engine_fallback", ge.__file__
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": None}):
            spec.loader.exec_module(mod)
        assert mod.AUTOMATION_AVAILABLE is False

    def test_lazy_orchestrator_resolution_caches(self):
        """_get_workflow_orchestrator() must resolve the singleton lazily and
        cache it in the module global (so callers patching
        core.graphrag_engine.orchestrator keep working)."""
        import core.graphrag_engine as ge

        orch = Mock()
        with patch.object(ge, "orchestrator", None), patch(
            "core.graphrag_engine.get_orchestrator", return_value=orch
        ):
            first = ge._get_workflow_orchestrator()
            second = ge._get_workflow_orchestrator()
            assert first is orch
            assert second is orch
            assert ge.orchestrator is orch


# ==================== 2/3. canonical_search property fallback ====================


class TestCanonicalSearchPropertyFallback:
    def _db_ctx(self, session):
        @contextmanager
        def ctx():
            yield session

        return patch("core.graphrag_engine.get_db_session", ctx)

    def test_all_property_search_fields_returns_empty(self, engine, session):
        """User.name is a @property (not a column) — with search_fields=["name"]
        every candidate filter is skipped and canonical_search returns []."""
        registry = {
            "model": User,
            "search_fields": ["name"],
            "search_field": "name",
            "display_field": "email",
        }
        with self._db_ctx(session), patch.object(
            engine, "_get_registry_entry", return_value=registry
        ):
            assert engine.canonical_search(entity_type="custom", query="z") == []

    def test_fallback_to_real_search_field_column(self, engine, session):
        """When the plural search_fields list is all-property, the singular
        search_field (a real column) must still produce a working query."""
        user = User(
            id=str(uuid.uuid4()), email="prop@x.com", hashed_password="p",
            first_name="P", last_name="X", tenant_id="t-1",
            workspace_id="ws-1", role="member", status="active",
        )
        session.add(user)
        session.commit()
        registry = {
            "model": User,
            "search_fields": ["name"],
            "search_field": "email",
            "display_field": "email",
        }
        with self._db_ctx(session), patch.object(
            engine, "_get_registry_entry", return_value=registry
        ):
            results = engine.canonical_search(
                entity_type="custom", query="prop"
            )
        assert results == [{"id": user.id, "name": "prop@x.com"}]


# ============================ 4. tenant_id-only isolation ============================


class TestCanonicalSearchTenantIsolation:
    def _db_ctx(self, session):
        @contextmanager
        def ctx():
            yield session

        return patch("core.graphrag_engine.get_db_session", ctx)

    def test_workspace_model_uses_tenant_id_filter(self, engine, session):
        """Workspace has tenant_id but no workspace_id — canonical_search must
        fall through to the tenant_id branch and scope results to the tenant."""
        own = Workspace(id="w-own", tenant_id="t-1", name="Tenant Co")
        other = Workspace(id="w-other", tenant_id="t-other", name="Tenant Co")
        session.add_all([own, other])
        session.commit()
        with self._db_ctx(session):
            results = engine.canonical_search(
                workspace_id="ws-1", tenant_id="t-1",
                entity_type="workspace", query="tenant",
            )
        assert results == [{"id": "w-own", "name": "Tenant Co"}]


# ============================ 5. pattern extraction failure ============================


class TestPatternExtractionFailure:
    def test_regex_failure_returns_empty(self, engine):
        """A re engine failure must not propagate — degrade to empty lists."""
        with patch(
            "core.graphrag_engine.re.finditer", side_effect=RuntimeError("boom")
        ):
            entities, relationships = engine._pattern_extract_entities_and_relationships(
                "any text", "d1", "src"
            )
        assert entities == []
        assert relationships == []
