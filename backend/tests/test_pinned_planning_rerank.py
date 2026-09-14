"""End-to-end wiring for the pin-then-unpin contract (R90 follow-up).

``test_chat_canvas_editor_pin_fallback.py`` proves the CALLER issues a second,
unpinned request. This module closes the last gap: that the unpinned request
really is re-ranked instead of landing back on the same dead model.

That matters because ``provider_model`` is implemented by collapsing the
candidate list to one tuple (``options = [provider_model]``). If the unpinned
retry still ended up on the same rate-limited model, the retry would be
theatre — the 2026-09-10 incident (OpenRouter 429 on ``qwen/qwen3.7-flash``)
would recur with one wasted extra round trip.

Harness mirrors ``tests/unit/llm/test_cascade_routing.py``: a fake
``instructor`` module, an ``AwaitableResult``-wrapped ranked list, and a
mocked tenant-plan lookup, so the real routing code runs with no I/O.
"""
from __future__ import annotations

import itertools
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    """Fake ``instructor`` whose ``from_openai`` records the client it wrapped.

    ``BYOKHandler`` builds each attempt as
    ``instructor.from_openai(self.clients[provider_id])``, so the client
    identity is the ground truth for WHICH provider was selected.
    """
    fake_module = MagicMock()
    attempted: list = []

    def _from_openai(client):
        def _create(**kwargs):
            attempted.append((client, kwargs.get("model")))
            raise RuntimeError(f"provider unavailable for {kwargs.get('model')}")
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

    fake_module.from_openai.side_effect = _from_openai
    fake_module.Mode = SimpleNamespace(JSON="json")
    monkeypatch.setitem(sys.modules, "instructor", fake_module)

    from core.llm import byok_handler

    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    fake_db = MagicMock()
    paid_workspace = SimpleNamespace(tenant_id="t-1")
    paid_tenant = SimpleNamespace(id="t-1", plan_type=SimpleNamespace(value="pro"))
    fake_db.query.return_value.filter.return_value.first.side_effect = itertools.cycle(
        [paid_workspace, paid_tenant]
    )

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(byok_handler, "get_db_session", lambda: _Ctx())
    return attempted


def _make_handler(options):
    """BYOKHandler skeleton wired to two distinct fake clients."""
    from core.llm.byok_handler import AwaitableResult, BYOKHandler

    openrouter_client = MagicMock(name="openrouter-client")
    openai_client = MagicMock(name="openai-client")

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.db_session = MagicMock()
    handler.clients = {"openrouter": openrouter_client, "openai": openai_client}
    handler.async_clients = {}
    handler.governance = None
    handler._is_trial_restricted = lambda: False
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)

    handler.analyze_query_complexity = MagicMock(return_value=MagicMock(value="standard"))
    handler.get_ranked_providers = MagicMock(return_value=AwaitableResult(list(options)))
    handler.get_context_window = MagicMock(return_value=8000)
    handler.truncate_to_context = MagicMock(side_effect=lambda p, *a, **k: p)
    return handler, openrouter_client, openai_client


@pytest.fixture(autouse=True)
def _moa_off(monkeypatch):
    monkeypatch.setattr(
        "core.hallucination_config.is_frontier_model", lambda *a, **k: False
    )
    monkeypatch.setattr(
        "core.hallucination_config.get_frontier_model_for_provider",
        lambda *a, **k: "gpt-4o",
    )
    monkeypatch.setattr(
        "core.hallucination_config.is_moa_enabled", lambda *a, **k: False
    )


@pytest.mark.asyncio
async def test_pinned_attempt_uses_only_the_pinned_provider(
    monkeypatch, _fake_instructor
):
    handler, or_client, _oa_client = _make_handler(
        [("openrouter", "qwen/qwen3.7-flash"), ("openai", "gpt-4o")]
    )
    await handler.generate_structured_response(
        prompt="plan",
        system_instruction="json",
        response_model=object,
        provider_model=("openrouter", "qwen/qwen3.7-flash"),
    )

    assert _fake_instructor, "pinned call never reached a provider"
    assert all(c is or_client for c, _ in _fake_instructor), (
        "a pinned call must not try other providers"
    )


@pytest.mark.asyncio
async def test_unpinned_retry_reaches_the_ranked_alternative(
    monkeypatch, _fake_instructor
):
    """The retry must land on the OTHER provider, not the dead pinned one."""
    handler, _or_client, oa_client = _make_handler([("openai", "gpt-4o")])
    await handler.generate_structured_response(
        prompt="plan",
        system_instruction="json",
        response_model=object,
    )

    assert _fake_instructor, "unpinned call never reached a provider"
    assert any(c is oa_client for c, _ in _fake_instructor), (
        "unpinned call must route to the ranked provider"
    )
    assert all(
        m != "qwen/qwen3.7-flash" for _, m in _fake_instructor
    ), "unpinned call must not re-select the dead pinned model"
