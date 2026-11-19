"""Focused synthetic tests for approved Outlook staged dispatch.

No database, no network, no workflow. The fake lifecycle implements only the
two TaskLifecycle methods the dispatcher uses, including the guarded-attach
preconditions; the fake provider records calls instead of reaching Graph.
"""
import asyncio
import copy

import pytest

from core.outlook_draft_dispatch import (
    CREATE_STARTED_FIELD,
    DRAFT_ID_FIELD,
    MAILBOX_FIELD,
    SEND_STARTED_FIELD,
    OutlookDispatchRefused,
    dispatch_approved_outlook_draft,
)
from core.task_lifecycle import TaskLifecycleError, _approval_payload_hash


MAILBOX_TOKEN_ROW_ID = "synthetic-token-row-owner"
MAILBOX_GRAPH_USER_ID = "owner@example.com"
SYNTHETIC_ACCESS_TOKEN = "synthetic-access-token"


def _mailbox():
    return {
        "token_row_id": MAILBOX_TOKEN_ROW_ID,
        "graph_user_id": MAILBOX_GRAPH_USER_ID,
    }


def _payload(**overrides):
    payload = {
        "user_id": "owner@example.com",
        "to_recipients": ["recipient@example.com"],
        "cc_recipients": [],
        "bcc_recipients": [],
        "subject": "Approved subject",
        "body": "Approved body",
        "conversation_id": None,
    }
    payload.update(overrides)
    return payload


def _scope(payload, **overrides):
    scope = {
        "action_name": "outlook.send_approved_draft",
        "workspace_id": "ws-1",
        "account_id": payload["user_id"],
    }
    scope.update(overrides)
    return scope


def _operation(payload, **overrides):
    digest = _approval_payload_hash(payload)
    operation = {
        "operation_id": "op-1",
        "operation_type": "outbound",
        "status": "running",
        "execution_id": "ex-1",
        "claimed_by": "test-worker",
        "operation_binding": {
            "action_name": "outlook.send_approved_draft",
            "workspace_id": "ws-1",
            "account_id": payload["user_id"],
        },
        "approval_request": {"payload_sha256": digest},
        "approval": {
            "payload_sha256": digest,
            "approved_by": "owner",
            "approved_at": "2026-11-19T00:00:00+00:00",
        },
        "approved_payload_sha256": digest,
    }
    operation.update(overrides)
    return operation


class _FakeLifecycle:
    def __init__(self, operation, *, authorization="authorized", events=None):
        self.record = {
            "task_revision": {"authorization": authorization},
            "operations": [operation],
        }
        self.events = events if events is not None else []

    def get_task(self, run_id):
        assert run_id == "run-1"
        return copy.deepcopy(self.record)

    def attach_operation_field(
        self,
        run_id,
        operation_id,
        key,
        value,
        *,
        expected_execution_id=None,
    ):
        assert run_id == "run-1"
        self.events.append(("attach", key))
        operation = self.record["operations"][0]
        assert operation["operation_id"] == operation_id
        if expected_execution_id is not None:
            if operation.get("status") != "running":
                raise TaskLifecycleError("operation is not running")
            if operation.get("execution_id") != expected_execution_id:
                raise TaskLifecycleError("execution claim mismatch")
            if key in operation:
                raise TaskLifecycleError("field is already present")
        operation[key] = copy.deepcopy(value)
        return copy.deepcopy(operation)


class _FakeOutlook:
    def __init__(
        self,
        *,
        create_result=None,
        send_result=None,
        evidence_result=None,
        events=None,
        token_row_id=MAILBOX_TOKEN_ROW_ID,
        graph_user_id=MAILBOX_GRAPH_USER_ID,
        access_token=SYNTHETIC_ACCESS_TOKEN,
    ):
        self.create_result = create_result
        self.send_result = send_result
        self.evidence_result = evidence_result
        self.events = events if events is not None else []
        self.create_calls = []
        self.send_calls = []
        self.evidence_calls = []
        self.token_row_id = token_row_id
        self.graph_user_id = graph_user_id
        self.access_token = access_token

    async def _get_access_token(self, user_id):
        return self.access_token

    async def get_user_profile(self, user_id, token=None):
        assert token == self.access_token
        return {"id": self.graph_user_id}

    async def create_draft_with_immutable_id(self, **kwargs):
        self.events.append(("provider", "create"))
        assert kwargs.pop("access_token", None) == self.access_token
        self.create_calls.append(kwargs)
        return copy.deepcopy(self.create_result)

    async def send_existing_immutable_draft(
        self, user_id, immutable_message_id, access_token=None,
    ):
        self.events.append(("provider", "send"))
        assert access_token == self.access_token
        self.send_calls.append((user_id, immutable_message_id))
        return copy.deepcopy(self.send_result)

    async def get_sent_message_evidence(
        self, user_id, immutable_message_id, access_token=None,
    ):
        self.events.append(("provider", "evidence"))
        assert access_token == self.access_token
        self.evidence_calls.append((user_id, immutable_message_id))
        return copy.deepcopy(self.evidence_result)


