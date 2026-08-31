"""BPE workspace admin API — observability + management for the agent harness.

The BPE subsystem (docs/architecture/BPE_WORKSPACE_PLAN.md) is self-regulating
by default (consult gating and genome application flip themselves from
recorded episode evidence), so this surface is primarily *observability* with
narrow, gated management:

- GET  /api/v1/admin/bpe/overview        → flags (+source), effective modes,
                                           consult-policy per-agent state,
                                           evolution population + readiness,
                                           cached workspace summaries,
                                           telemetry aggregates, meta-action
                                           definitions (user guidance).
- GET  /api/v1/admin/bpe/workspaces/detail → full serialized state for one
                                           cached (workspace, agent, scope).
- POST /api/v1/admin/bpe/evolution/apply/{family} → request application of the
                                           family's best genome. Still gated by
                                           the same automation/evidence rules
                                           as the automatic path — no bypass.

Flag overrides (kill-switches / tri-state modes) are managed through the
shared runtime-settings surface: PUT/DELETE /api/v1/admin/settings/{key}
(catalog category "BPE Agent Workspace"). Env vars always win over UI rows.

All endpoints require an admin role (super_admin/owner/admin/workspace_admin).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.bpe import actions as bpe_actions
from core.bpe import automation, consult_policy, evolution, workspace
from core.bpe.telemetry import SPAN_NAME_PREFIX
from core.database import get_db
from core.observability.tracing import (
    aggregate_spans,
    get_recent_spans,
)
from core.runtime_settings import resolve_setting
from core.settings_catalog import SETTING_CATALOG, find_spec

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/bpe", tags=["BPE Workspace"])

_ADMIN_ROLES = (
    "super_admin",
    "owner",
    "admin",
    "workspace_admin",
)

_BPE_FLAG_KEYS = (
    "ATOM_BPE_WORKSPACE_ENABLED",
    "ATOM_BPE_AUTOMATION",
    "ATOM_BPE_CONSULT_POLICY",
    "ATOM_BPE_EVOLUTION",
    "ATOM_BPE_EVOLUTION_ENABLED",
    "ATOM_BPE_DATA_DIR",
)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin gate (same roles as the runtime-settings surface)."""
    role = getattr(current_user, "role", None)
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def _flag_states(db: Session) -> Dict[str, Dict[str, Any]]:
    """Resolved value + source for every cataloged BPE flag."""
    out: Dict[str, Dict[str, Any]] = {}
    for key in _BPE_FLAG_KEYS:
        spec = find_spec(key)
        if spec is None:
            continue
        res = resolve_setting(key, db=db)
        out[key] = {"value": res.value, "source": res.source,
                    "type": spec.type, "description": spec.description}
    return out


def _evolution_readiness() -> list[Dict[str, Any]]:
    """Per-family evidence state against the auto-apply thresholds."""
    snap = evolution.get_population().snapshot()
    rows: list[Dict[str, Any]] = []
    for family, individuals in snap.items():
        best = max((i.get("fitness") or 0.0) for i in individuals) if individuals else 0.0
        rows.append({
            "family": family,
            "evaluated_genomes": len(individuals),
            "best_fitness": best,
            "apply_ready": automation.evolution_apply_ready(
                {family: individuals}),
        })
    return rows


def _telemetry_summary() -> Dict[str, Any]:
    """Recent bpe.* spans: aggregates + automation-flip audit trail."""
    spans = get_recent_spans(limit=500, name_prefix=f"{SPAN_NAME_PREFIX}.")
    agg = aggregate_spans(spans)
    for entry in agg.values():
        entry["error_count"] = 0
    for span in spans:
        entry = agg.get(span.get("name", "unknown"))
        if entry is not None and span.get("status") == "error":
            entry["error_count"] += 1
    flips = [
        {
            "at": span.get("ended_at"),
            "detail": (span.get("attributes") or {}),
        }
        for span in spans
        if span.get("name") == f"{SPAN_NAME_PREFIX}.automation_flip"
    ][:50]
    return {
        "window_spans": len(spans),
        "aggregate": agg,
        "automation_flips": flips,
    }


