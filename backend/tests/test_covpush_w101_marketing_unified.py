# -*- coding: utf-8 -*-
"""Coverage wave 101 — integrations/marketing_unified_service
(MarketingUnifiedService).

Standalone, fully mocked (atom_ingestion_pipeline patched), zero network, zero
LLM spend. Follows wave-95/97 conventions.

Covers: __init__, MarketingPlatform enum values, get_capabilities,
health_check, execute_operation (google_ads / tiktok_ads, unknown operation,
tenant mismatch, ImportError path, exception -> generic envelope),
get_campaign_performance (metrics shape + ingest_record call).

Bugs fixed (TDD RED -> GREEN):
- execute_operation leaked str(e); now generic envelope. This also covers the
  ImportError path where `atom_ingestion_pipeline` is undefined at module
  level and get_campaign_performance raises NameError.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.marketing_unified_service import (
    MarketingUnifiedService,
    MarketingPlatform,
)


def _svc(config=None):
    return MarketingUnifiedService(tenant_id="t1", config=config or {})


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"api_key": "k1"})
        assert svc.tenant_id == "t1"
        assert svc.config == {"api_key": "k1"}

    def test_explicit_none_config(self):
        svc = MarketingUnifiedService(tenant_id="t1", config=None)
        assert svc.config == {}


class TestImportFallback:
    def test_import_error_branch(self, monkeypatch):
        """Cover the module-level `except ImportError` fallback (lines 15-16)
        by executing the module source in an isolated namespace with the
        pipeline import blocked — the live module is never reloaded, so class
        identity (MarketingPlatform etc.) stays stable for other tests."""
        import builtins
        import pathlib
        import integrations.marketing_unified_service as mod

        real_import = builtins.__import__

        def blocked(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "integrations.atom_ingestion_pipeline":
                raise ImportError("blocked for coverage")
            return real_import(name, globals, locals, fromlist, level)

        src = pathlib.Path(mod.__file__).read_text()
        ns = {"__name__": mod.__name__, "__file__": mod.__file__}
        monkeypatch.setattr(builtins, "__import__", blocked)
        exec(compile(src, mod.__file__, "exec"), ns)
        monkeypatch.undo()
        assert "atom_ingestion_pipeline" not in ns
        assert "MarketingUnifiedService" in ns


class TestPlatformEnum:
    def test_values(self):
        assert MarketingPlatform.GOOGLE_ADS.value == "google_ads"
        assert MarketingPlatform.TIKTOK_ADS.value == "tiktok_ads"


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        assert caps["operations"] == [
            {"id": "get_campaign_performance", "name": "Get Campaign Performance",
             "parameters": {"platform": "string"}}
        ]
        assert caps["required_params"] == []
        assert caps["supports_webhooks"] is False


class TestHealthCheck:
    def test_healthy(self):
        out = _svc().health_check()
        assert out["ok"] is True
        assert out["status"] == "healthy"
        assert out["service"] == "marketing_unified"
        assert "timestamp" in out


class TestExecuteOperation:
    async def test_get_campaign_performance_google(self):
        svc = _svc()
        svc.get_campaign_performance = AsyncMock(return_value={"platform": "google_ads"})
        out = await svc.execute_operation("get_campaign_performance", {"platform": "google_ads"})
        assert out["success"] is True
        assert out["result"] == {"platform": "google_ads"}
        svc.get_campaign_performance.assert_awaited_once_with(MarketingPlatform.GOOGLE_ADS)

    async def test_get_campaign_performance_default_platform(self):
        svc = _svc()
        svc.get_campaign_performance = AsyncMock(return_value={})
        await svc.execute_operation("get_campaign_performance", {})
        svc.get_campaign_performance.assert_awaited_once_with(MarketingPlatform.GOOGLE_ADS)

    async def test_tiktok_platform(self):
        svc = _svc()
        svc.get_campaign_performance = AsyncMock(return_value={})
        await svc.execute_operation("get_campaign_performance", {"platform": "tiktok_ads"})
        svc.get_campaign_performance.assert_awaited_once_with(MarketingPlatform.TIKTOK_ADS)

    async def test_unknown_operation(self):
        out = await _svc().execute_operation("nope", {})
        assert out["success"] is False
        assert out["error"] == "Unknown operation: nope"

    async def test_tenant_mismatch_fails_closed(self):
        svc = _svc()
        svc.get_campaign_performance = AsyncMock(return_value={})
        out = await svc.execute_operation("get_campaign_performance", {},
                                          context={"tenant_id": "other"})
        assert out["success"] is False
        assert out["error"] == "Tenant ID mismatch"
        svc.get_campaign_performance.assert_not_awaited()

    async def test_tenant_match_proceeds(self):
        svc = _svc()
        svc.get_campaign_performance = AsyncMock(return_value={})
        out = await svc.execute_operation("get_campaign_performance", {},
                                          context={"tenant_id": "t1"})
        assert out["success"] is True

    async def test_invalid_platform_value_generic(self):
        """RED: exception leaked str(e) (ValueError from the enum); must be
        generic."""
        out = await _svc().execute_operation("get_campaign_performance",
                                             {"platform": "bogus"})
        assert out["success"] is False
        assert "bogus" not in out["error"]
        assert out["error"] == "Marketing Unified operation failed"

    async def test_exception_generic_envelope(self):
        svc = _svc()
        svc.get_campaign_performance = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_campaign_performance", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Marketing Unified operation failed"


class TestGetCampaignPerformance:
    async def test_returns_metrics_and_ingests(self):
        svc = _svc()
        pipeline = MagicMock()
        with patch("integrations.marketing_unified_service.atom_ingestion_pipeline",
                   pipeline):
            out = await svc.get_campaign_performance(MarketingPlatform.GOOGLE_ADS)
        assert out["platform"] == "google_ads"
        assert out["campaign_id"] == "c_555"
        assert out["spend"] == 500.0
        assert out["conversions"] == 22
        pipeline.ingest_record.assert_called_once()
        kwargs = pipeline.ingest_record.call_args.kwargs
        assert kwargs["app_type"] == "google_ads"
        assert kwargs["record_type"] == "campaign"
        assert kwargs["data"] == out

    async def test_import_error_path_generic(self):
        """When atom_ingestion_pipeline is unavailable the module-level name is
        undefined -> NameError inside the op -> generic envelope, no leak."""
        svc = _svc()
        import integrations.marketing_unified_service as mod
        with patch.object(mod, "atom_ingestion_pipeline", None):
            out = await svc.execute_operation("get_campaign_performance", {})
        assert out["success"] is False
        assert out["error"] == "Marketing Unified operation failed"
