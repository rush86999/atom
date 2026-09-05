"""Per-user action-autonomy policy: which TOPICS of agent actions always
require a human in the loop, and which the agent handles autonomously once
its maturity tier allows.

Three modes per topic:
- ``human_always``          — the agent may only PROPOSE (HITL proposal +
  approval); even an autonomous hire never executes directly.
- ``auto_if_mature``        — governance decides: a mature-enough hire
  executes, an immature one proposes (and learns from the approval/
  correction).
- ``auto_until_corrected``  — like auto_if_mature, but the autonomy is
  EARNED and revocable: a human correction on the topic resets the hire's
  capability tier to student (``reset_autonomy_cycle``), so it proposes
  again until verified work re-graduates the capability through the
  5/20/50 ladder (``CapabilityGraduationService.record_usage``) and it
  reaches autonomy again. The cycle rides the per-capability tier already
  stored on the hire (``configuration.capability_maturities``) — no entry
  means the career tier decides, exactly as before.

Defaults follow blast radius: external sends (email) and external system
writes (CRM) default to human-always — the OWNER can move them to either
auto mode from the Autonomy panel (tenant preference); internal surfaces
(canvas, tasks) default to auto-if-mature. Reads are never gated.

Gating (``gate_for_topic``) is the single mechanism both the runtime paths
and the Autonomy panel evaluate, so what the panel displays is exactly what
a turn enforces:

    outcome = mode(auto_*) AND maturity(tier >= topic bar) AND trust(score >= threshold)
              AND cycle(not reset by a correction, until_corrected mode)

- maturity comes from AgentGovernanceService.can_perform_action on the
  topic's governance action (same complexity table the runtime uses).
- trust is the R8 skill-scoped score (capability_stats, verified-gated).
  It only bites when skill-scoped trust is enabled (flag, default OFF) —
  disabled means trust_ok=True so legacy behavior is unchanged.
- the cycle check only bites under auto_until_corrected.

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
MODE_AUTO_UNTIL_CORRECTED = "auto_until_corrected"
_MODES = (MODE_HUMAN_ALWAYS, MODE_AUTO_IF_MATURE, MODE_AUTO_UNTIL_CORRECTED)

OUTCOME_EXECUTE = "execute"
OUTCOME_PROPOSE = "propose"


def mode_allows_autonomy(mode: str) -> bool:
    """Both auto modes let a qualified hire execute; human_always never does."""
    return mode in (MODE_AUTO_IF_MATURE, MODE_AUTO_UNTIL_CORRECTED)

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

# proposal/correction payload action_type → autonomy topic. The correction
# reset (``reset_autonomy_cycle``) is called from the shared human-correction
# paths, which know the ACTION type, not the topic — this is the bridge.
# Explicit entries come LAST so they win over the governance-action reverse
# map (pdf_canvas shares update_canvas with canvas_edit; the shared action
# resolves to the legacy canvas_edit topic, while PDF proposals carry their
# own pdf_canvas_edit action type).
_TOPIC_BY_ACTION: Dict[str, str] = {
    meta["governance_action"]: topic for topic, meta in TOPIC_GATES.items()
}
_TOPIC_BY_ACTION.update(
    {
        "send_email": "send_email",
        "canvas_edit": "canvas_edit",
        "crm_write": "crm_write",
        "task_create": "task_create",
        "email_attachment": "email_attachment",
        "update_canvas": "canvas_edit",
        # HITL proposal action types
        "pdf_canvas_edit": "pdf_canvas",
        "pdf_canvas": "pdf_canvas",
    }
)


def topic_for_action(action_type: Any) -> Optional[str]:
    """The autonomy topic a proposal/correction action_type maps to (None
    when unknown — callers must not guess)."""
    if not action_type:
        return None
    return _TOPIC_BY_ACTION.get(str(action_type).strip().lower())


def autonomy_cycle(db: Any, agent_id: Optional[str], topic: str) -> Dict[str, Any]:
    """The EARNED-autonomy cycle for one hire and topic (consulted only in
    ``auto_until_corrected`` mode): CapabilityGraduationService keeps a
    per-capability tier next to the hire's career tier. A human correction
    resets that entry to student (``reset_autonomy_cycle``); verified work
    re-graduates it through the 5/20/50 ladder — the cycle the hire rides
    back to autonomy.

    NO entry for the topic → the career tier decides, exactly as in the
    other modes (legacy agents are unaffected; the entry only exists once
    the capability was earned or reset).
    """
    meta = TOPIC_GATES.get(topic, {})
    out: Dict[str, Any] = {
        "applicable": False,
        "reset": False,
        "tier": None,
        "required": meta.get("min_maturity"),
        "ok": True,
        "reason": None,
    }
    if not agent_id or topic not in TOPIC_GATES:
        return out
    try:
        from core.models import AgentRegistry

        row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if row is None:
            return out
        out["applicable"] = True
        cfg = getattr(row, "configuration", None)
        maturities = (
            cfg.get("capability_maturities") if isinstance(cfg, dict) else None
        )
        tier = (
            maturities.get(meta.get("trust_domain") or topic)
            if isinstance(maturities, dict)
            else None
        )
        if not isinstance(tier, str) or not tier:
            return out  # nothing earned/reset — career tier decides
        out["tier"] = tier
        ladder = ("student", "intern", "supervised", "autonomous")
        required = out["required"] or "intern"
        tier_idx = ladder.index(tier) if tier in ladder else 0
        req_idx = ladder.index(required) if required in ladder else 0
        out["ok"] = tier_idx >= req_idx
        out["reset"] = not out["ok"]
        if not out["ok"]:
            label = TOPICS.get(topic, {}).get("label", topic)
            out["reason"] = (
                f"A human correction reset the {label.lower()} autonomy cycle — "
                f"re-earned capability tier {tier} so far, needs {required} "
                f"again (verified work re-graduates it)."
            )
    except Exception as e:
        logger.debug(f"autonomy cycle check skipped: {e}")
    return out


def reset_autonomy_cycle(db: Any, agent_id: Optional[str], topic: str,
                         reason: str = "human correction") -> bool:
    """A human correction resets the hire's EARNED autonomy for one topic:
    the capability tier drops to student, so ``auto_until_corrected`` topics
    propose again until verified work re-graduates the capability. No-op for
    unknown topics/hires; other modes never consult the entry, so resetting
    under human_always/auto_if_mature is inert bookkeeping that still makes
    the correction auditable."""
    if not agent_id or topic not in TOPIC_GATES:
        return False
    try:
        from core.capability_graduation_service import CapabilityGraduationService

        CapabilityGraduationService(db).reset_maturity(
            agent_id, TOPIC_GATES[topic].get("trust_domain") or topic,
            reason=reason,
        )
        logger.info(
            "autonomy cycle reset: %s lost earned %s autonomy (%s)",
            agent_id, topic, reason,
        )
        return True
    except Exception as e:
        logger.debug(f"autonomy cycle reset skipped: {e}")
        return False


# canvas_type (lowercased) → topics that canvas type PRIMARILY exercises.# Types not listed fall back to DEFAULT_CANVAS_TOPICS — every non-email
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
    cycle: Optional[Dict[str, Any]] = None,
) -> str:
    if not mode_ok:
        return f"You asked to approve every {label.lower()} — the hire proposes only."
    if cycle is not None and not cycle["ok"]:
        return cycle["reason"] or (
            f"A human correction reset the {label.lower()} autonomy cycle — "
            f"the hire proposes until it re-earns autonomy."
        )
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
    if cycle is not None:
        return (
            f"Policy allows autonomy, the hire clears the {maturity.get('required')} "
            f"bar, and no correction has reset the cycle — executes directly."
        )
    return f"Policy allows autonomy and the hire clears the {maturity.get('required')} bar — executes directly."


def gate_for_topic(
    db: Any,
    user_id: Optional[str],
    topic: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """The one gate: owner mode × governance maturity × skill-scoped trust
    (× correction cycle under ``auto_until_corrected``).

    ``execute`` only when the owner allowed autonomy AND the hire's tier
    clears the topic's governance bar AND (when the trust flag is on) the
    hire's verified trust clears the threshold AND — in until-corrected
    mode — no human correction has reset the hire's earned cycle. Everything
    else proposes — the runtime paths enforce exactly this, so the panel is
    a projection of runtime behavior, not a parallel truth.
    """
    mode = get_effective_mode(db, user_id, topic)
    maturity = maturity_check(db, agent_id, topic)
    trust = trust_check(db, agent_id, topic)
    mode_ok = mode_allows_autonomy(mode)
    cycle = (
        autonomy_cycle(db, agent_id, topic)
        if mode == MODE_AUTO_UNTIL_CORRECTED
        else None
    )
    execute = (
        mode_ok
        and maturity["ok"]
        and trust["ok"]
        and (cycle is None or cycle["ok"])
    )
    label = TOPICS.get(topic, {}).get("label", topic)
    return {
        "topic": topic,
        "mode": mode,
        "maturity": maturity,
        "trust": trust,
        "cycle": cycle,
        "outcome": OUTCOME_EXECUTE if execute else OUTCOME_PROPOSE,
        "reason": _gate_reason(label, mode_ok, maturity, trust, cycle),
    }


# The tier statuses a hire can hold while actively working. Non-tier states
# (paused/stopped/deprecated/deleted) are not steering canvases, so they are
# not gated (same convention as the governance tier ladder).
_TIER_STATUSES = ("student", "intern", "supervised", "autonomous")


def tenant_gate_for_topic(db: Any, topic: str,
                          tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """gate_for_topic aggregated over every active hire in the tenant — the
    projection the playbook evidence latch evaluates (a playbook is
    install-wide, so its no-human-gating question is fleet-shaped, not
    per-hire).

    Same contract as the action gate, one scope up: a tenant-wide rule
    promotes without a human click only when the topic's mode allows
    autonomy AND every hire that would follow it clears the same
    maturity×trust bar the runtime applies to their actions. One hire below
    the bar — or a human_always topic (external blast radius) — keeps the
    human approval gate, exactly like that hire's own actions would propose.

    Mode resolves from the topic defaults: the sleep-time job has no single
    owner, so the install-wide DEFAULT contract is what applies (external
    sends/CRM stay human_always unless the default itself changes).
    """
    mode = get_effective_mode(db, None, topic)
    label = TOPICS.get(topic, {}).get("label", topic)
    out: Dict[str, Any] = {
        "topic": topic,
        "mode": mode,
        "hires": 0,
        "outcome": OUTCOME_PROPOSE,
        "blocking": [],
        "reason": None,
    }
    if mode != MODE_AUTO_IF_MATURE:
        out["reason"] = (
            f"{label} is human_always — external blast radius keeps the "
            f"approval gate on tenant-wide rules."
        )
        return out

    from core.models import AgentRegistry

    q = (
        db.query(AgentRegistry)
        .filter(AgentRegistry.status.in_(_TIER_STATUSES))
        .filter(AgentRegistry.enabled.is_(True))
    )
    if tenant_id:
        q = q.filter(AgentRegistry.tenant_id == tenant_id)
    hires = q.all()
    out["hires"] = len(hires)
    for hire in hires:
        gate = gate_for_topic(db, None, topic, hire.id)
        if gate["outcome"] != OUTCOME_EXECUTE:
            out["blocking"].append(
                {"agent_id": hire.id, "name": hire.name, "reason": gate["reason"]}
            )
    if out["blocking"]:
        names = ", ".join(b["name"] or b["agent_id"] for b in out["blocking"][:3])
        out["reason"] = (
            f"{len(out['blocking'])} of {len(hires)} hires still propose "
            f"{label.lower()} ({names}) — the rule stays human-gated with them."
        )
    else:
        out["reason"] = (
            f"All {len(hires)} active hires clear the {label.lower()} bar — "
            f"validated rules on this topic promote without a human click."
            if hires else
            f"No active hires to gate {label.lower()} — evidence decides."
        )
    out["outcome"] = OUTCOME_EXECUTE if not out["blocking"] else OUTCOME_PROPOSE
    return out
