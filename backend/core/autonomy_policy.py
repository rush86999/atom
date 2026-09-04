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

Gating (``gate_for_topic``) is the single mechanism both the runtime paths
and the Autonomy panel evaluate, so what the panel displays is exactly what
a turn enforces:

    outcome = mode(auto_if_mature) AND maturity(tier >= topic bar) AND trust(score >= threshold)

- maturity comes from AgentGovernanceService.can_perform_action on the
  topic's governance action (same complexity table the runtime uses).
- trust is the R8 skill-scoped score (capability_stats, verified-gated).
  It only bites when skill-scoped trust is enabled (flag, default OFF) —
  disabled means trust_ok=True so legacy behavior is unchanged.

Topics are also keyed to CANVAS types (``topics_for_canvas``) so the
Autonomy tab on a canvas leads with the topics that canvas's type actually
exercises (an email canvas → sends/CRM; every other surface → edits/tasks),
while still exposing the full general set.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODE_HUMAN_ALWAYS = "human_always"
MODE_AUTO_IF_MATURE = "auto_if_mature"
_MODES = (MODE_HUMAN_ALWAYS, MODE_AUTO_IF_MATURE)

OUTCOME_EXECUTE = "execute"
OUTCOME_PROPOSE = "propose"

# Trust at or above this clears autonomous execution when skill-scoped trust
# is enabled. Neutral no-evidence trust is 0.5 and the R8 laundering cap is
# 0.6, so unevidenced hires propose and earn autonomy through VERIFIED work.
AUTONOMY_TRUST_THRESHOLD = 0.6

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
    "email_attachment": {
        "label": "Email attachments",
        "description": "Attaching/removing files on email drafts and reading their contents",
        "default_mode": MODE_AUTO_IF_MATURE,
    },
    "pdf_canvas": {
        "label": "PDF documents",
        "description": "Editing PDF canvases (pages/merge) and approving them for send-out",
        "default_mode": MODE_AUTO_IF_MATURE,
    },
}

# Per-topic gate metadata. governance_action is the action_type fed to
# AgentGovernanceService.can_perform_action — the SAME lookup the runtime
# paths use, so the complexity table stays the single source of truth
# (send_email/update_contact/create_task → 3 SUPERVISED+, update_canvas →
# 2 INTERN+). min_maturity is the display fallback when governance is
# unavailable. trust_domain keys into capability_stats (exact-name direct
# evidence; no alias inflation for these).
TOPIC_GATES: Dict[str, Dict[str, Any]] = {
    "send_email": {
        "governance_action": "send_email",
        "min_maturity": "supervised",
        "trust_domain": "send_email",
    },
    "crm_write": {
        "governance_action": "update_contact",
        "min_maturity": "supervised",
        "trust_domain": "crm_write",
    },
    "task_create": {
        "governance_action": "create_task",
        "min_maturity": "supervised",
        "trust_domain": "task_create",
    },
    "canvas_edit": {
        "governance_action": "update_canvas",
        "min_maturity": "intern",
        "trust_domain": "canvas_edit",
    },
    "email_attachment": {
        "governance_action": "email_attachment_write",
        "min_maturity": "intern",
        "trust_domain": "email_attachment",
    },
    # Reuses the update_canvas complexity row (INTERN+): pdf page/merge edits
    # are reversible draft mutations, same blast radius as text-canvas edits.
    # Approval-to-send (lifecycle approve) carries its own higher bar in the
    # tool layer (SUPERVISED) on top of this topic gate.
    "pdf_canvas": {
        "governance_action": "update_canvas",
        "min_maturity": "intern",
        "trust_domain": "pdf_canvas",
    },
}

# canvas_type (lowercased) → topics that canvas type PRIMARILY exercises.
# Types not listed fall back to DEFAULT_CANVAS_TOPICS — every non-email
# surface is a document-ish canvas where edits and tasks are the point.
_CANVAS_TYPE_TOPICS: Dict[str, List[str]] = {
    "email": ["send_email", "email_attachment", "crm_write"],
    "mail": ["send_email", "email_attachment", "crm_write"],
    "orchestration": ["task_create", "canvas_edit"],
    "pdf": ["pdf_canvas", "task_create"],
}
DEFAULT_CANVAS_TOPICS = ["canvas_edit", "task_create"]


def topics_for_canvas(canvas_type: Optional[str]) -> List[str]:
    """Topics PRIMARY for a canvas type (the Autonomy tab's canvas section)."""
    normalized = (canvas_type or "").strip().lower()
    return _CANVAS_TYPE_TOPICS.get(normalized, list(DEFAULT_CANVAS_TOPICS))


