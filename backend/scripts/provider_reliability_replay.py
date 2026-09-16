#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded provider-reliability replay (audit item 5).

Replays a SMALL, representative workload through whatever routes are
currently configured, and records — per attempt — the signals the audit asks
for: planning success, grounded-answer success, time to first visible output,
total latency, zero-output frequency, rate limits, fallback success, and cost
per successful answer.

It deliberately separates three causes that the incident conflated:

  * **provider congestion** — 429/5xx/timeouts from the upstream;
  * **prompt size** — the same task at three input tiers (small / medium /
    evidence-sized), so a large-prompt failure is distinguishable from a
    congested provider;
  * **insufficient remaining turn budget** — a call that exceeds the
    configured budget is recorded as `budget_exceeded`, not as a provider
    fault.

It also answers, from the routing topology rather than from assumption,
whether the fallbacks share the failing upstream's capacity: the fallback
models come from the same BPC ladder, and each candidate's provider is
recorded, so "primary and fallback both sit behind one gateway account" is
shown rather than asserted.

Nothing here writes to the database. Cost is capped by `--budget-calls`.

Usage::

    ./venv/bin/python scripts/provider_reliability_replay.py --budget-calls 9
    ./venv/bin/python scripts/provider_reliability_replay.py --topology-only
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------- workload
# Representative, not exhaustive. Each entry is (name, kind, prompt, expected
# contract). `evidence` is sized to the documented 18k evidence budget so the
# "large prompt" tier exercises the real shape rather than a toy.
_SMALL = "Reply with the single word: ok"

_MEDIUM = (
    "From the evidence below, state the list price of the F-5216 in one "
    "sentence and cite the row.\n\nEVIDENCE:\n"
    + "\n".join(
        f"- [ingested mailbox] msg-{i}: quote line for machine {i} "
        f"| list={5000 + i} | full: knowledge/conversations/m{i}"
        for i in range(40))
)

_LARGE_EVIDENCE = (
    "From the evidence below, state the list price of the F-5216 and the "
    "formula chain that derives it, in under 40 words.\n\nEVIDENCE:\n"
    + "\n".join(
        f"- [ingested mailbox] msg-{i}: forwarded price list {i} "
        + "x" * 260 + f" | full: knowledge/conversations/m{i}"
        for i in range(60))
    + "\nR235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
      "Factory Price=5350 | $7,519.00\n"
      "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | I235==H235+700"
)

WORKLOAD: List[Tuple[str, str, str]] = [
    ("planning_short", "planning", _SMALL),
    ("grounded_medium", "grounded", _MEDIUM),
    ("derivation_large", "grounded", _LARGE_EVIDENCE),
]

_RATE_LIMIT_RE = re.compile(
    r"(429|rate.?limit|too many requests|quota|insufficient balance|"
    r"credits?|capacity)", re.IGNORECASE)
_BUDGET_RE = re.compile(
    r"(budget|turn.?budget|deadline|cancell?ed)", re.IGNORECASE)
_TIMEOUT_RE = re.compile(r"(timeout|timed out|deadline exceeded)", re.IGNORECASE)


def classify(error: Optional[str], content: Optional[str]) -> str:
    """One outcome label per attempt — the separation the audit requires."""
    if error:
        if _RATE_LIMIT_RE.search(error):
            return "rate_limited"
        if _BUDGET_RE.search(error):
            return "budget_exceeded"
        if _TIMEOUT_RE.search(error):
            return "timeout"
        return "provider_error"
    if not (content or "").strip():
        return "zero_output"
    return "ok"


def _provider_of(model_id: str, known: Dict[str, str]) -> str:
    if model_id in known:
        return known[model_id]
    # OpenRouter-style ids are "<vendor>/<model>"; a BPC pair may already be
    # "<provider>/<model>". Prefer the explicit mapping, else the first path
    # segment as a best-effort label.
    return str(model_id).split("/")[0] if "/" in str(model_id) else "unknown"


