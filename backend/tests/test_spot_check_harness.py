"""Tests for spot-check harness purity (blinding + grading truth table)."""

import os
os.environ["TESTING"] = "1"

import importlib.util
import random


def _script():
    import pathlib
    path = (pathlib.Path(__file__).resolve().parents[2]
            / "scripts" / "spot_check_intent.py")
    spec = importlib.util.spec_from_file_location("spot_check_intent", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestHarness:
    def test_blind_lines_name_no_model(self):
        sp = _script()
        for line in sp.format_blind(("chat", 0.9), ("task", 0.6)):
            assert "LLM" not in line and "ollaya" not in line

    def test_grading_truth_table(self):
        sp = _script()
        assert sp.grade_answer("a", "LLM", "ollaya") == (True, False)
        assert sp.grade_answer("b", "LLM", "ollaya") == (False, True)
        assert sp.grade_answer("a", "ollaya", "LLM") == (False, True)
        assert sp.grade_answer("both", "LLM", "ollaya") == (True, True)
        assert sp.grade_answer("neither", "LLM", "ollaya") == (False, False)
        assert sp.grade_answer("skip", "LLM", "ollaya") is None
        assert sp.grade_answer("", "LLM", "ollaya") is None
        assert sp.grade_answer("xyz", "LLM", "ollaya") is None

    def test_blind_never_leaks_failure_sources(self):
        # Failure paths carry model-identifying strings: ollaya's source
        # flag can be literally "ollaya"/"fallback"/"breaker"/"disabled",
        # the LLM path surfaces exception class names. None may reach
        # the grader (regression: "A: None (ollaya)" was displayed).
        sp = _script()
        bad_picks = [(None, "ollaya"), (None, "fallback"), (None, "breaker"),
                     (None, "disabled"), (None, "TimeoutError"), (None, None)]
        banned = ("llm", "ollaya", "fallback", "breaker", "disabled",
                  "timeouterror")
        for bad in bad_picks:
            for lines in (sp.format_blind(bad, ("chat", 0.9)),
                          sp.format_blind(("task", 0.75), bad)):
                for line in lines:
                    low = line.lower()
                    for token in banned:
                        assert token not in low, f"{token!r} leaked in {line!r}"
            assert sp.format_blind(bad, ("chat", 0.9))[0].endswith("(n/a)")

    def test_blind_shows_numeric_confidence(self):
        sp = _script()
        assert sp.format_blind(("chat", 0.9), ("task", 0.6)) == [
            "  A: chat (0.90)", "  B: task (0.60)"]

    def test_shuffle_preserves_sides(self):
        sp = _script()
        (l1, _), (l2, _) = sp.build_sides(("chat", 1), ("task", 2), random.Random(7))
        assert sorted([l1, l2]) == ["LLM", "ollaya"]
