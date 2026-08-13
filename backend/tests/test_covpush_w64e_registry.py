"""Coverage wave 64e — core/llm/registry package (TDD, mocked httpx/redis, no network).

Covers the 8 previously-uncovered registry modules to >=95% statement coverage:
- transformers.py       (10% -> 100%): provider normalization, capability inference,
  litellm/openrouter transforms, batch transform, duplicate merging
- cache.py              (19% -> 100%): model/list cache CRUD, atomic swap w/ lock,
  tenant invalidation, warm cache, delete_model
- lmsys_client.py       (24% -> ~98%): leaderboard fetch (cache hit/miss/fallback),
  response parsing formats, name normalization + fuzzy mapping, ELO conversion
- fetchers.py           (40% -> ~98%): litellm/openrouter fetchers (retry + plain),
  error branches, concurrent fetch_all, context manager, convenience function
- sync_job.py           (32% -> ~98%): run states (skip/full/error), timestamp
  update, should_sync matrix, convenience runner
- heuristic_scorer.py   (71% -> 100%): tier scoring, version/context bonuses,
  clamping, tier info, convenience function
- rate_limiter.py       (31% -> 100%): rate-limit state, exponential backoff +
  jitter delay, 429/5xx/network retry matrix, retry-after header parsing
- curated_overrides.py  (84% -> 100%): pricing-shape conversion edge branches

Style: mocked dependencies, ZERO LLM spend, no network (httpx/redis mocked),
no real DB (db sessions are MagicMock).
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.llm.registry import cache as cache_module
from core.llm.registry import fetchers as fetchers_module
from core.llm.registry import heuristic_scorer as heuristic_module
from core.llm.registry import lmsys_client as lmsys_module
from core.llm.registry import rate_limiter as rate_module
from core.llm.registry import sync_job as sync_module
from core.llm.registry import transformers as transform_module
from core.llm.registry.cache import RegistryCacheService
from core.llm.registry.curated_overrides import (
    CURATED_OVERRIDES,
    apply_curated_overrides,
    apply_curated_overrides_to_pricing,
    curated_overrides_in_pricing_shape,
)
from core.llm.registry.fetchers import ModelMetadataFetcher, fetch_model_metadata
from core.llm.registry.heuristic_scorer import HeuristicScorer, calculate_quality_score
from core.llm.registry.lmsys_client import LMSYSClient, fetch_lmsys_scores
from core.llm.registry.rate_limiter import APIClientWithRetry, RateLimiter
from core.llm.registry.sync_job import ModelSyncJob, run_sync_job
from core.llm.registry.transformers import (
    normalize_provider,
    infer_capabilities,
    transform_litellm_model,
    transform_openrouter_model,
    transform_batch,
    merge_duplicate_models,
)


# --------------------------------------------------------------------------- #
# Shared fakes
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Plain (non-MagicMock) httpx-style response."""

    def __init__(self, payload=None, status_code=200, headers=None, raise_err=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self._raise_err = raise_err

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self._raise_err is not None:
            raise self._raise_err


class FakeAsyncClient:
    """Plain async client whose get() returns a configurable response.

    Responses carrying a ``raise_err`` raise it from get() (mirrors real
    httpx.AsyncClient behavior where transport errors surface at request time).
    """

    def __init__(self, responses, default_status=200):
        self.responses = list(responses)
        self.default_status = default_status
        self.closed = False

    async def get(self, *args, **kwargs):
        if self.responses:
            response = self.responses.pop(0)
            if getattr(response, "_raise_err", None) is not None:
                raise response._raise_err
            return response
        return FakeResponse(status_code=self.default_status)

    async def aclose(self):
        self.closed = True


def make_cache_mock() -> AsyncMock:
    """AsyncMock cache service: get_async -> None by default (cache miss)."""
    cache = AsyncMock()
    cache.get_async.return_value = None
    return cache


def real_http_response(status_code, payload=None, headers=None, raise_err=None):
    """Real httpx.Response for status-code / header-sensitive code paths."""
    return httpx.Response(
        status_code,
        json=payload,
        headers=headers or {},
        request=httpx.Request("GET", "http://example.invalid"),
    )


# --------------------------------------------------------------------------- #
# transformers.py
# --------------------------------------------------------------------------- #
class TestNormalizeProvider:
    def test_empty_string_returns_unknown(self):
        assert normalize_provider("") == "unknown"

    def test_none_returns_unknown(self):
        assert normalize_provider(None) == "unknown"

    def test_whitespace_only_returns_unknown(self):
        # Regression: whitespace-only input previously fell through to "" (the
        # truthy "   " passed the `if not provider` guard, then strip() made
        # the string empty). Fixed to return 'unknown'.
        assert normalize_provider("   ") == "unknown"

    def test_openai(self):
        assert normalize_provider("openai") == "openai"

    def test_openai_uppercase_with_spaces(self):
        assert normalize_provider("  OPENAI  ") == "openai"

    def test_gpt_variant(self):
        assert normalize_provider("gpt") == "openai"

    def test_azure_variant(self):
        assert normalize_provider("azure") == "openai"

    def test_anthropic(self):
        assert normalize_provider("anthropic") == "anthropic"

    def test_claude_variant(self):
        assert normalize_provider("claude") == "anthropic"

    def test_google(self):
        assert normalize_provider("google") == "google"

    def test_gemini_variant(self):
        assert normalize_provider("gemini") == "google"

    def test_palm_variant(self):
        assert normalize_provider("palm") == "google"

    def test_vertex_variant(self):
        assert normalize_provider("vertex") == "google"

    def test_meta(self):
        assert normalize_provider("meta") == "meta"

    def test_llama_variant(self):
        assert normalize_provider("llama") == "meta"

    def test_facebook_variant(self):
        assert normalize_provider("facebook") == "meta"

    def test_mistral(self):
        assert normalize_provider("mistral") == "mistral"

    def test_mixtral_variant(self):
        assert normalize_provider("mixtral") == "mistral"

    def test_cohere(self):
        assert normalize_provider("cohere") == "cohere"

    def test_perplexity(self):
        assert normalize_provider("perplexity") == "perplexity"

    def test_deepseek(self):
        assert normalize_provider("deepseek") == "deepseek"

    def test_unknown_provider_lowercased(self):
        assert normalize_provider("MyWeirdProvider") == "myweirdprovider"

    def test_unknown_with_leading_space(self):
        assert normalize_provider("  groq") == "groq"


class TestInferCapabilities:
    def test_empty_name_returns_empty_list(self):
        assert infer_capabilities("") == []
        assert infer_capabilities(None) == []

    def test_vision_patterns(self):
        for name in ["gpt-4-vision-preview", "gpt-4o", "claude-3-opus", "gemini-pro", "multimodal-x", "image-1", "qwen-vl-max"]:
            caps = infer_capabilities(name)
            assert "vision" in caps, f"{name} should have vision: {caps}"

    def test_tools_patterns(self):
        for name in ["gpt-4-turbo", "gpt-3.5-turbo", "claude-3-sonnet", "gemini-1.5-pro", "model-function-v1", "x-tool-y"]:
            caps = infer_capabilities(name)
            assert "tools" in caps, f"{name} should have tools: {caps}"

    def test_audio_patterns(self):
        for name in ["whisper-1", "audio-model", "speech-2", "transcription-x"]:
            caps = infer_capabilities(name)
            assert "audio" in caps, f"{name} should have audio: {caps}"

    def test_json_patterns(self):
        for name in ["gpt-json", "structured-out"]:
            caps = infer_capabilities(name)
            assert "json_mode" in caps, f"{name} should have json_mode: {caps}"

    def test_description_based_matching(self):
        caps = infer_capabilities("unknown-model", description="supports vision and audio input")
        assert "vision" in caps
        assert "audio" in caps

    def test_description_ignored_when_empty(self):
        caps = infer_capabilities("plain-model", description="")
        assert caps == []

    def test_no_match_returns_empty(self):
        assert infer_capabilities("random-model-7") == []

    def test_gpt4_special_case_adds_tools(self):
        caps = infer_capabilities("gpt-4o-mini")
        assert "tools" in caps

    def test_turbo_special_case_adds_tools(self):
        caps = infer_capabilities("llama-turbo")
        assert "tools" in caps

    def test_case_insensitive(self):
        assert "VISION" not in infer_capabilities("GPT-4-VISION")
        caps = infer_capabilities("GPT-4-VISION")
        assert "vision" in caps

    def test_sorted_results(self):
        caps = infer_capabilities("gpt-4o-audio-vision")
        assert caps == sorted(caps)


class TestTransformLitellmModel:
    def test_non_dict_input_returns_empty(self):
        assert transform_litellm_model([], "gpt-4") == {}
        assert transform_litellm_model(None, "gpt-4") == {}
        assert transform_litellm_model("str", "gpt-4") == {}

    def test_happy_path(self):
        result = transform_litellm_model(
            {
                "max_tokens": 8192,
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
                "litellm_provider": "openai",
                "mode": "chat",
                "extra_field": "kept",
            },
            "gpt-4",
        )
        assert result["provider"] == "openai"
        assert result["model_name"] == "gpt-4"
        assert result["context_window"] == 8192
        assert result["input_price_per_token"] == 0.00003
        assert result["output_price_per_token"] == 0.00006
        assert "tools" in result["capabilities"]
        assert result["provider_metadata"]["litellm_provider"] == "openai"
        assert result["provider_metadata"]["mode"] == "chat"
        assert result["provider_metadata"]["source"] == "litellm"
        assert result["provider_metadata"]["extra_field"] == "kept"
        # Excluded from metadata
        assert "max_tokens" not in result["provider_metadata"]
        assert "input_cost_per_token" not in result["provider_metadata"]

    def test_provider_inferred_from_model_name_when_unknown(self):
        result = transform_litellm_model({}, "claude-3-opus")
        assert result["provider"] == "anthropic"

    def test_max_input_tokens_fallback(self):
        result = transform_litellm_model({"max_input_tokens": 4096}, "m")
        assert result["context_window"] == 4096

    def test_max_context_tokens_fallback(self):
        result = transform_litellm_model({"max_context_tokens": 2048}, "m")
        assert result["context_window"] == 2048

    def test_no_context_fields_returns_none(self):
        result = transform_litellm_model({}, "m")
        assert result["context_window"] is None

    def test_pricing_string_conversion(self):
        result = transform_litellm_model(
            {"input_cost_per_token": "0.00003", "output_cost_per_token": "0.00006"}, "m"
        )
        assert result["input_price_per_token"] == 0.00003
        assert result["output_price_per_token"] == 0.00006

    def test_bad_pricing_strings_become_none(self):
        result = transform_litellm_model(
            {"input_cost_per_token": "abc", "output_cost_per_token": 0.5}, "m"
        )
        assert result["input_price_per_token"] is None
        assert result["output_price_per_token"] == 0.5

    def test_bad_pricing_type_becomes_none(self):
        result = transform_litellm_model(
            {"input_cost_per_token": 0.5, "output_cost_per_token": object()}, "m"
        )
        assert result["input_price_per_token"] == 0.5
        assert result["output_price_per_token"] is None

    def test_zero_pricing_kept(self):
        result = transform_litellm_model(
            {"input_cost_per_token": 0, "output_cost_per_token": 0}, "m"
        )
        assert result["input_price_per_token"] == 0
        assert result["output_price_per_token"] == 0

    def test_mode_default_chat(self):
        result = transform_litellm_model({}, "m")
        assert result["provider_metadata"]["mode"] == "chat"


class TestTransformOpenrouterModel:
    def test_non_dict_input_returns_empty(self):
        assert transform_openrouter_model("nope") == {}
        assert transform_openrouter_model(None) == {}

    def test_missing_id_returns_empty(self):
        assert transform_openrouter_model({"name": "x"}) == {}

    def test_happy_path(self):
        result = transform_openrouter_model(
            {
                "id": "openai/gpt-4",
                "name": "GPT-4",
                "description": "desc",
                "context_length": 8192,
                "pricing": {"prompt": 0.00003, "completion": 0.00006},
                "architecture": {"input_modalities": ["text"]},
                "extra": "meta",
            }
        )
        assert result["provider"] == "openai"
        assert result["model_name"] == "openai/gpt-4"
        assert result["context_window"] == 8192
        assert result["input_price_per_token"] == 0.00003
        assert result["output_price_per_token"] == 0.00006
        assert result["provider_metadata"]["name"] == "GPT-4"
        assert result["provider_metadata"]["description"] == "desc"
        assert result["provider_metadata"]["architecture"] == {"input_modalities": ["text"]}
        assert result["provider_metadata"]["source"] == "openrouter"
        assert result["provider_metadata"]["extra"] == "meta"

    def test_id_without_slash(self):
        # No slash -> no provider part -> normalize_provider('') -> 'unknown'
        result = transform_openrouter_model({"id": "justamodel", "name": "Just A Model"})
        assert result["provider"] == "unknown"
        assert result["model_name"] == "justamodel"

    def test_context_window_fallback(self):
        result = transform_openrouter_model({"id": "x/y", "context_window": 4096})
        assert result["context_window"] == 4096

    def test_no_context_returns_none(self):
        result = transform_openrouter_model({"id": "x/y"})
        assert result["context_window"] is None

    def test_pricing_strings_converted(self):
        result = transform_openrouter_model(
            {"id": "x/y", "pricing": {"prompt": "0.000001", "completion": "0.000002"}}
        )
        assert result["input_price_per_token"] == 0.000001
        assert result["output_price_per_token"] == 0.000002

    def test_bad_pricing_strings_become_none(self):
        result = transform_openrouter_model(
            {"id": "x/y", "pricing": {"prompt": "nope", "completion": 0.1}}
        )
        assert result["input_price_per_token"] is None
        assert result["output_price_per_token"] == 0.1

    def test_bad_output_pricing_string_becomes_none(self):
        result = transform_openrouter_model(
            {"id": "x/y", "pricing": {"prompt": 0.1, "completion": "nope"}}
        )
        assert result["input_price_per_token"] == 0.1
        assert result["output_price_per_token"] is None

    def test_pricing_non_dict(self):
        result = transform_openrouter_model({"id": "x/y", "pricing": "N/A"})
        assert result["input_price_per_token"] is None
        assert result["output_price_per_token"] is None

    def test_capabilities_from_name_and_description(self):
        result = transform_openrouter_model(
            {"id": "openai/gpt-4-vision", "name": "GPT-4 Vision", "description": "multimodal"}
        )
        assert "vision" in result["capabilities"]

    def test_provider_normalized_from_id(self):
        result = transform_openrouter_model({"id": "anthropic/claude-3-opus"})
        assert result["provider"] == "anthropic"


class TestTransformBatch:
    def _litellm_cases(self):
        return {"gpt-4": {"litellm_provider": "openai", "max_tokens": 1}}

    def test_litellm_source(self):
        out = transform_batch(
            {"gpt-4": {"litellm_provider": "openai", "max_tokens": 1}},
            "litellm",
            transform_litellm_model,
        )
        assert len(out) == 1
        assert out[0]["model_name"] == "gpt-4"

    def test_openrouter_source(self):
        out = transform_batch(
            {"openai/gpt-4": {"id": "openai/gpt-4", "name": "GPT-4"}},
            "openrouter",
            transform_openrouter_model,
        )
        assert len(out) == 1
        assert out[0]["provider"] == "openai"

    def test_unknown_source_skips_models(self):
        out = transform_batch({"a": {"id": "a"}}, "bogus", transform_openrouter_model)
        assert out == []

    def test_empty_result_increments_failed(self):
        out = transform_batch({"a": {"id": ""}}, "openrouter", transform_openrouter_model)
        assert out == []

    def test_exception_in_transformer_skips_model(self):
        def boom(data, model_id):
            raise RuntimeError("kaboom")

        out = transform_batch({"a": {}}, "litellm", boom)
        assert out == []

    def test_empty_models_dict(self):
        assert transform_batch({}, "litellm", transform_litellm_model) == []

    def test_mixed_success_and_failure(self):
        def flaky(data, model_id):
            if model_id == "bad":
                raise ValueError("no")
            return {"model_name": model_id}

        out = transform_batch({"ok": {}, "bad": {}}, "litellm", flaky)
        assert len(out) == 1
        assert out[0]["model_name"] == "ok"


class TestMergeDuplicateModels:
    def _model(self, provider, name, source):
        return {
            "provider": provider,
            "model_name": name,
            "provider_metadata": {"source": source},
        }

    def test_no_duplicates(self):
        models = [
            self._model("openai", "gpt-4", "litellm"),
            self._model("openai", "gpt-4o", "litellm"),
        ]
        out = merge_duplicate_models(models)
        assert len(out) == 2

    def test_duplicate_prefers_priority_source(self):
        models = [
            self._model("openai", "gpt-4", "openrouter"),
            self._model("openai", "gpt-4", "litellm"),
        ]
        out = merge_duplicate_models(models, priority_source="litellm")
        assert len(out) == 1
        assert out[0]["provider_metadata"]["source"] == "litellm"

    def test_duplicate_without_priority_source_keeps_existing(self):
        models = [
            self._model("openai", "gpt-4", "openrouter"),
            self._model("openai", "gpt-4", "bogus"),
        ]
        out = merge_duplicate_models(models, priority_source="litellm")
        assert len(out) == 1
        assert out[0]["provider_metadata"]["source"] == "openrouter"

    def test_duplicate_same_as_priority_keeps_existing(self):
        models = [
            self._model("openai", "gpt-4", "litellm"),
            self._model("openai", "gpt-4", "litellm"),
        ]
        out = merge_duplicate_models(models, priority_source="litellm")
        assert len(out) == 1
        assert out[0]["provider_metadata"]["source"] == "litellm"

    def test_empty_list(self):
        assert merge_duplicate_models([]) == []


# --------------------------------------------------------------------------- #
# cache.py
# --------------------------------------------------------------------------- #
class TestRegistryCacheKeys:
    def test_model_key(self):
        with patch.object(cache_module, "UniversalCacheService") as ucs:
            svc = RegistryCacheService()
            assert svc._model_key("t1", "openai", "gpt-4") == "llm_model:openai:gpt-4"
            assert ucs.called

    def test_list_key_with_provider(self):
        with patch.object(cache_module, "UniversalCacheService"):
            svc = RegistryCacheService()
            assert svc._list_key("t1", "openai") == "llm_models_list:openai"

    def test_list_key_without_provider(self):
        with patch.object(cache_module, "UniversalCacheService"):
            svc = RegistryCacheService()
            assert svc._list_key("t1") == "llm_models_list"

    def test_list_key_none_provider(self):
        with patch.object(cache_module, "UniversalCacheService"):
            svc = RegistryCacheService()
            assert svc._list_key("t1", None) == "llm_models_list"


class TestRegistryCacheGetSet:
    @pytest.fixture
    def svc(self):
        with patch.object(cache_module, "UniversalCacheService") as ucs:
            ucs.return_value = make_cache_mock()
            return RegistryCacheService(), ucs.return_value

    async def test_get_model_hit(self, svc):
        svc, cache = svc
        cache.get_async.return_value = {"context_window": 8192}
        result = await svc.get_model("t1", "openai", "gpt-4")
        assert result == {"context_window": 8192}
        cache.get_async.assert_called_once_with("llm_model:openai:gpt-4")

    async def test_get_model_miss(self, svc):
        svc, cache = svc
        result = await svc.get_model("t1", "openai", "gpt-4")
        assert result is None

    async def test_get_model_error_returns_none(self, svc):
        svc, cache = svc
        cache.get_async.side_effect = RuntimeError("redis down")
        assert await svc.get_model("t1", "openai", "gpt-4") is None

    async def test_set_model_success(self, svc):
        svc, cache = svc
        assert await svc.set_model("t1", "openai", "gpt-4", {"a": 1}) is True
        cache.set_async.assert_called_once_with("llm_model:openai:gpt-4", {"a": 1}, 86400)

    async def test_set_model_error_returns_false(self, svc):
        svc, cache = svc
        cache.set_async.side_effect = RuntimeError("down")
        assert await svc.set_model("t1", "openai", "gpt-4", {"a": 1}) is False

    async def test_get_models_list_hit(self, svc):
        svc, cache = svc
        cache.get_async.return_value = [{"a": 1}]
        assert await svc.get_models_list("t1") == [{"a": 1}]
        cache.get_async.assert_called_once_with("llm_models_list")

    async def test_get_models_list_hit_with_provider(self, svc):
        svc, cache = svc
        cache.get_async.return_value = [{"a": 1}]
        assert await svc.get_models_list("t1", "openai") == [{"a": 1}]
        cache.get_async.assert_called_once_with("llm_models_list:openai")

    async def test_get_models_list_miss(self, svc):
        svc, cache = svc
        assert await svc.get_models_list("t1") is None

    async def test_get_models_list_error_returns_none(self, svc):
        svc, cache = svc
        cache.get_async.side_effect = RuntimeError("down")
        assert await svc.get_models_list("t1") is None

    async def test_set_models_list_success(self, svc):
        svc, cache = svc
        assert await svc.set_models_list("t1", [{"a": 1}]) is True
        cache.set_async.assert_called_once_with("llm_models_list", [{"a": 1}], 86400)

    async def test_set_models_list_with_provider(self, svc):
        svc, cache = svc
        assert await svc.set_models_list("t1", [{"a": 1}], "openai") is True
        cache.set_async.assert_called_once_with("llm_models_list:openai", [{"a": 1}], 86400)

    async def test_set_models_list_error_returns_false(self, svc):
        svc, cache = svc
        cache.set_async.side_effect = RuntimeError("down")
        assert await svc.set_models_list("t1", [{"a": 1}]) is False


class TestRegistryCacheAtomicSwap:
    @pytest.fixture
    def svc(self):
        with patch.object(cache_module, "UniversalCacheService") as ucs:
            ucs.return_value = make_cache_mock()
            return RegistryCacheService(), ucs.return_value

    def _models(self):
        return [
            {"provider": "openai", "model_name": "gpt-4"},
            {"provider": "openai", "model_name": "gpt-4o"},
            {"provider": "anthropic", "model_name": "claude-3"},
        ]

    async def test_atomic_swap_success(self, svc):
        svc, cache = svc
        assert await svc.atomic_swap_registry("t1", self._models()) is True
        # lock acquired
        cache.set_async.assert_any_call("t1:llm_registry_swap_lock", "swapping", 60)
        # lock released
        cache.delete_async.assert_any_call("t1:llm_registry_swap_lock")
        # individual model sets
        cache.set_async.assert_any_call("llm_model:openai:gpt-4", {"provider": "openai", "model_name": "gpt-4"}, 86400)
        # all + provider lists
        cache.set_async.assert_any_call("llm_models_list", self._models(), 86400)
        cache.set_async.assert_any_call("llm_models_list:openai", self._models()[:2], 86400)
        cache.set_async.assert_any_call("llm_models_list:anthropic", [self._models()[2]], 86400)

    async def test_atomic_swap_lock_held_raises(self, svc):
        svc, cache = svc
        cache.get_async.return_value = "swapping"
        with pytest.raises(Exception, match="Swap in progress"):
            await svc.atomic_swap_registry("t1", self._models())

    async def test_atomic_swap_lock_get_error_raises(self, svc):
        svc, cache = svc
        cache.get_async.side_effect = RuntimeError("redis down")
        with pytest.raises(RuntimeError):
            await svc.atomic_swap_registry("t1", self._models())

    async def test_atomic_swap_body_error_raises_and_releases_lock(self, svc):
        svc, cache = svc
        with patch.object(RegistryCacheService, "set_models_list", new=AsyncMock(side_effect=RuntimeError("boom"))):
            with pytest.raises(RuntimeError):
                await svc.atomic_swap_registry("t1", self._models())
        cache.delete_async.assert_called_once_with("t1:llm_registry_swap_lock")

    async def test_atomic_swap_empty_models(self, svc):
        svc, cache = svc
        assert await svc.atomic_swap_registry("t1", []) is True
        cache.set_async.assert_any_call("llm_models_list", [], 86400)

    async def test_atomic_swap_lock_release_failure_swallowed(self, svc):
        svc, cache = svc
        cache.delete_async.side_effect = RuntimeError("delete failed")
        assert await svc.atomic_swap_registry("t1", self._models()) is True

    async def test_atomic_swap_missing_provider_defaults(self, svc):
        svc, cache = svc
        models = [{"model_name": "only-name"}]
        assert await svc.atomic_swap_registry("t1", models) is True
        cache.set_async.assert_any_call(
            "llm_model:unknown:only-name",
            {"model_name": "only-name"},
            86400,
        )


class TestRegistryCacheMisc:
    @pytest.fixture
    def svc(self):
        with patch.object(cache_module, "UniversalCacheService") as ucs:
            ucs.return_value = make_cache_mock()
            return RegistryCacheService(), ucs.return_value

    async def test_invalidate_tenant_success(self, svc):
        svc, cache = svc
        cache.delete_tenant_all.return_value = 5
        assert await svc.invalidate_tenant("t1") == 5
        cache.delete_tenant_all.assert_called_once_with("t1")

    async def test_invalidate_tenant_error_returns_zero(self, svc):
        svc, cache = svc
        cache.delete_tenant_all.side_effect = RuntimeError("down")
        assert await svc.invalidate_tenant("t1") == 0

    async def test_warm_cache(self, svc):
        svc, cache = svc
        models = [
            {"provider": "openai", "model_name": "gpt-4"},
            {"provider": "anthropic", "model_name": "claude-3"},
        ]
        await svc.warm_cache("t1", models)
        cache.set_async.assert_any_call("llm_model:openai:gpt-4", models[0], 86400)
        cache.set_async.assert_any_call("llm_model:anthropic:claude-3", models[1], 86400)
        cache.set_async.assert_any_call("llm_models_list", models, 86400)
        cache.set_async.assert_any_call("llm_models_list:openai", [models[0]], 86400)
        cache.set_async.assert_any_call("llm_models_list:anthropic", [models[1]], 86400)

    async def test_warm_cache_empty(self, svc):
        svc, cache = svc
        await svc.warm_cache("t1", [])
        cache.set_async.assert_any_call("llm_models_list", [], 86400)

    async def test_warm_cache_model_missing_provider(self, svc):
        svc, cache = svc
        await svc.warm_cache("t1", [{"model_name": "x"}])
        cache.set_async.assert_any_call("llm_model:unknown:x", {"model_name": "x"}, 86400)

    async def test_delete_model_success(self, svc):
        svc, cache = svc
        assert await svc.delete_model("t1", "openai", "gpt-4") is True
        cache.delete_async.assert_any_call("llm_model:openai:gpt-4")
        cache.delete_async.assert_any_call("llm_models_list")
        cache.delete_async.assert_any_call("llm_models_list:openai")

    async def test_delete_model_error_returns_false(self, svc):
        svc, cache = svc
        cache.delete_async.side_effect = RuntimeError("down")
        assert await svc.delete_model("t1", "openai", "gpt-4") is False


# --------------------------------------------------------------------------- #
# lmsys_client.py
# --------------------------------------------------------------------------- #
class TestLMSYSClientInit:
    def test_init_without_cache(self):
        with patch.object(lmsys_module, "UniversalCacheService") as ucs:
            client = LMSYSClient()
            assert ucs.called
            assert client._client is None

    def test_init_with_cache(self):
        cache = make_cache_mock()
        client = LMSYSClient(cache_service=cache)
        assert client.cache is cache


class TestLMSYSClientHttp:
    async def test_get_client_creates_and_reuses(self):
        with patch.object(lmsys_module, "UniversalCacheService"):
            client = LMSYSClient()
            c1 = await client._get_client()
            c2 = await client._get_client()
            assert c1 is c2

    async def test_close_with_client(self):
        with patch.object(lmsys_module, "UniversalCacheService"):
            client = LMSYSClient()
            await client._get_client()
            fake = client._client
            fake.aclose = AsyncMock()
            await client.close()
            fake.aclose.assert_called_once()
            assert client._client is None

    async def test_close_without_client(self):
        with patch.object(lmsys_module, "UniversalCacheService"):
            client = LMSYSClient()
            await client.close()
            assert client._client is None


class TestLMSYSFetchLeaderboard:
    @pytest.fixture
    def client(self):
        with patch.object(lmsys_module, "UniversalCacheService") as ucs:
            cache = make_cache_mock()
            ucs.return_value = cache
            yield LMSYSClient(), cache

    async def test_cache_hit(self, client):
        client, cache = client
        cache.get_async.return_value = json.dumps({"gpt-4": 1250.5})
        scores = await client.fetch_leaderboard()
        assert scores == {"gpt-4": 1250.5}
        # No HTTP client created on cache hit
        assert client._client is None

    async def test_cache_hit_corrupt_json_fetches_api(self, client):
        client, cache = client
        cache.get_async.return_value = "{not-json"
        client._client = FakeAsyncClient([FakeResponse({"data": [{"name": "gpt-4", "score": 1000}]})])
        scores = await client.fetch_leaderboard()
        assert scores == {"gpt-4": 1000.0}
        # API result cached
        cache.set_async.assert_called_once()

    async def test_force_refresh_skips_cache(self, client):
        client, cache = client
        cache.get_async.return_value = json.dumps({"stale": 1.0})
        client._client = FakeAsyncClient([FakeResponse({"models": [{"name": "fresh", "score": 2}]})])
        scores = await client.fetch_leaderboard(force_refresh=True)
        assert scores == {"fresh": 2.0}

    async def test_fetch_success_no_cache_used(self, client):
        client, cache = client
        client._client = FakeAsyncClient([FakeResponse({"leaderboard": [{"name": "a", "score": 10}]})])
        scores = await client.fetch_leaderboard(use_cache=False)
        assert scores == {"a": 10.0}
        cache.set_async.assert_called_once()

    async def test_api_failure_uses_cached_fallback(self, client):
        client, cache = client
        client._client = FakeAsyncClient(
            [FakeResponse(raise_err=httpx.ConnectTimeout("timeout"))]
        )
        cache.get_async.side_effect = [
            None,  # initial cache check -> miss
            json.dumps({"fallback": 900.0}),  # fallback read
        ]
        scores = await client.fetch_leaderboard()
        assert scores == {"fallback": 900.0}

    async def test_api_failure_corrupt_fallback_raises(self, client):
        client, cache = client
        client._client = FakeAsyncClient(
            [FakeResponse(raise_err=httpx.ConnectTimeout("timeout"))]
        )
        cache.get_async.side_effect = [None, "{corrupt"]
        with pytest.raises(httpx.ConnectTimeout):
            await client.fetch_leaderboard()

    async def test_api_failure_no_cache_raises(self, client):
        client, cache = client
        client._client = FakeAsyncClient(
            [FakeResponse(raise_err=httpx.ConnectTimeout("timeout"))]
        )
        with pytest.raises(httpx.ConnectTimeout):
            await client.fetch_leaderboard(use_cache=False)

    async def test_api_failure_fallback_disabled_raises(self, client):
        client, cache = client
        client._client = FakeAsyncClient(
            [FakeResponse(raise_err=httpx.HTTPError("http"))]
        )
        cache.get_async.side_effect = [None, None]
        with pytest.raises(httpx.HTTPError):
            await client.fetch_leaderboard()


class TestLMSYSParse:
    @pytest.fixture
    def client(self):
        with patch.object(lmsys_module, "UniversalCacheService"):
            return LMSYSClient()

    def test_parse_leaderboard_key(self, client):
        data = {"leaderboard": [{"name": "a", "score": "100.5"}]}
        assert client._parse_leaderboard_response(data) == {"a": 100.5}

    def test_parse_models_key(self, client):
        data = {"models": [{"model": "b", "elo": 200}]}
        assert client._parse_leaderboard_response(data) == {"b": 200.0}

    def test_parse_data_key(self, client):
        data = {"data": [{"id": "c", "rating": 300}]}
        assert client._parse_leaderboard_response(data) == {"c": 300.0}

    def test_parse_skips_non_dict_entries(self, client):
        data = {"leaderboard": ["string", 42, None, {"name": "ok", "score": 1}]}
        assert client._parse_leaderboard_response(data) == {"ok": 1.0}

    def test_parse_skips_missing_name(self, client):
        data = {"leaderboard": [{"score": 1}]}
        assert client._parse_leaderboard_response(data) == {}

    def test_parse_skips_missing_score(self, client):
        data = {"leaderboard": [{"name": "a"}]}
        assert client._parse_leaderboard_response(data) == {}

    def test_parse_skips_zero_score_name_present(self, client):
        data = {"leaderboard": [{"name": "a", "score": 0}]}
        # score 0 is falsy but the entry still has a name; 'or' chain skips 0
        assert client._parse_leaderboard_response(data) == {}

    def test_parse_invalid_score_warns_and_skips(self, client):
        data = {"leaderboard": [{"name": "a", "score": "not-a-number"}, {"name": "b", "score": 5}]}
        assert client._parse_leaderboard_response(data) == {"b": 5.0}

    def test_parse_empty_leaderboard(self, client):
        assert client._parse_leaderboard_response({}) == {}
        assert client._parse_leaderboard_response({"leaderboard": []}) == {}

    def test_normalize_model_name(self, client):
        assert client.normalize_model_name("ChatGPT-4.5-Turbo") == "gpt-4-5"
        assert client.normalize_model_name("chat_gpt-4.5_Turbo") == "gpt-4-5"


class TestLMSYSMap:
    @pytest.fixture
    def client(self):
        with patch.object(lmsys_module, "UniversalCacheService"):
            return LMSYSClient()

    def test_map_direct_match_case_insensitive(self, client):
        assert client.map_model_name("GPT-4", ["gpt-4", "claude-3"]) == "gpt-4"

    def test_map_normalized_exact_match(self, client):
        assert client.map_model_name("chatgpt-4-turbo", ["gpt-4-turbo"]) == "gpt-4-turbo"

    def test_map_prefix_match_lmsys_is_prefix(self, client):
        # "gpt-4-turbo" normalizes to "gpt-4" so this is caught by the exact
        # normalized match; use a suffix that normalization keeps to reach the
        # prefix loop (registry name starts with the lmsys name).
        assert client.map_model_name("gpt-4", ["gpt-4-turbo-extra"]) == "gpt-4-turbo-extra"

    def test_map_prefix_match_registry_is_prefix(self, client):
        # Second direction of the prefix loop: lmsys name starts with registry.
        assert client.map_model_name("gpt-4-turbo-extra", ["gpt-4"]) == "gpt-4"

    def test_map_no_match_returns_none(self, client):
        assert client.map_model_name("totally-unrelated", ["gpt-4"]) is None

    def test_map_empty_registry(self, client):
        assert client.map_model_name("gpt-4", []) is None

    async def test_map_scores_to_registry(self, client):
        scores = {"gpt-4": 100.0, "no-match-here": 50.0}
        mapped = await client.map_scores_to_registry(scores, ["gpt-4"])
        assert mapped == {"gpt-4": 100.0}

    async def test_map_scores_empty(self, client):
        assert await client.map_scores_to_registry({}, ["gpt-4"]) == {}

    def test_elo_to_quality_mid(self, client):
        assert client.elo_to_quality_score(1050) == 50.0

    def test_elo_to_quality_below_min_clamped(self, client):
        assert client.elo_to_quality_score(100) == 0.0

    def test_elo_to_quality_above_max_clamped(self, client):
        assert client.elo_to_quality_score(5000) == 100.0

    def test_elo_to_quality_exact_bounds(self, client):
        assert client.elo_to_quality_score(800) == 0.0
        assert client.elo_to_quality_score(1300) == 100.0


class TestFetchLmsysScores:
    async def test_fetch_scores_closes_client(self):
        fake_client = MagicMock()
        fake_client.fetch_leaderboard = AsyncMock(return_value={"gpt-4": 1.0})
        fake_client.close = AsyncMock()
        with patch.object(lmsys_module, "LMSYSClient", return_value=fake_client):
            scores = await fetch_lmsys_scores()
        assert scores == {"gpt-4": 1.0}
        fake_client.fetch_leaderboard.assert_called_once_with(use_cache=True)
        fake_client.close.assert_called_once()

    async def test_fetch_scores_closes_client_on_error(self):
        fake_client = MagicMock()
        fake_client.fetch_leaderboard = AsyncMock(side_effect=RuntimeError("boom"))
        fake_client.close = AsyncMock()
        with patch.object(lmsys_module, "LMSYSClient", return_value=fake_client):
            with pytest.raises(RuntimeError):
                await fetch_lmsys_scores(use_cache=False)
        fake_client.close.assert_called_once()


# --------------------------------------------------------------------------- #
# fetchers.py
# --------------------------------------------------------------------------- #
class TestModelMetadataFetcherInit:
    def test_init_defaults(self):
        fetcher = ModelMetadataFetcher()
        assert fetcher.timeout == 30
        assert fetcher.use_retry is True
        assert fetcher._client is None
        assert fetcher._retry_client is None

    def test_init_custom(self):
        fetcher = ModelMetadataFetcher(timeout=5, use_retry=False)
        assert fetcher.timeout == 5
        assert fetcher.use_retry is False

    async def test_get_client(self):
        fetcher = ModelMetadataFetcher()
        c1 = await fetcher._get_client()
        c2 = await fetcher._get_client()
        assert c1 is c2

    async def test_get_retry_client_creates(self):
        fetcher = ModelMetadataFetcher()
        rc = await fetcher._get_retry_client()
        assert isinstance(rc, APIClientWithRetry)
        assert fetcher._retry_client is rc

    async def test_get_retry_client_disabled(self):
        fetcher = ModelMetadataFetcher(use_retry=False)
        assert await fetcher._get_retry_client() is None

    async def test_close_both_clients(self):
        fetcher = ModelMetadataFetcher()
        fake_client = FakeAsyncClient([])
        fake_retry = MagicMock()
        fake_retry.close = AsyncMock()
        fetcher._client = fake_client
        fetcher._retry_client = fake_retry
        await fetcher.close()
        assert fake_client.closed is True
        assert fetcher._client is None
        fake_retry.close.assert_called_once()
        assert fetcher._retry_client is None

    async def test_close_none(self):
        fetcher = ModelMetadataFetcher()
        await fetcher.close()
        assert fetcher._client is None
        assert fetcher._retry_client is None


class TestFetchLitellmModels:
    @pytest.fixture
    def fetcher(self):
        # Non-retry path by default so no real APIClientWithRetry is constructed.
        return ModelMetadataFetcher(use_retry=False)

    async def test_success_with_retry_client(self, fetcher):
        fetcher.use_retry = True
        retry_client = MagicMock()
        retry_client.get = AsyncMock(return_value=FakeResponse({"gpt-4": {"max_tokens": 1}}))
        fetcher._retry_client = retry_client
        result = await fetcher.fetch_litellm_models()
        assert result == {"gpt-4": {"max_tokens": 1}}
        retry_client.get.assert_called_once_with(fetchers_module.LITELLM_PRICING_URL, provider="litellm")

    async def test_success_with_plain_client(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse({"a": 1})])
        result = await fetcher.fetch_litellm_models()
        assert result == {"a": 1}

    async def test_non_dict_response_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse([1, 2, 3])])
        assert await fetcher.fetch_litellm_models() == {}

    async def test_timeout_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse(raise_err=httpx.ConnectTimeout("t"))])
        assert await fetcher.fetch_litellm_models() == {}

    async def test_http_status_error_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient(
            [FakeResponse(raise_err=httpx.HTTPStatusError("boom", request=httpx.Request("GET", "u"), response=httpx.Response(500)))]
        )
        assert await fetcher.fetch_litellm_models() == {}

    async def test_generic_exception_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse(raise_err=RuntimeError("boom"))])
        assert await fetcher.fetch_litellm_models() == {}

    async def test_retry_client_created_lazily(self, fetcher):
        fetcher.use_retry = True
        retry_client = MagicMock()
        retry_client.get = AsyncMock(return_value=FakeResponse({"gpt-4": {}}))
        with patch.object(fetchers_module, "APIClientWithRetry", return_value=retry_client):
            result = await fetcher.fetch_litellm_models()
        assert result == {"gpt-4": {}}
        assert fetcher._retry_client is retry_client


