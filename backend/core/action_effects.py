"""Shared action-effect vocabulary (registry metadata, no verifier logic).

``ActionDefinition.effects`` is the trusted, registration-owned declaration of
what an action does.  This module is the single vocabulary both the assignment
executor and the planner read, so a mutation cannot be classified one way by
the dispatch consumer and another way by the coverage inventory.

An effect entry may also carry ``"scope": "local"|"external"``.  Scope is
declarative, never inferred from a business name: a local durable write
(canvas, task, mini-app, goal) and a provider write can both use ``update`` or
``create`` but have different failure and readback models.
"""
from __future__ import annotations

from typing import Any, List, Optional, Set

#: Effect names that mean the action changes durable state.  ``plan_produced``
#: is deliberately absent: a plan is structural output, not execution proof.
MUTATING_EFFECTS = frozenset({
    "write", "create", "update", "delete", "send", "execute",
    "graph_updated", "record_created", "record_updated", "record_deleted",
    "goal_created", "goal_run_started", "goal_evaluated",
})

#: Explicit non-mutating effect declarations.
READ_EFFECTS = frozenset({"read", "read_only"})

#: Structural plan output (goals.decompose) — validated, never persisted proof.
PLAN_EFFECTS = frozenset({"plan_produced"})

VALID_SCOPES = frozenset({"local", "external"})


def effect_entries(effects_or_action: Any) -> List[dict]:
    """Return normalized effect mappings from an action or an effects list."""
    if hasattr(effects_or_action, "effects"):
        raw = getattr(effects_or_action, "effects", None) or []
    else:
        raw = effects_or_action or []
    entries: List[dict] = []
    for item in raw:
        if isinstance(item, dict):
            entries.append(item)
        elif isinstance(item, str):
            entries.append({"effect": item})
    return entries


def effect_names(effects_or_action: Any) -> List[str]:
    """Lower-cased effect names declared by an action or effects list."""
    return [
        str(item.get("effect") or "").strip().lower()
        for item in effect_entries(effects_or_action)
        if str(item.get("effect") or "").strip()
    ]


def effect_scopes(effects_or_action: Any) -> Set[str]:
    """Declared scopes (``local``/``external``) as a lower-cased set."""
    scopes: Set[str] = set()
    for item in effect_entries(effects_or_action):
        scope = str(item.get("scope") or "").strip().lower()
        if scope in VALID_SCOPES:
            scopes.add(scope)
    return scopes


def declares_mutation(effects_or_action: Any) -> bool:
    """True when the declaration names at least one durable mutation."""
    return any(
        name in MUTATING_EFFECTS for name in effect_names(effects_or_action))


def declares_read_only(effects_or_action: Any) -> bool:
    """True when every declared effect is explicitly non-mutating."""
    names = effect_names(effects_or_action)
    return bool(names) and all(
        name in READ_EFFECTS or name in PLAN_EFFECTS for name in names)


def declares_plan_output(effects_or_action: Any) -> bool:
    """True when every declared effect is explicitly non-mutating and at
    least one is plan output. Unknown effects are not treated as read proof."""
    names = set(effect_names(effects_or_action))
    known_non_mutating = READ_EFFECTS | PLAN_EFFECTS
    return (
        bool(names & PLAN_EFFECTS)
        and names <= known_non_mutating
    )


def declared_scope(effects_or_action: Any) -> Optional[str]:
    """The single declared scope, or None when absent/mixed."""
    scopes = effect_scopes(effects_or_action)
    return next(iter(scopes)) if len(scopes) == 1 else None


def mutation_scope(
    effects_or_action: Any, *, default: Optional[str] = None,
) -> Optional[str]:
    """Scope for a declared mutation, falling back to ``default``."""
    if not declares_mutation(effects_or_action):
        return None
    return declared_scope(effects_or_action) or default
