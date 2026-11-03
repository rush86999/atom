"""Bounded employee work proposals over the existing assignment contracts.

The reasoning layer chooses *supported* next work from an ordinary objective
and the durable employee context. It never executes a tool, grants authority,
writes a receipt or supplies executable step JSON. Deterministic code
validates the proposal against the registered sources/actions and compiles it
through ``assignment_planner.plan_assignment`` for the existing
``AssignmentExecutor`` to own.

The module is deliberately small and pure. It is not another planner engine:
the compiler is the existing assignment planner, the state carrier is the
existing task lifecycle, and the executor remains the sole operation driver.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from core.assignment_resources import resource_binding

PROPOSAL_SCHEMA = "atom-employee-work-proposal-1"
MAX_EVIDENCE_READS = 5
MAX_CONTEXT_SOURCES = 10
MAX_CONTEXT_FACTS = 40
MAX_CONTEXT_OBLIGATIONS = 20


class EvidenceReadProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(default="", max_length=80)
    title: str = Field(default="", max_length=200)
    source_id: str = Field(default="", max_length=200)
    action: str = Field(default="", max_length=200)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requires: List[Dict[str, Any]] = Field(default_factory=list)
    reason: str = Field(default="", max_length=500)


class ClarificationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(max_length=400)
    concept: str = Field(default="", max_length=120)
    unblocks: str = Field(default="", max_length=300)
    expected_answer_type: str = Field(default="", max_length=80)


class EmployeeWorkProposal(BaseModel):
    """One reasoning proposal. Never an effect or an authority grant."""

    model_config = ConfigDict(extra="forbid")

    proposal_kind: Literal[
        "evidence_read", "clarification", "evidence_and_clarification"]
    reason: str = Field(default="", max_length=800)
    evidence_reads: List[EvidenceReadProposal] = Field(default_factory=list)
    clarification: Optional[ClarificationProposal] = None


def _text(value: Any, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


def source_handle(source: Mapping[str, Any]) -> str:
    """Stable, non-secret handle for an authorized source."""
    return _source_id(source)


def _source_id(source: Mapping[str, Any]) -> str:
    explicit = _text(source.get("source_id"), 200)
    if explicit:
        return explicit
    binding = resource_binding(dict(source)) if isinstance(source, Mapping) else {}
    for candidate in (
            binding.get("resource_id"),
            source.get("resource_id"),
            source.get("dataset_name"),
            source.get("external_id"),
            source.get("file_name"),
    ):
        if str(candidate or "").strip():
            return _text(candidate, 200)
    return ""


def _source_view(source: Mapping[str, Any]) -> Dict[str, Any]:
    raw = dict(source)
    nested = raw.get("binding")
    if isinstance(nested, Mapping):
        for key, value in nested.items():
            raw.setdefault(key, value)
    source = raw
    binding = resource_binding(raw)
    return {
        "source_id": _source_id(source),
        "kind": _text(source.get("kind"), 40),
        "representation": _text(
            source.get("representation") or binding.get("representation"), 40),
        "file_name": _text(
            source.get("file_name") or binding.get("file_name")
            or source.get("original_file_name"), 200),
        "sheet": _text(source.get("sheet") or binding.get("sheet"), 120),
        "columns": [
            _text(column, 120) for column in
            (source.get("columns") or binding.get("columns") or [])[:40]
            if str(column).strip()
        ],
        "numeric_columns": [
            _text(column, 120) for column in
            (source.get("numeric_columns")
             or binding.get("numeric_columns") or [])[:40]
            if str(column).strip()
        ],
        "row_count": source.get("row_count"),
        "coverage": dict(source.get("coverage") or {}),
        "source_version": _text(
            source.get("source_version") or binding.get("source_version"), 160),
    }


def build_employee_context(
    *,
    objective: str,
    employee_id: str = "",
    agent_id: Optional[str] = None,
    workspace_id: str = "",
    tenant_id: str = "",
    teaching: Optional[Mapping[str, Any]] = None,
    sources: Optional[Sequence[Mapping[str, Any]]] = None,
    task_context: Optional[Mapping[str, Any]] = None,
    criteria: Optional[Sequence[Mapping[str, Any]]] = None,
    facts: Optional[Sequence[Mapping[str, Any]]] = None,
    open_obligations: Optional[Sequence[Mapping[str, Any]]] = None,
    authorized_actions: Optional[Sequence[str]] = None,
    action_views: Optional[Sequence[Mapping[str, Any]]] = None,
    budget: Optional[Mapping[str, Any]] = None,
    task_version: Optional[int] = None,
    plan_revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Bounded context for the reasoning consumer, with stable handles only.

    File paths and raw document bodies are intentionally excluded. The model
    sees identities, schemas, coverage and typed facts; the executor resolves
    bytes from the binding when the proposed read actually runs.
    """
    teaching = dict(teaching or {})
    return {
        "schema": PROPOSAL_SCHEMA,
        "objective": _text(objective, 4000),
        "identity": {
            "employee_id": _text(employee_id, 120) or None,
            "agent_id": _text(agent_id, 120) or None,
            "workspace_id": _text(workspace_id, 120) or None,
            "tenant_id": _text(tenant_id, 120) or None,
            "execution_owner": "assignment",
        },
        "task_version": (
            int(task_version) if task_version is not None else None),
        "plan_revision": (
            int(plan_revision) if plan_revision is not None else None),
        "criteria": [dict(item) for item in (criteria or [])[:20]
                     if isinstance(item, Mapping)],
        "teaching": {
            "revision": _text(teaching.get("revision"), 80),
            "effective_lesson_ids": list(
                teaching.get("effective_lesson_ids") or [])[:20],
            "applicable_conditions": dict(
                teaching.get("applicable_conditions") or {}),
        },
        "task_context": dict(task_context or {}),
        "sources": [
            _source_view(item) for item in (sources or [])[:MAX_CONTEXT_SOURCES]
            if isinstance(item, Mapping) and _source_id(item)
        ],
        "facts": [
            {
                "fact_id": _text(item.get("fact_id"), 120),
                "subject": dict(item.get("subject") or {}),
                "field_id": _text(item.get("field_id"), 120) or None,
                "value": item.get("value"),
                "value_type": _text(item.get("value_type"), 40) or None,
                "evidence_state": _text(
                    item.get("evidence_state"), 20) or "unknown",
                "source_refs": [
                    dict(ref) for ref in (item.get("source_refs") or [])[:20]
                    if isinstance(ref, Mapping)],
                "authority_ref": _text(
                    item.get("authority_ref"), 200) or None,
                "validity": dict(item.get("validity") or {}),
            }
            for item in (facts or [])[:MAX_CONTEXT_FACTS]
            if isinstance(item, Mapping) and item.get("fact_id")
        ],
        "open_obligations": [
            {
                "question_id": _text(item.get("question_id"), 120),
                "question": _text(item.get("question"), 400),
                "concept": _text(item.get("concept"), 120) or None,
                "next_action": _text(item.get("next_action"), 400) or None,
                "kind": _text(item.get("kind"), 40),
            }
            for item in (open_obligations or [])[:MAX_CONTEXT_OBLIGATIONS]
            if isinstance(item, Mapping)
        ],
        "authorized_actions": [
            _text(item, 120) for item in (authorized_actions or [])
            if str(item).strip()
        ][:40],
        "action_views": [
            {
                "action": _text(item.get("action") or item.get("name"), 200),
                "effect": _text(item.get("effect") or "read_only", 40),
                "description": _text(item.get("description"), 300),
            }
            for item in (action_views or [])[:40]
            if isinstance(item, Mapping)
        ],
        "budget": dict(budget or {}),
        "rules": {
            "allowed_proposal_kinds": [
                "evidence_read", "clarification",
                "evidence_and_clarification"],
            "can_execute": False,
            "can_grant_authority": False,
            "can_supply_receipts": False,
            "evidence_only": True,
            "clarify_only_when_material": True,
        },
    }


