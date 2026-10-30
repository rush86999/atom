"""Environment-gated controlled outbound transport for acceptance runs.

This module is imported only when ``ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1``.
It is not a production sender: it writes JSON lines to a local outbox and
reports provider acceptance. The default registry never registers it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from core.assignment_executor import (
    ExternalOutcomeUnknown,
    WaitingForExternal,
    compose_outbound_content,
    default_adapter_registry,
)


def _outbox_path() -> Path:
    return Path(os.getenv("ATOM_ASSIGNMENT_OUTBOX") or
                "/tmp/atom-assignment-outbox.jsonl")


async def _controlled_send(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    content = compose_outbound_content(inputs, context)
    outbox = _outbox_path()
    outbox.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "operation_id": (context.get("step") or {}).get("operation_id"),
        "to": content.get("to"),
        "subject": content.get("subject"),
        "body": content.get("body"),
        "teaching_revision": (context.get("teaching") or {}).get(
            "revision") or "",
    }
    existing = []
    if outbox.exists():
        existing = [json.loads(line) for line in outbox.read_text().splitlines()
                    if line.strip()]
    if any(item.get("operation_id") == record["operation_id"]
           for item in existing):
        return {"status": "applied", "summary": "already in controlled outbox",
                "provider_state": "sent",
                "provider_ref": record["operation_id"]}
    existing.append(record)
    outbox.write_text("\n".join(json.dumps(item) for item in existing) + "\n")
    if os.getenv("ATOM_ASSIGNMENT_CONTROLLED_OUTCOME") == "uncertain":
        raise ExternalOutcomeUnknown(
            "controlled transport lost the response after acceptance",
            evidence=str(outbox))
    return {
        "status": "applied",
        "summary": "controlled provider accepted",
        "provider_state": "sent",
        "provider_ref": record["operation_id"],
    }


def _controlled_prepare(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    content = compose_outbound_content(inputs, context)
    payload = {
        "to": content.get("to"),
        "subject": content.get("subject"),
        "body": content.get("body"),
        "attachment": inputs.get("attachment"),
        "teaching_revision": (context.get("teaching") or {}).get(
            "revision") or "",
    }
    return {
        "payload": payload,
        "artifact_revision": inputs.get("draft_revision"),
        "requested_by": context.get("employee_id") or "",
    }


async def _controlled_wait(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    step = context.get("step") or {}
    response = step.get("external_response")
    if response:
        return {"status": "applied", "summary": "controlled reply received",
                "value": response.get("response")}
    raise WaitingForExternal({
        "event": "email",
        "state": "waiting_for_external",
        "party": inputs.get("party") or "controlled responder",
        "correlation_id": inputs.get("correlation_id"),
        "resume_on": "response",
        "detail": inputs.get("detail") or "waiting for the controlled reply",
        "fact": inputs.get("fact") or "",
    })


default_adapter_registry.register(
    "assignment.controlled_outbox",
    _controlled_send,
    prepare=_controlled_prepare,
    description="Acceptance-only local outbox sender",
    metadata={"effect": "external", "required_actions": ["outbound"],
              "requires_approval": True,
              "allow_standing_authorization": False},
)
default_adapter_registry.register(
    "assignment.controlled_wait",
    _controlled_wait,
    description="Acceptance-only external reply wait",
    metadata={"effect": "read_only", "required_actions": ["retrieve"],
              "allow_standing_authorization": False},
)