def _dispatch(lifecycle, outlook, payload, scope=None):
    return asyncio.run(dispatch_approved_outlook_draft(
        lifecycle=lifecycle,
        run_id="run-1",
        operation_id="op-1",
        execution_id="ex-1",
        outlook_service=outlook,
        payload=payload,
        scope=scope or _scope(payload),
    ))


def _accepted_send():
    return {
        "status": "provider_accepted",
        "message_id": "draft-1",
        "http_status": 202,
    }


def _resolved_evidence():
    return {"status": "resolved", "resolved": True}


def test_creates_once_commits_id_then_sends_once_and_verifies():
    payload = _payload()
    events = []
    lifecycle = _FakeLifecycle(_operation(payload), events=events)
    outlook = _FakeOutlook(
        create_result={
            "status": "created",
            "draft_id": "draft-1",
            "http_status": 201,
        },
        send_result=_accepted_send(),
        evidence_result=_resolved_evidence(),
        events=events,
    )

    result = _dispatch(lifecycle, outlook, payload)

    assert result["status"] == "sent_verified"
    assert result["accepted"] is True
    assert result["verified"] is True
    assert result["sent_items_verified"] is True
    assert result["draft_id"] == "draft-1"
    assert len(outlook.create_calls) == 1
    assert outlook.create_calls[0] == {
        "user_id": payload["user_id"],
        "to_recipients": payload["to_recipients"],
        "subject": payload["subject"],
        "body": payload["body"],
        "cc_recipients": [],
        "bcc_recipients": [],
        "conversation_id": None,
    }
    assert outlook.send_calls == [(payload["user_id"], "draft-1")]
    assert outlook.evidence_calls == [(payload["user_id"], "draft-1")]

    # The create reservation precedes the POST, the draft id is committed
    # BEFORE the send POST, and the send is reserved before it.
    create_reservation = events.index(("attach", CREATE_STARTED_FIELD))
    create_post = events.index(("provider", "create"))
    draft_commit = events.index(("attach", DRAFT_ID_FIELD))
    send_reservation = events.index(("attach", SEND_STARTED_FIELD))
    send_post = events.index(("provider", "send"))
    assert create_reservation < create_post
    assert create_post < draft_commit < send_reservation < send_post

    stored = lifecycle.record["operations"][0]
    assert stored[CREATE_STARTED_FIELD] == {"payload_sha256": _approval_payload_hash(payload)}
    assert stored[DRAFT_ID_FIELD] == "draft-1"
    assert stored[SEND_STARTED_FIELD] == {
        "draft_id": "draft-1",
        "payload_sha256": _approval_payload_hash(payload),
    }


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda op, payload: op.update({"approval": None}), "approval_missing"),
        (
            lambda op, payload: op["approval"].update({"approved_by": ""}),
            "approval_missing_approver",
        ),
        (
            lambda op, payload: op["approval"].update(
                {"payload_sha256": "wrong"}),
            "approval_payload_hash_mismatch",
        ),
        (
            lambda op, payload: op.update(
                {"approved_payload_sha256": "wrong"}),
            "approved_payload_hash_mismatch",
        ),
        (
            lambda op, payload: op["approval_request"].update(
                {"payload_sha256": "wrong"}),
            "approval_request_hash_mismatch",
        ),
        (
            lambda op, payload: op["operation_binding"].update(
                {"account_id": "other@example.com"}),
            "operation_scope_mismatch",
        ),
        (
            lambda op, payload: op["operation_binding"].update(
                {"workspace_id": "ws-other"}),
            "operation_scope_mismatch",
        ),
        (
            lambda op, payload: op.update({"status": "cancelled"}),
            "operation_not_running",
        ),
        (
            lambda op, payload: op.update({"execution_id": "ex-other"}),
            "execution_claim_mismatch",
        ),
        (
            lambda op, payload: op.update({"operation_type": "edit"}),
            "operation_not_outbound",
        ),
    ],
)
def test_refuses_without_exact_running_claim_approval_and_scope(
    mutate, reason,
):
    payload = _payload()
    operation = _operation(payload)
    mutate(operation, payload)
    lifecycle = _FakeLifecycle(operation)
    outlook = _FakeOutlook(
        create_result={"status": "created", "draft_id": "draft-1"},
        send_result=_accepted_send(),
        evidence_result=_resolved_evidence(),
    )

    with pytest.raises(OutlookDispatchRefused, match=reason):
        _dispatch(lifecycle, outlook, payload)

    assert outlook.create_calls == []
    assert outlook.send_calls == []
    assert outlook.evidence_calls == []


