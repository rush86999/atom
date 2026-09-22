#!/usr/bin/env python
"""Pre-flight smoke for the Phase 4 experiment: ONE live rollout.

Answers the only question that matters before committing the experiment
budget: does the pinned model actually drive the operator loop on the local
site (vision payload accepted, JSON decision parseable, loop completes with
a classified outcome)?

SAFETY: never connects to the live dev DB — requires DATABASE_URL pointed
at a scratch COPY (the BYOK keys must exist in it for provider auth).

Usage (from backend/):
    cp data/atom.db /tmp/atom-curriculum.db
    BROWSER_ALLOW_PRIVATE_ADDRESSES=1 \
    DATABASE_URL=sqlite:////tmp/atom-curriculum.db \
    ATOM_COMPUTER_USE_MODEL=glm-5.3-flash \
    python tests/operator_eval/smoke.py [--task find_code] [--model X]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from adapter import EnvInstance, run_rollout          # noqa: E402
from tasks import get_task                            # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("ATOM_COMPUTER_USE_MODEL",
                                                     "glm-5.3-flash"))
    parser.add_argument("--task", default="find_code")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--pinned", action="store_true",
                        help="call the opencode-go client directly with the "
                             "pinned model (routing frozen; the LLMService "
                             "ladder is bypassed entirely)")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", "")
    if "atom.db" in db_url and "/tmp" not in db_url:
        print(f"REFUSING: DATABASE_URL looks like the live dev DB ({db_url!r}) "
              f"— point it at a scratch copy (see module docstring).")
        return 2

    decider_factory = None
    if args.pinned:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        from core.llm_service import LLMService
        from pinned_decider import PinnedVisionDecider
        handler = LLMService(tenant_id="default")._get_handler(
            workspace_id="default")
        client = handler.async_clients["opencode-go"]
        decider_factory = (lambda: PinnedVisionDecider(
            client, args.model.split("/")[-1]))

    with EnvInstance() as instance:
        outcome = await run_rollout(
            instance, get_task(args.task), model=args.model,
            max_steps=args.max_steps, arm="smoke", env_label="base",
            decider_factory=decider_factory)
    print(outcome.to_dict())
    if outcome.summary:
        print("summary:", outcome.summary[:300])
    if outcome.error:
        print("error:", outcome.error[:300])
    status = outcome.status.value
    # A classified AGENT_FAIL is still a FEASIBILITY pass (the loop ran);
    # only harness errors mean the pinned model/path is unusable.
    print(f"FEASIBLE" if status != "harness_error" else "INFEASIBLE")
    return 0 if status != "harness_error" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
