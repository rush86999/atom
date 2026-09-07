"""
BPC flash-tier recalibration tests (Sept 2026).

Pins the cost/quality recalibration that lets flash-class models serve
ADVANCED-classified BYOK requests:

1. Vetted-table membership and scores for the Sept 2026 flash additions
   (google/gemini-3-flash-preview 93, z-ai/glm-5.3-flash 92,
   openai/gpt-5-mini 91, qwen/qwen3.8-flash 90,
   deepseek/deepseek-v4-flash-0731 88).
2. Attribution: OpenRouter-hosted IDs that CONTAIN another client's name
   ("deepseek/deepseek-v4-flash-0731" contains "deepseek") must rank under
   the OpenRouter client — api.deepseek.com 400s prefixed IDs.
3. Behavioral ranking: z-ai/glm-5.3-flash (92, $0.1625/M blend) tops all
   complexity tiers — ADVANCED drops from qwen3-max ($2.34/M) and
   SIMPLE/COMPLEX from mimo-v2.5-pro ($0.65/M), with the recall-verified
   deepseek-v4-flash-0731 ($0.075/M blend) as the runner-up under the
   pool-relative cost floor.
4. Recall-verified history: qwen3.7-flash stays unvetted (76).

Recall evidence: scripts/bpc_recall_probe_sept2026_v2.py — with a
production-like completion budget, ALL probed flash models pass transcript
recall; v1's "failures" were a 200-token budget starving reasoning models
into empty answers.
"""

import os
os.environ["TESTING"] = "1"

from unittest.mock import Mock, patch

import pytest

from core.benchmarks import MODEL_QUALITY_SCORES, get_quality_score
from core.llm.byok_handler import BYOKHandler, QueryComplexity

# model_id -> (litellm_provider, quality, blended $/M) — blended =
# (in+out)/2 per the cache-aware router's turn-0 formula. Prices mirror the
# live OpenRouter catalog (backend/data/ai_pricing_cache.json, Sept 6 2026).
_POOL = {
    "deepseek/deepseek-v4-flash-0731": ("openrouter", 88, 0.075),
    "z-ai/glm-5.3-flash":              ("openrouter", 92, 0.1625),
    "openai/gpt-5-mini":               ("openrouter", 91, 1.125),
    "google/gemini-3-flash-preview":   ("openrouter", 93, 1.75),
    "minimax/minimax-m3":              ("openrouter", 89, 0.75),
    "qwen/qwen3-max":                  ("openrouter", 90, 2.34),
}


def _fake_fetcher():
    fetcher = Mock()
    pricing = {}
    for mid, (prov, quality, blend) in _POOL.items():
        pricing[mid] = {
            "litellm_provider": prov,
            "input_cost_per_token": blend / 2e6,
            "output_cost_per_token": blend / 2e6,
            "max_input_tokens": 1_000_000,
            "supports_tools": True,
        }
    fetcher.pricing_cache = pricing
    return fetcher


@pytest.fixture
def handler():
    with patch("core.llm.byok_handler.get_byok_manager", return_value=Mock()), \
         patch("core.llm.byok_handler.get_db_session", return_value=Mock()):
        h = BYOKHandler()
    # deepseek FIRST — reproduces the real providers_config insertion order
    # that made substring-first attribution misroute deepseek-prefixed
    # OpenRouter IDs to api.deepseek.com.
    h.clients = {"deepseek": Mock(), "openrouter": Mock()}
    h.env_key_providers = {"openrouter", "deepseek"}  # BYOK: no plan gating
    h.cache_router = Mock()
    h.cache_router.calculate_effective_cost.side_effect = (
        lambda model, provider, estimated_tokens, turn_index=0, **kw:
            _POOL[model][2] / 1e6
    )
    return h


def _rank(handler, complexity):
    with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
               return_value=_fake_fetcher()):
        ranked = handler.get_ranked_providers(
            complexity,
            estimated_tokens=1000,  # default: complexity floors only
            is_managed_service=False,
        )
    return ranked