def test_refuses_a_cancelled_task_authorization():
    payload = _payload()
    lifecycle = _FakeLifecycle(
        _operation(payload), authorization="cancelled")
    outlook = _FakeOutlook(create_result={"status": "created", "draft_id": "d"})

    with pytest.raises(
        OutlookDispatchRefused, match="task_authorization_cancelled"):
        _dispatch(lifecycle, outlook, payload)

    assert outlook.create_calls == []


def test_started_create_phase_is_bound_to_the_approved_payload():
    payload = _payload(subject="new subject")
    operation = _operation(payload)
    operation[CREATE_STARTED_FIELD] = {
        "payload_sha256": _approval_payload_hash(
            _payload(subject="old subject")),
    }
    lifecycle = _FakeLifecycle(operation)
    outlook = _FakeOutlook(
        create_result={"status": "created", "draft_id": "draft-other"})

    with pytest.raises(
        OutlookDispatchRefused, match="dispatch_payload_mismatch"):
        _dispatch(lifecycle, outlook, payload)

    assert outlook.create_calls == []
    assert outlook.send_calls == []


def test_started_phase_without_a_mailbox_binding_is_refused():
    payload = _payload()
    operation = _operation(payload)
    operation[CREATE_STARTED_FIELD] = {
        "payload_sha256": _approval_payload_hash(payload),
    }
    operation[DRAFT_ID_FIELD] = "draft-existing"
    lifecycle = _FakeLifecycle(operation)
    outlook = _FakeOutlook(
        send_result=_accepted_send(),
        evidence_result=_resolved_evidence(),
    )

    with pytest.raises(
        OutlookDispatchRefused, match="mailbox_binding_missing"):
        _dispatch(lifecycle, outlook, payload)

    assert outlook.create_calls == []
    assert outlook.send_calls == []
    assert outlook.evidence_calls == []
    assert MAILBOX_FIELD not in lifecycle.record["operations"][0]


def test_create_unknown_is_never_recreated():
    payload = _payload()
    lifecycle = _FakeLifecycle(_operation(payload))
    outlook = _FakeOutlook(
        create_result={"status": "unknown", "reason": "transport_error"},
        send_result=_accepted_send(),
        evidence_result=_resolved_evidence(),
    )

    first = _dispatch(lifecycle, outlook, payload)
    assert first["status"] == "unknown"
    assert first["reason"] == "transport_error"
    assert first["draft_id"] is None
    assert len(outlook.create_calls) == 1

    second = _dispatch(lifecycle, outlook, payload)
    assert second["status"] == "unknown"
    assert second["reason"] == "create_phase_already_started"
    assert second["draft_id"] is None
    assert len(outlook.create_calls) == 1
    assert outlook.send_calls == []


def test_create_not_created_is_never_recreated_either():
    payload = _payload()
    lifecycle = _FakeLifecycle(_operation(payload))
    outlook = _FakeOutlook(
        create_result={
            "status": "not_created",
            "reason": "provider_rejected",
            "http_status": 403,
        },
        send_result=_accepted_send(),
        evidence_result=_resolved_evidence(),
    )

    first = _dispatch(lifecycle, outlook, payload)
    assert first["status"] == "not_created"
    assert first["accepted"] is None
    assert first["verified"] is False
    assert first["draft_id"] is None

    second = _dispatch(lifecycle, outlook, payload)
    assert second["status"] == "unknown"
    assert second["reason"] == "create_phase_already_started"
    assert len(outlook.create_calls) == 1
    assert outlook.send_calls == []


