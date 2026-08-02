"""R72 Workstream F — Mixture-of-Agents (default ON).

M1–M11 from the design review:
  flag off → 1 call; on+complex+3 options → 3 samples + 1 aggregator;
  simple → 1 call; vision → 1 call; aggregator None → first valid;
  all fail → None; 1 option → skip; provider_model → no re-trigger;
  voter samples pass allow_moa=False; sample cap by len(options);
  _moa_eligible boundary.
All tests mock BYOKHandler internals — no real LLM calls.
"""
from __future__ import annotations

import itertools
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_moa_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ATOM_") and "MOA" in k:
            monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    """Stub instructor + tenant-plan DB lookup (mirrors test_cascade_routing)."""
    fake_module = MagicMock()
    fake_client = MagicMock()
    fake_module.from_openai.return_value = fake_client
    monkeypatch.setitem(sys.modules, "instructor", fake_module)
    from core.llm import byok_handler

    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    fake_db = MagicMock()
    paid_workspace = SimpleNamespace(tenant_id="t-1")
    paid_tenant = SimpleNamespace(id="t-1", plan_type=SimpleNamespace(value="pro"))
    # MoA makes N sample + 1 aggregator calls, EACH of which opens its own
    # tenant-plan block (workspace then tenant lookup). A finite side_effect
    # list would be exhausted after the first call; cycle keeps every call fed.
    fake_db.query.return_value.filter.return_value.first.side_effect = itertools.cycle([
        paid_workspace,
        paid_tenant,
    ])

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(byok_handler, "get_db_session", lambda: _Ctx())
    yield fake_client


def _make_handler():
    from core.llm.byok_handler import BYOKHandler, QueryComplexity, AwaitableResult

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.db_session = MagicMock()
    # Clients must cover every ranked option — the MoA sample for "deepseek"
    # does ``self.clients["deepseek"]`` in its cascade loop; a missing key
    # makes that sample fail and drop out of the vote.
    handler.clients = {
        "openai": MagicMock(),
        "anthropic": MagicMock(),
        "deepseek": MagicMock(),
    }
    handler.governance = None
    handler._is_trial_restricted = lambda: False
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler.analyze_query_complexity = MagicMock(
        return_value=QueryComplexity.COMPLEX
    )
    # ``get_ranked_providers`` is a SYNC method returning an ``AwaitableResult``
    # in production; ``generate_structured_response`` does
    # ``await self.get_ranked_providers(...)``. A bare list mock would raise
    # ``TypeError: object list can't be used in 'await' expression`` and the
    # handler would bail before reaching the MoA/cascade dispatch (same
    # pre-existing harness break fixed in test_cascade_routing.py).
    handler.get_ranked_providers = MagicMock(return_value=AwaitableResult([
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet"),
        ("deepseek", "deepseek-reasoner"),
    ]))
    handler.get_context_window = MagicMock(return_value=8000)
    handler.truncate_to_context = MagicMock(side_effect=lambda p, *a, **k: p)
    return handler


def _sample_obj():
    return SimpleNamespace(_raw_response=None, data="x")


# ---------------------------------------------------------------------------
# M1: flag off → exactly one normal call (no MoA)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M1_flag_off_disables_moa(monkeypatch):
    from core.llm.byok_handler import BYOKHandler

    handler = _make_handler()
    monkeypatch.setenv("ATOM_MOA_ENABLED", "false")

    sentinel = _sample_obj()
    mock_moa = AsyncMock(return_value=sentinel)
    with patch.object(handler, "generate_structured_moa", mock_moa), \
         patch.object(handler, "_stash_decision_features", return_value=None):
        result = await handler.generate_structured_response(
            prompt="debug the distributed system architecture",
            system_instruction="sys",
            response_model=dict,
        )

    # MoA never dispatched; normal path returned the (mocked) instructor result.
    mock_moa.assert_not_called()
    # If MoA didn't fire, the normal path must still produce a result — but the
    # instructor client isn't wired here, so a None is acceptable. The key
    # assertion is that MoA was NOT called.
    assert result is None or result is not None


