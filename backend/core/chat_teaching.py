"""Train an agent from chat — the canvas co-editor panel AND regular chat.

Training was reachable only from the canvas Training tab (a form) and from
thumbs-down comments. The chat path itself had NO teaching channel: the
``ChatIntent`` enum has no teaching member, so a message like "always CC the
lead on quotes" was treated as ordinary conversation and nothing was stored —
even though lessons are permanent work-time guidance injected into every chat
turn, canvas edit plan, and task run (``core/student_learning_service``).

This module is that missing channel. It is deliberately CONSERVATIVE, in the
same spirit as ``core/chat_draft_classifier`` (structural, not intent
guessing) and honouring the lesson-poisoning rule in
``docs/canvas/agent-learning.md`` (lessons are human-gated writes; keep it
that way):

* **Explicit command** — ``/teach <rule>``. Deterministic, saved immediately,
  confirmed in the transcript. This is the primary, always-works channel.
* **Detected cue** — a message that OPENS with a clear teaching directive
  ("always …", "never …", "from now on …", "remember that …"). This NEVER
  saves on its own: it returns a *suggestion* the user confirms with one
  click, so a misread of conversational phrasing cannot write a permanent
  instruction into the agent's prompt.

Writes go through ``student_learning_service.deliver_teacher_lesson`` — the
same composite ``POST /api/agents/{id}/teach`` uses — so a lesson means the
same thing everywhere it was taught.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.student_learning_service import deliver_teacher_lesson

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

# `/teach <rule>` — the explicit channel. A bare `/teach` is a usage request
# (parsed as an empty lesson, not as "not a command"). ``\b`` keeps
# "/teacher" and "/teachings" from matching.
_TEACH_COMMAND_RE = re.compile(
    r"^\s*/\s*teach\b[ \t]*[:\-\u2013\u2014]?[ \t]*(?P<lesson>.*)$",
    re.IGNORECASE | re.DOTALL,
)

# Detected-cue channel: the message must OPEN with the directive. Anchoring
# at the start is what keeps "I always wonder whether…" or "do you always…?"
# out — a cue buried mid-sentence is prose, not training.
_TEACHING_CUE_RE = re.compile(
    r"^(?:please[ \t]+)?(?:"
    r"always\b|"
    r"never\b|"
    r"from now on\b|"
    r"going forward\b|"
    r"remember(?:[ \t]+that)?\b|"
    r"keep in mind(?:[ \t]+that)?\b|"
    r"note(?:[ \t]+that)?\b|"
    r"make sure(?:[ \t]+that)?[ \t]+you[ \t]+(?:always|never)\b|"
    r"when\b.{3,120}?,[ \t]*(?:always|never|you should)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

# Conversational openers that trip the cue regex but mean nothing instructional
# ("never mind", "always happy to help"). Cheap, documented guard — and the
# detected-cue channel only ever SUGGESTS, so an escape here costs one click.
_CUE_FALSE_POSITIVES_RE = re.compile(
    r"^(?:never[ \t]+mind|never[ \t]+thought|never[ \t]+wanted|"
    r"always[ \t]+(?:happy|glad|good|nice|welcome|a pleasure))\b",
    re.IGNORECASE,
)

# Soft lead-ins stripped so the stored lesson reads as the rule, not as the
# conversational wrapper. "always"/"never"/"from now on" are KEPT — they are
# the substance of the instruction.
_LEAD_IN_RE = re.compile(
    r"^(?:please[ \t]+)?(?:"
    r"remember(?:[ \t]+that)?|"
    r"keep in mind(?:[ \t]+that)?|"
    r"note(?:[ \t]+that)?"
    r")[ \t]*[,:]?[ \t]*",
    re.IGNORECASE,
)

# Bounds: too short is not a rule; too long is a pasted essay, not a lesson
# (the store truncates at 2000, but a bounded suggestion reads better).
_MIN_LESSON_CHARS = 12
_MAX_LESSON_CHARS = 600

# How many agents to offer when the chat has no attached agent. Enough to
# pick from, few enough to render inline in a chat bubble.
_AGENT_CHOICE_LIMIT = 8


def parse_teach_command(message: Any) -> Optional[str]:
    """The lesson text from an explicit ``/teach <rule>`` message.

    Returns the (stripped) lesson, ``""`` for a bare ``/teach`` usage
    request, or ``None`` when the message is not the command at all.
    """
    match = _TEACH_COMMAND_RE.match(str(message or ""))
    if not match:
        return None
    return str(match.group("lesson") or "").strip()


def _is_question(text: str) -> bool:
    return text.rstrip().endswith("?")


def detect_teaching_cue(message: Any) -> Optional[str]:
    """The lesson text when a message OPENS with a teaching directive.

    Conservative by construction: questions are rejected, false-positive
    conversational openers are rejected, and the result is length-bounded.
    Returns None when the message does not look like teaching.
    """
    text = " ".join(str(message or "").split())
    if not text or _is_question(text):
        return None
    if not _TEACHING_CUE_RE.match(text):
        return None
    if _CUE_FALSE_POSITIVES_RE.match(text):
        return None
    lesson = _LEAD_IN_RE.sub("", text).strip(" \t\n:,-.\u2013\u2014")
    lesson = " ".join(lesson.split())
    if len(lesson) < _MIN_LESSON_CHARS or len(lesson) > _MAX_LESSON_CHARS:
        return None
    return lesson


# ---------------------------------------------------------------------------
# Target agent
# ---------------------------------------------------------------------------

def list_teachable_agents(
    db: Session, workspace_id: str = "default", limit: int = _AGENT_CHOICE_LIMIT
) -> List[Dict[str, Any]]:
    """Active agents the user can pick from when no agent is attached.

    Uses the same workspace-scoped registry read as ``GET /api/agents``
    (``AgentGovernanceService.list_agents``) so the chat list can never
    surface an agent the Agent Control Center would hide. Ordered most
    recently updated first. Fault-isolated → [] (the reply then just asks
    for an agent without options).
    """
    try:
        from core.agent_governance_service import AgentGovernanceService

        agents = AgentGovernanceService(
            db, workspace_id=workspace_id or "default"
        ).list_agents()
    except Exception as e:  # noqa: BLE001 — never block the chat turn
        logger.debug(f"teachable-agent list skipped: {e}")
        return []

    def _sort_key(agent: Any):
        updated = getattr(agent, "updated_at", None)
        return (
            getattr(agent, "confidence_score", 0.0) or 0.0,
            updated.timestamp() if updated is not None else 0.0,
            str(getattr(agent, "name", "") or ""),
        )

    ordered = sorted(agents, key=_sort_key, reverse=True)
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "display_name": getattr(a, "display_name", None),
            "category": getattr(a, "category", None),
            "status": getattr(a, "status", None),
            "confidence": getattr(a, "confidence_score", None),
        }
        for a in ordered[: max(0, limit)]
    ]


def _agent_brief(agent_id: str, name: Any = None, status: Any = None) -> Dict[str, Any]:
    return {"id": str(agent_id), "name": name, "status": status}


# ---------------------------------------------------------------------------
# Goal context: explicit, then inferred
# ---------------------------------------------------------------------------
# A lesson taught while an agent works a long-running goal is usually ABOUT
# that goal. Two ways to know which:
#
#  1. EXPLICIT — the chat was opened from a run ("Chat with this agent" on
#     /goal-runs/{id}), so the goal is known. Deterministic, no model call.
#  2. INFERRED — plain chat with an agent that has active goals. A cheap
#     structured call picks the goal the rule is clearly about, or none.
#
# Inference is SUGGESTION-GRADE and biased to "none": a general rule wrongly
# narrowed to one goal silently stops applying everywhere else. That is why
# the model is told to prefer null, a confidence floor is enforced, a goal id
# the model was not offered is discarded, and the confirmation card always
# shows the scope with a one-click widen.

# The agent's goals that are still being worked (a terminal run's goal is not
# a candidate — you cannot scope new coaching to it).
_LIVE_GOAL_STATUSES = ("planning", "active", "waiting", "paused_hitl")

# Inference is a suggestion, not a decision: require real confidence.
_GOAL_INFERENCE_MIN_CONFIDENCE = 0.7


class LessonGoalMatch(BaseModel):
    """Structured output of the goal-inference call."""

    goal_id: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""


_GOAL_INFERENCE_SYSTEM = """You decide whether a rule a supervisor just taught \
an agent is specific to ONE of the goals that agent is currently working, or \
is general guidance for all of its work.