def test_crash_after_draft_commit_resumes_the_same_draft():
    payload = _payload()
    operation = _operation(payload)
    operation[CREATE_STARTED_FIELD] = {"payload_sha256": _approval_payload_hash(payload)}
    operation[DRAFT_ID_FIELD] = "draft-existing"
    operation[MAILBOX_FIELD] = _mailbox()
    lifecycle = _FakeLifecycle(operation)
    outlook = _FakeOutlook(
        send_result={
            "status": "provider_accepted",
            "message_id": "draft-existing",
            "http_status": 202,
        },
        evidence_result=_resolved_evidence(),
    )

    result = _dispatch(lifecycle, outlook, payload)

    assert result["status"] == "sent_verified"
    assert result["draft_id"] == "draft-existing"
    assert outlook.create_calls == []
    assert outlook.send_calls == [(payload["user_id"], "draft-existing")]
    assert SEND_STARTED_FIELD in lifecycle.record["operations"][0]


def test_send_started_is_never_resent_even_without_a_result():
    payload = _payload()
    operation = _operation(payload)
    operation[CREATE_STARTED_FIELD] = {}
    operation[DRAFT_ID_FIELD] = "draft-existing"
    operation[SEND_STARTED_FIELD] = {"draft_id": "draft-existing"}
    operation[MAILBOX_FIELD] = _mailbox()
    lifecycle = _FakeLifecycle(operation)
    outlook = _FakeOutlook(
        create_result={"status": "created", "draft_id": "draft-other"},
        send_result=_accepted_send(),
        evidence_result={
            "status": "unresolved",
            "resolved": False,
            "reason": "message_not_found",
        },
    )

    result = _dispatch(lifecycle, outlook, payload)

    assert result["status"] == "unknown"
    assert result["reason"] == "send_phase_already_started"
    assert result["draft_id"] == "draft-existing"
    assert result["accepted"] is None
    assert result["verified"] is False
    assert outlook.create_calls == []
    assert outlook.send_calls == []
    assert outlook.evidence_calls == [
        (payload["user_id"], "draft-existing")]


def test_send_unknown_is_never_resent_and_keeps_remote_id():
    payload = _payload()
    lifecycle = _FakeLifecycle(_operation(payload))
    outlook = _FakeOutlook(
        create_result={
            "status": "created",
            "draft_id": "draft-1",
            "http_status": 201,
        },
        send_result={
            "status": "unknown",
            "reason": "transport_error",
            "message_id": "draft-1",
        },
        evidence_result={"status": "unresolved", "resolved": False},
    )

    first = _dispatch(lifecycle, outlook, payload)
    assert first["status"] == "unknown"
    assert first["draft_id"] == "draft-1"
    assert first["accepted"] is None
    assert first["verified"] is False
    assert len(outlook.send_calls) == 1

    second = _dispatch(lifecycle, outlook, payload)
    assert second["status"] == "unknown"
    assert second["reason"] == "send_phase_already_started"
    assert second["draft_id"] == "draft-1"
    assert len(outlook.create_calls) == 1
    assert len(outlook.send_calls) == 1
    assert lifecycle.record["operations"][0][DRAFT_ID_FIELD] == "draft-1"


def test_conclusive_send_refusal_keeps_remote_id_for_reconciliation():
    payload = _payload()
    lifecycle = _FakeLifecycle(_operation(payload))
    outlook = _FakeOutlook(
        create_result={"status": "created", "draft_id": "draft-1"},
        send_result={
            "status": "not_sent",
            "reason": "provider_rejected",
            "message_id": "draft-1",
            "http_status": 403,
        },
        evidence_result=_resolved_evidence(),
    )

    result = _dispatch(lifecycle, outlook, payload)

    assert result["status"] == "not_sent"
    assert result["accepted"] is False
    assert result["verified"] is False
    assert result["draft_id"] == "draft-1"
    assert result["http_status"] == 403
    assert outlook.evidence_calls == []
    assert lifecycle.record["operations"][0][DRAFT_ID_FIELD] == "draft-1"


def test_accepted_send_stays_accepted_when_evidence_does_not_resolve():
    payload = _payload()
    lifecycle = _FakeLifecycle(_operation(payload))
    outlook = _FakeOutlook(
        create_result={"status": "created", "draft_id": "draft-1"},
        send_result=_accepted_send(),
        evidence_result={
            "status": "unresolved",
            "resolved": False,
            "reason": "message_not_found",
        },
    )

    result = _dispatch(lifecycle, outlook, payload)

    assert result["status"] == "send_accepted"
    assert result["accepted"] is True
    assert result["verified"] is False
    assert result["sent_items_verified"] is False
    assert result["draft_id"] == "draft-1"
