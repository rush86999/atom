"""Reference-bound learning from conversations.

This module is the bounded successor to the local-core teaching system. It
does NOT add a second knowledge store: candidates and their review history
are append-only ``ConversationEvent`` rows, resource identity reuses the
assignment catalog/binding contract, and accepted lessons are written through
``student_learning_service.journal_standing_lesson_entry``.

The three questions stay separate:

1. reference resolution — which resource did the speaker mean?
2. evidence sufficiency — does that resource actually support the claim?
3. teaching authority — is this speaker/statement allowed to become guidance?

A resolved attachment is not automatically correct evidence, and an
authorized speaker can still be ambiguous. ``resolve_reference_edges`` only
answers (1); ``derive_dependencies`` and ``candidate_readiness`` answer (2)
and (3) and keep the candidate blocked until the user confirms the missing
pieces.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from core.assignment_plan import canonical_sha256

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "conversation-learning-1"

REFERENCE_RELATIONS = {
    "attachment",
    "reply",
    "supersedes",
    "example",
    "calculation_input",
    "method_reference",
    "policy_reference",
    "context",
}

RESOLUTION_STATUSES = {
    "resolved",
    "ambiguous",
    "missing",
    "access_denied",
    "stale",
    "incomplete",
    "conflicting",
    "not_applicable",
}

DEPENDENCY_STATUSES = {
    "resolved",
    "ambiguous",
    "missing",
    "access_denied",
    "stale",
    "incomplete",
    "conflicting",
    "not_applicable",
}

METHOD_STATUSES = {
    "explicit",
    "example_only",
    "partially_inferred",
    "unresolved",
}

CANDIDATE_STATUSES = {
    "draft",
    "needs_clarification",
    "review_ready",
    "confirmed",
    "promoted",
    "rejected",
    "invalidated",
}

_LEARNING_EVENT_KINDS = {
    "learning_candidate_created",
    "learning_candidate_revised",
    "learning_candidate_dependency_resolved",
    "learning_candidate_confirmed",
    "learning_candidate_promoted",
    "learning_candidate_rejected",
    "learning_candidate_invalidated",
}

_WORKBOOK_SUFFIXES = (
    ".xlsx", ".xlsm", ".xlsb", ".xls", ".csv", ".tsv", ".parquet",
)
_DOCUMENT_SUFFIXES = (
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".eml",
)

_ATTACHMENT_RE = re.compile(
    r"\b(attached|attachment|attachments|enclosed)\b", re.IGNORECASE)
_PREVIOUS_RE = re.compile(
    r"\b(previous|earlier|last)\s+(message|email|workbook|file|spreadsheet|"
    r"attachment)\b", re.IGNORECASE)
_METHOD_RE = re.compile(
    r"\b(same|usual|standard|approved)\s+(approach|method|way|calculation|"
    r"formula|process)\b|\blike\s+last\s+time\b|\bdo\s+it\s+like\b",
    re.IGNORECASE)
_SUPERSEDES_RE = re.compile(
    r"\b(supersedes?|revised|updated|newest|new\s+version|latest\s+version)\b",
    re.IGNORECASE)
_EXAMPLE_RE = re.compile(
    r"\b(for\s+example|e\.g\.|example|sample)\b", re.IGNORECASE)
_POLICY_RE = re.compile(
    r"\b(approved|current|official|standing)\s+"
    r"(rates?|prices?|schedule|policy|method)\b", re.IGNORECASE)
_QUOTE_SPLIT_RE = re.compile(
    r"(?im)^(?:-{2,}\s*original message\s*-{2,}|on .+ wrote:|from:\s+.+)$")
_PERMISSION_EXPANSION_RE = re.compile(
    r"\b(?:grant|give|allow|enable)\b.{0,60}\b(?:admin|administrator|root|"
    r"superuser|access|permission|approval)\b|"
    r"\b(?:disable|bypass|skip)\b.{0,60}\b(?:approval|review|policy|"
    r"security|guard)\b",
    re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: Any, limit: int = 2000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _norm(value: Any) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def split_authored_quoted(body: str) -> Tuple[str, str]:
    """Split an email body into authored and quoted text.

    Quoted text is never teaching authority. The split is deliberately
    conservative: a reply header or a ``>`` block starts the quoted tail.
    """
    text = str(body or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return "", ""
    match = _QUOTE_SPLIT_RE.search(text)
    if match:
        authored = text[:match.start()].strip()
        quoted = text[match.start():].strip()
        return authored, quoted
    lines = text.splitlines()
    authored_lines: List[str] = []
    quoted_lines: List[str] = []
    in_quote = False
    for line in lines:
        if line.lstrip().startswith(">"):
            in_quote = True
            quoted_lines.append(line.lstrip()[1:].lstrip())
        elif in_quote and not line.strip():
            quoted_lines.append("")
        elif in_quote:
            quoted_lines.append(line)
        else:
            authored_lines.append(line)
    return "\n".join(authored_lines).strip(), "\n".join(quoted_lines).strip()


class AttachmentEvidence(BaseModel):
    attachment_id: str
    provider: str = ""
    message_id: str = ""
    filename: str = ""
    content_type: str = ""
    size: int = 0
    sha256: str = ""
    resource_id: Optional[str] = None
    ingestion_status: str = "unknown"
    inline: bool = False


class MessageEvidence(BaseModel):
    message_id: str
    provider: str = ""
    revision: str = ""
    content_sha256: str = ""
    mailbox_owner: str = ""
    sender: str = ""
    recipients: List[str] = Field(default_factory=list)
    cc: List[str] = Field(default_factory=list)
    sent_at: str = ""
    received_at: str = ""
    body: str = ""
    authored_segments: List[str] = Field(default_factory=list)
    quoted_segments: List[str] = Field(default_factory=list)
    attachments: List[AttachmentEvidence] = Field(default_factory=list)
    reply_to_message_id: str = ""
    references: List[str] = Field(default_factory=list)
    source_access_status: str = "available"

    @model_validator(mode="after")
    def _derive_segments(self):
        if not self.authored_segments and self.body:
            authored, quoted = split_authored_quoted(self.body)
            self.authored_segments = [authored] if authored else []
            if not self.quoted_segments and quoted:
                self.quoted_segments = [quoted]
        if not self.content_sha256 and self.body:
            self.content_sha256 = hashlib.sha256(
                self.body.encode("utf-8")).hexdigest()
        if not self.revision and self.content_sha256:
            self.revision = self.content_sha256[:16]
        return self

    @property
    def authored_text(self) -> str:
        return "\n".join(self.authored_segments).strip()

    @property
    def quoted_text(self) -> str:
        return "\n".join(self.quoted_segments).strip()


class ResourceBinding(BaseModel):
    resource_id: str
    dataset_name: str = ""
    source: str = ""
    source_kind: str = ""
    external_id: str = ""
    original_file_name: str = ""
    representation: str = ""
    source_version: str = ""
    sheet: str = ""
    locator: Dict[str, Any] = Field(default_factory=dict)
    columns: List[str] = Field(default_factory=list)
    numeric_columns: List[str] = Field(default_factory=list)
    row_count: Optional[int] = None
    coverage: Dict[str, Any] = Field(default_factory=dict)
    access_scope: Dict[str, Any] = Field(default_factory=dict)
    workspace_id: str = ""
    tenant_id: str = ""
    status: str = "active"
    internal_fixture: bool = False

    @classmethod
    def from_source(cls, source: Dict[str, Any]) -> "ResourceBinding":
        from core.assignment_resources import resource_binding

        return cls.model_validate(resource_binding(source))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class ReferenceEdge(BaseModel):
    edge_id: str = ""
    origin_message_id: str
    origin_span: str = ""
    reference_text: str
    relation: str = "context"
    resolution_status: str = "missing"
    target_binding: Optional[ResourceBinding] = None
    candidates: List[ResourceBinding] = Field(default_factory=list)
    resolution_basis: Optional[str] = None
    confirmed_by: Optional[str] = None
    detail: str = ""

    @model_validator(mode="after")
    def _defaults(self):
        if self.relation not in REFERENCE_RELATIONS:
            self.relation = "context"
        if self.resolution_status not in RESOLUTION_STATUSES:
            self.resolution_status = "missing"
        if not self.edge_id:
            self.edge_id = edge_key(self)
        return self


def edge_key(edge: ReferenceEdge | Dict[str, Any]) -> str:
    if isinstance(edge, ReferenceEdge):
        message_id = edge.origin_message_id
        span = edge.origin_span
        relation = edge.relation
        text = edge.reference_text
    else:
        message_id = str(edge.get("origin_message_id") or "")
        span = str(edge.get("origin_span") or "")
        relation = str(edge.get("relation") or "context")
        text = str(edge.get("reference_text") or "")
    raw = f"{message_id}|{span}|{relation}|{_norm(text)}"
    return "ref-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class EvidenceCoverage(BaseModel):
    messages_known: bool = True
    messages_truncated: bool = False
    attachments_complete: bool = True
    resources_known: bool = True
    source_access: str = "available"
    message_count: int = 0
    max_reference_depth: int = 1
    depth_reached: int = 0
    message_limit: int = 200
    resource_limit: int = 400
    cycles_detected: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ConversationEvidence(BaseModel):
    schema_version: str = SCHEMA_VERSION
    workspace_id: str
    tenant_id: str = ""
    account_id: str = ""
    thread_id: str
    messages: List[MessageEvidence] = Field(default_factory=list)
    resources: List[ResourceBinding] = Field(default_factory=list)
    references: List[ReferenceEdge] = Field(default_factory=list)
    coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)
    built_at: str = Field(default_factory=_now_iso)


class MethodInput(BaseModel):
    concept: str
    column: str = ""
    unit: str = ""
    unit_required: bool = True
    required: bool = True


class MethodSpec(BaseModel):
    intended_outcome: str = ""
    operation: str = ""
    inputs: List[MethodInput] = Field(default_factory=list)
    output_unit: str = ""
    transformation: str = ""
    decision_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)
    output_requirements: Dict[str, Any] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)
    rounding: Dict[str, Any] = Field(default_factory=dict)


class LearningDependency(BaseModel):
    dependency_id: str
    kind: str
    required: bool = True
    status: str = "missing"
    binding: Optional[ResourceBinding] = None
    question: str = ""
    detail: str = ""
    edge_id: str = ""
    concept: str = ""

    @model_validator(mode="after")
    def _defaults(self):
        if self.status not in DEPENDENCY_STATUSES:
            self.status = "missing"
        if not self.dependency_id:
            raw = f"{self.kind}|{self.status}|{self.question}"
            self.dependency_id = "dep-" + hashlib.sha256(
                raw.encode("utf-8")).hexdigest()[:16]
        return self


class LearningCandidate(BaseModel):
    schema_version: str = SCHEMA_VERSION
    candidate_id: str
    workspace_id: str
    tenant_id: str = ""
    agent_id: str
    thread_id: str
    proposed_lesson: str
    intended_outcome: str = ""
    applies_to: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    method: MethodSpec = Field(default_factory=MethodSpec)
    method_status: str = "unresolved"
    dependencies: List[LearningDependency] = Field(default_factory=list)
    references: List[ReferenceEdge] = Field(default_factory=list)
    evidence_message_ids: List[str] = Field(default_factory=list)
    evidence_resource_ids: List[str] = Field(default_factory=list)
    evidence_coverage: Dict[str, Any] = Field(default_factory=dict)
    authority_message_id: str = ""
    authority_excerpt: str = ""
    status: str = "draft"
    revision: int = 1
    digest: str = ""
    created_by: str = ""
    created_at: str = Field(default_factory=_now_iso)
    confirmed_by: Optional[str] = None
    confirmed_revision: Optional[int] = None
    confirmed_digest: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_reason: str = ""
    promoted_entry_id: Optional[str] = None
    invalidated_reason: str = ""

    @model_validator(mode="after")
    def _defaults(self):
        if self.method_status not in METHOD_STATUSES:
            self.method_status = "unresolved"
        if self.status not in CANDIDATE_STATUSES:
            self.status = "draft"
        return self

    def review_payload(self) -> Dict[str, Any]:
        return review_payload(self)


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------

def _in_scope(resource: ResourceBinding, workspace_id: str,
              tenant_id: str) -> bool:
    scope = resource.access_scope or {}
    resource_workspace = (
        resource.workspace_id or scope.get("workspace_id") or "")
    resource_tenant = resource.tenant_id or scope.get("tenant_id") or ""
    if resource_workspace and str(resource_workspace) != str(workspace_id):
        return False
    if resource_tenant and str(resource_tenant) != str(tenant_id):
        return False
    return True


def _resource_unavailable_reason(resource: ResourceBinding) -> Optional[str]:
    if str(resource.status or "active") not in ("active", "current"):
        return "stale"
    coverage = resource.coverage or {}
    if coverage.get("known") is False or coverage.get("truncated") is True:
        return "incomplete"
    if not str(resource.source_version or "").strip():
        return "incomplete"
    return None


def _candidate_payload(resource: ResourceBinding) -> Dict[str, Any]:
    return {
        "resource_id": resource.resource_id,
        "dataset_name": resource.dataset_name,
        "original_file_name": resource.original_file_name,
        "sheet": resource.sheet,
        "locator": resource.locator,
        "source_version": resource.source_version,
        "status": resource.status,
        "workspace_id": resource.workspace_id,
        "tenant_id": resource.tenant_id,
    }


def _find_by_attachment(
    attachment: AttachmentEvidence,
    catalog: Sequence[ResourceBinding],
) -> List[ResourceBinding]:
    """All catalog rows matching an attachment identity.

    Provider ids win; a filename is only a name, so every same-name catalog
    row is returned and the caller must treat more than one as ambiguous.
    """
    external = f"{attachment.message_id}:{attachment.attachment_id}"
    exact: List[ResourceBinding] = []
    for resource in catalog:
        if attachment.resource_id and str(resource.resource_id) == str(
                attachment.resource_id):
            exact.append(resource)
        elif str(resource.external_id or "") == external:
            exact.append(resource)
    if exact:
        return exact
    return [
        resource for resource in catalog
        if attachment.filename
        and _norm(resource.original_file_name) == _norm(attachment.filename)
    ]


def _attachment_candidates(
    attachments: Sequence[AttachmentEvidence],
    catalog: Sequence[ResourceBinding],
    *,
    workspace_id: str,
    tenant_id: str,
) -> List[ResourceBinding]:
    out: List[ResourceBinding] = []
    for attachment in attachments:
        for resource in _find_by_attachment(attachment, catalog):
            if _in_scope(resource, workspace_id, tenant_id):
                out.append(resource)
    return out


def _named_matches(
    text: str,
    catalog: Sequence[ResourceBinding],
) -> List[ResourceBinding]:
    """Exact identity mentions only.

    Punctuation is part of an identifier: ``rates-2026.xlsx`` is not the same
    name as ``rates 2026.xlsx``. Fuzzy similarity is deliberately absent —
    an uncertain name stays unresolved rather than silently binding.
    """
    lowered = str(text or "").lower()
    file_tokens = re.findall(
        r"[^\s/\\]+\.(?:xlsx|xlsm|xlsb|xls|csv|tsv|parquet|pdf|docx?)"
        r"(?![\w])", lowered, re.IGNORECASE)
    out: List[ResourceBinding] = []
    if file_tokens:
        # A filename mention is a file identity, not a sheet-name cue. The
        # punctuation must match exactly; no fuzzy fallback.
        for resource in catalog:
            name = str(resource.original_file_name or "").strip().lower()
            if name and name in file_tokens:
                out.append(resource)
        return out
    for resource in catalog:
        names = [
            resource.resource_id,
            resource.external_id,
            resource.dataset_name,
            resource.sheet,
        ]
        for name in names:
            value = str(name or "").strip()
            if not value:
                continue
            pattern = re.compile(
                rf"(?<![A-Za-z0-9]){re.escape(value.lower())}"
                rf"(?![A-Za-z0-9])", re.IGNORECASE)
            if pattern.search(lowered):
                out.append(resource)
                break
    return out


def _set_edge(
    edge: ReferenceEdge,
    *,
    status: str,
    binding: Optional[ResourceBinding] = None,
    candidates: Optional[Sequence[ResourceBinding]] = None,
    basis: Optional[str] = None,
    detail: str = "",
    confirmed_by: Optional[str] = None,
) -> ReferenceEdge:
    edge.resolution_status = status
    edge.target_binding = binding
    edge.candidates = list(candidates or [])
    edge.resolution_basis = basis
    edge.detail = _bounded(detail, 500)
    edge.confirmed_by = confirmed_by
    return edge


def _resolve_named_edge(
    edge: ReferenceEdge,
    catalog: Sequence[ResourceBinding],
    *,
    workspace_id: str,
    tenant_id: str,
) -> ReferenceEdge:
    matches = _named_matches(edge.reference_text, catalog)
    if not matches:
        return _set_edge(
            edge, status="missing", basis="no_catalog_match",
            detail="No catalog resource matches the reference text.")
    in_scope = [r for r in matches if _in_scope(r, workspace_id, tenant_id)]
    if not in_scope:
        return _set_edge(
            edge, status="access_denied", basis="outside_authenticated_scope",
            candidates=[], detail="The referenced resource is outside the "
            "requesting user's workspace/tenant scope.")
    active = [r for r in in_scope if str(r.status or "active") == "active"]
    pool = active or in_scope
    distinct = {str(r.resource_id): r for r in pool}
    if len(distinct) > 1:
        return _set_edge(
            edge, status="ambiguous", basis="multiple_catalog_matches",
            candidates=list(distinct.values()),
            detail="More than one active resource matches this reference.")
    resource = next(iter(distinct.values()))
    unavailable = _resource_unavailable_reason(resource)
    if unavailable:
        return _set_edge(
            edge, status=unavailable, binding=resource,
            basis="catalog_match_unavailable",
            detail="The matched resource is not usable as current evidence.")
    return _set_edge(
        edge, status="resolved", binding=resource,
        basis="catalog_exact_name",
        detail="Resolved by exact catalog name inside the authenticated scope.")


def _resolve_attachment_edge(
    edge: ReferenceEdge,
    message: MessageEvidence,
    messages: Sequence[MessageEvidence],
    catalog: Sequence[ResourceBinding],
    *,
    workspace_id: str,
    tenant_id: str,
) -> ReferenceEdge:
    text_norm = _norm(edge.reference_text)
    origin_attachments = list(message.attachments)
    if any(token in text_norm for token in ("previous", "earlier", "last")):
        prior: List[AttachmentEvidence] = []
        for item in messages:
            if item.message_id == message.message_id:
                break
            prior.extend(item.attachments)
        origin_attachments = prior
    named = [
        item for item in origin_attachments
        if _norm(item.filename) and _norm(item.filename) in text_norm
    ]
    attachments = named or origin_attachments
    if not attachments:
        return _set_edge(
            edge, status="missing", basis="no_attachment_in_message",
            detail="The message names an attachment but carries none.")
    resources = _attachment_candidates(
        attachments, catalog, workspace_id=workspace_id, tenant_id=tenant_id)
    distinct = {str(r.resource_id): r for r in resources}
    if len(distinct) > 1:
        return _set_edge(
            edge, status="ambiguous", basis="multiple_attachments",
            candidates=list(distinct.values()),
            detail="More than one attachment could be the referent.")
    if not distinct:
        # An attachment that was never materialized into the catalog is not
        # evidence. It stays incomplete with a concrete next step.
        return _set_edge(
            edge, status="incomplete", basis="attachment_not_materialized",
            detail="The attachment exists in the message but has no catalog "
                   "binding; materialize it before using it as evidence.")
    resource = next(iter(distinct.values()))
    unavailable = _resource_unavailable_reason(resource)
    if unavailable:
        return _set_edge(
            edge, status=unavailable, binding=resource,
            basis="attachment_unavailable",
            detail="The attached resource is not usable as current evidence.")
    return _set_edge(
        edge, status="resolved", binding=resource,
        basis="provider_attachment_id",
        detail="Resolved through the provider attachment identity.")


def _resolve_previous_edge(
    edge: ReferenceEdge,
    message: MessageEvidence,
    messages: Sequence[MessageEvidence],
    catalog: Sequence[ResourceBinding],
    *,
    workspace_id: str,
    tenant_id: str,
) -> ReferenceEdge:
    prior_messages = []
    for item in messages:
        if item.message_id == message.message_id:
            break
        prior_messages.append(item)
    attachments = [a for item in prior_messages for a in item.attachments]
    resources = _attachment_candidates(
        attachments, catalog, workspace_id=workspace_id, tenant_id=tenant_id)
    for item in prior_messages:
        for resource in _named_matches(item.authored_text, catalog):
            if _in_scope(resource, workspace_id, tenant_id):
                resources.append(resource)
    distinct = {str(r.resource_id): r for r in resources}
    if len(distinct) == 1:
        resource = next(iter(distinct.values()))
        unavailable = _resource_unavailable_reason(resource)
        if unavailable:
            return _set_edge(
                edge, status=unavailable, binding=resource,
                basis="thread_prior_resource_unavailable",
                detail="The prior resource is no longer current.")
        return _set_edge(
            edge, status="resolved", binding=resource,
            basis="thread_prior_resource",
            detail="Resolved to the only prior resource in the thread.")
    if len(distinct) > 1:
        return _set_edge(
            edge, status="ambiguous", basis="multiple_prior_resources",
            candidates=list(distinct.values()),
            detail="More than one prior resource could be the referent.")
    return _set_edge(
        edge, status="missing", basis="no_prior_resource",
        detail="No prior workbook or attachment exists in this thread.")


def _resolve_edge(
    edge: ReferenceEdge,
    message: MessageEvidence,
    messages: Sequence[MessageEvidence],
    catalog: Sequence[ResourceBinding],
    *,
    workspace_id: str,
    tenant_id: str,
    confirmed_targets: Dict[str, str],
) -> ReferenceEdge:
    confirmed = (
        confirmed_targets.get(edge.edge_id)
        or confirmed_targets.get(edge_key(edge))
    )
    if confirmed:
        target = next(
            (r for r in catalog if str(r.resource_id) == str(confirmed)),
            None)
        if target is None:
            return _set_edge(
                edge, status="missing", basis="confirmed_target_not_found",
                detail="The confirmed resource no longer exists.")
        if not _in_scope(target, workspace_id, tenant_id):
            return _set_edge(
                edge, status="access_denied",
                basis="confirmed_target_outside_scope",
                detail="The confirmed resource is outside the authenticated "
                       "scope.")
        unavailable = _resource_unavailable_reason(target)
        if unavailable:
            return _set_edge(
                edge, status=unavailable, binding=target,
                basis="confirmed_target_unavailable",
                detail="The confirmed resource is not current evidence.")
        return _set_edge(
            edge, status="resolved", binding=target,
            basis="user_confirmed", confirmed_by="user",
            detail="Resolved by explicit user confirmation.")

    if edge.relation in ("example", "supersedes",
                         "calculation_input", "policy_reference"):
        named = _resolve_named_edge(
            edge, catalog, workspace_id=workspace_id, tenant_id=tenant_id)
        if named.resolution_status != "missing":
            return named
        if message.attachments:
            resolved = _resolve_attachment_edge(
                edge, message, messages, catalog,
                workspace_id=workspace_id, tenant_id=tenant_id)
            if resolved.resolution_status != "missing":
                return resolved
        if any(token in _norm(edge.reference_text)
               for token in ("previous", "earlier", "last")):
            return _resolve_previous_edge(
                edge, message, messages, catalog,
                workspace_id=workspace_id, tenant_id=tenant_id)
        return named

    if edge.relation == "attachment":
        if message.attachments:
            resolved = _resolve_attachment_edge(
                edge, message, messages, catalog,
                workspace_id=workspace_id, tenant_id=tenant_id)
            if resolved.resolution_status != "missing":
                return resolved
        if any(token in _norm(edge.reference_text)
               for token in ("previous", "earlier", "last")):
            return _resolve_previous_edge(
                edge, message, messages, catalog,
                workspace_id=workspace_id, tenant_id=tenant_id)
        return _resolve_named_edge(
            edge, catalog, workspace_id=workspace_id, tenant_id=tenant_id)

    if edge.relation == "method_reference":
        return _set_edge(
            edge, status="missing", basis="method_not_established",
            detail="A method reference is not executable until the user "
                   "confirms which method and resource it means.")

    return _resolve_named_edge(
        edge, catalog, workspace_id=workspace_id, tenant_id=tenant_id)


def _detect_message_edges(message: MessageEvidence) -> List[ReferenceEdge]:
    text = message.authored_text
    if not text:
        return []
    edges: List[ReferenceEdge] = []

    def add(pattern: re.Pattern, relation: str) -> None:
        for match in pattern.finditer(text):
            edges.append(ReferenceEdge(
                origin_message_id=message.message_id,
                origin_span=f"{match.start()}:{match.end()}",
                reference_text=match.group(0),
                relation=relation,
            ))

    add(_ATTACHMENT_RE, "attachment")
    add(_PREVIOUS_RE, "attachment")
    add(_METHOD_RE, "method_reference")
    add(_SUPERSEDES_RE, "supersedes")
    add(_EXAMPLE_RE, "example")
    add(_POLICY_RE, "policy_reference")
    # Deduplicate by relation + normalized text + span.
    seen: set = set()
    out: List[ReferenceEdge] = []
    for edge in edges:
        key = (edge.relation, _norm(edge.reference_text), edge.origin_span)
        if key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out


def resolve_reference_edges(
    evidence: ConversationEvidence,
    catalog: Sequence[ResourceBinding | Dict[str, Any]],
    *,
    confirmed_targets: Optional[Dict[str, str]] = None,
) -> ConversationEvidence:
    """Resolve authored references against the authorized catalog.

    Order is identity-first: provider attachment ids, exact catalog refs,
    exact names inside the authenticated scope, then contextual candidates.
    Ambiguity is never resolved by recency or similarity.
    """
    resources = [
        item if isinstance(item, ResourceBinding)
        else ResourceBinding.model_validate(item)
        for item in (catalog or [])
    ]
    targets = dict(confirmed_targets or {})
    messages = list(evidence.messages)
    edges: List[ReferenceEdge] = []
    for message in messages:
        detected = _detect_message_edges(message)
        # Named catalog resources are explicit identity mentions. They are
        # added as edges so the review can show the exact binding.
        for resource in _named_matches(message.authored_text, resources):
            for name in (
                resource.original_file_name,
                resource.dataset_name,
                resource.sheet,
            ):
                if not name:
                    continue
                pattern = re.compile(
                    rf"(?<![A-Za-z0-9]){re.escape(str(name))}"
                    rf"(?![A-Za-z0-9])", re.IGNORECASE)
                match = pattern.search(message.authored_text)
                if match:
                    detected.append(ReferenceEdge(
                        origin_message_id=message.message_id,
                        origin_span=f"{match.start()}:{match.end()}",
                        reference_text=match.group(0),
                        relation="calculation_input",
                    ))
                    break
        # Resolve in message order; prior resources are visible to later
        # messages through the already-built message list.
        for edge in detected:
            edges.append(_resolve_edge(
                edge, message, messages, resources,
                workspace_id=evidence.workspace_id,
                tenant_id=evidence.tenant_id or evidence.workspace_id,
                confirmed_targets=targets,
            ))
    # A repeated reference to the same resource is not a conflict; two
    # different targets for the same normalized reference are.
    grouped: Dict[Tuple[str, str], List[ReferenceEdge]] = {}
    for edge in edges:
        grouped.setdefault((_norm(edge.reference_text), edge.relation), []).append(
            edge)
    for group in grouped.values():
        resolved_ids = {
            str(edge.target_binding.resource_id)
            for edge in group
            if edge.target_binding is not None
        }
        if len(resolved_ids) > 1:
            for edge in group:
                edge.resolution_status = "conflicting"
                edge.detail = (
                    "The same reference resolves to different resources in "
                    "this thread.")
    return evidence.model_copy(update={"references": edges})


# ---------------------------------------------------------------------------
# Dependencies, readiness and methods
# ---------------------------------------------------------------------------

def _dependency_question(kind: str, status: str, edge: ReferenceEdge) -> str:
    if status == "ambiguous":
        return (
            f"Which resource did '{edge.reference_text}' mean? "
            "Choose one of the listed candidates.")
    if status == "access_denied":
        return (
            f"The resource for '{edge.reference_text}' is not available to "
            "this user. Choose an authorized resource or ask for access.")
    if status == "stale":
        return (
            f"The resource for '{edge.reference_text}' has a newer version. "
            "Choose the current version and confirm the method again.")
    if status == "incomplete":
        return (
            f"The resource for '{edge.reference_text}' is not complete or not "
            "materialized. Supply the missing evidence before promotion.")
    if kind == "method_reference":
        return (
            f"What method does '{edge.reference_text}' refer to? State the "
            "inputs, calculation and exceptions explicitly.")
    return (
        f"Which resource did '{edge.reference_text}' mean? No authorized "
        "catalog resource matched it.")


def validate_method(method: MethodSpec) -> List[Dict[str, str]]:
    """Return explicit method issues; never infer a missing behavior."""
    issues: List[Dict[str, str]] = []
    if not _bounded(method.intended_outcome):
        issues.append({
            "kind": "method",
            "status": "missing",
            "question": "What outcome should this method produce?",
        })
    if not _bounded(method.operation):
        issues.append({
            "kind": "method",
            "status": "missing",
            "question": "Which calculation or decision operation is intended?",
        })
    elif method.operation not in {
            "sum", "count", "multiply_sum", "percentage", "ratio"}:
        issues.append({
            "kind": "method",
            "status": "ambiguous",
            "question": (
                f"The operation '{method.operation}' is not a supported "
                "explicit operation. State one of: sum, count, multiply_sum, "
                "percentage, ratio."),
        })
    if not method.inputs:
        issues.append({
            "kind": "method",
            "status": "missing",
            "question": "Which inputs does the method require?",
        })
    for item in method.inputs:
        if not _bounded(item.concept):
            issues.append({
                "kind": "method",
                "status": "incomplete",
                "question": "An input is missing its semantic concept.",
            })
        if item.unit_required and not _bounded(item.unit):
            issues.append({
                "kind": "unit",
                "status": "missing",
                "concept": item.concept,
                "question": (
                    f"What unit does input '{item.concept}' use? A numerical "
                    "conclusion is blocked until the unit is explicit."),
            })
    if method.operation in {"multiply_sum", "percentage", "ratio"} and not (
            _bounded(method.transformation) or method.assumptions):
        issues.append({
            "kind": "method",
            "status": "incomplete",
            "question": (
                "State the transformation or its assumptions explicitly; "
                "the operation alone does not establish the method."),
        })
    return issues


def derive_dependencies(candidate: LearningCandidate) -> List[LearningDependency]:
    deps: List[LearningDependency] = []
    seen: set = set()

    def add(kind: str, status: str, question: str,
            binding: Optional[ResourceBinding] = None,
            detail: str = "", edge_id: str = "",
            concept: str = "") -> None:
        key = (kind, status, _norm(question), str(
            binding.resource_id) if binding else "", edge_id, concept)
        if key in seen:
            return
        seen.add(key)
        deps.append(LearningDependency(
            dependency_id="",
            kind=kind,
            required=True,
            status=status,
            binding=binding,
            question=question,
            detail=detail,
            edge_id=edge_id,
            concept=concept,
        ))

    for edge in candidate.references:
        if edge.resolution_status == "resolved":
            continue
        add(
            edge.relation,
            edge.resolution_status,
            _dependency_question(edge.relation, edge.resolution_status, edge),
            binding=edge.target_binding,
            detail=edge.detail,
            edge_id=edge.edge_id,
        )

    if candidate.method_status != "explicit":
        status = (
            "missing" if candidate.method_status == "unresolved"
            else "ambiguous")
        add(
            "method",
            status,
            "The governing method is not explicit. Confirm the inputs, "
            "calculation, conditions and exceptions before promotion.",
        )

    for issue in validate_method(candidate.method):
        add(
            issue["kind"], issue["status"], issue["question"],
            concept=str(issue.get("concept") or ""))

    if not candidate.authority_message_id:
        add(
            "authority",
            "missing",
            "Which authored message authorizes this lesson? Quoted text and "
            "source content are not teaching authority.",
        )

    if not candidate.applies_to and not candidate.context:
        add(
            "applicability",
            "missing",
            "Where does this lesson apply? State the task, output, topic or "
            "context conditions.",
        )

    for key, value in (candidate.context or {}).items():
        if isinstance(value, dict) and "value" in value:
            field = _bounded(value.get("field"))
            if not field:
                add(
                    "mapping",
                    "missing",
                    f"Which dataset field or value identifies "
                    f"'{key}' = '{_bounded(value.get('value'), 120)}'?",
                )
        elif isinstance(value, str) and value.strip().lower() in {
                "northern", "southern", "regional", "north", "south"}:
            add(
                "mapping",
                "missing",
                f"Which dataset field/value defines '{value}' for '{key}'?",
            )

    # Conflicting references for the same text are a blocking dependency.
    by_ref: Dict[Tuple[str, str], set] = {}
    for edge in candidate.references:
        if edge.target_binding is None:
            continue
        by_ref.setdefault(
            (_norm(edge.reference_text), edge.relation), set()).add(
                str(edge.target_binding.resource_id))
    for (text, relation), ids in by_ref.items():
        if len(ids) > 1:
            add(
                "conflict",
                "conflicting",
                f"The reference '{text}' resolves to different resources; "
                "choose one before promotion.",
            )

    return deps


def candidate_readiness(candidate: LearningCandidate) -> Dict[str, Any]:
    dependencies = derive_dependencies(candidate)
    blocking = [
        dep for dep in dependencies
        if dep.required and dep.status not in ("resolved", "not_applicable")
    ]
    review_ready = (
        not blocking
        and candidate.method_status == "explicit"
        and bool(candidate.applies_to or candidate.context)
        and candidate.status not in ("rejected", "invalidated")
    )
    if candidate.status in ("rejected", "invalidated"):
        status = candidate.status
    elif review_ready:
        status = "review_ready"
    elif blocking:
        status = "needs_clarification"
    else:
        status = "draft"
    return {
        "review_ready": review_ready,
        "status": status,
        "dependencies": dependencies,
        "blocking": blocking,
    }


def _candidate_digest(candidate: LearningCandidate) -> str:
    payload = {
        "schema": SCHEMA_VERSION,
        "candidate_id": candidate.candidate_id,
        "revision": candidate.revision,
        "agent_id": candidate.agent_id,
        "thread_id": candidate.thread_id,
        "proposed_lesson": candidate.proposed_lesson,
        "intended_outcome": candidate.intended_outcome,
        "authority_message_id": candidate.authority_message_id,
        "authority_excerpt": candidate.authority_excerpt,
        "applies_to": list(candidate.applies_to),
        "context": candidate.context,
        "method": candidate.method.model_dump(mode="json"),
        "method_status": candidate.method_status,
        "references": [
            {
                "edge_id": edge.edge_id,
                "origin_message_id": edge.origin_message_id,
                "origin_span": edge.origin_span,
                "reference_text": edge.reference_text,
                "relation": edge.relation,
                "resolution_status": edge.resolution_status,
                "target_resource_id": (
                    edge.target_binding.resource_id
                    if edge.target_binding else None),
                "target_source_version": (
                    edge.target_binding.source_version
                    if edge.target_binding else None),
            }
            for edge in candidate.references
        ],
        "dependencies": [
            {
                "dependency_id": dep.dependency_id,
                "kind": dep.kind,
                "required": dep.required,
                "status": dep.status,
                "binding_resource_id": (
                    dep.binding.resource_id if dep.binding else None),
                "question": dep.question,
            }
            for dep in candidate.dependencies
        ],
    }
    return canonical_sha256(payload)


def refresh_candidate(candidate: LearningCandidate) -> LearningCandidate:
    readiness = candidate_readiness(candidate)
    candidate.dependencies = readiness["dependencies"]
    candidate.status = readiness["status"]
    candidate.digest = _candidate_digest(candidate)
    return candidate


def validate_authority(
    evidence: ConversationEvidence,
    *,
    message_id: str,
    excerpt: str = "",
    proposed_lesson: str = "",
) -> MessageEvidence:
    """The authority must come from an authored, accessible message segment.

    Quoted text and resource content are evidence, never a teaching grant.
    A lesson that expands permissions must itself be stated in the authored
    authority excerpt; a source document cannot grant it.
    """
    message = next(
        (item for item in evidence.messages
         if item.message_id == str(message_id or "")), None)
    if message is None:
        raise ValueError("authority_message_not_found")
    if message.source_access_status != "available":
        raise ValueError("authority_message_unavailable")
    wanted = _bounded(excerpt, 500)
    lesson = _bounded(proposed_lesson, 2000)
    if lesson and _PERMISSION_EXPANSION_RE.search(lesson):
        if not wanted or not _PERMISSION_EXPANSION_RE.search(wanted):
            raise ValueError("authority_cannot_expand_permissions")
    if not wanted:
        return message
    if wanted in message.authored_text:
        return message
    if wanted in message.quoted_text:
        raise ValueError("authority_is_quoted")
    raise ValueError("authority_excerpt_not_in_authored_segment")


def build_candidate(
    *,
    workspace_id: str,
    tenant_id: str,
    agent_id: str,
    thread_id: str,
    proposed_lesson: str,
    method: Optional[MethodSpec | Dict[str, Any]] = None,
    method_status: str = "unresolved",
    applies_to: Optional[Sequence[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    evidence: Optional[ConversationEvidence] = None,
    references: Optional[Sequence[ReferenceEdge | Dict[str, Any]]] = None,
    authority_message_id: str = "",
    authority_excerpt: str = "",
    created_by: str = "",
    candidate_id: Optional[str] = None,
) -> LearningCandidate:
    if authority_message_id and evidence is None:
        raise ValueError("authority_evidence_required")
    if evidence is not None and not authority_message_id:
        # The authority is the most recent authored segment, never a quoted
        # tail. A thread with only quoted content has no authority.
        authority_message_id = next(
            (message.message_id for message in reversed(evidence.messages)
             if message.authored_text), "")
    if evidence is not None and authority_message_id:
        validate_authority(
            evidence, message_id=authority_message_id,
            excerpt=authority_excerpt,
            proposed_lesson=proposed_lesson)
    method_model = (
        method if isinstance(method, MethodSpec)
        else MethodSpec.model_validate(method or {}))
    candidate = LearningCandidate(
        candidate_id=candidate_id or f"lc-{uuid.uuid4().hex[:16]}",
        workspace_id=str(workspace_id or ""),
        tenant_id=str(tenant_id or ""),
        agent_id=str(agent_id or ""),
        thread_id=str(thread_id or ""),
        proposed_lesson=_bounded(proposed_lesson, 2000),
        intended_outcome=_bounded(
            method_model.intended_outcome or proposed_lesson, 500),
        applies_to=[_bounded(item, 80) for item in (applies_to or []) if
                    _bounded(item, 80)],
        context=dict(context or {}),
        method=method_model,
        method_status=method_status,
        references=[
            item if isinstance(item, ReferenceEdge)
            else ReferenceEdge.model_validate(item)
            for item in (
                references if references is not None
                else (evidence.references if evidence else []))
        ],
        evidence_message_ids=[
            message.message_id for message in (evidence.messages if evidence
                                               else [])
        ],
        evidence_resource_ids=[
            resource.resource_id for resource in (evidence.resources if evidence
                                                  else [])
        ],
        evidence_coverage=(
            evidence.coverage.model_dump(mode="json") if evidence else {}),
        authority_message_id=str(authority_message_id or ""),
        authority_excerpt=_bounded(authority_excerpt, 500),
        created_by=str(created_by or ""),
    )
    return refresh_candidate(candidate)


# ---------------------------------------------------------------------------
# Durable candidate ledger (reuses ConversationEvent, no new table)
# ---------------------------------------------------------------------------

def _event_payload(candidate: LearningCandidate,
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {"candidate": candidate.model_dump(mode="json")}
    if extra:
        payload.update(extra)
    return payload


def _append_candidate_event(
    db: Session,
    kind: str,
    candidate: LearningCandidate,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    from core.models import ConversationEvent

    row = ConversationEvent(
        conversation_id=str(candidate.thread_id or ""),
        kind=kind,
        payload_json=json.dumps(
            _event_payload(candidate, extra), default=str),
        workspace_id=candidate.workspace_id or None,
        tenant_id=candidate.tenant_id or None,
    )
    db.add(row)
    db.commit()
    return str(row.id)


def save_candidate(
    db: Session,
    candidate: LearningCandidate,
    *,
    kind: str = "learning_candidate_created",
) -> LearningCandidate:
    candidate = refresh_candidate(candidate)
    _append_candidate_event(db, kind, candidate)
    return candidate


def load_candidate(
    db: Session,
    thread_id: str,
    candidate_id: str,
) -> Optional[LearningCandidate]:
    from core.models import ConversationEvent

    rows = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == str(thread_id or ""),
            ConversationEvent.kind.in_(sorted(_LEARNING_EVENT_KINDS)),
        )
        .order_by(ConversationEvent.created_at.asc(),
                  ConversationEvent.id.asc())
        .limit(500)
        .all()
    )
    latest: Optional[LearningCandidate] = None
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except (TypeError, ValueError):
            continue
        raw = payload.get("candidate")
        if not isinstance(raw, dict):
            continue
        if str(raw.get("candidate_id") or "") != str(candidate_id or ""):
            continue
        try:
            latest = LearningCandidate.model_validate(raw)
        except Exception:
            continue
    return latest


def list_candidates(
    db: Session,
    thread_id: str,
    *,
    workspace_id: str = "",
    tenant_id: str = "",
) -> List[LearningCandidate]:
    from core.models import ConversationEvent

    rows = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == str(thread_id or ""),
            ConversationEvent.kind.in_(sorted(_LEARNING_EVENT_KINDS)),
        )
        .order_by(ConversationEvent.created_at.asc(),
                  ConversationEvent.id.asc())
        .limit(500)
        .all()
    )
    latest: Dict[str, LearningCandidate] = {}
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except (TypeError, ValueError):
            continue
        raw = payload.get("candidate")
        if not isinstance(raw, dict):
            continue
        try:
            candidate = LearningCandidate.model_validate(raw)
        except Exception:
            continue
        if workspace_id and candidate.workspace_id != str(workspace_id):
            continue
        if tenant_id and candidate.tenant_id != str(tenant_id):
            continue
        latest[candidate.candidate_id] = candidate
    return list(latest.values())


def _find_edge(candidate: LearningCandidate,
               dep: LearningDependency) -> Optional[ReferenceEdge]:
    if dep.edge_id:
        return next(
            (edge for edge in candidate.references
             if edge.edge_id == dep.edge_id), None)
    return next(
        (edge for edge in candidate.references
         if edge.relation == dep.kind
         and edge.resolution_status != "resolved"), None)


def resolve_dependency(
    db: Session,
    candidate: LearningCandidate,
    dependency_id: str,
    *,
    catalog: Sequence[ResourceBinding | Dict[str, Any]] = (),
    resource_id: str = "",
    column: str = "",
    unit: str = "",
    value: Any = None,
    method_status: Optional[str] = None,
    confirmed_by: str = "",
) -> LearningCandidate:
    """Apply one user answer to a dependency, then require review again."""
    dep = next(
        (item for item in candidate.dependencies
         if item.dependency_id == str(dependency_id)), None)
    if dep is None:
        raise ValueError("dependency_not_found")

    resources = [
        item if isinstance(item, ResourceBinding)
        else ResourceBinding.model_validate(item)
        for item in (catalog or [])
    ]

    if dep.kind in ("attachment", "calculation_input", "policy_reference",
                    "example", "supersedes", "context", "method_reference"):
        if not resource_id:
            raise ValueError("resource_id_required")
        target = next(
            (item for item in resources
             if str(item.resource_id) == str(resource_id)), None)
        if target is None:
            raise ValueError("resource_not_found")
        if not _in_scope(target, candidate.workspace_id, candidate.tenant_id):
            raise ValueError("resource_outside_scope")
        unavailable = _resource_unavailable_reason(target)
        if unavailable:
            raise ValueError(f"resource_{unavailable}")
        edge = _find_edge(candidate, dep)
        if edge is None:
            raise ValueError("reference_edge_not_found")
        edge.target_binding = target
        edge.resolution_status = "resolved"
        edge.resolution_basis = "user_confirmed"
        edge.confirmed_by = confirmed_by or "user"
        edge.detail = "Resolved by explicit user confirmation."
    elif dep.kind in ("method", "unit"):
        target_concept = dep.concept
        if not target_concept:
            target_concept = next(
                (item.concept for item in candidate.method.inputs
                 if item.unit_required and not item.unit), "")
        if column:
            for item in candidate.method.inputs:
                if (not target_concept or item.concept == target_concept) \
                        and not item.column:
                    item.column = _bounded(column, 120)
                    break
        if unit:
            for item in candidate.method.inputs:
                if (not target_concept or item.concept == target_concept) \
                        and not item.unit:
                    item.unit = _bounded(unit, 40)
                    break
        if value is not None:
            if isinstance(value, dict):
                candidate.method = MethodSpec.model_validate(value)
                candidate.method_status = method_status or "explicit"
            else:
                candidate.method.assumptions.append(
                    _bounded(f"{dep.question} -> {value}", 300))
        if method_status is not None:
            candidate.method_status = method_status
        if not column and not unit and value is None and method_status is None:
            raise ValueError("dependency_answer_required")
    elif dep.kind == "mapping":
        key = next(
            (k for k, v in (candidate.context or {}).items()
             if isinstance(v, dict) and "value" in v
             and not _bounded(v.get("field"))),
            None)
        if not key:
            raise ValueError("mapping_context_not_found")
        candidate.context[key] = {
            **dict(candidate.context.get(key) or {}),
            "field": _bounded(column or value, 120),
        }
    elif dep.kind == "applicability":
        if value is None:
            raise ValueError("dependency_answer_required")
        candidate.applies_to.append(_bounded(value, 80))
    else:
        raise ValueError(f"unsupported_dependency_kind:{dep.kind}")

    # Any dependency change invalidates a prior approval.
    candidate.revision += 1
    candidate.confirmed_by = None
    candidate.confirmed_revision = None
    candidate.confirmed_digest = None
    candidate.status = "draft"
    candidate = refresh_candidate(candidate)
    _append_candidate_event(
        db, "learning_candidate_dependency_resolved", candidate,
        extra={"dependency_id": dependency_id,
               "resolved_by": confirmed_by or "user"})
    return candidate


def revise_candidate(
    db: Session,
    candidate: LearningCandidate,
    *,
    proposed_lesson: Optional[str] = None,
    method: Optional[MethodSpec | Dict[str, Any]] = None,
    method_status: Optional[str] = None,
    applies_to: Optional[Sequence[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    changed_by: str = "",
) -> LearningCandidate:
    """Change candidate content; any prior approval is no longer valid."""
    if proposed_lesson is not None:
        candidate.proposed_lesson = _bounded(proposed_lesson, 2000)
    if method is not None:
        candidate.method = (
            method if isinstance(method, MethodSpec)
            else MethodSpec.model_validate(method))
    if method_status is not None:
        candidate.method_status = method_status
    if applies_to is not None:
        candidate.applies_to = [
            _bounded(item, 80) for item in applies_to if _bounded(item, 80)]
    if context is not None:
        candidate.context = dict(context)
    candidate.revision += 1
    candidate.confirmed_by = None
    candidate.confirmed_revision = None
    candidate.confirmed_digest = None
    candidate.status = "draft"
    candidate = refresh_candidate(candidate)
    _append_candidate_event(
        db, "learning_candidate_revised", candidate,
        extra={"changed_by": changed_by})
    return candidate


def confirm_candidate(
    db: Session,
    candidate: LearningCandidate,
    *,
    reviewer: str,
    expected_revision: Optional[int] = None,
) -> LearningCandidate:
    if expected_revision is not None and int(expected_revision) != int(
            candidate.revision):
        raise ValueError("candidate_revision_changed")
    readiness = candidate_readiness(candidate)
    if not readiness["review_ready"]:
        raise ValueError("candidate_not_review_ready")
    candidate.status = "confirmed"
    candidate.confirmed_by = str(reviewer or "")
    candidate.confirmed_revision = candidate.revision
    candidate.confirmed_digest = _candidate_digest(candidate)
    _append_candidate_event(
        db, "learning_candidate_confirmed", candidate,
        extra={"reviewer": reviewer})
    return candidate


def reject_candidate(
    db: Session,
    candidate: LearningCandidate,
    *,
    reviewer: str,
    reason: str = "",
) -> LearningCandidate:
    candidate.status = "rejected"
    candidate.rejected_by = str(reviewer or "")
    candidate.rejected_reason = _bounded(reason, 500)
    _append_candidate_event(
        db, "learning_candidate_rejected", candidate,
        extra={"reviewer": reviewer, "reason": candidate.rejected_reason})
    return candidate


def promote_candidate(
    db: Session,
    candidate: LearningCandidate,
    *,
    reviewer: str,
    expected_revision: Optional[int] = None,
    expected_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Write an approved candidate through the one teaching journal."""
    if candidate.status in ("rejected", "invalidated"):
        raise ValueError(f"candidate_{candidate.status}")
    if expected_revision is not None and int(expected_revision) != int(
            candidate.revision):
        raise ValueError("candidate_revision_changed")
    if (candidate.confirmed_revision != candidate.revision
            or candidate.confirmed_digest != _candidate_digest(candidate)):
        raise ValueError("candidate_not_confirmed_at_current_revision")
    if expected_digest and str(expected_digest) != _candidate_digest(candidate):
        raise ValueError("candidate_digest_changed")
    readiness = candidate_readiness(candidate)
    if not readiness["review_ready"]:
        raise ValueError("candidate_not_review_ready")

    from core.student_learning_service import journal_standing_lesson_entry

    details = {
        "conversation_learning": {
            "schema": SCHEMA_VERSION,
            "candidate_id": candidate.candidate_id,
            "revision": candidate.revision,
            "digest": _candidate_digest(candidate),
            "thread_id": candidate.thread_id,
            "agent_id": candidate.agent_id,
            "applies_to": list(candidate.applies_to),
            "context": candidate.context,
            "method": candidate.method.model_dump(mode="json"),
            "method_status": candidate.method_status,
            "references": [
                {
                    "edge_id": edge.edge_id,
                    "origin_message_id": edge.origin_message_id,
                    "origin_span": edge.origin_span,
                    "reference_text": edge.reference_text,
                    "relation": edge.relation,
                    "resolution_status": edge.resolution_status,
                    "resolution_basis": edge.resolution_basis,
                    "resource_id": (
                        edge.target_binding.resource_id
                        if edge.target_binding else None),
                    "source_version": (
                        edge.target_binding.source_version
                        if edge.target_binding else None),
                }
                for edge in candidate.references
            ],
            "dependencies": [
                dep.model_dump(mode="json") for dep in candidate.dependencies
            ],
            "reviewed_by": reviewer,
            "promoted_at": _now_iso(),
        }
    }
    entry = journal_standing_lesson_entry(
        db,
        candidate.agent_id,
        candidate.proposed_lesson,
        source="teacher",
        topic=f"conversation:{candidate.thread_id}",
        teacher_agent_id=str(reviewer or "human_supervisor"),
        details=details,
        workspace_id=candidate.workspace_id,
    )
    if entry is None:
        raise ValueError("lesson_not_journaled")
    candidate.status = "promoted"
    candidate.promoted_entry_id = str(entry.get("id") or "")
    _append_candidate_event(
        db, "learning_candidate_promoted", candidate,
        extra={"reviewer": reviewer, "entry_id": candidate.promoted_entry_id})
    return {
        "candidate": candidate,
        "entry": entry,
        "lesson_id": candidate.promoted_entry_id,
    }


