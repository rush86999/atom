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

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel
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

# A lesson taught from a canvas (TrainingPanel on /canvas/{id}) carries the
# canvas it was taught on — name, app, and a bounded content digest — so at
# retrieval the agent knows WHAT the lesson is about, not just the rule.
_CANVAS_DIGEST_CHARS = 400

# Log entries that carry standing guidance (vs. one-time event observations).
_PERMANENT_OBSERVATIONS = {"human_correction", "user_style"}


def _new_entry_id() -> str:
    """Stable per-entry handle, minted at write time so the canvas Training
    tab can address ONE teaching point for editing/deletion (the log itself
    is append-only JSON, not a keyed table)."""
    return uuid.uuid4().hex


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


def _canvas_digest(content: Any) -> str:
    """Bounded plain-text digest of canvas content at teach time. The digest
    is recall context ("what the canvas looked like when I was taught this"),
    not an editable artifact — so lossy flattening is fine."""
    parts: List[str] = []
    if isinstance(content, str):
        parts.append(re.sub(r"<[^>]+>", " ", content))
    elif isinstance(content, dict):
        for value in content.values():
            if isinstance(value, str):
                parts.append(re.sub(r"<[^>]+>", " ", value))
            elif value is not None:
                parts.append(json.dumps(value, default=str, ensure_ascii=False))
    elif content is not None:
        parts.append(json.dumps(content, default=str, ensure_ascii=False))
    text = " ".join(p.strip() for p in parts if p and p.strip())
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _CANVAS_DIGEST_CHARS:
        text = text[:_CANVAS_DIGEST_CHARS] + "…"
    return text


