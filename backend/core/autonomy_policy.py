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
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

MODE_HUMAN_ALWAYS = "human_always"
MODE_AUTO_IF_MATURE = "auto_if_mature"
MODE_AUTO_UNTIL_CORRECTED = "auto_until_corrected"
_MODES = (MODE_HUMAN_ALWAYS, MODE_AUTO_IF_MATURE, MODE_AUTO_UNTIL_CORRECTED)

OUTCOME_EXECUTE = "execute"
OUTCOME_PROPOSE = "propose"

# Never-autonomous task-basket outcomes (additive to topic outcomes above).
NEVER_OUTCOME_REVIEW = "review"
NEVER_OUTCOME_UNAFFECTED = "unaffected"
NEVER_DIMENSIONS = ("difficulty", "category", "domain")
NEVER_RULE_MAX_NAMES = 5
NEVER_RULE_MAX_VALUES = 20
# Only effectful actions are execution. Reads (governance complexity 1) are
# not side effects and keep their pre-existing behavior.
NEVER_EFFECTFUL_MIN_COMPLEXITY = 2


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
    "integration_ingest": {
        "label": "Integration ingestion",
        "description": (
            "Pulling content from connected integrations into Atom memory "
            "(drives, CRM, tickets, inventory, chat, …)"
        ),
        "default_mode": MODE_AUTO_IF_MATURE,
    },
    "pdf_canvas": {
        "label": "PDF documents",
        "description": "Editing PDF canvases (pages/merge) and approving them for send-out",
        "default_mode": MODE_AUTO_IF_MATURE,
    },
    "canvas_assessment": {
        "label": "Substantive assessment",
        "description": (
            "Acting on model-dependent decisions for a user canvas. Default "
            "human_always until the serving configuration is qualified and the "
            "owner grants this topic autonomy."
        ),
        "default_mode": MODE_HUMAN_ALWAYS,
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
    # Reversible memory write (idempotent, source-scoped): the same bar as
    # email-attachment ingestion, one knob for every integration family.
    "integration_ingest": {
        "governance_action": "integration_ingest_write",
        "min_maturity": "intern",
        "trust_domain": "integration_ingest",
    },
    "canvas_assessment": {
        "governance_action": "update_canvas",
        "min_maturity": "supervised",
        "trust_domain": "canvas_assessment",
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
    the capability tier drops to student and a new verified-success baseline
    is bound at the reset, so ``auto_until_corrected`` topics propose again
    until POST-correction verified work re-graduates through the normal
    5/20/50 ladder (lifetime counters stay auditable but cannot be reused).
    Returns False for unknown topics/hires or when the reset could not be
    persisted. Other modes never consult the entry, so resetting under
    human_always/auto_if_mature remains inert bookkeeping."""
    if not agent_id or topic not in TOPIC_GATES:
        return False
    try:
        from core.capability_graduation_service import CapabilityGraduationService

        changed = CapabilityGraduationService(db).reset_maturity(
            agent_id, TOPIC_GATES[topic].get("trust_domain") or topic,
            reason=reason,
        )
        if not changed:
            # Unknown hire or a contended CAS: the correction was not
            # persisted, so do not report success.
            logger.debug(
                "autonomy cycle reset not applied for %s:%s", agent_id, topic)
            return False
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


def trust_calibration_check(db: Any) -> Dict[str, Any]:
    """Runtime authorization verdict from the trust-calibration ledger.

    This is the consumer the automation ledger was missing: when the
    gateway is enabled, autonomy relaxation is authorized ONLY while the
    latest durable action is an applied ``enable``. A subsequent
    certification regression writes a ``revoked`` row and this check turns
    false immediately — there is no cached grant and no process-local state,
    so a resumed wait or a restarted worker re-reads the same answer.

    Flag off (the default) is neutral-pass: the legacy gate behavior is
    unchanged. Flag on with no certified ledger entry proposes instead of
    executing, matching the documented "relax only after certification"
    contract.
    """
    out: Dict[str, Any] = {
        "enabled": False,
        "resolved": None,
        "ok": True,
        "reason": None,
    }
    try:
        from core.trust_calibration.gateway import enabled as _tc_enabled

        if not _tc_enabled():
            return out
        from core.trust_calibration.automation import resolved_trust_enforce

        out["enabled"] = True
        resolved = bool(resolved_trust_enforce(db))
        out["resolved"] = resolved
        out["ok"] = resolved
        if not resolved:
            out["reason"] = (
                "Trust calibration has not certified autonomous relaxation "
                "(or a verified regression revoked it) — the hire proposes "
                "until certification passes again."
            )
    except Exception as e:  # noqa: BLE001 — a ledger outage must not crash a turn
        logger.debug(f"trust calibration check skipped: {e}")
    return out


def revocation_check(db: Any, agent_id: Optional[str], topic: str) -> Dict[str, Any]:
    """Runtime revocation for a topic, written by verified regressions.

    ``CapabilityGraduationService.record_usage`` records a persisted
    ``autonomy_revocations`` entry when an externally verified failure hits a
    capability that had verified successes. The gate must refuse that topic
    until the hire re-earns it — a stored ledger row alone is not revocation.
    """
    out: Dict[str, Any] = {
        "applicable": False,
        "revoked": False,
        "ok": True,
        "reason": None,
        "detail": None,
    }
    if not agent_id or topic not in TOPIC_GATES:
        return out
    try:
        from core.models import AgentRegistry

        row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if row is None:
            return out
        config = getattr(row, "configuration", None)
        if not isinstance(config, dict):
            return out
        revocations = config.get("autonomy_revocations") or {}
        key = TOPIC_GATES[topic].get("trust_domain") or topic
        detail = revocations.get(key) or revocations.get(topic)
        if not detail:
            return out
        out.update(
            applicable=True,
            revoked=True,
            ok=False,
            reason=(
                detail.get("reason")
                if isinstance(detail, dict) else str(detail)
            ) or "verified_regression",
            detail=detail if isinstance(detail, dict) else {"reason": detail},
        )
    except Exception as e:  # noqa: BLE001 — fail CLOSED, never grant
        logger.warning("autonomy revocation check unavailable: %s", e)
        out.update(
            applicable=True,
            revoked=False,
            ok=False,
            unavailable=True,
            reason="authority_store_unavailable",
            detail={"error": f"{type(e).__name__}: {e}"[:200]},
        )
    return out


class NeverRuleValidationError(ValueError):
    """A rule body is malformed or names an unsupported dimension value."""


class NeverRuleNotFound(LookupError):
    """No rule with this id belongs to the authenticated owner."""


class NeverRuleConflict(RuntimeError):
    """An optimistic-concurrency revision no longer matches the row."""

    def __init__(self, current_revision: int):
        super().__init__("rule_revision_conflict")
        self.current_revision = int(current_revision)


def _normalize_dimension_values(dimension: str, values: Any) -> List[str]:
    from core.task_classification import (
        CATEGORY_VALUES,
        DIFFICULTY_VALUES,
        is_valid_domain_slug,
    )

    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        raise NeverRuleValidationError(
            f"match.{dimension} must be a list of strings")
    cleaned: List[str] = []
    for raw in values:
        text = str(raw or "").strip().lower()
        if not text:
            continue
        if dimension == "difficulty" and text not in DIFFICULTY_VALUES:
            raise NeverRuleValidationError(
                f"unknown difficulty '{text}' (expected one of "
                f"{', '.join(DIFFICULTY_VALUES)})")
        if dimension == "category" and text not in CATEGORY_VALUES:
            raise NeverRuleValidationError(
                f"unknown category '{text}' (expected one of "
                f"{', '.join(CATEGORY_VALUES)})")
        if dimension == "domain" and not is_valid_domain_slug(text):
            raise NeverRuleValidationError(
                f"invalid domain slug '{text}'")
        if text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= NEVER_RULE_MAX_VALUES:
            break
    return cleaned


def normalize_never_match(match: Any) -> Dict[str, List[str]]:
    """Validate/normalize rule dimensions.

    All specified dimensions are ANDed; values inside one dimension are
    alternatives (OR). At least one non-empty dimension is required.
    """
    if match is None:
        raise NeverRuleValidationError("match is required")
    if not isinstance(match, Mapping):
        raise NeverRuleValidationError("match must be an object")
    unknown = set(match) - set(NEVER_DIMENSIONS)
    if unknown:
        raise NeverRuleValidationError(
            f"unknown match dimension(s): {', '.join(sorted(unknown))}")
    normalized: Dict[str, List[str]] = {}
    for dimension in NEVER_DIMENSIONS:
        values = _normalize_dimension_values(dimension, match.get(dimension))
        if values:
            normalized[dimension] = values
    if not normalized:
        raise NeverRuleValidationError(
            "match must specify at least one non-empty difficulty, "
            "category, or domain")
    return normalized


def _rule_scope_matches(rule: Any, tenant_id: Optional[str],
                        workspace_id: Optional[str]) -> bool:
    """NULL scope is the Personal/default scope.

    A non-null rule scope is narrowed further only when the runtime supplies
    the corresponding scope. When the runtime has no scope value we cannot
    prove the rule inapplicable, so the rule stays eligible (same user only).
    """
    rule_tenant = getattr(rule, "tenant_id", None)
    rule_workspace = getattr(rule, "workspace_id", None)
    # "default" is the Personal edition's unnamed scope, equivalent to NULL
    # for narrowing purposes: it cannot prove the rule inapplicable.
    runtime_tenant = (
        None if str(tenant_id or "").strip().lower() in ("", "default")
        else tenant_id)
    runtime_workspace = (
        None if str(workspace_id or "").strip().lower() in ("", "default")
        else workspace_id)
    if rule_tenant and runtime_tenant and str(
            rule_tenant) != str(runtime_tenant):
        return False
    if rule_workspace and runtime_workspace and str(
            rule_workspace) != str(runtime_workspace):
        return False
    return True


def _serialize_never_rule(rule: Any) -> Dict[str, Any]:
    try:
        match = normalize_never_match(getattr(rule, "match_json", None))
    except Exception:
        # Corrupt persisted configuration is surfaced as-is (empty) and is
        # treated as potential at evaluation; it is never silently dropped.
        match = {}
    def _iso(value: Any) -> Optional[str]:
        return value.isoformat() if hasattr(value, "isoformat") else (
            str(value) if value else None)
    return {
        "id": str(getattr(rule, "id", "")),
        "name": str(getattr(rule, "name", "") or ""),
        "enabled": bool(getattr(rule, "enabled", False)),
        "match": match,
        "scope": {
            "user_id": getattr(rule, "user_id", None),
            "workspace_id": getattr(rule, "workspace_id", None),
            "tenant_id": getattr(rule, "tenant_id", None),
        },
        "revision": int(getattr(rule, "revision", 1) or 1),
        "created_at": _iso(getattr(rule, "created_at", None)),
        "updated_at": _iso(getattr(rule, "updated_at", None)),
    }


def list_never_rules(
    db: Any,
    user_id: Optional[str],
    *,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    enabled_only: bool = False,
) -> List[Dict[str, Any]]:
    """All rules owned by ``user_id`` in the applicable scope.

    API/list views pass no scope so the owner can edit every rule; runtime
    authorization passes the task's scope. Cross-user reads are impossible:
    ``user_id`` is a required filter, with no fallback to another owner.
    """
    if not user_id:
        return []
    from core.models import ActionAutonomyRule

    query = db.query(ActionAutonomyRule).filter(
        ActionAutonomyRule.user_id == str(user_id))
    if enabled_only:
        query = query.filter(ActionAutonomyRule.enabled.is_(True))
    rows = query.order_by(ActionAutonomyRule.created_at,
                          ActionAutonomyRule.id).all()
    return [
        _serialize_never_rule(row)
        for row in rows
        if _rule_scope_matches(row, tenant_id, workspace_id)
    ]


def _load_enabled_never_rows(
    db: Any,
    user_id: Optional[str],
    *,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> List[Any]:
    if not user_id:
        return []
    from core.models import ActionAutonomyRule

    rows = (
        db.query(ActionAutonomyRule)
        .filter(
            ActionAutonomyRule.user_id == str(user_id),
            ActionAutonomyRule.enabled.is_(True),
        )
        .order_by(ActionAutonomyRule.created_at, ActionAutonomyRule.id)
        .all()
    )
    return [
        row for row in rows
        if _rule_scope_matches(row, tenant_id, workspace_id)
    ]


_NEVER_CLEARANCE_TOKEN = object()
NEVER_CLEARANCE_CONTEXT_KEY = "_never_autonomous_clearance"


def grant_never_autonomous_clearance(context: Any, decision: Any) -> None:
    """Mark ONE execution as human-approved for the matched rules.

    The value carries a process-local opaque object, so a JSON request body
    or model tool argument can never forge clearance. It is per-execution
    state, not a rule mutation and not a durable blanket waiver.
    """
    if not isinstance(context, dict) or not isinstance(decision, Mapping):
        return
    if decision.get("outcome") != NEVER_OUTCOME_REVIEW:
        return
    context[NEVER_CLEARANCE_CONTEXT_KEY] = {
        "token": _NEVER_CLEARANCE_TOKEN,
        "rule_ids": list(decision.get("rule_ids") or []),
    }


def has_never_autonomous_clearance(
    context: Any, required_rule_ids: Any = None,
) -> bool:
    if not isinstance(context, Mapping):
        return False
    value = context.get(NEVER_CLEARANCE_CONTEXT_KEY)
    if not (isinstance(value, Mapping)
            and value.get("token") is _NEVER_CLEARANCE_TOKEN):
        return False
    required = {
        str(rule_id) for rule_id in (required_rule_ids or []) if rule_id
    }
    if not required:
        return True
    cleared = {str(rule_id) for rule_id in value.get("rule_ids") or []}
    return required.issubset(cleared)


def invalidate_never_autonomous_cache(*_args: Any, **_kwargs: Any) -> None:
    """Invalidation hook for any process-local memo.

    Runtime authorization deliberately reads the durable rows afresh (the
    small indexed query is cheaper than a stale security decision), so there
    is no long-lived policy cache to clear. Writes call this hook anyway so a
    future memo cannot silently shadow a durable edit.
    """
    return None


def create_never_rule(
    db: Any,
    user_id: str,
    *,
    name: str,
    match: Any,
    enabled: bool = True,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    from core.models import ActionAutonomyRule

    clean_name = str(name or "").strip()
    if not clean_name or len(clean_name) > 120:
        raise NeverRuleValidationError(
            "name must be 1-120 characters")
    clean_match = normalize_never_match(match)
    row = ActionAutonomyRule(
        user_id=str(user_id),
        tenant_id=str(tenant_id) if tenant_id else None,
        workspace_id=str(workspace_id) if workspace_id else None,
        name=clean_name,
        enabled=bool(enabled),
        match_json=clean_match,
        revision=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_never_autonomous_cache(user_id=user_id)
    return _serialize_never_rule(row)


def update_never_rule(
    db: Any,
    user_id: str,
    rule_id: str,
    *,
    name: str,
    match: Any,
    enabled: bool = True,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    from core.models import ActionAutonomyRule

    row = (
        db.query(ActionAutonomyRule)
        .filter(
            ActionAutonomyRule.id == str(rule_id),
            ActionAutonomyRule.user_id == str(user_id),
        )
        .first()
    )
    if row is None:
        raise NeverRuleNotFound(rule_id)
    if (expected_revision is not None
            and int(expected_revision) != int(row.revision or 1)):
        raise NeverRuleConflict(int(row.revision or 1))
    clean_name = str(name or "").strip()
    if not clean_name or len(clean_name) > 120:
        raise NeverRuleValidationError("name must be 1-120 characters")
    clean_match = normalize_never_match(match)
    row.name = clean_name
    row.enabled = bool(enabled)
    row.match_json = clean_match
    row.revision = int(row.revision or 1) + 1
    db.commit()
    db.refresh(row)
    invalidate_never_autonomous_cache(user_id=user_id)
    return _serialize_never_rule(row)


def delete_never_rule(db: Any, user_id: str, rule_id: str) -> bool:
    from core.models import ActionAutonomyRule

    row = (
        db.query(ActionAutonomyRule)
        .filter(
            ActionAutonomyRule.id == str(rule_id),
            ActionAutonomyRule.user_id == str(user_id),
        )
        .first()
    )
    if row is None:
        raise NeverRuleNotFound(rule_id)
    db.delete(row)
    db.commit()
    invalidate_never_autonomous_cache(user_id=user_id)
    return True


def _action_complexity(action_type: Optional[str]) -> Optional[int]:
    if not action_type:
        return None
    try:
        from core.agent_governance_service import AgentGovernanceService

        action = str(action_type).strip().lower()
        # Task-lifecycle read classes mutate no external system.
        if action in ("retrieve", "present", "calculate", "stop"):
            return 1
        if action in AgentGovernanceService.ACTION_COMPLEXITY:
            return int(AgentGovernanceService.ACTION_COMPLEXITY[action])
        matches = [
            level for name, level in
            AgentGovernanceService.ACTION_COMPLEXITY.items()
            if name in action
        ]
        return max(matches) if matches else 2
    except Exception as exc:  # noqa: BLE001 — unknown is effectful/fail-closed
        logger.debug("action complexity lookup skipped: %s", exc)
        return None


def _match_rule_dimensions(
    match: Mapping[str, List[str]], profile: Any,
) -> tuple:
    """Return (state, missing_dimensions) for one normalized rule."""
    missing: List[str] = []
    for dimension in NEVER_DIMENSIONS:
        alternatives = match.get(dimension) or []
        if not alternatives:
            continue
        task_value = getattr(profile, dimension, None) if profile else None
        if not task_value:
            missing.append(dimension)
            continue
        if str(task_value).strip().lower() not in alternatives:
            return "nonmatch", missing
    return ("potential" if missing else "match"), missing


def evaluate_never_autonomous(
    db: Any,
    user_id: Optional[str],
    task_profile: Any = None,
    *,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    action_type: Optional[str] = None,
    action_complexity: Optional[int] = None,
) -> Dict[str, Any]:
    """Evaluate the owner's enabled never-autonomous baskets.

    This is the single matching algorithm used by the topic gate, governance
    dispatch, the assignment re-check and the MCP guard. It is independent of
    agent maturity/graduation/trust/model/route state.

    Missing metadata is not a wildcard: if the profile (or a dimension a rule
    constrains) is unavailable, the rule is a **potential** match and review
    is required. Only a present, trusted value can prove a nonmatch.
    """
    from core.task_classification import is_trusted_task_profile

    complexity = (
        int(action_complexity) if action_complexity is not None
        else _action_complexity(action_type)
    )
    out: Dict[str, Any] = {
        "applicable": False,
        "matched": False,
        "potential": False,
        "outcome": NEVER_OUTCOME_UNAFFECTED,
        "rule_ids": [],
        "rule_names": [],
        "reason": None,
        "profile": None,
        "metadata_state": "not_required",
        "action_complexity": complexity,
        "error": None,
    }
    # Reads are not execution and keep their prior behavior.
    if complexity is not None and complexity < NEVER_EFFECTFUL_MIN_COMPLEXITY:
        return out

    profile = task_profile if is_trusted_task_profile(task_profile) else None
    resolved_user_id = user_id or (
        getattr(profile, "owner_user_id", None) if profile else None)
    try:
        rows = _load_enabled_never_rows(
            db, resolved_user_id, tenant_id=tenant_id,
            workspace_id=workspace_id)
    except Exception as exc:  # noqa: BLE001 — configured policy fails CLOSED
        # A store that has never been provisioned cannot contain a configured
        # rule (fresh installs create it via create_all, PostgreSQL via the
        # additive migration). Treat only that exact absence as "no policy";
        # every other read failure is a fail-closed policy outage.
        _error_text = str(exc).lower()
        if ("action_autonomy_rules" in _error_text
                and ("no such table" in _error_text
                     or "does not exist" in _error_text)):
            out["metadata_state"] = "policy_store_absent"
            return out
        logger.warning("never-autonomous policy unavailable: %s", exc)
        out.update(
            applicable=True,
            matched=False,
            potential=True,
            outcome=NEVER_OUTCOME_REVIEW,
            metadata_state="policy_unavailable",
            error=f"{type(exc).__name__}: {exc}"[:200],
            reason=(
                "Never-autonomous policy could not be evaluated "
                f"({type(exc).__name__}); human review is required."),
        )
        return out

    if not rows:
        return out

    out["applicable"] = True
    if profile is not None:
        out["profile"] = profile.as_dict()
        out["metadata_state"] = (
            "available" if not profile.missing_dimensions()
            else "partial")
    elif task_profile is None:
        out["metadata_state"] = "missing"
    else:
        out["metadata_state"] = "untrusted"

    definite: List[Dict[str, Any]] = []
    potential: List[Dict[str, Any]] = []
    missing_union: List[str] = []
    for row in rows:
        try:
            match = normalize_never_match(getattr(row, "match_json", None))
        except Exception as exc:  # noqa: BLE001 — corrupt rule fails CLOSED
            potential.append({
                "id": str(getattr(row, "id", "")),
                "name": str(getattr(row, "name", "") or "unreadable rule"),
                "invalid": True,
                "error": str(exc)[:120],
            })
            continue
        state, missing = _match_rule_dimensions(match, profile)
        if state == "nonmatch":
            continue
        entry = {
            "id": str(getattr(row, "id", "")),
            "name": str(getattr(row, "name", "") or ""),
        }
        if state == "match":
            definite.append(entry)
        else:
            potential.append(entry)
            for dimension in missing:
                if dimension not in missing_union:
                    missing_union.append(dimension)

    selected = definite or potential
    if not selected:
        return out

    rule_ids = [entry["id"] for entry in selected]
    rule_names = [entry["name"] for entry in selected if entry.get("name")]
    out.update(
        matched=True,
        potential=bool(potential) and not definite,
        outcome=NEVER_OUTCOME_REVIEW,
        rule_ids=rule_ids,
        rule_names=rule_names[:NEVER_RULE_MAX_NAMES],
    )
    names = ", ".join(f"“{name}”" for name in out["rule_names"]) or "rule"
    if definite:
        out["reason"] = (
            f"Never-autonomous {names} matched this task — "
            "a human must approve this execution.")
    else:
        missing_text = (
            ", ".join(missing_union) if missing_union else "task metadata")
        out["reason"] = (
            f"Never-autonomous {names} may apply, but {missing_text} "
            "is unavailable/untrusted — a human must review this execution.")
    return out


def never_autonomous_diagnostics(
    db: Any,
    user_id: Optional[str],
    *,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Read-only ceiling projection for existing qualification diagnostics."""
    rules = list_never_rules(
        db, user_id, tenant_id=tenant_id, workspace_id=workspace_id,
        enabled_only=True)
    return {
        "career_level": None,  # caller fills from AgentRegistry.status
        "scope": "user",
        "never_autonomous_rules": [
            {"id": rule["id"], "name": rule["name"], "enabled": True}
            for rule in rules
        ],
        "note": (
            "Career graduation is agent-wide; these task baskets still "
            "require human review and do not demote unrelated tasks."),
    }


def _gate_reason(
    label: str,
    mode_ok: bool,
    maturity: Dict[str, Any],
    trust: Dict[str, Any],
    cycle: Optional[Dict[str, Any]] = None,
    calibration: Optional[Dict[str, Any]] = None,
    revocation: Optional[Dict[str, Any]] = None,
    never: Optional[Dict[str, Any]] = None,
) -> str:
    if revocation is not None and not revocation["ok"]:
        if revocation.get("unavailable"):
            return (
                f"Authority state could not be checked "
                f"({revocation.get('reason')}) — the hire proposes instead of "
                f"acting on {label.lower()}."
            )
        return (
            f"{label} autonomy was revoked after a verified regression "
            f"({revocation.get('reason')}); the hire must re-earn it."
        )
    if never is not None and never.get("outcome") == NEVER_OUTCOME_REVIEW:
        return never.get("reason") or (
            "A never-autonomous task rule matched this action — a human "
            "must approve this execution.")
    if not mode_ok:
        return f"You asked to approve every {label.lower()} — the hire proposes only."
    if cycle is not None and not cycle["ok"]:
        return cycle["reason"] or (
            f"A human correction reset the {label.lower()} autonomy cycle — "
            f"the hire proposes until it re-earns autonomy."
        )
    if calibration is not None and not calibration["ok"]:
        return calibration["reason"] or (
            f"Trust calibration does not authorize autonomous "
            f"{label.lower()} right now — the hire proposes."
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
    *,
    task_profile: Any = None,
) -> Dict[str, Any]:
    """The one gate: owner mode × governance maturity × skill-scoped trust
    (× correction cycle under ``auto_until_corrected``) × never-autonomous
    task baskets.

    ``execute`` only when the owner allowed autonomy AND the hire's tier
    clears the topic's governance bar AND (when the trust flag is on) the
    hire's verified trust clears the threshold AND — in until-corrected
    mode — no human correction has reset the hire's earned cycle AND no
    enabled never-autonomous basket matches the task. Everything else
    proposes — the runtime paths enforce exactly this, so the panel is a
    projection of runtime behavior, not a parallel truth.

    ``task_profile`` is the server-built profile for this execution. When
    omitted, the profile bound for the run (``core.task_classification``)
    is used; a missing profile only affects owners who configured rules.
    """
    from core.task_classification import current_task_profile

    mode = get_effective_mode(db, user_id, topic)
    maturity = maturity_check(db, agent_id, topic)
    trust = trust_check(db, agent_id, topic)
    revocation = revocation_check(db, agent_id, topic)
    mode_ok = mode_allows_autonomy(mode)
    cycle = (
        autonomy_cycle(db, agent_id, topic)
        if mode == MODE_AUTO_UNTIL_CORRECTED
        else None
    )
    calibration = trust_calibration_check(db)
    resolved_profile = (
        task_profile if task_profile is not None else current_task_profile())
    never = evaluate_never_autonomous(
        db,
        user_id,
        resolved_profile,
        action_type=TOPIC_GATES.get(topic, {}).get("governance_action"),
    )
    execute = (
        mode_ok
        and maturity["ok"]
        and trust["ok"]
        and (cycle is None or cycle["ok"])
        and calibration["ok"]
        and revocation["ok"]
        and never["outcome"] != NEVER_OUTCOME_REVIEW
    )
    label = TOPICS.get(topic, {}).get("label", topic)
    return {
        "topic": topic,
        "mode": mode,
        "maturity": maturity,
        "trust": trust,
        "cycle": cycle,
        "calibration": calibration,
        "revocation": revocation,
        "never_autonomous": never,
        "outcome": OUTCOME_EXECUTE if execute else OUTCOME_PROPOSE,
        "reason": _gate_reason(
            label, mode_ok, maturity, trust, cycle, calibration, revocation,
            never),
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
