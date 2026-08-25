"""
Student agent learning.

Two complementary pathways, by design:
- TEACHER: the Atom meta agent teaches a student directly (a lesson, a
  correction, a worked example). This is the fast path — it only speeds
  up learning; it is not the only pathway.
- OBSERVATION: a student learns on its own by watching the workspace —
  human HITL approvals, workflow executions, and peer agent runs relevant
  to its capabilities. Slower, but always available.

Both pathways append to the student's learning log and nudge its
confidence upward in small, capped steps. Neither pathway can promote a
student on its own: the nudge ceiling sits below the promotion threshold
so maturity transitions still go through the training/graduation system
(StudentTrainingService.complete_training_session, graduation exams).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)

# Promotion to INTERN happens at confidence >= 0.5 via the training system.
# Learning nudges stop here so no amount of teaching or observation can
# graduate a student by itself.
_CONFIDENCE_CEILING = 0.45

_TEACHER_BOOST = 0.05   # a curated lesson from the meta agent
_OBSERVATION_BOOST = 0.01  # witnessing one relevant event

MAX_LOG_ENTRIES = 200


class StudentLearningService:
    """Records learning for STUDENT agents from teachers and observation."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Teacher pathway
    # ------------------------------------------------------------------

    def learn_from_teacher(
        self,
        student_agent_id: str,
        teacher_agent_id: str,
        lesson: str,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a teacher-delivered lesson (fast path)."""
        student = self._get_student(student_agent_id)
        if student is None:
            return {"status": "error", "reason": "student_not_found"}

        entry = {
            "source": "teacher",
            "teacher_agent_id": teacher_agent_id,
            "topic": topic or "general",
            "lesson": lesson[:2000],
            "learned_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._apply_learning(student, entry, boost=_TEACHER_BOOST)

    # ------------------------------------------------------------------
    # Observation pathway
    # ------------------------------------------------------------------

    def learn_from_observation(
        self,
        student_agent_id: str,
        observation_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record something the student learned by watching the workspace.

        observation_type: e.g. "hitl_approval", "workflow_execution",
        "peer_agent_run", "human_correction".
        """
        student = self._get_student(student_agent_id)
        if student is None:
            return {"status": "error", "reason": "student_not_found"}

        entry = {
            "source": "observation",
            "observation_type": observation_type,
            "summary": summary[:1000],
            "details": details or {},
            "learned_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._apply_learning(student, entry, boost=_OBSERVATION_BOOST)

    def observe_workspace(
        self,
        student_agent_id: str,
        workspace_id: str = "default",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Mine recent workspace events relevant to the student and learn
        from them in one batch. Returns how many observations were absorbed.

        Relevance: HITL approvals whose action_type overlaps the student's
        registered capabilities, and recent workflow runs in the workspace.
        """
        student = self._get_student(student_agent_id)
        if student is None:
            return {"status": "error", "reason": "student_not_found"}

        capabilities = set(student.capabilities or [])
        absorbed = 0

        try:
            from core.models import HITLAction, WorkflowExecutionLog

            approvals = (
                self.db.query(HITLAction)
                .filter(
                    HITLAction.workspace_id == workspace_id,
                    HITLAction.status == "approved",
                )
                .order_by(HITLAction.created_at.desc())
                .limit(limit)
                .all()
            )
            for approval in approvals:
                action = approval.action_type or ""
                relevant = bool(capabilities) and any(
                    action in cap or cap in action for cap in capabilities
                )
                self.learn_from_observation(
                    student_agent_id,
                    "hitl_approval",
                    f"A human approved '{action}'"
                    + (" matching the student's capability" if relevant else " in the workspace")
                    + (f": {approval.reason}" if approval.reason else ""),
                    details={"action_type": action, "relevant": relevant},
                )
                absorbed += 1

            runs = (
                self.db.query(WorkflowExecutionLog)
                .order_by(WorkflowExecutionLog.start_time.desc())
                .limit(limit)
                .all()
            )
            for run in runs:
                if run.status != "completed":
                    continue
                self.learn_from_observation(
                    student_agent_id,
                    "workflow_execution",
                    f"Observed workflow {run.workflow_id} step '{run.step_id}' complete successfully",
                    details={"workflow_id": run.workflow_id, "step_id": run.step_id},
                )
                absorbed += 1
        except Exception as e:
            logger.warning(f"Workspace observation mining partially failed: {e}")

        return {"status": "ok", "observations_absorbed": absorbed}

    # ------------------------------------------------------------------
    # Automated observation triggers
    # ------------------------------------------------------------------

    @staticmethod
    def relevant_to(student: AgentRegistry, action_type: str) -> bool:
        """Whether an action type overlaps the student's capabilities."""
        capabilities = set(student.capabilities or [])
        if not capabilities:
            return True  # generalist students observe everything
        action = (action_type or "").lower()
        return any(action in cap.lower() or cap.lower() in action for cap in capabilities)

    def dispatch_observation_event(
        self,
        workspace_id: str,
        observation_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
        action_type: Optional[str] = None,
    ) -> int:
        """Fan a single workspace event out to every STUDENT agent that
        should observe it (relevance-filtered by capability overlap).

        Returns how many students learned. Synchronous and cheap — designed
        to be called from event hooks (HITL resolution, workflow completion).
        """
        students = self.db.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.STUDENT.value,
            AgentRegistry.workspace_id == workspace_id,
        ).all()

        count = 0
        for student in students:
            if action_type and not self.relevant_to(student, action_type):
                continue
            result = self.learn_from_observation(
                student.id, observation_type, summary, details=details
            )
            if result.get("status") == "ok":
                count += 1
        return count

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_student(self, student_agent_id: str) -> Optional[AgentRegistry]:
        student = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == student_agent_id
        ).first()
        if student is None:
            logger.warning(f"Learning target agent {student_agent_id} not found")
            return None
        if student.status != AgentStatus.STUDENT.value:
            # Non-students have graduated beyond spoon-feeding; learning
            # continues through the normal execution/confidence loop.
            logger.info(f"Learning skipped for {student_agent_id}: status {student.status} (not STUDENT)")
            return None
        return student

    def _apply_learning(self, student: AgentRegistry, entry: Dict[str, Any], boost: float) -> Dict[str, Any]:
        from sqlalchemy.orm.attributes import flag_modified

        config = student.configuration if isinstance(student.configuration, dict) else {}
        learning = config.setdefault("learning", {})
        log: List[Dict[str, Any]] = learning.setdefault("log", [])
        log.append(entry)
        if len(log) > MAX_LOG_ENTRIES:
            del log[:-MAX_LOG_ENTRIES]
        learning["last_learned_at"] = entry["learned_at"]
        learning["pathways_used"] = sorted({e["source"] for e in log})
        config["learning"] = learning
        student.configuration = config
        flag_modified(student, "configuration")

        old_confidence = float(student.confidence_score or 0.0)
        # Cap below the promotion threshold: learning earns readiness,
        # the training system confers maturity.
        student.confidence_score = min(_CONFIDENCE_CEILING, old_confidence + boost)
        actual_boost = student.confidence_score - old_confidence

        self.db.commit()

        return {
            "status": "ok",
            "source": entry["source"],
            "confidence": student.confidence_score,
            "confidence_boost": round(actual_boost, 4),
            "at_learning_ceiling": student.confidence_score >= _CONFIDENCE_CEILING,
            "note": (
                "Learning ceiling reached — ready for a training session / "
                "graduation exam to advance maturity"
            ) if student.confidence_score >= _CONFIDENCE_CEILING else None,
        }


async def auto_observe(
    workspace_id: str,
    observation_type: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    action_type: Optional[str] = None,
) -> None:
    """Fire-and-forget event hook: opens its own DB session and feeds the
    event to all observing STUDENT agents in the workspace.

    Use from event paths (HITL resolution, workflow completion) via
    ``asyncio.create_task(auto_observe(...))`` — best-effort, never raises
    into the caller's flow.
    """
    try:
        from core.database import SessionLocal

        session = SessionLocal()
        try:
            count = StudentLearningService(session).dispatch_observation_event(
                workspace_id=workspace_id,
                observation_type=observation_type,
                summary=summary,
                details=details,
                action_type=action_type,
            )
            if count:
                logger.info(f"Observation event '{observation_type}' learned by {count} student(s) in {workspace_id}")
        finally:
            session.close()
    except Exception as e:
        logger.debug(f"Auto-observation skipped (non-fatal): {e}")
