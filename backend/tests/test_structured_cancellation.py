# -*- coding: utf-8 -*-
"""Cancellation semantics of the structured dispatch.

The structured attempt runs a SYNCHRONOUS Instructor client in a worker
thread. Cancelling the awaiting task does not cancel the worker. The
single-flight reservation must therefore belong to the WORKER's real
future, not to the cancelled awaiter:

  1. cancellation is logged as its own event
     ([structured-cancelled], reservation_released=false,
     cleanup_on_worker_exit=true);
  2. the worker is STILL RUNNING after the awaiter is cancelled;
  3. the reservation is STILL HELD while the worker runs, so a second
     boundary cannot overlap provider work;
  4. when the worker really exits, cleanup releases the reservation once
     and a later boundary can dispatch.

Demonstrated with a controlled blocking client (model-independent), on
a TEST-OWNED pricing fetcher and a deterministically forced route.
Blocking workers are ALWAYS released in a finally.
"""
import os
os.environ.setdefault("TESTING", "1")

import asyncio
import logging
import threading
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace as NS

import core.llm.byok_handler as bh
from core.chat_canvas_editor import CanvasEditPlan

LOCAL_PROVIDER = "local_cancel"
LOCAL_MODEL = "llama3.1:8b"


class _TestFetch:
    """A test-OWNED pricing fetcher: nothing shared with other files."""

    def __init__(self):
        self.pricing_cache = {}
        self.last_fetch = 1.0

    def get_model_capabilities(self, model_id):
        return {"supports_tools": True, "supports_vision": False,
                "supports_reasoning": False}

    def record_stale_consideration(self, *args, **kwargs):
        pass


class _BlockingWrapper:
    """The Instructor stand-in: create() blocks until released,
    counting entries. ALWAYS release in finally."""

    def __init__(self):
        self.lock = threading.Lock()
        self.started = 0
        self.finished = 0
        self.last_kwargs = {}
        self.release = threading.Event()

    def as_instructor(self):
        wrapper = self

        def create(**kwargs):
            with wrapper.lock:
                wrapper.started += 1
                wrapper.last_kwargs = dict(kwargs)
            wrapper.release.wait(timeout=60)
            plan = CanvasEditPlan(
                wants_edit=True,
                updated_content_json='"Valid until: 2026-12-31"')
            with wrapper.lock:
                wrapper.finished += 1
            return plan

        return NS(chat=NS(completions=NS(create=create)))


@pytest.fixture
def isolated_env(monkeypatch):
    test_fetch = _TestFetch()
    monkeypatch.setattr(
        bh, "get_pricing_fetcher_initialized_sync",
        lambda auto_refresh=True, force_refresh=False: test_fetch)
    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: test_fetch)
    handler = bh.BYOKHandler(workspace_id="ws-cancel",
                             tenant_id="tenant-cancel", provider_id="auto")
    monkeypatch.setattr(handler, "pricing_fetcher", test_fetch,
                        raising=False)
    monkeypatch.setattr(handler, "_load_local_providers", lambda: None)
    handler.clients[LOCAL_PROVIDER] = MagicMock()
    handler._local_routes[LOCAL_MODEL] = {
        "provider_key": LOCAL_PROVIDER,
        "workspace_id": "ws-cancel",
        "provider_id": "prov-cancel",
        "provider_type": "ollama",
        "supports_tools": True,
        "supports_vision": False,
        "supports_reasoning": False,
        "quality_score": 0.9,
        "context_window": 131072,
    }
    return handler


