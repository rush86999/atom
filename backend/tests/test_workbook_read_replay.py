from __future__ import annotations

import asyncio
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
    parse_outcomes,
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