class TestVettedTableMembership:
    def test_sept_2026_flash_entries_scores(self):
        expected = {
            "google/gemini-3-flash-preview": 93,
            "z-ai/glm-5.3-flash": 92,
            "openai/gpt-5-mini": 91,
            "qwen/qwen3.8-flash": 90,
            "deepseek/deepseek-v4-flash-0731": 88,
        }
        for mid, score in expected.items():
            assert MODEL_QUALITY_SCORES[mid] == score, mid
            assert get_quality_score(mid) == score, mid

    def test_qwen37_flash_stays_unvetted_below_conversational_floor(self):
        # Ultra-budget tier ($0.03/$0.13): vetted but scored 76 — below
        # every chat-complexity floor (SIMPLE 85 is the lowest).
        assert MODEL_QUALITY_SCORES["qwen/qwen3.7-flash"] == 76
        assert get_quality_score("qwen/qwen3.7-flash") == 76

    def test_bare_v4_flash_entry_unchanged(self):
        # Direct-route sibling — do not "align" with the 0731 score blindly
        # (different attribution/pricing route; see benchmarks.py comment).
        assert MODEL_QUALITY_SCORES["deepseek/deepseek-v4-flash"] == 84


class TestProviderAttribution:
    def test_deepseek_prefixed_openrouter_id_attribution(self, handler):
        # Regression: substring-first attribution matched the "deepseek"
        # client (initialized before "openrouter") and served the OpenRouter
        # ID against api.deepseek.com — a guaranteed 400.
        ranked = _rank(handler, QueryComplexity.COMPLEX)
        provider_by_model = {model: provider for provider, model in ranked}
        assert provider_by_model.get("deepseek/deepseek-v4-flash-0731") == "openrouter"

    def test_litellm_exact_match_wins_over_substring(self, handler):
        ranked = _rank(handler, QueryComplexity.ADVANCED)
        for provider, model in ranked:
            assert provider == _POOL[model][0], (model, provider)


class TestAdvancedRecalibration:
    def test_advanced_prefers_recall_safe_flash_over_frontier_price(self, handler):
        ranked = _rank(handler, QueryComplexity.ADVANCED)
        assert ranked, "ADVANCED pool must not be empty"
        # glm-5.3-flash (92, $0.1625/M blend) wins on value; the frontier
        # models remain as fallbacks, no longer forced.
        assert ranked[0][1] == "z-ai/glm-5.3-flash"
        assert "qwen/qwen3-max" in [m for _, m in ranked]

    def test_minimax_m3_does_not_win_advanced(self, handler):
        # 89 < the recalibrated 90 floor: no external frontier-class
        # evidence, so minimax tops out at COMPLEX.
        ranked = _rank(handler, QueryComplexity.ADVANCED)
        assert "minimax/minimax-m3" not in [m for m, _ in ranked]

    def test_complex_lands_on_flash_tier(self, handler):
        # 88 floor admits the Sept 2026 flash tier. glm-5.3-flash tops the
        # rank (highest quality among the floor-compressed cheap pool); the
        # recall-✓ v4-flash-0731 (88, $0.075/M blend — 8.7x cheaper than the
        # previous mimo winner) ranks directly behind it. The pre-change
        # winners (mimo $0.65 / qwen3-max $2.34) are demoted.
        ranked = _rank(handler, QueryComplexity.COMPLEX)
        assert ranked[0][1] == "z-ai/glm-5.3-flash"
        models = [m for _, m in ranked]
        assert "deepseek/deepseek-v4-flash-0731" in models
        for legacy in ("minimax/minimax-m3", "qwen/qwen3-max"):
            assert models.index(legacy) > models.index("z-ai/glm-5.3-flash")

    def test_simple_recall_floor_holds(self, handler):
        ranked = _rank(handler, QueryComplexity.SIMPLE)
        assert ranked
        # 85 floor: sub-85 models stay out; capable flash tier leads.
        assert ranked[0][1] == "z-ai/glm-5.3-flash"
        assert "deepseek/deepseek-v4-flash-0731" in [m for _, m in ranked]
