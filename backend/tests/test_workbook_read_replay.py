from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.workbook_read_replay as replay
from core.chat_tool_planner import _user_facing_workbook_answer
from scripts.workbook_read_replay import (
    FILE_NAME,
    TARGETS,
    TokenFileError,
    auth_report,
    evaluate,
    evaluate_retry,
    flatten_trace,
    identity_summary,
    parse_bullet_outcomes,
    parse_outcomes,
    parse_table_outcomes,
    pending_acknowledgement,
    read_token_file,
    resolve_session,
    verify_session,
)


def _reply() -> str:
    rows = [
        "| item | outcome | evidence |",
        "|---|---|---|",
        "| 381 | FOUND | Sheet1!A1 R1 (prices: B1=100) |",
        "| U-22 | FOUND | Sheet1!A2 R2 (prices: B2=200) |",
        "| 622 | FOUND | Sheet1!A3 R3 (prices: B3=300) |",
        "| SLE24-16 | FOUND | Sheet1!A4 R4 (prices: B4=400) |",
        "| GSL48-16 | FOUND | Sheet1!A5 R5 (prices: B5=500) |",
        "| GSL24-16 | NOT FOUND IN INDEXED CONTENT | all 5 indexed sheets probed |",
        "| SLE16-8 | NOT FOUND IN INDEXED CONTENT | all 5 indexed sheets probed |",
        "| U-38 | NOT FOUND IN INDEXED CONTENT | all 5 indexed sheets probed |",
    ]
    return "\n".join([
        f"Workbook read: {FILE_NAME}",
        "Source: MATERIALIZED COPY — resource=r1, content_hash=abc123, ingested=2026-09-24",
        "Coverage — indexed sheets=5; indexed content searched; no absolute absence claim",
        "Per-item results:",
        *rows,
    ])


def _bullet_reply() -> str:
    """Synthetic saved-answer delivery: one markdown bullet per item.

    The three shapes the async contract must prove are all present: a price
    with exact sheet/cell lineage, a 10-row ambiguity, and a scoped miss.
    """
    return "\n".join([
        f"From the saved copy of {FILE_NAME} (saved 2026-09-07):",
        "Checked 8 items — 4 with values, 1 need your pick, 3 no match.",
        "",
        "- **381** — 2,450 'PRICE' (RoperWhitney sheet, row 88, "
        "cell E88, matched at A88)",
        "- **U-22** — 1,777 'List Price' (LINMAC sheet, row 26, "
        "cell C26, matched at A26)",
        "- **622** — 10 possible rows (RoperWhitney 4, Tennsmith 3, "
        "LINMAC 3) — which sheet or exact code do you mean?",
        "- **SLE24-16** — 8,880 'PRICE' (Tennsmith sheet, row 101, "
        "cell E101, matched at A101)",
        "- **GSL48-16** — 14,166 'PRICE' (Tennsmith sheet, row 106, "
        "cell E106, matched at A106)",
        "- **GSL24-16** — no match in this copy",
        "- **SLE16-8** — no match in this copy",
        "- **U-38** — no match in this copy",
        "",
        f"From the saved copy of {FILE_NAME} (saved 2026-09-07) — searched "
        "all 3 sheets of this copy. A newer version of the file may differ; "
        "no-match lines are about this copy, not the live file.",
    ])


def _serving_identity():
    return {
        "instance_id": "i1", "source_id": "s1", "revision": "r1",
        "started_at": "t1", "pid": 1,
    }


def _saved_result() -> dict:
    return {
        "status": "retrieved",
        "identity": {
            "resource_id": "synthetic-resource-1",
            "content_hash": "a" * 40,
            "evidence_kind": "materialized_copy",
            "workbook_read": {"file_name": FILE_NAME, "content_hash": "a" * 40},
        },
        "execution_id": "exec-async-1",
        "retrieved_at": 123.0,
        "attempt_id": "attempt-async-1",
        "evidence_revision": "rev-async-1",
        "structured_result": {
            "attempt_id": "attempt-async-1",
            "evidence_revision": "rev-async-1",
            "source_identity": {
                "file_name": FILE_NAME,
                "resource_id": "synthetic-resource-1",
                "content_hash": "a" * 40,
                "evidence_kind": "materialized_copy",
            },
        },
    }