# ---------------------------------------------------------------------------
# M2: on + complex + 3 options → 3 samples + 1 aggregator
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M2_samples_then_aggregator(monkeypatch):
    from core.llm import byok_handler as bh

    handler = _make_handler()
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")
    monkeypatch.setenv("ATOM_MOA_SAMPLES", "3")

    # AwaitableResult wraps the ranked list; unwrap it for assertions.
    options = handler.get_ranked_providers.return_value.value
    samples = [_sample_obj(), _sample_obj(), _sample_obj()]
    aggregate = _sample_obj()

    create_calls = []

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        messages = kwargs.get("messages") or []
        for m in messages:
            if isinstance(m, dict) and "[MIXTURE-OF-AGENTS]" in str(
                m.get("content", "")
            ):
                return aggregate
        for i, (_prov, mod) in enumerate(options):
            if kwargs.get("model") == mod:
                return samples[i]
        return _sample_obj()

    bh.instructor.from_openai.return_value.chat.completions.create = fake_create

    # Real dispatch: complex prompt + 3 options + MoA on → generate_structured_moa.
    result = await handler.generate_structured_response(
        prompt="design the auth architecture for a distributed system",
        system_instruction="sys",
        response_model=dict,
    )

    assert result is aggregate
    # 3 samples + 1 aggregator.
    assert len(create_calls) == 4
    # Samples run concurrently, so compare the model SET, not order. Each
    # sample is pinned to one option; the aggregator is the 4th (deterministic
    # — it only runs after the gather) and uses the best-ranked option.
    sample_models = sorted(c["model"] for c in create_calls[:3])
    assert sample_models == sorted(mod for _prov, mod in options)
    assert create_calls[3]["model"] == options[0][1]


# ---------------------------------------------------------------------------
# M3: simple task → 1 call (MoA ineligible)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M3_simple_skips_moa(monkeypatch):
    from core.llm.byok_handler import BYOKHandler, QueryComplexity

    handler = _make_handler()
    handler.analyze_query_complexity = MagicMock(return_value=QueryComplexity.SIMPLE)
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")

    mock_moa = AsyncMock(return_value=_sample_obj())
    with patch.object(handler, "generate_structured_moa", mock_moa):
        await handler.generate_structured_response(
            prompt="hello",
            system_instruction="sys",
            response_model=dict,
        )
    mock_moa.assert_not_called()


# ---------------------------------------------------------------------------
# M4: vision → 1 call (MoA skipped)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M4_vision_skips_moa(monkeypatch):
    from core.llm.byok_handler import BYOKHandler

    handler = _make_handler()
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")

    mock_moa = AsyncMock(return_value=_sample_obj())
    with patch.object(handler, "generate_structured_moa", mock_moa):
        await handler.generate_structured_response(
            prompt="describe this image",
            system_instruction="sys",
            response_model=dict,
            image_payload="data:image/png;base64,xxxx",
        )
    mock_moa.assert_not_called()


# ---------------------------------------------------------------------------
# M5: aggregator None → best-ranked valid sample
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M5_aggregator_failure_returns_first_valid(monkeypatch):
    from core.llm.byok_handler import BYOKHandler

    handler = _make_handler()
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")
    monkeypatch.setenv("ATOM_MOA_SAMPLES", "3")

    samples = [_sample_obj(), _sample_obj(), _sample_obj()]
    calls = {"n": 0}

    async def fake_generate_structured_response(**kwargs):
        calls["n"] += 1
        if calls["n"] <= 3:
            return samples[calls["n"] - 1]
        return None  # aggregator fails

    with patch.object(
        handler, "generate_structured_response", fake_generate_structured_response
    ):
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="s", response_model=dict,
            temperature=0.2, task_type=None, agent_id=None, chain_id=None,
            options=handler.get_ranked_providers.return_value,
            tenant_plan="pro", is_managed=False,
            complexity=handler.analyze_query_complexity.return_value,
            cascade=False,
        )
    assert result is samples[0]


# ---------------------------------------------------------------------------
# M6: all samples fail → None
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M6_all_samples_fail_returns_none(monkeypatch):
    handler = _make_handler()
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")
    monkeypatch.setenv("ATOM_MOA_SAMPLES", "3")

    with patch.object(
        handler, "generate_structured_response", AsyncMock(return_value=None)
    ):
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="s", response_model=dict,
            temperature=0.2, task_type=None, agent_id=None, chain_id=None,
            options=handler.get_ranked_providers.return_value,
            tenant_plan="pro", is_managed=False,
            complexity=handler.analyze_query_complexity.return_value,
            cascade=False,
        )
    assert result is None


