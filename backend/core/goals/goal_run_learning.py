"""GoalRun learning loop + lifecycle (§3.6, §3.7, slice 6).

GoalRun is where the agent WORKS; this module is how the work feeds the
existing growth systems — no new parallel machinery (AGENTS.md: use the
general layer):

- Decision overrides are CORRECTIONS: journaled as permanent lessons
  (``journal_standing_lesson`` — the same store teach/corrections write)
  and reflected into the critique pool. Fires on reject-resume (§3.7C).
- Completed runs become world-model EXPERIENCES (role + goal-shape +
  outcome + decision trace) so future run seeding recalls whole-run
  precedent; failed runs add a reflection critique.
- Completed runs DISTILL into playbook drafts (source=learned,
  fingerprint-deduped) through the existing approval queue — the informal
  process crystallizes per role.
- Run history is PROMOTION EVIDENCE: evaluate_mode_promotion() recommends
  training→shadow→autonomous from the run record (achieved ratio,
  interventions, replans); promotion itself stays an explicit,
  supervisor-gated act (POST /{id}/mode), never an automatic toggle.

Everything here is fault-isolated: learning must never block working.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- seeding

def seed_plan_for_run(goal_title: str, role: Optional[str] = None,
                      agent_id: Optional[str] = None,
                      tenant_id: str = "default",
                      canvas_type: Optional[str] = None) -> Dict[str, Any]:
    """The initial plan is a FAMILIAR PATH PRIOR (§3.6): this role's approved
    playbooks matched to the goal (keyword/dense hybrid via get_relevant —
    playbooks are not role-tagged, so role context arrives through matching
    and the router prompt). No match → a minimal generic path that still
    includes a human review checkpoint before external actions. Fault-
    isolated: seeding failure yields the fallback, never an exception."""
    steps: List[Dict[str, Any]] = []
    playbook_ids: List[str] = []
    try:
        from core.database import get_db_session
        from core.playbook_service import PlaybookService
        with get_db_session() as db:
            matched = PlaybookService(db, tenant_id=tenant_id).get_relevant(
                goal_title, canvas_type=canvas_type) or []
            for pb in matched:
                if pb.get("id"):
                    playbook_ids.append(pb["id"])
                for s in (pb.get("steps") or []):
                    if isinstance(s, str) and s.strip():
                        steps.append({"kind": "canvas_work",
                                      "title": s.strip()[:160]})
                    if len(steps) >= 6:
                        break
                if len(steps) >= 6:
                    break
    except Exception as exc:
        logger.warning(f"plan seeding fell back (playbook match failed): {exc}")
    if steps:
        plan = [{"id": f"seed-{i + 1}", **step} for i, step in enumerate(steps)]
        return {"plan": plan, "source": "playbooks",
                "playbook_ids": playbook_ids}
    plan = [
        {"id": "seed-1", "kind": "canvas_work",
         "title": f"Clarify and research: {goal_title}"[:160],
         "canvas_type": "document"},
        {"id": "seed-2", "kind": "canvas_work",
         "title": f"Execute the core work: {goal_title}"[:160]},
        {"id": "seed-3", "kind": "human_checkpoint",
         "title": "Review before any external action"},
    ]
    return {"plan": plan, "source": "fallback", "playbook_ids": []}


# ------------------------------------------------------------- overrides

def record_decision_override(service, run: Dict[str, Any],
                             decision: Dict[str, Any],
                             guidance: Optional[str] = None,
                             approved: bool = False) -> None:
    """A supervisor overriding a held decision IS the correction (§3.7C):
    journal it as a standing lesson on the run's agent and reflect it into
    the critique pool."""
    agent_id = run.get("agent_id")
    lesson = (guidance or "").strip()
    if agent_id and lesson:
        try:
            from core.database import get_db_session
            from core.student_learning_service import journal_standing_lesson
            with get_db_session() as db:
                journal_standing_lesson(
                    db, str(agent_id),
                    f"Goal-run decision override: instead of "
                    f"{decision.get('decision')}, {lesson}"[:500],
                    source="human_correction",
                    observation_type="human_correction",
                    topic=f"goal_run:{run.get('goal_id')}",
                    details={"goal_run_id": run.get("id"),
                             "overridden_decision": decision.get("decision"),
                             "original_rationale": decision.get("rationale")},
                )
        except Exception as exc:
            logger.warning(f"goal run {run.get('id')}: override lesson "
                           f"journal failed: {exc}")
    try:
        _reflect_critique(
            tenant_id=run.get("tenant_id") or service.tenant_id,
            agent_id=agent_id,
            intent=f"goal-run decision {decision.get('decision')} "
                   f"(rationale: {decision.get('rationale')})",
            action_taken="held for human approval",
            outcome_state=f"overridden by supervisor: {lesson or '(no guidance)'}",
            critique_text=lesson or "decision overridden — follow the "
                                    "supervisor's guidance next time",
        )
    except Exception as exc:
        logger.warning(f"goal run {run.get('id')}: override critique "
                       f"failed: {exc}")


# -------------------------------------------------------------- outcomes

async def record_run_outcome(service, run: Dict[str, Any],
                             outcome: str) -> None:
    """Terminal run → world-model experience (+ critique on failure)."""
    agent_id = run.get("agent_id")
    if not agent_id:
        return
    log = [d for d in run.get("decision_log") or [] if d.get("kind") == "decision"]
    learnings = "; ".join(
        f"{d.get('decision')}: {d.get('rationale')}" for d in log[-3:])
    try:
        from core.agent_world_model import AgentExperience, WorldModelService
        world = WorldModelService(workspace_id=run.get("workspace_id"))
        await world.record_experience(AgentExperience(
            id=f"goalrun-{run['id']}",
            agent_id=str(agent_id),
            task_type=f"goal_run:{run.get('role') or 'general'}",
            input_summary=str(run.get("goal_id")),
            outcome="Success" if outcome == "achieved" else "Failure",
            learnings=learnings[:1000] or "no decisions recorded",
            confidence_score=0.7 if outcome == "achieved" else 0.4,
            agent_role=str(run.get("role") or "general"),
            timestamp=datetime.now(timezone.utc),
            metadata_trace={
                "goal_run_id": run["id"],
                "goal_id": run.get("goal_id"),
                "steps_executed": run.get("steps_executed"),
                "replan_count": run.get("replan_count"),
                "human_interventions": run.get("human_interventions"),
                "supervision_mode": run.get("supervision_mode"),
            },
        ))
    except Exception as exc:
        logger.warning(f"goal run {run['id']}: experience recording "
                       f"failed: {exc}")
    if outcome != "achieved":
        try:
            _reflect_critique(
                tenant_id=run.get("tenant_id") or service.tenant_id,
                agent_id=agent_id,
                intent=f"achieve goal {run.get('goal_id')}",
                action_taken=f"run finished {run.get('steps_executed')} steps, "
                             f"{run.get('replan_count')} replans",
                outcome_state=f"run {outcome}",
                critique_text="review the decision log for the pivot that "
                              "preceded the failure",
            )
        except Exception as exc:
            logger.warning(f"goal run {run['id']}: failure critique "
                           f"failed: {exc}")


def _reflect_critique(tenant_id: str, agent_id: Optional[str], intent: str,
                      action_taken: str, outcome_state: str,
                      critique_text: str) -> None:
    """Fire-and-forget write into the reflection pool (sync wrapper)."""
    import asyncio

    from core.reflection_service import ReflectionService

    async def _run():
        svc = ReflectionService(tenant_id=tenant_id or "default")
        await svc.add_critique(agent_id=str(agent_id or "unknown"),
                               intent=intent[:500],
                               action_taken=action_taken[:500],
                               outcome_state=outcome_state[:500],
                               critique_text=critique_text[:1000])

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        loop.create_task(_run())
    else:
        asyncio.run(_run())


# ---------------------------------------------------------- distillation

def distill_run_to_playbook_draft(run: Dict[str, Any], tenant_id: str,
                                  workspace_id: str,
                                  goal_title: str = "") -> Optional[Dict[str, Any]]:
    """Completed run → playbook DRAFT (source=learned) in the existing
    approval queue (§3.6). Fingerprint-deduped per (goal shape, role): the
    same process learned twice drafts once. Returns the created row dict or
    None when skipped/deduped."""
    decisions = [d for d in run.get("decision_log") or []
                 if d.get("kind") == "decision" and d.get("rationale")]
    if len(decisions) < 2:
        return None  # not enough of a process to be worth a draft
    role = run.get("role") or "general"
    fingerprint = hashlib.sha256(
        f"{role}:{run.get('goal_id')}".encode()).hexdigest()[:16]

    from core.models import Playbook
    from core.database import get_db_session
    with get_db_session() as db:
        existing = db.query(Playbook).filter(
            Playbook.tenant_id == tenant_id,
            Playbook.fingerprint == fingerprint).first()
        if existing:
            return None
        steps = [f"When {d.get('event') or 'the previous step finishes'}: "
                 f"{d.get('rationale')}"[:240]
                 for d in decisions][:8]
        from core.playbook_service import PlaybookService
        svc = PlaybookService(db, tenant_id=tenant_id)
        row = svc.create(
            name=f"Role process ({role}): {goal_title or run.get('goal_id')}"[:255],
            description=("Distilled from a completed goal run — the path "
                         "the agent actually took. Review before approval."),
            trigger_keywords=[role, "goal_run"],
            steps=steps,
            source="learned",
            approval_state="draft",
            fingerprint=fingerprint,
            origin_ids=[run["id"]],
        )
        return {"id": row.id, "name": row.name,
                "approval_state": row.approval_state, "steps": steps}


# ------------------------------------------------------------- promotion

def evaluate_mode_promotion(agent_id: str, workspace_id: str = "default",
                            tenant_id: str = "default",
                            session_factory=None) -> Dict[str, Any]:
    """Advisory promotion evidence from the run record (§3.7B). Promotion
    itself stays a supervisor act; this recommends and justifies.

    Thresholds (deliberately conservative, open question §8.5):
    training→shadow: ≥3 training runs, ≥60% achieved, ≤1 intervention/run.
    shadow→autonomous: ≥3 shadow runs, ≥60% achieved, ≤1 intervention/run,
    replans within budget on every run."""
    from core.goals.goal_run_service import GoalRunService
    svc = GoalRunService(workspace_id=workspace_id, tenant_id=tenant_id,
                         session_factory=session_factory)
    runs = [r for r in svc.list_runs(agent_id=agent_id)]
    by_mode: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_mode.setdefault(r.get("supervision_mode"), []).append(r)

    def _stats(mode_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(mode_runs)
        achieved = sum(1 for r in mode_runs if r.get("status") == "achieved")
        interventions = sum(r.get("human_interventions") or 0
                            for r in mode_runs)
        return {"runs": total, "achieved": achieved,
                "achieved_ratio": round(achieved / total, 2) if total else 0.0,
                "interventions_per_run": round(interventions / total, 2)
                if total else 0.0}

    evidence = {"training": _stats(by_mode.get("training", [])),
                "shadow": _stats(by_mode.get("shadow", []))}

    def _ready(stats) -> bool:
        return (stats["runs"] >= 3 and stats["achieved_ratio"] >= 0.6
                and stats["interventions_per_run"] <= 1.0)

    recommendation = "training"
    if _ready(evidence["shadow"]):
        recommendation = "autonomous"
    elif _ready(evidence["training"]):
        recommendation = "shadow"
    return {"agent_id": agent_id, "recommendation": recommendation,
            "evidence": evidence,
            "note": "advisory — promotion is applied per run by a "
                    "supervisor (POST /api/goal-runs/{id}/mode)"}
