# -*- coding: utf-8 -*-
"""SCRATCH tests for the opt-in strict direct WorkDrive proof (issue 620).

No network calls, credentials, or live services. The strict path is exercised
through the REAL ``UniversalIntegrationService._read_storage_file`` and
``inspect_workbook_bytes``; only the provider download and storage plans are
faked. The regression fixture deliberately gives the materialized copy one
value and the downloaded workbook a different value, so the answer proves
which source it used.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.answer_presentation import present_from_record
from core.workdrive_direct_proof import (
    ANSWER_SOURCE,
    DIRECT_KIND,
    DOWNLOADED_KIND,
    SCHEMA,
    WorkDriveProofError,
    proof_from_storage_read_result,
    read_workdrive_workbook_direct,
    strict_workdrive_proof_checks,
)
from scripts.workbook_read_replay import FILE_NAME, evaluate

RID = "u8ai1e3a4ceb"
ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, SLE16-8 "
    "and U-38"
)
TARGETS = [
    "381", "U-22", "622", "SLE24-16", "GSL48-16", "GSL24-16", "SLE16-8",
    "U-38",
]
CACHED_U22 = 1777.0
DOWNLOADED_U22 = 9999


def _downloaded_workbook_bytes() -> bytes:
    """A real xlsx whose U-22 price deliberately differs from the cache."""
    workbook = openpyxl.Workbook()
    linmac = workbook.active
    linmac.title = "LINMAC"
    linmac.append(["Model", "Description", "List Price", "Dealer"])
    linmac.append(["U-22", "Rotary machine", DOWNLOADED_U22, 9998])
    linmac.append(["622", "Press brake", 5000, 4999])
    tennsmith = workbook.create_sheet("Tennsmith")
    tennsmith.append([
        "MODEL", "Catalog No", "DESCRIPTION", "Type", "PRICE",
        "U.S. LIST", "U.S. COST",
    ])
    tennsmith.append([
        "SLE24-16", "SL-101", "Slitter", "Single wheel", 8880, 4500, 3600,
    ])
    tennsmith.append([
        "GSL48-16", "GS-106", "Slitter", "Gang", 14166, 9000, 7000,
    ])
    tennsmith.append([
        "GSL24-16", "GS-124", "Slitter", "Gang", 12000, 8000, 6000,
    ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


DOWNLOADED = _downloaded_workbook_bytes()
DOWNLOADED_SHA256 = hashlib.sha256(DOWNLOADED).hexdigest()


def _entry(path: str, sheet: str, content_hash: str, file_name: str = FILE_NAME):
    return {
        "source": "zoho_workdrive",
        "external_id": RID,
        "file_name": file_name,
        "entity_name": sheet,
        "parquet_path": path,
        "row_count": 1,
        "coverage": {"known": True, "truncated": False},
        "content_hash": content_hash,
        "ingested_at": "2026-09-07T23:06:19",
    }


@pytest.fixture()
def cached_workbook(tmp_path):
    """Materialized copy with the OLD (cached) U-22 price."""
    linmac = tmp_path / "linmac.parquet"
    pd.DataFrame([
        {"__sheet_row": 26, "Model": "U-22", "Description": "Rotary machine",
         "List Price": CACHED_U22, "Dealer": 1776.96},
    ]).to_parquet(linmac)
    tennsmith = tmp_path / "tennsmith.parquet"
    pd.DataFrame([
        {"__sheet_row": 101, "MODEL": "SLE24-16", "Catalog No": "SL-101",
         "DESCRIPTION": "Slitter", "Type": "Single wheel", "PRICE": 8880,
         "U.S. LIST": 4500.0, "U.S. COST": 3600.0},
        {"__sheet_row": 106, "MODEL": "GSL48-16", "Catalog No": "GS-106",
         "DESCRIPTION": "Slitter", "Type": "Gang", "PRICE": 14166},
    ]).to_parquet(tennsmith)
    return [
        _entry(str(linmac), "LINMAC", "cached-revision-sha1"),
        _entry(str(tennsmith), "Tennsmith", "cached-revision-sha1"),
    ]


class _FakeWorkDriveStorage:
    """Only the storage methods _read_storage_file actually calls."""

    access_token = None

    def __init__(self, content: bytes):
        self.content = content
        self.downloads = 0
        self.downloaded_ids: list[str] = []

    async def get_file_metadata(self, user_id, file_id):
        return {
            "id": file_id,
            "name": FILE_NAME,
            "version": "v42",
            "modified_time": "2026-11-12T00:00:00Z",
            "team_id": "team-1",
            "folder_id": "folder-1",
            "size": len(self.content),
        }

    async def download_file(self, user_id, file_id, workspace_id=None):
        self.downloads += 1
        self.downloaded_ids.append(str(file_id))
        return self.content


def _read_workdrive(workbook, storage, *, execution_id="exec-strict"):
    import core.workdrive_direct_proof as proof_module

    async def _run():
        with patch.object(
            proof_module,
            "read_workdrive_workbook_direct",
            wraps=proof_module.read_workdrive_workbook_direct,
        ):
            return await proof_module.read_workdrive_workbook_direct(
                user_id="u1",
                workspace_id="ws1",
                resource_id=RID,
                file_name=FILE_NAME,
                query=ASK,
                context={"requested_targets": TARGETS},
                execution_id=execution_id,
                storage_service=storage,
            )

    return asyncio.run(_run())


def _run_confirmed_read(workbook, *, strict: bool, storage):
    import integrations.chat_orchestrator as chat
    from core.pending_file_task import build_pending_task

    catalog = list(workbook)
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.ai_engines = {}
    orch.llm_service = None
    task = build_pending_task(ASK, FILE_NAME.lower())
    task["requested_targets"] = list(TARGETS)
    intent = {"reader": "datasets", "state": "resolved",
              "sources": [{"reader": "datasets",
                           "mention": FILE_NAME.lower()}]}

    def entries_for(source, external_id):
        return [e for e in catalog
                if e["source"] == source and e["external_id"] == external_id]

    async def fake_parse(content, ext, name, max_chars=None):
        return "LINMAC sheet text\nTennsmith sheet text"

    async def fake_ingest(self, content, **kwargs):
        return {"status": "skipped"}

    async def fake_datasets_for_file(source, external_id):
        return []

    async def fake_service_instance(self, connector_id, tenant_id="default"):
        assert connector_id == "zoho_workdrive"
        return storage

    if strict:
        os.environ["ATOM_620_STRICT_WORKDRIVE_PROOF"] = "1"
    else:
        os.environ.pop("ATOM_620_STRICT_WORKDRIVE_PROOF", None)
    try:
        with patch(
            "core.named_file_resolution.resolve_named_file_intent",
            new=MagicMock(return_value=intent),
        ), patch(
            "core.sheet_dataset_service.sheet_datasets_enabled",
            return_value=True,
        ), patch(
            "core.sheet_dataset_service.find_entries_sync",
            return_value=list(catalog),
        ), patch(
            "core.sheet_dataset_service.entries_for_file_sync",
            side_effect=entries_for,
        ), patch(
            "core.integrations.token_store.connected_source_grant_state",
            return_value="active",
        ), patch(
            "core.integration_registry.IntegrationRegistry.get_service_instance",
            new=fake_service_instance,
        ), patch(
            "core.auto_document_ingestion.parse_document_cached",
            new=fake_parse,
        ), patch(
            "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
            new=fake_ingest,
        ), patch(
            "core.sheet_dataset_service.ensure_sheet_dataset_background",
            new=MagicMock(),
        ), patch(
            "core.sheet_dataset_service.datasets_for_file",
            new=fake_datasets_for_file,
        ):
            return asyncio.run(orch._direct_confirmed_file_read(
                task, [], "u1", "s1", "ws1", execution_id="exec-strict"))
    finally:
        os.environ.pop("ATOM_620_STRICT_WORKDRIVE_PROOF", None)


def test_strict_read_derives_answer_and_proof_from_downloaded_bytes(
    cached_workbook,
):
    storage = _FakeWorkDriveStorage(DOWNLOADED)
    result = _run_confirmed_read(cached_workbook, strict=True, storage=storage)

    assert storage.downloads == 1
    assert storage.downloaded_ids == [RID]
    assert result["ok"] is True
    proof = result["direct_source_proof"]
    assert proof["status"] == "verified"
    assert proof["schema"] == SCHEMA
    assert proof["evidence_kind"] == DIRECT_KIND
    assert proof["answer_source"] == ANSWER_SOURCE
    assert proof["resource_id"] == RID
    assert proof["execution_id"] == "exec-strict"
    assert proof["downloaded_sha256"] == DOWNLOADED_SHA256
    assert proof["downloaded_bytes"] == len(DOWNLOADED)
    assert proof["receipt"]["schema"] == "workdrive-direct-receipt-1"
    assert proof["receipt"]["sha256"] == DOWNLOADED_SHA256
    assert proof["receipt"]["execution_id"] == "exec-strict"

    assert result["identity"]["content_hash"] == DOWNLOADED_SHA256
    assert result["identity"]["content_sha256"] == DOWNLOADED_SHA256
    assert result["identity"]["evidence_kind"] == DOWNLOADED_KIND
    assert result["identity"]["direct_source_proof"] == proof
    structured = result["structured_result"]
    assert structured["source_identity"]["content_hash"] == DOWNLOADED_SHA256
    assert structured["source_identity"]["evidence_kind"] == DOWNLOADED_KIND
    assert structured["source_identity"]["download_sha256"] == DOWNLOADED_SHA256

    checks = strict_workdrive_proof_checks(
        proof=proof,
        identity=result["identity"],
        structured_result=structured,
        execution_id="exec-strict",
        expected_resource_id=RID,
        expected_sha256=DOWNLOADED_SHA256,
    )
    assert all(checks.values()), checks

    # THE REGRESSION: cached copy says 1,777; downloaded workbook says 9,999.
    answer = present_from_record(structured)["answer"]
    assert "9,999" in answer
    assert "1,777" not in answer
    assert "U-22" in answer
    assert "SLE24-16" in answer and "8,880" in answer
    assert "GSL48-16" in answer and "14,166" in answer


def test_saved_answer_footer_names_the_downloaded_workbook_and_closes(
    cached_workbook,
):
    """The durable saved answer is the sanitized block.

    Its footer must name the workbook and its provenance wording must join
    to the verified direct proof: the harness's attribution check accepts
    ``From the downloaded copy of <workbook>`` while the strict proof gate
    still requires THIS execution/resource/SHA. Synthetic fixtures only.
    """
    from core.chat_tool_planner import _user_facing_workbook_answer

    storage = _FakeWorkDriveStorage(DOWNLOADED)
    result = _run_confirmed_read(cached_workbook, strict=True, storage=storage)
    assert result["ok"] is True

    # This is exactly what durable delivery stores/pins (the internal block
    # passed through the existing user-facing sanitizer).
    reply = _user_facing_workbook_answer(result["block"])
    assert "LIVE TOOL RESULTS" not in reply
    assert "GROUNDING RULE" not in reply
    assert f"From the downloaded copy of {FILE_NAME}" in reply
    assert "searched all 2 sheets of this copy" in reply
    assert "Source: DOWNLOADED COPY — resource=" + RID in reply

    proof = result["direct_source_proof"]
    structured = result["structured_result"]
    result_row = {
        "status": "retrieved",
        "identity": result["identity"],
        "structured_result": structured,
        "direct_source_proof": proof,
        "execution_id": "exec-strict",
        "retrieved_at": 123.0,
        "attempt_id": structured.get("attempt_id"),
        "evidence_revision": structured.get("evidence_revision"),
    }
    delivered_row = dict(result_row)
    delivered_row["status"] = "delivered"
    delivered_row["delivery_pin"] = {"delivered_text": reply[:24000]}
    state_after_2 = {
        "status": "pending", "result_status": "retrieved",
        "result": result_row, "read_error": "",
    }
    state_after_3 = {
        "status": "delivered", "result_status": "delivered",
        "result": delivered_row, "read_error": "",
    }
    serving = {
        "instance_id": "i1", "source_id": "s1", "revision": "r1",
        "started_at": "t1", "pid": 1,
    }
    report = evaluate(
        serving,
        serving,
        {"success": True},
        {"success": True, "message": "Reading it now."},
        [{"step_type": "observation",
          "observation": f"{FILE_NAME} 381 datasets"}],
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
        strict_workdrive_proof=True,
        expected_resource_id=RID,
        expected_sha256=DOWNLOADED_SHA256,
        r3={
            "success": True,
            "model": "deterministic",
            "message": reply,
            "data": {"deterministic_delivery": True},
        },
        state_after_3=state_after_3,
    )
    assert report["all_pass"], {
        key: value for key, value in report["checks"].items() if not value
    }
    assert report["checks"]["provenance_present"] is True
    assert report["checks"]["no_protocol_leakage"] is True
    assert report["checks"]["strict_workdrive_all_pass"] is True
    assert report["checks"]["strict_answer_not_materialized"] is True


def test_default_behavior_still_uses_cached_copy_and_never_downloads(
    cached_workbook,
):
    storage = _FakeWorkDriveStorage(DOWNLOADED)
    result = _run_confirmed_read(cached_workbook, strict=False, storage=storage)

    assert storage.downloads == 0
    assert result["ok"] is True
    assert result.get("direct_source_proof") is None
    answer = present_from_record(result["structured_result"])["answer"]
    assert "1,777" in answer
    assert "9,999" not in answer


def test_proof_rejects_materialized_fallback_missing_receipt_and_tampering():
    storage = _FakeWorkDriveStorage(DOWNLOADED)
    direct = _read_workdrive(None, storage)
    assert direct["status"] == "success"
    assert direct["proof"]["status"] == "verified"
    data = direct["data"]

    with pytest.raises(WorkDriveProofError):
        proof_from_storage_read_result(
            {**data, "evidence_kind": "materialized_copy"},
            execution_id="exec-strict",
        )
    without_receipt = dict(data)
    without_receipt.pop("strict_read_receipt", None)
    with pytest.raises(WorkDriveProofError):
        proof_from_storage_read_result(
            without_receipt, execution_id="exec-strict")
    tampered = {**data, "strict_read_receipt": dict(data["strict_read_receipt"])}
    tampered["strict_read_receipt"]["sha256"] = "0" * 64
    with pytest.raises(WorkDriveProofError):
        proof_from_storage_read_result(
            tampered, execution_id="exec-strict")
    with pytest.raises(WorkDriveProofError):
        proof_from_storage_read_result(
            data, execution_id="different-execution")

    checks = strict_workdrive_proof_checks(
        proof=None,
        identity={"resource_id": RID, "content_hash": "cached-revision-sha1",
                  "evidence_kind": "materialized_copy"},
        structured_result={"source_identity": {
            "resource_id": RID, "content_hash": "cached-revision-sha1",
            "evidence_kind": "materialized_copy"}},
        execution_id="exec-strict",
    )
    assert checks["strict_workdrive_proof_present"] is False
    assert checks["strict_workdrive_no_materialized_fallback"] is False
    assert checks["strict_workdrive_all_pass"] is False


def test_strict_read_fails_closed_when_download_is_unavailable():
    class _NoDownload(_FakeWorkDriveStorage):
        async def download_file(self, user_id, file_id, workspace_id=None):
            self.downloads += 1
            return None

    storage = _NoDownload(b"")
    direct = _read_workdrive(None, storage)
    assert storage.downloads == 1
    assert direct["status"] == "success"
    assert direct["proof"] is None
    assert direct["error"]
    checks = strict_workdrive_proof_checks(
        proof=direct["proof"],
        identity={},
        structured_result=None,
        execution_id="exec-strict",
    )
    assert checks["strict_workdrive_all_pass"] is False


def _reply() -> str:
    return "\n".join([
        f"Workbook read: {FILE_NAME}",
        "Source: DOWNLOADED COPY — resource=" + RID
        + ", content_hash=" + DOWNLOADED_SHA256
        + ", ingested=2026-11-12",
        "Coverage — indexed sheets=2; indexed content searched",
        "Per-item results:",
        "| item | outcome | evidence |",
        "|---|---|---|",
        "| 381 | NOT FOUND IN INDEXED CONTENT | all 2 sheets probed |",
        "| U-22 | FOUND | LINMAC!C2 (prices: 9999) |",
        "| 622 | FOUND | LINMAC!C3 (prices: 5000) |",
        "| SLE24-16 | FOUND | Tennsmith!E2 (prices: 8880) |",
        "| GSL48-16 | FOUND | Tennsmith!E3 (prices: 14166) |",
        "| GSL24-16 | FOUND | Tennsmith!E4 (prices: 12000) |",
        "| SLE16-8 | NOT FOUND IN INDEXED CONTENT | all 2 sheets probed |",
        "| U-38 | NOT FOUND IN INDEXED CONTENT | all 2 sheets probed |",
    ])


def test_replay_strict_mode_requires_and_accepts_direct_proof(cached_workbook):
    storage = _FakeWorkDriveStorage(DOWNLOADED)
    result = _run_confirmed_read(cached_workbook, strict=True, storage=storage)
    proof = result["direct_source_proof"]
    structured = result["structured_result"]
    result_row = {
        "status": "retrieved",
        "identity": result["identity"],
        "structured_result": structured,
        "direct_source_proof": proof,
        "execution_id": "exec-strict",
    }
    state_after_2 = {
        "status": "served", "result_status": "retrieved",
        "result": result_row, "read_error": "",
    }
    serving = {
        "instance_id": "i1", "source_id": "s1", "revision": "r1",
        "started_at": "t1", "pid": 1,
    }
    args = (
        serving, serving,
        {"success": True}, {"success": True, "message": _reply(),
                            "model": "deterministic",
                            "data": {"deterministic_delivery": True}},
        [{"step_type": "observation",
          "observation": f"{FILE_NAME} 381 datasets"}],
        {"status_code": 200, "error": ""},
        {"status": "pending", "read_error": ""},
        state_after_2,
    )
    report = evaluate(
        *args, strict_workdrive_proof=True,
        expected_resource_id=RID, expected_sha256=DOWNLOADED_SHA256,
    )
    assert report["all_pass"], {
        k: v for k, v in report["checks"].items() if not v
    }
    assert report["checks"]["strict_workdrive_proof_present"] is True
    assert report["checks"]["strict_workdrive_no_materialized_fallback"] is True
    assert report["checks"]["strict_workdrive_all_pass"] is True

    without_identity = {
        k: v for k, v in result_row["identity"].items()
        if k not in ("direct_source_proof", "content_sha256", "evidence_kind")
    }
    without_structured = {
        "source_identity": {
            k: v for k, v in structured["source_identity"].items()
            if k not in (
                "direct_source_proof", "download_sha256", "download_sha1",
                "download_resource_id", "download_execution_id",
                "proof_evidence_kind", "content_sha256",
            )
        }
    }
    without = evaluate(
        *args[:7],
        {"status": "served", "result_status": "retrieved",
         "result": {
             **result_row,
             "identity": without_identity,
             "structured_result": without_structured,
             "direct_source_proof": None,
         },
         "read_error": ""},
        strict_workdrive_proof=True,
        expected_resource_id=RID,
        expected_sha256=DOWNLOADED_SHA256,
    )
    assert without["all_pass"] is False
    assert without["checks"]["strict_workdrive_proof_present"] is False
    assert without["checks"]["strict_workdrive_no_materialized_fallback"] is False
