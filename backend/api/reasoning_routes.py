import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set, Tuple
import uuid
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_access import scoped_agent_for_scope
from core.agent_action_audit import log_correction_request
from core.agent_governance_service import AgentGovernanceService
from core.audit_access import (
    CORRECTION_CHANNELS,
    CORRECTION_TARGET_ID_RE,
    AuditAccessDenied,
    authoritative_actor,
    exact_execution_condition,
    execution_identifier_valid,
    execution_visible_to_scope,
    load_visible_audit_row,
    parse_metadata,
    recorded_correction_targets,
    resolve_audit_scope,
    row_execution_id,
    scoped_event_query,
)
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentExecution, AgentReasoningStep, User
from core.personal_scope import PERSONAL_WORKSPACE_ID

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


@dataclass(frozen=True)
class _CorrectionSubject:
    """The proven correction subject — server-recorded ids only.

    ``execution_id`` is always the id recorded on the subject audit row (or
    the independently authorized execution for an execution-only request).
    A caller-supplied id never becomes the binding by itself.
    """

    execution_id: Optional[str]
    audit_id: Optional[str]
    step_number: Optional[int]
    channel_target_basis: Optional[str]
    repair_link_proven: bool


def _correction_refusal(
    status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _authorized_execution(
    db: Session,
    scope: Dict[str, Any],
    execution_id: str,
    agent_id: str,
) -> None:
    """Independently authorize one supplied execution id.

    A supplied execution is a claim, not evidence: it must be visible under
    the SAME audit read scope as the subject row and, when a persisted run
    exists, name the same agent. A member's ownership evidence is an
    owner-scoped audit row (or a workspace-bound run for a supervisor).
    """
    if (
        not execution_identifier_valid(execution_id)
        or not execution_visible_to_scope(db, scope, execution_id)
    ):
        raise _correction_refusal(
            404,
            "AUDIT_SUBJECT_NOT_FOUND",
            (
                "That execution is not in your authorized audit scope; "
                "no correction was recorded."
            ),
        )
    execution = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == execution_id)
        .first()
    )
    if (
        execution is not None
        and execution.agent_id
        and str(execution.agent_id) != str(agent_id)
    ):
        raise _correction_refusal(
            422,
            "CORRECTION_SUBJECT_MISMATCH",
            "The agent id does not match the execution.",
        )


def _subject_recorded_targets(
    db: Session,
    scope: Dict[str, Any],
    row: Any,
    execution_id: Optional[str],
) -> Set[Tuple[str, str]]:
    """Server-recorded (channel, target) pairs for the proven subject.

    Mirrors the audit reader: the subject event's own metadata, the bound
    execution's metadata, and the scoped events of that execution. Only
    allowlisted keys written by the server count; a caller-asserted pair can
    never enter this set.
    """
    sources: list = []
    if row is not None:
        sources.append(parse_metadata(row.metadata_json))
    if execution_id:
        execution = (
            db.query(AgentExecution)
            .filter(AgentExecution.id == execution_id)
            .first()
        )
        if execution is not None:
            raw = execution.metadata_json
            sources.append(raw if isinstance(raw, dict) else parse_metadata(raw))
        for event_row in (
            scoped_event_query(db, scope)
            .filter(exact_execution_condition(execution_id))
            .all()
        ):
            sources.append(parse_metadata(event_row.metadata_json))
    pairs: Set[Tuple[str, str]] = set()
    for source in sources:
        for target in recorded_correction_targets(source):
            pairs.add((str(target["channel"]), str(target["target_id"])))
    return pairs


