"""Env-curriculum core: primitives for evolving-environment agent training.

Ports the environment-side half of Google's EnvHarness (arXiv:2608.19880,
apache 2.0) for Atom: a fail-closed sandbox for generated mutation code, a
rollout outcome taxonomy that separates agent failures from harness failures,
and the two-stage (screen then confirm) difficulty-band admission protocol.

Environment-agnostic by design: this package never imports from tests/ and
knows nothing about specific environments — bridges live next to the
environments they adapt (e.g. backend/tests/operator_eval/).

Design doc: docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md (rev 2).
"""

from core.env_curriculum.outcomes import (
    AdmissionDecision,
    BandSpec,
    RolloutOutcome,
    RolloutStatus,
    admit_mutation,
    pass_rate,
    wilson_interval,
)
from core.env_curriculum.sandbox import (
    MutationSandboxUnavailable,
    execute_mutation,
)

__all__ = [
    "AdmissionDecision",
    "BandSpec",
    "MutationSandboxUnavailable",
    "RolloutOutcome",
    "RolloutStatus",
    "admit_mutation",
    "execute_mutation",
    "pass_rate",
    "wilson_interval",
]
