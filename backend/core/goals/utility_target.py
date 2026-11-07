"""Deterministic utility-target scoring for goal trajectories (GOAL-02).

A utility target is an explicit, persisted optimization signal attached to a
``GoalObjective`` (``metadata_json["utility_target"]``). It ranks *completed*
candidate trajectories (``GoalRun`` rows) by one durable metric.

The target is an optimization signal, never a replacement for objective
satisfaction. An outcome that is incomplete, violated a constraint, or carries
missing/malformed/non-finite evidence is ineligible and cannot outrank a
completed outcome, whatever its metric value. Ineligible outcomes get
``utility=None`` and no rank — unknown stays unknown.

This module is deliberately pure: validation, scoring, and ranking only. The
durable records live in the existing ``GoalObjective`` / ``GoalRun`` tables;
``GoalService`` persists the target and feeds run rows here. No second goal
engine, evaluator store, or lifecycle.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

# Durable GoalRun fields that may be named by a utility target. Keeping the
# allowlist explicit prevents a target from pointing at caller-supplied
# numbers that were never observed as trajectory evidence.
UTILITY_METRICS: Dict[str, str] = {
    "human_interventions": "goal_run.human_interventions",
    "steps_executed": "goal_run.steps_executed",
    "replan_count": "goal_run.replan_count",
}

UTILITY_DIRECTIONS = ("maximize", "minimize")

_TARGET_KEYS = frozenset({"metric", "direction", "source", "description"})


class UtilityTargetError(ValueError):
    """Raised when a utility target is not an explicit accepted definition."""


def normalize_utility_target(raw: Any) -> Dict[str, Any]:
    """Validate and normalize a persisted utility target.

    Explicit is required: metric, direction and source must all be supplied
    (source may only name the durable GoalRun evidence namespace). No silent
    defaults — a malformed target must not start ranking trajectories.
    """
    if not isinstance(raw, dict):
        raise UtilityTargetError("utility target must be an object")
    unknown = set(raw) - _TARGET_KEYS
    if unknown:
        raise UtilityTargetError(
            "utility target has unsupported keys: " + ", ".join(sorted(unknown)))

    metric = str(raw.get("metric") or "").strip()
    if metric not in UTILITY_METRICS:
        raise UtilityTargetError(
            "utility target metric must be one of: "
            + ", ".join(sorted(UTILITY_METRICS)))

    direction = str(raw.get("direction") or "").strip().lower()
    if direction not in UTILITY_DIRECTIONS:
        raise UtilityTargetError(
            "utility target direction must be one of: "
            + ", ".join(UTILITY_DIRECTIONS))

    source = str(raw.get("source") or "").strip()
    expected_source = UTILITY_METRICS[metric].split(".", 1)[0]
    if source != expected_source:
        raise UtilityTargetError(
            f"utility target source must be '{expected_source}' for metric "
            f"'{metric}'")

    description = raw.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise UtilityTargetError("utility target description must be a string")

    return {
        "metric": metric,
        "direction": direction,
        "source": source,
        "description": description[:500],
    }


def finite_metric(value: Any) -> Optional[float]:
    """Return a finite non-negative integral count, or None when invalid.

    The allowed utility metrics are durable COUNT fields (GoalRun counters),
    not arbitrary signed measurements. Negative values, fractional values,
    booleans, strings, and non-finite numbers are unknown. A huge Python int
    that cannot be represented as a float is also unknown rather than letting
    ``float()`` raise OverflowError into a ranking caller.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value < 0:
            return None
        try:
            number = float(value)
        except OverflowError:
            return None
    elif isinstance(value, float):
        if value < 0 or not math.isfinite(value):
            return None
        if not value.is_integer():
            return None
        number = value
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def utility_score(target: Dict[str, Any], value: float) -> float:
    """Normalize a metric so a *higher* utility is always better."""
    normalized = normalize_utility_target(target)
    if normalized["direction"] == "maximize":
        return float(value)
    return -float(value)


def outcome_from_goal_run(run: Dict[str, Any]) -> Dict[str, Any]:
    """Project a durable GoalRun row into a candidate outcome.

    Completion comes from persisted run state, not from a caller's score.
    ``failed`` / ``cancelled`` runs are incomplete or stopped; only an
    ``achieved`` run is constraint-eligible. There is deliberately no
    inferred safety marker here: actual GoalRun decision-log producers do not
    emit a standard constraint-kind vocabulary, so inventing one would make
    the gate claim stronger than the evidence. Callers with trusted
    constraint evidence can set ``constraints_ok`` explicitly on a candidate
    (the pure ranking gate honors it).
    """
    status = str(run.get("status") or "")
    completed = status == "achieved"
    metrics = {
        field: run.get(field)
        for path in UTILITY_METRICS.values()
        for field in (path.split(".", 1)[1],)
    }
    return {
        "id": str(run.get("id") or ""),
        "completed": completed,
        "constraints_ok": completed,
        "metrics": metrics,
        "evidence": {
            "source": "goal_runs",
            "run_id": str(run.get("id") or ""),
            "goal_id": str(run.get("goal_id") or ""),
            "status": status,
            "supervision_mode": run.get("supervision_mode"),
            "updated_at": run.get("updated_at"),
        },
    }


def rank_trajectories(target: Any,
                      outcomes: Iterable[Any]) -> Dict[str, Any]:
    """Rank candidate outcomes against one persisted utility target.

    Eligible outcomes are completed, constraint-clean, and carry a finite
    metric. They are ordered by normalized utility (higher first), then by a
    stable id tie-break. Every ineligible outcome is retained with a reason and
    no rank so the caller can show what was withheld and why.
    """
    normalized = normalize_utility_target(target)
    metric = normalized["metric"]
    entries: List[Dict[str, Any]] = []

    for index, outcome in enumerate(outcomes or []):
        if not isinstance(outcome, dict):
            entries.append({
                "id": "",
                "utility": None,
                "rank": None,
                "eligible": False,
                "reason": "malformed_candidate",
                "evidence": {},
                "_index": index,
            })
            continue

        candidate_id = str(outcome.get("id") or outcome.get("run_id") or "")
        metrics = outcome.get("metrics")
        raw_value = metrics.get(metric) if isinstance(metrics, dict) else None
        value = finite_metric(raw_value)
        completed = outcome.get("completed") is True
        constraints_ok = outcome.get("constraints_ok") is True

        if not candidate_id:
            reason = "missing_identity"
        elif not completed:
            reason = "not_completed"
        elif not constraints_ok:
            reason = "constraint_failed"
        elif value is None:
            reason = "metric_unknown"
        else:
            reason = "ranked"

        eligible = reason == "ranked"
        entries.append({
            "id": candidate_id,
            "utility": utility_score(normalized, value) if eligible else None,
            "rank": None,
            "eligible": eligible,
            "reason": reason,
            "evidence": outcome.get("evidence") or {},
            "_index": index,
        })

    eligible_entries = [e for e in entries if e["eligible"]]
    eligible_entries.sort(key=lambda item: (-item["utility"], item["id"]))
    for position, entry in enumerate(eligible_entries, start=1):
        entry["rank"] = position

    ineligible_entries = [e for e in entries if not e["eligible"]]
    ineligible_entries.sort(key=lambda item: (item["id"], item["_index"]))
    ordered = eligible_entries + ineligible_entries
    for entry in ordered:
        entry.pop("_index", None)

    return {
        "target": normalized,
        "ranking": ordered,
        "winner": eligible_entries[0]["id"] if eligible_entries else None,
        "eligible_count": len(eligible_entries),
    }
