"""Self-directed pathway progress — shared read side + milestone nudges.

The self-directed STUDENT→INTERN pathway (StudentTrainingService.
_evaluate_intern_readiness) is evidence-based: outcome-tracked AgentEpisode
rows plus completed training sessions. Until recently that evidence was
invisible to the human who is supposed to validate it — the Training tab
showed "Readiness unavailable" and nobody was nudged to review the work.

This module is the single source of truth for:

- ``snapshot()``      — what the UI renders (progress vs evidence floors,
                        readiness verdict, recent episode list, guidance
                        steps). Consumed by GET /api/maturity/training/
                        self-directed and by the milestone notifier.
- ``maybe_notify_milestone()`` — fault-isolated in-app notification when the
                        agent's verified-episode count first crosses 25/50/
                        75/100% of the required floor. Deduped via a marker
                        in the agent's configuration.learning dict so a
                        notification fires ONCE per milestone, ever.

Milestones hang off the AgentEpisode ledger write (episode segmentation),
which is the same evidence the graduation gate counts — manual canvas work
and recorded runs both land there.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

# Milestone fractions of the required-episode floor. 1.0 additionally
# evaluates full readiness (ratio + sessions) before claiming "ready".
_MILESTONES = (0.25, 0.5, 0.75, 1.0)

_MIN_SUCCESS_RATIO = 0.7  # mirrors ATOM_PROMOTION_MIN_SUCCESS_RATIO default


def _required_episodes() -> int:
    """Evidence floor for the self-directed pathway (same knob as the gate)."""
    try:
        return int(os.getenv("ATOM_PROMOTION_MIN_EPISODES", "10"))
    except (TypeError, ValueError):
        return 10


def _evidence_totals(db, agent_id: str) -> Dict[str, Any]:
    """All-time outcome-ledger totals for the agent (any tenant scope — the
    ledger rows may predate tenancy or carry 'default')."""
    from core.models import AgentEpisode
    from sqlalchemy import or_

    rows = (
        db.query(AgentEpisode)
        .filter(
            AgentEpisode.agent_id == agent_id,
            or_(
                AgentEpisode.outcome == "success",
                AgentEpisode.outcome == "failure",
                AgentEpisode.outcome == "partial",
            ),
        )
        .count()
    )
    successes = (
        db.query(AgentEpisode)
        .filter(AgentEpisode.agent_id == agent_id, AgentEpisode.outcome == "success")
        .count()
    )
    ratio = (successes / rows) if rows else 0.0
    return {"episodes": rows, "successes": successes, "success_ratio": round(ratio, 4)}


def _recent_episodes(db, agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Newest ledger rows the human is validating — the work itself."""
    from core.models import AgentEpisode

    rows = (
        db.query(AgentEpisode)
        .filter(AgentEpisode.agent_id == agent_id)
        .order_by(AgentEpisode.started_at.desc())
        .limit(limit)
        .all()
    )
    recent: List[Dict[str, Any]] = []
    for r in rows:
        recent.append(
            {
                "id": r.id,
                "task": (r.task_description or "Untitled work")[:200],
                "outcome": r.outcome or "unknown",
                "success": bool(r.success),
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "human_interventions": r.human_intervention_count or 0,
                "maturity_at_time": r.maturity_at_time,
                "canvas_ids": r.canvas_ids or [],
            }
        )
    return recent


def _completed_sessions(db, agent_id: str) -> int:
    from core.models import TrainingSession

    return (
        db.query(TrainingSession)
        .filter(TrainingSession.agent_id == agent_id, TrainingSession.status == "completed")
        .count()
    )


