import json
import logging
from typing import Any, Dict, Optional
import uuid
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_action_audit import log_correction_request
from core.agent_governance_service import AgentGovernanceService
from core.audit_access import (
    CORRECTION_CHANNELS,
    CORRECTION_TARGET_ID_RE,
    AuditAccessDenied,
    authoritative_actor,
    execution_identifier_valid,
    execution_visible_to_scope,
    load_visible_audit_row,
    parse_metadata,
    resolve_audit_scope,
    row_execution_id,
    scoped_event_query,
)
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentExecution, User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/reasoning", tags=["reasoning"])


class ReasoningStepFeedback(BaseModel):
    agent_id: str
    run_id: str
    step_index: int
    step_content: Dict[str, Any]  # The thought/action/observation payload
    feedback_type: str  # "thumbs_up", "thumbs_down"
    comment: Optional[str] = None
    # When the step came from a persisted run, these identify the
    # AgentReasoningStep row so the feedback is stamped directly on the trace
    # (consumed by harness evolution / failure-pattern mining).
    execution_id: Optional[str] = None
    step_number: Optional[int] = None
    # Correction REQUEST linkage (F2). This records a dispute/request against
    # an already-authorized audit subject; it never applies or verifies a
    # repair. Omitted for ordinary thumbs feedback, preserving old behaviour.
    correction_requested: bool = False
    subject_audit_id: Optional[str] = None
    subject_step_number: Optional[int] = None
    correction_channel: Optional[str] = None
    correction_target_id: Optional[str] = None
    correction_reason: Optional[str] = None


