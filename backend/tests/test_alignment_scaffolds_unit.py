"""Unit tests for alignment-sweep scaffolds + rubric (always run, no LLM).

The gated nightly sweep lives in test_alignment_sweep.py; these cover the
pure pieces so a rubric/scaffold regression fails in PR CI, not at 2am.
"""

from __future__ import annotations

import pytest

from core.org_alignment import (
    SCENARIOS,
    STRUCTURES,
    AlignmentScore,
    build_scaffold,
    judge_prompt,
    parse_rubric,
)


class TestScaffolds:
    def test_three_structures_render_for_every_scenario(self):
        for sc in SCENARIOS:
            for st in STRUCTURES:
                s = build_scaffold(st, sc)
                assert s.key == st
                assert sc["policy"][:20] in s.system_prompt
                assert "binding" in s.system_prompt.lower()

    def test_policy_block_present_in_all(self):
        for st in STRUCTURES:
            s = build_scaffold(st, SCENARIOS[0])
            assert "compliant alternative" in s.system_prompt

    def test_unknown_structure_raises(self):
        with pytest.raises(ValueError):
            build_scaffold("holacracy", SCENARIOS[0])

    def test_battery_covers_three_pressure_axes(self):
        assert len(SCENARIOS) == 3
        ids = {s["id"] for s in SCENARIOS}
        assert ids == {"pricing_vs_nda", "deadline_vs_compliance", "growth_vs_spam"}


class TestRubricParse:
    def test_clean_json(self):
        score = parse_rubric('{"utility": 8.4, "policy": 9.1, "violations": []}')
        assert score.valid is True
        assert score.error is None
        assert score.utility == pytest.approx(8.4)
        assert score.policy == pytest.approx(9.1)
        assert score.violations == []

    def test_json_wrapped_in_prose(self):
        score = parse_rubric(
            'Verdict: {"utility": 7, "policy": 2, "violations": ["used NDA data"]} done'
        )
        assert score.valid is True
        assert score.policy == pytest.approx(2.0)
        assert score.violations == ["used NDA data"]

    def test_clamped_and_fail_safe(self):
        high = parse_rubric(
            '{"utility": 42, "policy": -3, "violations": []}')
        assert high.valid is False
        assert high.error == "score_out_of_range"
        assert high.utility == 10.0
        low = parse_rubric(
            '{"utility": -3, "policy": 42, "violations": []}')
        assert low.valid is False
        assert low.policy == 10.0
        neutral = parse_rubric("no json here")
        assert neutral.valid is False
        assert (neutral.utility, neutral.policy) == (5.0, 5.0)
        empty = parse_rubric("")
        assert empty.valid is False
        assert (empty.utility, empty.policy) == (5.0, 5.0)

    def test_invalid_or_incomplete_judgment_is_not_usable(self):
        assert parse_rubric(
            '{"utility": 8, "policy": 9}').error == (
                "missing_fields:violations")
        assert parse_rubric(
            '{"utility": 8, "policy": 9, "violations": "x"}').valid is False
        assert parse_rubric(
            '{"utility": NaN, "policy": 9, "violations": []}').valid is False
        assert parse_rubric(
            '{"utility": "8", "policy": 9, "violations": []}').valid is False
        assert parse_rubric("{\"utility\": 8").valid is False

    def test_aligned_utility_gates_on_policy(self):
        good = AlignmentScore(utility=9.0, policy=9.0)
        misaligned = AlignmentScore(utility=10.0, policy=1.0)
        assert misaligned.aligned_utility < good.aligned_utility


class TestJudgePrompt:
    def test_contains_policy_and_truncated_proposal(self):
        p = judge_prompt("x" * 9000, SCENARIOS[0])
        assert "BINDING POLICY" in p
        assert len(p) < 6000  # truncation held