def _validate_correction_subject(
    db: Session,
    scope: Dict[str, Any],
    feedback: ReasoningStepFeedback,
) -> _CorrectionSubject:
    """Prove the COMPLETE correction subject is a linked, server-known object.

    The subject may be an audit row and/or an execution. Every supplied
    identifier is authorized independently against the same audit read scope
    used by /api/audit, and the event/execution/agent/step binding must be
    proven from recorded data — never inferred from a caller-supplied id.
    Validation happens before any feedback row is written.

    Rules:
    * An owned audit row with no recorded execution supports an event-only
      correction (no ``execution_id``). Supplying an execution for that
      unbound event is refused: there is no recorded link to prove.
    * A supplied execution must be visible to the actor and match the
      execution recorded on the event (and its agent) when both exist.
    * ``run_id`` must agree with the proven execution when both are present.
    * A supplied step (``subject_step_number``/``step_number``) must belong to
      the proven execution; an unknown step is refused, not silently accepted.
    * A channel target is labelled ``recorded_subject_target`` only when the
      server recorded that exact (channel, target) pair for the subject;
      otherwise it stays caller-asserted and never implies repair authority.
    """
    execution_id = (feedback.execution_id or "").strip() or None
    subject_audit_id = (feedback.subject_audit_id or "").strip() or None
    row: Any = None

    if subject_audit_id:
        try:
            row = load_visible_audit_row(db, scope, subject_audit_id)
        except AuditAccessDenied as exc:
            raise _audit_denial(exc) from exc
        row_meta = parse_metadata(row.metadata_json)
        row_agent = row_meta.get("agent_id") or row.resource
        if row_agent and str(row_agent) != str(feedback.agent_id):
            raise _correction_refusal(
                422,
                "CORRECTION_SUBJECT_MISMATCH",
                "The agent id does not match the audit event.",
            )
        recorded_execution = row_execution_id(row)
        if execution_id:
            # A visible event with a different recorded execution is a
            # mismatch the actor can be told about (the row is already theirs
            # to read). Visibility of the supplied id is then checked on its
            # own, so a foreign id cannot ride an owned event.
            if recorded_execution is not None and recorded_execution != execution_id:
                raise _correction_refusal(
                    422,
                    "CORRECTION_SUBJECT_MISMATCH",
                    "The audit event and execution ids do not match.",
                )
            _authorized_execution(db, scope, execution_id, feedback.agent_id)
            if recorded_execution is None:
                raise _correction_refusal(
                    422,
                    "CORRECTION_SUBJECT_UNBOUND",
                    (
                        "That audit event has no recorded execution, so a "
                        "supplied execution id cannot be proven to belong to "
                        "it; no correction was recorded."
                    ),
                )
        # The binding is the id recorded on the event, never the caller's id.
        execution_id = recorded_execution
    elif execution_id:
        _authorized_execution(db, scope, execution_id, feedback.agent_id)
    else:
        raise _correction_refusal(
            422,
            "CORRECTION_SUBJECT_REQUIRED",
            "A correction request must reference an audited event or execution.",
        )

    claimed_run = (feedback.run_id or "").strip() or None
    if execution_id and claimed_run and claimed_run != execution_id:
        raise _correction_refusal(
            422,
            "CORRECTION_SUBJECT_MISMATCH",
            "The run id does not match the proven execution.",
        )

    step_number = (
        feedback.subject_step_number
        if feedback.subject_step_number is not None
        else feedback.step_number
    )
    if step_number is not None:
        if not execution_id:
            raise _correction_refusal(
                422,
                "CORRECTION_STEP_UNVERIFIED",
                (
                    "No execution is recorded for this subject, so the step "
                    "cannot be verified; no correction was recorded."
                ),
            )
        step_exists = (
            db.query(AgentReasoningStep.id)
            .filter(
                AgentReasoningStep.execution_id == execution_id,
                AgentReasoningStep.step_number == step_number,
            )
            .first()
        )
        if step_exists is None:
            raise _correction_refusal(
                422,
                "CORRECTION_STEP_NOT_FOUND",
                (
                    "That step is not recorded for the proven execution; "
                    "no correction was recorded."
                ),
            )

    channel = (feedback.correction_channel or "").strip() or None
    if channel and channel not in CORRECTION_CHANNELS:
        raise _correction_refusal(
            422,
            "CORRECTION_CHANNEL_UNSUPPORTED",
            "That repair channel is not supported.",
        )
    target_id = (feedback.correction_target_id or "").strip() or None
    if target_id and not CORRECTION_TARGET_ID_RE.match(target_id):
        raise _correction_refusal(
            422,
            "CORRECTION_TARGET_INVALID",
            "The correction target identifier is not valid.",
        )

    recorded_targets: Set[Tuple[str, str]] = set()
    if channel or target_id:
        recorded_targets = _subject_recorded_targets(
            db, scope, row, execution_id)
    if channel and target_id:
        if (channel, target_id) in recorded_targets:
            basis, proven = "recorded_subject_target", True
        else:
            basis, proven = "caller_asserted_unverified", False
    elif channel:
        basis, proven = "channel_only_unverified", False
    elif target_id:
        basis, proven = "target_without_channel", False
    else:
        basis, proven = None, False

    return _CorrectionSubject(
        execution_id=execution_id,
        audit_id=str(row.id) if row is not None else None,
        step_number=step_number,
        channel_target_basis=basis,
        repair_link_proven=proven,
    )


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
    subject: _CorrectionSubject,
) -> Dict[str, Any]:
    """Truthful receipt: requested/recorded only — never applied/verified."""
    note = {
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
    }.get(status, "Correction request recorded. Nothing was applied or verified.")
    if (
        status in ("recorded", "already_recorded")
        and subject.channel_target_basis == "caller_asserted_unverified"
    ):
        note += (
            " The named review target is caller-asserted: it is not recorded "
            "on this subject and is not presented as a proven repair link."
        )
    return {
        "id": feedback_id,
        "feedback_id": feedback_id,
        "correction_status": status,
        "correction_audit_id": audit_id,
        "applied": False,
        "verified": False,
        "channel": (feedback.correction_channel or "").strip() or None,
        "channel_target_id": (feedback.correction_target_id or "").strip() or None,
        "channel_target_basis": subject.channel_target_basis,
        "repair_link_proven": subject.repair_link_proven,
        "status_note": note,
    }