def method_from_lesson(entry: Dict[str, Any]) -> Optional[MethodSpec]:
    """Read the structured method a promoted lesson carries.

    Returns None for ordinary lessons or malformed provenance. The lesson
    text remains the human-authored rule; the method is the validated
    executable part.
    """
    if not isinstance(entry, dict):
        return None
    details = entry.get("details") if isinstance(entry.get("details"),
                                                dict) else {}
    learning = details.get("conversation_learning") if isinstance(
        details.get("conversation_learning"), dict) else {}
    method = learning.get("method")
    if not isinstance(method, dict):
        return None
    try:
        return MethodSpec.model_validate(method)
    except Exception:
        return None


def apply_lesson_method(
    entry: Dict[str, Any],
    rows: Sequence[Dict[str, Any]],
    *,
    field_mapping: Optional[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply a promoted lesson's validated method, or refuse if it has none."""
    method = method_from_lesson(entry)
    if method is None:
        return {
            "status": "blocked",
            "reason": "lesson_has_no_confirmed_method",
        }
    return apply_confirmed_method(
        method, rows, field_mapping=field_mapping, context=context)


def invalidate_candidate(
    db: Session,
    candidate: LearningCandidate,
    *,
    reason: str,
) -> LearningCandidate:
    candidate.status = "invalidated"
    candidate.invalidated_reason = _bounded(reason, 500)
    _append_candidate_event(
        db, "learning_candidate_invalidated", candidate,
        extra={"reason": candidate.invalidated_reason})
    return candidate


def _mark_promoted_lesson_stale(
    db: Session,
    candidate: LearningCandidate,
    reason: str,
) -> None:
    """Mark the promoted lesson for revalidation without deleting it.

    The raw journal keeps the old lesson and its provenance; work-time
    retrieval skips entries whose structured provenance says revalidation is
    required. The candidate remains the review handle for the new version.
    """
    if not candidate.promoted_entry_id:
        return
    try:
        from sqlalchemy.orm.attributes import flag_modified

        from core.models import AgentRegistry

        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == candidate.agent_id).first()
        if agent is None:
            return
        config = agent.configuration if isinstance(
            agent.configuration, dict) else {}
        learning = dict(config.get("learning") or {})
        log = list(learning.get("log") or [])
        changed = False
        for entry in log:
            if str(entry.get("id") or "") != str(
                    candidate.promoted_entry_id):
                continue
            details = dict(entry.get("details") or {})
            provenance = dict(
                details.get("conversation_learning") or {})
            provenance["revalidation_required"] = True
            provenance["revalidation_reason"] = _bounded(reason, 500)
            details["conversation_learning"] = provenance
            entry["details"] = details
            entry["stale"] = True
            changed = True
        if changed:
            learning["log"] = log
            config = {**config, "learning": learning}
            agent.configuration = config
            flag_modified(agent, "configuration")
            db.commit()
    except Exception as exc:  # noqa: BLE001 — staleness must not break review
        logger.debug("promoted lesson revalidation mark skipped: %s", exc)


def revalidate_candidate(
    db: Session,
    candidate: LearningCandidate,
    catalog: Sequence[ResourceBinding | Dict[str, Any]],
) -> LearningCandidate:
    """Invalidate reuse when a governing resource changed; keep the lesson."""
    resources = [
        item if isinstance(item, ResourceBinding)
        else ResourceBinding.model_validate(item)
        for item in (catalog or [])
    ]
    current = {str(item.resource_id): item for item in resources}
    for edge in candidate.references:
        if edge.target_binding is None:
            continue
        binding = current.get(str(edge.target_binding.resource_id))
        reason = ""
        if binding is None:
            reason = f"resource_missing:{edge.target_binding.resource_id}"
        elif str(binding.source_version) != str(
                edge.target_binding.source_version):
            reason = (
                f"source_version_changed:"
                f"{edge.target_binding.resource_id}")
        else:
            unavailable = _resource_unavailable_reason(binding)
            if unavailable:
                reason = (
                    f"resource_{unavailable}:"
                    f"{edge.target_binding.resource_id}")
        if reason:
            _mark_promoted_lesson_stale(db, candidate, reason)
            return invalidate_candidate(db, candidate, reason=reason)
    return candidate


def review_payload(candidate: LearningCandidate) -> Dict[str, Any]:
    readiness = candidate_readiness(candidate)
    return {
        "candidate_id": candidate.candidate_id,
        "status": candidate.status,
        "revision": candidate.revision,
        "digest": _candidate_digest(candidate),
        "review_ready": readiness["review_ready"],
        "proposed_lesson": candidate.proposed_lesson,
        "where_it_applies": {
            "applies_to": list(candidate.applies_to),
            "context": candidate.context,
        },
        "referenced_data_and_versions": [
            {
                "reference": edge.reference_text,
                "relation": edge.relation,
                "status": edge.resolution_status,
                "basis": edge.resolution_basis,
                "resource_id": (
                    edge.target_binding.resource_id
                    if edge.target_binding else None),
                "file_name": (
                    edge.target_binding.original_file_name
                    if edge.target_binding else None),
                "sheet": (
                    edge.target_binding.sheet
                    if edge.target_binding else None),
                "locator": (
                    edge.target_binding.locator
                    if edge.target_binding else {}),
                "source_version": (
                    edge.target_binding.source_version
                    if edge.target_binding else None),
                "candidates": [
                    _candidate_payload(item) for item in edge.candidates
                ],
            }
            for edge in candidate.references
        ],
        "method_and_assumptions": {
            "method_status": candidate.method_status,
            "method": candidate.method.model_dump(mode="json"),
        },
        "exceptions": list(candidate.method.exceptions),
        "unresolved_questions": [
            {
                "dependency_id": dep.dependency_id,
                "kind": dep.kind,
                "status": dep.status,
                "question": dep.question,
                "resource_id": (
                    dep.binding.resource_id if dep.binding else None),
            }
            for dep in readiness["dependencies"]
            if dep.required and dep.status not in ("resolved", "not_applicable")
        ],
        "supporting_messages": [
            {
                "message_id": message_id,
                "is_authority": message_id == candidate.authority_message_id,
            }
            for message_id in candidate.evidence_message_ids
        ],
        "authority": {
            "message_id": candidate.authority_message_id,
            "excerpt": candidate.authority_excerpt,
        },
        "confirmed_by": candidate.confirmed_by,
        "confirmed_revision": candidate.confirmed_revision,
        "rejected_by": candidate.rejected_by,
        "rejected_reason": candidate.rejected_reason,
        "invalidated_reason": candidate.invalidated_reason,
        "promoted_entry_id": candidate.promoted_entry_id,
    }


# ---------------------------------------------------------------------------
# Deterministic method application (allowlisted, no eval)
# ---------------------------------------------------------------------------

_OPERATIONS = {"sum", "count", "multiply_sum", "percentage", "ratio"}


def _dec(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {
            "nan", "none", "null", "n/a", "na", "-", "—"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _row_matches(row: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    field = str(condition.get("field") or "")
    if not field:
        return True
    actual = row.get(field)
    if "equals" in condition:
        return str(actual) == str(condition.get("equals"))
    if "not_equals" in condition:
        return str(actual) != str(condition.get("not_equals"))
    if "in" in condition and isinstance(condition.get("in"), (list, tuple)):
        return str(actual) in {str(item) for item in condition["in"]}
    if "not_in" in condition and isinstance(condition.get("not_in"),
                                            (list, tuple)):
        return str(actual) not in {str(item) for item in condition["not_in"]}
    if "contains" in condition:
        return str(condition.get("contains")) in str(actual)
    return True


def apply_confirmed_method(
    method: MethodSpec | Dict[str, Any],
    rows: Sequence[Dict[str, Any]],
    *,
    method_status: str = "explicit",
    field_mapping: Optional[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply an explicit method to rows with Decimal arithmetic.

    This is a bounded allowlist (sum/count/multiply_sum/percentage/ratio),
    never ``eval`` and never a model-generated program. It refuses to guess
    a unit, a missing input or an unsupported operation.
    """
    if method_status != "explicit":
        return {
            "status": "blocked",
            "reason": "method_not_explicit",
            "method_status": method_status,
        }
    model = (method if isinstance(method, MethodSpec)
             else MethodSpec.model_validate(method or {}))
    mapping = dict(field_mapping or {})
    if model.operation not in _OPERATIONS:
        return {
            "status": "blocked",
            "reason": "unsupported_operation",
            "operation": model.operation,
        }
    if not model.inputs:
        return {"status": "blocked", "reason": "no_inputs"}

    resolved_inputs: List[Tuple[MethodInput, str]] = []
    missing: List[str] = []
    for item in model.inputs:
        column = mapping.get(item.concept) or item.column
        if not column:
            missing.append(f"column:{item.concept}")
            continue
        if item.unit_required and not _bounded(item.unit):
            missing.append(f"unit:{item.concept}")
            continue
        resolved_inputs.append((item, column))
    if missing:
        return {
            "status": "blocked",
            "reason": "missing_required_inputs",
            "missing": missing,
        }

    selected = []
    for row in rows:
        if not all(_row_matches(row, cond)
                   for cond in model.decision_conditions):
            continue
        if any(_row_matches(row, exc) for exc in model.exceptions):
            continue
        selected.append(row)

    values: Dict[str, List[Decimal]] = {}
    missing_values: Dict[str, int] = {}
    for item, column in resolved_inputs:
        numbers: List[Decimal] = []
        absent = 0
        for row in selected:
            number = _dec(row.get(column))
            if number is None:
                absent += 1
            else:
                numbers.append(number)
        if item.required and absent:
            missing_values[item.concept] = absent
        values[item.concept] = numbers
    if missing_values:
        return {
            "status": "blocked",
            "reason": "missing_required_values",
            "missing_values": missing_values,
            "selected_rows": len(selected),
        }

    if model.operation == "count":
        result = Decimal(len(selected))
    elif model.operation == "sum":
        result = sum(values[resolved_inputs[0][0].concept], Decimal("0"))
    elif model.operation == "multiply_sum":
        if len(resolved_inputs) < 2:
            return {"status": "blocked", "reason": "two_inputs_required"}
        left = values[resolved_inputs[0][0].concept]
        right = values[resolved_inputs[1][0].concept]
        result = sum((a * b for a, b in zip(left, right)), Decimal("0"))
    elif model.operation == "percentage":
        if len(resolved_inputs) < 2:
            return {"status": "blocked", "reason": "two_inputs_required"}
        base = sum(values[resolved_inputs[0][0].concept], Decimal("0"))
        rate = sum(values[resolved_inputs[1][0].concept], Decimal("0"))
        result = base * rate / Decimal("100")
    else:  # ratio
        if len(resolved_inputs) < 2:
            return {"status": "blocked", "reason": "two_inputs_required"}
        numerator = sum(values[resolved_inputs[0][0].concept], Decimal("0"))
        denominator = sum(values[resolved_inputs[1][0].concept], Decimal("0"))
        if denominator == 0:
            return {"status": "blocked", "reason": "zero_denominator"}
        result = numerator / denominator

    places = model.rounding.get("places")
    if places is not None:
        try:
            places = int(places)
            quantum = Decimal("1").scaleb(-places)
            result = result.quantize(quantum, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return {"status": "blocked", "reason": "invalid_rounding"}

    return {
        "status": "applied",
        "operation": model.operation,
        "value": format(result.normalize(), "f"),
        "unit": model.output_unit,
        "selected_rows": len(selected),
        "input_totals": {
            concept: format(sum(numbers, Decimal("0")).normalize(), "f")
            for concept, numbers in values.items()
        },
        "assumptions": list(model.assumptions),
        "context": dict(context or {}),
    }


# ---------------------------------------------------------------------------
# Local email-canvas evidence collection (no live mailbox access)
# ---------------------------------------------------------------------------

def _resource_from_dataset_entry(entry: Any) -> ResourceBinding:
    columns = list(getattr(entry, "columns_json", None) or [])
    return ResourceBinding(
        resource_id=str(getattr(entry, "id", "") or ""),
        dataset_name=str(getattr(entry, "dataset_name", "") or ""),
        source=str(getattr(entry, "source", "") or ""),
        source_kind=str(getattr(entry, "source_kind", "") or ""),
        external_id=str(getattr(entry, "external_id", "") or ""),
        original_file_name=str(getattr(entry, "file_name", "") or ""),
        representation="parquet",
        source_version=str(getattr(entry, "content_hash", "") or ""),
        sheet=str(getattr(entry, "entity_name", "") or ""),
        locator={"sheet": str(getattr(entry, "entity_name", "") or "")},
        columns=columns,
        numeric_columns=[],
        row_count=getattr(entry, "row_count", None),
        coverage={"known": True, "truncated": False},
        access_scope={
            "workspace_id": str(getattr(entry, "workspace_id", "") or ""),
            "tenant_id": str(getattr(entry, "tenant_id", "") or ""),
            "user_id": str(getattr(entry, "created_by", "") or ""),
        },
        workspace_id=str(getattr(entry, "workspace_id", "") or ""),
        tenant_id=str(getattr(entry, "tenant_id", "") or ""),
        status=str(getattr(entry, "status", "") or "active"),
    )


def _message_from_canvas_dict(raw: Dict[str, Any], *,
                              mailbox_owner: str) -> MessageEvidence:
    attachments = []
    for item in raw.get("attachments") or []:
        if not isinstance(item, dict):
            continue
        ingestion = item.get("ingestion") if isinstance(
            item.get("ingestion"), dict) else {}
        attachments.append(AttachmentEvidence(
            attachment_id=str(item.get("attachment_id") or ""),
            provider=str(item.get("provider") or ""),
            message_id=str(item.get("message_id") or raw.get("message_id") or ""),
            filename=str(item.get("filename") or ""),
            content_type=str(item.get("content_type") or ""),
            size=int(item.get("size") or 0),
            sha256=str(item.get("sha256") or ""),
            resource_id=(
                str(ingestion.get("doc_id"))
                if ingestion.get("doc_id") else None),
            ingestion_status=str(ingestion.get("status") or "unknown"),
            inline=bool(item.get("is_inline")),
        ))
    body = str(raw.get("body") or "")
    authored, quoted = split_authored_quoted(body)
    return MessageEvidence(
        message_id=str(raw.get("message_id") or ""),
        provider=str(raw.get("provider") or "email_canvas"),
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest()
        if body else "",
        mailbox_owner=mailbox_owner,
        sender=str(raw.get("from_email") or ""),
        recipients=[str(item) for item in raw.get("to_emails") or []],
        cc=[str(item) for item in raw.get("cc_emails") or []],
        sent_at=str(raw.get("timestamp") or raw.get("sent_at") or ""),
        received_at=str(raw.get("received_at") or ""),
        body=body,
        authored_segments=[authored] if authored else [],
        quoted_segments=[quoted] if quoted else [],
        attachments=attachments,
        reply_to_message_id=str(
            raw.get("in_reply_to") or raw.get("reply_to_message_id") or ""),
        references=[str(item) for item in raw.get("references") or []],
        source_access_status="available",
    )


def list_email_threads(
    db: Session,
    user: Any,
    *,
    limit: int = 50,
    audit_limit: int = 500,
) -> List[Dict[str, Any]]:
    """Local email threads available for review, without a provider call."""
    from core.models import Canvas, CanvasAudit

    workspace_id = str(getattr(user, "workspace_id", "") or "default")
    tenant_id = str(getattr(user, "tenant_id", "") or "default")
    canvas_ids = {
        str(row.id)
        for row in (
            db.query(Canvas.id)
            .filter(
                Canvas.workspace_id == workspace_id,
                Canvas.tenant_id == tenant_id,
            )
            .limit(2000)
            .all()
        )
    }
    rows = (
        db.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_type == "email",
            CanvasAudit.tenant_id == tenant_id,
        )
        .order_by(CanvasAudit.created_at.desc())
        .limit(audit_limit)
        .all()
    )
    threads: Dict[str, Dict[str, Any]] = {}
    for audit in rows:
        if canvas_ids and str(audit.canvas_id) not in canvas_ids:
            continue
        details = audit.details_json if isinstance(
            audit.details_json, dict) else {}
        thread_id = str(details.get("thread_id") or "").strip()
        if not thread_id:
            continue
        messages = [
            item for item in (details.get("messages") or [])
            if isinstance(item, dict)
        ]
        imported = details.get("imported_message")
        if isinstance(imported, dict):
            messages.append(imported)
        subject = str(
            details.get("subject")
            or next((item.get("subject") for item in messages
                     if item.get("subject")), "")
            or "(no subject)")
        last_at = (
            audit.created_at.isoformat() if audit.created_at else "")
        entry = threads.setdefault(thread_id, {
            "thread_id": thread_id,
            "subject": subject[:200],
            "message_count": 0,
            "last_at": last_at,
        })
        entry["message_count"] = max(entry["message_count"], len(messages))
        if last_at > entry["last_at"]:
            entry["last_at"] = last_at
    ordered = sorted(
        threads.values(), key=lambda item: item["last_at"], reverse=True)
    return ordered[:max(1, int(limit or 50))]


def collect_email_thread_evidence(
    db: Session,
    user: Any,
    thread_id: str,
    *,
    catalog_limit: int = 400,
    audit_limit: int = 200,
) -> ConversationEvidence:
    """Build evidence from persisted email-canvas audits only.

    No provider call is made. If the thread is not present locally, coverage
    says so instead of silently returning an empty, authoritative-looking
    conversation.
    """
    from core.models import Canvas, CanvasAudit, DatasetEntry

    workspace_id = str(getattr(user, "workspace_id", "") or "default")
    tenant_id = str(getattr(user, "tenant_id", "") or "default")
    user_id = str(getattr(user, "id", "") or "")

    canvas_ids = {
        str(row.id)
        for row in (
            db.query(Canvas.id)
            .filter(
                Canvas.workspace_id == workspace_id,
                Canvas.tenant_id == tenant_id,
            )
            .limit(2000)
            .all()
        )
    }
    audits = (
        db.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_type == "email",
            CanvasAudit.tenant_id == tenant_id,
        )
        .order_by(CanvasAudit.created_at.asc())
        .limit(audit_limit)
        .all()
    )
    if canvas_ids:
        audits = [
            audit for audit in audits
            if str(audit.canvas_id) in canvas_ids
        ]
    messages_by_id: Dict[str, MessageEvidence] = {}
    seen_thread = False
    for audit in audits:
        details = audit.details_json if isinstance(
            audit.details_json, dict) else {}
        audit_thread = str(details.get("thread_id") or "")
        if audit_thread and audit_thread != str(thread_id or ""):
            continue
        seen_thread = True
        raw_messages = list(details.get("messages") or [])
        imported = details.get("imported_message")
        if isinstance(imported, dict):
            raw_messages.append(imported)
        for raw in raw_messages:
            if not isinstance(raw, dict):
                continue
            message = _message_from_canvas_dict(
                raw, mailbox_owner=user_id)
            if message.message_id:
                messages_by_id[message.message_id] = message

    catalog_rows = (
        db.query(DatasetEntry)
        .filter(DatasetEntry.tenant_id == tenant_id)
        .order_by(DatasetEntry.ingested_at.desc())
        .limit(catalog_limit)
        .all()
    )
    resources = [_resource_from_dataset_entry(row) for row in catalog_rows]

    coverage = EvidenceCoverage(
        messages_known=bool(messages_by_id),
        messages_truncated=len(audits) >= audit_limit,
        attachments_complete=all(
            attachment.ingestion_status not in ("error", "unknown")
            for message in messages_by_id.values()
            for attachment in message.attachments
        ),
        resources_known=True,
        source_access="available" if seen_thread else "missing",
        message_count=len(messages_by_id),
        max_reference_depth=1,
        depth_reached=0,
        message_limit=audit_limit,
        resource_limit=catalog_limit,
        notes=[] if seen_thread else [
            "No persisted email canvas audit matched this thread; the "
            "evidence package is not authoritative."],
    )
    evidence = ConversationEvidence(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        account_id=user_id,
        thread_id=str(thread_id or ""),
        messages=list(messages_by_id.values()),
        resources=resources,
        coverage=coverage,
    )
    return resolve_reference_edges(evidence, resources)