class TestFetchOpenrouterModels:
    @pytest.fixture
    def fetcher(self):
        return ModelMetadataFetcher(use_retry=False)

    async def test_success_with_retry_client(self, fetcher):
        fetcher.use_retry = True
        retry_client = MagicMock()
        retry_client.get = AsyncMock(
            return_value=FakeResponse({"data": [{"id": "openai/gpt-4", "name": "GPT-4"}]})
        )
        fetcher._retry_client = retry_client
        result = await fetcher.fetch_openrouter_models()
        assert "openai/gpt-4" in result
        assert "openrouter/owl-alpha" in result  # curated override merged
        retry_client.get.assert_called_once_with(fetchers_module.OPENROUTER_MODELS_URL, provider="openrouter")

    async def test_success_with_plain_client(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse({"data": [{"id": "a/b"}]})])
        result = await fetcher.fetch_openrouter_models()
        assert "a/b" in result
        # curated override is always merged on the success path
        assert "openrouter/owl-alpha" in result

    async def test_missing_data_field_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse({"unexpected": 1})])
        assert await fetcher.fetch_openrouter_models() == {}

    async def test_data_not_list_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse({"data": {"a": 1}})])
        assert await fetcher.fetch_openrouter_models() == {}

    async def test_entries_without_id_skipped(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse({"data": [{"no_id": 1}, {"id": "x/y"}]})])
        result = await fetcher.fetch_openrouter_models()
        assert result == {"x/y": {"id": "x/y"}, "openrouter/owl-alpha": CURATED_OVERRIDES["openrouter/owl-alpha"]}

    async def test_timeout_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse(raise_err=httpx.ConnectTimeout("t"))])
        assert await fetcher.fetch_openrouter_models() == {}

    async def test_http_status_error_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient(
            [FakeResponse(raise_err=httpx.HTTPStatusError("boom", request=httpx.Request("GET", "u"), response=httpx.Response(429)))]
        )
        assert await fetcher.fetch_openrouter_models() == {}

    async def test_generic_exception_returns_empty(self, fetcher):
        fetcher._client = FakeAsyncClient([FakeResponse(raise_err=ValueError("bad json"))])
        assert await fetcher.fetch_openrouter_models() == {}