def _async_states(reply: str):
    before = _saved_result()
    after = dict(before)
    after["status"] = "delivered"
    after["delivered_at"] = 124.0
    after["delivery_pin"] = {"delivered_text": reply[:24000]}
    state_after_2 = {
        "status": "pending",
        "result_status": "retrieved",
        "result": before,
        "read_error": "",
    }
    state_after_3 = {
        "status": "delivered",
        "result_status": "delivered",
        "result": after,
        "read_error": "",
    }
    return state_after_2, state_after_3


def _async_trace():
    return [{
        "step_type": "observation",
        "observation": f"{FILE_NAME} 381 datasets",
    }]


def test_user_facing_workbook_answer_removes_protocol_but_keeps_table():
    raw = "\n".join([
        "LIVE TOOL RESULTS (datasets.named-file) — the query NAMED this file",
        "MATERIALIZED COPY — source=zoho, resource=r1, ingested=t, content_hash=h",
        "COVERAGE LIMITS — indexed content; do not claim absence from the workbook and do not substitute other files' rows.",
        "PER-ITEM OUTCOMES (deterministic, rendered from the scan — reproduce VERBATIM; do not recount or re-derive):",
        "| item | outcome | evidence |",
        "| 381 | FOUND | Sheet1!A1 R1 |",
        "WORKBOOK READ ARTIFACT: internal",
        "TARGET 381: FOUND | Sheet1!A1",
    ])
    clean = _user_facing_workbook_answer(raw)
    assert "LIVE TOOL RESULTS" not in clean
    assert "WORKBOOK READ ARTIFACT" not in clean
    assert "reproduce VERBATIM" not in clean
    assert "| 381 | FOUND | Sheet1!A1 R1 |" in clean


def test_flatten_trace_reads_nested_runs():
    payload = {"runs": [{"steps": [
        {"step_type": "thought", "observation": "Consolidated Price List 2019.xlsx 381"}
    ]}]}
    steps = flatten_trace(payload)
    assert len(steps) == 1
    assert "Consolidated" in steps[0]["observation"]


def test_parse_outcomes_keeps_exact_requested_targets():
    rows = parse_outcomes(_reply())
    assert [row["target"] for row in rows] == list(TARGETS)


def test_evaluate_accepts_complete_structured_closure():
    identity = {
        "instance_id": "i1", "source_id": "s1", "revision": "r1",
        "started_at": "t1", "pid": 1,
    }
    report = evaluate(
        identity,
        identity,
        {"success": True},
        {"success": True, "message": _reply(), "model": "deterministic",
         "data": {"deterministic_delivery": True}},
        [{"step_type": "observation", "observation": "Consolidated Price List 2019.xlsx 381 datasets"}],
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        {"status": "served", "read_error": ""},
    )
    assert report["all_pass"], report["checks"]


def test_evaluate_accepts_outage_mode_and_retrieved_delivery_state():
    identity = {
        "instance_id": "i1", "source_id": "s1", "revision": "r1",
        "started_at": "t1", "pid": 1,
    }
    report = evaluate(
        identity,
        identity,
        {"success": False, "message": "temporarily unavailable"},
        {"success": True, "message": _reply(), "model": "deterministic",
         "data": {"deterministic_delivery": True}},
        [{"step_type": "observation", "observation": "Consolidated Price List 2019.xlsx 381 datasets"}],
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        {
            "status": "retrieved",
            "result_status": "retrieved",
            "read_error": "",
        },
        "r1",
        True,
    )
    assert report["all_pass"], report["checks"]


def test_evaluate_retry_requires_persisted_result_unchanged():
    result = {
        "status": "retrieved",
        "identity": {
            "resource_id": "r1",
            "workbook_read": {"file_name": FILE_NAME, "content_hash": "h"},
        },
        "execution_id": "exec-1",
        "retrieved_at": 123.0,
    }
    before = {
        "status": "retrieved",
        "result_status": "retrieved",
        "result": result,
    }
    after_result = dict(result)
    after_result["status"] = "delivered"
    after_result["delivered_at"] = 124.0
    after = {
        "status": "delivered",
        "result_status": "delivered",
        "result": after_result,
    }
    report = evaluate_retry(
        before,
        after,
        {
            "success": True,
            "model": "deterministic",
            "message": _reply(),
            "data": {"deterministic_delivery": True},
        },
    )
    assert report["all_pass"], report["checks"]


