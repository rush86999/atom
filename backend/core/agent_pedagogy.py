"""
Pedagogical framework for agent skill-building.

Implements evidence-based education principles so STUDENT/INTERN agents
learn the way people do, and so grey-area decisions get a structured
middle ground — rigid rules ("always block") and unlimited flexibility
("always allow") are both extremes that fail in ambiguity.

Principles and their source:
- Zone of Proximal Development (Vygotsky): learning happens on tasks just
  beyond independent ability. We classify every task as too_easy / in_zpd /
  too_hard for the agent's current maturity.
- Scaffolding + Fading (Collins, Brown & Newman's cognitive apprenticeship):
  support starts high (full guidance) and is gradually withdrawn as mastery
  of a topic is demonstrated — never all-at-once, never permanent.
- Mastery learning (Bloom): progression per topic requires demonstrated
  competence (repeated successful exposures), not time served.
- Deliberate practice feedback loop (Ericsson): every grey-area decision is
  recorded with its rationale (articulation) and its outcome feeds back into
  topic mastery (reflection) — mistakes add corrective lessons.
- Banded judgment: instead of a rigid allow/deny rule or free-form agent
  discretion, grey areas resolve through calibrated confidence bands that
  map to escalation actions, each auditable and reversible.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import AgentRegistry

logger = logging.getLogger(__name__)

# Exposures (with good outcomes) needed before a topic counts as mastered.
MASTERY_THRESHOLD = 3

# Confidence bands for grey-area judgment. Between the rigid extreme
# (always escalate) and the flexible extreme (always proceed), three bands
# give a defensible, auditable middle:
#   < ASK_TEACHER_BELOW  -> the student asks the meta agent (cheap, fast)
#   < ASK_HUMAN_BELOW    -> human-in-the-loop review (HITL)
#   otherwise            -> proceed, logged, with mandatory outcome review
ASK_TEACHER_BELOW = 0.35
ASK_HUMAN_BELOW = 0.70

_MATURITY_ORDER = ["student", "intern", "supervised", "autonomous"]


class ScaffoldLevel(str, Enum):
    """Support levels, ordered from most to least support (fading order)."""

    FULL_GUIDANCE = "full_guidance"  # teacher demonstrates; student watches
    HINTS = "hints"                  # student acts; teacher gives hints
    CHECKLIST = "checklist"          # student acts with a written checklist
    INDEPENDENT = "independent"      # no scaffold; outcome review only

    @classmethod
    def fade_order(cls) -> List["ScaffoldLevel"]:
        return [cls.FULL_GUIDANCE, cls.HINTS, cls.CHECKLIST, cls.INDEPENDENT]


class TaskFit(str, Enum):
    TOO_EASY = "too_easy"      # no learning; safe to batch/automate
    IN_ZPD = "in_zpd"          # learn here: guided stretch
    TOO_HARD = "too_hard"      # blocked; needs teacher first


class GreyAreaDecision(str, Enum):
    ASK_TEACHER = "ask_teacher"
    ASK_HUMAN = "ask_human"
    PROCEED_LOGGED = "proceed_logged"


class PedagogicalFramework:
    """Scaffolding, mastery, and grey-area judgment for one agent."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # ZPD: match tasks to the agent's current ability
    # ------------------------------------------------------------------

    def classify_task(self, agent: AgentRegistry, action_complexity: int) -> Dict[str, Any]:
        """Classify a task's fit for the agent (Zone of Proximal Development).

        in_zpd means: within reach with guidance — at most one complexity
        level above what the agent can already do unsupervised.
        """
        status = (agent.status or "student").lower()
        maturity_idx = _MATURITY_ORDER.index(status) if status in _MATURITY_ORDER else 0
        # complexity is 1-based (1..4); at-level == maturity_idx (0-based)
        if action_complexity <= maturity_idx:
            fit = TaskFit.TOO_EASY
        elif action_complexity <= maturity_idx + 2:
            fit = TaskFit.IN_ZPD
        else:
            fit = TaskFit.TOO_HARD

        return {
            "fit": fit.value,
            "recommended_scaffold": self.get_scaffold_level(agent, topic=None, task_fit=fit).level.value,
            "note": {
                TaskFit.TOO_EASY: "Trivially within ability — no learning value; safe to automate or batch",
                TaskFit.IN_ZPD: "Learning zone: stretch task with guidance (scaffolded)",
                TaskFit.TOO_HARD: "Beyond reach even with guidance — teach first, then retry",
            }[fit],
        }

    # ------------------------------------------------------------------
    # Scaffolding with fading
    # ------------------------------------------------------------------

    def get_scaffold_level(
        self,
        agent: AgentRegistry,
        topic: Optional[str] = None,
        task_fit: Optional[TaskFit] = None,
    ) -> "ScaffoldAssignment":
        """Return the current scaffold for this agent (and topic).

        Fading rule: support decreases step-by-step with demonstrated topic
        mastery first, then overall confidence — never from FULL_GUIDANCE
        straight to INDEPENDENT.
        """
        mastery = self._get_mastery(agent)
        if topic is not None and mastery.get(topic, 0) >= MASTERY_THRESHOLD:
            # Topic mastered: fade by overall confidence
            progress = 3  # mastered -> at least checklist
        else:
            topic_progress = max(mastery.values(), default=0)
            progress = min(2, topic_progress)  # unmastered: cap at hints

        confidence = float(agent.confidence_score or 0.0)
        if confidence >= 0.40:
            progress = max(progress, 3)
        elif confidence >= 0.30:
            progress = max(progress, 2)
        elif confidence >= 0.20:
            progress = max(progress, 1)

        if task_fit is TaskFit.TOO_HARD:
            progress = 0  # hardest tasks get full guidance or get deferred
        if task_fit is TaskFit.TOO_EASY:
            progress = 3  # trivial tasks never carry scaffolds

        level = ScaffoldLevel.fade_order()[min(progress, 3)]
        return ScaffoldAssignment(level=level, topic=topic, framework=self, agent=agent)

    # ------------------------------------------------------------------
    # Mastery learning
    # ------------------------------------------------------------------

    def record_mastery_exposure(
        self,
        agent: AgentRegistry,
        topic: str,
        positive: bool,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record one exposure (success or mistake) for a topic.

        Mastery learning: only positive exposures count toward mastery;
        mistakes add a corrective entry instead of resetting progress
        (errors are information, not punishment).
        """
        from sqlalchemy.orm.attributes import flag_modified

        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        pedagogy = config.setdefault("pedagogy", {})
        mastery: Dict[str, int] = pedagogy.setdefault("mastery", {})
        history: List[Dict[str, Any]] = pedagogy.setdefault("mastery_history", [])
        history.append({
            "topic": topic,
            "positive": positive,
            "note": (note or "")[:500],
            "at": datetime.now(timezone.utc).isoformat(),
        })
        if len(history) > MAX_HISTORY:
            del history[:-MAX_HISTORY]

        if positive:
            mastery[topic] = mastery.get(topic, 0) + 1
        else:
            pedagogy.setdefault("corrections", []).append({
                "topic": topic, "note": note or "", "at": datetime.now(timezone.utc).isoformat(),
            })

        just_mastered = mastery.get(topic, 0) >= MASTERY_THRESHOLD
        config["pedagogy"] = pedagogy
        agent.configuration = config
        flag_modified(agent, "configuration")
        self.db.commit()

        return {
            "topic": topic,
            "exposures": mastery.get(topic, 0),
            "mastered": just_mastered or mastery.get(topic, 0) > MASTERY_THRESHOLD,
            "remaining": max(0, MASTERY_THRESHOLD - mastery.get(topic, 0)),
        }

    def get_mastery_report(self, agent: AgentRegistry) -> Dict[str, Any]:
        mastery = self._get_mastery(agent)
        return {
            "topics": dict(mastery),
            "mastered": [t for t, n in mastery.items() if n >= MASTERY_THRESHOLD],
            "in_progress": {t: n for t, n in mastery.items() if n < MASTERY_THRESHOLD},
            "threshold": MASTERY_THRESHOLD,
        }

    # ------------------------------------------------------------------
    # Grey-area judgment (banded, auditable, feedback-driven)
    # ------------------------------------------------------------------

    def judge_grey_area(
        self,
        agent: AgentRegistry,
        situation: str,
        action_complexity: int,
        estimated_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Decide how an agent should act in a grey area.

        NOT a rigid rule (which would block all growth) and NOT free
        discretion (which invites chaos): a calibrated band decides between
        asking the teacher, asking a human, or proceeding under logging —
        and the agent must articulate its rationale (articulation), which is
        stored with the decision for later reflection.
        """
        confidence = estimated_confidence if estimated_confidence is not None else float(agent.confidence_score or 0.0)

        if confidence < ASK_TEACHER_BELOW:
            decision = GreyAreaDecision.ASK_TEACHER
        elif confidence < ASK_HUMAN_BELOW:
            decision = GreyAreaDecision.ASK_HUMAN
        else:
            decision = GreyAreaDecision.PROCEED_LOGGED

        # Hard safety floor: actions above the agent's reachable complexity
        # never proceed regardless of confidence (grey ≠ unsafe).
        status = (agent.status or "student").lower()
        maturity_idx = _MATURITY_ORDER.index(status) if status in _MATURITY_ORDER else 0
        if action_complexity > maturity_idx + 2 and decision == GreyAreaDecision.PROCEED_LOGGED:
            decision = GreyAreaDecision.ASK_HUMAN

        decision_id = f"grey_{uuid.uuid4().hex[:10]}"
        from sqlalchemy.orm.attributes import flag_modified
        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        pedagogy = config.setdefault("pedagogy", {})
        pending = pedagogy.setdefault("pending_decisions", {})
        pending[decision_id] = {
            "situation": situation[:1000],
            "decision": decision.value,
            "confidence": round(confidence, 3),
            "action_complexity": action_complexity,
            "made_at": datetime.now(timezone.utc).isoformat(),
            "outcome": None,
        }
        config["pedagogy"] = pedagogy
        agent.configuration = config
        flag_modified(agent, "configuration")
        self.db.commit()

        return {
            "decision_id": decision_id,
            "decision": decision.value,
            "rationale": (
                f"confidence {confidence:.2f} in band '{decision.value}' "
                f"(bands: teacher<{ASK_TEACHER_BELOW}, human<{ASK_HUMAN_BELOW}, else logged-proceed)"
            ),
            "guidance": {
                GreyAreaDecision.ASK_TEACHER: "Consult the Atom meta agent before acting",
                GreyAreaDecision.ASK_HUMAN: "Create an HITL approval request before acting",
                GreyAreaDecision.PROCEED_LOGGED: "Proceed now; outcome review is mandatory",
            }[decision],
        }

    def record_decision_outcome(
        self,
        agent: AgentRegistry,
        decision_id: str,
        outcome: str,
        topic: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Close the feedback loop on a grey-area decision (reflection).

        Good outcomes count toward topic mastery; bad ones become corrective
        lessons — deliberate-practice style.
        """
        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        pedagogy = config.get("pedagogy", {})
        pending = pedagogy.get("pending_decisions", {})
        record = pending.pop(decision_id, None)
        if record is None:
            return {"status": "error", "reason": "decision_not_found"}
        record["outcome"] = outcome
        pedagogy.setdefault("decision_history", []).append(record)

        from sqlalchemy.orm.attributes import flag_modified
        config["pedagogy"] = pedagogy
        agent.configuration = config
        flag_modified(agent, "configuration")

        positive = outcome == "good"
        resolved_topic = topic or record.get("situation", "")[:60]
        mastery_result = self.record_mastery_exposure(agent, resolved_topic, positive, note=note)
        return {"status": "ok", "recorded_outcome": outcome, "mastery": mastery_result}

    # ------------------------------------------------------------------

    def _get_mastery(self, agent: AgentRegistry) -> Dict[str, int]:
        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        mastery = config.get("pedagogy", {}).get("mastery", {})
        return mastery if isinstance(mastery, dict) else {}


MAX_HISTORY = 100


class ScaffoldAssignment:
    """A concrete scaffold handed to the caller, with its instructions."""

    _INSTRUCTIONS = {
        ScaffoldLevel.FULL_GUIDANCE: (
            "Do not act yet. Request a worked demonstration from the teacher "
            "(atom_main) for this task, then attempt it under observation."
        ),
        ScaffoldLevel.HINTS: (
            "Attempt the task yourself; ask the teacher for hints if stuck. "
            "The teacher reviews the result."
        ),
        ScaffoldLevel.CHECKLIST: (
            "Proceed using your stored checklist for this topic; escalate "
            "only if a checklist item fails."
        ),
        ScaffoldLevel.INDEPENDENT: (
            "Proceed without support. The outcome will be reviewed and "
            "recorded against this topic's mastery."
        ),
    }

    def __init__(self, level: ScaffoldLevel, topic: Optional[str],
                 framework: PedagogicalFramework, agent: AgentRegistry):
        self.level = level
        self.topic = topic
        self.framework = framework
        self.agent = agent

    @property
    def instructions(self) -> str:
        return self._INSTRUCTIONS[self.level]
