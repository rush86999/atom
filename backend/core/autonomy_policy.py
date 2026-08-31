"""Per-user action-autonomy policy: which TOPICS of agent actions always
require a human in the loop, and which the agent handles autonomously once
its maturity tier allows.

Two modes per topic:
- ``human_always``  — the agent may only PROPOSE (HITL proposal + approval);
  even an autonomous hire never executes directly.
- ``auto_if_mature`` — governance decides: a mature-enough hire executes,
  an immature one proposes (and learns from the approval/correction).

Defaults follow blast radius: external sends (email) and external system
writes (CRM) default to human-always; internal surfaces (canvas, tasks)
default to auto-if-mature. Reads are never gated.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODE_HUMAN_ALWAYS = "human_always"
MODE_AUTO_IF_MATURE = "auto_if_mature"
_MODES = (MODE_HUMAN_ALWAYS, MODE_AUTO_IF_MATURE)

# topic -> (label, description, default_mode)
TOPICS: Dict[str, Dict[str, str]] = {
    "send_email": {
        "label": "Send email",
        "description": "Sending emails on your behalf (external, irreversible)",
        "default_mode": MODE_HUMAN_ALWAYS,
    },
    "crm_write": {
        "label": "CRM writes",
        "description": "Creating/updating leads, contacts, deals in connected CRMs",
        "default_mode": MODE_HUMAN_ALWAYS,
    },
    "task_create": {
        "label": "Create tasks",
        "description": "Creating tasks/reminders in your task tracker",
        "default_mode": MODE_AUTO_IF_MATURE,
    },
    "canvas_edit": {
        "label": "Canvas edits",
        "description": "Editing drafts and documents on canvases",
        "default_mode": MODE_AUTO_IF_MATURE,
    },
}


def list_topics(user_id: str, db: Any) -> List[Dict[str, str]]:
    """All topics with the user's effective mode (explicit row or default)."""
    from core.models import ActionAutonomyPolicy

    rows = {
        r.topic: r.mode
        for r in db.query(ActionAutonomyPolicy)
        .filter(ActionAutonomyPolicy.user_id == user_id)
        .all()
    }
    return [
        {
            "topic": topic,
            "label": meta["label"],
            "description": meta["description"],
            "default_mode": meta["default_mode"],
            "mode": rows.get(topic, meta["default_mode"]),
        }
        for topic, meta in TOPICS.items()
    ]


def get_effective_mode(db: Any, user_id: Optional[str], topic: str) -> str:
    """Effective mode for a topic: the user's explicit choice, else default."""
    from core.models import ActionAutonomyPolicy

    if topic not in TOPICS:
        return MODE_AUTO_IF_MATURE
    try:
        row = (
            db.query(ActionAutonomyPolicy)
            .filter(
                ActionAutonomyPolicy.user_id == user_id,
                ActionAutonomyPolicy.topic == topic,
            )
            .first()
        )
        if row is not None and row.mode in _MODES:
            return row.mode
    except Exception as e:
        logger.debug(f"autonomy policy lookup skipped: {e}")
    return TOPICS[topic]["default_mode"]


def set_mode(db: Any, user_id: str, topic: str, mode: str) -> bool:
    """Set the user's mode for a topic (upsert). Returns success."""
    from core.models import ActionAutonomyPolicy

    if topic not in TOPICS or mode not in _MODES:
        return False
    row = (
        db.query(ActionAutonomyPolicy)
        .filter(
            ActionAutonomyPolicy.user_id == user_id,
            ActionAutonomyPolicy.topic == topic,
        )
        .first()
    )
    if row is None:
        db.add(ActionAutonomyPolicy(user_id=user_id, topic=topic, mode=mode))
    else:
        row.mode = mode
    db.commit()
    return True