# --- async WorkDrive delivery (turn 2 ack, turn 3 saved bullets) -----------

def test_bullet_parser_reads_all_three_saved_answer_shapes():
    rows = parse_bullet_outcomes(_bullet_reply())
    assert [row["target"] for row in rows] == list(TARGETS)
    by_target = {row["target"]: row for row in rows}
    assert by_target["U-22"]["kind"] == "found"
    assert "cell C26" in by_target["U-22"]["evidence"]
    assert by_target["622"]["kind"] == "ambiguous"
    assert "10 possible rows" in by_target["622"]["evidence"]
    assert by_target["U-38"]["kind"] == "absent"
    assert "no match in this copy" in by_target["U-38"]["evidence"]
    # The saved answer is bullets only: the synchronous table parser finds
    # nothing to count twice.
    assert parse_table_outcomes(_bullet_reply()) == []
    assert len(parse_outcomes(_bullet_reply())) == len(TARGETS)


def test_pending_acknowledgement_only_accepts_a_pending_non_delivery():
    pending = {"status": "pending", "result_status": None}
    assert pending_acknowledgement(
        "I'm reading the saved copy now — I'll return the item statuses "
        "when it lands.", pending)
    assert not pending_acknowledgement(_bullet_reply(), pending)
    assert not pending_acknowledgement(_reply(), pending)
    assert not pending_acknowledgement(
        "still pending", {"status": "retrieved", "result_status": "retrieved"})
    assert not pending_acknowledgement("", pending)


def test_evaluate_accepts_async_ack_then_turn3_bullet_delivery():
    identity = _serving_identity()
    state_after_2, state_after_3 = _async_states(_bullet_reply())
    report = evaluate(
        identity,
        identity,
        {"success": True},
        {
            "success": True,
            "message": "I'm reading the saved copy now — I'll return the "
                       "item statuses when it lands.",
        },
        _async_trace(),
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
        r3={
            "success": True,
            "model": "deterministic",
            "message": _bullet_reply(),
            "data": {"deterministic_delivery": True},
        },
        state_after_3=state_after_3,
    )
    assert report["async_delivery"] is True
    assert report["all_pass"], {
        key: value for key, value in report["checks"].items() if not value
    }
    assert report["checks"]["turn2_acknowledgement"] is True
    assert report["checks"]["turn3_delivered"] is True
    assert report["checks"]["markdown_bullets"] is True
    assert report["checks"]["delivered_statuses"] is True
    assert report["checks"]["coverage_present"] is True
    assert report["checks"]["provenance_present"] is True
    assert report["checks"]["named_file_only"] is True


def test_evaluate_async_requires_the_saved_answer_not_a_second_read():
    identity = _serving_identity()
    state_after_2, state_after_3 = _async_states(_bullet_reply())
    report = evaluate(
        identity,
        identity,
        {"success": True},
        {"success": True, "message": "Reading it now."},
        _async_trace(),
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
        r3={
            "success": True,
            "model": "deterministic",
            "message": _bullet_reply(),
            "data": {"deterministic_delivery": True},
        },
        state_after_3=state_after_3,
    )
    assert report["all_pass"]
    retry = evaluate_retry(
        state_after_2, state_after_3,
        {
            "success": True,
            "model": "deterministic",
            "message": _bullet_reply(),
            "data": {"deterministic_delivery": True},
        },
        async_delivery=True,
    )
    assert retry["all_pass"], retry["checks"]

    # A turn-3 re-read would change the retrieval timestamp and identity.
    reread_result = dict(state_after_3["result"])
    reread_result["retrieved_at"] = 999.0
    reread = evaluate_retry(
        state_after_2,
        {**state_after_3, "result": reread_result},
        {
            "success": True,
            "model": "deterministic",
            "message": _bullet_reply(),
            "data": {"deterministic_delivery": True},
        },
        async_delivery=True,
    )
    assert reread["checks"]["no_reread"] is False
    assert reread["all_pass"] is False

    # No pinned delivery means the turn cannot prove it served the saved
    # answer instead of re-rendering a fresh read.
    unpinned = dict(state_after_3["result"])
    unpinned.pop("delivery_pin", None)
    report = evaluate_retry(
        state_after_2,
        {**state_after_3, "result": unpinned},
        {
            "success": True,
            "model": "deterministic",
            "message": _bullet_reply(),
            "data": {"deterministic_delivery": True},
        },
        async_delivery=True,
    )
    assert report["checks"]["delivered_answer_pinned"] is False
    assert report["all_pass"] is False


