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

from collections.abc import Sequence
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

#: Every effect name the shared classifier understands.  Anything else is
#: unqualified and can never be used as a read/plan exemption.
KNOWN_NON_MUTATING_EFFECTS = READ_EFFECTS | PLAN_EFFECTS
KNOWN_EFFECTS = MUTATING_EFFECTS | KNOWN_NON_MUTATING_EFFECTS

VALID_SCOPES = frozenset({"local", "external"})


def _raw_declaration(effects_or_action: Any) -> Any:
    if hasattr(effects_or_action, "effects"):
        return getattr(effects_or_action, "effects", None)
    return effects_or_action


def _declaration_items(effects_or_action: Any) -> Optional[List[Any]]:
    """Raw declaration entries, or ``None`` when the container is invalid.

    A declaration is a sequence of entries.  A bare string/mapping (or any
    other non-sequence) is not iterable metadata; treating it as one would
    invent effect names from its characters/keys.
    """
    raw = _raw_declaration(effects_or_action)
    if raw is None:
        return None
    if isinstance(raw, (str, bytes, bytearray, dict)):
        return None
    if not isinstance(raw, Sequence):
        return None
    return list(raw)


def _effect_name(item: Any) -> Optional[str]:
    """Normalized effect name for one raw entry, or ``None`` if unusable."""
    if isinstance(item, str):
        name = item
    elif isinstance(item, dict):
        name = item.get("effect")
    else:
        return None
    if not isinstance(name, str):
        return None
    name = name.strip().lower()
    return name or None


def effect_entries(effects_or_action: Any) -> List[dict]:
    """Return normalized effect mappings from an action or an effects list.

    Only the container is normalized: mapping entries are returned as-is and
    bare strings become ``{"effect": name}``.  A malformed non-mapping entry is
    preserved as an empty mapping (never silently dropped), and an invalid
    container normalizes to an empty list.  Callers must use
    :func:`effect_declaration_problems` (or the ``declares_*`` helpers) before
    treating a declaration as proof of non-mutation.
    """
    items = _declaration_items(effects_or_action)
    if items is None:
        return []
    entries: List[dict] = []
    for item in items:
        if isinstance(item, dict):
            entries.append(item)
        elif isinstance(item, str):
            entries.append({"effect": item})
        else:
            # Keep malformed entries visible to the classifier as an entry with
            # no effect name; they must never vanish into a read/plan exemption.
            entries.append({})
    return entries


def effect_names(effects_or_action: Any) -> List[str]:
    """Lower-cased effect names declared by an action or effects list."""
    names: List[str] = []
    for item in _declaration_items(effects_or_action) or []:
        name = _effect_name(item)
        if name:
            names.append(name)
    return names


def effect_declaration_problems(effects_or_action: Any) -> List[str]:
    """Reasons the raw declaration is not fully valid and explicit.

    A read/plan exemption requires an empty problem list: every raw entry must
    be a mapping (or a bare effect-name string) with a non-empty effect name
    from the shared known vocabulary.  Missing declarations and invalid raw
    containers are unqualified, never an implicit read proof.
    """
    items = _declaration_items(effects_or_action)
    if items is None:
        raw = _raw_declaration(effects_or_action)
        return [
            "effect declaration is missing"
            if raw is None
            else (
                "effect declaration container "
                f"{type(raw).__name__} is not a sequence")
        ]
    problems: List[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, (dict, str)):
            problems.append(
                f"effect entry {index} is not a mapping or string")
            continue
        name = _effect_name(item)
        if name is None:
            problems.append(f"effect entry {index} has no effect name")
            continue
        if name not in KNOWN_EFFECTS:
            problems.append(
                f"effect entry {index} declares unknown effect {name!r}")
    return problems


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
    """True when every declared effect is explicitly non-mutating.

    Malformed entries, unknown names, missing declarations and invalid
    containers stay unqualified: no entry may disappear during normalization.
    """
    if effect_declaration_problems(effects_or_action):
        return False
    names = effect_names(effects_or_action)
    return bool(names) and all(
        name in KNOWN_NON_MUTATING_EFFECTS for name in names)


def declares_plan_output(effects_or_action: Any) -> bool:
    """True when every declared effect is explicitly non-mutating and at
    least one is plan output. Unknown/malformed entries are not read proof."""
    if effect_declaration_problems(effects_or_action):
        return False
    names = set(effect_names(effects_or_action))
    return (
        bool(names & PLAN_EFFECTS)
        and names <= KNOWN_NON_MUTATING_EFFECTS
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
