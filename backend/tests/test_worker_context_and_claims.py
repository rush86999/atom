"""Worker context propagation and claim-generation ownership controls.

The structured/text provider calls run synchronous clients in a worker pool.
Two invariants are load-bearing:

1. Each submission runs in a COPY of the caller's ContextVars. Concurrent
   jobs must not share one Context, and worker-local changes must not leak
   back or sideways.
2. A claim is an opaque generation. A worker whose lease expired may finish
   late, but it must not release or extend a newer worker's reservation.
"""
from __future__ import annotations

import contextvars
import asyncio
import threading
import time

import pytest

import core.llm.byok_handler as bh


@pytest.mark.asyncio
async def test_thread_bridge_preserves_callers_context():
    scope = contextvars.ContextVar("verifier_scope", default="missing")
    token = scope.set("workspace-a:trace-17")
    try:
        observed = await bh._to_thread_safe(scope.get)
    finally:
        scope.reset(token)
    assert observed == "workspace-a:trace-17"


@pytest.mark.asyncio
async def test_thread_bridge_isolates_concurrent_callers():
    scope = contextvars.ContextVar("concurrent_scope", default="missing")

    async def run(value: str) -> str:
        token = scope.set(value)
        try:
            await asyncio.sleep(0)
            return await bh._to_thread_safe(scope.get)
        finally:
            scope.reset(token)

    results = await asyncio.gather(run("workspace-a"), run("workspace-b"))
    assert results == ["workspace-a", "workspace-b"]


@pytest.mark.asyncio
async def test_worker_context_changes_do_not_leak_back_or_sideways():
    scope = contextvars.ContextVar("mutating_scope", default="caller")

    def mutate_once() -> str:
        scope.set("worker-only")
        return scope.get()

    assert await bh._to_thread_safe(mutate_once) == "worker-only"
    assert scope.get() == "caller"
    # A second worker gets a fresh copy of the caller's context, not the
    # first worker's mutation.
    assert await bh._to_thread_safe(scope.get) == "caller"


def _handler():
    return bh.BYOKHandler.__new__(bh.BYOKHandler)


def _clear_claim(provider: str, model: str) -> None:
    pair = f"{provider}/{model}"
    with bh._MODEL_ATTEMPT_INFLIGHT_LOCK:
        bh._MODEL_ATTEMPT_INFLIGHT.pop(pair, None)
        bh._MODEL_ATTEMPT_HOLDERS.pop(pair, None)
        bh._MODEL_ATTEMPT_TOKENS.pop(pair, None)
        bh._MODEL_ATTEMPT_EXPIRY.pop(pair, None)


def test_claim_token_binds_release_to_one_generation():
    handler = _handler()
    provider, model = "verifier-token", "worker-model"
    try:
        token_a = handler._claim_model_attempt(
            provider, model, holder="worker-A")
        assert token_a
        assert handler._claim_model_attempt(
            provider, model, holder="worker-B") is False
        assert handler._release_model_attempt(
            provider, model, holder="worker-B", token="wrong-token") is False
        assert handler._release_model_attempt(
            provider, model, holder="worker-A", token=token_a) is True
        assert handler._release_model_attempt(
            provider, model, holder="worker-A", token=token_a) is False
    finally:
        _clear_claim(provider, model)


def test_expired_worker_cannot_release_a_newer_claim():
    handler = _handler()
    provider, model = "verifier-owner", "worker-model"
    pair = f"{provider}/{model}"
    try:
        token_a = handler._claim_model_attempt(
            provider, model, holder="worker-A")
        assert token_a
        # The verifier's supported bounded-lease recovery path.
        with bh._MODEL_ATTEMPT_INFLIGHT_LOCK:
            bh._MODEL_ATTEMPT_INFLIGHT[pair] = (
                time.time() - bh._MODEL_ATTEMPT_INFLIGHT_TTL_SECONDS - 1)
        token_b = handler._claim_model_attempt(
            provider, model, holder="worker-B")
        assert token_b and token_b != token_a
        # A's late cleanup must not pop B's generation.
        assert handler._release_model_attempt(
            provider, model, holder="worker-A") is False
        assert handler._release_model_attempt(
            provider, model, token=token_a) is False
        assert bh._MODEL_ATTEMPT_HOLDERS[pair][0] == "worker-B"
        assert handler._claim_model_attempt(
            provider, model, holder="worker-C") is False
        assert handler._release_model_attempt(
            provider, model, holder="worker-B", token=token_b) is True
    finally:
        _clear_claim(provider, model)


