# -*- coding: utf-8 -*-
"""Dispatch-policy controls for the structured planning path (verifier
directive, J6 round).

The free-tier managed restriction is PER ROUTE and lives in the router's
ownership classification (`_plan_applies` + `is_model_approved` in
get_ranked_providers): env-key and registered-local (`local_*`) routes
are the workspace's own and exempt; every managed (platform-billed)
route is held to the tenant plan's allowlist. A blanket pre-dispatch
return in generate_structured_response rejected a correctly ranked
workspace-owned route before any model call (J6 draft runs 1-4) and was
removed — these controls pin the policy at the dispatch boundary:

  A  registered local provider, free workspace: the workspace's OWN
     client is dispatched and a schema-valid plan comes back.
  B  no configured provider: zero dispatch, and the planning consumer
     reports truthful unavailability (CanvasPlanUnavailable).
  C  managed cloud route, free workspace: the plan allowlist still
     holds — a high-quality non-allowlisted managed route is excluded
     even when an unrelated local client is ALSO registered, an
     allowlisted value model remains eligible, and a managed-only pool
     ranks empty (zero dispatch by construction).
"""
import os
os.environ.setdefault("TESTING", "1")

import asyncio

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.llm.byok_handler import BYOKHandler
from core.chat_canvas_editor import CanvasEditPlan, plan_canvas_edit
from core.cost_config import MODEL_TIER_RESTRICTIONS

LOCAL_PROVIDER = "local_ctrl1234"
LOCAL_MODEL = "llama3.1:8b"


def _handler(workspace_id="ws-ctrl", tenant_id="tenant-ctrl") -> BYOKHandler:
    return BYOKHandler(
        workspace_id=workspace_id, tenant_id=tenant_id, provider_id="auto")


def _seed_pool(handler: BYOKHandler, monkeypatch, *,
               with_local: bool = True,
               managed_models=("gpt-4o", "gpt-4o-mini")) -> None:
    """Offline pricing pool: one workspace-owned local route plus managed
    cloud routes (gpt-4o is high-quality but NOT on the free allowlist;
    gpt-4o-mini is). No network: the fetcher's sources are emptied."""
    from core.dynamic_pricing_fetcher import get_pricing_fetcher

    if with_local:
        handler.clients[LOCAL_PROVIDER] = MagicMock()
        handler._local_routes[LOCAL_MODEL] = {
            "provider_key": LOCAL_PROVIDER,
            "workspace_id": handler.workspace_id,
            "provider_id": "prov-ctrl",
            "provider_type": "ollama",
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": False,
            "quality_score": 0.9,
            "context_window": 131072,
        }

    fetcher = get_pricing_fetcher()

    async def _empty():
        return {}

    monkeypatch.setattr(fetcher, "fetch_litellm_pricing", _empty)
    monkeypatch.setattr(fetcher, "fetch_openrouter_pricing", _empty)
    monkeypatch.setattr(fetcher, "fetch_opencode_pricing", _empty)
    fetcher.last_fetch = None
    fetcher.pricing_cache = {}
    # The initializer refreshes whenever `_pricing_initialized` is False —
    # a fresh test process would re-fetch REAL sources over this pool.
    # Mark it initialized AND bypass the initializer entirely: the seeded
    # cache below is the pool under test, immune to inter-test singleton
    # pollution.
    monkeypatch.setattr(
        "core.dynamic_pricing_fetcher._pricing_initialized", True)
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
        lambda auto_refresh=True, force_refresh=False: fetcher)
    # Ranking reloads the handler's registrations from the (empty) test
    # DB at call time, which would wipe the seeded route — keep the
    # seeded state frozen for the duration.
    monkeypatch.setattr(handler, "_load_local_providers", lambda: None)
    if with_local:
        fetcher.pricing_cache[LOCAL_MODEL] = {
            "litellm_provider": "ollama",
            "max_input_tokens": 131072,
        }
    for m in managed_models:
        fetcher.pricing_cache[m] = {
            "litellm_provider": "openai",
            "max_input_tokens": 128000,
            "supports_tools": True,
        }
    # Managed pool choice: gpt-4o (quality 90) is NOT on the free
    # allowlist; gpt-4o-mini (quality 85) IS. Both clear the 85 quality
    # floor and both are genuine OpenAI catalog models, so plan gating
    # is the only filter difference the control measures.
    # The cache must stay NON-empty: the ranking initializer refreshes
    # (from real sources) whenever it finds it empty — a refresh would
    # replace this seeded pool. Non-empty cache -> needs_init False.