class TestFetchAll:
    @pytest.fixture
    def fetcher(self):
        return ModelMetadataFetcher()

    async def test_fetch_all_success(self, fetcher):
        fetcher.fetch_litellm_models = AsyncMock(return_value={"gpt-4": {}})
        fetcher.fetch_openrouter_models = AsyncMock(return_value={"openai/gpt-4": {}})
        result = await fetcher.fetch_all()
        assert result["litellm"] == {"gpt-4": {}}
        assert result["openrouter"] == {"openai/gpt-4": {}}
        assert result["metadata"]["litellm_count"] == 1
        assert result["metadata"]["openrouter_count"] == 1
        assert "fetched_at" in result["metadata"]

    async def test_fetch_all_litellm_exception(self, fetcher):
        fetcher.fetch_litellm_models = AsyncMock(side_effect=RuntimeError("boom"))
        fetcher.fetch_openrouter_models = AsyncMock(return_value={"a": {}})
        result = await fetcher.fetch_all()
        assert result["litellm"] == {}
        assert result["openrouter"] == {"a": {}}
        assert result["metadata"]["litellm_count"] == 0

    async def test_fetch_all_openrouter_exception(self, fetcher):
        fetcher.fetch_litellm_models = AsyncMock(return_value={"a": {}})
        fetcher.fetch_openrouter_models = AsyncMock(side_effect=RuntimeError("boom"))
        result = await fetcher.fetch_all()
        assert result["openrouter"] == {}
        assert result["litellm"] == {"a": {}}

    async def test_fetch_all_non_dict_results(self, fetcher):
        fetcher.fetch_litellm_models = AsyncMock(return_value=[1, 2])
        fetcher.fetch_openrouter_models = AsyncMock(return_value="nope")
        result = await fetcher.fetch_all()
        assert result["litellm"] == {}
        assert result["openrouter"] == {}
        assert result["metadata"]["litellm_count"] == 0
        assert result["metadata"]["openrouter_count"] == 0

    async def test_fetch_all_gather_error(self, fetcher):
        with patch.object(fetchers_module.asyncio, "gather", side_effect=RuntimeError("gather failed")):
            result = await fetcher.fetch_all()
        assert result["litellm"] == {}
        assert result["openrouter"] == {}
        assert "error" in result["metadata"]
        assert result["metadata"]["litellm_count"] == 0


