#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Router-evidence reconciliation report — what the learning-router history
actually contains, and what it does NOT license.

Written for audit item 3 ("establish trustworthy router evidence before
choosing a trust horizon"). The audit's claim of "~90 verdict rows" for
auto-activation is not reproducible as a *representative* sample: accrual was
dead from 9a4a2a774 (a latent TypeError in the ``assess_response_quality``
call) until 76cc51bcd repaired it, so every row in the table postdates
2026-09-15 22:24 and comes from the incident's own traffic. This script makes
that auditable instead of asserted, and reports the numbers the activation
threshold is computed from.

Read-only. Never writes to the database.

Usage::

    ./venv/bin/python scripts/router_evidence_report.py
    ./venv/bin/python scripts/router_evidence_report.py --db data/atom.db --json out.json
    ./venv/bin/python scripts/router_evidence_report.py --holdout-frac 0.3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# Fabrication verdict provenance. Kept in sync with
# core.llm.response_quality.FABRICATION_VERDICTS; duplicated here so the
# report can be run against a DB from an older checkout without importing
# application code (and without a DB session).
FABRICATION_VERDICTS = {"unsupported_figures", "ungrounded_claims"}
# Availability/latency outcomes must never be counted as fabrication. Kept
# explicit so the report can SHOW the misclassification the old rule caused.
AVAILABILITY_VERDICTS = {
    "timeout", "rate_limited", "auth_error", "network_error",
    "provider_error", "context_length", "empty",
}


def _db_path_from_env(default: str = "data/atom.db") -> str:
    url = os.getenv("DATABASE_URL", "") or ""
    m = re.sub(r"^sqlite:///", "", url)
    return m or default


def load_rows(db_path: str) -> List[Dict[str, Any]]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            "SELECT id, routing_result_id, tenant_id, task_type, model_id, "
            "success, quality_satisfied, user_satisfaction, actual_cost, "
            "actual_latency_ms, prompt_features, created_at "
            "FROM llm_routing_feedback ORDER BY created_at"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def _verdict(row: Dict[str, Any]) -> Optional[str]:
    """Explicit provenance, if the row carries any.

    Two channels are recognised: the ``verdict`` key inside the persisted
    ``prompt_features`` JSON (the corrective-signal channel introduced with
    the fabrication bench) and a dedicated column if one exists.
    """
    raw = row.get("prompt_features")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    if isinstance(parsed, dict):
        v = parsed.get("verdict") or parsed.get("quality_verdict")
        return str(v) if v else None
    return None


def _features_present(row: Dict[str, Any]) -> bool:
    """True only when the row carries a real feature dict.

    SQLite stores a JSON `null` as the TEXT `'null'`, which is truthy — the
    first cut of this report counted 67 null-feature rows as populated.
    """
    raw = row.get("prompt_features")
    if not raw:
        return False
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return False
    return bool(parsed) and isinstance(parsed, dict)


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _mean(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def _p95(values: List[float]) -> Optional[float]:
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    idx = min(len(values) - 1, int(round(0.95 * (len(values) - 1))))
    return round(values[idx], 1)


def build_report(rows: List[Dict[str, Any]], holdout_frac: float = 0.3) -> Dict[str, Any]:
    total = len(rows)
    generations: Dict[str, int] = defaultdict(int)
    for r in rows:
        generations[str(r.get("routing_result_id"))] += 1
    dup_generations = {k: v for k, v in generations.items() if v > 1}

    ts = [t for t in (_parse_ts(r.get("created_at")) for r in rows) if t]
    first, last = (min(ts), max(ts)) if ts else (None, None)
    span_h = round((last - first).total_seconds() / 3600.0, 2) if ts else None

    verdict_counts: Dict[str, int] = defaultdict(int)
    no_features = 0
    for r in rows:
        v = _verdict(r)
        verdict_counts[v or "(none)"] += 1
        if not _features_present(r):
            no_features += 1

    # The bench rule that was actually shipped: satisfaction <= 0.15 means
    # fabrication. Show what that selects, and how much of it is NOT
    # fabrication by provenance.
    band = [r for r in rows if (r.get("user_satisfaction") or 0) <= 0.15]
    band_true_fab = [r for r in band if _verdict(r) in FABRICATION_VERDICTS]
    band_unprovenanced = [r for r in band if _verdict(r) is None]
    # Everything the score threshold selects that is NOT an explicit
    # fabrication verdict is a misclassification by definition.
    band_misclassified = [r for r in band if _verdict(r) not in FABRICATION_VERDICTS]
    # Of those, how many are shaped like availability/latency failures
    # (provider exception, empty output) rather than an unknown verdict.
    band_availability_shaped = [
        r for r in band_misclassified
        if (not r.get("success")) or _verdict(r) in AVAILABILITY_VERDICTS
    ]

    by_model: Dict[str, Dict[str, Any]] = {}
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[str(r.get("model_id"))].append(r)
    for model, rs in grouped.items():
        n = len(rs)
        succ = sum(1 for r in rs if r.get("success"))
        qsat = sum(1 for r in rs if r.get("quality_satisfied"))
        costs = [r.get("actual_cost") for r in rs if r.get("actual_cost") is not None]
        lat = [r.get("actual_latency_ms") for r in rs if r.get("actual_latency_ms")]
        by_model[model] = {
            "rows": n,
            "success_rate_pct": _pct(succ, n),
            "quality_satisfied_pct": _pct(qsat, n),
            "mean_satisfaction": _mean([r.get("user_satisfaction") for r in rs]),
            "mean_latency_ms": _mean(lat),
            "p95_latency_ms": _p95(lat),
            "total_cost": round(sum(c for c in costs if c is not None), 6),
            "cost_per_successful_answer": (
                round(sum(c for c in costs if c is not None) / succ, 6)
                if succ and costs else None
            ),
            "rows_without_prompt_features": sum(
                1 for r in rs if not _features_present(r)),
        }

    by_task: Dict[str, Dict[str, Any]] = {}
    grouped_task: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped_task[str(r.get("task_type"))].append(r)
    for task, rs in grouped_task.items():
        by_task[task] = {
            "rows": len(rs),
            "models": sorted({str(r.get("model_id")) for r in rs}),
            "quality_satisfied_pct": _pct(
                sum(1 for r in rs if r.get("quality_satisfied")), len(rs)),
        }

    # ---- Temporal holdout: does learned ordering beat static BPC? ----
    # Observational only. The recorded rows are outcomes of the model BPC
    # ALREADY chose, so an unexecuted alternative has NO observed outcome and
    # must not be scored as if it did.
    holdout = _holdout_eval(rows, holdout_frac)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "rows": total,
            "distinct_generations": len(generations),
            "duplicate_generations": len(dup_generations),
            "duplicate_row_excess": sum(v - 1 for v in dup_generations.values()),
            "models": len(grouped),
            "first_row_utc": first.isoformat() if first else None,
            "last_row_utc": last.isoformat() if last else None,
            "span_hours": span_h,
            "rows_per_hour": round(total / span_h, 2) if span_h else None,
            "rows_without_prompt_features": no_features,
            "rows_without_prompt_features_pct": _pct(no_features, total),
        },
        "provenance": dict(sorted(verdict_counts.items(), key=lambda kv: -kv[1])),
        "fabrication_band": {
            "rule": "user_satisfaction <= 0.15",
            "rows_in_band": len(band),
            "with_fabrication_verdict": len(band_true_fab),
            "unprovenanced": len(band_unprovenanced),
            "misclassified": len(band_misclassified),
            "availability_shaped_misclassified": len(band_availability_shaped),
            "models_in_band": sorted({str(r.get("model_id")) for r in band}),
        },
        "duplicate_generation_detail": [
            {
                "routing_result_id": gid,
                "rows": count,
                "models": sorted({
                    str(r.get("model_id")) for r in rows
                    if str(r.get("routing_result_id")) == gid}),
                "satisfactions": [
                    r.get("user_satisfaction") for r in rows
                    if str(r.get("routing_result_id")) == gid],
            }
            for gid, count in sorted(dup_generations.items(),
                                     key=lambda kv: -kv[1])[:10]
        ],
        "by_model": by_model,
        "by_task": by_task,
        "holdout": holdout,
        "limitations": [
            "Rows are outcomes of the model BPC already chose (observational, "
            "not randomised): an unexecuted alternative has no known outcome "
            "and is reported as unobserved, never as a win or a loss.",
            "Accrual began only after the assess_response_quality TypeError was "
            "repaired, so the window is one incident's traffic, not a "
            "representative workload.",
            "prompt_features are NULL for rows written without a stashed "
            "decision id, so those rows train on task-default features "
            "(train/serve skew); see totals.rows_without_prompt_features.",
            "No decision log persists the candidate ordering, so routing "
            "disagreements cannot be reconstructed retroactively.",
        ],
    }


