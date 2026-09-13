#!/usr/bin/env python
"""Computer-use operator eval runner — measure, don't guess (AGENTS.md §2).

Runs the operator loop (real Chromium + real model) against the local
eval site for every task, per model, and prints a success/steps/seconds
table. Numbers belong in the commit/PR message when the model pool or
loop changes.

Usage (from backend/):
    BROWSER_ALLOW_PRIVATE_ADDRESSES=1 python tests/operator_eval/run_eval.py \
        --model gpt-6-astra [--max-steps 15] [--only form_fill,login_flow]

Requires: playwright installed, a working model key (BYOK/env), and the
explicit private-address opt-in above (the eval site serves on
127.0.0.1). NEVER run against the live dev DB — this harness uses no DB.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_site import start_site                      # noqa: E402
from tasks import TASKS, _reset_state                 # noqa: E402


async def run_task(base_url, task, model, max_steps):
    from core.operator.loop import OperatorLoop, JsonVisionDecider
    from core.operator.session import OperatorSession

    _reset_state()
    backend = OperatorSession(user_id="operator-eval")
    try:
        await backend.start(start_url=base_url + task["start_url"])
        loop = OperatorLoop(backend=backend,
                            decider=JsonVisionDecider(),
                            max_steps=max_steps)
        started = time.monotonic()
        result = await loop.run(task["goal"])
        elapsed = time.monotonic() - started
        passed = bool(task["verify"](result))
        return {
            "task": task["id"],
            "passed": passed,
            "done": result.get("done"),
            "steps": result.get("steps"),
            "seconds": round(elapsed, 1),
            "summary": (result.get("summary") or "")[:120],
        }
    finally:
        await backend.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True,
                        help="model id (sets ATOM_COMPUTER_USE_MODEL)")
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--only", default="",
                        help="comma-separated task ids to run")
    args = parser.parse_args()

    os.environ["ATOM_COMPUTER_USE_MODEL"] = args.model

    tasks = TASKS
    if args.only:
        wanted = {t.strip() for t in args.only.split(",")}
        tasks = [t for t in TASKS if t["id"] in wanted]

    base_url, stop = start_site()
    print(f"# operator eval — model={args.model} tasks={len(tasks)}")
    print(f"| {'task':<22} | pass | done | steps | sec |")
    print(f"|{'-' * 24}:|:----:|:----:|:-----:|:----:|")
    results = []
    try:
        for task in tasks:
            try:
                row = await run_task(base_url, task, args.model,
                                     args.max_steps)
            except Exception as exc:
                row = {"task": task["id"], "passed": False, "done": False,
                       "steps": None, "seconds": None,
                       "summary": f"harness error: {exc}"}
            results.append(row)
            print(f"| {row['task']:<22} | {'✓' if row['passed'] else '✗'}    "
                  f"| {str(row['done']):<4} | {str(row['steps']):<5} | "
                  f"{str(row['seconds']):<4} |")
    finally:
        stop()

    passed = sum(1 for r in results if r["passed"])
    print(f"\n**{passed}/{len(results)} passed** "
          f"({100 * passed / max(1, len(results)):.0f}%)")
    # Results go under results/ (gitignored) — never into the repo tree.
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "results.json"
    out.write_text(json.dumps(
        {"model": args.model, "results": results}, indent=2))
    print(f"details: {out}")


if __name__ == "__main__":
    asyncio.run(main())
