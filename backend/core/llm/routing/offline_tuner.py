"""
Offline Routing Weight Tuner.

Multi-objective optimizer that replays OBSERVED feedback to find the best
{quality, cost, speed} weight configuration per task type. Writes the winning
weights back to the live router via ``_set_cached_weights`` — no hot-path
code is added.

Design grounded in:
- BOute (MLSys 2026): MOBO for LLM serving cost/quality/latency (38% avg savings).
- Multi-Objective HPO for LLM/RAG (arXiv 2502.18635): GP surrogate + qLogNEHVI.
- OmniRouter (KDD): constrained optimization from (query, model, outcome) pairs.

This implementation uses a lightweight random-restart + Pareto-frontier search
(no scipy/botorch dependency). It's the recommended first iteration; upgrade
to GP-MOBO once the replay harness is proven and feedback volume justifies it.

Usage:
    from core.llm.routing.offline_tuner import tune_routing_weights
    result = await tune_routing_weights(router, tenant_id="default")
    # → inspects _preference_data + _ema_scores, searches weight space,
    #   writes winners via _set_cached_weights, returns a summary.
"""
from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum feedback rows required to tune a task type (below this, the online
# EMA + predictor blend already adapts and there's too little signal).
MIN_SAMPLES_PER_TASK = 50

# How many candidate weight-sets to evaluate per task type.
N_CANDIDATES = 200

# Default weights if no feedback exists for a task type.
DEFAULT_TASK_WEIGHTS: Dict[str, Dict[str, float]] = {
    "code_generation": {"quality": 0.5, "cost": 0.2, "speed": 0.3},
    "question_answering": {"quality": 0.4, "cost": 0.3, "speed": 0.3},
    "reasoning": {"quality": 0.6, "cost": 0.1, "speed": 0.3},
    "tool_use": {"quality": 0.3, "cost": 0.3, "speed": 0.4},
    "vision": {"quality": 0.5, "cost": 0.2, "speed": 0.3},
    "extraction": {"quality": 0.3, "cost": 0.4, "speed": 0.3},
}
DEFAULT_FALLBACK = {"quality": 0.4, "cost": 0.3, "speed": 0.3}


def _normalize_weights(q: float, c: float, s: float) -> Dict[str, float]:
    """Normalize a weight triple so it sums to 1.0."""
    total = q + c + s
    if total <= 0:
        return dict(DEFAULT_FALLBACK)
    return {"quality": q / total, "cost": c / total, "speed": s / total}


def _random_weights() -> Dict[str, float]:
    """Sample a random weight set on the simplex."""
    q, c, s = random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1)
    return _normalize_weights(q, c, s)


def _evaluate_candidate(
    weights: Dict[str, float],
    feedback_rows: List[dict],
    model_specs: Dict[str, Any],
) -> Tuple[float, float, float]:
    """Replay feedback under a candidate weight-set.

    Returns (satisfaction, total_cost, p95_latency). Each feedback row carries
    the model_id, success, actual_cost, actual_latency_ms. We don't re-route
    (that would need a live call); instead we approximate the score each model
    WOULD have received under these weights, and pick the top-ranked model for
    each row — then report the outcome that model actually had.

    This is a counterfactual replay: "if we'd used these weights, would the
    winning model for each historical query have satisfied the user?"
    """
    qw, cw, sw = weights["quality"], weights["cost"], weights["speed"]

    satisfaction_scores: List[float] = []
    costs: List[float] = []
    latencies: List[float] = []

    for row in feedback_rows:
        models_in_row = row.get("models", {})
        if not models_in_row:
            continue

        # Score each candidate model under the trial weights.
        best_model = None
        best_score = -1.0
        for model_id, spec in models_in_row.items():
            # Base score = weighted sum (same formula as _combined_model_score).
            max_cost = max(
                (s.get("cost_per_million", 1.0) for s in models_in_row.values()),
                default=1.0,
            ) or 1.0
            cost_score = 1.0 - (spec.get("cost_per_million", 0) / max_cost)
            score = (
                spec.get("quality_score", 0.5) * qw
                + cost_score * cw
                + spec.get("speed_score", 0.5) * sw
            )
            if score > best_score:
                best_score = score
                best_model = model_id

        # Report the actual outcome the winning model had on this row.
        if best_model:
            outcome = models_in_row[best_model]
            satisfaction_scores.append(outcome.get("success", 0.0))
            costs.append(outcome.get("actual_cost", 0.0) or 0.0)
            latencies.append(outcome.get("actual_latency_ms", 1000.0) or 1000.0)

    if not satisfaction_scores:
        return (0.0, 0.0, float("inf"))

    satisfaction = sum(satisfaction_scores) / len(satisfaction_scores)
    total_cost = sum(costs)
    latencies.sort()
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[min(p95_idx, len(latencies) - 1)]

    return (satisfaction, total_cost, p95)


