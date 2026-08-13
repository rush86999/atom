# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/canvas_presentation_summary (summary gen, empty
canvas, truncation).

CanvasPresentationSummaryService tested with the LLM service and cache fully
mocked (zero LLM spend):

- _get_cache_key / _hash_canvas_state: key shape, deterministic SHA256 hash,
  order-insensitive JSON serialization.
- generate_presentation_summary: async cache hit, sync cache hit, cache
  miss → LLM generation + async/sync cache set, cache get/set failures
  (warning + fall-through), LLM failure → fallback summary, empty LLM
  response, unknown canvas type → generic prompt, empty canvas state.
"""
import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.canvas_presentation_summary import (
    CANVAS_PROMPTS, CanvasPresentationSummaryService,
)


@pytest.fixture()
def service():
    with patch("core.service_factory.ServiceFactory.get_llm_service",
               return_value=MagicMock()):
        return CanvasPresentationSummaryService(db=MagicMock())


# ---------------------------------------------------------------------------
# cache key / state hash
# ---------------------------------------------------------------------------

def test_get_cache_key_shape(service):
    key = service._get_cache_key("canvas-1", "sheets", "deadbeef")
    assert key == "canvas:summary:canvas-1:sheets:deadbeef"


def test_hash_canvas_state_deterministic_and_order_insensitive(service):
    h1 = service._hash_canvas_state({"a": 1, "b": 2})
    h2 = service._hash_canvas_state({"b": 2, "a": 1})
    h3 = service._hash_canvas_state({"a": 1, "b": 3})
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)


# ---------------------------------------------------------------------------
# generate_presentation_summary — cache paths
# ---------------------------------------------------------------------------

def test_async_cache_hit_skips_llm(service):
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value="cached summary")
    fake_cache.set = AsyncMock()
    service.llm.generate_response = AsyncMock(return_value="should not run")
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {"data": [1, 2]}, tenant_id="t1"
        ))
    assert result == "cached summary"
    service.llm.generate_response.assert_not_awaited()


def test_sync_cache_hit_skips_llm(service):
    fake_cache = MagicMock()
    fake_cache.get.return_value = "sync cached"
    fake_cache.set.return_value = None
    service.llm.generate_response = AsyncMock(return_value="should not run")
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {"data": [1, 2]}, tenant_id="t1"
        ))
    assert result == "sync cached"
    service.llm.generate_response.assert_not_awaited()


def test_cache_get_failure_warns_and_falls_through(service, caplog):
    import logging
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(side_effect=RuntimeError("redis down"))
    fake_cache.set = AsyncMock()
    service.llm.generate_response = AsyncMock(return_value="llm summary")
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        with caplog.at_level(logging.WARNING, logger="core.canvas_presentation_summary"):
            result = asyncio.run(service.generate_presentation_summary(
                "c1", "sheets", {"data": [1, 2]}, tenant_id="t1"
            ))
    assert result == "llm summary"
    assert "Cache get failed" in caplog.text
    service.llm.generate_response.assert_awaited_once()


def test_no_cache_module_available(service):
    service.llm.generate_response = AsyncMock(return_value="no cache summary")
    with patch("builtins.__import__", side_effect=_import_raiser("core.cache")):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {"data": [1, 2]}, tenant_id="t1"
        ))
    assert result == "no cache summary"


def test_use_cache_false_skips_cache(service):
    service.llm.generate_response = AsyncMock(return_value="fresh")
    fake_cache = MagicMock()
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {}, tenant_id="t1", use_cache=False
        ))
    assert result == "fresh"
    fake_cache.get.assert_not_called()


# ---------------------------------------------------------------------------
# generate_presentation_summary — LLM paths
# ---------------------------------------------------------------------------

def test_llm_generation_and_async_cache_set(service):
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=None)
    fake_cache.set = AsyncMock()
    service.llm.generate_response = AsyncMock(return_value="  The user is reconciling invoices.  ")
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {"rows": 10}, tenant_id="t1"
        ))
    assert result == "The user is reconciling invoices."
    # LLM called with the sheets prompt + state
    _, kwargs = service.llm.generate_response.await_args
    assert kwargs["tenant_id"] == "t1"
    assert kwargs["max_tokens"] == 150
    user_msg = kwargs["messages"][1]["content"]
    assert "Analyze this spreadsheet canvas" in user_msg
    assert '"rows": 10' in user_msg
    # cached with 1h TTL
    fake_cache.set.assert_awaited_once()
    args = fake_cache.set.await_args
    assert args.args[1] == "The user is reconciling invoices."
    assert args.kwargs.get("expire") == 3600


def test_llm_generation_sync_cache_set(service):
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=None)
    fake_cache.set = MagicMock(return_value=None)
    service.llm.generate_response = AsyncMock(return_value="sync set summary")
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {}, tenant_id="t1"
        ))
    assert result == "sync set summary"
    fake_cache.set.assert_called_once()


def test_llm_generation_cache_set_failure_warns(service, caplog):
    import logging
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=None)
    fake_cache.set = AsyncMock(side_effect=RuntimeError("set failed"))
    service.llm.generate_response = AsyncMock(return_value="summary still returned")
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        with caplog.at_level(logging.WARNING, logger="core.canvas_presentation_summary"):
            result = asyncio.run(service.generate_presentation_summary(
                "c1", "sheets", {}, tenant_id="t1"
            ))
    assert result == "summary still returned"
    assert "Cache set failed" in caplog.text


def test_llm_failure_falls_back_to_generic_summary(service, caplog):
    import logging
    service.llm.generate_response = AsyncMock(side_effect=RuntimeError("llm outage"))
    with patch("builtins.__import__", side_effect=_import_raiser("core.cache")):
        with caplog.at_level(logging.ERROR, logger="core.canvas_presentation_summary"):
            result = asyncio.run(service.generate_presentation_summary(
                "c1", "terminal", {"pwd": "/home"}, tenant_id="t1"
            ))
    assert result == "Terminal canvas with 1 state elements"
    assert "Failed to generate LLM summary" in caplog.text


def test_llm_empty_response_not_cached(service):
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=None)
    fake_cache.set = AsyncMock()
    service.llm.generate_response = AsyncMock(return_value=None)
    with patch.dict(sys.modules, _cache_module(fake_cache)):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "sheets", {}, tenant_id="t1"
        ))
    assert result == ""
    fake_cache.set.assert_not_called()


def test_unknown_canvas_type_uses_generic_prompt(service):
    service.llm.generate_response = AsyncMock(return_value="generic summary")
    with patch("builtins.__import__", side_effect=_import_raiser("core.cache")):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "hologram", {}, tenant_id="t1"
        ))
    assert result == "generic summary"
    user_msg = service.llm.generate_response.await_args.kwargs["messages"][1]["content"]
    assert "Analyze this canvas" in user_msg  # generic prompt


def test_empty_canvas_state_generates_summary(service):
    service.llm.generate_response = AsyncMock(return_value="Empty canvas")
    with patch("builtins.__import__", side_effect=_import_raiser("core.cache")):
        result = asyncio.run(service.generate_presentation_summary(
            "c1", "docs", {}, tenant_id="t1"
        ))
    assert result == "Empty canvas"


def test_all_prompt_keys_present():
    for expected in ("terminal", "desktop", "docs", "sheets", "email",
                     "integration", "browser", "generic"):
        assert expected in CANVAS_PROMPTS


def _cache_module(fake_cache):
    mod = ModuleType("core.cache")
    mod.cache = fake_cache
    return {"core.cache": mod}


def _import_raiser(blocked):
    real_import = __import__

    def _raiser(name, *a, **k):
        if name == blocked or name.startswith(blocked + "."):
            raise ImportError(f"No module named {blocked}")
        return real_import(name, *a, **k)

    return _raiser