@pytest.mark.parametrize(
    "mutate, failing_check",
    [
        (lambda text: text.replace("searched all 3 sheets of this copy", ""),
         "coverage_present"),
        (lambda text: text.replace(
            "From the saved copy of", "From an unnamed file; original:"),
         "provenance_present"),
        (lambda text: text + "\nAlso Sept 2026 Email Prices.xlsx",
         "named_file_only"),
        (lambda text: "\n".join(
            line for line in text.splitlines()
            if "**SLE16-8**" not in line), "eight_structured_outcomes"),
        (lambda text: text.replace(
            "- **GSL24-16** — no match in this copy",
            "- **GSL24-16** — 2 possible rows (Tennsmith 2)"),
         "missing_outcomes"),
    ],
)
def test_evaluate_async_rejects_incomplete_saved_answers(mutate, failing_check):
    identity = _serving_identity()
    reply = mutate(_bullet_reply())
    state_after_2, state_after_3 = _async_states(reply)
    report = evaluate(
        identity,
        identity,
        {"success": True},
        {"success": True, "message": "Reading it now."},
        _async_trace(),
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
        r3={
            "success": True,
            "model": "deterministic",
            "message": reply,
            "data": {"deterministic_delivery": True},
        },
        state_after_3=state_after_3,
    )
    assert report["checks"][failing_check] is False, report["checks"]
    assert report["all_pass"] is False


def test_evaluate_async_ack_without_turn3_cannot_close():
    identity = _serving_identity()
    state_after_2, _ = _async_states(_bullet_reply())
    report = evaluate(
        identity,
        identity,
        {"success": True},
        {"success": True, "message": "Reading it now."},
        _async_trace(),
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
    )
    assert report["async_delivery"] is False
    assert report["all_pass"] is False


# --- strict direct WorkDrive proof survives the async delivery --------------

def _strict_async_fixture(reply: str):
    from core.workdrive_direct_proof import (
        DOWNLOADED_KIND,
        RECEIPT_SCHEMA,
        build_workdrive_proof,
    )

    resource_id = "synthetic-resource-1"
    sha256 = hashlib.sha256(b"synthetic-workbook-bytes").hexdigest()
    proof = build_workdrive_proof(
        resource_id=resource_id,
        downloaded_sha256=sha256,
        downloaded_bytes=1234,
        execution_id="exec-async-1",
        file_name=FILE_NAME,
        receipt={
            "schema": RECEIPT_SCHEMA,
            "sha256": sha256,
            "resource_id": resource_id,
            "execution_id": "exec-async-1",
        },
    )
    identity = {
        "resource_id": resource_id,
        "content_hash": sha256,
        "content_sha256": sha256,
        "evidence_kind": DOWNLOADED_KIND,
        "execution_id": "exec-async-1",
        "direct_source_proof": proof,
        "workbook_read": {"file_name": FILE_NAME},
    }
    structured = {
        "attempt_id": "attempt-async-1",
        "evidence_revision": "rev-async-1",
        "source_identity": {
            "file_name": FILE_NAME,
            "resource_id": resource_id,
            "content_hash": sha256,
            "evidence_kind": DOWNLOADED_KIND,
            "direct_source_proof": proof,
        },
        "direct_source_proof": proof,
    }
    result = {
        "status": "retrieved",
        "identity": identity,
        "structured_result": structured,
        "direct_source_proof": proof,
        "execution_id": "exec-async-1",
        "retrieved_at": 123.0,
        "attempt_id": "attempt-async-1",
        "evidence_revision": "rev-async-1",
    }
    after = dict(result)
    after["status"] = "delivered"
    after["delivery_pin"] = {"delivered_text": reply[:24000]}
    state_after_2 = {
        "status": "pending", "result_status": "retrieved",
        "result": result, "read_error": "",
    }
    state_after_3 = {
        "status": "delivered", "result_status": "delivered",
        "result": after, "read_error": "",
    }
    return state_after_2, state_after_3, resource_id, sha256


