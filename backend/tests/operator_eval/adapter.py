"""Env adapter: one isolated site instance ↔ one operator rollout.

Phase 2 of docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md. Binds the
operator_eval site (real Chromium via OperatorLoop) to the core rollout
taxonomy: every rollout returns PASS / AGENT_FAIL / HARNESS_ERROR, and the
classification rule is deliberately mechanical —

- ANY exception from session/loop/control machinery  → HARNESS_ERROR
  (a provider 401 or a crashed loop is not evidence about the agent);
- loop completed, verifier rejects                    → AGENT_FAIL;
- loop completed, verifier accepts                    → PASS.

The verifier itself is frozen: the adapter never wraps or post-processes
task["verify"], it only isolates its crashes as harness errors.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.env_curriculum.mutations import MutationStack          # noqa: E402
from core.env_curriculum.outcomes import RolloutOutcome, RolloutStatus  # noqa: E402
from test_site import (                                          # noqa: E402
    OBSERVE_RULE_KINDS,
    ACTION_RULE_KINDS,
    WORLD_SCHEMA,
    EvalSite,
    start_site,
)

RULE_KINDS = {**OBSERVE_RULE_KINDS, **ACTION_RULE_KINDS}


class EnvInstance:
    """One ephemeral site + token. One instance per rollout/concurrent arm —
    the site keeps no module-global state, so instances never see each other.

    Also the bridge for MutationStacks: applies a stack's setup (world keys
    only — schema-enforced) and rules (kind-validated) through the same
    validated paths the control API uses.
    """

    def __init__(self, base_world: dict | None = None):
        self.site, self._stop = start_site(port=0, base_world=base_world)

    @property
    def base_url(self) -> str:
        return self.site.base_url

    def reset(self) -> None:
        self.site.control_reset()

    def apply_stack(self, stack: MutationStack) -> None:
        """Validate against the site schema, then apply. Raises (never
        partially applies) on any illegal key or rule kind."""
        if stack.setup is not None:
            stack.setup.validate(WORLD_SCHEMA)
        if stack.rules is not None:
            stack.rules.validate(RULE_KINDS)
        self.reset()
        if stack.setup is not None:
            self.site.load_world_updates(stack.setup.world_updates)
        if stack.rules is not None:
            self.site.set_rules(
                observe=[{"kind": r.kind, **r.params} for r in stack.rules.observe],
                action=[{"kind": r.kind, **r.params} for r in stack.rules.action],
            )

    def close(self) -> None:
        self._stop()

    def __enter__(self) -> "EnvInstance":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


async def run_rollout(
    instance: EnvInstance,
    task: dict,
    model: str | None = None,
    max_steps: int = 15,
    arm: str = "",
    env_label: str = "base",
    loop_factory: Callable[[Any, int], Any] | None = None,
    session_factory: Callable[[], Any] | None = None,
    decider_factory: Callable[[], Any] | None = None,
    stack: "MutationStack | None" = None,
) -> RolloutOutcome:
    """One task rollout against `instance`. Mechanical classification per
    the module docstring; `loop_factory`/`session_factory`/`decider_factory`
    are injection points for deterministic tests or a pinned-model decider
    (default: real Chromium + vision decider). `stack` is applied AFTER the
    adapter's reset so the rollout runs against the mutated environment."""
    try:
        instance.reset()
        if stack is not None:
            instance.apply_stack(stack)   # apply_stack resets again first — idempotent
        if model:
            os.environ["ATOM_COMPUTER_USE_MODEL"] = model
        from core.operator.loop import OperatorLoop, JsonVisionDecider
        from core.operator.session import OperatorSession

        session = (session_factory or (lambda: OperatorSession(
            user_id="operator-eval")))()
        try:
            await session.start(start_url=instance.base_url + task["start_url"])
            loop = loop_factory(session, max_steps) if loop_factory else \
                OperatorLoop(backend=session,
                             decider=decider_factory() if decider_factory
                             else JsonVisionDecider(),
                             max_steps=max_steps)
            started = time.monotonic()
            result = await loop.run(task["goal"])
            seconds = time.monotonic() - started
        finally:
            await session.close()
    except Exception as exc:  # noqa: BLE001 — machinery failure, by design
        return RolloutOutcome(
            task_id=task["id"], status=RolloutStatus.HARNESS_ERROR,
            env_label=env_label, arm=arm, error=f"{type(exc).__name__}: {exc}",
        )

    try:
        passed = bool(task["verify"](result, instance.site))
    except Exception as exc:  # noqa: BLE001 — verifier crash is not agent signal
        return RolloutOutcome(
            task_id=task["id"], status=RolloutStatus.HARNESS_ERROR,
            env_label=env_label, arm=arm,
            error=f"verifier crashed: {type(exc).__name__}: {exc}",
        )

    return RolloutOutcome(
        task_id=task["id"],
        status=RolloutStatus.PASS if passed else RolloutStatus.AGENT_FAIL,
        env_label=env_label, arm=arm,
        steps=result.get("steps"),
        seconds=round(seconds, 1),
        summary=(result.get("summary") or "")[:200],
        evidence=dict(instance.site.evidence),
        actions=result.get("actions") or [],
    )
