"""Role-template registry — training Phase 2.

{domain → canvas set, default tasks, trusted scope} spawns the typed-canvas
set at training-session start and stamps artifacts into CanvasAudit under the
session id, so /approvals can render trainee work as visual cards.

Role plans mirror docs/operations/role-training-plan.md.
"""
import logging
from typing import Any, Dict, List, Optional
import uuid

from core.models import AgentRegistry, Canvas, CanvasAudit, ChatSession

logger = logging.getLogger(__name__)

# Canonical role keys → {canvas_set, default_tasks, trusted_scope}.
# trusted_scope["never"] lists actions a role is NEVER allowed to run
# autonomously (hard boundary — e.g. bookkeepers never move money).
ROLE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "sales": {
        "key": "sales",
        "description": "Sales / SDR — lead cards, email drafts, call-priority list.",
        "canvas_set": ["email", "sheets"],
        "default_tasks": [
            "Qualify the newest lead",
            "Draft the opening email for the lead",
            "Draft a follow-up for the second lead",
        ],
        "trusted_scope": {"never": []},
    },
    "bookkeeper": {
        "key": "bookkeeper",
        "description": "Finance / Bookkeeping — reconciliation sheet, AP-aging, exceptions.",
        "canvas_set": ["sheets", "docs"],
        "default_tasks": [
            "Reconcile 3 bills against this month's payments",
            "Flag anything older than 30 days",
        ],
        # Hard trust boundary: drafts for human execution, never money movement.
        "trusted_scope": {"never": ["send_payment"]},
    },
    "operations": {
        "key": "operations",
        "description": "Operations / Coordination — order tracker, task board, flags.",
        "canvas_set": ["sheets", "docs"],
        "default_tasks": [
            "Summarize open production orders by stage",
            "Flag the two oldest stalled ones with a recommended nudge",
        ],
        "trusted_scope": {"never": []},
    },
    "marketing": {
        "key": "marketing",
        "description": "Marketing — copy-doc card, audience segment table.",
        "canvas_set": ["docs", "sheets"],
        "default_tasks": [
            "Draft the customer update from the price-policy fact sheet",
            "Segment the audience list into distributors vs end users",
        ],
        "trusted_scope": {"never": []},
    },
    "support": {
        "key": "support",
        "description": "Support — ticket-thread card, response draft, knowledge refs.",
        "canvas_set": ["docs", "email"],
        "default_tasks": [
            "Pick the most recent unresolved customer email",
            "Summarize the issue and draft a response citing one knowledge doc",
        ],
        "trusted_scope": {"never": []},
    },
    "hr": {
        "key": "hr",
        "description": "HR / Admin — checklist doc, schedule summary.",
        "canvas_set": ["docs", "sheets"],
        "default_tasks": [
            "Assemble an onboarding checklist for the next hire from the standard template",
        ],
        "trusted_scope": {"never": []},
    },
}

# AgentRegistry.category (lowercased) → canonical role key. Resolved only
# when the agent has no specialty that maps to a template directly.
CATEGORY_ALIASES: Dict[str, str] = {
    "sales": "sales",
    "communication": "sales",
    "finance": "bookkeeper",
    "bookkeeping": "bookkeeper",
    "accounting": "bookkeeper",
    "operations": "operations",
    "coordination": "operations",
    "marketing": "marketing",
    "support": "support",
    "customer service": "support",
    "hr": "hr",
    "human resources": "hr",
    "admin": "hr",
    "administration": "hr",
}

# Friendly labels for typed canvas names.
CANVAS_TYPE_LABELS: Dict[str, str] = {
    "email": "Email",
    "docs": "Docs",
    "sheets": "Sheets",
    "presentation": "Presentation",
}


def get_role_template(domain: str) -> Optional[Dict[str, Any]]:
    """Return the template for a canonical role key (case-insensitive)."""
    if not domain:
        return None
    return ROLE_TEMPLATES.get(domain.strip().lower())


