"""GLM (Zhipu AI) first-class BYOK provider — routing + recognition tests.

GLM-5.2 (June 2026 flagship) was wired into the BYOK system across four
registries (byok_handler, hallucination_config, cache_aware_router). These
tests pin that wiring so a future refactor doesn't silently drop GLM back
to second-class status.

Covers:
  * PROVIDER_TIERS membership (budget for cost routing, premium for frontier)
  * COST_EFFICIENT_MODELS complexity ladder (SIMPLE → glm-4.5, ADVANCED → glm-5.2)
  * FRONTIER_MODELS recognition (incl. snapshot-suffix matching)
  * _FRONTIER_BY_PROVIDER lookup (both "glm" and "zhipu" keys)
  * CACHE_CAPABILITIES entry exists with expected shape
  * Cascade-routing provider-family invariant: GLM stays GLM on escalation
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clean_mitigation_env(monkeypatch):
    """Reset ATOM_* hallucination-mitigation env vars before each test."""
    for k in list(os.environ):
        if k.startswith("ATOM_") and (
            "VERIFIED" in k or "CASCADE" in k or "SELF_CONSISTENCY" in k
        ):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    """Stub instructor so BYOKHandler imports cleanly without the dependency."""
    fake_module = MagicMock()
    fake_client = MagicMock()
    fake_module.from_openai.return_value = fake_client
    monkeypatch.setitem(sys.modules, "instructor", fake_module)
    from core.llm import byok_handler

    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    # Stub the tenant-plan DB lookup.
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


# ===========================================================================
# G1: PROVIDER_TIERS — GLM is in both budget and premium
# ===========================================================================


@pytest.mark.unit
def test_G1_glm_in_budget_tier():
    """GLM remains in the budget tier for cost routing on simple tasks."""
    from core.llm.byok_handler import PROVIDER_TIERS

    assert "glm" in PROVIDER_TIERS["budget"]


@pytest.mark.unit
def test_G1b_glm_in_premium_tier():
    """GLM-5.2 is frontier-class → GLM is also in the premium tier."""
    from core.llm.byok_handler import PROVIDER_TIERS

    assert "glm" in PROVIDER_TIERS["premium"]


# ===========================================================================
# G2: COST_EFFICIENT_MODELS — complexity ladder culminates in glm-5.2
# ===========================================================================


@pytest.mark.unit
def test_G2_glm_complexity_ladder_present():
    """GLM must have a complexity→model mapping like every other provider."""
    from core.llm.byok_handler import COST_EFFICIENT_MODELS

    assert "glm" in COST_EFFICIENT_MODELS, (
        "GLM missing from COST_EFFICIENT_MODELS — complexity-based routing "
        "will not work for GLM"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "complexity, expected_model",
    [
        ("SIMPLE", "glm-4.5"),
        ("MODERATE", "glm-4.6"),
        ("COMPLEX", "glm-5"),
        ("ADVANCED", "glm-5.2"),
    ],
)
def test_G2b_glm_complexity_routing(complexity, expected_model):
    """Each query complexity routes to the expected GLM model.

    ADVANCED must route to glm-5.2 — the June 2026 flagship. If this
    breaks, GLM cannot serve high-complexity tasks (code, reasoning,
    long-context analysis) at frontier quality.
    """
    from core.llm.byok_handler import COST_EFFICIENT_MODELS, QueryComplexity

    qc = QueryComplexity[complexity]
    assert COST_EFFICIENT_MODELS["glm"][qc] == expected_model


@pytest.mark.unit
def test_G2c_glm_advanced_uses_latest_flagship():
    """ADVANCED query complexity must use glm-5.2 (not an older GLM variant).

    This is the canonical test that GLM-5.2 specifically — not just 'some
    GLM model' — is the routing target for hard tasks. If a future model
    refresh changes the target, this test should be updated deliberately,
    not silently.
    """
    from core.llm.byok_handler import COST_EFFICIENT_MODELS, QueryComplexity

    assert COST_EFFICIENT_MODELS["glm"][QueryComplexity.ADVANCED] == "glm-5.2"


# ===========================================================================
# G3: FRONTIER_MODELS — glm-5.2 + glm-5 recognized as frontier
# ===========================================================================


@pytest.mark.unit
@pytest.mark.parametrize("model", ["glm-5.2", "glm-5"])
def test_G3_glm_flagships_in_frontier_models(model):
    """GLM-5.2 and GLM-5 must be in the FRONTIER_MODELS set."""
    from core.hallucination_config import FRONTIER_MODELS

    assert model in FRONTIER_MODELS, (
        f"{model} missing from FRONTIER_MODELS — cascade routing cannot "
        f"recognize GLM flagships"
    )


@pytest.mark.unit
def test_G3b_is_frontier_model_recognizes_glm_52():
    """is_frontier_model() returns True for bare glm-5.2."""
    from core.hallucination_config import is_frontier_model

    assert is_frontier_model("glm-5.2") is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "model",
    [
        "glm-5.2-20260601",       # compact dated suffix
        "glm-5.2-2026-06-01",     # dashed dated suffix
        "glm-5.2-2026",           # year-only suffix
        "GLM-5.2",                # case-insensitive
    ],
)
def test_G3c_snapshot_suffix_matching(model):
    """Dated-snapshot and case variants still register as frontier.

    The _model_base() helper strips dated snapshot suffixes so
    'glm-5.2-20260601' matches the 'glm-5.2' frontier entry. If this
    breaks, version-pinned GLM deployments won't get frontier treatment.

    Note: non-dated tags like '-preview' are intentionally NOT stripped
    — those represent genuinely distinct model variants. Only dated
    snapshots (the Anthropic/OpenAI convention) are normalized away.
    """
    from core.hallucination_config import is_frontier_model

    assert is_frontier_model(model) is True, (
        f"{model!r} should be recognized as frontier (matches glm-5.2 base)"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "model",
    [
        "glm-4.5",    # older generation
        "glm-4.6",    # older generation
        "glm-4",      # much older
        "chatglm",    # legacy name
    ],
)
def test_G3d_older_glm_models_not_frontier(model):
    """Older GLM generations are NOT frontier — only 5.x and above.

    This guards against accidentally promoting the entire GLM family to
    frontier status (which would cascade every GLM call to the flagship).
    """
    from core.hallucination_config import is_frontier_model

    assert is_frontier_model(model) is False, (
        f"{model!r} should NOT be recognized as frontier"
    )


# ===========================================================================
# G4: _FRONTIER_BY_PROVIDER — both "glm" and "zhipu" keys resolve
# ===========================================================================


@pytest.mark.unit
def test_G4_frontier_lookup_glm_key():
    """The 'glm' provider key (used by byok_handler) resolves to glm-5.2."""
    from core.hallucination_config import get_frontier_model_for_provider

    assert get_frontier_model_for_provider("glm") == "glm-5.2"


@pytest.mark.unit
def test_G4b_frontier_lookup_zhipu_key():
    """The 'zhipu' provider key (used by learning_llm_router) resolves to glm-5.2.

    The learning router registers GLM-5.2 with provider='zhipu' while
    byok_handler uses 'glm'. Both keys MUST resolve or cascade escalation
    silently fails for one of the two code paths.
    """
    from core.hallucination_config import get_frontier_model_for_provider

    assert get_frontier_model_for_provider("zhipu") == "glm-5.2"


@pytest.mark.unit
def test_G4c_frontier_lookup_case_insensitive():
    """Provider lookup is case-insensitive (matches 'GLM', 'Glm', 'glm')."""
    from core.hallucination_config import get_frontier_model_for_provider

    assert get_frontier_model_for_provider("GLM") == "glm-5.2"
    assert get_frontier_model_for_provider("Glm") == "glm-5.2"


@pytest.mark.unit
def test_G4d_frontier_lookup_unknown_provider_returns_none():
    """Unknown provider returns None (callers treat as 'do not escalate')."""
    from core.hallucination_config import get_frontier_model_for_provider

    assert get_frontier_model_for_provider("nonsense_provider") is None
    assert get_frontier_model_for_provider(None) is None


# ===========================================================================
# G5: CACHE_CAPABILITIES — GLM entry exists with expected shape
# ===========================================================================


@pytest.mark.unit
def test_G5_glm_in_cache_capabilities():
    """GLM must have a CACHE_CAPABILITIES entry (even if caching unsupported).

    Without this entry, CacheAwareRouter silently treats GLM as
    'supports_cache=False' anyway — but the explicit entry makes the
    capability declaration intentional and discoverable.
    """
    from core.llm.cache_aware_router import CacheAwareRouter

    assert "glm" in CacheAwareRouter.CACHE_CAPABILITIES


@pytest.mark.unit
def test_G5b_glm_cache_shape():
    """GLM cache entry has the three required keys with correct types."""
    from core.llm.cache_aware_router import CacheAwareRouter

    entry = CacheAwareRouter.CACHE_CAPABILITIES["glm"]
    assert "supports_cache" in entry
    assert "cached_cost_ratio" in entry
    assert "min_tokens" in entry
    assert isinstance(entry["supports_cache"], bool)
    assert isinstance(entry["cached_cost_ratio"], (int, float))
    assert isinstance(entry["min_tokens"], int)


@pytest.mark.unit
def test_G5c_glm_cache_disabled_matches_reality():
    """As of June 2026, Zhipu AI has no documented prompt cache.

    If Zhipu ships prompt caching, flip this assertion and update the
    cached_cost_ratio + min_tokens. Until then, supports_cache=False
    ensures accurate cost reporting (no phantom cache discounts).
    """
    from core.llm.cache_aware_router import CacheAwareRouter

    entry = CacheAwareRouter.CACHE_CAPABILITIES["glm"]
    assert entry["supports_cache"] is False
    assert entry["cached_cost_ratio"] == 1.0  # full price when no cache


# ===========================================================================
# G6: Provider-family invariant — GLM stays GLM on cascade escalation
# ===========================================================================


@pytest.mark.unit
def test_G6_glm_frontier_same_family_as_glm_52():
    """The frontier target for 'glm' is in the same provider family.

    Cascade routing's structural invariant: escalation stays within the
    provider family. GLM's frontier (glm-5.2) must be in the GLM family,
    not get re-routed to OpenAI or Anthropic. This is the explicit
    assertion of that invariant for the GLM family.
    """
    from core.hallucination_config import (
        _FRONTIER_BY_PROVIDER,
        get_frontier_model_for_provider,
    )

    glm_frontier = get_frontier_model_for_provider("glm")
    assert glm_frontier is not None
    # The frontier model id itself starts with "glm-" (same family)
    assert glm_frontier.startswith("glm-"), (
        f"GLM frontier '{glm_frontier}' is not in the GLM family — "
        f"cascade routing would cross provider families"
    )
    # And the registry entry is consistent
    assert _FRONTIER_BY_PROVIDER.get("glm") == glm_frontier


# ===========================================================================
# G7: Regression — GLM addition didn't displace existing providers
# ===========================================================================


@pytest.mark.unit
def test_G7_existing_providers_still_have_frontier_targets():
    """Adding GLM must not have removed frontier targets for other providers.

    Guards against a copy-paste error where editing _FRONTIER_BY_PROVIDER
    could accidentally drop a neighboring entry.
    """
    from core.hallucination_config import _FRONTIER_BY_PROVIDER

    expected = {
        "openai": "gpt-4o",
        "anthropic": "claude-3-5-sonnet",
        "deepseek": "deepseek-reasoner",
        "gemini": "gemini-1.5-pro",
        "minimax": "minimax-m2.7",
        "mistral": "mistral-large-latest",
        "qwen": "qwen-max",
        "groq": "llama-3.3-70b-versatile",
        "cohere": "command-r-plus",
        "ollama": "llama3:70b",
        "lux": "gpt-4o",
    }
    for provider, model in expected.items():
        assert _FRONTIER_BY_PROVIDER.get(provider) == model, (
            f"{provider} frontier displaced by GLM addition (was {model!r}, "
            f"now {_FRONTIER_BY_PROVIDER.get(provider)!r})"
        )


@pytest.mark.unit
def test_G7b_existing_cost_efficient_providers_preserved():
    """Adding GLM to COST_EFFICIENT_MODELS didn't remove existing providers."""
    from core.llm.byok_handler import COST_EFFICIENT_MODELS

    # Spot-check a representative set
    for provider in ("openai", "anthropic", "deepseek", "gemini", "ollama"):
        assert provider in COST_EFFICIENT_MODELS, (
            f"{provider} missing from COST_EFFICIENT_MODELS after GLM addition"
        )


# ===========================================================================
# G8: GLM appears alongside peer providers in tier routing
# ===========================================================================


@pytest.mark.unit
def test_G8_glm_peer_with_other_frontier_providers_in_premium():
    """Premium tier contains GLM alongside the other frontier providers.

    Documents the intent: GLM-5.2 is treated as a frontier-class provider
    for premium routing, same tier as OpenAI and Anthropic.
    """
    from core.llm.byok_handler import PROVIDER_TIERS

    premium = PROVIDER_TIERS["premium"]
    assert "glm" in premium
    # And the established frontier providers are still there
    assert "openai" in premium
    assert "anthropic" in premium
