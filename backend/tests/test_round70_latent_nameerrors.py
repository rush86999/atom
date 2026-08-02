"""
Round 70 — Latent NameError sweep across production code (Red-Green-Refactor).

A static sweep with ``ruff --select F821`` over ``api/``, ``core/``, ``tools/``,
``services/`` and ``main_api_app.py`` surfaced ~26 undefined-name sites in
shipped (non-test) code. Every one is a latent ``NameError``: some fire at
import time, some silently degrade a feature because the exception is swallowed
by a broad ``except``, and one breaks a *fail-closed* security path.

Highest-impact sites covered by targeted tests below:

  A. tools/office_tool.py — ``List`` never imported but used in three runtime
     (non-string) annotations → ``import tools.office_tool`` raises NameError,
     so the ENTIRE office toolset is unreachable. Same class as Round 52.
  B. core/sandbox_tripwire.py — the Bug-#12 "fail CLOSED under enforcement"
     branch returns ``decision=DENIED``; only ``ALLOWED``/``BLOCKED`` are
     imported, so the fail-closed path raises NameError instead of blocking.
  C. core/llm/registry/sync_job.py — an incomplete refactor left ``tenant_id``
     out of the ``should_sync`` / ``_update_sync_timestamp`` signatures while
     their bodies (and ``run()``'s call sites) still used it:
     ``should_sync(tenant_id, db)`` bound a *string* to ``db`` (swallowed →
     always "sync needed") and ``_update_sync_timestamp(tenant_id)`` raised
     TypeError, so every sync run reported failure after doing the work.
  D. core/llm/registry/queries.py — same incomplete refactor across 10 query
     helpers: ``tenant_id`` filtered in the body, absent from the signature.
     Per docs/architecture/TENANT_ID_STRATEGY.md, Atom keeps tenant_id on all
     models and query filters (single-tenant Personal Edition, SaaS schema
     parity), so the fix restores the parameter — it does NOT remove filters.
     It also references ``last_sync_timestamp``, a column LLMModel never had
     (the real column is ``last_refreshed_at``), so sync tracking silently no-oped.
  E. core/enterprise_security.py — ``security_middleware`` never awaits
     ``call_next``; its body ends on a bare ``response`` expression.
  F. core/token_storage.py — ``timedelta`` missing → ``is_token_expired``
     always returns True (swallowed by ``except Exception``), so every token
     looks expired.
  G. core/condition_checkers.py — dispatch compares against
     ``ConditionMonitorType.<X>.value``, but ``ConditionMonitorType`` is an
     unimported SQLAlchemy *table* model, not an enum → every check raises.
  H. core/entity_schema_suggestion_service.py — ``_instance_lock`` never
     defined → the singleton accessor raises on first call.
  I. core/lancedb_handler.py — ``create_memory_schema`` uses undefined
     ``Vector``; ``np`` used without import in the zero-vector fallback.

The remaining sites (missing ``os``/``time``/``json``/``httpx``/``defaultdict``
/``logger`` imports, leftover ``tenant_id``/``server_id``/``budget_check``/
``max_intervention_rate``/``ENTITY_REGISTRY``/``CORE_ENTITY_SCHEMAS``
references, and the ``str(e)`` NameError in the degraded-mode fallback app) are
covered by the module-attribute checks and the whole-tree F821 sweep at the end,
which also guards against regressions.
"""

import importlib
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# A. tools/office_tool.py must be importable at all
# ---------------------------------------------------------------------------
class TestOfficeToolImportable:
    def test_office_tool_module_imports(self):
        """Missing `List` import makes the whole office toolset unreachable."""
        module = importlib.import_module("tools.office_tool")

        assert callable(module.add_excel_pivot_table)

    def test_office_tool_annotations_resolve(self):
        """Runtime annotations must resolve (no string/future-annotations here)."""
        import typing

        module = importlib.import_module("tools.office_tool")
        hints = typing.get_type_hints(module.add_excel_pivot_table)

        assert hints["rows"] == typing.List[str]


# ---------------------------------------------------------------------------
# B. sandbox tripwire fail-closed path
# ---------------------------------------------------------------------------
class TestTripwireFailsClosed:
    def test_internal_error_under_enforcement_returns_blocked(self):
        from core import sandbox_tripwire
        from core.sandbox_policy import BLOCKED, VT_TRIPWIRE

        with patch.object(
            sandbox_tripwire.sandbox_config,
            "is_sandbox_force_enforce_enabled",
            return_value=True,
        ), patch.object(
            sandbox_tripwire, "match", side_effect=RuntimeError("boom")
        ):
            decision = sandbox_tripwire.check(
                tool_name="browser_click", args={"selector": "#x"}
            )

        assert decision.decision == BLOCKED
        assert decision.enforced is True
        assert decision.violation_type == VT_TRIPWIRE

    def test_internal_error_in_shadow_mode_still_fails_open(self):
        from core import sandbox_tripwire
        from core.sandbox_policy import ALLOWED

        with patch.object(
            sandbox_tripwire.sandbox_config,
            "is_sandbox_force_enforce_enabled",
            return_value=False,
        ), patch.object(
            sandbox_tripwire, "match", side_effect=RuntimeError("boom")
        ):
            decision = sandbox_tripwire.check(
                tool_name="browser_click", args={"selector": "#x"}
            )

        assert decision.decision == ALLOWED


