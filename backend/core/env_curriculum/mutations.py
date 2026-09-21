"""Declarative mutation vocabulary (env-agnostic core shapes).

Mutations are DATA, not code, until a validated reason exists to generate
code (plan §Phase 3: hand-authored first). A `MutationStack` names what a
bridge should do to an environment before a rollout:

- SetupMutation  — replace values in the environment's MUTABLE world
                   (start-state change; upstream `Setup` layers).
- RulesMutation  — declare observation filters and action interceptors
                   (upstream `Rules` layers).

The world/evidence split is enforced by the environment bridge: world keys
are the only legal mutation targets, and the bridge's schema validation
rejects anything else. These dataclasses carry the generic shapes and
validation that every bridge shares.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetupMutation:
    """Key/value replacements applied to the env's mutable world before reset."""

    world_updates: dict[str, Any]

    def validate(self, world_schema: set[str]) -> None:
        illegal = set(self.world_updates) - world_schema
        if illegal:
            raise ValueError(
                f"Setup targets non-world keys {sorted(illegal)} — "
                f"mutations may only write world keys "
                f"(evidence/verifier state is immutable)."
            )


@dataclass(frozen=True)
class RuleSpec:
    """One declarative rule. `kind` is interpreted by the environment bridge."""

    kind: str
    params: dict[str, Any] = field(default_factory=dict)

    def validate(self, known_kinds: dict[str, set[str]]) -> None:
        if self.kind not in known_kinds:
            raise ValueError(
                f"Unknown rule kind {self.kind!r} — bridge supports "
                f"{sorted(known_kinds)}."
            )
        required = known_kinds[self.kind]
        missing = required - set(self.params)
        if missing:
            raise ValueError(f"Rule {self.kind!r} missing params {sorted(missing)}.")


@dataclass(frozen=True)
class RulesMutation:
    observe: tuple[RuleSpec, ...] = ()
    action: tuple[RuleSpec, ...] = ()

    def validate(self, known_kinds: dict[str, set[str]]) -> None:
        for rule in (*self.observe, *self.action):
            rule.validate(known_kinds)


@dataclass(frozen=True)
class MutationStack:
    """A named, ordered mutation candidate for one environment."""

    name: str
    setup: SetupMutation | None = None
    rules: RulesMutation | None = None
    notes: str = ""

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "setup": dict(self.setup.world_updates) if self.setup else {},
            "rules": {
                "observe": [vars(r) | {"params": dict(r.params)} for r in (self.rules.observe if self.rules else ())],
                "action": [vars(r) | {"params": dict(r.params)} for r in (self.rules.action if self.rules else ())],
            },
            "notes": self.notes,
        }
