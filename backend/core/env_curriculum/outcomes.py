"""Rollout outcome taxonomy + two-stage difficulty-band admission.

Three outcome states, because a verifier FAIL and an infrastructure failure
are different animals (a provider 401 is not evidence the agent can't solve
the task):

- PASS            loop completed, frozen verifier accepted the end state
- AGENT_FAIL      loop completed, frozen verifier rejected the end state
- HARNESS_ERROR   loop/control/verifier machinery failed — excluded from
                  success-rate math and rerun, never counted as agent failure

Admission is two-stage (plan §Phase 5): cheap screening rejects clearly
impossible/trivial candidates, then an independent confirmation set decides
via a Wilson interval — because at n=3 a genuinely 90%-solvable mutation
screens as all-pass 27% of the time and a bare point estimate would admit on
that noise.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RolloutStatus(str, Enum):
    PASS = "pass"
    AGENT_FAIL = "agent_fail"
    HARNESS_ERROR = "harness_error"


@dataclass
class RolloutOutcome:
    task_id: str
    status: RolloutStatus
    env_label: str = "base"          # which env/mutation stack produced it
    steps: int | None = None
    seconds: float | None = None
    summary: str = ""
    error: str = ""                  # populated for HARNESS_ERROR
    evidence: dict[str, Any] = field(default_factory=dict)
    arm: str = ""                    # experiment arm (A/B), free-form
    actions: list[dict[str, Any]] = field(default_factory=list)  # step trace

    @property
    def counts_for_rate(self) -> bool:
        return self.status != RolloutStatus.HARNESS_ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "env_label": self.env_label,
            "steps": self.steps,
            "seconds": self.seconds,
            "error": self.error,
            "arm": self.arm,
        }


def pass_rate(outcomes: list[RolloutOutcome]) -> dict[str, Any]:
    """Success rate over scorable outcomes only. Harness errors are reported
    separately, never folded into the denominator."""
    scorable = [o for o in outcomes if o.counts_for_rate]
    harness = [o for o in outcomes if not o.counts_for_rate]
    n = len(scorable)
    passes = sum(1 for o in scorable if o.status == RolloutStatus.PASS)
    return {
        "n": n,
        "passes": passes,
        "rate": (passes / n) if n else None,
        "harness_errors": len(harness),
    }


def wilson_interval(
    successes: int, total: int, z: float = 1.96
) -> tuple[float, float]:
    """Wilson score interval on a binomial proportion.

    Unlike the Wald interval it stays inside [0, 1] at the boundaries,
    which is exactly where band decisions live (all-pass / all-fail sets).
    """
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    half = (
        z
        * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))
        / denom
    )
    return (max(0.0, center - half), min(1.0, center + half))


@dataclass
class BandSpec:
    """Difficulty band + confirmation protocol parameters.

    A mutation is admitted only if it is *statistically distinguishable from
    both trivial and impossible* AND its confirmation interval overlaps the
    band. Upstream (arXiv:2608.19880) targets ≈0.4–0.6 with a point estimate;
    we use the overlap rule because with confirm_n in single digits the
    interval is wide and interval-in-band would reject nearly everything.
    The reported interval carries the honest uncertainty either way.
    """

    low: float = 0.25
    high: float = 0.75
    screen_n: int = 3                # cheap screening rollouts
    confirm_n: int = 6               # independent confirmation rollouts
    z: float = 1.96


@dataclass
class AdmissionDecision:
    admitted: bool
    reason: str
    screen: dict[str, Any]
    confirm: dict[str, Any] | None
    interval: tuple[float, float] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "reason": self.reason,
            "screen": self.screen,
            "confirm": self.confirm,
            "interval": list(self.interval) if self.interval else None,
        }


def _needs(outcomes: list[RolloutOutcome], want: int, stage: str) -> list[RolloutOutcome]:
    scorable = [o for o in outcomes if o.counts_for_rate]
    if len(scorable) < want:
        raise ValueError(
            f"{stage} needs {want} scorable rollouts (non-harness), "
            f"got {len(scorable)} — rerun harness errors before deciding."
        )
    return scorable


def admit_mutation(
    screen: list[RolloutOutcome],
    confirm: list[RolloutOutcome],
    band: BandSpec | None = None,
) -> AdmissionDecision:
    """Two-stage admission decision from screening + confirmation rollouts.

    Rules, in order:
    1. Screening all-fail → reject (impossible). All other screens proceed.
    2. Confirmation interval must exclude both 0 and 1 — i.e. the confirmation
       set contains at least one pass AND at least one fail — proving the
       candidate is neither trivially solved nor unsolvable, with the Wilson
       bound as the statistical backstop.
    3. The confirmation interval must overlap [band.low, band.high].

    Harness errors never reach these rules: this function raises unless both
    stages have their full complement of scorable rollouts.
    """
    band = band or BandSpec()
    s = _needs(screen, band.screen_n, "screening")
    c = _needs(confirm, band.confirm_n, "confirmation")

    s_passes = sum(1 for o in s if o.status == RolloutStatus.PASS)
    screen_summary = {
        "n": len(s),
        "passes": s_passes,
        "rate": s_passes / len(s),
    }
    if s_passes == 0:
        return AdmissionDecision(
            admitted=False,
            reason="impossible: 0 passes in screening",
            screen=screen_summary,
            confirm=None,
            interval=None,
        )

    c_passes = sum(1 for o in c if o.status == RolloutStatus.PASS)
    lo, hi = wilson_interval(c_passes, len(c), z=band.z)
    confirm_summary = {
        "n": len(c),
        "passes": c_passes,
        "rate": c_passes / len(c),
    }

    if c_passes == 0:
        return AdmissionDecision(
            admitted=False,
            reason="impossible: 0 passes in confirmation",
            screen=screen_summary,
            confirm=confirm_summary,
            interval=(lo, hi),
        )
    if c_passes == len(c):
        return AdmissionDecision(
            admitted=False,
            reason="trivial: all confirmation rollouts passed "
                   "(interval touches 1.0 — indistinguishable from a task "
                   "the agent never fails)",
            screen=screen_summary,
            confirm=confirm_summary,
            interval=(lo, hi),
        )
    if hi < band.low:
        return AdmissionDecision(
            admitted=False,
            reason=f"too hard: confirmation upper bound {hi:.3f} below band "
                   f"floor {band.low}",
            screen=screen_summary,
            confirm=confirm_summary,
            interval=(lo, hi),
        )
    if lo > band.high:
        return AdmissionDecision(
            admitted=False,
            reason=f"too easy: confirmation lower bound {lo:.3f} above band "
                   f"ceiling {band.high}",
            screen=screen_summary,
            confirm=confirm_summary,
            interval=(lo, hi),
        )
    return AdmissionDecision(
        admitted=True,
        reason=f"in band: confirmation interval ({lo:.3f}, {hi:.3f}) "
               f"overlaps [{band.low}, {band.high}] and excludes 0 and 1",
        screen=screen_summary,
        confirm=confirm_summary,
        interval=(lo, hi),
    )
