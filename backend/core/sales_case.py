"""
Sales Case service — the central object of the AI sales agent.

One customer inquiry becomes a SalesCase that tracks intent, products,
requirements, decisions, actions, human interventions, vendor communications,
the quote and shipping state. Status changes are *validated transitions*
(dynamic state, not a hardcoded workflow), and asking a human creates a
HITLAction (pending) and pauses the case in WAITING_FOR_HUMAN — the same
governance surface the Outlook automation loop uses.

Design notes (docs/sales plan): the agent loop reasons over a case, calls
tools, updates the case, and repeats until DONE (completed) or WAITING (a
waiting_for_* status). Nothing here assumes a paid LLM; the tools layer is
kept thin and testable.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import get_db_session
from core.models import HITLAction, HITLActionStatus, SalesCase, SalesCaseStatus

logger = logging.getLogger(__name__)

# Valid status transitions: current status -> allowed next statuses.
SALES_CASE_TRANSITIONS: Dict[str, List[str]] = {
    "new": ["understanding", "researching", "waiting_for_human", "waiting_for_customer", "completed"],
    "understanding": ["researching", "waiting_for_human", "waiting_for_customer", "completed"],
    "researching": ["quoting", "waiting_for_vendor", "waiting_for_inventory",
                    "waiting_for_human", "waiting_for_customer", "completed"],
    "waiting_for_vendor": ["researching", "quoting", "waiting_for_human", "waiting_for_customer", "completed"],
    "waiting_for_inventory": ["researching", "quoting", "waiting_for_human", "completed"],
    "waiting_for_human": ["researching", "quoting", "waiting_for_vendor",
                          "waiting_for_customer", "completed"],
    "waiting_for_customer": ["researching", "quoting", "completed"],
    "quoting": ["quote_pending_approval", "quoted", "waiting_for_human",
                "waiting_for_customer", "completed"],
    "quote_pending_approval": ["quoted", "quoting", "waiting_for_human", "completed"],
    "quoted": ["ordered", "waiting_for_customer", "completed"],
    "ordered": ["purchasing", "shipping", "waiting_for_human", "completed"],
    "purchasing": ["shipping", "waiting_for_vendor", "waiting_for_human", "completed"],
    "shipping": ["completed", "waiting_for_human"],
    "completed": [],
}

WAITING_STATUSES = {
    "waiting_for_human", "waiting_for_vendor", "waiting_for_customer",
    "waiting_for_inventory",
}


def valid_transition(current: str, next_status: str) -> bool:
    return next_status in SALES_CASE_TRANSITIONS.get(current, [])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_list(value: Any) -> list:
    return list(value or [])


def case_to_dict(case: SalesCase) -> Dict[str, Any]:
    """Serialize a SalesCase row (JSON columns -> lists/dicts safely)."""
    return {
        "id": case.id,
        "tenant_id": case.tenant_id,
        "workspace_id": case.workspace_id,
        "user_id": case.user_id,
        "status": case.status,
        "intent": case.intent or "",
        "customer_name": case.customer_name or "",
        "customer_email": case.customer_email or "",
        "subject": case.subject or "",
        "email_id": case.email_id,
        "conversation_id": case.conversation_id,
        "products": _json_list(case.products),
        "requirements": _json_list(case.requirements),
        "decisions": _json_list(case.decisions),
        "actions": _json_list(case.actions),
        "pending_actions": _json_list(case.pending_actions),
        "human_interventions": _json_list(case.human_interventions),
        "vendor_communications": _json_list(case.vendor_communications),
        "quote": case.quote or {},
        "shipping": case.shipping or {},
        "metadata": case.metadata_json or {},
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def create_case(
    *,
    workspace_id: str = "default",
    user_id: Optional[str] = None,
    tenant_id: str = "default",
    customer_name: str = "",
    customer_email: str = "",
    subject: str = "",
    email_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    intent: str = "",
    products: Optional[list] = None,
    requirements: Optional[list] = None,
) -> Dict[str, Any]:
    """Create a new sales case (status NEW). Never raises for data issues."""
    with get_db_session() as db:
        case = SalesCase(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            status=SalesCaseStatus.NEW.value,
            customer_name=customer_name,
            customer_email=customer_email,
            subject=subject,
            email_id=email_id,
            conversation_id=conversation_id,
            intent=intent,
            products=products or [],
            requirements=requirements or [],
            decisions=[{"action": "case_created", "by": user_id or "agent", "at": _now_iso()}],
            actions=[{"action": "case_created", "by": user_id or "agent", "at": _now_iso()}],
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case_to_dict(case)


def get_case(case_id: str) -> Optional[Dict[str, Any]]:
    with get_db_session() as db:
        case = db.query(SalesCase).filter(SalesCase.id == case_id).first()
        return case_to_dict(case) if case else None


def find_case_by_email(
    *,
    customer_email: Optional[str] = None,
    email_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    open_only: bool = True,
) -> Optional[Dict[str, Any]]:
    """Find an (open) case by customer email, originating email id, or thread
    (conversation) id — used to correlate a vendor/customer reply to its case
    and resume reasoning. Returns the newest match or None."""
    with get_db_session() as db:
        q = db.query(SalesCase)
        if customer_email:
            q = q.filter(SalesCase.customer_email == customer_email.strip().lower())
        elif email_id:
            q = q.filter(SalesCase.email_id == email_id)
        elif conversation_id:
            q = q.filter(SalesCase.conversation_id == conversation_id)
        else:
            return None
        if open_only:
            q = q.filter(SalesCase.status != SalesCaseStatus.COMPLETED.value)
        case = q.order_by(SalesCase.updated_at.desc()).first()
        return case_to_dict(case) if case else None


def list_cases(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_session() as db:
        q = db.query(SalesCase)
        if status:
            q = q.filter(SalesCase.status == status)
        cases = q.order_by(SalesCase.updated_at.desc()).limit(limit).all()
        return [case_to_dict(c) for c in cases]


def transition(
    case_id: str,
    next_status: str,
    reason: str = "",
    actor: str = "agent",
) -> Dict[str, Any]:
    """Validate + apply a status transition; append to decisions/actions.
    Returns {"success": bool, "case": {...}|None, "error": str|None}."""
    with get_db_session() as db:
        case = db.query(SalesCase).filter(SalesCase.id == case_id).first()
        if case is None:
            return {"success": False, "case": None, "error": "case_not_found"}
        if next_status == case.status:
            return {"success": True, "case": case_to_dict(case), "error": None}
        if not valid_transition(case.status, next_status):
            return {
                "success": False,
                "case": case_to_dict(case),
                "error": f"invalid_transition:{case.status}->{next_status}",
            }
        entry = {"action": f"status:{case.status}->{next_status}", "by": actor,
                 "at": _now_iso(), "reason": reason}
        case.status = next_status
        decisions = list(case.decisions or [])
        decisions.append(entry)
        case.decisions = decisions
        actions = list(case.actions or [])
        actions.append(entry)
        case.actions = actions
        db.commit()
        db.refresh(case)
        return {"success": True, "case": case_to_dict(case), "error": None}


def ask_human(
    case_id: str,
    question: str,
    agent_id: str = "sales_agent",
    priority: str = "MEDIUM",
) -> Dict[str, Any]:
    """Pause the case for a human decision: create a pending HITLAction tied
    to the case and move it to WAITING_FOR_HUMAN. Returns the HITL id."""
    with get_db_session() as db:
        case = db.query(SalesCase).filter(SalesCase.id == case_id).first()
        if case is None:
            return {"success": False, "error": "case_not_found", "hitl_id": None}

        hitl = HITLAction(
            id=str(uuid.uuid4()),
            tenant_id=case.tenant_id or "default",
            workspace_id=case.workspace_id or "default",
            agent_id=agent_id,
            action_type="sales_case_human_decision",
            platform="sales_case",
            params={"case_id": case_id, "question": question},
            status=HITLActionStatus.PENDING.value,
            reason=f"Sales case {case_id}: {question}",
            priority=priority,
            user_id=case.user_id,
        )
        db.add(hitl)

        interventions = list(case.human_interventions or [])
        interventions.append({"question": question, "answer": None, "hitl_id": hitl.id,
                              "asked_at": _now_iso()})
        case.human_interventions = interventions

        if case.status != SalesCaseStatus.WAITING_FOR_HUMAN.value:
            decisions = list(case.decisions or [])
            decisions.append({"action": f"status:{case.status}->waiting_for_human",
                              "by": agent_id, "at": _now_iso(), "reason": f"ask human: {question}"})
            case.decisions = decisions
            case.status = SalesCaseStatus.WAITING_FOR_HUMAN.value
        db.commit()
        return {"success": True, "hitl_id": hitl.id, "case_id": case_id}
