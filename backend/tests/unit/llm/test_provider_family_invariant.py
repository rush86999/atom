"""Workstream D — provider-family invariant tests.

These tests make the existing structural invariant an explicit, enforced
property: within a single logical call, the provider family never
changes. The revised Phase 2 design (see
.planning/HALLUCINATION_MITIGATION_PHASE2_REVISION.md) puts cascade
inside BYOKHandler, so the invariant is structural — but these tests
catch future regressions if someone re-introduces cross-provider
escalation.
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_mitigation_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ATOM_") and (
            "VERIFIED" in k or "CASCADE" in k or "SELF_CONSISTENCY" in k
        ):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    fake_module = MagicMock()
    fake_client = MagicMock()
    fake_module.from_openai.return_value = fake_client
    monkeypatch.setitem(sys.modules, "instructor", fake_module)
    from core.llm import byok_handler

    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    # Stub the tenant-plan DB lookup (same as test_cascade_routing).
    fake_db = MagicMock()
    paid_workspace = SimpleNamespace(tenant_id="t-1")
    paid_tenant = SimpleNamespace(plan_type=SimpleNamespace(value="pro"))
    fake_db.query.return_value.filter.return_value.first.side_effect = [
        paid_workspace,
        paid_tenant,
    ]

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(byok_handler, "get_db_session", lambda: _Ctx())
    yield fake_client


# ---------------------------------------------------------------------------
# D1: cascade inside BYOKHandler stays in the same provider family
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_D1_generate_structured_keeps_provider_family_within_task(_fake_instructor):
    """A schema failure on an OpenAI model escalates to an OpenAI flagship.

    The escalation MUST NOT cross to Anthropic / DeepSeek / etc. — BYOK
    credentials, cost tracking, and rate limits are per-provider, and the
    caller has only authorized the provider that resolved the original
    call.
    """
    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.db_session = MagicMock()
    # Only OpenAI is configured.
    handler.clients = {"openai": MagicMock()}
    handler.governance = None
    handler._is_trial_restricted = lambda: False
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler.analyze_query_complexity = MagicMock(return_value=MagicMock(value="standard"))
    handler.get_ranked_providers = MagicMock(return_value=[("openai", "gpt-4o-mini")])
    handler.get_context_window = MagicMock(return_value=8000)
    handler.truncate_to_context = MagicMock(side_effect=lambda p, *a, **k: p)

    seen_providers: list[str] = []

    class _SpyDict(dict):
        """Records direct ``d[key]`` access (upstream's pattern)."""

        def __getitem__(self, key):
            seen_providers.append(key)
            return super().__getitem__(key)

    openai_client = handler.clients["openai"]
    handler.clients = _SpyDict({"openai": openai_client})

    def fake_create(**kwargs):
        model = kwargs.get("model", "")
        if "mini" in model:
            raise json.JSONDecodeError("schema fail", "doc", 0)
        return SimpleNamespace(_raw_response=None)

    _fake_instructor.chat.completions.create = fake_create

    with patch(
        "core.hallucination_config.is_frontier_model", return_value=False
    ), patch(
        "core.hallucination_config.get_frontier_model_for_provider",
        return_value="gpt-4o",
    ) as frontier_spy:
        await handler.generate_structured_response(
            prompt="p",
            system_instruction="sys",
            response_model=dict,
            cascade=True,
        )

    # The frontier lookup was called with the OpenAI provider.
    frontier_spy.assert_called_once_with("openai")
    # Every client fetch went to OpenAI — never any other family.
    assert seen_providers, "expected at least one client fetch"
    assert all(p == "openai" for p in seen_providers), (
        f"cross-provider leak: {seen_providers}"
    )


# ---------------------------------------------------------------------------
# D2: self-consistency voter — all N samples stay in the same family
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_D2_self_consistency_voter_keeps_provider_family():
    """All N voter samples go through the same BYOKHandler instance.

    Since the handler's ``self.clients`` map is set once per workspace,
    every sample draws from the same credential set. Combined with D1
    (per-call cascade stays in family), this guarantees the provider
    family is constant across the entire 3-sample vote.
    """
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    # Single shared handler — same instance, same .clients map.
    handler_instances: list = []

    class _Handler:
        async def generate_structured_response(self, **kwargs):
            handler_instances.append(self)
            return SimpleNamespace(action="search")

    shared = _Handler()
    voter = SelfConsistencyVoter(handler=shared)
    await voter.vote(
        prompt="p", response_model=dict, system_instruction="sys"
    )

    # All 3 samples used the same handler instance.
    assert len(handler_instances) == 3
    assert all(h is shared for h in handler_instances), (
        "voter must reuse a single handler instance to preserve the family invariant"
    )