def _is_dominated(
    candidate: Tuple[float, float, float],
    incumbent: Tuple[float, float, float],
) -> bool:
    """Check if candidate is dominated by incumbent (Pareto).

    Objectives: maximize satisfaction, minimize cost, minimize latency.
    """
    c_sat, c_cost, c_lat = candidate
    i_sat, i_cost, i_lat = incumbent
    return i_sat >= c_sat and i_cost <= c_cost and i_lat <= c_lat


async def tune_routing_weights(
    router: Any,
    tenant_id: str = "default",
    task_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the offline tuner and write winners back to the live router.

    Args:
        router: A LearningBasedRouter instance (must have _preference_data,
                _ema_scores, _model_registry, _set_cached_weights).
        tenant_id: Tenant to tune for.
        task_types: Specific task types to tune (default: all with enough data).

    Returns:
        Summary dict with per-task results.
    """
    results: Dict[str, Any] = {"tenant_id": tenant_id, "tasks_tuned": []}

    # Gather feedback data per task type.
    task_data: Dict[str, List[dict]] = defaultdict(list)

    for key, feedback_list in router._preference_data.items():
        if not key.startswith(f"{tenant_id}:"):
            continue
        task = key.split(":", 1)[1] if ":" in key else key
        rows_for_task = []
        for fb in feedback_list:
            model_id = fb.model_id
            spec = router._model_registry.get(model_id)
            if not spec:
                continue
            rows_for_task.append({
                "task": task,
                "models": {
                    model_id: {
                        "quality_score": spec.quality_score,
                        "cost_per_million": spec.cost_per_million,
                        "speed_score": spec.speed_score,
                        "success": 1.0 if (fb.success and getattr(fb, "quality_satisfied", True)) else 0.0,
                        "actual_cost": fb.actual_cost or (spec.cost_per_million * 0.001),
                        "actual_latency_ms": fb.actual_latency_ms or 1000.0,
                    }
                },
            })
        task_data[task].extend(rows_for_task)

    # If no task types specified, tune all with enough data.
    if task_types is None:
        task_types = [t for t, rows in task_data.items() if len(rows) >= MIN_SAMPLES_PER_TASK]

    if not task_types:
        results["reason"] = (
            f"No task types with ≥{MIN_SAMPLES_PER_TASK} feedback rows. "
            "The online EMA + predictor blend is sufficient until more data accumulates."
        )
        logger.info(results["reason"])
        return results

    for task in task_types:
        rows = task_data.get(task, [])
        if len(rows) < MIN_SAMPLES_PER_TASK:
            results["tasks_tuned"].append({
                "task": task,
                "status": "skipped",
                "reason": f"Only {len(rows)} samples (need ≥{MIN_SAMPLES_PER_TASK})",
            })
            continue

        # Evaluate candidates: random search over the weight simplex.
        # Include the current weights as a seed (warm-start).
        cache_key = f"{tenant_id}:{task}"
        current_weights = router._router_cache.get(
            cache_key,
            DEFAULT_TASK_WEIGHTS.get(task, DEFAULT_FALLBACK),
        )
        candidates = [current_weights] + [_random_weights() for _ in range(N_CANDIDATES)]

        pareto_front: List[Tuple[Dict[str, float], Tuple[float, float, float]]] = []
        for w in candidates:
            metrics = _evaluate_candidate(w, rows, router._model_registry)
            # Check if dominated by any incumbent.
            dominated = any(_is_dominated(metrics, inc[1]) for inc in pareto_front)
            if not dominated:
                # Remove any incumbents dominated by this candidate.
                pareto_front = [
                    (iw, im) for iw, im in pareto_front
                    if not _is_dominated(im, metrics)
                ]
                pareto_front.append((w, metrics))

        if not pareto_front:
            results["tasks_tuned"].append({"task": task, "status": "no_valid_candidates"})
            continue

        # Select the best from the Pareto frontier.
        # Strategy: maximize satisfaction, then minimize cost, then minimize latency.
        # (The operator can adjust this scalarization preference.)
        best_weights, best_metrics = max(
            pareto_front,
            key=lambda x: (x[1][0], -x[1][1], -x[1][2]),
        )

        # Write the winner back to the live router.
        router._set_cached_weights(cache_key, best_weights, tenant_id)

        results["tasks_tuned"].append({
            "task": task,
            "status": "tuned",
            "samples": len(rows),
            "candidates_evaluated": len(candidates),
            "pareto_front_size": len(pareto_front),
            "best_weights": best_weights,
            "objectives": {
                "satisfaction": round(best_metrics[0], 4),
                "total_cost": round(best_metrics[1], 6),
                "p95_latency_ms": round(best_metrics[2], 1),
            },
            "previous_weights": current_weights,
        })
        logger.info(
            f"[OfflineTuner] Tuned {task}: weights={best_weights} "
            f"satisfaction={best_metrics[0]:.3f} cost=${best_metrics[1]:.4f} "
            f"p95={best_metrics[2]:.0f}ms (pareto={len(pareto_front)})"
        )

    results["tasks_tuned_count"] = sum(1 for t in results["tasks_tuned"] if t.get("status") == "tuned")
    return results
