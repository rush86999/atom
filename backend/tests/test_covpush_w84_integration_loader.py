# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/integration_loader (standalone; importlib and the
ingestion pipeline fully mocked, real thread-pool timeout exercised with a
short timeout).

- IntegrationLoader ctor: env default timeout + explicit override.
- _validate_module_path: valid dotted paths, invalid paths (uppercase, slash,
  leading digit, empty), blocked prefixes (os./sys./subprocess./eval).
- _load_module_with_timeout: success, module import error (re-raised).
- load_integration: condition false, success (status loaded), timeout
  (status timeout), ImportError (status failed), AttributeError (no entry),
  generic Exception (status error).
- get_loaded_integrations filtering.
- auto_ingest: async dict/list/falsy/ingest-raise; sync dict/list/falsy;
  decorator wrapper selection.
"""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

import core.integration_loader as mod
from core.integration_loader import IntegrationLoader, auto_ingest


# ============================================================================
# ctor
# ============================================================================

class TestInit:
    def test_default_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("INTEGRATION_LOAD_TIMEOUT", "7")
        assert IntegrationLoader().timeout_seconds == 7

    def test_env_fallback_five(self, monkeypatch):
        monkeypatch.delenv("INTEGRATION_LOAD_TIMEOUT", raising=False)
        assert IntegrationLoader().timeout_seconds == 5

    def test_explicit_timeout_wins(self, monkeypatch):
        monkeypatch.setenv("INTEGRATION_LOAD_TIMEOUT", "7")
        assert IntegrationLoader(timeout=3).timeout_seconds == 3

    def test_starts_empty(self):
        assert IntegrationLoader().integrations == []


# ============================================================================
# _validate_module_path
# ============================================================================

class TestValidateModulePath:
    def test_valid(self):
        loader = IntegrationLoader()
        assert loader._validate_module_path("integrations.asana_routes") is True
        assert loader._validate_module_path("a.b.c1") is True

    def test_invalid_patterns(self):
        loader = IntegrationLoader()
        for bad in ["Integrations.X", "integrations/x", "integrations..x",
                    "1integrations", "", "a.b-c"]:
            with pytest.raises(ValueError, match="Invalid module path"):
                loader._validate_module_path(bad)

    def test_blocked_prefixes(self):
        loader = IntegrationLoader()
        for bad in ["os.system", "sys.modules", "subprocess.run", "eval", "evalx.y"]:
            with pytest.raises(ValueError, match="Restricted module"):
                loader._validate_module_path(bad)


# ============================================================================
# _load_module_with_timeout
# ============================================================================

class TestLoadModuleWithTimeout:
    def test_returns_router(self):
        loader = IntegrationLoader()
        fake_router = object()
        module = MagicMock()
        module.router = fake_router
        with patch("core.integration_loader.importlib.import_module", return_value=module):
            assert loader._load_module_with_timeout("integrations.x", "router") is fake_router

    def test_raises_on_missing_module(self):
        loader = IntegrationLoader()
        with patch("core.integration_loader.importlib.import_module",
                   side_effect=ImportError("no module")):
            with pytest.raises(ImportError):
                loader._load_module_with_timeout("integrations.missing", "router")

    def test_raises_on_missing_attr(self):
        loader = IntegrationLoader()
        module = MagicMock()
        del module.router
        with patch("core.integration_loader.importlib.import_module", return_value=module):
            with pytest.raises(AttributeError):
                loader._load_module_with_timeout("integrations.x", "router")


# ============================================================================
# load_integration
# ============================================================================

class TestLoadIntegration:
    def test_condition_false_returns_none(self):
        loader = IntegrationLoader()
        assert loader.load_integration("integrations.x", condition=False) is None
        assert loader.integrations == []

    def test_success(self):
        loader = IntegrationLoader()
        fake_router = object()
        module = MagicMock()
        module.router = fake_router
        with patch("core.integration_loader.importlib.import_module", return_value=module):
            result = loader.load_integration("integrations.asana_routes")
        assert result is fake_router
        assert loader.integrations[-1] == {
            "name": "integrations.asana_routes",
            "router": fake_router,
            "status": "loaded",
        }
        assert len(loader.get_loaded_integrations()) == 1

    def test_timeout(self):
        loader = IntegrationLoader(timeout=0.01)
        with patch.object(loader, "_load_module_with_timeout", side_effect=lambda *a: time.sleep(0.2)):
            result = loader.load_integration("integrations.slow")
        assert result is None
        entry = loader.integrations[-1]
        assert entry["status"] == "timeout"
        assert entry["router"] is None
        assert "Timeout after" in entry["error"]

    def test_import_error(self):
        loader = IntegrationLoader()
        with patch("core.integration_loader.importlib.import_module",
                   side_effect=ImportError("no dist")):
            result = loader.load_integration("integrations.missing")
        assert result is None
        entry = loader.integrations[-1]
        assert entry["status"] == "failed"
        assert entry["error"] == "no dist"

    def test_attribute_error(self):
        loader = IntegrationLoader()
        module = MagicMock()
        del module.router
        with patch("core.integration_loader.importlib.import_module", return_value=module):
            result = loader.load_integration("integrations.x")
        assert result is None
        assert len(loader.integrations) == 0

    def test_generic_error(self):
        loader = IntegrationLoader()
        with patch("core.integration_loader.importlib.import_module",
                   side_effect=RuntimeError("boom")):
            result = loader.load_integration("integrations.x")
        assert result is None
        entry = loader.integrations[-1]
        assert entry["status"] == "error"
        assert entry["error"] == "boom"

    def test_invalid_module_path_is_caught_as_error(self):
        loader = IntegrationLoader()
        with patch("core.integration_loader.importlib.import_module") as import_mock:
            result = loader.load_integration("../../etc/passwd")
        assert result is None
        entry = loader.integrations[-1]
        assert entry["status"] == "error"
        assert "Invalid module path" in entry["error"]
        import_mock.assert_not_called()

    def test_get_loaded_integrations_filters(self):
        loader = IntegrationLoader()
        loader.integrations = [
            {"name": "a", "router": object(), "status": "loaded"},
            {"name": "b", "router": None, "status": "failed"},
            {"name": "c", "router": None, "status": "timeout"},
            {"name": "d", "router": None, "status": "error"},
        ]
        loaded = loader.get_loaded_integrations()
        assert [i["name"] for i in loaded] == ["a"]


# ============================================================================
# auto_ingest decorator
# ============================================================================

class TestAutoIngest:
    def test_async_dict(self):
        pipeline = MagicMock()

        @auto_ingest("apps", "records")
        async def handler():
            return {"id": 1}

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", pipeline.ingest_record):
            result = asyncio.run(handler())
        assert result == {"id": 1}
        pipeline.ingest_record.assert_called_once_with("apps", "records", {"id": 1})

    def test_async_list(self):
        pipeline = MagicMock()

        @auto_ingest("apps", "records")
        async def handler():
            return [{"id": 1}, {"id": 2}]

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", pipeline.ingest_record):
            result = asyncio.run(handler())
        assert result == [{"id": 1}, {"id": 2}]
        assert pipeline.ingest_record.call_count == 2

    def test_async_falsy_no_ingest(self):
        pipeline = MagicMock()

        @auto_ingest("apps", "records")
        async def handler():
            return None

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", pipeline.ingest_record):
            result = asyncio.run(handler())
        assert result is None
        pipeline.ingest_record.assert_not_called()

    def test_async_ingest_raise_is_swallowed(self):
        def boom(app_type, record_type, item):
            raise RuntimeError("pipe down")

        @auto_ingest("apps", "records")
        async def handler():
            return {"id": 1}

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", boom):
            result = asyncio.run(handler())
        assert result == {"id": 1}

    def test_sync_dict(self):
        pipeline = MagicMock()

        @auto_ingest("apps", "records")
        def handler():
            return {"id": 1}

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", pipeline.ingest_record):
            result = handler()
        assert result == {"id": 1}
        pipeline.ingest_record.assert_called_once_with("apps", "records", {"id": 1})

    def test_sync_list(self):
        pipeline = MagicMock()

        @auto_ingest("apps", "records")
        def handler():
            return [{"id": 1}]

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", pipeline.ingest_record):
            result = handler()
        assert result == [{"id": 1}]
        pipeline.ingest_record.assert_called_once()

    def test_sync_falsy_no_ingest(self):
        pipeline = MagicMock()

        @auto_ingest("apps", "records")
        def handler():
            return []

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", pipeline.ingest_record):
            result = handler()
        assert result == []
        pipeline.ingest_record.assert_not_called()

    def test_sync_ingest_raise_is_swallowed(self):
        def boom(app_type, record_type, item):
            raise ValueError("bad")

        @auto_ingest("apps", "records")
        def handler():
            return {"id": 1}

        with patch.object(mod.atom_ingestion_pipeline, "ingest_record", boom):
            result = handler()
        assert result == {"id": 1}

    def test_keeps_metadata(self):
        @auto_ingest("apps", "records")
        def handler():
            """docstring"""
            return {"id": 1}

        assert handler.__name__ == "handler"
        assert handler.__doc__ == "docstring"
        assert asyncio.iscoroutinefunction(handler) is False

    def test_async_wrapper_for_coroutine(self):
        @auto_ingest("apps", "records")
        async def handler():
            return {"id": 1}

        assert asyncio.iscoroutinefunction(handler) is True