def snapshot(db, agent) -> Dict[str, Any]:
    """Everything the validation UI needs for one STUDENT agent.

    Never raises for data-shaped reasons: readiness evaluation is the
    multi-pathway gate and may be expensive, so it is wrapped — a failure
    degrades to pathway "unknown" rather than 500-ing the panel.
    """
    evidence = _evidence_totals(db, agent.id)
    required = _required_episodes()
    sessions = _completed_sessions(db, agent.id)

    pathway: Dict[str, Any] = {}
    try:
        from core.student_training_service import StudentTrainingService

        pathway = StudentTrainingService(db)._evaluate_intern_readiness(agent) or {}
    except Exception as e:  # pragma: no cover — degrade, don't break the panel
        logger.debug("self-directed readiness evaluation failed for %s: %s", agent.id, e)

    episode_progress = min(1.0, evidence["episodes"] / required) if required else 1.0
    ratio_ok = evidence["success_ratio"] >= _MIN_SUCCESS_RATIO
    confidence_ok = float(agent.confidence_score or 0.0) >= 0.5
    evidence_ready = evidence["episodes"] >= required and ratio_ok
    # "Ready for review" = the episode-evidence floor the supervisor's
    # manual promotion weighs (graduation readiness). It is deliberately
    # broader than the strict multi-pathway auto-promotion verdict (which
    # additionally demands completed training sessions) — the decision is
    # still the supervisor's; this only says the evidence is worth reviewing.
    ready_for_review = bool(evidence_ready and confidence_ok)

    guidance: List[Dict[str, Any]] = [
        {
            "label": f"Real work recorded: {evidence['episodes']}/{required} episodes",
            "done": evidence["episodes"] >= required,
            "detail": (
                "Every piece of real work the agent completes is outcome-tracked "
                "here — successes and failures alike."
            ),
        },
        {
            "label": f"Success ratio: {round(evidence['success_ratio'] * 100)}% (needs ≥ {round(_MIN_SUCCESS_RATIO * 100)}%)",
            "done": ratio_ok,
            "detail": "Derived from execution results, not self-reported — failed tool calls and errors count against it.",
        },
        {
            "label": f"Confidence ≥ 50%: {round(float(agent.confidence_score or 0.0) * 100)}%",
            "done": confidence_ok,
            "detail": "Grows from teaching, feedback and completed work; teaching alone never promotes.",
        },
    ]
    auto_route_available = sessions > 0 or pathway.get("pathway") == "mentor_taught"
    guidance.append(
        {
            "label": f"Completed training sessions: {sessions}/3",
            "done": sessions >= 3,
            "detail": (
                "Self-directed graduation needs 3 completed supervised sessions. "
                "They start when an automated task is blocked and you approve the "
                "training proposal — or promote manually once the evidence is ready."
                if not auto_route_available
                else "Sessions you completed appear here; keep going until 3."
            ),
        }
    )
    if pathway.get("ready"):
        guidance.append(
            {
                "label": "Ready — review the work below, then Promote to INTERN",
                "done": True,
                "detail": "Promotion is your judgment call as supervisor; the episodes below are the evidence.",
            }
        )
    elif ready_for_review:
        guidance.append(
            {
                "label": "Evidence floor met — review the work below, then decide on promotion",
                "done": True,
                "detail": (
                    "Auto-promotion also needs 3 completed training sessions, but as "
                    "supervisor you can promote on this evidence directly."
                ),
            }
        )

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "category": agent.category,
        "tier": agent.status,
        "confidence": float(agent.confidence_score or 0.0),
        "evidence": {**evidence, "required_episodes": required},
        "episode_progress": round(episode_progress, 4),
        "success_ratio_ok": ratio_ok,
        "confidence_ok": confidence_ok,
        "evidence_floor_met": evidence_ready,
        "ready_for_review": ready_for_review,
        "completed_sessions": sessions,
        "readiness": {
            "ready": bool(pathway.get("ready")),
            "pathway": pathway.get("pathway"),
            "reason": pathway.get("reason"),
            "required_training_sessions": pathway.get("required_training_sessions"),
            "required_episodes": pathway.get("required_episodes"),
            "success_ratio": pathway.get("success_ratio"),
        },
        "recent_episodes": _recent_episodes(db, agent.id),
        "guidance": guidance,
    }