def resolve_template_for_agent(
    db, agent_id: str
) -> Optional[Dict[str, Any]]:
    """Resolve the role template for an agent.

    Specialty (AgentRegistry.specialty, e.g. "finance") wins first; falls
    back to the category alias map (e.g. category "Finance" → bookkeeper).
    Returns None when neither resolves.
    """
    if not agent_id:
        return None
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id
    ).first()
    if agent is None:
        return None

    specialty = getattr(agent, "specialty", None)
    if specialty:
        template = get_role_template(specialty)
        if template:
            return template

    category = getattr(agent, "category", None)
    if category:
        role_key = CATEGORY_ALIASES.get(category.strip().lower())
        if role_key:
            template = get_role_template(role_key)
            if template:
                return template
    return None


def spawn_session_canvases(
    db,
    session,
    supervisor_id: str,
    template: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Spawn the role's typed-canvas set for a training session.

    Creates the FK-safe ChatSession row (id == session.id so
    CanvasAudit.session_id → chat_sessions.id stays valid), one Canvas per
    template canvas_type, and one CanvasAudit per canvas stamped with the
    session id. Canvas ids are assigned explicitly so the audit FK matches
    before any flush. Returns spawned canvas descriptors.
    """
    if template is None:
        template = resolve_template_for_agent(
            db, getattr(session, "agent_id", None)
        )
    if not template:
        return []
    canvas_set = template.get("canvas_set") or []
    if not canvas_set:
        return []

    session_id = getattr(session, "id", None) or str(uuid.uuid4())
    tenant_id = getattr(session, "tenant_id", None) or "default"
    agent_id = getattr(session, "agent_id", None)
    role_key = template.get("key") or "custom"
    default_tasks = template.get("default_tasks", [])
    trusted_scope = template.get("trusted_scope", {})

    # ChatSession must exist for CanvasAudit.session_id's FK to hold.
    chat = ChatSession(
        id=session_id,
        user_id=supervisor_id,
        title=f"Role training: {role_key}",
        metadata_json={
            "training_session_id": session_id,
            "role_template": role_key,
            "spawned_by": "role_template_registry",
        },
    )
    db.add(chat)

    spawned: List[Dict[str, Any]] = []
    for canvas_type in canvas_set:
        canvas_id = str(uuid.uuid4())
        label = CANVAS_TYPE_LABELS.get(canvas_type, canvas_type.title())
        canvas = Canvas(
            id=canvas_id,
            tenant_id=tenant_id,
            created_by=supervisor_id,
            name=f"{role_key.title()} {label}",
            canvas_type=canvas_type,
            description=template.get("description"),
        )
        db.add(canvas)

        audit = CanvasAudit(
            canvas_id=canvas_id,
            tenant_id=tenant_id,
            session_id=session_id,
            agent_id=agent_id,
            user_id=supervisor_id,
            action_type="session_spawn",
            canvas_type=canvas_type,
            details_json={
                "default_tasks": default_tasks,
                "trusted_scope": trusted_scope,
                "role_template": role_key,
            },
        )
        db.add(audit)

        spawned.append(
            {
                "canvas_id": canvas_id,
                "canvas_type": canvas_type,
                "details": {
                    "name": canvas.name,
                    "default_tasks": default_tasks,
                    "trusted_scope": trusted_scope,
                },
            }
        )

    db.commit()
    logger.info(
        f"spawned {len(spawned)} role canvases for session {session_id} "
        f"(template={role_key})"
    )
    return spawned


def get_session_canvases(
    db, session_id: str, tenant_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return canvases spawned for a training session (for /approvals cards).

    When tenant_id is given the audit rows are scoped to that tenant so a
    caller can never read another tenant's canvas metadata (IDOR guard — a
    foreign session UUID must resolve to nothing outside its tenant).
    """
    filters = [CanvasAudit.session_id == session_id]
    if tenant_id:
        filters.append(CanvasAudit.tenant_id == tenant_id)
    rows = db.query(CanvasAudit).filter(*filters).all()
    return [
        {
            "canvas_id": row.canvas_id,
            "canvas_type": row.canvas_type,
            "details": row.details_json,
        }
        for row in rows
    ]
