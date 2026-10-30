"""Conversation-derived, reference-bound learning routes.

The UI reviews a candidate's evidence chain before promotion. Promotion is
the only path that writes a standing lesson, and it requires the reviewed
revision and dependency digest to still match.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.base_routes import BaseAPIRouter
from core.conversation_learning import (
    ConversationEvidence,
    LearningCandidate,
    build_candidate,
    candidate_readiness,
    collect_email_thread_evidence,
    confirm_candidate,
    list_candidates,
    list_email_threads,
    load_candidate,
    promote_candidate,
    reject_candidate,
    resolve_dependency,
    review_payload,
    revise_candidate,
    save_candidate,
)
from core.database import get_db

router = BaseAPIRouter(
    prefix="/api/conversation-learning", tags=["Conversation Learning"])


class EvidenceRequest(BaseModel):
    thread_id: str


class CandidateCreate(BaseModel):
    thread_id: str
    agent_id: str
    proposed_lesson: str
    method: Dict[str, Any] = {}
    method_status: str = "unresolved"
    applies_to: List[str] = []
    context: Dict[str, Any] = {}
    references: Optional[List[Dict[str, Any]]] = None
    authority_message_id: str = ""
    authority_excerpt: str = ""


class CandidateRevise(BaseModel):
    thread_id: str
    proposed_lesson: Optional[str] = None
    method: Optional[Dict[str, Any]] = None
    method_status: Optional[str] = None
    applies_to: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None
    changed_by: str = ""


class DependencyResolve(BaseModel):
    thread_id: str
    dependency_id: str
    resource_id: str = ""
    column: str = ""
    unit: str = ""
    value: Any = None
    confirmed_by: str = ""


class CandidateConfirm(BaseModel):
    thread_id: str
    reviewer: str
    expected_revision: int


class CandidatePromote(BaseModel):
    thread_id: str
    reviewer: str
    expected_revision: int
    expected_digest: str = ""


class CandidateReject(BaseModel):
    thread_id: str
    reviewer: str
    reason: str = ""


def _scope(user: User) -> tuple:
    return (
        str(user.workspace_id or "default"),
        str(user.tenant_id or "default"),
    )


def _evidence(db: Session, user: User, thread_id: str) -> ConversationEvidence:
    return collect_email_thread_evidence(db, user, thread_id)


def _load_scoped(
    db: Session, user: User, thread_id: str, candidate_id: str,
) -> LearningCandidate:
    candidate = load_candidate(db, thread_id, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Learning candidate not found")
    workspace_id, tenant_id = _scope(user)
    if (candidate.workspace_id != workspace_id
            or candidate.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Learning candidate not found")
    return candidate


def _payload(candidate: LearningCandidate) -> Dict[str, Any]:
    readiness = candidate_readiness(candidate)
    return {
        "candidate": candidate.model_dump(mode="json"),
        "review": review_payload(candidate),
        "review_ready": readiness["review_ready"],
        "blocking": [
            dep.model_dump(mode="json") for dep in readiness["blocking"]
        ],
    }


@router.get("/threads")
def get_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "threads": list_email_threads(db, current_user),
    }


@router.post("/evidence")
def build_evidence(
    request: EvidenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = _evidence(db, current_user, request.thread_id)
    return evidence.model_dump(mode="json")


@router.get("/threads/{thread_id}/evidence")
def get_evidence(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = _evidence(db, current_user, thread_id)
    return evidence.model_dump(mode="json")


@router.get("/threads/{thread_id}/candidates")
def get_thread_candidates(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_id, tenant_id = _scope(current_user)
    candidates = list_candidates(
        db, thread_id, workspace_id=workspace_id, tenant_id=tenant_id)
    return {
        "thread_id": thread_id,
        "candidates": [_payload(candidate) for candidate in candidates],
    }


@router.post("/candidates")
def create_candidate(
    request: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_id, tenant_id = _scope(current_user)
    evidence = _evidence(db, current_user, request.thread_id)
    try:
        candidate = build_candidate(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            agent_id=request.agent_id,
            thread_id=request.thread_id,
            proposed_lesson=request.proposed_lesson,
            method=request.method,
            method_status=request.method_status,
            applies_to=request.applies_to,
            context=request.context,
            evidence=evidence,
            references=request.references,
            authority_message_id=request.authority_message_id,
            authority_excerpt=request.authority_excerpt,
            created_by=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = save_candidate(db, candidate)
    return _payload(saved)


@router.get("/candidates/{candidate_id}")
def get_candidate(
    candidate_id: str,
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    candidate = _load_scoped(db, current_user, thread_id, candidate_id)
    return _payload(candidate)


@router.post("/candidates/{candidate_id}/revise")
def revise(
    candidate_id: str,
    request: CandidateRevise,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    candidate = _load_scoped(
        db, current_user, request.thread_id, candidate_id)
    try:
        revised = revise_candidate(
            db, candidate,
            proposed_lesson=request.proposed_lesson,
            method=request.method,
            method_status=request.method_status,
            applies_to=request.applies_to,
            context=request.context,
            changed_by=request.changed_by or str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payload(revised)


@router.post("/candidates/{candidate_id}/resolve")
def resolve(
    candidate_id: str,
    request: DependencyResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    candidate = _load_scoped(
        db, current_user, request.thread_id, candidate_id)
    evidence = _evidence(db, current_user, request.thread_id)
    try:
        resolved = resolve_dependency(
            db, candidate, request.dependency_id,
            catalog=evidence.resources,
            resource_id=request.resource_id,
            column=request.column,
            unit=request.unit,
            value=request.value,
            confirmed_by=request.confirmed_by or str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payload(resolved)


@router.post("/candidates/{candidate_id}/confirm")
def confirm(
    candidate_id: str,
    request: CandidateConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    candidate = _load_scoped(
        db, current_user, request.thread_id, candidate_id)
    try:
        confirmed = confirm_candidate(
            db, candidate, reviewer=request.reviewer,
            expected_revision=request.expected_revision)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _payload(confirmed)


@router.post("/candidates/{candidate_id}/promote")
def promote(
    candidate_id: str,
    request: CandidatePromote,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    candidate = _load_scoped(
        db, current_user, request.thread_id, candidate_id)
    try:
        result = promote_candidate(
            db, candidate, reviewer=request.reviewer,
            expected_revision=request.expected_revision,
            expected_digest=request.expected_digest)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "candidate": result["candidate"].model_dump(mode="json"),
        "entry": result["entry"],
        "lesson_id": result["lesson_id"],
        "review": review_payload(result["candidate"]),
    }


@router.post("/candidates/{candidate_id}/reject")
def reject(
    candidate_id: str,
    request: CandidateReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    candidate = _load_scoped(
        db, current_user, request.thread_id, candidate_id)
    rejected = reject_candidate(
        db, candidate, reviewer=request.reviewer, reason=request.reason)
    return _payload(rejected)