def _strict_async_report(reply: str, *, drop_proof: bool = False):
    state_after_2, state_after_3, resource_id, sha256 = (
        _strict_async_fixture(reply))
    if drop_proof:
        result = state_after_3["result"]
        result.pop("direct_source_proof", None)
        result["identity"] = {
            key: value for key, value in result["identity"].items()
            if key not in ("direct_source_proof", "content_sha256")
        }
        result["structured_result"] = {
            "source_identity": {
                key: value
                for key, value in result["structured_result"][
                    "source_identity"].items()
                if key not in ("direct_source_proof", "content_sha256")
            }
        }
    identity = _serving_identity()
    return evaluate(
        identity,
        identity,
        {"success": True},
        {"success": True, "message": "Reading it now."},
        _async_trace(),
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
        strict_workdrive_proof=True,
        expected_resource_id=resource_id,
        expected_sha256=sha256,
        r3={
            "success": True,
            "model": "deterministic",
            "message": reply,
            "data": {"deterministic_delivery": True},
        },
        state_after_3=state_after_3,
    )


def test_evaluate_async_preserves_strict_exact_source_proof():
    report = _strict_async_report(_bullet_reply())
    assert report["all_pass"], {
        key: value for key, value in report["checks"].items() if not value
    }
    assert report["checks"]["strict_workdrive_all_pass"] is True
    assert report["checks"]["strict_workdrive_proof_same_execution"] is True
    assert report["checks"]["strict_answer_not_materialized"] is True


def test_evaluate_async_strict_proof_fails_closed_without_joined_proof():
    report = _strict_async_report(_bullet_reply(), drop_proof=True)
    assert report["checks"]["strict_workdrive_proof_present"] is False
    assert report["checks"]["strict_workdrive_no_materialized_fallback"] is False
    assert report["all_pass"] is False


def test_evaluate_async_strict_rejects_materialized_answer_language():
    reply = _bullet_reply().replace(
        "From the saved copy of", "Source: MATERIALIZED COPY. From the copy of"
    )
    report = _strict_async_report(reply)
    assert report["checks"]["strict_answer_not_materialized"] is False
    assert report["all_pass"] is False


# --- server-issued session from an explicit private token file -------------

class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        return self.response


class _FakeAsyncClient(_FakeClient):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def _token_file(tmp_path, content="server-token", mode=0o600):
    path = tmp_path / "session.token"
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


def test_read_token_file_requires_an_explicit_private_file(tmp_path):
    private = _token_file(tmp_path, " header.payload.signature\n")
    assert read_token_file(str(private)) == "header.payload.signature"

    with pytest.raises(TokenFileError):
        read_token_file(str(tmp_path / "missing.token"))

    empty = _token_file(tmp_path, "   \n")
    with pytest.raises(TokenFileError):
        read_token_file(str(empty))

    multiple = _token_file(tmp_path, "one\ntwo\n")
    with pytest.raises(TokenFileError):
        read_token_file(str(multiple))

    with pytest.raises(TokenFileError):
        read_token_file(str(tmp_path))


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes only")
def test_read_token_file_rejects_shared_permissions(tmp_path):
    shared = _token_file(tmp_path, "server-token", mode=0o644)
    with pytest.raises(TokenFileError) as excinfo:
        read_token_file(str(shared))
    assert "private" in str(excinfo.value)
    assert "server-token" not in str(excinfo.value)