# ---------------------------------------------------------------------------
# C. + D. LLM model registry: incomplete single-tenant refactor
# ---------------------------------------------------------------------------
class TestModelRegistryTenantContract:
    """registry helpers must take tenant_id again (TENANT_ID_STRATEGY.md:
    keep tenant_id on models + filters for SaaS parity) — the NameError was
    the signature losing the param while the body kept filtering."""

    def test_should_sync_accepts_tenant_id(self):
        from core.llm.registry.sync_job import ModelSyncJob

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        assert ModelSyncJob.should_sync("tenant-1", db, interval_hours=24) is True
        assert db.query.called, "tenant_id must not shadow the db argument"

    def test_update_sync_timestamp_accepts_tenant_id(self):
        from core.llm.registry.sync_job import ModelSyncJob

        job = ModelSyncJob.__new__(ModelSyncJob)
        job.db = MagicMock()
        job.logger = MagicMock()
        job.db.query.return_value.filter.return_value.update.return_value = 3

        job._update_sync_timestamp("tenant-1")

        assert job.db.commit.called

    @pytest.mark.parametrize(
        "func_name,args",
        [
            ("query_by_capability", ("vision",)),
            ("query_by_all_capabilities", (["vision", "tools"],)),
            ("query_by_any_capability", (["vision", "tools"],)),
            ("get_models_by_quality_range", ()),
            ("get_frontier_models", ()),
            ("get_auto_include_models", ()),
        ],
    )
    def test_query_helpers_accept_tenant_id(self, func_name, args):
        from core.llm.registry import queries

        func = getattr(queries, func_name)
        db = MagicMock()

        # Must not raise NameError/TypeError building the query.
        func(db, "tenant-1", *args)

    def test_query_by_metadata_accepts_tenant_id(self):
        from core.llm.registry import queries

        queries.query_by_metadata(MagicMock(), "tenant-1", "provider", "openai")

    @pytest.mark.asyncio
    async def test_sync_run_reports_success(self):
        """run() passed tenant_id into should_sync/_update_sync_timestamp whose
        signatures had lost it: should_sync bound the string to `db` and
        _update_sync_timestamp raised TypeError, so a successful fetch was
        always reported as a failed sync."""
        from core.llm.registry.sync_job import ModelSyncJob

        job = ModelSyncJob.__new__(ModelSyncJob)
        job.db = MagicMock()
        job.logger = MagicMock()
        job.registry_service = MagicMock()

        async def fetch_and_store(tenant_id):
            return {"total": 4, "created": 3, "updated": 1, "failed": 0}

        job.registry_service.fetch_and_store = fetch_and_store
        job.db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        job.db.query.return_value.filter.return_value.update.return_value = 4

        result = await job.run("tenant-1")

        assert result["error"] is None
        assert result["success"] is True
        assert result["created"] == 3


# ---------------------------------------------------------------------------
# E. enterprise security middleware must forward the request
# ---------------------------------------------------------------------------
class TestEnterpriseSecurityMiddleware:
    @pytest.mark.asyncio
    async def test_middleware_returns_downstream_response(self):
        from core import enterprise_security

        sentinel = MagicMock(status_code=200)
        called = {}

        async def call_next(request):
            called["hit"] = True
            return sentinel

        request = MagicMock()
        request.client.host = "10.0.0.1"
        request.url.path = "/api/agents"
        request.method = "GET"

        with patch.object(
            enterprise_security.enterprise_security,
            "check_rate_limit",
            return_value=True,
        ):
            response = await enterprise_security.security_middleware(request, call_next)

        assert called.get("hit") is True, "middleware never called call_next"
        assert response is sentinel