def list_topics(
    user_id: str,
    db: Any,
    canvas_type: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """All topics with the user's effective mode (explicit row or default).

    When ``canvas_type`` is given, each topic carries ``canvas_relevant``
    (primary for that canvas type) so the Autonomy tab can lead with the
    canvas-specific set. When ``agent_id`` is given, each topic also carries
    ``gate`` — the live trust×maturity×mode outcome for that hire.
    """
    from core.models import ActionAutonomyPolicy

    rows = {
        r.topic: r.mode
        for r in db.query(ActionAutonomyPolicy)
        .filter(ActionAutonomyPolicy.user_id == user_id)
        .all()
    }
    canvas_primary = set(topics_for_canvas(canvas_type)) if canvas_type else set()
    topics: List[Dict[str, Any]] = []
    for topic, meta in TOPICS.items():
        entry: Dict[str, Any] = {
            "topic": topic,
            "label": meta["label"],
            "description": meta["description"],
            "default_mode": meta["default_mode"],
            "mode": rows.get(topic, meta["default_mode"]),
            "canvas_relevant": topic in canvas_primary,
        }
        if agent_id:
            entry["gate"] = gate_for_topic(db, user_id, topic, agent_id)
        topics.append(entry)
    return topics


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


def maturity_check(db: Any, agent_id: Optional[str], topic: str) -> Dict[str, Any]:
    """Governance maturity verdict for a topic's action (same lookup the
    runtime paths make). Fail-open (ok=True, unknown tier) when there is no
    hire or governance is unavailable — mirrors the runtime try/except
    convention so a governance hiccup degrades to the owner's mode choice,
    never to a spurious lockout."""
    meta = TOPIC_GATES.get(topic, {})
    out: Dict[str, Any] = {
        "known": False,
        "maturity_level": None,
        "required": meta.get("min_maturity"),
        "ok": True,
        "reason": None,
    }
    if not agent_id or topic not in TOPIC_GATES:
        return out
    try:
        from core.service_factory import ServiceFactory

        governance = ServiceFactory.get_governance_service(db)
        check = governance.can_perform_action(
            agent_id=agent_id, action_type=meta["governance_action"]
        )
        out["known"] = True
        out["maturity_level"] = (
            str(check.get("agent_status")).lower()
            if check.get("agent_status")
            else None
        )
        if check.get("required_status"):
            out["required"] = str(check["required_status"]).lower()
        out["ok"] = bool(check.get("allowed", True))
        out["reason"] = check.get("reason")
    except Exception as e:
        logger.debug(f"autonomy maturity check skipped: {e}")
    return out


def trust_check(db: Any, agent_id: Optional[str], topic: str) -> Dict[str, Any]:
    """Skill-scoped trust verdict for a topic (R8: verified-gated, per-skill,
    slow to gain / fast to lose). Neutral-pass while the flag is off or the
    hire is unknown — the same condition the runtime gate evaluates."""
    meta = TOPIC_GATES.get(topic, {})
    out: Dict[str, Any] = {
        "enabled": False,
        "trust": None,
        "threshold": float(meta.get("trust_threshold", AUTONOMY_TRUST_THRESHOLD)),
        "cold_start": None,
        "ok": True,
    }
    if not agent_id or topic not in TOPIC_GATES:
        return out
    try:
        from core.skill_scoped_trust import skill_scoped_trust_enabled

        if not skill_scoped_trust_enabled():
            return out
        from core.models import AgentRegistry
        from core.skill_scoped_trust import agent_domain_trust

        row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if row is None:
            return out
        trust, cold_start = agent_domain_trust(row, meta.get("trust_domain") or topic)
        out.update(
            {
                "enabled": True,
                "trust": trust,
                "cold_start": cold_start,
                "ok": trust >= out["threshold"],
            }
        )
    except Exception as e:
        logger.debug(f"autonomy trust check skipped: {e}")
    return out


def _gate_reason(
    label: str,
    mode_ok: bool,
    maturity: Dict[str, Any],
    trust: Dict[str, Any],
) -> str:
    if not mode_ok:
        return f"You asked to approve every {label.lower()} — the hire proposes only."
    if not maturity["ok"]:
        return (
            f"Maturity {maturity.get('maturity_level') or 'unknown'} is below the "
            f"{maturity.get('required')} tier {label.lower()} needs."
        )
    if not trust["ok"]:
        return (
            f"Trust {trust.get('trust'):.2f} is below the "
            f"{trust['threshold']:.2f} bar for autonomous {label.lower()}."
        )
    return f"Policy allows autonomy and the hire clears the {maturity.get('required')} bar — executes directly."


def gate_for_topic(
    db: Any,
    user_id: Optional[str],
    topic: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """The one gate: owner mode × governance maturity × skill-scoped trust.

    ``execute`` only when the owner allowed autonomy AND the hire's tier
    clears the topic's governance bar AND (when the trust flag is on) the
    hire's verified trust clears the threshold. Everything else proposes —
    the runtime paths enforce exactly this, so the panel is a projection of
    runtime behavior, not a parallel truth.
    """
    mode = get_effective_mode(db, user_id, topic)
    maturity = maturity_check(db, agent_id, topic)
    trust = trust_check(db, agent_id, topic)
    mode_ok = mode == MODE_AUTO_IF_MATURE
    execute = mode_ok and maturity["ok"] and trust["ok"]
    label = TOPICS.get(topic, {}).get("label", topic)
    return {
        "topic": topic,
        "mode": mode,
        "maturity": maturity,
        "trust": trust,
        "outcome": OUTCOME_EXECUTE if execute else OUTCOME_PROPOSE,
        "reason": _gate_reason(label, mode_ok, maturity, trust),
    }