def build_canvas_context(db: Session, canvas_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Snapshot the named canvas (name, app, bounded content digest) for a
    lesson entry — what the teacher was looking at when they taught it.
    Fault-isolated: returns None when the canvas is missing or anything
    fails; a teach must never break on context capture."""
    if not canvas_id:
        return None
    try:
        from core.canvas_app_schema import normalize_app_type, resolve_app_spec
        from core.models import Canvas

        canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
        if canvas is None:
            return None
        # File binding wins over the legacy registry canvas_type so an office
        # .xlsx canvas reports "office_excel" instead of the generic "sheet".
        spec = resolve_app_spec(canvas.canvas_type, canvas.content)
        canvas_type = spec.canvas_type or normalize_app_type(canvas.canvas_type)
        return {
            "canvas_id": str(canvas.id),
            "name": str(canvas.name or "")[:120],
            "canvas_type": canvas_type,
            "label": spec.label,
            "digest": _canvas_digest(canvas.content),
        }
    except Exception as e:
        logger.debug(f"canvas context capture skipped for {canvas_id}: {e}")
        return None


def get_agent_lessons(
    db: Session,
    agent_id: str,
    query: Optional[str] = None,
    limit: int = WORK_TIME_LESSON_LIMIT,
    goal_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """The agent's permanent lessons, newest first, for injection at work time.

    Reads the durable learning log from AgentRegistry.configuration — the
    same store learn_from_teacher / learn_from_observation write. Works for
    ANY agent status: lessons survive graduation (that is what makes a
    trained agent stay trained). When ``query`` is given, lessons are
    keyword-scored against it and relevance breaks recency ties, so the
    lessons that matter for THIS task fit in the limit. Fault-isolated:
    returns [] on any failure — never blocks the working turn.

    ``goal_id`` is the SCOPE the caller is working in. A lesson can be taught
    against one goal ("check the FX rate before asking me" — true for that
    deal, noise everywhere else) or for all of the agent's work. Pass the
    goal being worked and goal-scoped lessons for THAT goal are included;
    omit it (chat, canvas edits, ordinary task runs) and only the agent's
    global lessons apply. Entries written before scope existed have none and
    are therefore global — the historical behaviour, unchanged.
    """
    lessons = [
        e for e in _permanent_lessons(db, agent_id)
        if _lesson_in_scope(e, goal_id)
    ]

    if query:
        q_tokens = {
            t for t in re.findall(r"[a-z0-9]{3,}", str(query).lower())
            if t not in {"the", "and", "for", "with", "this", "that", "please", "can", "you", "your"}
        }
        def _score(entry: Dict[str, Any]) -> int:
            # The canvas a lesson was taught on is part of the lesson's
            # subject: "the invoice sheet" should surface the lesson taught
            # on that canvas even if the rule text never says "invoice".
            canvas = entry.get("canvas") if isinstance(entry.get("canvas"), dict) else {}
            haystack = " ".join((
                str(entry.get("topic") or ""),
                _lesson_text(entry),
                str(canvas.get("name") or ""),
                str(canvas.get("label") or ""),
                str(canvas.get("digest") or ""),
            )).lower()
            return sum(1 for t in q_tokens if t in haystack)
        # Relevance first, recency as the tie-break (reverse() above made
        # the list newest-first, and sort is stable, so equal scores keep it).
        lessons.sort(key=_score, reverse=True)

    return lessons[:max(0, limit)]


def _permanent_lessons(db: Session, agent_id: str) -> List[Dict[str, Any]]:
    """EVERY permanent lesson for the agent, newest first, ignoring scope.

    The raw journal view: dedup ("is this rule already known at least as
    broadly?") and the goal-run page's "what has it learned" list need to see
    goal-scoped entries too, which ``get_agent_lessons`` deliberately hides
    from work time. Fault-isolated → []."""
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
    return lessons


def _lesson_in_scope(entry: Dict[str, Any], goal_id: Optional[str]) -> bool:
    """True when this lesson applies while working ``goal_id``.

    Only lessons explicitly scoped to a goal are excluded — everything else
    (and everything written before scope existed) is global guidance and
    always applies."""
    if not isinstance(entry, dict) or entry.get("scope") != "goal":
        return True
    return bool(goal_id) and str(entry.get("goal_id") or "") == str(goal_id)


def list_agent_lessons(
    db: Session,
    agent_id: str,
    goal_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """The agent's permanent lessons for DISPLAY, newest first, with scope.

    Powers the goal-run page's "what has it learned" list: unlike
    ``get_agent_lessons`` this returns a flat, render-ready shape and can be
    asked for one goal's view (that goal's scoped lessons + the agent's
    global guidance). Fault-isolated → []."""
    out: List[Dict[str, Any]] = []
    for entry in _permanent_lessons(db, agent_id):
        if not _lesson_in_scope(entry, goal_id):
            continue
        out.append({
            "id": entry.get("id"),
            "text": _lesson_text(entry),
            "scope": entry.get("scope") or "global",
            "goal_id": entry.get("goal_id"),
            "source": entry.get("source"),
            "topic": entry.get("topic") or entry.get("observation_type"),
            "learned_at": entry.get("learned_at"),
        })
        if len(out) >= max(0, limit):
            break
    return out


# ---------------------------------------------------------------------------
# Teaching-point editing (canvas Training tab)
# ---------------------------------------------------------------------------
# The journal is the read side of the teach channel; a lesson that is wrong,
# duplicated, or superseded must be CORRECTABLE in place, not only appendable —
# a permanent lesson is injected into every later turn, so a typo outlives the
# mistake it was meant to fix. Entries written before ids existed are addressed
# by position ("log:<index>"); the first edit mints a real id so later edits
# survive log trimming (the append path drops the OLDEST rows, which shifts
# every positional handle).


def teaching_point_id(entry: Any, index: int) -> str:
    """The stable handle for one log entry — the stored uuid, or the legacy
    positional id for rows written before ids existed."""
    if isinstance(entry, dict):
        stored = entry.get("id")
        if isinstance(stored, str) and stored:
            return stored
    return f"log:{index}"


def resolve_teaching_point(
    agent: AgentRegistry, point_id: str
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """``(index, entry)`` for a teaching-point handle, or None when it does
    not exist on this agent.

    Accepts a stored uuid or a legacy "log:<index>" positional id. A
    positional handle stops resolving once its row carries a real id (the
    uuid is then the only addressing), so a stale index can never rewrite a
    different lesson after the log shifts.
    """
    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning") if isinstance(config.get("learning"), dict) else {}
    log = learning.get("log") if isinstance(learning, dict) else None
    if not isinstance(log, list):
        return None
    pid = str(point_id or "")
    if pid.startswith("log:"):
        try:
            index = int(pid[4:])
        except ValueError:
            return None
        if (
            0 <= index < len(log)
            and isinstance(log[index], dict)
            and not log[index].get("id")
        ):
            return index, log[index]
        return None
    for index, entry in enumerate(log):
        if isinstance(entry, dict) and entry.get("id") == pid:
            return index, entry
    return None


def _commit_log(db: Session, agent: AgentRegistry, log: List[Any]) -> None:
    """Persist a rewritten lesson log. Fresh-dict assign + flag_modified so
    the JSON column actually flushes (same contract as journal_standing_lesson)."""
    from sqlalchemy.orm.attributes import flag_modified

    config = dict(agent.configuration) if isinstance(agent.configuration, dict) else {}
    learning = dict(config.get("learning") or {})
    if len(log) > MAX_LOG_ENTRIES:
        del log[:-MAX_LOG_ENTRIES]
    learning["log"] = list(log)
    learning["pathways_used"] = sorted(
        {str(e.get("source") or "observation") for e in log if isinstance(e, dict)}
    )
    config["learning"] = learning
    agent.configuration = config
    flag_modified(agent, "configuration")
    db.commit()


def update_teaching_point(
    db: Session,
    agent_id: str,
    point_id: str,
    *,
    text: Optional[str] = None,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """Rewrite one teaching point in place (its text and, for teacher
    lessons, its topic). Never raises — returns a service-shaped result.

    An edit is a CORRECTION, not new learning: ``learned_at`` is preserved,
    no confidence nudge is applied, and ``edited_at`` records the change. The
    rewritten text is what ``get_agent_lessons`` injects from now on.
    """
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if agent is None:
        return {"status": "error", "reason": "agent_not_found"}
    resolved = resolve_teaching_point(agent, point_id)
    if resolved is None:
        return {"status": "error", "reason": "point_not_found"}
    index, entry = resolved

    new_text = text.strip() if isinstance(text, str) else None
    new_topic = topic.strip() if isinstance(topic, str) else None
    if new_text == "":
        return {"status": "error", "reason": "empty_lesson"}
    if new_topic == "":
        new_topic = None
    if new_text is None and new_topic is None:
        return {"status": "error", "reason": "nothing_to_update"}
    # observation_type classifies the entry (human_correction IS standing
    # guidance, hitl_approval is not) — a topic edit must not silently change
    # how the lesson is applied at work time.
    if new_topic is not None and entry.get("source") == "observation":
        return {"status": "error", "reason": "topic_not_editable"}

    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning") if isinstance(config.get("learning"), dict) else {}
    log = list(learning.get("log") or [])

    updated: Dict[str, Any] = dict(entry)
    if new_text is not None:
        if updated.get("source") == "observation":
            updated["summary"] = new_text[:1000]
        else:
            updated["lesson"] = new_text[:2000]
    if new_topic is not None:
        updated["topic"] = new_topic[:200]
    updated["id"] = updated.get("id") or _new_entry_id()
    updated["edited_at"] = datetime.now(timezone.utc).isoformat()

    log[index] = updated
    _commit_log(db, agent, log)
    return {"status": "ok", "point_id": updated["id"], "entry": updated}


def delete_teaching_point(
    db: Session, agent_id: str, point_id: str
) -> Dict[str, Any]:
    """Drop one teaching point from the agent's log. Used for junk/duplicate
    lessons that would otherwise be injected at work time forever. Never
    raises — returns a service-shaped result."""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if agent is None:
        return {"status": "error", "reason": "agent_not_found"}
    resolved = resolve_teaching_point(agent, point_id)
    if resolved is None:
        return {"status": "error", "reason": "point_not_found"}
    index, entry = resolved

    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning") if isinstance(config.get("learning"), dict) else {}
    log = list(learning.get("log") or [])
    del log[index]
    _commit_log(db, agent, log)
    return {"status": "ok", "point_id": teaching_point_id(entry, index)}


def journal_standing_lesson_entry(
    db: Session,
    agent_id: str,
    lesson: str,
    *,
    source: str = "observation",
    observation_type: Optional[str] = "human_correction",
    topic: Optional[str] = None,
    teacher_agent_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    canvas_context: Optional[Dict[str, Any]] = None,
    scope: str = "global",
    goal_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Append a permanent lesson DIRECTLY to an agent's registry lesson log —
    status-independent, so a taught rule reaches SUPERVISED and graduated
    hires too (StudentLearningService's instance methods only accept
    STUDENT-status agents, but "the supervisor's correction IS the approval
    for their own agent" — commit eaaa8b71a's rationale, generalized to
    every teaching surface). Deduped against the existing log so repeated
    identical lessons don't stack. Fresh-dict assign + flag_modified so the
    JSON column actually flushes.

    Returns the appended entry (whose ``id`` is the teaching-point handle
    the Training tab and the chat confirmation chip address) or None when
    the agent is missing or the lesson is empty/duplicate; raises nothing.
    """
    text = str(lesson or "").strip()
    if not text or not agent_id:
        return None
    try:
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
        if agent is None:
            return None
        existing = {
            _lesson_text(e) for e in get_agent_lessons(db, agent_id, limit=50)
        }
        if text in existing:
            return None

        if source == "teacher":
            entry: Dict[str, Any] = {
                "id": _new_entry_id(),
                "source": "teacher",
                "teacher_agent_id": teacher_agent_id or "human_supervisor",
                "topic": topic or "general",
                "lesson": text[:2000],
                "learned_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            entry = {
                "id": _new_entry_id(),
                "source": "observation",
                "observation_type": observation_type or "human_correction",
                "summary": text[:1000],
                "details": dict(details or {}),
                "learned_at": datetime.now(timezone.utc).isoformat(),
            }
        if canvas_context:
            entry["canvas"] = canvas_context
        # Scope: a lesson taught against ONE goal applies only while working
        # that goal; everything else is global guidance. Absent scope (rows
        # written before this existed) reads as global.
        if scope == "goal" and goal_id:
            entry["scope"] = "goal"
            entry["goal_id"] = str(goal_id)
        else:
            entry["scope"] = "global"

        from sqlalchemy.orm.attributes import flag_modified

        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        learning = dict(config.get("learning") or {})
        log = list(learning.get("log") or [])
        log.append(entry)
        if len(log) > MAX_LOG_ENTRIES:
            del log[:-MAX_LOG_ENTRIES]
        learning["log"] = log
        learning["last_learned_at"] = entry["learned_at"]
        config = {**config, "learning": learning}
        agent.configuration = config
        flag_modified(agent, "configuration")
        db.commit()
        return entry
    except Exception as e:
        logger.debug(f"standing-lesson journal skipped for {agent_id}: {e}")
        return None


def journal_standing_lesson(
    db: Session,
    agent_id: str,
    lesson: str,
    *,
    source: str = "observation",
    observation_type: Optional[str] = "human_correction",
    topic: Optional[str] = None,
    teacher_agent_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    canvas_context: Optional[Dict[str, Any]] = None,
    scope: str = "global",
    goal_id: Optional[str] = None,
) -> bool:
    """Boolean face of :func:`journal_standing_lesson_entry` — the shape every
    existing caller (canvas corrections, teaching circuits, goal runs) already
    depends on. True when the lesson landed, False when it was empty, a
    duplicate, or the agent is missing."""
    return journal_standing_lesson_entry(
        db, agent_id, lesson,
        source=source,
        observation_type=observation_type,
        topic=topic,
        teacher_agent_id=teacher_agent_id,
        details=details,
        canvas_context=canvas_context,
        scope=scope,
        goal_id=goal_id,
    ) is not None


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
        "id": _new_entry_id(),
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
        # The canvas the lesson was taught on — the agent should know what
        # the lesson's subject looks like without being able to ask.
        canvas = entry.get("canvas") if isinstance(entry.get("canvas"), dict) else {}
        if canvas.get("name"):
            label = str(canvas.get("label") or canvas.get("canvas_type") or "").strip()
            line += f" — taught on canvas \"{canvas['name']}\"" + (f" ({label})" if label else "")
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
        canvas_context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
        goal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a teacher-delivered lesson (fast path). ``canvas_context``
        (see build_canvas_context) pins the lesson to the canvas it was
        taught on so retrieval can recall the subject, not just the rule.
        ``scope``/``goal_id`` mark a lesson that is true only for ONE goal
        (see journal_standing_lesson_entry)."""
        student = self._get_student(student_agent_id)
        if student is None:
            return {"status": "error", "reason": "student_not_found"}

        entry = {
            "id": _new_entry_id(),
            "source": "teacher",
            "teacher_agent_id": teacher_agent_id,
            "topic": topic or "general",
            "lesson": lesson[:2000],
            "learned_at": datetime.now(timezone.utc).isoformat(),
        }
        if canvas_context:
            entry["canvas"] = canvas_context
        if scope == "goal" and goal_id:
            entry["scope"] = "goal"
            entry["goal_id"] = str(goal_id)
        else:
            entry["scope"] = "global"
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
            "id": _new_entry_id(),
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


def deliver_teacher_lesson(
    db: Session,
    agent_id: str,
    lesson: str,
    *,
    topic: Optional[str] = None,
    canvas_id: Optional[str] = None,
    teacher_agent_id: str = "human_supervisor",
    record_session_lesson: bool = True,
    scope: str = "global",
    goal_id: Optional[str] = None,
) -> Dict[str, Any]:
    """One human/mentor-delivered lesson → permanent training, at ANY tier.

    This is the composite EVERY teaching surface shares — ``POST
    /api/agents/{id}/teach`` (the canvas Training tab's form, the goal-run
    page's teach box) and the chat teaching channel (``/teach`` in the
    message box, detected teaching cues) — so a lesson means the same thing
    wherever it was taught:

      1. snapshot the canvas the lesson was taught on (recall context),
      2. a STUDENT gets the pedagogy circuit (confidence nudge + mastery
         exposure + filing into an ACTIVE training session),
      3. everyone else gets the status-independent standing journal (a
         graduated hire still learns; lessons survive graduation).

    ``scope="goal"`` + ``goal_id`` records a lesson that is true only while
    working THAT goal (a deal-specific instruction); the default is global
    guidance for all of the agent's work.

    Fault-isolated: returns a service-shaped dict and never raises. The
    ``entry`` is the appended lesson (its ``id`` is the teaching-point
    handle the Training tab and the chat confirmation chip address).
    """
    result: Dict[str, Any] = {
        "status": "agent_not_found",
        "mode": None,
        "agent_name": None,
        "agent_status": None,
        "entry": None,
        "confidence": None,
        "data": {},
    }
    try:
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
    except Exception as e:  # noqa: BLE001 — a lookup failure must not 500 the chat turn
        logger.debug(f"teacher-lesson agent lookup skipped for {agent_id}: {e}")
        return result
    if agent is None:
        return result

    text = str(lesson or "").strip()
    result["agent_name"] = agent.name
    result["agent_status"] = agent.status
    if not text:
        return {**result, "status": "empty"}

    # Dedup must cover BOTH pathways. The standing journal already refused
    # repeated identical lessons, but the STUDENT pedagogy path did not — so
    # teaching the same rule twice stacked two identical entries, and the
    # bounded work-time block rendered the same instruction twice while
    # spending a lesson slot. Checked here, before either write, so every
    # teaching surface (the /teach form, the chat channel, mentor lessons)
    # behaves alike.
    #
    # Scope-aware: a lesson already known GLOBALLY covers a goal-scoped
    # request (global applies everywhere), and a lesson already scoped to
    # THIS goal covers a repeat of it — but the same words taught against a
    # DIFFERENT goal is genuinely new guidance and must be allowed.
    try:
        already_taught = _has_covering_lesson(db, agent_id, text, scope, goal_id)
    except Exception:  # noqa: BLE001 — a read failure must not block a teach
        already_taught = False
    if already_taught:
        return {**result, "status": "duplicate"}

    canvas_context = build_canvas_context(db, canvas_id)

    # STUDENT fast path: the pedagogy circuit (confidence + mastery).
    student_result = StudentLearningService(db).learn_from_teacher(
        student_agent_id=agent_id,
        teacher_agent_id=teacher_agent_id,
        lesson=text,
        topic=topic,
        canvas_context=canvas_context,
        scope=scope,
        goal_id=goal_id,
    )
    if student_result.get("status") == "ok":
        entry = None
        try:
            newest = get_agent_lessons(db, agent_id, goal_id=goal_id, limit=1)
            entry = newest[0] if newest else None
        except Exception as e:  # noqa: BLE001
            logger.debug(f"teacher-lesson entry read skipped for {agent_id}: {e}")

        if record_session_lesson:
            # A lesson taught while a training session is ACTIVE also lands in
            # that session's guidance record (best-effort — the journal and
            # confidence above are the contract).
            try:
                from core.student_training_service import StudentTrainingService

                StudentTrainingService(db).record_session_lesson(
                    agent_id=agent_id, lesson=text, topic=topic,
                )
            except Exception as session_lesson_err:  # noqa: BLE001
                logger.debug(f"session lesson record skipped: {session_lesson_err}")

        return {
            **result,
            "status": "ok",
            "mode": "student",
            "entry": entry,
            "confidence": student_result.get("confidence"),
            "data": dict(student_result),
        }

    # Standing-guidance path: the same status-independent journal the canvas
    # correction and chat-feedback circuits use.
    entry = journal_standing_lesson_entry(
        db, str(agent.id), text,
        source="teacher",
        topic=topic,
        teacher_agent_id=teacher_agent_id,
        canvas_context=canvas_context,
        scope=scope,
        goal_id=goal_id,
    )
    if entry is not None:
        return {
            **result,
            "status": "ok",
            "mode": "standing_guidance",
            "entry": entry,
            "data": {"status": "ok", "mode": "standing_guidance",
                     "agent_status": agent.status},
        }

    # Nothing was appended: either the agent already carries this exact lesson
    # (dedup) or the journal failed. Distinguish so the UI can be honest.
    try:
        duplicate = _has_covering_lesson(db, agent_id, text, scope, goal_id)
    except Exception:  # noqa: BLE001
        duplicate = False
    return {**result, "status": "duplicate" if duplicate else "journal_failed"}


def _has_covering_lesson(
    db: Session,
    agent_id: str,
    text: str,
    scope: str,
    goal_id: Optional[str],
) -> bool:
    """True when this exact rule is ALREADY known at least as broadly.

    A global lesson covers every scope (it applies everywhere), and a lesson
    scoped to the same goal covers a repeat of itself. The same words scoped
    to a DIFFERENT goal is new guidance, not a duplicate — so coaching goal A
    never blocks coaching goal B with the same phrasing. Checks the raw
    journal (``_permanent_lessons``), because ``get_agent_lessons`` hides
    other goals' lessons from work-time callers."""
    want_goal = str(goal_id or "")
    for entry in _permanent_lessons(db, agent_id):
        if _lesson_text(entry) != text:
            continue
        if entry.get("scope") != "goal":
            return True  # already global — covers every scope
        if scope == "goal" and str(entry.get("goal_id") or "") == want_goal:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────
# Correction distillation: supervisor fixes the draft ON the canvas → the
# hire learns a REAL rule immediately, no send required (live 2026-09-04:
# the hire only visibly advanced when an email was sent+approved, because
# canvas corrections journaled a raw JSON dump as the "lesson" — unreadable
# at work time and in the Training panel, so the promised "fix it here and
# I'll learn" never landed until the send circuit fired).
# ─────────────────────────────────────────────────────────────────────────

_FALLBACK_CORRECTION_PREFIX = (
    "Supervisor corrected my work — follow the corrected "
    "version's content and style:"
)


class CorrectionLesson(BaseModel):
    """Structured output of the correction-distillation call."""
    teachable: bool = True
    lesson: str = ""


def _correction_llm():
    """Best-effort shared LLM accessor (same contract as the eval runner
    and exchange_memory_maintenance): None when no provider is configured,
    so the caller falls back to journaling the raw diff instead."""
    try:
        from core.incident_eval_runner import _default_llm_service

        return _default_llm_service()
    except Exception:
        return None


def raw_correction_gist(corrected_action: Any) -> str:
    """The legacy fallback lesson text — the corrected payload serialized.
    Kept byte-compatible with the pre-distillation journal so the no-LLM
    path behaves exactly as before."""
    gist = corrected_action if isinstance(corrected_action, str) else json.dumps(corrected_action, default=str)
    return f"{_FALLBACK_CORRECTION_PREFIX} {gist[:400]}"


async def distill_and_journal_correction(
    agent_id: str,
    original_content: Any,
    corrected_content: Any,
    canvas_id: Optional[str] = None,
    canvas_type: Optional[str] = None,
    canvas_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Distill a supervisor's canvas correction into ONE imperative rule and
    journal it as a permanent ``human_correction`` lesson — fire-and-forget
    from the correction-recording path (own DB session, like auto_observe).

    The distilled lesson is what the hire actually uses: get_agent_lessons
    feeds it into every canvas edit plan and the Training panel shows it as
    a teaching point. When no LLM is reachable the legacy raw-diff gist is
    journaled instead, so learning is never LOST — only less readable. A
    diff the LLM judges UNTEACHABLE (pure formatting, no-op) journals
    nothing: junk lessons crowd out real ones in the bounded work-time
    lesson list.
    """
    try:
        outcome, lesson_text = "fallback", None
        llm = _correction_llm()
        if llm is not None:
            try:
                outcome, lesson_text = await _distill_with_llm(
                    llm, original_content, corrected_content,
                    canvas_type, canvas_title,
                )
            except Exception as distill_err:
                # A dead/timed-out distill call must not lose the lesson:
                # degrade to the raw gist (same as no provider at all).
                logger.debug(f"correction distill call failed: {distill_err}")
                outcome, lesson_text = "unavailable", None
        if outcome == "unteachable":
            logger.info("correction distillation: diff judged unteachable — not journaled")
            return {"status": "not_teachable"}
        if outcome != "distilled" or not lesson_text:
            outcome, lesson_text = "fallback", raw_correction_gist(corrected_content)

        from core.database import SessionLocal

        session = SessionLocal()
        try:
            result = StudentLearningService(session).learn_from_observation(
                agent_id,
                "human_correction",
                lesson_text,
                details={
                    "canvas_id": canvas_id,
                    "canvas_type": canvas_type,
                    "distilled": outcome == "distilled",
                },
            )
        finally:
            session.close()
        logger.info(
            f"[LEARNING] correction lesson ({outcome}) journaled for {agent_id}"
        )
        return {"status": outcome, "journal": result, "lesson": lesson_text}
    except Exception as e:
        logger.debug(f"correction distillation skipped: {e}")
        return {"status": "error", "reason": str(e)}


async def _distill_with_llm(
    llm: Any,
    original_content: Any,
    corrected_content: Any,
    canvas_type: Optional[str],
    canvas_title: Optional[str],
) -> tuple:
    """One cheap structured call: BEFORE → AFTER diff ⇒ one imperative rule.
    Returns (outcome, lesson_text): ("distilled", rule) when the diff taught
    something, ("unteachable", None) when BEFORE and AFTER mean the same
    thing, ("unavailable", None) when the LLM returned nothing usable."""
    def _brief(value: Any, limit: int = 1500) -> str:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        return text[:limit]

    prompt = (
        "A supervisor just corrected a draft an AI assistant produced. "
        "Distill WHAT CHANGED into ONE short, imperative lesson the "
        "assistant must follow from now on. Judge only the difference "
        "between BEFORE and AFTER — do not invent rules about parts that "
        "are identical. Good lessons name the concrete rule: \"Always CC "
        "vipul@ and chandrakant@ on customer quote emails\", \"Use the "
        "exact list price, never a rounded figure\". Most corrections ARE "
        "teachable; return teachable=false ONLY when AFTER means the same "
        "thing as BEFORE (pure formatting, reordering, or a no-op).\n\n"
        f"Canvas type: {canvas_type or 'generic'}"
        + (f" ({canvas_title})" if canvas_title else "") + "\n\n"
        f"BEFORE (assistant's draft):\n{_brief(original_content)}\n\n"
        f"AFTER (supervisor's correction):\n{_brief(corrected_content)}\n\n"
        "Return the lesson (one sentence, at most 200 characters, "
        "imperative voice, from the assistant's perspective: \"Always …\", "
        "\"Never …\")."
    )
    plan = await llm.generate_structured_response(
        prompt=prompt,
        response_model=CorrectionLesson,
        system_instruction="You return only the requested JSON object.",
        temperature=0.0,
    )
    if plan is None:
        return "unavailable", None
    if not getattr(plan, "teachable", True):
        return "unteachable", None
    lesson = (getattr(plan, "lesson", "") or "").strip()
    if not lesson:
        return "unavailable", None
    return "distilled", lesson

