"""Checker unit tests for the BPC tier benchmark battery.

The battery's credibility rests on its checkers: every checker type is tested
here against hand-built PASS/FAIL/INCONCLUSIVE samples so a benchmark FAIL
can only mean the model, never the grader. Mirrors the runner's check()
exactly (imported from scripts/bpc_tier_benchmark.py).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bpc_tier_benchmark.py"
_spec = importlib.util.spec_from_file_location("bpc_tier_benchmark", _SCRIPT)
_bench = importlib.util.module_from_spec(_spec)
sys.modules["bpc_tier_benchmark"] = _bench
_spec.loader.exec_module(_bench)
check = _bench.check

BATTERY = json.load(open(_SCRIPT.parent / "bpc_tier_battery.json"))
TASKS = {t["id"]: t for t in BATTERY["tasks"]}


def _checker_task(checker):
    return {"tier": "simple", "checker": checker, "prompt": "x", "max_tokens": 1}


class TestCheckerTypes:
    def test_all_strings(self):
        c = {"type": "all_strings", "strings": ["PO-77142", "Priya Shah"]}
        assert check(_checker_task(c), "PO number PO-77142 with Priya Shah.")[0] == "PASS"
        assert check(_checker_task(c), "PO-77142 only")[0] == "FAIL"

    def test_numeric_exact_and_missing(self):
        c = {"type": "numeric", "value": 4030, "tolerance": 0.5}
        assert check(_checker_task(c), "The total is 4,030.")[0] == "PASS"
        assert check(_checker_task(c), "The total is 4029.")[0] == "FAIL"
        assert check(_checker_task(c), "I cannot compute.")[0] == "INCONCLUSIVE"

    def test_sequence_order_insensitive_lines(self):
        c = {"type": "sequence", "expect": ["A: APPROVED", "B: DENIED"]}
        assert check(_checker_task(c), "A: APPROVED\nB: DENIED")[0] == "PASS"
        assert check(_checker_task(c), "1) A: APPROVED\n2) B: DENIED")[0] == "PASS"
        assert check(_checker_task(c), "A: DENIED\nB: DENIED")[0] == "FAIL"

    def test_max_words_constraint(self):
        c = {"type": "max_words", "limit": 5, "must_include_any": [["revenue"]]}
        assert check(_checker_task(c), "Revenue grew 12% overall.")[0] == "PASS"
        assert check(_checker_task(c), "Revenue grew 12% overall and churn held flat at 2.1 percent.")[0] == "FAIL"
        assert check(_checker_task(c), "Sales up.")[0] == "FAIL"

    def test_json_fields_comma_normalization(self):
        c = {"type": "json_fields", "normalize_commas": True,
             "fields": {"tags": "beta, vip"}}
        assert check(_checker_task(c), '{"tags": "beta,vip"}')[0] == "PASS"
        assert check(_checker_task(c), '{"tags": "vip, beta"}')[0] == "FAIL"

    def test_json_fields_with_dotted_args(self):
        c = {"type": "json_fields", "fields": {
            "tool": "search_orders", "args.limit": 5,
            "args.status": "delivered", "amount": 10.0}}
        good = '{"tool": "search_orders", "args": {"limit": 5, "status": "delivered"}, "amount": 10.0}'
        assert check(_checker_task(c), f"```json\n{good}\n```")[0] == "PASS"
        bad = '{"tool": "refund_order", "args": {"limit": 5, "status": "delivered"}, "amount": 10.0}'
        assert check(_checker_task(c), bad)[0] == "FAIL"
        assert check(_checker_task(c), "here you go, no json")[0] == "INCONCLUSIVE"

    def test_schedule_constraint(self):
        c = {"type": "schedule_constraint",
             "busy": {"Alice": ["Monday", "Tuesday"], "Bob": ["Wednesday-before-12"]},
             "required": {"Client": "Friday"}}
        ok1 = "Alice: Wednesday 10:00\nBob: Thursday 11:00\nClient: Friday 09:00"
        assert check(_checker_task(c), ok1)[0] == "PASS"
        # Bob on Wednesday is valid only in the afternoon.
        ok2 = "Alice: Thursday 10:00\nBob: Wednesday 14:00\nClient: Friday 09:00"
        assert check(_checker_task(c), ok2)[0] == "PASS"
        assert check(_checker_task(c), "Alice: Monday 10:00\nBob: Thursday 11:00\nClient: Friday 09:00")[0] == "FAIL"
        assert check(_checker_task(c), "Alice: Wednesday 10:00\nBob: Wednesday 15:00\nClient: Friday 09:00")[0] == "FAIL"
        # Day abbreviations must be accepted.
        assert check(_checker_task(c), "Alice: Wed 09:00\nBob: Thu 11:00\nClient: Fri 09:00")[0] == "PASS"

    def test_labeled_numerics(self):
        c = {"type": "labeled_numerics",
             "labels": {"Q2_YOY": 25.0, "H1_2026": "North"}, "tolerance": 0.05}
        assert check(_checker_task(c), "Q2_YOY: 25.0\nH1_2026: North")[0] == "PASS"
        assert check(_checker_task(c), "Q2_YOY: 24.97\nH1_2026: North")[0] == "PASS"
        assert check(_checker_task(c), "Q2_YOY: 30\nH1_2026: South")[0] == "FAIL"

    def test_constraint_set(self):
        c = {"type": "constraint_set", "max_words": 60, "constraints": [
            {"tag": "[RETRY]", "min_len": 10, "requires_digit": True},
            {"tag": "[POISON]", "min_len": 10}]}
        good = "[RETRY] 3 attempts with 5s backoff\n[POISON] moved to dead-letter queue"
        assert check(_checker_task(c), good)[0] == "PASS"
        assert check(_checker_task(c), "[RETRY] retries happen\n[POISON] moved to dead-letter queue")[0] == "FAIL"
        assert check(_checker_task(c), "[POISON] moved to dead-letter queue")[0] == "FAIL"

    def test_set_match_min(self):
        c = {"type": "set_match_min", "min": 4,
             "categories_any_of": [["INJECTION"], ["AUTHZ"], ["SECRET", "LOGGING"], ["XSS"], ["SSRF"]]}
        assert check(_checker_task(c), "1. INJECTION\n2. AUTHZ\n3. SECRET\n4. XSS\n5. SSRF")[0] == "PASS"
        assert check(_checker_task(c), "1. LOGGING (covers secret leak)\n2. INJECTION\n3. XSS")[0] == "FAIL"

    def test_code_asserts_pass_and_fail(self):
        c = {"type": "code_asserts", "setup": "from sol import top_words",
             "asserts": ["top_words('b a b a', 1) == ['a']"]}
        good = "```python\ndef top_words(text, n):\n    ws = text.lower().split()\n    cs = {w: ws.count(w) for w in set(ws)}\n    return sorted(cs, key=lambda w: (-cs[w], w))[:n]\n```"
        verdict, _ = check(_checker_task(c), good)
        assert verdict == "PASS"
        bad = "```python\ndef top_words(text, n):\n    return []\n```"
        assert check(_checker_task(c), bad)[0] == "FAIL"
        assert check(_checker_task(c), "I would write a function.")[0] == "INCONCLUSIVE"

    def test_exact_text(self):
        c = {"type": "exact_text", "value": "a,b\nx,y"}
        assert check(_checker_task(c), "a,b\nx,y")[0] == "PASS"
        assert check(_checker_task(c), "a, b\nx, y")[0] == "FAIL"


class TestBatteryIntegrity:
    def test_battery_loads_and_is_complete(self):
        assert len(BATTERY["tasks"]) == 20
        tiers = {t["tier"] for t in BATTERY["tasks"]}
        assert tiers == {"simple", "moderate", "complex", "advanced"}
        assert len({t["id"] for t in BATTERY["tasks"]}) == 20

    def test_every_checker_type_known(self):
        known = {"all_strings", "sequence", "max_words", "numeric", "string_set",
                 "exact_text", "json_fields", "labeled_numerics", "constraint_set",
                 "set_match_min", "code_asserts", "schedule_constraint"}
        for t in BATTERY["tasks"]:
            assert t["checker"]["type"] in known, t["id"]

    def test_gradeable_checkers_dont_crash_on_empty(self):
        for t in BATTERY["tasks"]:
            if t["checker"]["type"] == "code_asserts":
                continue  # needs a code block; empty -> INCONCLUSIVE anyway
            verdict, _ = check(t, "")
            assert verdict in ("PASS", "FAIL", "INCONCLUSIVE"), t["id"]
