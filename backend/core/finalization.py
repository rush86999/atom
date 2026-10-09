"""Finalization layer — M1 slice (review rounds 19–26 scope).

M1's first obligation (the frozen failure-concealment case): when an
execution fails, the delivered response must PRESERVE EXECUTION IDENTITY
and REPORT THE FAILURE ACCURATELY. The legacy route-level fallback text
("Message processed successfully") concealed a failed execution and
dropped its id (frozen evidence: frozen_trace__1790368265.json; execution
row status=failed while the API claimed success).

Domain-independent by contract (04_CONTRACTS): the finalizer consumes the
execution record's own status — it never diagnoses causes, never repairs
the underlying failure, and adds no business vocabulary. This module is
NEW code behind a capability flag; the integration seam (chat_routes
response assembly) is a separately coordinated change. The editor
exception that triggers the failure in the acceptance case is deliberately
LEFT UNREPAIRED in this baseline: M1 is credited for accurate reporting,
never for the fix.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

FINALIZATION_VERSION = "m1"
UNKNOWN_OUTCOME_MESSAGE = (
    "This turn's outcome could not be verified; nothing it "
    "attempted should be assumed complete."
)


def finalize_payload(
    execution: Optional[Dict[str, Any]],
    drafted: Dict[str, Any],
) -> Dict[str, Any]:
    """Finalize a turn's response payload against its execution record.

    Rules (M1):
    - Execution identity is ALWAYS preserved: the payload carries the
      execution id of the turn that produced it, whatever happened.
    - A FAILED execution is delivered as an accurate failure: success is
      forced false, the message names the failure and its stage from the
      execution record, and no success-shaped wording survives.
    - A drafted structured error is NEVER rewritten: when the reply leg
      already produced a specific terminal envelope (error_code plus a
      real message, e.g. the provider-credit failure with
      failure_reason/recovery_url), finalization keeps its message and
      fields verbatim. Rebuilding record-derived text here truncated the
      cause and cut off the remedy (case-5 finding, 2026-10-06). The
      generic record-derived message is only synthesized when the draft
      carries no specific message.
    - Unknown/missing execution records are delivered as UNKNOWN — never
      rounded to success.
    - This function never fabricates content: it adjusts status, identity,
      and the failure message only. It never adds failure fields to a
      success, and never strips the drafted failure fields.
    """
    payload = dict(drafted or {})
    exec_id = (execution or {}).get("execution_id") or payload.get("execution_id")
    status = (execution or {}).get("status")

    if exec_id:
        payload["execution_id"] = exec_id

    if status == "failed":
        payload["success"] = False
        payload["error_code"] = payload.get("error_code") or "execution_failed"
        drafted_message = str(payload.get("message") or "")
        if drafted_message.strip() and drafted_message.strip() not in (
                "Message processed successfully",):
            # A specific terminal envelope is already drafted — keep it
            # verbatim (message, error_code, failure_reason, recovery_url).
            # The previous rebuild replaced it with record-derived generic
            # text, truncating the cause to 300 chars and dropping the
            # remedy that follows it (live case-5 T2: the persisted row
            # carried the generic prefix, not the credit text).
            # Fields ride the dict copy; pin them explicitly so the
            # contract does not depend on copy semantics.
            for _key in ("failure_reason", "recovery_url"):
                _value = (drafted or {}).get(_key)
                if _value is not None:
                    payload[_key] = _value
        else:
            stage = (execution or {}).get("failure_stage") or "execution"
            summary = str((execution or {}).get("result_summary") or "the operation failed")
            payload["message"] = (
                f"This turn failed and nothing it attempted should be assumed "
                f"complete. Failure at {stage}: {summary[:300]} "
                f"(execution {exec_id})" if exec_id else
                f"This turn failed and nothing it attempted should be assumed "
                f"complete. Failure at {stage}: {summary[:300]}"
            )
        data = payload.get("data")
        if isinstance(data, dict):
            data.pop("deterministic_delivery", None)
            payload["data"] = data
    elif status in (None, "unknown", ""):
        # Unknown stays unknown — NEVER delivered as success, and a
        # route-level fallback text is not an outcome: replace it.
        payload["success"] = False
        if not payload.get("message") or payload["message"].strip() in (
                "Message processed successfully", ""):
            payload["message"] = UNKNOWN_OUTCOME_MESSAGE
    return payload


def execution_record_from_row(row: Optional[Dict[str, Any]],
                              execution_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Adapt a persisted agent_executions row (+id) into the record shape
    finalize_payload consumes. Harness/production seam."""
    if row is None and not execution_id:
        return None
    meta: Dict[str, Any] = {}
    raw = (row or {}).get("metadata_json")
    if isinstance(raw, dict):
        meta = raw
    elif isinstance(raw, str):
        try:
            import json as _json
            parsed = _json.loads(raw or "{}")
            if isinstance(parsed, dict):
                meta = parsed
        except Exception:
            meta = {}
    cont = meta.get("continuation") or {}
    return {
        "execution_id": execution_id or (row or {}).get("id"),
        "status": (row or {}).get("status"),
        "result_summary": (row or {}).get("result_summary"),
        "failure_stage": cont.get("failure_stage") or (row or {}).get("failure_stage"),
    }
