#!/usr/bin/env python
"""Phase 4 learning experiment: static-env arm (A) vs mutated-curriculum arm (B).

Implements the REGISTERED design in
docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md (2026-09-21). Deviations from
the registration are invalid — this file only mechanizes it.

Per family: arm A trains twice on the base env; arm B trains on base +
a train-rotated instance. Each arm distills ONE strategy brief per family
from its own train trajectories (same pinned model, text-only call). Both
arms are then tested on the SAME rotated test instances, disjoint from every
train value and from the base values (the memorization trap). Success = the
frozen verifier; classification per the adapter taxonomy.

SAFETY: no DB writes; run against a scratch DATABASE_URL copy (BYOK keys
only). Results checkpoint to results/experiment_*.json after every rollout.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from adapter import EnvInstance, run_rollout            # noqa: E402
from core.env_curriculum.mutations import (             # noqa: E402
    MutationStack,
    SetupMutation,
)
from pinned_decider import PinnedVisionDecider          # noqa: E402
from tasks import BASE_TASKS, get_task                  # noqa: E402

MODEL = "glm-5.3-flash"
SEED = 20260921
MAX_STEPS = 15
WALL_CLOCK_CAP_S = 3.5 * 3600
STAGE_HARNESS_ABORT = 0.25
BRIFF_MAX_CHARS = 1200

# World knobs per family: {world_updates} shape matches EvalSite.load_world.
# TRAIN and TEST pools are disjoint from each other and from base values.
FAMILIES = {
    "find_code": {
        "knob": lambda v: {"docs": {"3": {"api_code": v}}},
        "train": ["ATOM-2026", "ATOM-31337"],
        "test": ["ATOM-55501", "ATOM-60088"],
    },
    "search_and_click": {
        "knob": lambda v: {"docs": {"2": {"secret_word": v}}},
        "train": ["capybara", "axolotl"],
        "test": ["pangolin", "ibex"],
    },
    "scroll_find": {
        "knob": lambda v: {"longpage_code": v},
        "train": ["LONGPAGE-7", "LONGPAGE-31"],
        "test": ["LONGPAGE-55", "LONGPAGE-88"],
    },
    "login_flow": {
        "knob": lambda v: {"creds": v},
        "train": [{"user": "ada", "pass": "engine42"},
                  {"user": "marie", "pass": "curie23"}],
        "test": [{"user": "grace", "pass": "hopper60"},
                 {"user": "alan", "pass": "turing42"}],
    },
    "form_validation": {
        "knob": lambda v: {"form_error_message": v},
        "train": ["Please complete every field before submitting.",
                  "Some required fields are still empty."],
        "test": ["All three fields must be filled in.",
                 "Submission incomplete — every field is required."],
    },
    "extract_headline": {
        "knob": lambda v: {"headline": v},
        "train": ["METRO BUSINESS WIRE", "COASTAL GAZETTE"],
        "test": ["HARBOR COUNTY LEDGER", "SUMMIT VALLEY POST"],
    },
    "form_fill": {
        "knob": lambda v: {"form_fields": v},
        "train": [[{"name": "name", "label": "Your full name"},
                   {"name": "email", "label": "Work email address"},
                   {"name": "company", "label": "Employer name"}],
                  [{"name": "name", "label": "Full name"},
                   {"name": "email", "label": "E-mail"},
                   {"name": "company", "label": "Organization"}]],
        "test": [[{"name": "name", "label": "Name of attendee"},
                  {"name": "email", "label": "Contact e-mail"},
                  {"name": "company", "label": "Firm"}],
                 [{"name": "name", "label": "Customer name"},
                  {"name": "email", "label": "Primary email"},
                  {"name": "company", "label": "Company name"}]],
    },
    "ordered_navigation": {
        "knob": lambda v: {"docs": v},
        "train": [{"1": {"title": "Getting Started"},
                   "2": {"title": "Plans"},
                   "3": {"title": "Appendix"}},
                  {"1": {"title": "Intro"},
                   "2": {"title": "Pricing Docs"},
                   "3": {"title": "Reference Doc"}}],
        # 4b registration: six test title-sets, disjoint from the train pool
        # (titles render on the doc pages; navigation is by URL, so
        # solvability is unaffected — titles are the observation-level knob).
        "test": [{"1": {"title": "Overview"},
                  "2": {"title": "Tariffs"},
                  "3": {"title": "Footnotes"}},
                 {"1": {"title": "Onboarding Walk"},
                  "2": {"title": "Costs"},
                  "3": {"title": "Annex"}},
                 {"1": {"title": "Hello"},
                  "2": {"title": "Fees"},
                  "3": {"title": "Glossary"}},
                 {"1": {"title": "First Steps"},
                  "2": {"title": "Billing"},
                  "3": {"title": "Extras"}},
                 {"1": {"title": "Welcome Aboard"},
                  "2": {"title": "Charges"},
                  "3": {"title": "Index of Terms"}},
                 {"1": {"title": "Begin Here"},
                  "2": {"title": "Payment Plans"},
                  "3": {"title": "Supplement"}}],
    },
}

BRIEF_INSTRUCTION = (
    "You distill one transferable strategy brief for a web task family from "
    "two practice runs on the SAME small site. Write the specific procedure: "
    "which pages/URLs hold what, what to click, what to watch out for. "
    "CRITICAL: concrete VALUES (codes, names, passwords, headlines) change "
    "between instances — never bake a value into the brief; describe where "
    "to read each value instead. Under 1200 characters."
)


def _mk_stack(family: str, value) -> MutationStack:
    return MutationStack(name=f"{family}:{json.dumps(value, default=str)[:40]}",
                         setup=SetupMutation(FAMILIES[family]["knob"](value)))


def _brief_goal(brief: str, goal: str) -> str:
    return (f"[Strategy notes from an earlier practice session on this same "
            f"site — concrete values may differ now]\n{brief}\n\n"
            f"[Current task]\n{goal}")


def _format_actions(actions: list[dict]) -> str:
    """Render a step trace for the distiller: action type, the ACTUAL
    parameters (coordinates/selector/text — captured on executed entries by
    core/operator/loop.py), and navigated URL/title where recorded."""
    parts = []
    for a in actions:
        arg = a.get("parameters") or {}
        detail = a.get("detail") or {}
        bits = []
        if arg:
            bits.append(json.dumps(arg, default=str)[:80])
        if detail:
            bits.append(json.dumps(detail, default=str)[:80])
        suffix = f" ({'; '.join(bits)})" if bits else ""
        parts.append(f"{a['action_type']}{suffix} -> "
                     f"{'ok' if a['success'] else 'FAIL'}")
    return "; ".join(parts) or "(none)"


class Runner:
    def __init__(self, out_path: Path, only: set[str] | None = None,
                 delta_threshold: float = 0.15):
        from core.llm_service import LLMService
        self.handler = LLMService(tenant_id="default")._get_handler(
            workspace_id="default")
        self.client = self.handler.async_clients["opencode-go"]
        self.decider = lambda: PinnedVisionDecider(self.client, MODEL)
        self.only = only
        self.delta_threshold = delta_threshold
        self.families = [f for f in FAMILIES if not only or f in only]
        self.out_path = out_path
        self.record: dict = {
            "registered": {
                "model": MODEL, "seed": SEED, "max_steps": MAX_STEPS,
                "delta_threshold_pp": round(delta_threshold * 100, 1),
                "registered_at": "2026-09-21 (plan doc rev, commit 7ff7377cf)",
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "rollouts": [],
            "briefs": {},
        }
        self._t0 = time.monotonic()

    # -- persistence ---------------------------------------------------------

    def _checkpoint(self) -> None:
        self.out_path.write_text(json.dumps(self.record, indent=1, default=str))

    def _budget_left(self) -> bool:
        if time.monotonic() - self._t0 > WALL_CLOCK_CAP_S:
            print("!! WALL CLOCK CAP HIT — stopping, results checkpointed")
            return False
        return True

    # -- rollout with harness-error rerun discipline -------------------------

    async def _rollout(self, stage: str, arm: str, task: dict,
                       stack=None, goal_override: str | None = None,
                       env_label: str = "base") -> dict:
        reruns = 0
        while True:
            task_run = dict(task)
            if goal_override:
                task_run["goal"] = goal_override
            with EnvInstance() as instance:
                outcome = await run_rollout(
                    instance, task_run, max_steps=MAX_STEPS, arm=arm,
                    env_label=env_label, decider_factory=self.decider,
                    stack=stack)
            row = outcome.to_dict() | {
                "stage": stage, "actions": outcome.actions,
                "summary": outcome.summary[:300],
            }
            self.record["rollouts"].append(row)
            self._checkpoint()
            tag = (f"[{stage}] {arm}/{task['id']}/{env_label} -> "
                   f"{outcome.status.value} steps={outcome.steps} "
                   f"sec={outcome.seconds}")
            print(tag, flush=True)
            if outcome.status.value != "harness_error":
                return row
            reruns += 1
            if reruns > 2:
                print(f"  !! gave up after 2 reruns (harness error)")
                return row
            print("  rerun (harness error)", flush=True)

    def _stage_harness_rate(self, stage: str) -> float:
        rows = [r for r in self.record["rollouts"] if r["stage"] == stage]
        if not rows:
            return 0.0
        return sum(1 for r in rows
                   if r["status"] == "harness_error") / len(rows)

    # -- distillation ----------------------------------------------------------

    async def _distill(self, arm: str, family: str, task: dict,
                       train_rows: list[dict]) -> str:
        traj_lines = []
        for i, r in enumerate(train_rows, 1):
            traj_lines.append(
                f"Run {i} (outcome={'pass' if r['status']=='pass' else 'fail'}): "
                f"goal was: {task['goal']}\n  actions (with parameters and "
                f"navigated URL / page title where recorded): "
                f"{_format_actions(r.get('actions', []))}\n"
                f"  final summary: {r.get('summary') or '(none)'}")
        prompt = (f"{BRIEF_INSTRUCTION}\n\nTask family: {family}\n\n"
                  + "\n\n".join(traj_lines)
                  + '\n\nReply with ONLY a JSON object: {"brief": "..."}')
        try:
            resp = await asyncio.wait_for(self.client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system",
                           "content": BRIEF_INSTRUCTION},
                          {"role": "user", "content": prompt}],
                # glm-5.3-flash is a reasoning model: it burns budget on
                # reasoning_content first (probe: 500 cap -> empty content,
                # finish_reason=length), so briefs need headroom.
                max_tokens=2048, temperature=0.2,
            ), timeout=180)
            from core.operator.loop import _extract_json
            msg = resp.choices[0].message
            text = msg.content or ""
            if not text.strip():
                # reasoning-truncated: the answer usually sits at the end of
                # the reasoning stream — try it before giving up.
                text = getattr(msg, "reasoning_content", "") or ""
            data = _extract_json(text)
            brief = (data or {}).get("brief") or ""
        except Exception as exc:  # noqa: BLE001 — distillation is best-effort
            brief = ""
            print(f"  !! distill failed for {arm}/{family}: {exc}")
        brief = brief[:BRIFF_MAX_CHARS]
        self.record["briefs"][f"{arm}/{family}"] = brief
        self._checkpoint()
        print(f"[distill] {arm}/{family} -> {len(brief)} chars", flush=True)
        return brief

    # -- stages ----------------------------------------------------------------

    async def train_arm(self, arm: str) -> dict[str, list[dict]]:
        """Train rollouts per family; returns rows grouped for distillation."""
        grouped: dict[str, list[dict]] = {}
        stage = f"train_{arm}"
        for family in self.families:
            task = get_task(family)
            rows = []
            if arm == "A":       # static: base env twice (registered design)
                for inst in (1, 2):
                    if not self._budget_left():
                        return grouped
                    rows.append(await self._rollout(
                        stage, "A", task, stack=None,
                        env_label=f"base#{inst}"))
            else:                # curriculum: base + train-rotated
                if not self._budget_left():
                    return grouped
                rows.append(await self._rollout(
                    stage, "B", task, stack=None, env_label="base#1"))
                if not self._budget_left():
                    return grouped
                value = FAMILIES[family]["train"][0]
                rows.append(await self._rollout(
                    stage, "B", task, stack=_mk_stack(family, value),
                    env_label=f"train:{value}"))
            grouped[family] = rows
        rate = self._stage_harness_rate(stage)
        if rate > STAGE_HARNESS_ABORT:
            raise SystemExit(f"stage {stage}: harness-error rate {rate:.0%} "
                             f"exceeds {STAGE_HARNESS_ABORT:.0%} — aborting")
        return grouped

    async def distill_arm(self, arm: str, grouped: dict) -> None:
        for family in self.families:
            await self._distill(arm, family, get_task(family),
                                grouped.get(family, []))

    async def test_arm(self, arm: str) -> None:
        stage = f"test_{arm}"
        for family in self.families:
            task = get_task(family)
            brief = self.record["briefs"].get(f"{arm}/{family}", "")
            goal = _brief_goal(brief, task["goal"]) if brief else task["goal"]
            for i, value in enumerate(FAMILIES[family]["test"], 1):
                if not self._budget_left():
                    return
                await self._rollout(stage, arm, task,
                                    stack=_mk_stack(family, value),
                                    goal_override=goal,
                                    env_label=f"test:{value}")
        rate = self._stage_harness_rate(stage)
        if rate > STAGE_HARNESS_ABORT:
            raise SystemExit(f"stage {stage}: harness-error rate {rate:.0%} "
                             f"exceeds {STAGE_HARNESS_ABORT:.0%} — aborting")

    async def run(self) -> None:
        a_rows = await self.train_arm("A")
        b_rows = await self.train_arm("B")
        await self.distill_arm("A", a_rows)
        await self.distill_arm("B", b_rows)
        await self.test_arm("A")
        await self.test_arm("B")
        self._score()

    def _score(self) -> None:
        def tally(stage: str, family: str) -> tuple[int, int]:
            rows = [r for r in self.record["rollouts"]
                    if r["stage"] == stage and r["task_id"] == family
                    and r["status"] != "harness_error"]
            return (sum(1 for r in rows if r["status"] == "pass"), len(rows))

        summary: dict = {"per_family": {}, "totals": {}}
        raw_rates: dict = {}
        for stage in ("test_A", "test_B"):
            passes = total = 0
            per = {}
            for family in self.families:
                p, n = tally(stage, family)
                per[family] = f"{p}/{n}"
                passes, total = passes + p, total + n
            # Raw fraction for decisions; rounding is display-only.
            raw = (passes / total) if total else 0.0
            raw_rates[stage] = raw
            summary["totals"][stage] = {
                "passes": passes, "n": total,
                "rate": round(raw, 3),
            }
            summary["per_family"][stage] = per
        a, b = summary["totals"]["test_A"], summary["totals"]["test_B"]
        if a["n"] and b["n"]:
            delta = raw_rates["test_B"] - raw_rates["test_A"]
            # Epsilon guards the exact-boundary case (e.g. 2/6 gap vs the
            # 1/3 threshold) against binary-float underflow.
            met = delta + 1e-9 >= self.delta_threshold
        else:
            delta = None
            met = False
        summary["delta_pp"] = round(delta * 100, 1) if delta is not None else None
        summary["registered_threshold_pp"] = round(self.delta_threshold * 100, 1)
        summary["decision"] = (
            f"THRESHOLD MET (>= {self.delta_threshold * 100:.1f}pp)"
            if met
            else "NOT MET at the tested budget — benefit not demonstrated")
        self.record["score"] = summary
        self._checkpoint()
        print(json.dumps(summary, indent=1), flush=True)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="",
                        help="comma-separated family ids (dry-run)")
    parser.add_argument("--delta-threshold", type=float, default=0.15,
                        help="registered minimum improvement (fraction); "
                             "recorded in the score output")
    parser.add_argument("--test-only", action="store_true",
                        help="skip training; reuse briefs already in the "
                             "checkpoint (resume path)")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL", "")
    if "atom.db" in db_url and "/tmp" not in db_url:
        print(f"REFUSING: DATABASE_URL looks like the live dev DB ({db_url!r})")
        return 2

    only = {f.strip() for f in args.only.split(",") if f.strip()} or None
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    runner = Runner(out_dir / f"experiment_{stamp}.json", only=only,
                    delta_threshold=args.delta_threshold)

    if not args.test_only:
        await runner.run()
    else:
        await runner.test_arm("A")
        await runner.test_arm("B")
        runner._score()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