def _holdout_eval(rows: List[Dict[str, Any]], frac: float) -> Dict[str, Any]:
    """Time-ordered split; report per-model measured outcomes on the holdout.

    Deliberately does NOT declare a winner: with one model per decision and no
    randomisation, the holdout can measure each model's observed quality,
    latency and cost, but cannot answer "what would the other model have
    done". The comparison to static BPC is therefore reported as the set of
    decisions where the learned order and the cost-priority order DISAGREE,
    with the alternative's outcome marked unobserved.
    """
    ts_rows = [(t, r) for t, r in ((_parse_ts(r.get("created_at")), r) for r in rows) if t]
    ts_rows.sort(key=lambda p: p[0])
    if len(ts_rows) < 10:
        return {"status": "insufficient_rows", "rows": len(ts_rows)}
    cut = max(1, int(len(ts_rows) * (1.0 - frac)))
    train = [r for _t, r in ts_rows[:cut]]
    holdout = [r for _t, r in ts_rows[cut:]]

    def _agg(rs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        g: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rs:
            g[str(r.get("model_id"))].append(r)
        for m, mrs in g.items():
            lat = [r.get("actual_latency_ms") for r in mrs if r.get("actual_latency_ms")]
            costs = [r.get("actual_cost") for r in mrs if r.get("actual_cost") is not None]
            out[m] = {
                "rows": len(mrs),
                "quality_satisfied_pct": _pct(
                    sum(1 for r in mrs if r.get("quality_satisfied")), len(mrs)),
                "mean_latency_ms": _mean(lat),
                "total_cost": round(sum(c for c in costs if c is not None), 6),
            }
        return out

    train_agg, holdout_agg = _agg(train), _agg(holdout)

    # Ordering candidates must clear the same per-model observation floor the
    # activation rule uses (>=8 obs). A 2-row model that happens to score 100%
    # must not be reported as "the learned top" — that is a small-sample
    # artifact, not evidence.
    MIN_OBS = 8
    eligible = [m for m, a in train_agg.items() if a["rows"] >= MIN_OBS]
    excluded_small = sorted(m for m in train_agg if m not in eligible)
    # Learned order = train-set quality_satisfied rate desc (what the predictor
    # learns from). Static BPC order = cost-priority asc (documented default).
    learned_order = sorted(
        eligible, key=lambda m: (-(train_agg[m]["quality_satisfied_pct"] or 0),
                                 train_agg[m]["mean_latency_ms"] or 0))
    static_order = sorted(
        eligible, key=lambda m: (train_agg[m]["total_cost"], m))

    disagreements = []
    if learned_order and static_order and learned_order[0] != static_order[0]:
        disagreements.append({
            "train_top_learned": learned_order[0],
            "train_top_static_cost_priority": static_order[0],
            "observed_outcome_of_chosen": holdout_agg.get(static_order[0]),
            "unobserved_alternative": learned_order[0],
            "alternative_outcome": "unobserved",
        })
    return {
        "status": "ok",
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_by_model": train_agg,
        "holdout_by_model": holdout_agg,
        "learned_order_from_train": learned_order,
        "static_cost_priority_order": static_order,
        "ordering_min_observations": MIN_OBS,
        "models_excluded_small_sample": excluded_small,
        "disagreements": disagreements,
        "verdict": (
            "Held-out comparison is INCONCLUSIVE by construction: the holdout "
            "contains only outcomes of the model that was actually executed. "
            "Certifying superiority over static BPC requires an executed "
            "split (ATOM_TRAFFIC_SPLIT-style) or a persisted candidate-order "
            "log with counterfactual sampling."
        ),
    }


def render_markdown(rep: Dict[str, Any]) -> str:
    t = rep["totals"]
    lines = [
        "# Router evidence — reconciliation",
        "",
        f"_Generated {rep['generated_at']} by `backend/scripts/router_evidence_report.py`._",
        "",
        "## 1. What the table actually holds",
        "",
        f"- **{t['rows']} outcome rows** across **{t['distinct_generations']} distinct "
        f"generations** ({t['models']} models).",
        f"- Window: `{t['first_row_utc']}` → `{t['last_row_utc']}` "
        f"(**{t['span_hours']} h**, ~{t['rows_per_hour']} rows/h).",
        f"- Duplicate generations: **{t['duplicate_generations']}** "
        f"({t['duplicate_row_excess']} excess row(s)) — one generation written "
        "more than once.",
        f"- Rows with **no stashed prompt features**: "
        f"**{t['rows_without_prompt_features']}** "
        f"({t['rows_without_prompt_features_pct']}%) → these train on "
        "task-default features.",
        "",
        "### Provenance carried by the rows",
        "",
        "| verdict | rows |",
        "|---|---|",
    ]
    for k, v in rep["provenance"].items():
        lines.append(f"| `{k}` | {v} |")
    fb = rep["fabrication_band"]
    lines += [
        "",
        "### The fabrication bench's selection rule, audited",
        "",
        f"Rule `{fb['rule']}` selects **{fb['rows_in_band']}** rows. Of those:",
        "",
        f"- **{fb['with_fabrication_verdict']}** carry an explicit fabrication verdict.",
        f"- **{fb['unprovenanced']}** carry no verdict at all.",
        f"- **{fb['misclassified']}** are selected by the score threshold but are "
        "NOT provenanced as fabrication"
        + (f", of which **{fb['availability_shaped_misclassified']}** are "
           "availability-shaped (provider exception / empty output)."
           if fb['availability_shaped_misclassified'] else "."),
        "",
    ]
    if rep.get("duplicate_generation_detail"):
        lines += ["### Generations written more than once", "",
                  "| routing_result_id | rows | models | satisfactions |",
                  "|---|---|---|---|"]
        for d in rep["duplicate_generation_detail"]:
            lines.append(
                f"| `{d['routing_result_id']}` | {d['rows']} | "
                f"{', '.join(d['models'])} | {d['satisfactions']} |")
        lines += ["", "A duplicated row inflates the bench's denominator and, "
                      "when the duplicate is a fabrication verdict, its "
                      "numerator — one generation must not be counted twice.",
                  ""]
    lines += [
        "## 2. Observed outcomes by model",
        "",
        "| model | rows | success % | quality-satisfied % | mean sat | mean ms | p95 ms | total cost | cost/success | no features |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m, a in sorted(rep["by_model"].items(), key=lambda kv: -kv[1]["rows"]):
        lines.append(
            f"| `{m}` | {a['rows']} | {a['success_rate_pct']} | "
            f"{a['quality_satisfied_pct']} | {a['mean_satisfaction']} | "
            f"{a['mean_latency_ms']} | {a['p95_latency_ms']} | "
            f"{a['total_cost']} | {a['cost_per_successful_answer']} | "
            f"{a['rows_without_prompt_features']} |")
    lines += [
        "",
        "## 3. Observed outcomes by task",
        "",
        "| task | rows | models | quality-satisfied % |",
        "|---|---|---|---|",
    ]
    for task, a in sorted(rep["by_task"].items(), key=lambda kv: -kv[1]["rows"]):
        lines.append(f"| `{task}` | {a['rows']} | {len(a['models'])} | "
                     f"{a['quality_satisfied_pct']} |")
    h = rep["holdout"]
    lines += ["", "## 4. Held-out comparison vs static BPC", ""]
    if h.get("status") != "ok":
        lines.append(f"- **{h.get('status')}** ({h.get('rows')} rows).")
    else:
        lines += [
            f"- Train {h['train_rows']} rows / holdout {h['holdout_rows']} rows "
            "(time-ordered split).",
            f"- Learned order from train (quality-satisfied desc): "
            f"`{h['learned_order_from_train']}`",
            f"- Static cost-priority order: `{h['static_cost_priority_order']}`",
            "",
            "| model | holdout rows | quality-satisfied % | mean ms | total cost |",
            "|---|---|---|---|---|",
        ]
        for m, a in sorted(h["holdout_by_model"].items()):
            lines.append(f"| `{m}` | {a['rows']} | {a['quality_satisfied_pct']} | "
                         f"{a['mean_latency_ms']} | {a['total_cost']} |")
        lines += ["", f"**{h['verdict']}**"]
        if h["disagreements"]:
            lines += ["", "### Logged disagreements", ""]
            for d in h["disagreements"]:
                lines.append(
                    f"- Train-top learned `{d['train_top_learned']}` vs static "
                    f"`{d['train_top_static_cost_priority']}`; the executed "
                    f"alternative's holdout outcome is observed, the "
                    f"`{d['unobserved_alternative']}` outcome is "
                    f"**{d['alternative_outcome']}**.")
    lines += ["", "## 5. Limitations (read before trusting a horizon)", ""]
    lines += [f"- {x}" for x in rep["limitations"]]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="SQLite path (default: DATABASE_URL)")
    ap.add_argument("--json", default=None, help="also write the raw report as JSON")
    ap.add_argument("--markdown", default=None, help="write the rendered markdown here")
    ap.add_argument("--holdout-frac", type=float, default=0.3)
    args = ap.parse_args(argv)

    db = args.db or _db_path_from_env()
    if not os.path.exists(db):
        print(f"database not found: {db}", file=sys.stderr)
        return 2
    rows = load_rows(db)
    rep = build_report(rows, holdout_frac=args.holdout_frac)
    md = render_markdown(rep)
    print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
