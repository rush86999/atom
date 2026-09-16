"""Unit tests for the pure parts of the provider-reliability harness.

Covers exactly the pieces the harness's honesty depends on and that need no
network, database or provider credentials:

* answer contracts (sentinel token, expected number, unsupported fixture);
* fixture limitations (the assertions the fixtures cannot support);
* retry / spend caps;
* four-state fallback-topology classification;
* first-visible extraction from a synthetic chunk stream;
* denominators — no rate rendered with a zero denominator.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from scripts.provider_reliability_replay import (
    STATE_ALL_SHARED,
    STATE_NO_FALLBACK,
    STATE_NO_SHARED,
    STATE_SOME_SHARED,
    STATE_UNKNOWN,
    STATUS_SATISFIED,
    STATUS_UNSUPPORTED,
    STATUS_VIOLATED,
    TOPOLOGY_STATES,
    AnswerContract,
    Probe,
    SpendLedger,
    build_workload,
    build_parser,
    classify,
    classify_fallback_topology,
    delta_text,
    fixture_limitations,
    first_visible_index,
    looks_like_non_answer,
    parse_numbers,
    rate,
    resolve_fallback_pairs,
    streamed_text,
    summarize,
    transport_outcome,
)

# ---------------------------------------------------------------------------
# Answer contracts
# ---------------------------------------------------------------------------


class TestSentinelContract:
    def test_token_present_satisfies(self):
        r = AnswerContract(kind="sentinel_token", token="ok").check("ok")
        assert r.status == STATUS_SATISFIED and r.satisfied is True

    def test_token_absent_violates(self):
        r = AnswerContract(kind="sentinel_token", token="ok").check("I cannot help with that.")
        assert r.status == STATUS_VIOLATED and r.satisfied is False

    def test_token_must_be_a_word_not_a_substring(self):
        r = AnswerContract(kind="sentinel_token", token="ok").check("okay then")
        assert r.status == STATUS_VIOLATED

    def test_empty_reply_violates(self):
        assert AnswerContract(kind="sentinel_token", token="ok").check("").status == STATUS_VIOLATED
        assert AnswerContract(kind="sentinel_token", token="ok").check(None).status == STATUS_VIOLATED

    def test_single_word_flag_reports_non_sole_content_but_still_satisfies(self):
        r = AnswerContract(kind="sentinel_token", token="ok", single_word=True).check("Sure: ok")
        assert r.status == STATUS_SATISFIED
        assert "sole content" in r.detail

    def test_single_word_flag_accepts_punctuation_around_the_token(self):
        r = AnswerContract(kind="sentinel_token", token="ok", single_word=True).check('"ok."')
        assert r.status == STATUS_SATISFIED

    def test_apology_is_not_a_satisfied_contract(self):
        """The defect this item exists for: a non-empty apology used to be ok."""
        apology = ("I'm sorry, an error occurred while generating a response. "
                   "Please try again.")
        assert looks_like_non_answer(apology)
        assert AnswerContract(kind="sentinel_token", token="ok").check(apology).status == STATUS_VIOLATED


class TestNumberContract:
    def test_plain_number_satisfies(self):
        r = AnswerContract(kind="number", number=7519.0).check("The list price is 7519.0.")
        assert r.status == STATUS_SATISFIED

    def test_thousands_separator_and_currency_satisfy(self):
        assert AnswerContract(kind="number", number=7519.0).check("$7,519.00").status == STATUS_SATISFIED

    def test_wrong_number_violates_and_reports_observed(self):
        r = AnswerContract(kind="number", number=7519.0).check("It is 4815 dollars")
        assert r.status == STATUS_VIOLATED and "4815" in r.detail

    def test_no_number_violates(self):
        r = AnswerContract(kind="number", number=7519.0).check("I could not find that row.")
        assert r.status == STATUS_VIOLATED and "none" in r.detail

    def test_required_row_token_must_be_cited(self):
        c = AnswerContract(kind="number", number=7519.0, row_token="R235")
        assert c.check("7519.0").status == STATUS_VIOLATED
        assert c.check("R235 lists 7519.0").status == STATUS_SATISFIED

    def test_parse_numbers_strips_commas(self):
        assert parse_numbers("a 7,519.00 and -12 and 0.5") == [7519.0, -12.0, 0.5]


class TestUnsupportedContract:
    def test_unsupported_is_excluded_not_counted(self):
        r = AnswerContract(kind="unsupported_by_fixture",
                           unsupported_reason="no link to the identifier").check("7519")
        assert r.status == STATUS_UNSUPPORTED
        assert r.supported is False
        assert r.satisfied is None  # neither True nor False

    def test_describe_states_the_reason(self):
        c = AnswerContract(kind="unsupported_by_fixture", unsupported_reason="why not")
        assert "unsupported_by_fixture" in c.describe() and "why not" in c.describe()


class TestFixtureLimitations:
    def test_medium_fixture_has_no_link_to_the_identifier(self):
        from scripts.provider_reliability_replay import _MEDIUM

        assert "F-5216" in _MEDIUM.split("EVIDENCE")[0]  # asked in the question
        evidence = _MEDIUM.split("EVIDENCE:", 1)[1]
        assert "F-5216" not in evidence  # but never present in the evidence

    def test_medium_probe_contract_is_unsupported_by_fixture(self):
        probe = {p.name: p for p in build_workload()}["grounded_medium"]
        assert probe.contract.kind == STATUS_UNSUPPORTED
        assert probe.unsupported_expectations == ("list_price_of_F-5216",)

    def test_large_fixture_formulas_reference_undefined_cells(self):
        from scripts.provider_reliability_replay import _LARGE_EVIDENCE

        assert "R235" in _LARGE_EVIDENCE and "7519.0" in _LARGE_EVIDENCE
        assert "F235" in _LARGE_EVIDENCE and "H235" in _LARGE_EVIDENCE
        # The referenced source cells are never defined in the fixture, and the
        # stated formula cannot produce the stated price.
        assert "F235=" not in _LARGE_EVIDENCE and "H235=" not in _LARGE_EVIDENCE
        assert abs(5350 * 0.9 - 7519.0) > 1

    def test_large_probe_checks_the_supported_part_only(self):
        probe = {p.name: p for p in build_workload()}["derivation_large"]
        assert probe.contract.kind == "number"
        assert probe.contract.number == 7519.0
        assert "formula_chain_derives_7519" in probe.unsupported_expectations

    def test_limitations_are_stated_in_output(self):
        joined = " ".join(fixture_limitations())
        assert "F-5216" in joined and "unsupported" in joined.lower()
        assert "F235" in joined and "H235" in joined


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


class TestSpendLedger:
    def test_retry_cap_blocks_after_the_cap_is_used(self):
        led = SpendLedger(retry_cap=1, spend_cap_usd=100.0)
        assert led.blocked_reason(retry=False) is None
        led.note_attempt(cost=None, cost_estimate=0.0, is_retry=False)
        # no retry used yet for this generation -> the first retry is allowed
        assert led.blocked_reason(retry=True, retries_this_generation=0) is None
        led.note_attempt(cost=None, cost_estimate=0.0, is_retry=True)
        assert led.blocked_reason(retry=True, retries_this_generation=1) == "retry_cap"
        assert led.blocked_by_retry_cap == 1
        assert led.retries_used == 1

    def test_retry_cap_is_per_generation_not_run_wide(self):
        led = SpendLedger(retry_cap=1, spend_cap_usd=100.0)
        led.note_attempt(cost=None, cost_estimate=0.0, is_retry=True)
        # A NEW generation starts with a fresh retry budget.
        assert led.blocked_reason(retry=False, retries_this_generation=0) is None
        assert led.blocked_reason(retry=True, retries_this_generation=0) is None

    def test_retry_cap_zero_forbids_retries(self):
        led = SpendLedger(retry_cap=0, spend_cap_usd=100.0)
        assert led.blocked_reason(retry=True, retries_this_generation=0) == "retry_cap"
        assert led.blocked_reason(retry=False) is None

    def test_spend_cap_blocks_on_reported_cost(self):
        led = SpendLedger(retry_cap=5, spend_cap_usd=0.01)
        assert led.blocked_reason(retry=False) is None
        led.note_attempt(cost=0.02, cost_estimate=None, is_retry=False)
        assert led.blocked_reason(retry=False) == "spend_cap"
        assert led.blocked_by_spend_cap == 1

    def test_spend_cap_charges_the_estimate_when_cost_is_unknown(self):
        led = SpendLedger(retry_cap=5, spend_cap_usd=0.01)
        led.note_attempt(cost=None, cost_estimate=0.02, is_retry=False)
        assert led.cost_unknown_attempts == 1
        assert led.charged_from_estimate == pytest.approx(0.02)
        assert led.blocked_reason(retry=False) == "spend_cap"

    def test_attempt_with_neither_cost_nor_estimate_cannot_be_charged(self):
        led = SpendLedger(retry_cap=5, spend_cap_usd=0.0001)
        led.note_attempt(cost=None, cost_estimate=None, is_retry=False)
        assert led.charged_total == 0.0
        assert led.cost_unknown_attempts == 1
        assert led.blocked_reason(retry=False) is None  # cap cannot bind
        report = led.to_dict(budget_calls=6)
        assert report["effective_caps"] == {
            "budget_calls": 6, "retry_cap": 5, "spend_cap_usd": 0.0001,
        }
        assert "estimate" in report["spend_cap_basis"]


# ---------------------------------------------------------------------------
# Topology (four required states + the fully-independent case)
# ---------------------------------------------------------------------------


class TestTopologyStates:
    def test_all_four_required_states_exist(self):
        for state in (STATE_SOME_SHARED, STATE_ALL_SHARED,
                      STATE_NO_FALLBACK, STATE_UNKNOWN):
            assert state in TOPOLOGY_STATES

    def test_some_shared_fallbacks(self):
        out = classify_fallback_topology(
            ("openrouter", "a"),
            [("openrouter", "b"), ("deepseek", "c")],
        )
        assert out["state"] == STATE_SOME_SHARED
        assert out["shared_providers"] == ["openrouter"]

    def test_all_shared_fallbacks(self):
        out = classify_fallback_topology(
            ("openrouter", "a"),
            [("openrouter", "b"), ("openrouter", "c")],
        )
        assert out["state"] == STATE_ALL_SHARED
        assert out["fallbacks_share_primary_upstream"] is True

    def test_no_shared_fallbacks_is_expressible(self):
        """The boolean could not say this; the state can."""
        out = classify_fallback_topology(
            ("openrouter", "a"),
            [("deepseek", "b"), ("opencode-go", "c")],
        )
        assert out["state"] == STATE_NO_SHARED
        assert out["fallbacks_share_primary_upstream"] is False

    def test_no_fallback(self):
        out = classify_fallback_topology(("openrouter", "a"), [])
        assert out["state"] == STATE_NO_FALLBACK
        assert out["fallback_count"] == 0

    def test_unknown_when_a_fallback_provider_is_unresolvable(self):
        out = classify_fallback_topology(
            ("openrouter", "a"),
            [("unknown", "b"), ("deepseek", "c")],
        )
        assert out["state"] == STATE_UNKNOWN
        assert out["unresolved_fallback_providers"] == ["unknown"]

    def test_unknown_when_primary_provider_missing(self):
        assert classify_fallback_topology(None, [("deepseek", "b")])["state"] == STATE_UNKNOWN
        assert classify_fallback_topology(("", "a"), [("deepseek", "b")])["state"] == STATE_UNKNOWN

    def test_legacy_boolean_key_is_preserved(self):
        out = classify_fallback_topology(("openrouter", "a"), [("openrouter", "b")])
        assert out["fallbacks_share_primary_upstream"] is True
        assert out["fallbacks_sharing_primary_upstream"] == ["openrouter"]

    def test_pairs_are_preserved_not_collapsed_to_model_names(self):
        out = classify_fallback_topology(
            ("openrouter", "shared-model"),
            [("deepseek", "shared-model")],
        )
        assert out["fallback_pairs"] == [{"provider": "deepseek", "model": "shared-model"}]
        assert out["state"] == STATE_NO_SHARED


# ---------------------------------------------------------------------------
# Fallback-name resolution (provider identity must survive)
# ---------------------------------------------------------------------------


class TestResolveFallbackPairs:
    LADDER = [
        ("opencode-go", "gpt-5.3-codex-spark"),
        ("opencode-go", "glm-5.3-flash"),
        ("openrouter", "z-ai/glm-5.3-flash"),
        ("deepseek", "deepseek-reasoner"),
    ]

    def test_names_are_resolved_back_to_pairs(self):
        pairs, unresolved, ambiguous = resolve_fallback_pairs(
            ["glm-5.3-flash", "deepseek-reasoner"], self.LADDER
        )
        assert pairs == [("opencode-go", "glm-5.3-flash"), ("deepseek", "deepseek-reasoner")]
        assert unresolved == [] and ambiguous == {}

    def test_same_name_on_two_gateways_is_ambiguous_not_guessed(self):
        ladder = [("openrouter", "shared"), ("deepseek", "shared")]
        pairs, unresolved, ambiguous = resolve_fallback_pairs(["shared"], ladder)
        assert pairs == [("unknown", "shared")]
        assert ambiguous == {"shared": ["deepseek", "openrouter"]}
        assert unresolved == []

    def test_unknown_name_is_reported_and_makes_topology_unknown(self):
        pairs, unresolved, _ = resolve_fallback_pairs(["mystery-model"], self.LADDER)
        assert pairs == [("unknown", "mystery-model")]
        assert unresolved == ["mystery-model"]
        topo = classify_fallback_topology(("opencode-go", "primary"), pairs)
        assert topo["state"] == STATE_UNKNOWN


# ---------------------------------------------------------------------------
# Streamed first-visible extraction
# ---------------------------------------------------------------------------

def _chunk(text=None, role=None):
    """An OpenAI-style chunk with a single choice."""
    delta = {}
    if role is not None:
        delta["role"] = role
    if text is not None:
        delta["content"] = text
    return {"choices": [{"delta": delta}]}


class TestStreamExtraction:
    def test_role_only_and_empty_deltas_do_not_stamp_first_visible(self):
        chunks = [
            {"choices": []},
            _chunk(role="assistant"),
            _chunk(""),
            _chunk("   "),
            None,
        ]
        assert first_visible_index(chunks) is None
        assert streamed_text(chunks).strip() == ""

    def test_first_content_chunk_stamps(self):
        chunks = [{"choices": []}, _chunk(role="assistant"), _chunk("ok")]
        assert first_visible_index(chunks) == 2

    def test_whitespace_then_content_stamps_on_content(self):
        chunks = [_chunk(" "), _chunk("he"), _chunk("llo")]
        assert first_visible_index(chunks) == 1
        assert streamed_text(chunks) == " he" + "llo"

    def test_object_chunks_are_understood(self):
        chunk = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hi"))]
        )
        assert delta_text(chunk) == "hi"

    def test_content_part_lists_are_flattened(self):
        chunk = {"choices": [{"delta": {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]}
        assert delta_text(chunk) == "ab"

    def test_raw_string_tokens_are_understood(self):
        assert first_visible_index(["", "x"]) == 1


# ---------------------------------------------------------------------------
# Denominators
# ---------------------------------------------------------------------------


def _attempt(**over):
    base = {
        "workload": "planning_short",
        "repeat": 0,
        "generation": 1,
        "prompt_chars": 30,
        "used": {"provider": "openrouter", "model": "z-ai/glm-5.3-flash"},
        "outcome": "ok",
        "contract": {"status": STATUS_SATISFIED, "satisfied": True, "supported": True},
        "first_visible_ms": 120.0,
        "completion_ms": 400.0,
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "cost": None,
        "cost_unknown": True,
        "cost_estimate": 0.0002,
        "looks_like_non_answer": False,
    }
    base.update(over)
    return base


class TestRates:
    def test_rate_with_zero_denominator_is_none_not_zero(self):
        r = rate(0, 0)
        assert r["pct"] is None and r["denominator"] == 0

    def test_rate_carries_numerator_and_denominator(self):
        assert rate(3, 4) == {"pct": 75.0, "numerator": 3, "denominator": 4}


class TestSummarize:
    def test_denominators_are_reported_alongside_every_rate(self):
        attempts = [
            _attempt(),
            _attempt(generation=2, repeat=1,
                     used={"provider": "deepseek", "model": "deepseek-chat"}),
        ]
        s = summarize(attempts, SpendLedger(), budget_calls=6)
        assert s["denominators"]["attempts"] == 2
        assert s["denominators"]["distinct_generations"] == 2
        assert s["denominators"]["provider_model_pairs"] == 2
        assert s["rates"]["contract_pass"] == {
            "pct": 100.0, "numerator": 2, "denominator": 2,
        }
        assert s["rates"]["transport_success"]["denominator"] == 2

    def test_empty_run_has_no_undefined_rate_printed_as_zero(self):
        s = summarize([], SpendLedger(), budget_calls=6)
        assert s["answer_success_rate_pct"] is None
        assert s["zero_output_rate_pct"] is None
        assert s["contract_pass_rate_pct"] is None
        assert s["rates"]["transport_success"]["denominator"] == 0
        assert s["cost"]["cost_per_successful_answer"] is None
        assert s["latency"]["first_visible_ms"]["denominator"] == 0

    def test_unsupported_contracts_are_excluded_from_the_pass_rate(self):
        attempts = [
            _attempt(generation=1),
            _attempt(generation=2,
                     contract={"status": STATUS_UNSUPPORTED, "satisfied": None,
                               "supported": False}),
        ]
        s = summarize(attempts, SpendLedger(), budget_calls=6)
        assert s["denominators"]["contract_checked_attempts"] == 1
        assert s["denominators"]["unsupported_by_fixture_attempts"] == 1
        assert s["rates"]["contract_pass"] == {
            "pct": 100.0, "numerator": 1, "denominator": 1,
        }
        assert s["rates"]["transport_success"]["denominator"] == 2  # still counted

    def test_violated_contract_lowers_the_pass_rate_but_not_transport(self):
        attempts = [
            _attempt(generation=1),
            _attempt(generation=2,
                     contract={"status": STATUS_VIOLATED, "satisfied": False,
                               "supported": True}),
        ]
        s = summarize(attempts, SpendLedger(), budget_calls=6)
        assert s["rates"]["contract_pass"]["pct"] == 50.0
        assert s["rates"]["transport_success"]["pct"] == 100.0

    def test_pairs_are_keyed_by_provider_and_model(self):
        attempts = [
            _attempt(used={"provider": "openrouter", "model": "same-model"}),
            _attempt(generation=2, used={"provider": "deepseek", "model": "same-model"}),
        ]
        s = summarize(attempts, SpendLedger(), budget_calls=6)
        assert set(s["by_provider_model"]) == {
            "openrouter/same-model", "deepseek/same-model",
        }
        # No name-keyed rollup remains: the same model name through two
        # gateways must never collapse into one bucket.
        assert "by_model" not in s

    def test_cost_is_unknown_and_flagged(self):
        s = summarize([_attempt()], SpendLedger(), budget_calls=6)
        assert s["cost"]["cost_unknown_attempts"] == 1
        assert s["cost"]["estimated_total"] == pytest.approx(0.0002)
        assert s["cost"]["cost_per_successful_answer"] is None


# ---------------------------------------------------------------------------
# Transport classification + CLI compatibility
# ---------------------------------------------------------------------------


class TestClassify:
    def test_rate_limit_and_timeout_and_zere_output(self):
        assert classify({"type": "E", "message": "429 Too Many Requests"}, None) == "rate_limited"
        assert classify({"type": "E", "message": "request timed out"}, None) == "timeout"
        assert classify(None, "   ") == "zero_output"
        assert classify(None, "ok") == "ok"
        assert classify({"type": "E", "message": "boom"}, None) == "provider_error"


class TestTransportOutcome:
    """Non-empty output after every provider failed is not transport success."""

    def test_all_attempts_failed_makes_it_a_provider_error(self):
        apology = "I'm sorry, an error occurred while generating a response."
        outcome, all_failed = transport_outcome(
            None, apology, [{"success": False}, {"success": False}]
        )
        assert outcome == "provider_error"
        assert all_failed is True

    def test_one_successful_attempt_is_still_ok(self):
        outcome, all_failed = transport_outcome(
            None, "ok", [{"success": False}, {"success": True}]
        )
        assert outcome == "ok" and all_failed is False

    def test_no_observed_attempts_falls_back_to_content(self):
        assert transport_outcome(None, "ok", []) == ("ok", False)
        assert transport_outcome(None, "", []) == ("zero_output", False)

    def test_explicit_error_wins(self):
        outcome, _ = transport_outcome(
            {"type": "E", "message": "429 too many requests"}, "x", []
        )
        assert outcome == "rate_limited"


class TestCliCompatibility:
    def test_existing_flags_still_parse(self):
        args = build_parser().parse_args(
            ["--topology-only", "--budget-calls", "9", "--repeats", "2",
             "--timeout-s", "12.5", "--json", "out.json", "--markdown", "out.md",
             "--db", "x.db"]
        )
        assert args.topology_only is True
        assert args.budget_calls == 9
        assert args.repeats == 2
        assert args.timeout_s == 12.5
        assert args.json == "out.json" and args.markdown == "out.md"
        assert args.db == "x.db"

    def test_defaults_are_bounded(self):
        args = build_parser().parse_args([])
        assert args.budget_calls == 6
        assert args.retry_cap >= 0
        assert args.spend_cap_usd > 0
        assert args.mode == "stream"
        assert args.fallback_independence is False
        assert args.allow_learning_writes is False

    def test_new_flags_parse(self):
        args = build_parser().parse_args(
            ["--mode", "completion", "--retry-cap", "3", "--spend-cap-usd", "0.25",
             "--fallback-independence", "--force-primary-provider", "deepseek",
             "--force-primary-model", "nope", "--fallback-limit", "2"]
        )
        assert args.mode == "completion"
        assert args.retry_cap == 3
        assert args.spend_cap_usd == 0.25
        assert args.fallback_independence is True
        assert args.force_primary_provider == "deepseek"
        assert args.force_primary_model == "nope"
        assert args.fallback_limit == 2


class TestProbe:
    def test_probe_is_frozen_and_contract_checkable(self):
        p = Probe(name="p", kind="planning", prompt="hi",
                  contract=AnswerContract(kind="sentinel_token", token="ok"))
        assert p.contract.check("ok").satisfied is True
        with pytest.raises(Exception):
            p.name = "other"  # frozen dataclass


# ---------------------------------------------------------------------------
# Caps enforced inside the replay loop (stubbed handler, no network)
# ---------------------------------------------------------------------------


class _StubHandler:
    """Minimal BYOKHandler stand-in: always answers, never satisfies a contract."""

    calls: list = []

    def __init__(self, reply="not the sentinel", **kwargs):
        self.reply = reply
        self._record_outcome_feedback = lambda *a, **k: None

    def analyze_query_complexity(self, prompt, kind=None):
        return "SIMPLE"

    def get_ranked_providers(self, complexity):
        return [("provider-a", "model-a"), ("provider-b", "model-b")]

    def get_available_providers(self):
        return ["provider-a", "provider-b"]

    async def stream_completion(self, **kwargs):
        _StubHandler.calls.append(kwargs)
        yield self.reply


def _args(**over):
    base = {
        "mode": "stream", "budget_calls": 10, "retry_cap": 1,
        "spend_cap_usd": 1000.0, "repeats": 1, "timeout_s": 5.0,
        "max_tokens": 16, "allow_learning_writes": True,
        "fallback_independence": False, "fallback_limit": 2,
        "force_primary_provider": None, "force_primary_model": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


class TestReplayLoopCaps:
    def _replay(self, monkeypatch, **over):
        import asyncio

        import core.llm.byok_handler as byok

        _StubHandler.calls = []
        monkeypatch.setattr(byok, "BYOKHandler", _StubHandler)
        from scripts.provider_reliability_replay import replay

        return asyncio.run(replay(_args(**over)))

    def test_retry_cap_bounds_attempts_per_generation(self, monkeypatch):
        run = self._replay(monkeypatch, retry_cap=1)
        attempts = run["attempts"]
        # planning + large: 1 attempt + 1 retry each, then blocked by the cap.
        # grounded_medium: its contract is unsupported_by_fixture, so it is
        # excluded from the pass rate and must NOT consume retries.
        assert [a["workload"] for a in attempts] == [
            "planning_short", "planning_short",
            "grounded_medium",
            "derivation_large", "derivation_large",
        ]
        assert [a["retry_index"] for a in attempts] == [0, 1, 0, 0, 1]
        assert [a["retry"] for a in attempts] == [False, True, False, False, True]
        assert [b["reason"] for b in run["blocked"]] == ["retry_cap"] * 2
        assert run["ledger"].blocked_by_retry_cap == 2
        assert run["ledger"].retries_used == 2

    def test_retry_cap_zero_makes_every_generation_single_attempt(self, monkeypatch):
        run = self._replay(monkeypatch, retry_cap=0)
        assert len(run["attempts"]) == 3
        assert all(a["retry"] is False for a in run["attempts"])
        assert run["ledger"].retries_used == 0

    def test_budget_calls_bounds_total_attempts(self, monkeypatch):
        run = self._replay(monkeypatch, budget_calls=2, retry_cap=5)
        assert len(run["attempts"]) == 2
        assert run["blocked"][-1]["reason"] == "budget_calls"
        assert run["ledger"].attempts == 2

    def test_spend_cap_stops_the_loop(self, monkeypatch):
        run = self._replay(monkeypatch, spend_cap_usd=0.0)
        assert run["attempts"] == []
        assert run["blocked"][0]["reason"] == "spend_cap"

    def test_contract_violation_is_what_drives_a_retry(self, monkeypatch):
        run = self._replay(monkeypatch, retry_cap=0)
        first = run["attempts"][0]
        assert first["outcome"] == "ok"           # transport succeeded
        assert first["contract"]["satisfied"] is False  # contract did not
        assert first["retry"] is False            # but the cap forbade a retry