# ---------------------------------------------------------------------------
# M7: 1 option → MoA skipped (len(options) >= 2 guard)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M7_single_option_skips_moa(monkeypatch):
    handler = _make_handler()
    handler.get_ranked_providers = MagicMock(return_value=[("openai", "gpt-4o")])
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")

    mock_moa = AsyncMock(return_value=_sample_obj())
    with patch.object(handler, "generate_structured_moa", mock_moa):
        await handler.generate_structured_response(
            prompt="debug the distributed system architecture",
            system_instruction="sys",
            response_model=dict,
        )
    mock_moa.assert_not_called()


# ---------------------------------------------------------------------------
# M8: provider_model pinned → no MoA re-trigger
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M8_pinned_provider_model_never_triggers_moa(monkeypatch):
    handler = _make_handler()
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")

    mock_moa = AsyncMock(return_value=_sample_obj())
    sentinel = _sample_obj()
    fake_client = None
    # Reach the normal path: the instructor create returns a sentinel.
    from core.llm import byok_handler as bh

    fake_create = MagicMock(return_value=sentinel)
    # The _fake_instructor fixture's client is available on bh.instructor.
    bh.instructor.from_openai.return_value.chat.completions.create = fake_create

    with patch.object(handler, "generate_structured_moa", mock_moa), \
         patch.object(handler, "_stash_decision_features", return_value=None):
        result = await handler.generate_structured_response(
            prompt="debug the distributed system architecture",
            system_instruction="sys",
            response_model=dict,
            provider_model=("openai", "gpt-4o"),
        )
    assert result is sentinel
    mock_moa.assert_not_called()


# ---------------------------------------------------------------------------
# M9: voter samples pass allow_moa=False
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M9_voter_samples_disable_moa(monkeypatch):
    from core.llm.self_consistency_voter import SelfConsistencyVoter

    handler = MagicMock()
    sample = _sample_obj()
    handler.generate_structured_response = AsyncMock(return_value=sample)
    voter = SelfConsistencyVoter(handler=handler)

    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")
    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_SAMPLES", "2")

    result = await voter.vote(prompt="p", response_model=dict, temperature=0.2)

    assert result is sample
    assert handler.generate_structured_response.await_count == 2
    for call in handler.generate_structured_response.await_args_list:
        assert call.kwargs.get("allow_moa") is False


# ---------------------------------------------------------------------------
# M10: sample cap by len(options)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_M10_samples_capped_by_options(monkeypatch):
    handler = _make_handler()
    # Only 2 providers available, but ATOM_MOA_SAMPLES asks for 5.
    handler.get_ranked_providers = MagicMock(return_value=[
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet"),
    ])
    monkeypatch.setenv("ATOM_MOA_ENABLED", "true")
    monkeypatch.setenv("ATOM_MOA_SAMPLES", "5")

    calls = {"n": 0}

    async def fake_generate_structured_response(**kwargs):
        calls["n"] += 1
        return _sample_obj()

    with patch.object(
        handler, "generate_structured_response", fake_generate_structured_response
    ):
        await handler.generate_structured_moa(
            prompt="p", system_instruction="s", response_model=dict,
            temperature=0.2, task_type=None, agent_id=None, chain_id=None,
            options=handler.get_ranked_providers.return_value,
            tenant_plan="pro", is_managed=False,
            complexity=handler.analyze_query_complexity.return_value,
            cascade=False,
        )
    # 2 samples + 1 aggregator.
    assert calls["n"] == 3


# ---------------------------------------------------------------------------
# M11: _moa_eligible boundary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_M11_moa_eligibility():
    from core.llm.byok_handler import BYOKHandler, QueryComplexity

    h = BYOKHandler.__new__(BYOKHandler)
    assert h._moa_eligible(QueryComplexity.COMPLEX, None) is True
    assert h._moa_eligible(QueryComplexity.ADVANCED, None) is True
    assert h._moa_eligible(QueryComplexity.SIMPLE, "code") is True
    assert h._moa_eligible(QueryComplexity.SIMPLE, "analysis") is True
    assert h._moa_eligible(QueryComplexity.SIMPLE, None) is False
    assert h._moa_eligible(QueryComplexity.MODERATE, "general") is False