def _context_source(context: Mapping[str, Any], source_id: str) -> Optional[Dict]:
    for source in context.get("sources") or []:
        if str(source.get("source_id") or "") == source_id:
            return dict(source)
    return None


def _context_action(context: Mapping[str, Any], action: str) -> Optional[Dict]:
    for item in context.get("action_views") or []:
        if str(item.get("action") or "") == action:
            return dict(item)
    return None


def validate_employee_proposal(
    proposal: Any,
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return ``{"valid", "errors", "proposal"}``; never adopt on errors."""
    errors: List[str] = []
    if isinstance(proposal, BaseModel):
        proposal = proposal.model_dump()
    if not isinstance(proposal, Mapping):
        return {"valid": False, "errors": ["proposal must be an object"],
                "proposal": None}
    try:
        normalized = EmployeeWorkProposal.model_validate(dict(proposal))
    except Exception as exc:  # pydantic validation is the schema boundary
        return {"valid": False,
                "errors": [f"proposal schema: {_text(exc, 800)}"],
                "proposal": None}
    kind = normalized.proposal_kind
    if kind in ("evidence_read", "evidence_and_clarification"):
        if not normalized.evidence_reads:
            errors.append("evidence_read proposal requires at least one read")
    if kind in ("clarification", "evidence_and_clarification"):
        if normalized.clarification is None:
            errors.append("clarification proposal requires a question")
        elif not normalized.clarification.question.strip():
            errors.append("clarification question is empty")
    if len(normalized.evidence_reads) > MAX_EVIDENCE_READS:
        errors.append(f"at most {MAX_EVIDENCE_READS} evidence reads are allowed")
    seen_steps = set()
    for index, read in enumerate(normalized.evidence_reads):
        where = f"evidence_reads[{index}]"
        step_id = read.step_id.strip()
        if not step_id:
            errors.append(f"{where} requires a stable step_id")
        elif step_id in seen_steps:
            errors.append(f"duplicate evidence step_id {step_id!r}")
        else:
            seen_steps.add(step_id)
        source_id = read.source_id.strip()
        action = read.action.strip()
        if source_id and action:
            errors.append(
                f"{where} must choose a source read or an action, not both")
        if not source_id and not action:
            errors.append(f"{where} requires source_id or action")
        if source_id and _context_source(context, source_id) is None:
            errors.append(f"{where} names unknown source_id {source_id!r}")
        if action:
            action_view = _context_action(context, action)
            if action_view is None:
                errors.append(f"{where} names unknown action {action!r}")
            elif str(action_view.get("effect") or "").lower() not in (
                    "read_only", "retrieve"):
                errors.append(
                    f"{where} action {action!r} is not read-only; effects "
                    "cannot be proposed by the reasoning layer")
            if not isinstance(read.arguments, dict):
                errors.append(f"{where} arguments must be an object")
        if read.requires:
            try:
                from core.assignment_readiness import normalize_requirements
                normalize_requirements(read.requires)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{where} requirements: {_text(exc, 300)}")
    return {
        "valid": not errors,
        "errors": errors,
        "proposal": normalized.model_dump() if not errors else None,
    }


def _deterministic_proposal(context: Mapping[str, Any]) -> Dict[str, Any]:
    sources = list(context.get("sources") or [])
    if sources:
        source = sources[0]
        return {
            "proposal_kind": "evidence_read",
            "reason": (
                "No model proposal is available; read the strongest "
                "authorized source so the employee can establish evidence "
                "without guessing."),
            "evidence_reads": [{
                "step_id": "evidence-1",
                "title": (
                    f"Read {source.get('file_name') or source.get('source_id')}"
                    f" ({source.get('sheet') or 'source'})"),
                "source_id": source.get("source_id"),
                "reason": "Authorized evidence is the safest useful first "
                          "step.",
            }],
        }
    return {
        "proposal_kind": "clarification",
        "reason": "No authorized source is available to establish the "
                  "objective's material evidence.",
        "clarification": {
            "question": (
                "Which authorized source should I use for this objective?"),
            "concept": "source_access",
            "unblocks": "Reading the governing evidence and preparing the "
                        "requested result.",
            "expected_answer_type": "resource selection",
        },
    }


def _proposal_prompt(context: Mapping[str, Any]) -> str:
    return (
        "You are the accountable employee's planning reasoner. Choose the "
        "next useful supported work from the bounded context below.\n\n"
        "Rules:\n"
        "- Propose at most five READ-ONLY evidence reads, one targeted "
        "business clarification, or both.\n"
        "- You cannot execute a tool, create an external effect, grant "
        "permission, invent source/action IDs, or provide receipts.\n"
        "- Use only source_id values and action names present in the context.\n"
        "- Ask a question only when the missing fact materially changes the "
        "result or allowed action and cannot be read from an authorized "
        "source.\n"
        "- A question must name the exact fact/choice and what it unblocks.\n"
        "- Do not ask the user to choose implementation steps or provide "
        "data already available from an authorized source.\n"
        "- Return JSON matching this shape: "
        '{"proposal_kind":"evidence_read|clarification|'
        'evidence_and_clarification","reason":"...",'
        '"evidence_reads":[{"step_id":"evidence-1","title":"...",'
        '"source_id":"...|","action":"...|","arguments":{},'
        '"requires":[],"reason":"..."}],'
        '"clarification":{"question":"...","concept":"...",'
        '"unblocks":"...","expected_answer_type":"..."}|null}\n\n'
        "CONTEXT:\n" + json.dumps(context, sort_keys=True, default=str)
    )


async def propose_employee_work(
    context: Mapping[str, Any],
    *,
    llm_service: Any = None,
    deadline_seconds: float = 120.0,
) -> Dict[str, Any]:
    """Propose supported read/clarification work; never an effect.

    The model receives only the bounded context. A provider/protocol failure
    falls back to a deterministic authorized read (or a source-access
    clarification), and the result records which path produced it.
    """
    if llm_service is not None:
        try:
            from core.llm.pinned_planning import pinned_structured_call
            result = await pinned_structured_call(
                llm_service,
                prompt=_proposal_prompt(context),
                response_model=EmployeeWorkProposal,
                system_instruction=(
                    "You are a read-only employee work planner. You never "
                    "execute, authorize or invent facts. Return JSON only."),
                call_kwargs=None,
                extra_kwargs={
                    "output_mode": "json",
                    "cascade": False,
                    "allow_moa": False,
                    "max_tokens": 1800,
                },
                log_label="employee work proposal",
                task_type="planning",
                workspace_id=context.get("identity", {}).get("workspace_id"),
                tenant_id=context.get("identity", {}).get("tenant_id"),
            )
        except Exception:  # noqa: BLE001 — the fallback remains explicit
            result = None
        if result is not None:
            checked = validate_employee_proposal(result, context)
            if checked["valid"]:
                return {
                    "proposal": checked["proposal"],
                    "source": "model",
                    "technical_fallback": False,
                    "errors": [],
                }
            fallback = _deterministic_proposal(context)
            return {
                "proposal": fallback,
                "source": "deterministic",
                "technical_fallback": True,
                "errors": checked["errors"],
            }
    fallback = _deterministic_proposal(context)
    return {
        "proposal": fallback,
        "source": "deterministic",
        "technical_fallback": llm_service is not None,
        "errors": [],
    }


def compile_employee_proposal(
    proposal: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    sources: Sequence[Mapping[str, Any]],
    facts: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Turn a validated proposal into ``plan_assignment`` descriptors."""
    checked = validate_employee_proposal(proposal, context)
    if not checked["valid"]:
        return {"valid": False, "errors": checked["errors"], "plan_kwargs": None}
    normalized = checked["proposal"]
    reads = list(normalized.get("evidence_reads") or [])
    selected_sources: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    source_ids = {
        _source_id(source): source
        for source in (sources or [])
        if _source_id(source)
    }
    for read in reads:
        source_id = str(read.get("source_id") or "")
        if source_id:
            source = source_ids.get(source_id)
            if source is None:
                return {
                    "valid": False,
                    "errors": [f"compiled source {source_id!r} disappeared"],
                    "plan_kwargs": None,
                }
            item = dict(source)
            item["requires"] = list(read.get("requires") or [])
            selected_sources.append(item)
        elif read.get("action"):
            actions.append({
                "step_id": read.get("step_id"),
                "title": read.get("title") or f"Read via {read['action']}",
                "action": read["action"],
                "arguments": dict(read.get("arguments") or {}),
                "requires": list(read.get("requires") or []),
            })
    if not selected_sources:
        # The existing planner requires an authorized source even for an
        # action read; use the context's first source as the declared scope.
        first = (context.get("sources") or [None])[0]
        if first:
            source = source_ids.get(str(first.get("source_id") or ""))
            if source is not None:
                selected_sources = [dict(source)]
    return {
        "valid": True,
        "errors": [],
        "plan_kwargs": {
            "sources": selected_sources,
            "actions": actions,
            "facts": list(facts or []),
            "clarification": normalized.get("clarification"),
            "proposal": normalized,
        },
    }


def employee_job_view(
    assignment: Mapping[str, Any],
    *,
    record: Optional[Mapping[str, Any]] = None,
    open_obligations: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """The bounded business view used by the normal job surface."""
    steps = list(assignment.get("steps") or [])
    try:
        from core.task_outcome_contract import build_assignment_outcome
        business_outcome = build_assignment_outcome(
            dict(assignment), dict(record or {}))
    except Exception:  # noqa: BLE001 — a read view must not crash
        business_outcome = None
    return {
        "objective": assignment.get("objective"),
        "identity": {
            "employee_id": assignment.get("employee_id"),
            "workspace_id": assignment.get("workspace_id"),
            "tenant_id": assignment.get("tenant_id"),
            "execution_owner": "assignment",
        },
        "criteria": list(assignment.get("completion_criteria") or []),
        "facts": list(assignment.get("facts") or []),
        "sources": [
            _source_view(source) for source in (assignment.get("sources") or [])
            if isinstance(source, Mapping)
        ],
        "steps": [
            {
                "step_id": step.get("step_id"),
                "title": step.get("title"),
                "status": step.get("status"),
                "required": bool(step.get("required", True)),
                "effect": step.get("effect"),
                "requires": list(step.get("requires") or []),
                "readiness": step.get("readiness"),
                "readiness_blocker": step.get("readiness_blocker"),
                "result_summary": (
                    (step.get("result") or {}).get("summary")
                    if isinstance(step.get("result"), dict) else None),
            }
            for step in steps
        ],
        "open_obligations": [
            dict(item) for item in (open_obligations or [])
            if isinstance(item, Mapping)
        ],
        "budget": dict(assignment.get("budget") or {}),
        "status": assignment.get("status"),
        "task_version": (
            record.get("task_version") if isinstance(record, Mapping)
            else None),
        "plan_revision": assignment.get("plan_revision"),
        "business_outcome": business_outcome,
    }
