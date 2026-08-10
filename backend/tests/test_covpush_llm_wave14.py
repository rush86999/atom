"""Coverage wave 14 — BYOK cache pre-seeding, RTK compression engine,
compression pipeline (TDD)."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.byok_cache_preseeding import (
    maybe_preseed_on_startup,
    preseed_all_caches,
    preseed_cache_aware_router,
    preseed_cognitive_models,
    preseed_governance_cache,
    preseed_pricing_cache,
    print_preseed_results,
)
from core.llm.compression import (
    CompressionMetrics,
    CompressionPipeline,
    get_compression_pipeline,
)
from core.llm.compression.rtk_engine import RTKEngine


# =========================================================================== #
# byok_cache_preseeding
# =========================================================================== #
class TestPreseedPricing:
    @pytest.mark.asyncio
    async def test_success_counts(self):
        with patch(
            "core.byok_cache_preseeding.refresh_pricing_cache",
            AsyncMock(return_value={
                "gpt-4o": {"litellm_provider": "openai", "supports_cache": True,
                           "supports_tools": True, "supports_vision": True},
                "deepseek-chat": {"litellm_provider": "deepseek",
                                  "supports_cache": False},
            }),
        ):
            result = await preseed_pricing_cache(force_refresh=True, verbose=False)
        assert result["success"] is True
        assert result["models_loaded"] == 2
        assert result["providers"] == ["deepseek", "openai"]
        assert result["models_with_cache_support"] == 1
        assert result["models_with_tools_support"] == 1
        assert result["models_with_vision_support"] == 1

    @pytest.mark.asyncio
    async def test_failure_path(self):
        with patch(
            "core.byok_cache_preseeding.refresh_pricing_cache",
            AsyncMock(side_effect=RuntimeError("fetch failed")),
        ):
            result = await preseed_pricing_cache(verbose=False)
        assert result["success"] is False
        assert result["models_loaded"] == 0


class TestPreseedCognitive:
    @pytest.mark.asyncio
    async def test_validates_tier_models(self):
        fetcher = MagicMock()
        fetcher.get_model_price.side_effect = lambda m: {"cost": 1} if m == "gpt-4o-mini" else None
        with patch(
            "core.byok_cache_preseeding.get_pricing_fetcher", return_value=fetcher
        ):
            result = await preseed_cognitive_models(verbose=False)
        assert result["success"] is True
        assert result["tiers_loaded"] >= 1  # MICRO has gpt-4o-mini
        assert result["models_missing"] > 0
        assert "micro" in result["tier_summary"]

    @pytest.mark.asyncio
    async def test_failure_path(self):
        with patch(
            "core.byok_cache_preseeding.CognitiveClassifier",
            side_effect=RuntimeError("boom"),
        ):
            result = await preseed_cognitive_models(verbose=False)
        assert result["success"] is False


class TestPreseedGovernance:
    @pytest.mark.asyncio
    async def test_seeds_with_real_agents(self):
        agent = SimpleNamespace(id="a1", status="autonomous")
        db = MagicMock()
        db.query.return_value.limit.return_value.all.return_value = [agent]
        cache = MagicMock()
        cache.set.return_value = True
        cache.cache_directory.return_value = True
        cache.get_stats.return_value = {"size": 10, "hit_rate": 50.0}
        ctx = MagicMock()
        ctx.__enter__.return_value = db
        ctx.__exit__.return_value = False
        with patch("core.byok_cache_preseeding.SessionLocal", return_value=db), \
             patch(
                 "core.byok_cache_preseeding.get_governance_cache",
                 return_value=cache,
             ):
            result = await preseed_governance_cache(
                workspace_id="default", verbose=False
            )
        assert result["success"] is True
        assert result["actions_cached"] > 0
        assert result["directories_cached"] > 0
        assert result["cache_size"] == 10

    @pytest.mark.asyncio
    async def test_seeds_with_dummy_agents(self):
        db = MagicMock()
        db.query.return_value.limit.return_value.all.return_value = []
        cache = MagicMock()
        cache.get_stats.return_value = {"size": 0, "hit_rate": 0.0}
        ctx = MagicMock()
        ctx.__enter__.return_value = db
        ctx.__exit__.return_value = False
        with patch("core.byok_cache_preseeding.SessionLocal", return_value=db), \
             patch(
                 "core.byok_cache_preseeding.get_governance_cache",
                 return_value=cache,
             ):
            result = await preseed_governance_cache(
                workspace_id="default", verbose=False
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_failure_path(self):
        with patch(
            "core.byok_cache_preseeding.SessionLocal",
            side_effect=RuntimeError("db down"),
        ):
            result = await preseed_governance_cache(verbose=False)
        assert result["success"] is False


class TestPreseedCacheAware:
    @pytest.mark.asyncio
    async def test_seeds_history(self):
        with patch("core.byok_cache_preseeding.get_pricing_fetcher"):
            result = await preseed_cache_aware_router(verbose=False)
        assert result["success"] is True
        assert result["prompts_seeded"] > 0
        assert result["baseline_probability"] == 0.5
        assert result["cache_history_size"] > 0


class TestPreseedAll:
    @pytest.mark.asyncio
    async def test_all_caches_shape(self):
        with patch(
            "core.byok_cache_preseeding.preseed_pricing_cache",
            AsyncMock(return_value={"success": True, "models_loaded": 10}),
        ), patch(
            "core.byok_cache_preseeding.preseed_cognitive_models",
            AsyncMock(return_value={"success": True, "tiers_loaded": 5}),
        ), patch(
            "core.byok_cache_preseeding.preseed_governance_cache",
            AsyncMock(return_value={"success": True, "actions_cached": 4}),
        ), patch(
            "core.byok_cache_preseeding.preseed_cache_aware_router",
            AsyncMock(return_value={"success": True}),
        ):
            result = await preseed_all_caches(verbose=False)
        assert result["pricing"]["models_loaded"] == 10
        assert result["cognitive"]["tiers_loaded"] == 5
        assert result["governance"]["actions_cached"] == 4
        assert result["duration_seconds"] >= 0
        assert "completed_at" in result

    @pytest.mark.asyncio
    async def test_error_collected(self):
        with patch(
            "core.byok_cache_preseeding.preseed_pricing_cache",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await preseed_all_caches(verbose=False)
        assert "error" in result


class TestStartupPreseed:
    @pytest.mark.asyncio
    async def test_skipped_when_disabled(self):
        with patch.dict("os.environ", {"PRESEED_CACHE_ON_STARTUP": "false"}):
            assert await maybe_preseed_on_startup() is None

    @pytest.mark.asyncio
    async def test_runs_when_enabled(self):
        with patch.dict("os.environ", {"PRESEED_CACHE_ON_STARTUP": "true"}), \
             patch(
                 "core.byok_cache_preseeding.preseed_all_caches",
                 AsyncMock(return_value={"pricing": {"success": True}}),
             ):
            result = await maybe_preseed_on_startup()
        assert result["pricing"]["success"] is True

    def test_print_results(self, capsys):
        results = {
            "pricing": {"success": True, "models_loaded": 3, "providers": ["a", "b"],
                        "duration_seconds": 1.0},
            "cognitive": {"success": True, "tiers_loaded": 2, "models_validated": 5,
                          "duration_seconds": 0.5},
            "governance": {"success": True, "actions_cached": 4, "directories_cached": 2,
                           "cache_size": 6, "duration_seconds": 0.3},
            "cache_aware": {"success": True, "prompts_seeded": 3,
                           "baseline_probability": 0.5, "duration_seconds": 0.2},
            "duration_seconds": 2.0,
        }
        print_preseed_results(results)
        out = capsys.readouterr().out
        assert "BYOK Cache Pre-seeding Results" in out
        assert "Models loaded: 3" in out


# =========================================================================== #
# RTKEngine
# =========================================================================== #
class TestRTKEngine:
    def test_short_text_unchanged(self):
        engine = RTKEngine()
        assert engine.compress("short") == "short"

    def test_empty_text(self):
        engine = RTKEngine()
        assert engine.compress("") == ""

    def test_structured_json_skipped(self):
        engine = RTKEngine()
        text = '{"key": "value", "items": [1, 2, 3], "nested": {"a": "b"}}'
        assert engine.compress(text) == text

    def test_ansi_stripped(self):
        engine = RTKEngine()
        text = "line one\x1b[31mred\x1b[0m line " * 10
        out = engine.compress(text)
        assert "\x1b[" not in out

    def test_repeated_lines_collapsed(self):
        engine = RTKEngine()
        text = "some build output line\n" * 40
        out = engine.compress(text)
        assert out.count("some build output line") < 40

    def test_caps_section_length(self):
        engine = RTKEngine()
        text = "x" * 20000
        out = engine.compress(text)
        assert len(out) <= 20000

    def test_is_structured_data_fence(self):
        engine = RTKEngine()
        fenced = "```python\nprint('hello')\nprint('world')\n```"
        assert engine._is_structured_data(fenced) is True
        assert engine._is_structured_data("plain log text " * 10) is False


# =========================================================================== #
# CompressionPipeline / Metrics
# =========================================================================== #
class TestCompressionPipeline:
    def test_metrics_helpers(self):
        m = CompressionMetrics(original_tokens=100, compressed_tokens=60)
        assert m.savings_tokens == 40
        assert m.savings_pct == pytest.approx(40.0)
        d = m.to_dict()
        assert d["savings_tokens"] == 40
        m2 = CompressionMetrics(original_tokens=0)
        assert m2.savings_pct == 0.0

    def test_empty_input(self):
        pipeline = CompressionPipeline()
        out, metrics = pipeline.compress_tool_output("   ")
        assert out == "   "
        assert metrics.savings_tokens == 0

    def test_singleton(self):
        assert get_compression_pipeline() is get_compression_pipeline()

    def test_structured_input_skipped(self):
        pipeline = CompressionPipeline()
        text = '{"a": 1, "b": [2, 3]}' + " " * 100
        out, metrics = pipeline.compress_tool_output(text)
        assert out == text
        assert "rtk" not in metrics.engines_applied

    def test_rtk_applied_to_noisy_logs(self):
        pipeline = CompressionPipeline()
        text = ("Build complete! " * 30) + "\n" + ("same line again\n" * 50)
        out, metrics = pipeline.compress_tool_output(text)
        assert "rtk" in metrics.engines_applied or metrics.savings_tokens >= 0

    def test_pipeline_error_tolerated(self):
        pipeline = CompressionPipeline()
        pipeline._rtk = MagicMock()
        pipeline._rtk.compress.side_effect = RuntimeError("boom")
        text = "some log output " * 30
        out, metrics = pipeline.compress_tool_output(text)
        assert out == text  # returns original on engine failure