class TestFetcherContextManager:
    async def test_aenter_returns_self(self):
        fetcher = ModelMetadataFetcher()
        assert await fetcher.__aenter__() is fetcher

    async def test_aexit_closes(self):
        fetcher = ModelMetadataFetcher()
        fetcher.close = AsyncMock()
        await fetcher.__aexit__(None, None, None)
        fetcher.close.assert_called_once()

    async def test_fetch_model_metadata_convenience(self):
        fake_fetcher = MagicMock()
        fake_fetcher.fetch_all = AsyncMock(return_value={"litellm": {}})
        fake_fetcher.__aenter__ = AsyncMock(return_value=fake_fetcher)
        fake_fetcher.__aexit__ = AsyncMock(return_value=False)
        with patch.object(fetchers_module, "ModelMetadataFetcher", return_value=fake_fetcher) as m:
            result = await fetch_model_metadata(timeout=7)
        assert result == {"litellm": {}}
        m.assert_called_once_with(timeout=7)
        fake_fetcher.__aexit__.assert_called_once()


# --------------------------------------------------------------------------- #
# sync_job.py
# --------------------------------------------------------------------------- #
class TestModelSyncJobInit:
    def test_init_creates_registry_service(self):
        db = MagicMock()
        job = ModelSyncJob(db)
        assert job.db is db
        assert job.registry_service is not None
        assert job.logger is not None