def student_agents(db, tenant_id: Optional[str] = None, agent_id: Optional[str] = None):
    """STUDENT-tier registry rows, optionally narrowed to one agent.

    Matches on the string tier value; NULL/empty tenants are included —
    legacy adopted agents (see the readiness fix in episode_service) must
    not vanish from the validation queue.
    """
    from core.models import AgentRegistry, AgentStatus

    q = db.query(AgentRegistry).filter(AgentRegistry.status == AgentStatus.STUDENT.value)
    if agent_id:
        q = q.filter(AgentRegistry.id == agent_id)
    if tenant_id:
        from sqlalchemy import or_

        # NULL/empty tenants are legacy adopted rows — SQL NOT() is NULL for
        # a NULL column, so an empty-tenant match must be spelled out.
        q = q.filter(
            or_(
                AgentRegistry.tenant_id == tenant_id,
                AgentRegistry.tenant_id.is_(None),
                AgentRegistry.tenant_id == "",
            )
        )
    return q.order_by(AgentRegistry.confidence_score.desc()).all()


def maybe_notify_milestone(db, agent_id: str) -> Optional[Dict[str, Any]]:
    """Fire the once-per-milestone nudge after a new ledger row lands.

    Called from episode segmentation (post-commit). Never raises: a
    notification problem must not fail episode archival. Returns the sent
    payload for logging, or None.
    """
    try:
        from core.models import AgentRegistry, AgentStatus

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent or agent.status != AgentStatus.STUDENT.value:
            return None

        evidence = _evidence_totals(db, agent_id)
        required = _required_episodes()
        if not required:
            return None
        fraction = evidence["episodes"] / required
        crossed = [m for m in _MILESTONES if fraction >= m]
        if not crossed:
            return None

        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        learning = config.get("learning") if isinstance(config.get("learning"), dict) else {}
        notified: List[float] = list(learning.get("milestones_notified") or [])
        pending = [m for m in crossed if m not in notified]
        if not pending:
            return None

        # Highest newly-crossed milestone drives the copy; all are marked so
        # a burst of episodes doesn't spam four notifications at once.
        top = max(pending)
        pct = round(evidence["success_ratio"] * 100)
        if top >= 1.0 and evidence["episodes"] >= required:
            title = f"{agent.name} hit its self-directed evidence floor"
            message = (
                f"{evidence['episodes']} verified episodes at {pct}% success — "
                "ready for your graduation review. Validate the work, then decide "
                "on promotion."
            )
        else:
            title = f"{agent.name} is learning on the job"
            message = (
                f"{evidence['episodes']}/{required} verified episodes "
                f"({pct}% success) toward self-directed graduation. "
                "Review the work so far."
            )

        from core.notification_service import NotificationService

        user_id = getattr(agent, "user_id", None)
        if not user_id:
            return None  # no owner to nudge; queue endpoint still surfaces progress
        payload = {
            "title": title,
            "message": message,
            "workspace_id": getattr(agent, "workspace_id", None) or "default",
            "tenant_id": getattr(agent, "tenant_id", None) or "default",
            "action_url": "/approvals",
            "action_label": "Review evidence",
            "agent_id": agent_id,
        }
        # send_notification is async in name only (its persist path is fully
        # synchronous), so call the sync body directly — this hook runs from
        # sync segmentation code where run_until_complete on a running loop
        # (pytest-asyncio, async endpoints) would raise. Same try/except
        # semantics as the wrapper: never raises.
        svc = NotificationService(db)
        try:
            result = svc._persist_and_maybe_email(
                user_id=str(user_id),
                notification_type="agent_training_milestone",
                data=payload,
            )
        except Exception as exc:
            logger.error("milestone notification failed for %s: %s", agent_id, exc)
            return None  # leave markers unset so the nudge retries next episode
        if not result.get("success"):
            return None

        notified.extend(pending)
        learning["milestones_notified"] = notified
        config["learning"] = learning
        agent.configuration = config
        # Reassignment already dirties a mapped instance; flag_modified is
        # belt-and-braces for JSONColumn mutation tracking (and a no-op
        # failure for non-mapped test doubles).
        try:
            flag_modified(agent, "configuration")
        except Exception:
            pass
        db.commit()
        logger.info(
            "self-directed milestone %s notified for %s (episodes=%s, sent=%s)",
            top, agent_id, evidence["episodes"], result.get("success"),
        )
        return payload
    except Exception as e:  # pragma: no cover — best-effort by contract
        logger.debug("milestone notification skipped for %s: %s", agent_id, e)
        try:
            db.rollback()
        except Exception:
            pass
        return None