@pytest.mark.asyncio
async def test_cancellation_retains_reservation_until_the_worker_exits(
        isolated_env, monkeypatch, caplog):
    import core.llm.byok_handler as _bh2

    handler = isolated_env
    wrapper = _BlockingWrapper()
    try:
        async def _forced_rank(*args, **kwargs):
            # This test is about CANCELLATION semantics, not ranking
            # correctness (the dispatch-policy file pins ranking).
            return [(LOCAL_PROVIDER, LOCAL_MODEL)]

        with patch.object(_bh2.BYOKHandler, "get_ranked_providers",
                          _forced_rank), \
             patch.object(bh.instructor, "from_openai",
                          lambda client, **k: wrapper.as_instructor()), \
             caplog.at_level(logging.WARNING,
                             logger="core.llm.byok_handler"):
            first = asyncio.create_task(
                handler.generate_structured_response(
                    prompt="update the valid until date",
                    system_instruction="You return only the requested "
                                       "JSON object.",
                    response_model=CanvasEditPlan,
                    task_type="planning",
                    route_trace_id="canvas_edit_plan:exec-cancel",
                    claim_wait_seconds=0.5,
                ))
            for _ in range(3000):
                with wrapper.lock:
                    if wrapper.started:
                        break
                await asyncio.sleep(0.01)
            assert wrapper.started == 1, (
                "the first dispatch must reach the client")

            first.cancel()
            try:
                await first
            except asyncio.CancelledError:
                pass
            cancelled = [r for r in caplog.records
                         if "[structured-cancelled]" in r.getMessage()
                         and "route=canvas_edit_plan:exec-cancel"
                         in r.getMessage()]
            assert cancelled, "cancellation must be its own logged event"
            message = cancelled[0].getMessage()
            assert "reservation_released=false" in message
            assert "cleanup_on_worker_exit=true" in message
            assert "worker_may_still_run=true" in message

            with wrapper.lock:
                assert wrapper.started == 1 and wrapper.finished == 0, (
                    "the synchronous request keeps running after the "
                    "awaiter is cancelled")

            assert handler._claim_model_attempt(
                LOCAL_PROVIDER, LOCAL_MODEL, holder="probe") is False, (
                "the reservation must stay with the running worker")

            # A second boundary cannot reach the endpoint while the first
            # worker is still running. It waits its bounded claim window,
            # then returns no structured result instead of overlapping.
            second = asyncio.create_task(
                handler.generate_structured_response(
                    prompt="update the valid until date",
                    system_instruction="You return only the requested "
                                       "JSON object.",
                    response_model=CanvasEditPlan,
                    task_type="planning",
                    route_trace_id="canvas_edit_plan:exec-second",
                    claim_wait_seconds=0.3,
                ))
            second_result = await asyncio.wait_for(second, timeout=10)
            assert second_result is None
            with wrapper.lock:
                assert wrapper.started == 1, (
                    "the second boundary overlapped the running worker")
                assert wrapper.finished == 0

            # Release the worker. Cleanup runs on its real completion, not on
            # the cancelled awaiter.
            wrapper.release.set()
            for _ in range(3000):
                with wrapper.lock:
                    if wrapper.finished:
                        break
                await asyncio.sleep(0.01)
            assert wrapper.finished == 1
            released = False
            for _ in range(3000):
                if handler._claim_model_attempt(
                        LOCAL_PROVIDER, LOCAL_MODEL, holder="probe"):
                    released = True
                    handler._release_model_attempt(
                        LOCAL_PROVIDER, LOCAL_MODEL)
                    break
                await asyncio.sleep(0.01)
            assert released, (
                "the worker completion callback must release the claim")

            third = asyncio.create_task(
                handler.generate_structured_response(
                    prompt="update the valid until date",
                    system_instruction="You return only the requested "
                                       "JSON object.",
                    response_model=CanvasEditPlan,
                    task_type="planning",
                    route_trace_id="canvas_edit_plan:exec-third",
                    claim_wait_seconds=0.5,
                ))
            for _ in range(3000):
                with wrapper.lock:
                    if wrapper.started >= 2:
                        break
                await asyncio.sleep(0.01)
            with wrapper.lock:
                assert wrapper.started == 2, (
                    "a later boundary must dispatch after real cleanup")
            third.cancel()
            try:
                await third
            except asyncio.CancelledError:
                pass
    finally:
        wrapper.release.set()
        for _ in range(3000):
            with wrapper.lock:
                if wrapper.finished >= wrapper.started:
                    break
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_capability_profile_owns_the_transport_retry_budget(
        isolated_env, monkeypatch):
    """An unprofiled legacy call keeps Instructor's historical retries; a
    capability-bound employee call sends exactly one wire attempt per outer
    dispatch so the outer deadline/retry owner is the only budget."""
    import core.llm.byok_handler as _bh2

    handler = isolated_env
    wrapper = _BlockingWrapper()
    wrapper.release.set()

    async def _forced_rank(*args, **kwargs):
        return [(LOCAL_PROVIDER, LOCAL_MODEL)]

    with patch.object(_bh2.BYOKHandler, "get_ranked_providers",
                      _forced_rank), \
         patch.object(bh.instructor, "from_openai",
                      lambda client, **k: wrapper.as_instructor()):
        await handler.generate_structured_response(
            prompt="update the valid until date",
            system_instruction="json",
            response_model=CanvasEditPlan,
            task_type="planning",
            capability_profile="employee_adaptive_planning_compact",
        )
        assert wrapper.last_kwargs.get("max_retries") == 0

        await handler.generate_structured_response(
            prompt="update the valid until date",
            system_instruction="json",
            response_model=CanvasEditPlan,
            task_type="planning",
        )
        assert "max_retries" not in wrapper.last_kwargs
