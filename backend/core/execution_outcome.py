"""Versioned per-operation execution-outcome records (M4 slice).

One record per operation with four independent dimensions — execution,
evidence, verification, delivery — each owned by its own producer with
its own state machine. A single tri-state cannot represent these, and
the dimensions are never folded into one task verdict inside the record;
folding happens only in consumers (e.g. the contract-v2 projection used
by learning, whose semantics this module does not change).

Identity threads downward: objective (with revision lineage) binds
execution, which binds operations (and background continuations).
Unknown stays unknown: an unset dimension is None, never a guess.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

RECORD_VERSION = 1
STORAGE_KEY = "execution_outcome_v1"

EXECUTION_NOT_STARTED = "not_started"
EXECUTION_RUNNING = "running"
EXECUTION_SUCCEEDED = "succeeded"
EXECUTION_FAILED = "failed"
EXECUTION_TIMEOUT = "timeout"
EXECUTION_SUPERSEDED = "superseded"

EVIDENCE_SUFFICIENT = "sufficient"
EVIDENCE_PARTIAL = "partial"
EVIDENCE_INSUFFICIENT = "insufficient"
EVIDENCE_CONTRADICTORY = "contradictory"

VERIFIED = "verified"
UNVERIFIED = "unverified"
UNSUPPORTED = "unsupported"

DELIVERY_STREAMING = "streaming"
DELIVERY_DELIVERED = "delivered"
DELIVERY_PARTIAL_PENDING = "partial_pending"
DELIVERY_FAILED = "failed_delivery"
DELIVERY_PENDING_CONTINUATION = "pending_continuation"

_EXECUTION_TRANSITIONS = {
    None: (
        EXECUTION_NOT_STARTED,
        EXECUTION_RUNNING,
        EXECUTION_SUCCEEDED,
        EXECUTION_FAILED,
        EXECUTION_TIMEOUT,
        EXECUTION_SUPERSEDED,
    ),
    EXECUTION_NOT_STARTED: (EXECUTION_RUNNING,),
    EXECUTION_RUNNING: (
        EXECUTION_SUCCEEDED,
        EXECUTION_FAILED,
        EXECUTION_TIMEOUT,
        EXECUTION_SUPERSEDED,
    ),
    EXECUTION_SUCCEEDED: (),
    EXECUTION_FAILED: (),
    EXECUTION_TIMEOUT: (),
    EXECUTION_SUPERSEDED: (),
}

_EVIDENCE_TRANSITIONS = {
    None: (
        EVIDENCE_SUFFICIENT,
        EVIDENCE_PARTIAL,
        EVIDENCE_INSUFFICIENT,
        EVIDENCE_CONTRADICTORY,
    ),
    EVIDENCE_SUFFICIENT: (EVIDENCE_CONTRADICTORY,),
    EVIDENCE_PARTIAL: (EVIDENCE_SUFFICIENT, EVIDENCE_CONTRADICTORY),
    EVIDENCE_INSUFFICIENT: (
        EVIDENCE_SUFFICIENT,
        EVIDENCE_PARTIAL,
        EVIDENCE_CONTRADICTORY,
    ),
    EVIDENCE_CONTRADICTORY: (),
}

_VERIFICATION_TRANSITIONS = {
    None: (VERIFIED, UNVERIFIED, UNSUPPORTED),
    VERIFIED: (),
    UNVERIFIED: (VERIFIED, UNSUPPORTED),
    UNSUPPORTED: (),
}

_DELIVERY_TRANSITIONS = {
    None: (DELIVERY_STREAMING, DELIVERY_DELIVERED, DELIVERY_PENDING_CONTINUATION),
    DELIVERY_STREAMING: (
        DELIVERY_DELIVERED,
        DELIVERY_PARTIAL_PENDING,
        DELIVERY_FAILED,
        DELIVERY_PENDING_CONTINUATION,
    ),
    DELIVERY_DELIVERED: (),
    DELIVERY_PARTIAL_PENDING: (DELIVERY_DELIVERED, DELIVERY_FAILED),
    DELIVERY_FAILED: (),
    DELIVERY_PENDING_CONTINUATION: (DELIVERY_DELIVERED, DELIVERY_FAILED),
}

_TRANSITIONS = {
    "execution_status": _EXECUTION_TRANSITIONS,
    "evidence_sufficiency": _EVIDENCE_TRANSITIONS,
    "result_verification": _VERIFICATION_TRANSITIONS,
    "delivery_status": _DELIVERY_TRANSITIONS,
}


class IllegalTransition(ValueError):
    pass


def new_operation_record(
    *,
    operation_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    objective_id: Optional[str] = None,
    supersedes_objective_id: Optional[str] = None,
    refinement_basis: Optional[str] = None,
    continuation_id: Optional[str] = None,
    operation_class: str = "unknown",
    producer: str = "unknown",
) -> Dict[str, Any]:
    """Create an empty per-operation record. All dimensions start unset."""
    return {
        "record_version": RECORD_VERSION,
        "record_id": f"oprec-{uuid.uuid4().hex[:12]}",
        "operation_id": operation_id,
        "operation_class": str(operation_class)[:120],
        "execution_id": execution_id,
        "objective_id": objective_id,
        "supersedes_objective_id": supersedes_objective_id,
        "refinement_basis": (str(refinement_basis)[:500] if refinement_basis else None),
        "continuation_id": continuation_id,
        "execution_status": None,
        "evidence_sufficiency": None,
        "evidence_missing_fields": [],
        "result_verification": None,
        "verifier_id": None,
        "evidence_ids": [],
        "delivery_status": None,
        "delivery_pending_operations": [],
        "transitions": [],
        "producer": str(producer)[:120],
    }


def transition(
    record: Dict[str, Any],
    dimension: str,
    value: Optional[str],
    *,
    producer: str = "unknown",
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Move one dimension forward, stamping who/when. Illegal moves raise."""
    allowed = _TRANSITIONS.get(dimension)
    if allowed is None:
        raise IllegalTransition(f"unknown dimension: {dimension!r}")
    current = record.get(dimension)
    if value is not None and value not in allowed.get(current, ()):
        raise IllegalTransition(f"{dimension}: {current!r} -> {value!r} is not a legal transition")
    record[dimension] = value
    entry: Dict[str, Any] = {
        "dimension": dimension,
        "from": current,
        "to": value,
        "at": time.time(),
        "producer": str(producer)[:120],
    }
    if isinstance(detail, dict):
        entry["detail"] = dict(detail)
    transitions = record.get("transitions")
    if not isinstance(transitions, list):
        transitions = []
        record["transitions"] = transitions
    transitions.append(entry)
    return record