@router.get("/chain/{chain_id}")
async def get_reasoning_chain(
    chain_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a reasoning chain by id for the Reasoning Audit dialog.

    W45: the frontend called /api/v1/voice/reasoning/{chain_id} which never
    existed (404) — the audit dialog was dead. The tracker is in-memory
    (core.reasoning_chain.ReasoningTracker), so serve what it holds.
    """
    from core.reasoning_chain import get_reasoning_tracker

    chain = get_reasoning_tracker().get_chain(chain_id)
    if not chain:
        raise router.not_found_error("ReasoningChain", chain_id)
    return router.success_response(
        data=chain.dict() if hasattr(chain, "dict") else chain.__dict__,
        message="Reasoning chain retrieved",
    )


def _audit_denial(exc: AuditAccessDenied) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


def _resolve_correction_authority(db: Session, current_user: User):
    """Fresh actor + audit read scope for a correction request.

    The token is only a subject hint: a deactivated account, a changed role or
    a moved workspace is resolved from the durable User row before any write.
    """
    try:
        actor = authoritative_actor(db, current_user)
    except AuditAccessDenied as exc:
        raise _audit_denial(exc) from exc
    return actor, resolve_audit_scope(actor)


def _validate_correction_subject(
    db: Session,
    scope: Dict[str, Any],
    feedback: ReasoningStepFeedback,
) -> Optional[str]:
    """Prove the referenced audit subject is visible to this actor.

    The subject may be an audit row id, an execution id, or both. Both are
    checked against the SAME audit read scope used by /api/audit; a mismatch
    between the claimed ids, a foreign workspace row, or an unowned execution
    is refused before any feedback is written.
    """
    execution_id = (feedback.execution_id or "").strip() or None
    subject_audit_id = (feedback.subject_audit_id or "").strip() or None

    if subject_audit_id:
        try:
            row = load_visible_audit_row(db, scope, subject_audit_id)
        except AuditAccessDenied as exc:
            raise _audit_denial(exc) from exc
        row_execution = row_execution_id(row)
        if execution_id and row_execution and row_execution != execution_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "CORRECTION_SUBJECT_MISMATCH",
                    "message": "The audit event and execution ids do not match.",
                },
            )
        execution_id = execution_id or row_execution
        row_meta = parse_metadata(row.metadata_json)
        row_agent = row_meta.get("agent_id") or row.resource
        if row_agent and str(row_agent) != str(feedback.agent_id):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "CORRECTION_SUBJECT_MISMATCH",
                    "message": "The agent id does not match the audit event.",
                },
            )
    elif execution_id:
        if (
            not execution_identifier_valid(execution_id)
            or not execution_visible_to_scope(db, scope, execution_id)
        ):
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "AUDIT_SUBJECT_NOT_FOUND",
                    "message": (
                        "That execution is not in your authorized audit scope; "
                        "no correction was recorded."
                    ),
                },
            )
        execution = (
            db.query(AgentExecution)
            .filter(AgentExecution.id == execution_id)
            .first()
        )
        if (
            execution is not None
            and execution.agent_id
            and str(execution.agent_id) != str(feedback.agent_id)
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "CORRECTION_SUBJECT_MISMATCH",
                    "message": "The agent id does not match the execution.",
                },
            )
    else:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CORRECTION_SUBJECT_REQUIRED",
                "message": "A correction request must reference an audited event or execution.",
            },
        )

    channel = (feedback.correction_channel or "").strip() or None
    if channel and channel not in CORRECTION_CHANNELS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CORRECTION_CHANNEL_UNSUPPORTED",
                "message": "That repair channel is not supported.",
            },
        )
    target_id = (feedback.correction_target_id or "").strip() or None
    if target_id and not CORRECTION_TARGET_ID_RE.match(target_id):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CORRECTION_TARGET_INVALID",
                "message": "The correction target identifier is not valid.",
            },
        )
    return execution_id


def _existing_correction_link(
    db: Session,
    scope: Dict[str, Any],
    feedback_id: str,
):
    """Return the already-written audit receipt for this feedback row, if any."""
    from core.models import AuditLog

    needle = json.dumps({"feedback_id": str(feedback_id)})[1:-1]
    escaped = (
        needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    row = (
        scoped_event_query(db, scope)
        .filter(AuditLog.action == "correction_requested")
        .filter(AuditLog.metadata_json.like(f"%{escaped}%", escape="\\"))
        .first()
    )
    if row is None:
        return None
    if str(parse_metadata(row.metadata_json).get("feedback_id")) != str(feedback_id):
        return None
    return row


def _bind_feedback_execution(
    db: Session,
    db_feedback: Any,
    execution_id: Optional[str],
) -> None:
    """Stamp the existing AgentFeedback row with its execution when it exists."""
    if not execution_id:
        return
    if str(getattr(db_feedback, "agent_execution_id", "") or "") == str(execution_id):
        return
    execution_exists = (
        db.query(AgentExecution.id)
        .filter(AgentExecution.id == execution_id)
        .first()
    )
    if execution_exists is None:
        return
    try:
        db_feedback.agent_execution_id = str(execution_id)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — feedback already persisted
        logger.warning(
            "Feedback execution binding skipped (error_class=%s)",
            type(exc).__name__,
        )


def _correction_payload(
    feedback_id: str,
    status: str,
    audit_id: Optional[str],
    feedback: ReasoningStepFeedback,
) -> Dict[str, Any]:
    """Truthful receipt: requested/recorded only — never applied/verified."""
    return {
        "id": feedback_id,
        "feedback_id": feedback_id,
        "correction_status": status,
        "correction_audit_id": audit_id,
        "applied": False,
        "verified": False,
        "channel": (feedback.correction_channel or "").strip() or None,
        "channel_target_id": (feedback.correction_target_id or "").strip() or None,
        "status_note": {
            "recorded": (
                "Correction request recorded and linked to the audited item. "
                "Nothing was applied or verified."
            ),
            "already_recorded": (
                "An identical correction request is already recorded and linked. "
                "Nothing was applied or verified."
            ),
            "feedback_recorded_audit_unavailable": (
                "Feedback was recorded, but the audit link could not be written. "
                "The request is not shown as applied or verified."
            ),
        }.get(status, "Correction request recorded. Nothing was applied or verified."),
    }


def _write_correction_receipt(
    db: Session,
    scope: Dict[str, Any],
    actor: User,
    feedback_row: Any,
    feedback: ReasoningStepFeedback,
    execution_id: str,
) -> Dict[str, Any]:
    existing_link = _existing_correction_link(db, scope, str(feedback_row.id))
    if existing_link is not None:
        return _correction_payload(
            str(feedback_row.id), "already_recorded", str(existing_link.id), feedback)
    audit_id = log_correction_request(
        feedback_id=str(feedback_row.id),
        user_id=str(actor.id),
        workspace_id=scope["workspace_id"],
        agent_id=feedback.agent_id,
        execution_id=execution_id,
        subject_audit_id=(feedback.subject_audit_id or "").strip() or None,
        subject_step_number=(
            feedback.subject_step_number
            if feedback.subject_step_number is not None
            else feedback.step_number
        ),
        channel=(feedback.correction_channel or "").strip() or None,
        target_id=(feedback.correction_target_id or "").strip() or None,
        reason=(feedback.correction_reason or "").strip()[:2000] or None,
    )
    return _correction_payload(
        str(feedback_row.id),
        "recorded" if audit_id else "feedback_recorded_audit_unavailable",
        audit_id,
        feedback,
    )



def _stamp_canvas_chat_feedback(db, feedback, db_feedback, user_id: str = None) -> None:
    """Persist the canvas panel's thumbs choice on the canvas context so it
    survives refresh (the panel restores it from there on hydration). Keyed
    by the assistant message's input_summary — exactly what the panel sends.
    Fault-isolated: feedback recording must never fail on this.
    """
    try:
        content = feedback.step_content or {}
        if content.get("source") != "canvas_chat" or not content.get("canvas_id"):
            return
        key = str(content.get("input_summary") or "")[:200]
        if not key:
            return
        from core.models import CanvasContext
        from core.service_factory import ServiceFactory

        service = ServiceFactory.get_canvas_context_service(db, tenant_id="default")
        ctx = service.get_context(str(content["canvas_id"]), user_id) if user_id else None
        # Fall back to the canvas's single context row when the caller has
        # no own row (feedback before the first chat turn bound one).
        if ctx is None:
            row = db.query(CanvasContext).filter(CanvasContext.canvas_id == str(content["canvas_id"])).first()
            if row is None:
                return
            ctx = row
        state = dict(ctx.current_state or {})
        map_ = dict(state.get("chat_feedback") or {})
        map_[key] = {
            "feedback_type": feedback.feedback_type,
            "comment": feedback.comment,
            "feedback_id": getattr(db_feedback, "id", None),
        }
        state["chat_feedback"] = map_
        ctx.current_state = state
        db.commit()
    except Exception as e:
        logger.debug(f"canvas chat-feedback stamp skipped: {e}")


@router.post("/feedback")
async def submit_step_feedback(
    feedback: ReasoningStepFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback for a specific reasoning step.
    This reuses the AgentFeedback model by storing step details in input_context.

    When ``correction_requested`` is set, the SAME write also records a
    ``correction_requested`` audit row linking the feedback to an authorized
    execution/step/audit subject. That row states ``applied=False`` and
    ``verified=False``: this endpoint never repairs anything itself.
    """

    # Correction linkage is authority-checked BEFORE any feedback row is
    # written, so a refused request leaves no half-recorded dispute behind.
    correction_actor: Optional[User] = None
    correction_scope: Optional[Dict[str, Any]] = None
    correction_execution_id: Optional[str] = None
    if feedback.correction_requested:
        correction_actor, correction_scope = _resolve_correction_authority(
            db, current_user)
        correction_execution_id = _validate_correction_subject(
            db, correction_scope, feedback)

    # Context payload describing the step being reviewed. feedback_type is
    # stored explicitly (R82): user_correction prefers the comment, so without
    # this the thumbs_up/thumbs_down polarity would be lost for adjudication.
    context_payload = {
        "run_id": feedback.run_id,
        "step_index": feedback.step_index,
        "feedback_type": feedback.feedback_type,
        "step_content": feedback.step_content
    }
    if feedback.correction_requested:
        # A correction against a different audit subject is a different
        # dispute; keeping it in the idempotency key prevents the old
        # thumbs-dedup from silently swallowing it.
        context_payload["correction"] = {
            "subject_audit_id": feedback.subject_audit_id,
            "subject_execution_id": correction_execution_id,
            "subject_step_number": feedback.subject_step_number,
            "channel": feedback.correction_channel,
            "target_id": feedback.correction_target_id,
        }

    input_context = json.dumps(context_payload)

    # Idempotent training feed: the canvas panel's thumbs state is client
    # state — a refresh clears it and the user clicks the SAME thumb again.
    # Every re-click used to append another identical AgentFeedback row and
    # re-run adjudication, feeding the training loop duplicate data. An
    # identical resubmit (same agent, same step context, same polarity and
    # comment) is a no-op that returns the existing row. A CHANGED choice
    # (up→down, or a new comment) still records.
    from core.models import AgentFeedback as AgentFeedbackModel

    existing = (
        db.query(AgentFeedbackModel)
        .filter(
            AgentFeedbackModel.agent_id == feedback.agent_id,
            AgentFeedbackModel.user_id == str(current_user.id),
            AgentFeedbackModel.input_context == input_context,
            AgentFeedbackModel.user_correction == (feedback.comment or feedback.feedback_type),
        )
        .order_by(AgentFeedbackModel.created_at.desc())
        .first()
    )
    if existing is not None:
        _stamp_canvas_chat_feedback(db, feedback, existing, user_id=str(current_user.id))
        if feedback.correction_requested and correction_scope is not None:
            _bind_feedback_execution(db, existing, correction_execution_id)
            data = _write_correction_receipt(
                db, correction_scope, correction_actor, existing, feedback,
                correction_execution_id or "",
            )
            data["duplicate"] = True
            return router.success_response(
                data=data,
                message=data["status_note"],
            )
        return router.success_response(
            data={"id": existing.id, "duplicate": True},
            message="Feedback already recorded — no duplicate training data created",
        )

    governance_service = AgentGovernanceService(db)

    # original_output is the thought being judged
    original_output = json.dumps(feedback.step_content.get('thought', ''))

    # user_correction is the feedback type (thumbs_up/down) or comment
    user_correction = (
        feedback.comment
        or (feedback.correction_reason if feedback.correction_requested else None)
        or feedback.feedback_type
    )

    try:
        # Submit feedback (this will trigger async adjudication and confidence updates)
        db_feedback = await governance_service.submit_feedback(
            agent_id=feedback.agent_id,
            user_id=(correction_actor.id if correction_actor is not None else current_user.id),
            original_output=original_output,
            user_correction=user_correction,
            input_context=input_context
        )
        _stamp_canvas_chat_feedback(db, feedback, db_feedback, user_id=str(current_user.id))

        # Write-through: when the reviewed step belongs to a persisted run,
        # stamp the polarity + comment directly on the reasoning-step row so
        # training consumers (harness evolution, failure-pattern mining) can
        # query it without parsing AgentFeedback input_context blobs.
        if feedback.execution_id and feedback.step_number is not None:
            from core.models import AgentReasoningStep

            step_row = (
                db.query(AgentReasoningStep)
                .filter(
                    AgentReasoningStep.execution_id == feedback.execution_id,
                    AgentReasoningStep.step_number == feedback.step_number,
                )
                .first()
            )
            if step_row is not None:
                step_row.feedback_score = (
                    1 if feedback.feedback_type == "thumbs_up" else -1
                )
                if feedback.comment:
                    step_row.feedback_text = feedback.comment
                db.commit()

        if feedback.correction_requested and correction_scope is not None:
            _bind_feedback_execution(db, db_feedback, correction_execution_id)
            data = _write_correction_receipt(
                db, correction_scope, correction_actor, db_feedback, feedback,
                correction_execution_id or "",
            )
            return router.success_response(
                data=data,
                message=data["status_note"],
            )

        return router.success_response(
            data={"id": db_feedback.id},
            message="Feedback submitted and processed by governance engine",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise router.internal_error("Internal error")
