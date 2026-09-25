from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat_tool_planner import _user_facing_workbook_answer
from scripts.workbook_read_replay import (
    FILE_NAME,
    TARGETS,
    evaluate,
    evaluate_retry,
    flatten_trace,
    parse_outcomes,
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