Return `goal_id` = the id of the single goal the rule is clearly about, or \
null when the rule is general — style, tone, formatting, a standing policy, \
a house rule, or anything not tied to one goal's subject.

Prefer null when unsure: a general rule wrongly scoped to one goal stops \
applying to everything else the agent does.

`confidence` is 0..1 (how sure you are it belongs to that goal), `reason` is \
one short sentence."""


def goal_title(db: Session, goal_id: Optional[str]) -> Optional[str]:
    """The human title of a goal (fault-isolated → None)."""
    if not goal_id:
        return None
    try:
        from core.models import GoalObjective

        goal = db.query(GoalObjective).filter(GoalObjective.id == goal_id).first()
        return (goal.title or None) if goal is not None else None
    except Exception as e:  # noqa: BLE001
        logger.debug(f"goal title lookup skipped for {goal_id}: {e}")
        return None


def goal_context_for_run(db: Session, goal_run_id: Optional[str]) -> Optional[Dict[str, str]]:
    """``{goal_id, title}`` for a goal run — the EXPLICIT scope signal.

    Set when the chat was opened from a run ("Chat with this agent" on the
    run page), which makes the goal known without any inference. Returns None
    for a missing/unknown run so the caller falls back to inference or global.
    Fault-isolated."""
    if not goal_run_id:
        return None
    try:
        from core.models import GoalRun

        run = db.query(GoalRun).filter(GoalRun.id == str(goal_run_id)).first()
        if run is None or not run.goal_id:
            return None
        return {"goal_id": str(run.goal_id),
                "title": goal_title(db, str(run.goal_id)) or ""}
    except Exception as e:  # noqa: BLE001
        logger.debug(f"goal-run context lookup skipped for {goal_run_id}: {e}")
        return None


def active_goals_for_agent(
    db: Session, agent_id: Optional[str], limit: int = 8
) -> List[Dict[str, str]]:
    """Goals this agent is still working — ``[{goal_id, title}]``, newest first.

    The candidate set for scope inference AND the reason inference is skipped
    entirely for agents with no live goals (no call, no cost). Fault-isolated
    → []."""
    if not agent_id:
        return []
    try:
        from core.models import GoalObjective, GoalRun

        runs = (
            db.query(GoalRun.goal_id)
            .filter(
                GoalRun.agent_id == str(agent_id),
                GoalRun.status.in_(_LIVE_GOAL_STATUSES),
            )
            .order_by(GoalRun.created_at.desc())
            .limit(max(1, limit) * 2)
            .all()
        )
        goal_ids: List[str] = []
        for (gid,) in runs:
            if gid and gid not in goal_ids:
                goal_ids.append(gid)
        goal_ids = goal_ids[: max(1, limit)]
        if not goal_ids:
            return []
        goals = (
            db.query(GoalObjective)
            .filter(GoalObjective.id.in_(goal_ids))
            .all()
        )
        titles = {g.id: (g.title or "") for g in goals}
        return [
            {"goal_id": gid, "title": titles.get(gid, "")[:120]}
            for gid in goal_ids
            if gid in titles
        ]
    except Exception as e:  # noqa: BLE001 — never block a teach on this
        logger.debug(f"active-goal lookup skipped for {agent_id}: {e}")
        return []


async def infer_lesson_goal(
    llm_service: Any,
    *,
    lesson: str,
    candidates: List[Dict[str, str]],
    min_confidence: float = _GOAL_INFERENCE_MIN_CONFIDENCE,
) -> Optional[Dict[str, Any]]:
    """The one active goal a taught rule is clearly about, or None.

    Suggestion-grade by construction: returns None on any failure, on an
    answer below ``min_confidence``, and when the model names a goal that was
    not offered (hallucination guard). Never raises.
    """
    if not candidates or llm_service is None:
        return None
    try:
        from core.llm.pinned_planning import pinned_structured_call

        listing = "\n".join(
            f"- {c.get('title') or '(untitled goal)'} (id: {c['goal_id']})"
            for c in candidates
        )
        prompt = (
            f"Rule the supervisor just taught:\n\"{lesson}\"\n\n"
            f"Goals this agent is currently working:\n{listing}\n\n"
            "Which single goal, if any, is this rule about?"
        )
        result = await pinned_structured_call(
            llm_service,
            prompt=prompt,
            response_model=LessonGoalMatch,
            system_instruction=_GOAL_INFERENCE_SYSTEM,
            log_label="lesson goal inference",
            task_type="planning",
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"lesson goal inference skipped: {e}")
        return None

    named = getattr(result, "goal_id", None)
    if not named:
        return None
    try:
        confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if confidence < min_confidence:
        logger.debug(
            f"lesson goal inference below floor ({confidence:.2f}) — left general"
        )
        return None
    match = next((c for c in candidates if c.get("goal_id") == named), None)
    if match is None:
        # The model named a goal we never offered — treat as "no match" rather
        # than trusting an id it may have invented.
        logger.debug("lesson goal inference named an unoffered goal — ignored")
        return None
    return {**match, "confidence": confidence}


# ---------------------------------------------------------------------------
# Notices (the shape the frontend renders)
# ---------------------------------------------------------------------------

def _notice(status: str, *, lesson: str, message: str, **extra: Any) -> Dict[str, Any]:
    return {"status": status, "lesson": lesson, "message": message, **extra}


def teach_from_chat(
    db: Session,
    *,
    agent_id: Optional[str],
    lesson: str,
    canvas_id: Optional[str] = None,
    workspace_id: str = "default",
    goal_id: Optional[str] = None,
    goal_title: Optional[str] = None,
    goal_inferred: bool = False,
) -> Dict[str, Any]:
    """Save a `/teach` lesson for the chat's agent and describe the outcome.

    ``goal_id`` scopes the lesson to that goal (see the module docstring on
    scope): pass it when the chat was opened from a run, or when inference
    matched one. Omitting it keeps the lesson global — the default for chat,
    which has no goal context of its own.

    Returns a notice dict (see :func:`_notice`) with ``status`` one of
    ``saved`` / ``duplicate`` / ``needs_agent`` / ``empty`` / ``error``. A
    ``needs_agent`` notice carries the pickable ``agents`` list so the UI can
    resolve it inline instead of bouncing the user to another page.
    Never raises.
    """
    text = " ".join(str(lesson or "").split())
    if not text:
        return _notice(
            "empty",
            lesson="",
            message=(
                "Tell me what to teach, for example: "
                "`/teach Always CC the lead on quotes`"
            ),
        )
    if len(text) > 2000:
        text = text[:2000]

    if not agent_id:
        return _notice(
            "needs_agent",
            lesson=text,
            message=(
                "I can save that as a permanent lesson, but I need to know "
                "which agent should learn it. Pick one below — or open a "
                "canvas and teach from its chat to use its attached agent."
            ),
            agents=list_teachable_agents(db, workspace_id=workspace_id),
        )

    scope = "goal" if goal_id else "global"
    try:
        delivery = deliver_teacher_lesson(
            db, str(agent_id), text, canvas_id=canvas_id,
            scope=scope, goal_id=goal_id,
        )
    except Exception as e:  # noqa: BLE001 — a teach must never break the turn
        logger.debug(f"chat teach delivery skipped for {agent_id}: {e}")
        return _notice("error", lesson=text,
                       message="I couldn't save that lesson — nothing was changed.")

    status = delivery.get("status")
    agent = _agent_brief(
        agent_id, delivery.get("agent_name"), delivery.get("agent_status")
    )
    entry = delivery.get("entry") or {}
    point_id = entry.get("id") if isinstance(entry, dict) else None
    scope_payload: Dict[str, Any] = {
        "scope": scope,
        "goal_id": goal_id,
        "goal_title": goal_title,
        "goal_inferred": bool(goal_id and goal_inferred),
    }

    if status == "ok":
        name = delivery.get("agent_name") or "the agent"
        if goal_id:
            where = f'only while working "{goal_title}"' if goal_title \
                else "only while working that goal"
            message = (
                f"✓ Learned — {name} will apply this {where}."
                + (" (I inferred the goal from what you're working on — "
                   "say the word to apply it to all of their work.)"
                   if goal_inferred else "")
            )
        else:
            message = (
                f"✓ Learned — {name} will apply this to all of their work "
                "from now on."
            )
        return _notice("saved", lesson=text, message=message, agent=agent,
                       mode=delivery.get("mode"), teaching_point_id=point_id,
                       **scope_payload)

    if status == "duplicate":
        name = delivery.get("agent_name") or "that agent"
        return _notice(
            "duplicate",
            lesson=text,
            message=f"That's already one of {name}'s lessons — nothing to add.",
            agent=agent,
            **scope_payload,
        )

    if status == "agent_not_found":
        return _notice(
            "needs_agent",
            lesson=text,
            message=(
                "I couldn't find that agent any more. Pick the agent that "
                "should learn this:"
            ),
            agents=list_teachable_agents(db, workspace_id=workspace_id),
        )

    return _notice("error", lesson=text, agent=agent,
                   message="I couldn't save that lesson — nothing was changed.")


def suggest_lesson(
    db: Session,
    *,
    agent_id: Optional[str],
    lesson: str,
    canvas_id: Optional[str] = None,
    workspace_id: str = "default",
) -> Optional[Dict[str, Any]]:
    """A *detected* teaching cue as a confirm-first suggestion.

    Detected cues are never saved on their own (see the module docstring):
    this builds the inline confirmation card. Returns None when there is no
    agent to teach — with no target there is nothing to confirm, and the
    suggestion would just be noise on an ordinary conversational turn.
    Never raises.
    """
    text = " ".join(str(lesson or "").split())
    if not text or not agent_id:
        return None
    try:
        from core.models import AgentRegistry

        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == str(agent_id)
        ).first()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"lesson suggestion lookup skipped for {agent_id}: {e}")
        return None
    if agent is None:
        return None
    name = agent.name or "this agent"
    return _notice(
        "suggested",
        lesson=text,
        message=f"Save this as a permanent lesson for {name}?",
        agent=_agent_brief(agent_id, agent.name, agent.status),
        canvas_id=canvas_id,
    )