def test_stale_retain_cannot_extend_a_newer_claim():
    handler = _handler()
    provider, model = "verifier-retain", "worker-model"
    pair = f"{provider}/{model}"
    try:
        token_a = handler._claim_model_attempt(
            provider, model, holder="worker-A")
        assert token_a
        with bh._MODEL_ATTEMPT_INFLIGHT_LOCK:
            bh._MODEL_ATTEMPT_INFLIGHT[pair] = (
                time.time() - bh._MODEL_ATTEMPT_INFLIGHT_TTL_SECONDS - 1)
        token_b = handler._claim_model_attempt(
            provider, model, holder="worker-B")
        assert token_b
        before = bh._MODEL_ATTEMPT_EXPIRY[pair]
        assert handler._retain_model_attempt(
            provider, model, 9999, token=token_a) is False
        assert handler._retain_model_attempt(
            provider, model, 9999, holder="worker-A") is False
        assert bh._MODEL_ATTEMPT_EXPIRY[pair] == before
        assert handler._claim_model_attempt(
            provider, model, holder="worker-C") is False
    finally:
        _clear_claim(provider, model)


def test_retain_lease_longer_than_ttl_uses_explicit_expiry():
    handler = _handler()
    provider, model = "verifier-lease", "worker-model"
    pair = f"{provider}/{model}"
    try:
        token = handler._claim_model_attempt(
            provider, model, holder="worker-A")
        assert token
        assert handler._retain_model_attempt(
            provider, model,
            bh._MODEL_ATTEMPT_INFLIGHT_TTL_SECONDS * 2,
            token=token, holder="worker-A") is True
        remaining = bh._MODEL_ATTEMPT_EXPIRY[pair] - time.time()
        assert remaining > bh._MODEL_ATTEMPT_INFLIGHT_TTL_SECONDS
        assert handler._claim_model_attempt(
            provider, model, holder="worker-B") is False
    finally:
        _clear_claim(provider, model)


def test_release_is_idempotent_and_never_resurrects_a_claim():
    handler = _handler()
    provider, model = "verifier-idempotent", "worker-model"
    try:
        token_a = handler._claim_model_attempt(
            provider, model, holder="worker-A")
        assert token_a
        assert handler._release_model_attempt(
            provider, model, holder="worker-A", token=token_a) is True
        assert handler._release_model_attempt(
            provider, model, holder="worker-A", token=token_a) is False
        token_b = handler._claim_model_attempt(
            provider, model, holder="worker-B")
        assert token_b and token_b != token_a
        assert handler._release_model_attempt(
            provider, model, holder="worker-A", token=token_a) is False
        assert handler._claim_model_attempt(
            provider, model, holder="worker-C") is False
        assert handler._release_model_attempt(
            provider, model, holder="worker-B", token=token_b) is True
    finally:
        _clear_claim(provider, model)


@pytest.mark.asyncio
async def test_worker_exception_propagates_and_cleanup_runs_once():
    done = threading.Event()

    def boom() -> None:
        raise ValueError("controlled worker failure")

    with pytest.raises(ValueError, match="controlled worker failure"):
        await bh._to_thread_safe(boom, on_worker_done=done.set)
    assert done.wait(2.0)
    # A second call still works after a synchronous worker exception.
    assert await bh._to_thread_safe(lambda: "ok") == "ok"


@pytest.mark.asyncio
async def test_cancelled_worker_cleanup_runs_on_real_exit_not_cancellation():
    started = threading.Event()
    release = threading.Event()
    done = threading.Event()

    def blocked() -> str:
        started.set()
        release.wait(5.0)
        return "finished"

    task = asyncio.create_task(
        bh._to_thread_safe(blocked, on_worker_done=done.set))
    for _ in range(3000):
        if started.is_set():
            break
        await asyncio.sleep(0.01)
    assert started.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not done.is_set(), "cleanup must wait for the real worker exit"
    release.set()
    assert done.wait(5.0), "cleanup must run when the worker really exits"