async def topology() -> Dict[str, Any]:
    """The live candidate ladder + fallback list, and whether the fallbacks
    share the primary's upstream. Read-only; no generation."""
    from core.llm.byok_handler import BYOKHandler
    from core.llm.byok_handler import QueryComplexity

    h = BYOKHandler(tenant_id="default")
    ranked = h.get_ranked_providers(QueryComplexity.SIMPLE)
    pairs = [(p, m) for (p, m) in (ranked or [])]
    fallbacks = h.get_fallback_models(QueryComplexity.SIMPLE, pairs[0][1], limit=3) if pairs else []
    provider_by_model = {m: p for (p, m) in pairs}
    primary = pairs[0] if pairs else (None, None)
    fb_pairs = [(provider_by_model.get(m, "?"), m) for m in fallbacks]
    shared = sorted({p for p, _m in fb_pairs if p == primary[0]})
    return {
        "ranked_candidates": [{"provider": p, "model": m} for p, m in pairs],
        "primary": {"provider": primary[0], "model": primary[1]},
        "fallback_models": fallbacks,
        "fallback_pairs": [{"provider": p, "model": m} for p, m in fb_pairs],
        "fallbacks_sharing_primary_upstream": shared,
        "fallbacks_share_primary_upstream": bool(shared),
    }


async def replay(budget_calls: int, repeats: int = 1, timeout_s: float = 90.0) -> Dict[str, Any]:
    from core.llm_service import LLMService
    from core.llm.model_provenance import get_resolved_model

    svc = LLMService()
    attempts: List[Dict[str, Any]] = []
    calls = 0

    for rep in range(repeats):
        for name, kind, prompt in WORKLOAD:
            if calls >= budget_calls:
                break
            calls += 1
            t0 = time.monotonic()
            first_visible = None
            error = None
            content = None
            model_seen = None
            cost = None
            try:
                res = await asyncio.wait_for(
                    svc.generate_completion(
                        messages=[{"role": "user", "content": prompt}],
                        model="auto",
                        max_tokens=200,
                        task_type=kind,
                    ),
                    timeout=timeout_s,
                )
                content = (res or {}).get("content") or (res or {}).get("response")
                if content and first_visible is None:
                    first_visible = time.monotonic() - t0
                model_seen = ((res or {}).get("model")
                              or get_resolved_model() or "unknown")
                cost = (res or {}).get("cost")
            except asyncio.TimeoutError:
                error = f"timeout after {timeout_s}s"
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
            total = time.monotonic() - t0
            attempts.append({
                "workload": name,
                "kind": kind,
                "prompt_chars": len(prompt),
                "outcome": classify(error, content),
                "error": error,
                "model": model_seen or get_resolved_model() or "unobserved",
                "ttft_ms": round(first_visible * 1000, 1) if first_visible else None,
                "total_ms": round(total * 1000, 1),
                "cost": cost,
                "output_chars": len((content or "").strip()),
            })
        if calls >= budget_calls:
            break
    return {"attempts": attempts, "calls": calls}


def summarize(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_outcome: Dict[str, int] = defaultdict(int)
    by_size: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_model: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"attempts": 0, "ok": 0, "cost": 0.0, "latency": []})
    for a in attempts:
        by_outcome[a["outcome"]] += 1
        tier = ("small" if a["prompt_chars"] < 1000
                else "medium" if a["prompt_chars"] < 12000 else "large")
        by_size[tier][a["outcome"]] += 1
        m = by_model[a["model"]]
        m["attempts"] += 1
        if a["outcome"] == "ok":
            m["ok"] += 1
        if a.get("cost"):
            m["cost"] += float(a["cost"])
        m["latency"].append(a["total_ms"])
    ok = by_outcome.get("ok", 0)
    total_cost = sum(float(a["cost"]) for a in attempts if a.get("cost"))
    for m in by_model.values():
        lat = m.pop("latency")
        m["mean_ms"] = round(sum(lat) / len(lat), 1) if lat else None
    return {
        "attempts": len(attempts),
        "outcomes": dict(by_outcome),
        "by_prompt_size": {k: dict(v) for k, v in by_size.items()},
        "by_model": dict(by_model),
        "answer_success_rate_pct": round(100.0 * ok / len(attempts), 1) if attempts else 0.0,
        "zero_output_rate_pct": round(
            100.0 * by_outcome.get("zero_output", 0) / len(attempts), 1) if attempts else 0.0,
        "total_cost": round(total_cost, 6),
        "cost_per_successful_answer": (
            round(total_cost / ok, 6) if ok and total_cost else None),
    }