def record_to_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-serializable copy for storage under the record's own keys."""
    import copy

    return copy.deepcopy(record)


def record_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Rehydrate a stored record, rejecting foreign versions and shapes."""
    if not isinstance(data, dict):
        raise ValueError("execution-outcome record must be a dict")
    if data.get("record_version") != RECORD_VERSION:
        raise ValueError(f"unsupported record version: {data.get('record_version')!r}")
    record = new_operation_record()
    for key in record:
        if key in data:
            record[key] = data[key]
    dimensions = (
        "execution_status",
        "evidence_sufficiency",
        "result_verification",
        "delivery_status",
    )
    for dimension in dimensions:
        value = record.get(dimension)
        if value is None:
            continue
        legal_values: set = set()
        for targets in _TRANSITIONS[dimension].values():
            legal_values.update(targets)
        if value not in legal_values:
            raise ValueError(f"illegal stored value {value!r} for {dimension}")
    return record


def open_dimensions(record: Dict[str, Any]) -> List[str]:
    """Dimensions still unknown — the work remaining on this operation."""
    return [dimension for dimension in _TRANSITIONS if record.get(dimension) is None]


def load_operation_records(metadata: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Operation records stored under the versioned key. Never parses
    other metadata keys; unknown shapes are skipped, not repaired."""
    if not isinstance(metadata, dict):
        return {}
    stored = metadata.get(STORAGE_KEY)
    if not isinstance(stored, dict):
        return {}
    operations = stored.get("operations")
    if not isinstance(operations, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for operation_id, record in operations.items():
        if isinstance(record, dict) and record.get("record_version") == RECORD_VERSION:
            out[str(operation_id)] = record
    return out


def store_operation_record(
    metadata: Optional[Dict[str, Any]],
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge one operation record under the versioned key, keyed by its
    operation id. Other operations and all other metadata keys pass
    through untouched."""
    merged: Dict[str, Any] = {}
    if isinstance(metadata, dict):
        merged = dict(metadata)
    operations: Dict[str, Any] = {}
    stored = merged.get(STORAGE_KEY)
    if isinstance(stored, dict):
        raw_operations = stored.get("operations")
        if isinstance(raw_operations, dict):
            operations = dict(raw_operations)
    operation_id = str(record.get("operation_id") or record.get("record_id"))
    operations[operation_id] = record_to_dict(record)
    merged[STORAGE_KEY] = {"record_version": RECORD_VERSION, "operations": operations}
    return merged