def _rank_structured(handler: BYOKHandler):
    # SIMPLE complexity explicitly: its 85 quality floor keeps BOTH
    # managed seeds eligible (gpt-4o 90, deepseek-v4-flash 88), so plan
    # gating is the only filter difference the control measures.
    from core.llm.byok_handler import QueryComplexity

    return handler.get_ranked_providers(
        QueryComplexity.SIMPLE,
        task_type="planning",
        tenant_plan="free",
        is_managed_service=True,
        requires_structured=True,
    )


class TestControlCManagedRestrictedPerRoute:
    """Free workspace: managed routes are plan-gated per route; the
    workspace's own local route is exempt — in the SAME pool."""

    def test_managed_nonallowlisted_excluded_local_exempt(self,
                                                          monkeypatch):
        handler = _handler()
        _seed_pool(handler, monkeypatch, with_local=True)
        from types import SimpleNamespace as NS

        # The workspace ALSO holds a BYOK openai key: the managed routes
        # enumerate (candidates require a client) and the plan allowlist
        # — not client presence — decides their eligibility. The
        # provider's DISCOVERED catalogue is recorded so route
        # reconciliation knows openai serves these identifiers (an empty
        # catalog would exclude them for availability, which is a
        # different gate than the one under test).
        _openai_client = MagicMock()
        # discover_provider_models reads models.list().data as a list of
        # {"id": ...} dicts — give it real shapes, not Mocks.
        _openai_client.models.list.return_value = NS(data=[
            {"id": "gpt-4o"}, {"id": "gpt-4o-mini"}])
        handler.clients["openai"] = _openai_client
        from core.llm.model_route_registry import (
            discover_provider_models,
            get_provider_model_catalog,
        )

        catalog = get_provider_model_catalog()
        ids, err = discover_provider_models(handler.clients["openai"],
                                            "openai")
        assert ids, f"discovery must succeed for the catalog seed: {err}"
        catalog.record_discovery("openai", ids)
        ranked = _rank_structured(handler)
        pairs = [(p, m) for p, m in ranked]
        assert (LOCAL_PROVIDER, LOCAL_MODEL) in pairs, (
            f"the workspace's own route must rank; got {pairs}")
        assert ("openai", "gpt-4o") not in pairs, (
            "the high-quality NON-allowlisted managed route must stay "
            f"plan-restricted on a free workspace; got {pairs}")
        assert ("openai", "gpt-4o-mini") in pairs, (
            "the allowlisted value model must remain eligible — the "
            f"restriction is per route, not a blanket ban; got {pairs}")

    def test_managed_nonallowlisted_excluded_without_local(self,
                                                           monkeypatch):
        """Same exclusion with NO local client registered — the managed
        restriction does not depend on the local route's presence.
        Disclosed pre-existing behavior (out of scope here): when the
        gated pool empties entirely, ranking's LEGACY static-default
        fallback may append unrelated default pairs; this control pins
        the SEEDED managed route's exclusion, which is the per-route
        policy under test."""
        handler = _handler()
        _seed_pool(handler, monkeypatch, with_local=False,
                   managed_models=("gpt-4o",))
        pairs = [(p, m) for p, m in _rank_structured(handler)]
        assert ("openai", "gpt-4o") not in pairs, (
            f"the non-allowlisted managed route must stay excluded on a "
            f"free workspace with no local client; got {pairs}")


class TestControlALocalReachesEndpoint:
    @pytest.mark.asyncio
    async def test_structured_dispatch_reaches_the_workspace_client(
            self, monkeypatch):
        """Free workspace, mixed pool: the ONLY dispatch goes to the
        workspace's own local client, and a schema-valid plan comes
        back through the structured call."""
        from types import SimpleNamespace as NS

        import core.llm.byok_handler as bh

        handler = _handler()
        _seed_pool(handler, monkeypatch, with_local=True)
        # Managed candidates have no client in THIS handler — the attempt
        # loop skips them; the local route is the only dispatchable one.

        plan = CanvasEditPlan(
            wants_edit=True,
            updated_content_json='"Valid until: 2026-12-31"')
        create = MagicMock(return_value=plan)

        def _fake_from_openai(client, **kwargs):
            return NS(chat=NS(completions=NS(create=create)))

        with patch.object(bh.instructor, "from_openai", _fake_from_openai):
            out = await handler.generate_structured_response(
                prompt="update the valid until date",
                system_instruction="You return only the requested JSON object.",
                response_model=CanvasEditPlan,
                task_type="planning",
            )
        assert isinstance(out, CanvasEditPlan) and out.wants_edit is True, (
            f"a schema-valid plan must come back; got {out!r}")
        assert create.called, (
            "the dispatch must reach the workspace's own client")
        model_used = (create.call_args.kwargs or {}).get("model") or (
            create.call_args.args and create.call_args.args[0])
        assert LOCAL_MODEL in str(model_used), (
            f"the dispatch must target the registered local route; "
            f"got {model_used!r}")


