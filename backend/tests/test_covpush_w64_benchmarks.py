"""Coverage wave 64 — core/benchmarks.py (TDD, mocked benchmark fetcher).

Covers get_quality_score / get_capability_score: dynamic fetcher priority
(score, None, ImportError, generic exception), static exact match,
longest-partial-match semantics, unknown-model heuristics, capability
exact/partial matches, and the general-quality fallback.
"""
import sys
from types import SimpleNamespace

import pytest

from core.benchmarks import (
    MODEL_CAPABILITY_SCORES,
    MODEL_QUALITY_SCORES,
    get_capability_score,
    get_quality_score,
)


def make_fetcher(score=None, capability_score=None, raises=None, capability_raises=None):
    def bench_score(model_id):
        if raises is not None:
            raise raises
        return score

    def cap_score(model_id, capability):
        if capability_raises is not None:
            raise capability_raises
        return capability_score

    return SimpleNamespace(
        get_benchmark_score=bench_score,
        get_capability_score=cap_score,
    )


@pytest.fixture(autouse=True)
def neutral_fetcher(monkeypatch):
    monkeypatch.setattr(
        "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
        lambda: make_fetcher(score=None, capability_score=None),
    )


class TestQualityScoreDynamic:
    def test_dynamic_score_used(self, monkeypatch):
        from core.benchmarks import get_quality_score as gqs
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(score=87.4),
        )
        assert gqs("some-model") == 87

    def test_dynamic_score_rounded_not_truncated(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(score=87.6),
        )
        assert get_quality_score("some-model") == 88

    def test_dynamic_score_clamped_above(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(score=104.6),
        )
        assert get_quality_score("some-model") == 100

    def test_dynamic_score_clamped_below(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(score=-5.0),
        )
        assert get_quality_score("some-model") == 0

    def test_dynamic_none_falls_back_to_static(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(score=None),
        )
        assert get_quality_score("deepseek-v4-flash") == 88

    def test_import_error_falls_back(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.dynamic_benchmark_fetcher", None)
        assert get_quality_score("gpt-5") == 99

    def test_generic_exception_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(raises=ValueError("bad")),
        )
        assert get_quality_score("gemini-3-pro") == 100


class TestQualityScoreStatic:
    def test_exact_match(self):
        assert get_quality_score("gpt-4o") == MODEL_QUALITY_SCORES["gpt-4o"]

    def test_exact_match_case_insensitive_partial_prefers_longest(self):
        assert get_quality_score("gpt-4o-mini-2024-07-18") == 85
        assert get_quality_score("GPT-4O-MINI-2024-07-18") == 85

    def test_partial_match_prefers_longest_key(self):
        assert get_quality_score("deepseek-v3.2-speciale-extra") == 99
        assert get_quality_score("kimi-k2.7-code-anything") == 97

    def test_partial_match_single_key(self):
        assert get_quality_score("gpt-5.2-reasoning") == 100

    def test_heuristic_reasoner(self):
        assert get_quality_score("acme-reasoner-1") == 95

    def test_heuristic_thinking(self):
        assert get_quality_score("acme-thinking-x") == 95

    def test_o1_substring_matches_o1_key_before_heuristics(self):
        assert get_quality_score("acme-o1-large") == 92

    def test_heuristic_flash(self):
        assert get_quality_score("acme-flash-1") == 80

    def test_heuristic_haiku(self):
        assert get_quality_score("acme-haiku") == 80

    def test_heuristic_mini(self):
        assert get_quality_score("acme-mini-2") == 80

    def test_heuristic_70b(self):
        assert get_quality_score("acme-70b-whatever") == 88

    def test_heuristic_72b(self):
        assert get_quality_score("acme-72b") == 88

    def test_heuristic_8b(self):
        assert get_quality_score("acme-8b") == 75

    def test_heuristic_7b(self):
        assert get_quality_score("acme-7b") == 75

    def test_default_floor(self):
        assert get_quality_score("totally-unknown-model") == 70


class TestCapabilityScoreDynamic:
    def test_dynamic_capability_score_used(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(capability_score=99),
        )
        assert get_capability_score("some-model", "vision") == 99

    def test_dynamic_none_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(capability_score=None),
        )
        assert get_capability_score("lux-1.0", "computer_use") == 95

    def test_import_error_falls_back(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.dynamic_benchmark_fetcher", None)
        assert get_capability_score("gpt-4o", "vision") == 95

    def test_generic_exception_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            "core.dynamic_benchmark_fetcher.get_benchmark_fetcher",
            lambda: make_fetcher(capability_raises=ValueError("bad")),
        )
        assert get_capability_score("gpt-4o", "vision") == 95


class TestCapabilityScoreStatic:
    def test_exact_match(self):
        assert get_capability_score("lux-1.0", "computer_use") == 95
        assert get_capability_score("gpt-4o", "vision") == 95
        assert get_capability_score("claude-3.5-sonnet", "tools") == 93

    def test_partial_match_prefers_longest(self):
        assert get_capability_score("lux-1.0-beta", "computer_use") == 95
        assert get_capability_score("gpt-4o-2024-05-13", "tools") == 91

    def test_unknown_capability_uses_quality_score(self):
        assert get_capability_score("gpt-4o", "non_existent_cap") == 90

    def test_unknown_model_in_capability_uses_quality_score(self):
        assert get_capability_score("deepseek-v4-flash", "tools") == 88

    def test_unknown_model_heuristic_fallback(self):
        assert get_capability_score("unknown-70b-model", "vision") == 88

    def test_static_capability_scores_contract(self):
        assert MODEL_CAPABILITY_SCORES["computer_use"]["claude-3.5-sonnet"] == 85
        assert MODEL_CAPABILITY_SCORES["vision"]["gemini-2.0-flash"] == 88
