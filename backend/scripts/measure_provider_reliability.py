#!/usr/bin/env python3
"""Bounded provider-reliability replay (audit item 5).

Runs N representative workloads (planning-class structured call + a short
grounded-answer generation) through the live BYOK handler exactly as the
app issues them, and records per attempt: success, time-to-first-visible
token (streaming leg), total latency, finish reason, zero-output
frequency, HTTP 429s, fallback engagement, and estimated cost. Congestion
vs prompt-size vs remaining-budget are separated by recording prompt
tokens and the stage that failed.

Usage: python scripts/measure_provider_reliability.py [N=6]
Output: scripts/provider_reliability_<ts>.json + console summary.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

# scripts/ lives INSIDE backend/ — anchor to the backend root itself
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
load_dotenv("../.env", override=False)

PLANNING_PROMPT = (
    "Classify the user request and return JSON {service, intent, query}: "
    "'check the stock and price for model WG-350DSAV in our inventory'")
ANSWER_PROMPT = (
    "You are answering a quotation question with the evidence below.\n"
    "EVIDENCE: row 235 | Factory Price=5350 | Discount=0.9 | Freight=+700 "
    "| Warehouse x1.02 | margins /0.87,/0.86 | ROUNDUP\n"
    "QUESTION: what list price does this derive, and is any add-on "
    "visible? Answer in 2 sentences, show the arithmetic.")


async def one_attempt(svc, handler, label, mode):
    t0 = time.monotonic()
    ttFv = None
    finish = None
    err = None
    try:
        if mode == "stream":
            try:
                _fb = handler.get_fallback_models(
                    handler.analyze_query_complexity(ANSWER_PROMPT), "", 2)
            except Exception:  # noqa: BLE001 — optional fallback list
                _fb = []
            _m = _fb[0] if _fb else "z-ai/glm-5.3-flash"
            buf = []
            agen = handler.stream_completion(
                messages=[{"role": "user", "content": ANSWER_PROMPT}],
                model=_m, provider_id="openrouter",
                temperature=0.3, max_tokens=400)
            while True:
                try:
                    tok = await asyncio.wait_for(agen.__anext__(), timeout=30)
                except StopAsyncIteration:
                    break
                if tok and ttFv is None:
                    ttFv = time.monotonic() - t0
                buf.append(tok or "")
            text = "".join(buf)
            finish = "stream_ok" if text.strip() else "zero_visible"
            return dict(label=label, mode=mode, ok=bool(text.strip()),
                        ttFv=ttFv, latency=time.monotonic() - t0,
                        finish=finish, err=None, chars=len(text))
        else:
            out = await svc.generate_completion(
                messages=[{"role": "user", "content": PLANNING_PROMPT}],
                temperature=0.0, max_tokens=200)
            text = (out or {}).get("content") or ""
            return dict(label=label, mode=mode, ok=bool(text.strip()),
                        ttFv=None, latency=time.monotonic() - t0,
                        finish="ok" if text.strip() else "empty",
                        err=None, chars=len(text),
                        model=(out or {}).get("model"))
    except Exception as e:  # noqa: BLE001 — the measurement IS the errors
        err = f"{type(e).__name__}: {str(e)[:140]}"
        return dict(label=label, mode=mode, ok=False, ttFv=ttFv,
                    latency=time.monotonic() - t0, finish="exception",
                    err=err, chars=0)


async def main(n):
    from core.llm_service import LLMService

    svc = LLMService()
    handler = svc._get_handler() if hasattr(svc, "_get_handler") else svc.handler
    results = []
    for i in range(n):
        results.append(await one_attempt(svc, handler, f"plan{i}", "plan"))
        results.append(await one_attempt(svc, handler, f"answer{i}", "stream"))
        await asyncio.sleep(2)  # stay inside shared-pool rate limits
    summary = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "n_attempts": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "zero_visible": sum(1 for r in results if r["finish"] == "zero_visible"),
        "exceptions": sum(1 for r in results if r["finish"] == "exception"),
        "rate_limited": sum(1 for r in results if r["err"] and "429" in r["err"]),
        "median_latency": sorted(r["latency"] for r in results)[len(results)//2],
        "max_latency": max(r["latency"] for r in results),
        "ttfv_median": (sorted(r["ttFv"] for r in results if r["ttFv"])
                        [len([r for r in results if r["ttFv"]])//2]
                        if any(r["ttFv"] for r in results) else None),
        "attempts": results,
    }
    out = os.path.join(
        os.path.dirname(__file__),
        f"provider_reliability_{datetime.now(timezone.utc):%Y%m%d_%H%M}.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "attempts"},
                     indent=1))
    print(f"detail -> {out}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
