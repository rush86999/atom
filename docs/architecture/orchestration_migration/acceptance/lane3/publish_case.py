#!/usr/bin/env python3
"""Publish a C16 case's assertions, with inapplicable ones marked, never hidden.

WHY
`controlled_planner_c16.py` records two checks that only make sense when a
mutation actually landed:

    landed_mutation_attributable_to_this_request
    landed_mutation_is_the_current_revision

On `--mode bg-failure` the case is *supposed* to land nothing -- `zero_update_audits`
and `old_text_intact` assert exactly that -- so both of those read False and the
case reports a failure that is not one. Two honest ways to report that exist, and
the wrong ones are common: folding them into the denominator (a clean-looking
"24/26" that hides a scoping bug behind a red number) or dropping them (a "26/26"
that silently claims a mutation was attributed when none existed).

So: every assertion is published, each as PASS / FAIL / NOT APPLICABLE, and an
inapplicable one carries the assertion that makes it inapplicable. The case
verdict is then the applicable subset, stated with its own count.

    publish_case.py <c16_case.json> [--key case_bg-failure]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

#: (assertion, the assertion whose truth makes these two meaningless)
SUCCESS_ONLY: Dict[str, Tuple[str, str]] = {
    "landed_mutation_attributable_to_this_request": (
        "zero_update_audits",
        "no mutation landed, by the case's own design, so there is nothing to "
        "attribute to this request"),
    "landed_mutation_is_the_current_revision": (
        "zero_update_audits",
        "no mutation landed, so there is no landed row whose revision currency "
        "could be checked"),
}


def publish(path: Path, key: str = "") -> Dict[str, Any]:
    doc = json.loads(path.read_text())
    case = None
    if key:
        case = doc.get(key)
    else:
        for k, v in doc.items():
            if isinstance(v, dict) and "checks" in v:
                case = v
                key = k
                break
    if case is None:
        raise SystemExit(f"no case with 'checks' found in {path}")

    checks: Dict[str, Any] = case.get("checks") or {}
    rows: List[Dict[str, Any]] = []
    n_pass = n_fail = n_na = 0
    for name, value in checks.items():
        if name in SUCCESS_ONLY and not value:
            guard, reason = SUCCESS_ONLY[name]
            guard_value = checks.get(guard)
            if guard_value is True:
                rows.append({"assertion": name, "verdict": "NOT APPLICABLE",
                             "recorded_value": value, "reason": reason,
                             "established_by": f"{guard} = True"})
                n_na += 1
                continue
        rows.append({"assertion": name,
                     "verdict": "PASS" if value else "FAIL",
                     "recorded_value": value})
        n_pass += 1 if value else 0
        n_fail += 0 if value else 1

    applicable = n_pass + n_fail
    return {
        "schema": "lane3-published-case-v1",
        "source_artifact": str(path),
        "case_key": key,
        "generated_at": doc.get("generated_at"),
        "world": doc.get("world"),
        "verdict": "PASS" if n_fail == 0 else "FAIL",
        "counts": {"published": len(rows), "pass": n_pass, "fail": n_fail,
                   "not_applicable": n_na,
                   "applicable": applicable,
                   "note": f"{n_pass}/{applicable} of the APPLICABLE assertions "
                           f"passed; {n_na} published as NOT APPLICABLE and not "
                           f"counted in the ratio"},
        "assertions": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artifact")
    ap.add_argument("--key", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    src = Path(args.artifact)
    out = publish(src, args.key)
    dest = Path(args.out) if args.out else src.parent / (src.stem + "_published.json")
    dest.write_text(json.dumps(out, indent=1, default=str))

    print(f"case {out['case_key']}  verdict {out['verdict']}")
    print(f"  {out['counts']['note']}")
    for row in out["assertions"]:
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "NOT APPLICABLE": "n/a "}[row["verdict"]]
        print(f"  {mark} {row['assertion']}")
        if row["verdict"] == "NOT APPLICABLE":
            print(f"         {row['reason']} ({row['established_by']})")
    print(f"-> {dest}")
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