def test_identity_summary_accepts_flat_and_wrapped_me_payloads():
    flat = {"id": "u1", "email": "person@example.com", "role": "admin"}
    wrapped = {
        "success": True,
        "data": {"user_id": "u2", "role": "workspace_admin"},
    }
    assert identity_summary(flat)["user_id"] == "u1"
    assert identity_summary(wrapped)["user_id"] == "u2"
    assert identity_summary({"user": {"id": "u3"}})["user_id"] == "u3"
    assert "email" not in identity_summary(flat)
    assert identity_summary({}) == {}


def test_verify_session_uses_the_authenticated_me_endpoint():
    client = _FakeClient(_FakeResponse(
        200, {"success": True, "data": {"user_id": "u9", "role": "admin"}}
    ))
    identity, meta = asyncio.run(
        verify_session(client, "http://127.0.0.1:8001", "server-token")
    )
    assert identity["user_id"] == "u9"
    assert meta["verified"] is True
    assert meta["status_code"] == 200
    assert client.calls[0]["url"].endswith("/api/auth/me")
    assert client.calls[0]["headers"] == {
        "Authorization": "Bearer server-token"
    }
    assert "server-token" not in json.dumps([identity, meta])


def test_verify_session_fails_closed_without_server_identity():
    responses = (
        _FakeResponse(401, {"detail": "invalid"}, text="invalid"),
        _FakeResponse(200, {"data": {}}),
        _FakeResponse(200, ValueError("not json")),
    )
    for response in responses:
        identity, meta = asyncio.run(
            verify_session(_FakeClient(response), "http://127.0.0.1:8001",
                           "server-token")
        )
        assert identity == {}
        assert meta["verified"] is False
        assert meta["error"]
        assert "server-token" not in json.dumps(meta)


def test_resolve_session_reads_token_file_without_minting(tmp_path, monkeypatch):
    path = _token_file(tmp_path, "issued-token")

    def _must_not_mint():
        raise AssertionError("scratch mint must not run in token-file mode")

    monkeypatch.setattr(replay, "mint_token", _must_not_mint)
    client = _FakeClient(_FakeResponse(200, {"id": "u-file", "role": "admin"}))

    token, identity, meta = asyncio.run(
        resolve_session(client, "http://127.0.0.1:8001", str(path))
    )

    assert token == "issued-token"
    assert identity["user_id"] == "u-file"
    assert meta == {
        "mode": "token-file",
        "verified": True,
        "status_code": 200,
        "error": "",
    }
    assert "issued-token" not in json.dumps([identity, meta])


def test_resolve_session_preserves_the_scratch_mint_path(monkeypatch):
    monkeypatch.setattr(replay, "mint_token", lambda: ("minted-token", "u1"))
    client = _FakeClient(_FakeResponse(200, {"id": "u1"}))

    token, identity, meta = asyncio.run(
        resolve_session(client, "http://127.0.0.1:8001", None)
    )

    assert token == "minted-token"
    assert identity["user_id"] == "u1"
    assert meta["mode"] == "scratch-mint"
    assert meta["verified"] is True


def test_main_rejects_unverified_token_without_printing_it(
    tmp_path, monkeypatch, capsys
):
    path = _token_file(tmp_path, "super-secret-token")
    response = _FakeResponse(401, {"detail": "invalid"}, text="invalid")
    monkeypatch.setattr(
        replay.httpx, "AsyncClient", lambda *args, **kwargs: _FakeAsyncClient(
            response
        )
    )
    args = types.SimpleNamespace(
        base="http://127.0.0.1:8001",
        token_file=str(path),
    )

    exit_code = asyncio.run(replay.main_async(args))

    output = capsys.readouterr()
    assert exit_code == 2
    assert "FATAL" in output.err
    assert "super-secret-token" not in output.out
    assert "super-secret-token" not in output.err


def test_auth_report_contains_no_token_or_email():
    report = auth_report(
        {"mode": "token-file", "verified": True, "status_code": 200},
        {"user_id": "u1", "role": "admin", "email": "person@example.com"},
    )
    assert report == {
        "mode": "token-file",
        "identity_verified": True,
        "identity_status_code": 200,
        "user_id": "u1",
    }