def _write_correction_receipt(
    db: Session,
    scope: Dict[str, Any],
    actor: User,
    feedback_row: Any,
    feedback: ReasoningStepFeedback,
    subject: _CorrectionSubject,
) -> Dict[str, Any]:
    existing_link = _existing_correction_link(db, scope, str(feedback_row.id))
    if existing_link is not None:
        return _correction_payload(
            str(feedback_row.id), "already_recorded",
            str(existing_link.id), feedback, subject)
    audit_id = log_correction_request(
        feedback_id=str(feedback_row.id),
        user_id=str(actor.id),
        workspace_id=scope["workspace_id"],
        agent_id=feedback.agent_id,
        execution_id=subject.execution_id,
        subject_audit_id=subject.audit_id,
        subject_step_number=subject.step_number,
        channel=(feedback.correction_channel or "").strip() or None,
        target_id=(feedback.correction_target_id or "").strip() or None,
        channel_target_basis=subject.channel_target_basis,
        repair_link_proven=subject.repair_link_proven,
        reason=(feedback.correction_reason or "").strip()[:2000] or None,
    )
    return _correction_payload(
        str(feedback_row.id),
        "recorded" if audit_id else "feedback_recorded_audit_unavailable",
        audit_id,
        feedback,
        subject,
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
    correction_subject: Optional[_CorrectionSubject] = None
    if feedback.correction_requested:
        correction_actor, correction_scope = _resolve_correction_authority(
            db, current_user)
        correction_subject = _validate_correction_subject(
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
    if correction_subject is not None:
        # A correction against a different audit subject is a different
        # dispute; keeping it in the idempotency key prevents the old
        # thumbs-dedup from silently swallowing it. Only the proven subject
        # ids are stored, never the raw caller-asserted ones.
        context_payload["correction"] = {
            "subject_audit_id": correction_subject.audit_id,
            "subject_execution_id": correction_subject.execution_id,
            "subject_step_number": correction_subject.step_number,
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
        if correction_subject is None:
            _stamp_canvas_chat_feedback(
                db, feedback, existing, user_id=str(current_user.id))
        if correction_subject is not None and correction_scope is not None:
            _bind_feedback_execution(db, existing, correction_subject.execution_id)
            data = _write_correction_receipt(
                db, correction_scope, correction_actor, existing, feedback,
                correction_subject,
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

    # A correction was already authorized against the durable actor's audit
    # scope (actor -> workspace -> subject). Resolve the reviewed agent under
    # the SAME shared/legacy-reader predicate GET /api/agents uses, and only
    # AFTER the linked subject is proven: a request body alone must never
    # choose a writer target. Shared rows (NULL/""/"default") and the actor's
    # exact workspace are legitimate; a foreign workspace/tenant is refused
    # before anything is written. Ordinary thumbs feedback keeps the
    # historical default construction.
    if correction_subject is not None:
        correction_agent = scoped_agent_for_scope(
            db, correction_scope, feedback.agent_id)
        if correction_agent is None:
            raise _correction_refusal(
                404,
                "CORRECTION_AGENT_NOT_FOUND",
                (
                    "The reviewed agent is not available in your authorized "
                    "scope; no correction was recorded."
                ),
            )
        # Bind the governance writer to the EXACT resolved registry row's
        # workspace so its own lookup, adjudication and confidence queries
        # all see that same row. A legacy NULL row keeps the historical
        # ``default`` shared bucket (same value the base writer used); an
        # empty-string legacy row is matched exactly. The tenant stays the
        # actor's separate durable ACCOUNT key, never the workspace id, so
        # persistent feedback/learning land in the right account.
        agent_workspace = correction_agent.workspace_id
        if agent_workspace is None:
            agent_workspace = PERSONAL_WORKSPACE_ID
        governance_service = AgentGovernanceService(
            db,
            workspace_id=agent_workspace,
            tenant_id=correction_scope["tenant_id"],
        )
    else:
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
            input_context=input_context,
            # Only the correction path has a freshly resolved actor scope;
            # the ordinary thumbs path keeps the service's historical
            # workspace/default learning key.
            feedback_tenant_id=(
                correction_scope["tenant_id"]
                if correction_scope is not None else None
            ),
        )
        if correction_subject is None:
            _stamp_canvas_chat_feedback(
                db, feedback, db_feedback, user_id=str(current_user.id))

        # Write-through: when the reviewed step belongs to a persisted run,
        # stamp the polarity + comment directly on the reasoning-step row so
        # training consumers (harness evolution, failure-pattern mining) can
        # query it without parsing AgentFeedback input_context blobs.
        # On a correction request the execution is the PROVEN subject
        # execution, so a client-supplied foreign id can never reach a
        # reasoning-step row (a canvas is likewise never touched above).
        step_execution_id = (
            correction_subject.execution_id
            if correction_subject is not None
            else feedback.execution_id
        )
        if step_execution_id and feedback.step_number is not None:
            step_row = (
                db.query(AgentReasoningStep)
                .filter(
                    AgentReasoningStep.execution_id == step_execution_id,
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

        if correction_subject is not None and correction_scope is not None:
            _bind_feedback_execution(
                db, db_feedback, correction_subject.execution_id)
            data = _write_correction_receipt(
                db, correction_scope, correction_actor, db_feedback, feedback,
                correction_subject,
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
