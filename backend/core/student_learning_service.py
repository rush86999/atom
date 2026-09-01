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

Work-time application: the log is not write-only. get_agent_lessons +
format_lessons_block put permanent lessons (teacher lessons, observed
human corrections) back in front of the agent in every chat turn, canvas
edit plan, and task execution — the point of teaching.
"""

import logging
import re
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

# ---------------------------------------------------------------------------
# Work-time lesson application
# ---------------------------------------------------------------------------
# Lessons are PERMANENT training, not just confidence signals: a lesson taught
# once via /teach (or a human correction observed on the job) must shape every
# later chat turn, canvas edit, and task execution — including after the agent
# graduates beyond STUDENT. Storage alone changes a score; these accessors are
# what put the lesson in front of the model at work time.
WORK_TIME_LESSON_LIMIT = 5
_LESSON_TEXT_CHARS = 320
_LESSON_BLOCK_CHARS = 1600

# Log entries that carry standing guidance (vs. one-time event observations).
_PERMANENT_OBSERVATIONS = {"human_correction", "user_style"}


def _is_permanent_lesson(entry: Dict[str, Any]) -> bool:
    """Teacher lessons and observed human corrections are standing guidance;
    plain event observations (an approval happened, a workflow ran) are not."""
    if not isinstance(entry, dict):
        return False
    if entry.get("source") == "teacher":
        return True
    return (
        entry.get("source") == "observation"
        and entry.get("observation_type") in _PERMANENT_OBSERVATIONS
    )


def _lesson_text(entry: Dict[str, Any]) -> str:
    return str(entry.get("lesson") or entry.get("summary") or "").strip()


def get_agent_lessons(
    db: Session,
    agent_id: str,
    query: Optional[str] = None,
    limit: int = WORK_TIME_LESSON_LIMIT,
) -> List[Dict[str, Any]]:
    """The agent's permanent lessons, newest first, for injection at work time.

    Reads the durable learning log from AgentRegistry.configuration — the
    same store learn_from_teacher / learn_from_observation write. Works for
    ANY agent status: lessons survive graduation (that is what makes a
    trained agent stay trained). When ``query`` is given, lessons are
    keyword-scored against it and relevance breaks recency ties, so the
    lessons that matter for THIS task fit in the limit. Fault-isolated:
    returns [] on any failure — never blocks the working turn.
    """
    try:
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()
    except Exception as e:
        logger.debug(f"lesson lookup failed for {agent_id}: {e}")
        return []
    if agent is None:
        return []
    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning")
    log = learning.get("log") if isinstance(learning, dict) else None
    if not isinstance(log, list):
        return []

    lessons = [e for e in log if _is_permanent_lesson(e)]
    lessons.reverse()  # newest first (the log is append-ordered)

    if query:
        q_tokens = {
            t for t in re.findall(r"[a-z0-9]{3,}", str(query).lower())
            if t not in {"the", "and", "for", "with", "this", "that", "please", "can", "you", "your"}
        }
        def _score(entry: Dict[str, Any]) -> int:
            haystack = " ".join((
                str(entry.get("topic") or ""),
                _lesson_text(entry),
            )).lower()
            return sum(1 for t in q_tokens if t in haystack)
        # Relevance first, recency as the tie-break (reverse() above made
        # the list newest-first, and sort is stable, so equal scores keep it).
        lessons.sort(key=_score, reverse=True)

    return lessons[:max(0, limit)]


def learn_user_style(
    db: Session,
    agent_id: str,
    user_id: str,
    signature_html: str,
    style_notes: str = "",
) -> Dict[str, Any]:
    """Record/refresh a user's email formatting style as a PERMANENT lesson
    for the agent (work-time injected alongside teacher lessons).

    Used when an agent sends email on a user's behalf: the agent should
    draft in THAT user's format — their signature, fonts, and closing
    style. One entry per (agent, user): refreshed in place, never
    accumulated, so style edits propagate and the log stays clean.
    """
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id
    ).first()
    if agent is None:
        return {"status": "error", "reason": "agent_not_found"}

    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.setdefault("learning", {})
    log = learning.setdefault("log", [])

    entry = {
        "source": "observation",
        "observation_type": "user_style",
        "topic": "email_style",
        "user_id": user_id,
        "summary": (
            "Email style for this user: draft in their format — use their "
            "styled signature block verbatim at the end of every email, "
            "match their font and closing style."
            + (f" {style_notes}" if style_notes else "")
        ),
        "details": {"user_id": user_id, "signature_html": (signature_html or "")[:2000]},
        "learned_at": datetime.now(timezone.utc).isoformat(),
    }
    log[:] = [
        e for e in log
        if not (isinstance(e, dict) and e.get("observation_type") == "user_style"
                and (e.get("details") or {}).get("user_id") == user_id)
    ]
    log.append(entry)
    if len(log) > MAX_LOG_ENTRIES:
        del log[:-MAX_LOG_ENTRIES]
    learning["last_learned_at"] = entry["learned_at"]
    learning["pathways_used"] = sorted({e.get("source", "observation") for e in log})
    config["learning"] = learning
    agent.configuration = config
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(agent, "configuration")
    db.commit()
    return {"status": "ok", "topic": "email_style"}


def format_lessons_block(lessons: List[Dict[str, Any]]) -> str:
    """Render lessons as a bounded prompt block asserting their permanence.

    The framing matters: general memory disclaimers ("may be stale") must not
    weaken standing instructions, so this block says explicitly that these
    are durable teacher guidance. Empty string when there are no lessons."""
    if not lessons:
        return ""
    lines: List[str] = []
    used = 0
    for i, entry in enumerate(lessons, 1):
        entry = entry or {}
        topic = str(entry.get("topic") or "general")
        text = " ".join(_lesson_text(entry).split())
        if not text:
            continue
        if len(text) > _LESSON_TEXT_CHARS:
            text = text[:_LESSON_TEXT_CHARS] + "…"
        line = f"{i}. [{topic}] {text}"
        if used + len(line) + 1 > _LESSON_BLOCK_CHARS:
            break
        lines.append(line)
        used += len(line) + 1
    if not lines:
        return ""
    header = (
        "TRAINING LESSONS — PERMANENT INSTRUCTIONS you were taught by your "
        "supervisor/mentor. This is standing guidance for ALL your work (it "
        "does not expire): apply it to the current task, match the preferences "
        "it describes, and never contradict it unless the user explicitly "
        "overrides it in this conversation:\n"
    )
    return header + "\n".join(lines)


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
        result = self._apply_learning(student, entry, boost=_TEACHER_BOOST)

        # Pedagogy circuit: a taught lesson is a POSITIVE exposure for its
        # topic — it builds mastery so the pedagogy scaffolding withdraws
        # (that is the point of teaching). Best-effort: the journal +
        # confidence above are the contract; mastery tracking must never
        # break lesson intake.
        if result.get("status") == "ok":
            try:
                from core.agent_pedagogy import PedagogicalFramework

                PedagogicalFramework(self.db).record_mastery_exposure(
                    student,
                    entry["topic"],
                    positive=True,
                    note=entry["lesson"][:200],
                )
            except Exception as e:
                logger.debug(f"mastery exposure skipped: {e}")

        return result

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
        """Whether an action type is relevant for this student to observe.

        Students are role-based by design: capabilities first; if none are
        registered, the student's role (template specialty keywords) filters;
        a roleless generic student observes everything.
        """
        capabilities = set(student.capabilities or [])
        action = (action_type or "").lower()
        if capabilities:
            return any(action in cap.lower() or cap.lower() in action for cap in capabilities)

        config = student.configuration if isinstance(student.configuration, dict) else {}
        role = (config.get("role") or "").lower()
        if role and role != "general":
            from core.guided_automation_service import _TEMPLATE_KEYWORDS
            keywords = _TEMPLATE_KEYWORDS.get(role)
            if keywords:
                return any(kw in action or action in kw.replace(" ", "_") for kw in keywords)
        return True  # generic students observe everything

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
        # the training system confers maturity. Never lowers confidence
        # (agents created with a higher starting score keep it).
        student.confidence_score = max(old_confidence, min(_CONFIDENCE_CEILING, old_confidence + boost))
        actual_boost = student.confidence_score - old_confidence

        self.db.commit()

        # Real-time circuit: the hire's confidence just moved (lesson,
        # observation, correction). The trigger path caches maturity +
        # confidence in the GovernanceCache for up to 5 minutes — drop the
        # cached snapshot so the NEXT gated decision sees the updated agent.
        # Best-effort: cache unavailability must never fail the learning.
        try:
            from core.governance_cache import get_governance_cache

            get_governance_cache().invalidate_agent(student.id)
        except Exception as cache_err:
            logger.debug(f"governance cache invalidate skipped: {cache_err}")

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