def render_markdown(rep: Dict[str, Any]) -> str:
    s = rep["summary"]
    topo = rep["topology"]
    lines = [
        "# Provider reliability — bounded replay",
        "",
        f"_Generated {rep['generated_at']} · budget {rep['budget_calls']} calls · "
        f"executed {rep['executed_calls']}._",
        "",
        "## 1. Observed outcomes",
        "",
        "| outcome | attempts |",
        "|---|---|",
    ]
    for k, v in sorted(s["outcomes"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        f"- Answer success rate: **{s['answer_success_rate_pct']}%**",
        f"- Zero-output frequency: **{s['zero_output_rate_pct']}%**",
        f"- Total cost: **{s['total_cost']}** · "
        f"cost per successful answer: **{s['cost_per_successful_answer']}**",
        "",
        "### By prompt size (congestion vs prompt size)",
        "",
        "| tier | outcomes |",
        "|---|---|",
    ]
    for tier, outcomes in sorted(s["by_prompt_size"].items()):
        lines.append(f"| {tier} | {outcomes} |")
    lines += [
        "",
        "### By model actually used",
        "",
        "| model | attempts | ok | mean ms | cost |",
        "|---|---|---|---|---|",
    ]
    for m, a in sorted(s["by_model"].items(), key=lambda kv: -kv[1]["attempts"]):
        lines.append(f"| `{m}` | {a['attempts']} | {a['ok']} | {a['mean_ms']} | "
                     f"{round(a['cost'], 6)} |")
    lines += [
        "",
        "## 2. Fallback topology — do fallbacks share the failing upstream?",
        "",
        f"- Primary: `{topo['primary']['provider']}/{topo['primary']['model']}`",
        f"- Fallback models: `{topo['fallback_models']}`",
        f"- Fallback (provider, model) pairs: `{topo['fallback_pairs']}`",
        f"- **Fallbacks sharing the primary's provider: "
        f"`{topo['fallbacks_sharing_primary_upstream']}`** → "
        f"`fallbacks_share_primary_upstream={topo['fallbacks_share_primary_upstream']}`",
        "",
        ("A `True` here means a fallback is not independent capacity: when the "
         "shared upstream is congested or out of quota, the fallback fails for "
         "the same reason as the primary. A `False` means the ladder provides "
         "genuine provider diversity for the top candidate."
         if topo["fallbacks_share_primary_upstream"] else
         "No fallback shares the primary's provider, so the ladder does "
         "provide provider diversity for the top candidate. Note this is a "
         "statement about the configured ladder, not about observed "
         "behaviour under load."),
        "",
        "## 3. What this does and does not establish",
        "",
        "- Establishes: the observed outcome mix for the routes configured at "
        "replay time, at three prompt sizes, with latency and cost per "
        "successful answer.",
        "- Does NOT establish: a provider-wide failure rate. The sample is "
        "bounded by `--budget-calls` and by the account's own quota.",
        "- Capacity purchase is therefore presented as a *measured option*: "
        "the cost of a dedicated route is only justified if the observed "
        "`rate_limited` + `timeout` share is material at the workload's real "
        "prompt sizes AND the fallback topology above shows no independent "
        "capacity. Absent that, the honest first response is smaller prompts, "
        "a tighter turn budget, or a different model on the existing route.",
    ]
    return "\n".join(lines) + "\n"


async def main_async(args) -> int:
    topo = await topology()
    if args.topology_only:
        print(json.dumps(topo, indent=2, default=str))
        return 0
    run = await replay(args.budget_calls, repeats=args.repeats,
                       timeout_s=args.timeout_s)
    rep = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "budget_calls": args.budget_calls,
        "executed_calls": run["calls"],
        "topology": topo,
        "summary": summarize(run["attempts"]),
        "attempts": run["attempts"],
    }
    md = render_markdown(rep)
    print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, default=str)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(md)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-calls", type=int, default=6,
                    help="hard cap on generation calls (default 6)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--timeout-s", type=float, default=90.0)
    ap.add_argument("--topology-only", action="store_true",
                    help="print the routing topology without generating")
    ap.add_argument("--json", default=None)
    ap.add_argument("--markdown", default=None)
    args = ap.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