def _meta_action_docs() -> list[Dict[str, Any]]:
    """The registered workspace.* actions (guidance copy for the UI)."""
    try:
        from core.action_registry import action_registry

        return [
            {"name": a.name, "description": a.description,
             "parameters": a.parameters_schema}
            for a in action_registry.get_all_definitions()
            if a.name.startswith("workspace.")
        ]
    except Exception:
        return []


@router.get("/overview")
async def bpe_overview(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """One aggregated status payload for the management page."""
    try:
        policy = consult_policy.get_consult_policy()
        policy_snapshot = policy.snapshot()
        for agent_id, state in policy_snapshot.items():
            state["render_mode"] = policy.render_mode(agent_id)
            state["suppressed"] = policy.value_below_threshold(agent_id)
            state["harness_call_rate"] = round(policy.harness_call_rate(agent_id), 3)

        data_dir = None
        persisted_files = 0
        try:
            from core.bpe.persistence import DATA_DIR

            data_dir = str(DATA_DIR)
            persisted_files = sum(
                1 for _ in DATA_DIR.glob("*.json")) if DATA_DIR.exists() else 0
        except Exception:
            pass

        return {
            "success": True,
            "data": {
                "flags": _flag_states(db),
                "modes": {
                    "workspace_enabled": bpe_actions.bpe_enabled(),
                    "automation_active": automation.automation_enabled(),
                    "consult_gating_active": automation.consult_gating_active(),
                    "evolution_apply_enabled": automation.evolution_apply_enabled(),
                },
                "thresholds": {
                    "min_episodes_for_value_gate":
                        consult_policy.MIN_EPISODES_FOR_VALUE_GATE,
                    "recall_only_share": consult_policy.RECALL_ONLY_SHARE,
                    "recall_only_min_episodes":
                        consult_policy.RECALL_ONLY_MIN_EPISODES,
                    "min_evaluated_genomes": automation.MIN_EVALUATED_GENOMES,
                    "evolution_apply_fitness": automation.EVOLUTION_APPLY_FITNESS,
                    "population_size": evolution.POPULATION_SIZE,
                    "target_call_rate": evolution.TARGET_CALL_RATE,
                },
                "active_bounds": workspace.get_active_bounds(),
                "gene_bounds": {
                    gene: {"min": lo, "max": hi}
                    for gene, (lo, hi) in workspace.GENE_BOUNDS.items()
                },
                "consult_policy": policy_snapshot,
                "population": evolution.get_population().snapshot(),
                "evolution_readiness": _evolution_readiness(),
                "workspaces": workspace.list_workspace_summaries(),
                "persistence": {"data_dir": data_dir,
                                "snapshot_files": persisted_files},
                "telemetry": _telemetry_summary(),
                "meta_actions": _meta_action_docs(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BPE overview failed: {e}")
        raise HTTPException(status_code=500, detail="BPE status unavailable")


@router.get("/workspaces/detail")
async def bpe_workspace_detail(
    workspace_id: str,
    agent_id: str,
    scope_key: str = "",
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Full serialized state for one cached workspace scope (read-only)."""
    snapshot = workspace.get_workspace_snapshot(workspace_id, agent_id, scope_key)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Workspace scope not cached")
    return {"success": True, "data": snapshot}


@router.post("/evolution/apply/{family}")
async def bpe_evolution_apply(
    family: str,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Request deployment of the family's best evolved genome.

    Deliberately uses the SAME gates as the automatic path (kill-switch +
    evidence thresholds, unless explicitly forced via env/UI override) —
    this endpoint never bypasses them.
    """
    applied = evolution.apply_best(family)
    if applied is None:
        snap = evolution.get_population().snapshot().get(family, [])
        return {
            "success": True,
            "applied": False,
            "reason": (
                "no evaluated genomes for this family yet"
                if not snap
                else "held: evidence thresholds not met or application disabled "
                     "(see ATOM_BPE_EVOLUTION / ATOM_BPE_AUTOMATION)"
            ),
        }
    return {"success": True, "applied": True, "data": {"bounds": applied}}
