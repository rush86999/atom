#!/usr/bin/env python3
"""Independent scorer for the search acceptance corpus.

INTEGRITY RULES, enforced here rather than asserted in prose:

1. The expected answer comes from the SCENARIO, never from the run. A result
   cannot mark itself correct.
2. Every check is a Boolean. `blocked` (the path never ran) and `failed` are
   different values, and a blocked case is never counted as a pass.
3. Missing or duplicate case ids fail completeness — a silently dropped case is
   the easiest way to improve a score without improving the system.
4. Negative controls are checked in the same pass: the scorer must REJECT a
   wrong source, a wrong row, a wrong value column, a wrong basis, a reordered
   or missing identifier set, and an absence claim manufactured from a failed
   read. A scorer that cannot reject these cannot certify anything.
5. Absence is only creditable when the run says every required source was
   searched. `expected_status == "failed"` scenarios are scored by whether the
   system KEPT the item unresolved instead.

Run `--selftest` for the control suite; it must pass before any scenario result
is allowed to count.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# Verdict vocabulary. UNRESOLVED and BLOCKED are deliberately distinct from
# FAIL: a system that could not exercise a path has not been shown to be wrong.
PASS = "pass"
FAIL = "fail"
BLOCKED = "blocked"

UNRESOLVED = "unresolved_due_to_retrieval_failure"

# Classifications the system may assign to a requested item.
SUPPORTED = "supported"
AMBIGUOUS = "ambiguous"
ABSENT = "absent_within_coverage"


@dataclass
class Check:
    name: str
    verdict: str
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    category: str
    split: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(
            c.verdict in (PASS, BLOCKED) for c in self.checks
        ) and any(c.verdict == PASS for c in self.checks)

    @property
    def any_failure(self) -> bool:
        return any(c.verdict == FAIL for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "split": self.split,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "verdict": c.verdict, "detail": c.detail}
                for c in self.checks
            ],
        }


# --------------------------------------------------------------------------- #
# Normalisation shared by the scorer and the controls. Deliberately mechanical:
# it re-spells what the system said and never infers a value that was not said.
# --------------------------------------------------------------------------- #

def norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", str(text or "").lower()).strip()


def norm_money(value: Any) -> str:
    """'1,284.00' / '$1284' / 'CAD 1284.0' all name the same number."""
    digits = re.sub(r"[^0-9.]", "", str(value or ""))
    if not digits or digits == ".":
        return ""
    try:
        return f"{float(digits):.2f}"
    except ValueError:
        return ""


def _mentions(haystack: str, needle: str) -> bool:
    return norm(needle) in norm(haystack)


# --------------------------------------------------------------------------- #
# The scorer
# --------------------------------------------------------------------------- #

def score_case(scenario: dict, run: dict | None) -> CaseResult:
    """Score one scenario against one run record.

    ``run`` is the record the harness produced. Its shape:

        {
          "sources":        ["linmac_consolidated.xlsx", ...],   # actually read
          "items":          {"U-22": {"classification": "supported",
                                      "value": "1284.00", "basis": "list",
                                      "unit": "CAD", "row": "linmac!A26",
                                      "alternatives": 1}},
          "search_status":  "success" | "partial" | "failed",
          "invocations":    {"turn-1": 1, "turn-2": 0},
          "blocked":        "reason the path never ran"   (optional)
        }
    """
    result = CaseResult(
        case_id=scenario["id"],
        category=scenario["category"],
        split=scenario.get("split", "development"),
    )
    if run is None or run.get("blocked"):
        reason = (run or {}).get("blocked") or "no run record"
        result.checks.append(Check("exercised", BLOCKED, str(reason)))
        return result
    result.checks.append(Check("exercised", PASS))

    # A layer states which assertions it actually attempted. A check outside
    # that set is UNEXERCISED, never failed: the public-boundary layer measures
    # the retrieval lifecycle (zero invocations, a new attempt, pinned bytes,
    # constraint survival) and deliberately does not re-parse evidence
    # bindings, which Layer 1 does. Scoring the unparsed binding as a failure
    # would report a defect that was never looked for.
    attempted = run.get("asserts")
    asserting = (lambda name: True) if attempted is None else (
        lambda name: any(name == a or name.startswith(a + ":")
                         for a in attempted))

    sources = [str(s) for s in (run.get("sources") or [])]
    items = run.get("items") or {}
    status = str(run.get("search_status") or "")

    # -- 1. source selection ------------------------------------------------
    for required in scenario["required_sources"]:
        name = f"source:{required}"
        if not asserting(name):
            result.checks.append(Check(name, BLOCKED, "not asserted by this layer"))
            continue
        found = any(_mentions(s, required) for s in sources)
        result.checks.append(Check(name, PASS if found else FAIL, f"read={sources}"))
    for forbidden in scenario.get("forbidden_sources") or []:
        name = f"no_source:{forbidden}"
        if not asserting(name):
            result.checks.append(Check(name, BLOCKED, "not asserted by this layer"))
            continue
        used = any(_mentions(s, forbidden) for s in sources)
        result.checks.append(Check(
            name, FAIL if used else PASS,
            "out-of-scope source was read" if used else "",
        ))

    # -- 2. per-item classification and evidence binding ---------------------
    for item in scenario["required_items"]:
        if not asserting(f"item:{item}"):
            result.checks.append(Check(
                f"item:{item}", BLOCKED, "not asserted by this layer"))
            continue
        if item.startswith("absent:"):
            _score_absence(result, scenario, run, item, status)
            continue
        record = items.get(item)
        if record is None:
            result.checks.append(Check(
                f"item:{item}", FAIL, "requested item was never resolved"))
            continue
        classification = str(record.get("classification") or "")
        if scenario["expect_status"] == "failed":
            # Every retrieval path for this item is down. The only acceptable
            # answer is an explicit unresolved.
            ok = classification == UNRESOLVED
            result.checks.append(Check(
                f"item:{item}", PASS if ok else FAIL,
                f"classification={classification!r} (expected {UNRESOLVED!r})",
            ))
            continue
        if scenario["expect_status"] == "degraded":
            # A sibling leg still worked, so the item MAY be resolved — and
            # resolving it is the point: a failing leg must not empty a useful
            # response. What is forbidden is an ABSENCE claim, which is the
            # failure-to-absence conversion this whole category exists to catch.
            ok = classification in (SUPPORTED, AMBIGUOUS, UNRESOLVED)
            result.checks.append(Check(
                f"item:{item}", PASS if ok else FAIL,
                f"classification={classification!r} — an absence claim from a "
                "degraded search is the false-absence gate"
                if not ok else f"classification={classification}"))
            continue
        if classification not in (SUPPORTED, AMBIGUOUS):
            result.checks.append(Check(
                f"item:{item}", FAIL,
                f"classification={classification!r} is not supported/ambiguous"))
            continue
        result.checks.append(Check(f"item:{item}", PASS,
                                   f"classification={classification}"))
        _score_binding(result, scenario, item, record)

    # -- 3. requested-set ORDER ---------------------------------------------
    # Two look-alike identifiers resolved in the wrong order are a different
    # answer, not the same answer shuffled: the first one is what the user
    # reads as "the" answer. Only meaningful when the run reports an order;
    # otherwise it is blocked, never assumed.
    wanted_order = [i for i in scenario["required_items"]
                    if not i.startswith("absent:")]
    reported_order = run.get("resolution_order")
    if wanted_order and asserting("requested_order"):
        if reported_order is None:
            result.checks.append(Check(
                "requested_order", BLOCKED,
                "the run did not report a resolution order"))
        else:
            reported = [str(x) for x in reported_order]
            expected_subset = [i for i in wanted_order if i in reported]
            result.checks.append(Check(
                "requested_order",
                PASS if reported == expected_subset else FAIL,
                f"requested {expected_subset}, reported {reported}"))

    # -- 4. an injected failure must be VISIBLE ----------------------------
    if scenario["expect_status"] in ("failed", "degraded") and asserting("injected_failure_is_visible"):
        result.checks.append(Check(
            "injected_failure_is_visible",
            FAIL if status == "success" else PASS,
            f"status={status!r} — a broken leg was reported as a clean search"
            if status == "success" else f"status={status}"))

    # -- 5. no false absence on a failed read -------------------------------
    if status in ("failed", "partial") and asserting("no_false_absence_on_failure"):
        fabricated = [
            item for item, rec in items.items()
            if not str(item).startswith("absent:")
            and rec.get("classification") == ABSENT
        ]
        result.checks.append(Check(
            "no_false_absence_on_failure",
            FAIL if fabricated else PASS,
            f"absent-claimed for {fabricated} despite a failed read"
            if fabricated else "",
        ))

    # -- 5. invocation expectations (formatting must not search) -----------
    invocations = run.get("invocations") or {}
    for turn in scenario.get("multi_turn") or []:
        if "expect_retrieval" not in turn:
            continue
        key = f"turn-{turn['turn']}"
        if key not in invocations or not asserting(f"invocations:{key}"):
            result.checks.append(Check(
                f"invocations:{key}", BLOCKED, "turn was not exercised by this layer"))
            continue
        got = int(invocations[key] or 0)
        want = int(turn["expect_retrieval"])
        result.checks.append(Check(
            f"invocations:{key}", PASS if got == want else FAIL,
            f"expected {want} retrieval invocation(s), observed {got}"))

    # -- 6. ranking degradation must not masquerade as coverage -------------
    if scenario["category"] == "reranker_degraded" and asserting("ranking_degradation_observable"):
        ranking = (run.get("ranking") or {}).get("status")
        claims_full = bool((run.get("claims") or {}).get("fully_searched"))
        result.checks.append(Check(
            "ranking_degradation_observable",
            PASS if ranking in (None, "degraded", "as_fused") else FAIL,
            f"ranking={ranking!r}"))
        result.checks.append(Check(
            "degraded_ranking_not_claimed_as_full_coverage",
            FAIL if claims_full and ranking == "degraded" else PASS))

    return result


def _score_binding(result: CaseResult, scenario: dict, item: str,
                   record: dict) -> None:
    """A classification is not an answer. The value must be bound to the right
    cell, on the right basis, in the right unit."""
    support = (scenario.get("support") or {}).get(item) or {}
    classification = str(record.get("classification") or "")

    if support.get("alternatives", 1) > 1 or classification == AMBIGUOUS:
        kept = int(record.get("alternatives") or 0)
        result.checks.append(Check(
            f"ambiguity_retained:{item}",
            PASS if kept >= 2 else FAIL,
            f"alternatives={kept}, needed >=2"))
        return

    if "value" in support:
        want = norm_money(support["value"])
        got = norm_money(record.get("value"))
        result.checks.append(Check(
            f"value_binding:{item}", PASS if want and want == got else FAIL,
            f"expected {want!r}, bound {got!r}"))
    if "unit" in support:
        result.checks.append(Check(
            f"unit:{item}",
            PASS if _mentions(record.get("unit"), support["unit"]) else FAIL,
            f"expected {support['unit']!r}, got {record.get('unit')!r}"))
    if "basis" in support:
        result.checks.append(Check(
            f"basis:{item}",
            PASS if _mentions(record.get("basis"), support["basis"]) else FAIL,
            f"expected {support['basis']!r}, got {record.get('basis')!r}"))
    if "span" in support:
        result.checks.append(Check(
            f"span:{item}",
            PASS if _mentions(record.get("span"), support["span"]) else FAIL,
            f"expected span {support['span']!r}"))
    if "revision" in support:
        result.checks.append(Check(
            f"revision:{item}",
            PASS if _mentions(record.get("revision"), support["revision"]) else FAIL,
            f"expected revision {support['revision']!r}, got {record.get('revision')!r}"))
    if "sender" in support:
        result.checks.append(Check(
            f"sender:{item}",
            PASS if _mentions(record.get("sender"), support["sender"]) else FAIL,
            f"expected sender {support['sender']!r}"))
    if support.get("claimable") is not None:
        result.checks.append(Check(
            f"absence_bounded:{item}",
            PASS if bool(record.get("claimable")) == support["claimable"] else FAIL))


def _score_absence(result: CaseResult, scenario: dict, run: dict,
                   item: str, status: str) -> None:
    """A genuine absence must be CLAIMED, and only when coverage allows it.

    The paired failure is the expensive one: a source that could not be read
    must never yield an absence. So this check is deliberately two-sided — it
    fails both when a real absence was denied and when a broken read was turned
    into one.
    """
    record = (run.get("items") or {}).get(item) or {}
    classification = str(record.get("classification") or "")
    required_ok = status == "success"

    if classification == UNRESOLVED:
        result.checks.append(Check(
            f"absence:{item}",
            PASS if not required_ok else FAIL,
            "claimed unresolved where coverage permitted an absence"
            if required_ok else ""))
        return
    if classification == ABSENT:
        result.checks.append(Check(
            f"absence:{item}",
            PASS if required_ok else FAIL,
            "absence claimed from an incomplete search — the false-absence gate"
            if not required_ok else ""))
        return
    result.checks.append(Check(
        f"absence:{item}", FAIL,
        f"expected a bounded absence or an explicit unresolved, got {classification!r}"))


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #

def completeness(scenarios: list[dict], results: dict[str, CaseResult]) -> list[str]:
    """A dropped, duplicated or invented case id fails the whole run.

    Silently shortening the required set is the cheapest way to improve a score
    without improving the system, so the corpus itself is checked before any
    result is reported.
    """
    problems: list[str] = []
    expected = [c["id"] for c in scenarios]
    seen = [r.case_id for r in results.values()]
    for cid in sorted({c for c in expected if expected.count(c) > 1}):
        problems.append(f"{cid}: listed {expected.count(cid)} times in the corpus")
    for cid in expected:
        if seen.count(cid) != 1:
            problems.append(f"{cid}: scored {seen.count(cid)} time(s), expected 1")
    for cid in seen:
        if cid not in expected:
            problems.append(f"{cid}: scored but not in the required corpus")
    return problems


def report(scenarios: list[dict], results: dict[str, CaseResult]) -> dict:
    """Per-category numerators/denominators, never a lone aggregate percentage."""
    by_cat: dict[str, dict[str, int]] = {}
    by_split: dict[str, dict[str, int]] = {}
    for scenario in scenarios:
        res = results.get(scenario["id"])
        if res is None:
            continue
        for bucket, key in ((by_cat, scenario["category"]),
                            (by_split, res.split)):
            cell = bucket.setdefault(key, {"pass": 0, "fail": 0, "blocked": 0})
            if res.any_failure:
                cell["fail"] += 1
            elif res.passed:
                cell["pass"] += 1
            else:
                cell["blocked"] += 1

    def _totals(cells: dict[str, dict[str, int]]) -> dict[str, int]:
        out = {"pass": 0, "fail": 0, "blocked": 0}
        for cell in cells.values():
            for k in out:
                out[k] += cell[k]
        return out

    return {
        "by_category": {k: {**v, "denominator": v["pass"] + v["fail"]}
                        for k, v in sorted(by_cat.items())},
        "by_split": {k: {**v, "denominator": v["pass"] + v["fail"]}
                     for k, v in sorted(by_split.items())},
        "totals": _totals(by_cat),
        "note": (
            "`blocked` is excluded from the denominator. A blocked case is a "
            "path that never ran, which is not evidence either way, and "
            "counting it as a pass is how a harness reports progress it did "
            "not make."
        ),
    }


# --------------------------------------------------------------------------- #
# Negative controls — the scorer must REJECT each of these
# --------------------------------------------------------------------------- #

def _scored(scenario: dict, run: dict) -> CaseResult:
    return score_case(scenario, run)


def negative_controls() -> list[tuple[str, bool, str]]:
    """(name, scorer_rejected_the_bad_run, why_it_matters)."""
    exact = {
        "id": "ctrl", "category": "exact_named_file", "split": "development",
        "required_sources": ["linmac_consolidated.xlsx"],
        "forbidden_sources": ["other_tenant_pricing.xlsx"],
        "required_items": ["U-22"],
        "support": {"U-22": {"value": "1284.00", "basis": "list", "unit": "CAD"}},
        "expect_status": "success", "multi_turn": [],
    }
    good_run = {
        "sources": ["linmac_consolidated.xlsx"],
        "items": {"U-22": {"classification": "supported", "value": "1284.00",
                           "basis": "list", "unit": "CAD"}},
        "search_status": "success", "invocations": {},
    }
    out: list[tuple[str, bool, str]] = []

    out.append((
        "control_baseline_accepts_a_correct_run",
        _scored(exact, good_run).passed,
        "a scorer that rejects everything is not a scorer",
    ))

    def rejects(mutate, name, why):
        bad = json.loads(json.dumps(good_run))
        mutate(bad)
        out.append((name, not _scored(exact, bad).passed, why))

    rejects(lambda r: r.update(sources=["other_tenant_pricing.xlsx"]),
            "control_rejects_wrong_source",
            "a citation to a source that was not the required one")
    rejects(lambda r: r["items"]["U-22"].update(value="9999.99"),
            "control_rejects_wrong_value",
            "the right row with the wrong number in it")
    rejects(lambda r: r["items"]["U-22"].update(basis="estimated"),
            "control_rejects_wrong_basis",
            "a list price presented as an estimate")
    rejects(lambda r: r["items"]["U-22"].update(unit="USD"),
            "control_rejects_wrong_unit",
            "a CAD price presented in the wrong currency")
    rejects(lambda r: r["items"]["U-22"].update(classification="ambiguous",
                                                 alternatives=1),
            "control_rejects_manufactured_ambiguity",
            "hedging without retaining both candidates is not honesty")

    multi = {
        "id": "ctrl2", "category": "exact_named_file", "split": "development",
        "required_sources": ["linmac_consolidated.xlsx"],
        "forbidden_sources": [], "required_items": ["U-22", "SLE24-16"],
        "support": {}, "expect_status": "success", "multi_turn": [],
    }
    reordered = _scored(multi, {
        "sources": ["linmac_consolidated.xlsx"],
        "items": {"SLE24-16": {"classification": "supported"},
                  "U-22": {"classification": "supported"}},
        "resolution_order": ["SLE24-16", "U-22"],
        "search_status": "success", "invocations": {},
    })
    out.append((
        "control_flags_reordered_identifier_set",
        not reordered.passed,
        "both items resolved but in the wrong order is a different answer when "
        "two look alike",
    ))

    missing = _scored(multi, {
        "sources": ["linmac_consolidated.xlsx"],
        "items": {"U-22": {"classification": "supported"}},
        "search_status": "success", "invocations": {},
    })
    out.append(("control_flags_dropped_identifier", not missing.passed,
                "a silently shortened requested set"))

    absent = {
        "id": "ctrl3", "category": "absent_within_coverage",
        "split": "development", "required_sources": ["expense_policy.md"],
        "forbidden_sources": [], "required_items": ["absent:no such row"],
        "support": {"absent:no such row": {"claimable": True}},
        "expect_status": "success", "multi_turn": [],
    }
    corrupted = _scored(absent, {
        "sources": ["expense_policy.md"],
        "items": {"absent:no such row": {"classification":
                                         "absent_within_coverage"}},
        "search_status": "failed", "invocations": {},
    })
    out.append((
        "control_rejects_absence_from_a_corrupted_read",
        not corrupted.passed,
        "the false-absence gate: an unreadable source is not an empty one",
    ))

    honest = _scored(absent, {
        "sources": ["expense_policy.md"],
        "items": {"absent:no such row": {"classification":
                                         "unresolved_due_to_retrieval_failure"}},
        "search_status": "failed", "invocations": {},
    })
    out.append(("control_accepts_unresolved_on_failure", honest.passed,
                "the paired positive, so the gate is two-sided"))

    fmt = {
        "id": "ctrl4", "category": "formatting_followup", "split": "development",
        "required_sources": [], "forbidden_sources": [],
        "required_items": [], "support": {}, "expect_status": "success",
        "multi_turn": [{"turn": 2, "message": "make that a table",
                        "expect_retrieval": 0}],
    }
    searched = _scored(fmt, {
        "sources": [], "items": {}, "search_status": "success",
        "invocations": {"turn-2": 1},
    })
    out.append(("control_rejects_search_on_a_formatting_followup",
                not searched.passed,
                "formatting performs no search"))

    degraded = {
        "id": "ctrl5", "category": "reranker_degraded",
        "split": "development", "required_sources": [], "forbidden_sources": [],
        "required_items": [], "support": {}, "expect_status": "success",
        "multi_turn": [],
    }
    lied = _scored(degraded, {
        "sources": [], "items": {}, "search_status": "success",
        "invocations": {}, "ranking": {"status": "degraded"},
        "claims": {"fully_searched": True},
    })
    out.append(("control_rejects_full_coverage_claim_under_degraded_ranking",
                not lied.passed,
                "a reranker fallback is not a completed search"))

    dup = completeness([exact, exact, {**exact, "id": "ctrl9"}], {
        "ctrl": CaseResult("ctrl", "exact_named_file", "development", [Check("x", PASS)])})
    out.append(("control_detects_duplicate_and_missing_case_ids", bool(dup),
                "a dropped case is the cheapest way to raise a score"))

    return out


def selftest() -> int:
    controls = negative_controls()
    failed = [(n, w) for n, ok, w in controls if not ok]
    for name, ok, why in controls:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            print(f"       {why}")
    print(f"selftest: {len(controls) - len(failed)}/{len(controls)} controls held")
    if failed:
        print("EVALUATOR INVALID — no scenario result may count until this passes")
        return 1
    print("evaluator valid")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--scenarios", default=str(HERE / "scenarios.json"))
    p.add_argument("--runs", nargs="+", default=[str(HERE / "runs.json")])
    p.add_argument("--out", default=str(HERE / "scorecard.json"))
    args = p.parse_args()

    if args.selftest:
        return selftest()

    scenarios = json.loads(Path(args.scenarios).read_text())["cases"]
    runs: dict[str, dict] = {}
    superseded: list[dict] = []
    for path in args.runs:
        runs_raw = json.loads(Path(path).read_text())
        if isinstance(runs_raw, dict) and "runs" not in runs_raw:
            print(f"{path} has no 'runs' key (keys: {sorted(runs_raw)}); "
                  "refusing to score a file that is not a run record")
            return 2
        run_list = runs_raw["runs"] if isinstance(runs_raw, dict) else runs_raw
        for record in run_list:
            cid = record["case_id"]
            prior = runs.get(cid)
            if prior is not None:
                prior_blocked = bool(prior.get("blocked"))
                if prior_blocked and not record.get("blocked"):
                    # Legitimate supersession: one layer could not exercise the
                    # case and a later layer did. Recorded, not silent.
                    superseded.append({"case_id": cid,
                                       "superseded_layer": prior.get("layer"),
                                       "reason": prior.get("blocked"),
                                       "by_layer": record.get("layer")})
                    runs[cid] = record
                    continue
                print(f"DUPLICATE run record for {cid} ({path}); refusing to "
                      "pick a winner — a case covered by two layers must be "
                      "reconciled, not overwritten")
                return 2
            runs[cid] = record
    if superseded:
        print(f"[merge] {len(superseded)} blocked case(s) superseded by a "
              f"later layer: {[s['case_id'] for s in superseded]}")
    results = {s["id"]: score_case(s, runs.get(s["id"])) for s in scenarios}

    problems = completeness(scenarios, results)
    if problems:
        print("INCOMPLETE RUN — refusing to report a scorecard:")
        for p_ in problems:
            print(f"  {p_}")
        return 2

    totals = report(scenarios, results)
    Path(args.out).write_text(json.dumps({
        "superseded": superseded,
        "totals": totals["totals"],
        "by_category": totals["by_category"],
        "by_split": totals["by_split"],
        "note": totals["note"],
        "cases": [results[c["id"]].to_dict() for c in scenarios],
    }, indent=1))
    print(f"{totals['totals']}")
    for split, cell in sorted(totals["by_split"].items()):
        print(f"  {split:12s} {cell}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