# ---------------------------------------------------------------------------
# F. token_storage expiry math
# ---------------------------------------------------------------------------
class TestTokenStorageExpiry:
    def test_future_token_is_not_reported_expired(self, tmp_path):
        from core.token_storage import TokenStorage

        storage = TokenStorage(storage_file=str(tmp_path / "tokens.json"))
        storage._tokens = {
            "google": {
                "access_token": "abc",
                "expires_at": (datetime.now() + timedelta(hours=2)).isoformat(),
            }
        }

        assert storage.is_token_expired("google") is False

    def test_past_token_is_reported_expired(self, tmp_path):
        from core.token_storage import TokenStorage

        storage = TokenStorage(storage_file=str(tmp_path / "tokens.json"))
        storage._tokens = {
            "google": {
                "access_token": "abc",
                "expires_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            }
        }

        assert storage.is_token_expired("google") is True


# ---------------------------------------------------------------------------
# G. condition checker dispatch
# ---------------------------------------------------------------------------
class TestConditionCheckerDispatch:
    @pytest.mark.parametrize(
        "condition_type,handler",
        [
            ("inbox_volume", "_check_inbox_volume"),
            ("task_backlog", "_check_task_backlog"),
            ("api_metrics", "_check_api_metrics"),
            ("database_query", "_check_database_query"),
            ("composite", "_check_composite"),
        ],
    )
    def test_dispatch_routes_by_string_type(self, condition_type, handler):
        from core.condition_checkers import ConditionCheckers

        checkers = ConditionCheckers(MagicMock())
        monitor = MagicMock()
        monitor.condition_type = condition_type

        with patch.object(
            ConditionCheckers, handler, return_value={"triggered": True}
        ) as mocked:
            result = checkers.check_condition(monitor)

        assert mocked.called
        assert result == {"triggered": True}

    def test_unknown_type_returns_untriggered(self):
        from core.condition_checkers import ConditionCheckers

        checkers = ConditionCheckers(MagicMock())
        monitor = MagicMock()
        monitor.condition_type = "not_a_real_type"

        result = checkers.check_condition(monitor)

        assert result["triggered"] is False


# ---------------------------------------------------------------------------
# H. entity schema suggestion singleton
# ---------------------------------------------------------------------------
class TestEntitySchemaSuggestionSingleton:
    def test_accessor_is_thread_safe_and_returns_singleton(self):
        from core import entity_schema_suggestion_service as mod

        assert hasattr(mod, "_instance_lock"), "double-checked lock is undefined"

        with patch.object(mod, "EntitySchemaSuggestionService", MagicMock()):
            mod._instance = None
            first = mod.get_entity_schema_suggestion_service()
            second = mod.get_entity_schema_suggestion_service()

        mod._instance = None
        assert first is second


# ---------------------------------------------------------------------------
# I. lancedb helpers
# ---------------------------------------------------------------------------
class TestLanceDBHelpers:
    def test_create_memory_schema_has_vector_field(self):
        from core.lancedb_handler import create_memory_schema

        schema = create_memory_schema(vector_size=384)

        assert "vector" in schema
        assert schema["vector"] is not None


# ---------------------------------------------------------------------------
# Module-level names that were used but never imported.
# ---------------------------------------------------------------------------
MISSING_MODULE_IMPORTS = [
    ("core.token_storage", "timedelta"),
    ("core.token_refresher", "httpx"),
    ("core.llm.byok_handler", "time"),
    ("core.llm_oauth_handler", "os"),
    ("core.workflow_engine", "os"),
    ("core.graphrag.dynamic_graph", "defaultdict"),
    ("core.integration_enhancement_endpoints", "logger"),
    ("core.fleet_orchestration.fleet_scaler_service", "os"),
    ("services.agent_service", "json"),
]


@pytest.mark.parametrize("module_path,name", MISSING_MODULE_IMPORTS)
def test_module_defines_used_global(module_path, name):
    module = importlib.import_module(module_path)

    assert hasattr(module, name), f"{module_path} uses `{name}` but never imports it"


# ---------------------------------------------------------------------------
# Leftover references from incomplete refactors (must be gone from source).
# ---------------------------------------------------------------------------
LEFTOVER_REFERENCES = [
    ("core/fleet_orchestration/fleet_scaler_service.py", "budget_check["),
    ("core/graphrag_engine.py", "ENTITY_REGISTRY"),
    ("core/generic_agent.py", "{server_id}"),
    ("core/memory/pomdp_memory_framework.py", "max_intervention_rate*100"),
    ("core/marketing_skills_service.py", "return summary"),
]


@pytest.mark.parametrize("rel_path,needle", LEFTOVER_REFERENCES)
def test_no_leftover_undefined_reference(rel_path, needle):
    source = (BACKEND_DIR / rel_path).read_text()

    assert needle not in source, f"{rel_path} still references undefined `{needle}`"


def test_ingestion_pipeline_imports_core_entity_schemas():
    from core import ingestion_pipeline

    assert hasattr(ingestion_pipeline, "CORE_ENTITY_SCHEMAS")


def test_degraded_mode_fallback_does_not_reference_dead_exception_var():
    """`except Exception as e:` unbinds `e`; the closure below leaked+crashed."""
    source = (BACKEND_DIR / "main_api_app.py").read_text()
    tail = source.split("Failed to create FastAPI app", 1)[1]

    assert '"details": str(e)' not in tail


# ---------------------------------------------------------------------------
# Whole-tree regression net.
# ---------------------------------------------------------------------------
PRODUCTION_TARGETS = [
    "api",
    "core",
    "tools",
    "services",
    "cli",
    "main_api_app.py",
]


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_no_undefined_names_in_production_code():
    """Regression net: zero F821 (undefined name) in shipped backend code."""
    result = subprocess.run(
        ["ruff", "check", *PRODUCTION_TARGETS, "--select", "F821",
         "--no-cache", "--output-format", "concise"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    hits = [line for line in result.stdout.splitlines() if ": F821" in line]

    assert not hits, "undefined names in production code:\n" + "\n".join(hits)
