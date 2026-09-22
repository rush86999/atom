"""Tests for the computer-use evidence restriction (2026-09-21).

Web-researched restriction per user directive: only models with external
benchmark evidence (OSWorld-Verified / ScreenSpot-Pro / BenchLM
computer-use, Sep 2026) or local measurement may serve task_type=
computer_use. The catalog's capability flags are self-declared and
insufficient — glm-5.3-flash is vision-servable yet locally measured to
floor on actuation (ENV_HARNESS_ADOPTION_PLAN.md Phases 4a/4b).
"""

import pytest

from core.benchmarks import (
    COMPUTER_USE_EVIDENCE,
    MODEL_CAPABILITY_SCORES,
    computer_use_evidence,
)
from core.llm.byok_handler import BYOKHandler


EVIDENCED = ["gpt-6-astra", "kimi-k3", "qwen3.8-max", "claude-sonnet-4-6",
             "claude-opus-4-8", "glm-5.3", "lux-1.0"]
NOT_EVIDENCED = ["glm-5.3-flash", "mimo-v2.5", "grok-4.6", "minimax-m3",
                 "deepseek-v4-pro", "deepseek-v4-flash-vision-exp",
                 "gpt-5.6-luna", "qwen3.7-plus", "kimi-k2.6",
                 "some-unknown-model"]


@pytest.fixture
def handler():
    # _filter_by_capabilities touches no instance state for the
    # capability_index fast path — a bare instance avoids heavy __init__.
    return object.__new__(BYOKHandler)


# ---------------------------------------------------------------------------
# Registry resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model", EVIDENCED)
def test_evidenced_models_resolve(model):
    entry = computer_use_evidence(model)
    assert entry is not None
    assert 0 <= entry["score"] <= 100
    assert entry["source"]


@pytest.mark.parametrize("model", NOT_EVIDENCED)
def test_nonevidenced_models_do_not_resolve(model):
    assert computer_use_evidence(model) is None


def test_composite_ids_resolve_through_prefixes():
    assert computer_use_evidence("opencode-go/kimi-k3")["score"] == \
        COMPUTER_USE_EVIDENCE["kimi-k3"]["score"]
    assert computer_use_evidence("openrouter/openai/gpt-4o") is not None
    assert computer_use_evidence("opencode-go/glm-5.3-flash") is None


def test_registry_entries_all_carry_sources():
    for model, entry in COMPUTER_USE_EVIDENCE.items():
        assert entry["source"].strip(), model
        assert 0 <= entry["score"] <= 100, model


def test_flash_variant_of_evidenced_flagship_is_not_admitted():
    # glm-5.3 is evidenced; its flash variant is NOT (local actuation floor)
    assert computer_use_evidence("glm-5.3") is not None
    assert computer_use_evidence("glm-5.3-flash") is None


# ---------------------------------------------------------------------------
# The routing gate
# ---------------------------------------------------------------------------

def test_computer_use_gate_admits_evidenced_models(handler):
    idx = {m: ["chat", "vision", "computer_use"] for m in EVIDENCED}
    for model in EVIDENCED:
        assert handler._filter_by_capabilities(
            model, "computer_use", idx), model


def test_computer_use_gate_excludes_nonevidenced_even_if_catalog_claims_it(
        handler):
    # The whole point: self-declared capability flags are not sufficient.
    idx = {m: ["chat", "vision", "computer_use"] for m in NOT_EVIDENCED}
    for model in NOT_EVIDENCED:
        assert not handler._filter_by_capabilities(
            model, "computer_use", idx), model


def test_computer_use_gate_fails_closed_on_unknown_models(handler):
    # Unknown models pass through for OTHER capabilities but are excluded
    # from computer_use (evidence-gated, fail-closed).
    idx = {"gpt-6-astra": ["computer_use"]}
    assert not handler._filter_by_capabilities(
        "brand-new-frontier-model", "computer_use", idx)


def test_escape_hatch_admits_unverified(handler, monkeypatch):
    monkeypatch.setenv("ATOM_COMPUTER_USE_ALLOW_UNVERIFIED", "1")
    idx = {"glm-5.3-flash": ["chat", "vision", "computer_use"]}
    assert handler._filter_by_capabilities(
        "glm-5.3-flash", "computer_use", idx)
    monkeypatch.setenv("ATOM_COMPUTER_USE_ALLOW_UNVERIFIED", "0")
    assert not handler._filter_by_capabilities(
        "glm-5.3-flash", "computer_use", idx)


def test_vision_capability_routing_is_unchanged(handler):
    # The restriction is computer_use-specific: vision-only routing keeps
    # its conservative pass-through semantics for unknown models, and
    # index-known models still need the actual capability flag.
    idx = {"gpt-6-astra": ["vision"], "kimi-k3": ["chat", "computer_use"]}
    assert handler._filter_by_capabilities("gpt-6-astra", "vision", idx)
    assert handler._filter_by_capabilities(
        "totally-unknown-model", "vision", idx)  # unknown passes through
    assert not handler._filter_by_capabilities("kimi-k3", "vision", idx)


def test_no_capability_requirement_is_unchanged(handler):
    assert handler._filter_by_capabilities("anything-at-all", None, {})


# ---------------------------------------------------------------------------
# Score-table consistency
# ---------------------------------------------------------------------------

def test_capability_scores_registry_consistency():
    """Every computer_use capability-score entry must be evidence-admitted
    (scores rank admitted models; they must not admit unadmitted ones)."""
    scored = MODEL_CAPABILITY_SCORES["computer_use"]
    for model in scored:
        assert computer_use_evidence(model) is not None, model


def test_registry_and_scores_agree_where_both_listed():
    scored = MODEL_CAPABILITY_SCORES["computer_use"]
    for model, score in scored.items():
        entry = COMPUTER_USE_EVIDENCE[model]
        assert scored[model] == entry["score"], model