class TestModelSyncJobRun:
    def _job(self):
        db = MagicMock()
        with patch("core.llm.registry.sync_job.LLMRegistryService") as lrs:
            job = ModelSyncJob(db)
            job.registry_service = MagicMock()
            return job, db, lrs

    async def test_run_skips_when_not_needed(self):
        job, db, _ = self._job()
        with patch.object(ModelSyncJob, "should_sync", return_value=False):
            result = await job.run("tenant-1")
        assert result["success"] is True
        assert result["models_fetched"] == 0
        assert "sync_timestamp" in result
        assert result["duration_seconds"] >= 0
        job.registry_service.fetch_and_store.assert_not_called()

    async def test_run_full_flow(self):
        job, db, _ = self._job()
        job.registry_service.fetch_and_store = AsyncMock(
            return_value={"total": 10, "created": 4, "updated": 5, "failed": 1}
        )
        with patch.object(ModelSyncJob, "should_sync", return_value=True):
            result = await job.run("tenant-1")
        assert result["success"] is True
        assert result["models_fetched"] == 10
        assert result["created"] == 4
        assert result["updated"] == 5
        assert result["failed"] == 1
        assert result["error"] is None

    async def test_run_exception_captured(self):
        job, db, _ = self._job()
        job.registry_service.fetch_and_store = AsyncMock(side_effect=RuntimeError("fetch failed"))
        with patch.object(ModelSyncJob, "should_sync", return_value=True):
            result = await job.run("tenant-1")
        assert result["success"] is False
        assert result["error"] == "fetch failed"
        assert result["duration_seconds"] >= 0

    async def test_run_exception_during_timestamp_update(self):
        job, db, _ = self._job()
        job.registry_service.fetch_and_store = AsyncMock(return_value={"total": 1})
        job._update_sync_timestamp = MagicMock(side_effect=RuntimeError("db down"))
        with patch.object(ModelSyncJob, "should_sync", return_value=True):
            result = await job.run("tenant-1")
        assert result["success"] is False
        assert result["error"] == "db down"

    async def test_run_stats_missing_keys_default_to_zero(self):
        job, db, _ = self._job()
        job.registry_service.fetch_and_store = AsyncMock(return_value={})
        with patch.object(ModelSyncJob, "should_sync", return_value=True):
            result = await job.run("tenant-1")
        assert result["models_fetched"] == 0
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["failed"] == 0


