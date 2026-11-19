"""Synthetic controls for the dedicated staged invoice Outlook dispatch."""
from __future__ import annotations

import asyncio

from core.outlook_draft_dispatch import (
    CREATE_STARTED_FIELD,
    DRAFT_ID_FIELD,
    SEND_STARTED_FIELD,
    dispatch_approved_outlook_draft,
)
from core.task_lifecycle import TaskLifecycleError, _approval_payload_hash


MAILBOX_TOKEN_ROW_ID = "synthetic-token-row-invoice"
MAILBOX_GRAPH_USER_ID = "actor-context"
SYNTHETIC_ACCESS_TOKEN = "synthetic-access-token-invoice"


def _payload() -> dict:
    return {
        "user_id": "actor-context",
        "to_recipients": ["customer@example.invalid"],
        "cc_recipients": [],
        "bcc_recipients": [],
        "subject": "Payment reminder for invoice INV-1",
        "body": "Hello,\n\nPlease pay invoice INV-1.\n\nSIGNED",
        "canvas_id": "canvas-op-context",
        "invoice": {"invoice_id": "inv-1", "invoice_number": "INV-1"},
        "native_draft": {"draft_id": "draft-canvas", "draft_revision": "rev-1"},
    }


class FakeLifecycle:
    def __init__(self, payload: dict):
        digest = _approval_payload_hash(payload)
        self.operation = {
            "operation_id": "op-send",
            "operation_type": "outbound",
            "status": "running",
            "execution_id": "exec-1",
            "approval": {
                "approved_by": "approver",
                "approved_at": "2026-11-19T00:00:00+00:00",
                "payload_sha256": digest,
            },
            "approval_request": {"payload_sha256": digest},
            "approved_payload_sha256": digest,
            "operation_binding": {
                "action_name": "invoice.send_reminder",
                "workspace_id": "ws-context",
                "account_id": "actor-context",
            },
        }
        self.record = {
            "task_revision": {"authorization": "authorized", "revision": 1},
            "operations": [self.operation],
        }

    def get_task(self, run_id):
        assert run_id == "run-context"
        return self.record

    def attach_operation_field(
            self, run_id, operation_id, key, value, *,
            expected_execution_id=None, expected_value=None):
        assert run_id == "run-context"
        assert operation_id == self.operation["operation_id"]
        assert expected_execution_id == "exec-1"
        if key in self.operation:
            raise TaskLifecycleError("field already present")
        self.operation[key] = value
        return self.operation


class FakeOutlook:
    def __init__(self, *, evidence_resolved: bool = True):
        self.create_calls = 0
        self.send_calls = 0
        self.evidence_resolved = evidence_resolved
        self.draft_id_at_send = None
        self.lifecycle = None
        self.token_row_id = MAILBOX_TOKEN_ROW_ID
        self.graph_user_id = MAILBOX_GRAPH_USER_ID
        self.access_token = SYNTHETIC_ACCESS_TOKEN

    async def _get_access_token(self, user_id):
        return self.access_token

    async def get_user_profile(self, user_id, token=None):
        assert token == self.access_token
        return {"id": self.graph_user_id}

    async def create_draft_with_immutable_id(self, **kwargs):
        self.create_calls += 1
        assert kwargs.pop("access_token", None) == self.access_token
        assert kwargs["to_recipients"] == ["customer@example.invalid"]
        assert kwargs["subject"] == "Payment reminder for invoice INV-1"
        return {
            "status": "created",
            "draft_id": "provider-draft",
            "http_status": 201,
        }

    async def send_existing_immutable_draft(
            self, *, user_id, immutable_message_id, access_token=None):
        self.send_calls += 1
        assert access_token == self.access_token
        assert immutable_message_id == "provider-draft"
        assert self.lifecycle.operation[CREATE_STARTED_FIELD]
        assert self.lifecycle.operation[DRAFT_ID_FIELD] == "provider-draft"
        assert self.lifecycle.operation[SEND_STARTED_FIELD]
        return {
            "status": "provider_accepted",
            "message_id": "provider-draft",
            "http_status": 202,
        }

    async def get_sent_message_evidence(
            self, user_id, immutable_message_id, access_token=None):
        assert access_token == self.access_token
        assert immutable_message_id == "provider-draft"
        if not self.evidence_resolved:
            return {"status": "unresolved", "resolved": False}
        return {
            "status": "resolved",
            "resolved": True,
            "id": "provider-draft",
            "isDraft": False,
            "conversationId": "conv-1",
            "internetMessageId": "<msg@example.invalid>",
        }


def _dispatch(lifecycle, outlook):
    return asyncio.run(dispatch_approved_outlook_draft(
        lifecycle=lifecycle,
        run_id="run-context",
        operation_id="op-send",
        execution_id="exec-1",
        outlook_service=outlook,
        payload=_payload(),
        scope={
            "action_name": "invoice.send_reminder",
            "workspace_id": "ws-context",
            "account_id": "actor-context",
        },
    ))


def test_dispatch_saves_draft_id_before_one_send_and_verifies():
    payload = _payload()
    lifecycle = FakeLifecycle(payload)
    outlook = FakeOutlook(evidence_resolved=True)
    outlook.lifecycle = lifecycle

    result = _dispatch(lifecycle, outlook)

    assert result["status"] == "sent_verified"
    assert result["accepted"] is True
    assert result["verified"] is True
    assert result["draft_id"] == "provider-draft"
    assert outlook.create_calls == 1
    assert outlook.send_calls == 1


def test_dispatch_keeps_202_accepted_distinct_from_unresolved_readback():
    payload = _payload()
    lifecycle = FakeLifecycle(payload)
    outlook = FakeOutlook(evidence_resolved=False)
    outlook.lifecycle = lifecycle

    result = _dispatch(lifecycle, outlook)

    assert result["status"] == "send_accepted"
    assert result["accepted"] is True
    assert result["verified"] is False
    assert result["draft_id"] == "provider-draft"
    assert outlook.create_calls == 1
    assert outlook.send_calls == 1


def test_dispatch_never_resends_after_send_started():
    payload = _payload()
    lifecycle = FakeLifecycle(payload)
    outlook = FakeOutlook(evidence_resolved=False)
    outlook.lifecycle = lifecycle

    first = _dispatch(lifecycle, outlook)
    second = _dispatch(lifecycle, outlook)

    assert first["status"] == "send_accepted"
    assert second["status"] == "unknown"
    assert second["reason"] == "send_phase_already_started"
    assert outlook.create_calls == 1
    assert outlook.send_calls == 1