class TestControlBNoProviderNoDispatch:
    def test_zero_configured_providers_returns_none(self, monkeypatch):
        """No clients, no routes: generate_structured_response returns
        None at the availability gate — zero dispatch, no exception."""
        handler = _handler()
        handler.clients = {}
        handler.async_clients = {}
        handler._local_routes = {}
        _seed_pool(handler, monkeypatch, with_local=False,
                   managed_models=("gpt-4o",))
        import asyncio

        out = asyncio.run(handler.generate_structured_response(
            prompt="update the quote",
            system_instruction="You return only the requested JSON object.",
            response_model=CanvasEditPlan,
            task_type="planning",
        ))
        assert out is None

    @pytest.mark.asyncio
    async def test_planner_reports_truthful_unavailability(self):
        """The planning consumer converts a None into CanvasPlanUnavailable
        — the honest 'couldn't complete' contract, never a silent pass."""
        llm = MagicMock()
        llm.generate_structured_response = AsyncMockNone()

        with pytest.raises(Exception) as ei:
            await plan_canvas_edit(
                "update the valid until date", [], {
                    "canvas_id": "c-1", "canvas_type": "document",
                    "title": "Q", "content": "x",
                }, llm)
        assert "provider failure" in str(ei.value)


class AsyncMockNone:
    """Awaitable that resolves to None (the every-provider-failed shape)."""

    def __call__(self, *args, **kwargs):
        import asyncio

        fut = asyncio.get_event_loop().create_future()
        fut.set_result(None)
        return fut

    def __await__(self):
        import asyncio

        return self.__call__().__await__() if False else _await_none()


async def _await_none():
    return None


def test_malformed_native_payload_settles_nothing(monkeypatch):
    """Valid JSON is not a valid plan: a wrong-typed payload through
    the real instructor path (mock HTTP transport) exhausts the cascade
    and returns None — no partial write, no certified completion."""
    import httpx
    import openai
    import core.llm.byok_handler as bh

    handler = _handler()
    _seed_pool(handler, monkeypatch, with_local=True)
    # This control intentionally forces a connection failure. Keep that
    # failure inside a test-local health monitor: the process-global monitor
    # would otherwise open the circuit breaker for the local route and leak
    # an empty candidate pool into every later ranking test in the same run.
    from core.provider_health_monitor import ProviderHealthMonitor

    handler.health_monitor = ProviderHealthMonitor()

    def _malformed_response(request: httpx.Request) -> httpx.Response:
        body = {
            "id": "chatcmpl-bad", "object": "chat.completion",
            "created": 1, "model": MODEL,
            "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content":
                            '{"ops": {"find": 42}, '
                            '"wants_edit": "yes"}'},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(_malformed_response)
    real_client = openai.OpenAI(
        base_url="http://localhost:11434/v1", api_key="ollama",
        http_client=httpx.Client(transport=transport))
    handler.clients[LOCAL_PROVIDER] = real_client

    out = asyncio.run(handler.generate_structured_response(
        prompt="update the valid until date",
        system_instruction="You return only the requested JSON object.",
        response_model=CanvasEditPlan,
        task_type="planning",
        route_trace_id="diagnostic_minimal:bad",
    ))
    assert out is None
    # TEARDOWN: clear what the failed run taught the in-memory memos,
    # so this pin teaches nothing forward.
    bh._STRUCTURED_PROTOCOL_UNSUPPORTED.discard(
        f"{LOCAL_PROVIDER}/{LOCAL_MODEL}")
    bh._AUTH_FAILED.discard(f"{LOCAL_PROVIDER}/{LOCAL_MODEL}")
    bh._REASONING_MANDATORY.discard(f"{LOCAL_PROVIDER}/{LOCAL_MODEL}")