class TestModelSyncJobTimestamp:
    def test_update_sync_timestamp_success(self):
        db = MagicMock()
        with patch("core.llm.registry.sync_job.LLMRegistryService"):
            job = ModelSyncJob(db)
        job._update_sync_timestamp("t1")
        db.commit.assert_called_once()

    def test_update_sync_timestamp_error_rolls_back_and_raises(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit failed")
        with patch("core.llm.registry.sync_job.LLMRegistryService"):
            job = ModelSyncJob(db)
        with pytest.raises(RuntimeError):
            job._update_sync_timestamp("t1")
        db.rollback.assert_called_once()

    def test_should_sync_no_rows(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        assert ModelSyncJob.should_sync("t1", db) is True

    def test_should_sync_none_timestamp(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (None,)
        assert ModelSyncJob.should_sync("t1", db) is True

    def test_should_sync_old_timestamp(self):
        db = MagicMock()
        old = datetime.now(timezone.utc) - timedelta(days=40)
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (old,)
        assert ModelSyncJob.should_sync("t1", db) is True

    def test_should_sync_recent_timestamp(self):
        db = MagicMock()
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (recent,)
        assert ModelSyncJob.should_sync("t1", db) is False

    def test_should_sync_exact_threshold(self):
        db = MagicMock()
        exact = datetime.now(timezone.utc) - timedelta(hours=720)
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (exact,)
        assert ModelSyncJob.should_sync("t1", db, interval_hours=720) is True

    def test_should_sync_custom_interval(self):
        db = MagicMock()
        ts = datetime.now(timezone.utc) - timedelta(hours=10)
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (ts,)
        assert ModelSyncJob.should_sync("t1", db, interval_hours=24) is False
        assert ModelSyncJob.should_sync("t1", db, interval_hours=8) is True

    def test_should_sync_error_fails_open(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert ModelSyncJob.should_sync("t1", db) is True


class TestRunSyncJob:
    async def test_run_sync_job_convenience(self):
        fake_db = MagicMock()
        fake_job = MagicMock()
        fake_job.run = AsyncMock(return_value={"success": True})
        with patch("core.database.SessionLocal", return_value=fake_db):
            with patch.object(sync_module, "ModelSyncJob", return_value=fake_job) as mj:
                result = await run_sync_job("tenant-9")
        assert result == {"success": True}
        mj.assert_called_once_with(fake_db)
        fake_job.run.assert_called_once_with("tenant-9")
        fake_db.close.assert_called_once()

    async def test_run_sync_job_convenience_closes_db_on_error(self):
        fake_db = MagicMock()
        fake_job = MagicMock()
        fake_job.run = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.database.SessionLocal", return_value=fake_db):
            with patch.object(sync_module, "ModelSyncJob", return_value=fake_job):
                with pytest.raises(RuntimeError):
                    await run_sync_job("tenant-9")
        fake_db.close.assert_called_once()


# --------------------------------------------------------------------------- #
# heuristic_scorer.py
# --------------------------------------------------------------------------- #
class TestHeuristicScorerInit:
    def test_defaults(self):
        scorer = HeuristicScorer()
        assert scorer.min_score == 75.0
        assert scorer.max_score == 98.0
        assert scorer.context_bonus_enabled is True
        assert scorer.version_bonus_enabled is True

    def test_overrides(self):
        scorer = HeuristicScorer(
            min_score=60.0,
            max_score=100.0,
            context_bonus_enabled=False,
            version_bonus_enabled=False,
        )
        assert scorer.min_score == 60.0
        assert scorer.max_score == 100.0
        assert scorer.context_bonus_enabled is False
        assert scorer.version_bonus_enabled is False

    def test_zero_min_uses_default(self):
        # min_score=0 is falsy -> falls back to default (documented quirk)
        scorer = HeuristicScorer(min_score=0.0, max_score=0.0)
        assert scorer.min_score == 75.0


class TestHeuristicScoring:
    def test_tier_1_keywords(self):
        for name in ["claude-3-opus", "gpt-ultra", "flagship-2"]:
            assert HeuristicScorer()._get_base_tier_score(name) == 95.0

    def test_tier_2_keywords(self):
        for name in ["claude-3-sonnet", "gpt-4-pro", "gpt-4-plus"]:
            assert HeuristicScorer()._get_base_tier_score(name) == 90.0

    def test_tier_3_keywords(self):
        for name in ["claude-haiku", "gemini-flash", "gpt-4-turbo", "gpt-4-lite"]:
            assert HeuristicScorer()._get_base_tier_score(name) == 85.0

    def test_tier_4_keywords(self):
        for name in ["gpt-4-base", "llama-small", "gpt-4-mini"]:
            assert HeuristicScorer()._get_base_tier_score(name) == 80.0

    def test_tier_5_keywords(self):
        for name in ["model-experimental", "model-preview", "alpha-1", "beta-2", "v1-rc"]:
            assert HeuristicScorer()._get_base_tier_score(name) == 70.0

    def test_no_tier_match_returns_82(self):
        assert HeuristicScorer()._get_base_tier_score("mystery-model") == 82.0

    def test_calculate_score_clamps_to_min(self):
        scorer = HeuristicScorer(min_score=90.0, max_score=98.0)
        assert scorer.calculate_score("random-model") == 90.0

    def test_calculate_score_clamps_to_max(self):
        scorer = HeuristicScorer(min_score=0.0, max_score=95.0)
        assert scorer.calculate_score("gpt-4-opus", context_window=1_000_000) == 95.0

    def test_calculate_score_full_bonuses(self):
        scorer = HeuristicScorer()
        # claude-3-opus: 95 base + 3 (v3) + 5 (200k ctx) = 103 -> clamp 98
        assert scorer.calculate_score("claude-3-opus", context_window=200_000) == 98.0

    def test_calculate_score_no_context_bonus(self):
        scorer = HeuristicScorer()
        # gpt-4: 82 base? no - gpt-4 has no tier keyword; 82 + 5 (v4) = 87
        assert scorer.calculate_score("gpt-4", context_window=None) == 87.0

    def test_context_bonus_disabled(self):
        scorer = HeuristicScorer(context_bonus_enabled=False)
        # 95 base + 3 version bonus, no context bonus, clamp to 98
        assert scorer.calculate_score("claude-3-opus", context_window=200_000) == 98.0

    def test_version_bonus_disabled(self):
        scorer = HeuristicScorer(version_bonus_enabled=False)
        assert scorer.calculate_score("gpt-4") == 82.0

    def test_version_bonus_v4(self):
        assert HeuristicScorer()._calculate_version_bonus("gpt-4") == 5.0

    def test_version_bonus_v35(self):
        assert HeuristicScorer()._calculate_version_bonus("claude-3.5-sonnet") == 4.0

    def test_version_bonus_v3(self):
        assert HeuristicScorer()._calculate_version_bonus("gemini-3-flash") == 3.0

    def test_version_bonus_v2(self):
        assert HeuristicScorer()._calculate_version_bonus("llama-2-7b") == 1.0

    def test_version_bonus_v1(self):
        assert HeuristicScorer()._calculate_version_bonus("mistral-1-small") == 0.0

    def test_version_bonus_deepseek_v_prefix(self):
        assert HeuristicScorer()._calculate_version_bonus("deepseek-v3") == 3.0

    def test_version_bonus_deepseek_no_v(self):
        assert HeuristicScorer()._calculate_version_bonus("deepseek-2") == 1.0

    def test_version_bonus_no_series_match(self):
        assert HeuristicScorer()._calculate_version_bonus("random-model-9") == 0.0

    def test_version_bonus_unparseable_version(self):
        # Series keyword present but version group is not numeric -> ValueError path
        with patch.object(
            heuristic_module.re,
            "search",
            return_value=MagicMock(group=MagicMock(return_value="not-a-version")),
        ):
            assert HeuristicScorer()._calculate_version_bonus("gpt-x") == 0.0

    def test_context_bonus_none(self):
        assert HeuristicScorer()._calculate_context_bonus(None) == 0.0

    def test_context_bonus_zero(self):
        assert HeuristicScorer()._calculate_context_bonus(0) == 0.0

    def test_context_bonus_below_all_thresholds(self):
        assert HeuristicScorer()._calculate_context_bonus(1000) == 0.0

    def test_context_bonus_128k(self):
        assert HeuristicScorer()._calculate_context_bonus(128_000) == 3.0

    def test_context_bonus_200k(self):
        assert HeuristicScorer()._calculate_context_bonus(200_000) == 5.0

    def test_context_bonus_1m(self):
        assert HeuristicScorer()._calculate_context_bonus(1_000_000) == 7.0

    def test_context_bonus_between_thresholds(self):
        assert HeuristicScorer()._calculate_context_bonus(150_000) == 3.0


class TestHeuristicTierInfo:
    def test_tier_info_match(self):
        info = HeuristicScorer().get_tier_info("claude-3-opus")
        assert info["tier"] == "tier_1"
        assert info["base_score"] == 95.0
        assert "opus" in info["keywords"]
        assert info["description"]

    def test_tier_info_unknown(self):
        info = HeuristicScorer().get_tier_info("mystery")
        assert info["tier"] == "unknown"
        assert info["base_score"] == 82.0
        assert info["keywords"] == []
        assert info["description"] == "Unknown model tier"

    def test_tier_info_case_insensitive(self):
        info = HeuristicScorer().get_tier_info("CLAUDE-3-OPUS")
        assert info["tier"] == "tier_1"

    def test_calculate_quality_score_convenience(self):
        assert calculate_quality_score("gpt-4-opus") == 98.0


# --------------------------------------------------------------------------- #
# rate_limiter.py
# --------------------------------------------------------------------------- #
class TestRateLimiter:
    @pytest.fixture
    def limiter(self):
        cache = make_cache_mock()
        return RateLimiter(cache_service=cache), cache

    def test_get_key(self, limiter):
        limiter, _ = limiter
        assert limiter._get_key("openai") == "llm_registry_rate_limit:openai"

    async def test_is_rate_limited_true(self, limiter):
        limiter, cache = limiter
        cache.get_async.return_value = "rate_limited"
        assert await limiter.is_rate_limited("openai") is True

    async def test_is_rate_limited_false(self, limiter):
        limiter, cache = limiter
        assert await limiter.is_rate_limited("openai") is False

    async def test_mark_rate_limited(self, limiter):
        limiter, cache = limiter
        await limiter.mark_rate_limited("openai", retry_after=30)
        cache.set_async.assert_called_once_with("llm_registry_rate_limit:openai", "rate_limited", 30)

    async def test_mark_rate_limited_clamped_to_ttl(self, limiter):
        limiter, cache = limiter
        await limiter.mark_rate_limited("openai", retry_after=99999)
        cache.set_async.assert_called_once_with("llm_registry_rate_limit:openai", "rate_limited", 300)

    async def test_mark_rate_limited_default(self, limiter):
        limiter, cache = limiter
        await limiter.mark_rate_limited("openai")
        cache.set_async.assert_called_once_with("llm_registry_rate_limit:openai", "rate_limited", 60)

    async def test_clear_rate_limit(self, limiter):
        limiter, cache = limiter
        await limiter.clear_rate_limit("openai")
        cache.delete_async.assert_called_once_with("llm_registry_rate_limit:openai")

    def test_init_defaults_create_cache(self):
        with patch.object(rate_module, "UniversalCacheService") as ucs:
            RateLimiter()
            assert ucs.called


class TestAPIClientWithRetry:
    @pytest.fixture
    def client(self):
        cache = make_cache_mock()
        rate_limiter = RateLimiter(cache_service=cache)
        c = APIClientWithRetry(rate_limiter=rate_limiter)
        c._client = FakeAsyncClient([])
        return c, rate_limiter

    @pytest.fixture(autouse=True)
    def no_sleeps(self):
        with patch.object(rate_module.asyncio, "sleep", new=AsyncMock()):
            yield

    async def test_init_defaults(self):
        with patch.object(rate_module, "RateLimiter") as rl:
            c = APIClientWithRetry()
            assert c.max_retries == 5
            assert c.initial_delay == 1.0
            assert c.max_delay == 60.0
            assert rl.called

    async def test_get_client_create_and_reuse(self, client):
        c, _ = client
        c._client = None
        with patch.object(rate_module.httpx, "AsyncClient") as ac:
            c1 = await c._get_client()
            c2 = await c._get_client()
            assert c1 is c2
            ac.assert_called_once()

    async def test_close_with_client(self, client):
        c, _ = client
        c._client.aclose = AsyncMock()
        await c.close()
        assert c._client is None

    async def test_close_without_client(self, client):
        c, _ = client
        c._client = None
        await c.close()

    def test_calculate_delay_with_retry_after(self, client):
        c, _ = client
        with patch.object(rate_module.random, "uniform", return_value=0.0):
            assert c._calculate_delay(0, retry_after=10) == 10.0

    def test_calculate_delay_retry_after_capped(self, client):
        c, _ = client
        with patch.object(rate_module.random, "uniform", return_value=0.0):
            assert c._calculate_delay(0, retry_after=500) == 60.0

    def test_calculate_delay_exponential(self, client):
        c, _ = client
        with patch.object(rate_module.random, "uniform", return_value=0.0):
            assert c._calculate_delay(0) == 1.0
            assert c._calculate_delay(1) == 2.0
            assert c._calculate_delay(2) == 4.0

    def test_calculate_delay_exponential_capped(self, client):
        c, _ = client
        with patch.object(rate_module.random, "uniform", return_value=0.0):
            assert c._calculate_delay(10) == 60.0

    def test_calculate_delay_jitter_applied(self, client):
        c, _ = client
        with patch.object(rate_module.random, "uniform", return_value=0.5):
            # random.uniform(-0.1, 0.1) mocked to return 0.5 -> 1.0 + 0.5 = 1.5
            assert c._calculate_delay(0) == 1.5

    def test_calculate_delay_never_negative(self, client):
        c, _ = client
        with patch.object(rate_module.random, "uniform", return_value=-100.0):
            assert c._calculate_delay(0) == 0.0

    async def test_get_success_clears_rate_limit(self, client):
        c, rl = client
        c._client.responses.append(real_http_response(200, payload={"ok": True}))
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 200
        assert await rl.is_rate_limited("p") is False

    async def test_get_404_returns_response(self, client):
        c, rl = client
        c._client.responses.append(real_http_response(404))
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 404

    async def test_get_429_with_retry_after_then_success(self, client):
        c, rl = client
        c._client.responses = [
            real_http_response(429, headers={"Retry-After": "5"}),
            real_http_response(200),
        ]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 200
        # rate limit marked then cleared
        assert await rl.is_rate_limited("p") is False

    async def test_get_429_invalid_retry_after(self, client):
        c, rl = client
        c._client.responses = [
            real_http_response(429, headers={"Retry-After": "not-an-int"}),
            real_http_response(200),
        ]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 200
        # default 60s ttl was used
        rl.cache.set_async.assert_any_call("llm_registry_rate_limit:p", "rate_limited", 60)

    async def test_get_429_max_retries_raises(self, client):
        c, rl = client
        c._client.responses = [real_http_response(429) for _ in range(6)]
        with pytest.raises(httpx.HTTPError, match="Max retries"):
            await c.get("http://u", provider="p")

    async def test_get_429_max_retries_zero(self, client):
        c, rl = client
        c.max_retries = 0
        c._client.responses = [real_http_response(429)]
        with pytest.raises(httpx.HTTPError, match="Max retries"):
            await c.get("http://u", provider="p")

    async def test_get_500_retries_then_success(self, client):
        c, rl = client
        c._client.responses = [real_http_response(500), real_http_response(200)]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 200

    async def test_get_500_at_max_retries_returns_response(self, client):
        c, rl = client
        c.max_retries = 0
        c._client.responses = [real_http_response(500)]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 500

    async def test_get_500_after_all_retries_returns_last(self, client):
        c, rl = client
        c.max_retries = 2
        c._client.responses = [real_http_response(500), real_http_response(503), real_http_response(502)]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 502

    async def test_get_timeout_retries_then_success(self, client):
        c, rl = client
        c._client.responses = [
            FakeResponse(raise_err=httpx.ConnectTimeout("t")),
            real_http_response(200),
        ]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 200

    async def test_get_network_error_retries_then_success(self, client):
        c, rl = client
        c._client.responses = [
            FakeResponse(raise_err=httpx.NetworkError("n")),
            real_http_response(200),
        ]
        resp = await c.get("http://u", provider="p")
        assert resp.status_code == 200

    async def test_get_timeout_max_retries_raises(self, client):
        c, rl = client
        c.max_retries = 1
        c._client.responses = [
            FakeResponse(raise_err=httpx.ConnectTimeout("t")),
            FakeResponse(raise_err=httpx.ConnectTimeout("t")),
        ]
        with pytest.raises(httpx.ConnectTimeout):
            await c.get("http://u", provider="p")

    async def test_get_network_error_max_retries_raises(self, client):
        c, rl = client
        c.max_retries = 0
        c._client.responses = [FakeResponse(raise_err=httpx.NetworkError("n"))]
        with pytest.raises(httpx.NetworkError):
            await c.get("http://u", provider="p")

    async def test_get_negative_max_retries_raises_immediately(self, client):
        # range(max_retries + 1) with max_retries = -1 is empty -> the
        # post-loop fallback raise is the only exit.
        c, rl = client
        c.max_retries = -1
        with pytest.raises(httpx.HTTPError, match="Max retries"):
            await c.get("http://u", provider="p")

    async def test_get_kwargs_passed_through(self, client):
        c, rl = client
        c._client = FakeAsyncClient([real_http_response(200)])
        await c.get("http://u", provider="p", headers={"X": "1"})
        assert c._client.responses == []


# --------------------------------------------------------------------------- #
# curated_overrides.py
# --------------------------------------------------------------------------- #
class TestCuratedOverridesPricingShape:
    def test_pricing_shape_float_conversion_errors_use_zero(self):
        with patch("core.llm.registry.curated_overrides.CURATED_OVERRIDES", {
            "openrouter/owl-alpha": {
                "pricing": {"prompt": "not-a-number", "completion": "also-bad"},
                "context_length": 1000,
                "name": "Owl",
                "litellm_provider": "openrouter",
            }
        }):
            priced = curated_overrides_in_pricing_shape()
            assert priced["openrouter/owl-alpha"]["input_cost_per_token"] == 0.0
            assert priced["openrouter/owl-alpha"]["output_cost_per_token"] == 0.0

    def test_pricing_shape_missing_pricing(self):
        with patch("core.llm.registry.curated_overrides.CURATED_OVERRIDES", {
            "x/y": {"context_length": 500},
        }):
            priced = curated_overrides_in_pricing_shape()
            assert priced["x/y"]["input_cost_per_token"] == 0.0
            assert priced["x/y"]["max_tokens"] == 500
            assert priced["x/y"]["name"] == "x/y"

    def test_pricing_shape_no_context_falls_back_to_max_tokens(self):
        with patch("core.llm.registry.curated_overrides.CURATED_OVERRIDES", {
            "x/y": {"max_tokens": 777},
        }):
            priced = curated_overrides_in_pricing_shape()
            assert priced["x/y"]["max_tokens"] == 777

    def test_pricing_shape_no_context_at_all_zero(self):
        with patch("core.llm.registry.curated_overrides.CURATED_OVERRIDES", {
            "x/y": {},
        }):
            priced = curated_overrides_in_pricing_shape()
            assert priced["x/y"]["max_tokens"] == 0

    def test_pricing_shape_float_values_parsed(self):
        with patch("core.llm.registry.curated_overrides.CURATED_OVERRIDES", {
            "x/y": {"pricing": {"prompt": "0.0005", "completion": "0.001"}, "context_length": 100},
        }):
            priced = curated_overrides_in_pricing_shape()
            assert priced["x/y"]["input_cost_per_token"] == 0.0005
            assert priced["x/y"]["output_cost_per_token"] == 0.001

    def test_apply_to_pricing_adds_when_absent(self):
        upstream = {"a/b": {"input_cost_per_token": 1.0}}
        result = apply_curated_overrides_to_pricing(upstream)
        assert "a/b" in result
        assert "openrouter/owl-alpha" in result
        assert result["a/b"]["input_cost_per_token"] == 1.0

    def test_apply_to_pricing_does_not_override_on_collision(self):
        upstream = {"openrouter/owl-alpha": {"input_cost_per_token": 9.9, "name": "UPSTREAM"}}
        result = apply_curated_overrides_to_pricing(upstream)
        assert result["openrouter/owl-alpha"]["name"] == "UPSTREAM"
        assert result["openrouter/owl-alpha"]["input_cost_per_token"] == 9.9

    def test_apply_curated_overrides_adds_when_absent(self):
        upstream = {"a/b": {"id": "a/b"}}
        result = apply_curated_overrides(upstream)
        assert "openrouter/owl-alpha" in result
        assert "a/b" in result

    def test_apply_curated_overrides_does_not_override_on_collision(self):
        upstream = {"openrouter/owl-alpha": {"id": "openrouter/owl-alpha", "name": "UPSTREAM"}}
        result = apply_curated_overrides(upstream)
        assert result["openrouter/owl-alpha"]["name"] == "UPSTREAM"

    def test_apply_curated_overrides_empty_upstream(self):
        result = apply_curated_overrides({})
        assert result == dict(CURATED_OVERRIDES)

    def test_apply_curated_overrides_non_dict_upstream(self):
        for bad in (None, [], "string", 42):
            result = apply_curated_overrides(bad)  # type: ignore[arg-type]
            assert result == dict(CURATED_OVERRIDES)

    def test_apply_to_pricing_non_dict_upstream(self):
        for bad in (None, [], "string", 42):
            result = apply_curated_overrides_to_pricing(bad)  # type: ignore[arg-type]
            assert "openrouter/owl-alpha" in result

    def test_curated_overrides_structure(self):
        assert CURATED_OVERRIDES["openrouter/owl-alpha"]["curated"] is True
        assert CURATED_OVERRIDES["openrouter/owl-alpha"]["litellm_provider"] == "openrouter"
        assert CURATED_OVERRIDES["openrouter/owl-alpha"]["max_tokens"] == 32_000
