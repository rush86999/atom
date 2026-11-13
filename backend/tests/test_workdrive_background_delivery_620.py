# -*- coding: utf-8 -*-
"""Focused tests for issue-620 durable background WorkDrive delivery.

The interactive strict read keeps its deadline.  When that deadline is
reached, the same authorized read continues as a durable AgentExecution job
with its OWN execution id, downloads the workbook, emits its own receipt, and
writes the result onto the existing persisted-file-delivery carrier
(``ChatMessage.metadata_json["pending_file_result"]``).  A retry/reload then
delivers from persistence without another download.

Everything here is synthetic: no credentials, network, live workbook, or
production database.  ``TESTING=1`` is set before application imports.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core import workdrive_background_delivery as background
from core.pending_file_task import (
    FILE_TASK_SESSION_KEY,
    build_pending_task,
)
from core.workdrive_direct_proof import (
    DOWNLOADED_KIND,
    proof_from_storage_read_result,
)

RID = "u-background-620"
FILE_NAME = "Synthetic Price List 2026.xlsx"
ORIGIN_EXECUTION = "exec-interactive-620"
ASK = (
    "find the prices of U-22 and 622 in Synthetic Price List 2026.xlsx"
)
TARGETS = ["U-22", "622"]


def _workbook_bytes(price: float = 4321.0) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "LINMAC"
    sheet.append(["Model", "Description", "List Price"])
    sheet.append(["U-22", "Rotary machine", price])
    sheet.append(["622", "Press brake", 5000])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class _FakeWorkDrive:
    access_token = None

    def __init__(self, content: bytes):
        self.content = content
        self.downloads = 0
        self.downloaded_ids: list[str] = []

    async def get_file_metadata(self, user_id, file_id):
        return {
            "id": file_id,
            "name": FILE_NAME,
            "version": "v620-bg",
            "modified_time": "2026-11-12T00:00:00Z",
            "team_id": "team-620",
            "folder_id": "folder-620",
            "size": len(self.content),
        }

    async def download_file(self, user_id, file_id, workspace_id=None):
        self.downloads += 1
        self.downloaded_ids.append(str(file_id))
        return self.content


@pytest.fixture()
def durable_db(monkeypatch):
    """In-memory schema for the durable AgentExecution/ChatMessage carriers."""
    from core import database as database_module
    from core.models_registration import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        db = session_factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)
    yield
    engine.dispose()


@pytest.fixture()
def active_grant():
    with patch(
        "core.integrations.token_store.connected_source_grant_state",
        return_value="active",
    ):
        yield


@pytest.fixture()
def fake_storage():
    content = _workbook_bytes()
    storage = _FakeWorkDrive(content)

    async def fake_service_instance(self, connector_id, tenant_id="default"):
        assert connector_id == "zoho_workdrive"
        return storage

    async def fake_datasets_for_file(source, external_id):
        return []

    with patch(
        "core.integration_registry.IntegrationRegistry.get_service_instance",
        new=fake_service_instance,
    ), patch(
        "core.sheet_dataset_service.ensure_sheet_dataset_background",
        new=MagicMock(),
    ), patch(
        "core.sheet_dataset_service.datasets_for_file",
        new=fake_datasets_for_file,
    ):
        yield storage, hashlib.sha256(content).hexdigest()


def _identity() -> dict:
    return {
        "service": "zoho_workdrive",
        "file_id": RID,
        "resource_id": RID,
        "file_name": FILE_NAME,
        "identity_verified": True,
    }


def _schedule(**overrides):
    kwargs = {
        "session_id": "session-bg-620",
        "user_id": "u1",
        "workspace_id": "ws-620",
        "execution_id": ORIGIN_EXECUTION,
        "original_message": ASK,
        "query": ASK,
        "mention": FILE_NAME.lower(),
        "resource_id": RID,
        "file_name": FILE_NAME,
        "requested_targets": TARGETS,
        "identity": _identity(),
        "pending_task": build_pending_task(ASK, FILE_NAME.lower()),
        "history": [],
        "canvas": None,
        "tenant_id": "default",
        "spawn": False,
    }
    kwargs.update(overrides)
    return background.schedule_strict_workdrive_read(**kwargs)


def _job_row(job_id: str):
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        return db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()


def _job_metadata(job_id: str) -> dict:
    row = _job_row(job_id)
    return dict(row.metadata_json or {})[background.JOB_METADATA_KEY]


def _write_job_metadata(job_id: str, job: dict) -> None:
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        meta = dict(row.metadata_json or {})
        meta[background.JOB_METADATA_KEY] = job
        row.metadata_json = meta
        db.commit()


def _assistant_rows(session_id: str = "session-bg-620"):
    from core.database import get_db_session
    from core.models import ChatMessage

    with get_db_session() as db:
        return db.query(ChatMessage).filter(
            ChatMessage.conversation_id == session_id,
            ChatMessage.role == "assistant",
        ).all()


def test_schedule_creates_durable_job_with_its_own_execution_id(
    durable_db, active_grant,
):
    scheduled = _schedule()

    assert scheduled["ok"] is True
    job_id = scheduled["job_id"]
    assert job_id != ORIGIN_EXECUTION
    assert scheduled["execution_id"] == job_id
    assert scheduled["origin_execution_id"] == ORIGIN_EXECUTION
    assert len(scheduled["original_digest"]) == 64

    row = _job_row(job_id)
    assert row is not None
    assert row.triggered_by == background.TRIGGERED_BY
    assert row.status == "running"
    job = _job_metadata(job_id)
    assert job["job_id"] == job_id
    assert job["execution_id"] == job_id
    assert job["origin_execution_id"] == ORIGIN_EXECUTION
    assert job["status"] == "scheduled"
    assert job["resource_id"] == RID
    assert job["authorization"]["state"] == "active"
    # The digest is derived from the accepted scope, not stored blindly.
    assert job["original_digest"] == background.canonical_request_digest(
        job["request_scope"])


def test_execute_downloads_once_and_emits_receipt_from_its_own_execution(
    durable_db, active_grant, fake_storage,
):
    storage, expected_sha = fake_storage
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    result = asyncio.run(background.execute_background_read(job_id))

    assert result["ok"] is True
    assert result["delivered"] is True
    assert storage.downloads == 1
    assert storage.downloaded_ids == [RID]

    row = result["result"]
    proof = row["direct_source_proof"]
    assert proof["status"] == "verified"
    assert proof["execution_id"] == job_id
    assert proof["execution_id"] != ORIGIN_EXECUTION
    assert proof["downloaded_sha256"] == expected_sha
    assert proof["resource_id"] == RID
    assert proof["receipt"]["execution_id"] == job_id
    assert proof["receipt"]["sha256"] == expected_sha
    assert row["identity"]["evidence_kind"] == DOWNLOADED_KIND
    assert row["identity"]["content_sha256"] == expected_sha
    assert row["original_digest"] == scheduled["original_digest"]
    marker = row[background.BACKGROUND_DELIVERY_KEY]
    assert marker["job_id"] == job_id
    assert marker["origin_execution_id"] == ORIGIN_EXECUTION
    assert marker["original_digest"] == scheduled["original_digest"]
    assert marker["content_sha256"] == expected_sha

    # The durable carrier is the existing assistant-row metadata field.
    rows = _assistant_rows()
    assert len(rows) == 1
    meta = json.loads(rows[0].metadata_json)
    persisted = meta["pending_file_result"]
    assert persisted["background_delivery"]["job_id"] == job_id
    assert meta["pending_file_task"]["status"] == "retrieved"
    assert meta["resolved_file_identity"]["content_sha256"] == expected_sha

    # Retry/reload uses the persisted carrier: no second download.
    import integrations.chat_orchestrator as chat

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    loaded = orch._load_pending_file_result("session-bg-620")
    assert loaded is not None
    assert loaded["background_delivery"]["job_id"] == job_id
    assert storage.downloads == 1
    assert background.persisted_delivery_is_valid(loaded, user_id="u1")
    with patch(
        "core.integrations.token_store.connected_source_grant_state",
        return_value="revoked",
    ):
        assert not background.persisted_delivery_is_valid(
            loaded, user_id="u1")

    # The strict verifier accepts the persisted proof/subject binding.
    verified = proof_from_storage_read_result(
        {
            "served": True,
            "read_completed": True,
            "resource_id": RID,
            "content_sha256": expected_sha,
            "strict_read_receipt": proof["receipt"],
            "workbook_read": row["workbook_read"],
        },
        execution_id=job_id,
        expected_resource_id=RID,
    )
    assert verified["status"] == "verified"

    # A second execution is idempotent and still performs no download.
    again = asyncio.run(background.execute_background_read(job_id))
    assert again["ok"] is True
    assert storage.downloads == 1


def _legacy_raw_block(sha: str) -> str:
    """The pre-fix durable text: internal envelope + grounding contract."""
    return "\n".join([
        "LIVE TOOL RESULTS (zoho_workdrive.read_storage_file, file='"
        f"{FILE_NAME}') — the answer below was derived from the DOWNLOADED "
        "WorkDrive bytes in this execution:",
        "Source: DOWNLOADED COPY — resource=" + RID
        + f", sha256={sha}, bytes=4920, execution=legacy-job",
        "Coverage — sheets searched=1; coverage_complete=True",
        "",
        f"From the downloaded copy of {FILE_NAME}:",
        "",
        "- **U-22** — 4,321 'List Price' (LINMAC sheet, row 2, "
        "cell C2, matched at A2)",
        "- **622** — 5,000 'List Price' (LINMAC sheet, row 3, "
        "cell C3, matched at A3)",
        "",
        f"From the downloaded copy of {FILE_NAME} — searched all 1 "
        "sheets of this copy. A newer version of the file may differ; "
        "no-match lines are about this copy, not the live file.",
        "",
        "GROUNDING RULE: specific facts must come from the evidence above.",
    ])


def test_durable_delivery_sanitizes_before_pinning(
    durable_db, active_grant, fake_storage,
):
    storage, expected_sha = fake_storage
    scheduled = _schedule()
    result = asyncio.run(
        background.execute_background_read(scheduled["job_id"]))
    assert result["ok"] is True

    row = result["result"]
    rendered = row["rendered"]
    # The internal evidence carrier never becomes the persisted answer...
    assert "LIVE TOOL RESULTS" not in rendered
    assert "GROUNDING RULE" not in rendered
    # ...while the user-facing source footer names the workbook and keeps
    # the verified downloaded provenance.
    assert f"From the downloaded copy of {FILE_NAME}" in rendered
    assert "Source: DOWNLOADED COPY — resource=" + RID in rendered
    assert f"sha256={expected_sha}" in rendered
    # The pin records exactly what the user received.
    assert row["delivery_pin"]["delivered_text"] == rendered
    assert row["identity"]["content_sha256"] == expected_sha
    assert row["direct_source_proof"]["downloaded_sha256"] == expected_sha

    # The durable carrier is sanitized too (a retry reads this, not the
    # in-process result).
    loaded = json.loads(_assistant_rows()[0].metadata_json)[
        "pending_file_result"]
    assert "LIVE TOOL RESULTS" not in loaded["rendered"]
    assert loaded["delivery_pin"]["delivered_text"] == rendered


def test_retry_boundary_sanitizes_a_legacy_raw_row():
    import integrations.chat_orchestrator as chat

    raw = _legacy_raw_block("a" * 64)
    legacy = {
        "status": "delivered",
        "rendered": raw,
        "identity": {
            "resource_id": RID,
            "file_name": FILE_NAME,
            "content_sha256": "a" * 64,
            "evidence_kind": DOWNLOADED_KIND,
        },
        "direct_source_proof": {
            "status": "verified",
            "execution_id": "legacy-job",
            "downloaded_sha256": "a" * 64,
        },
        "background_delivery": {
            "job_id": "legacy-job",
            "content_sha256": "a" * 64,
        },
    }

    response = chat.ChatOrchestrator._persisted_background_delivery_response(
        legacy)

    assert "LIVE TOOL RESULTS" not in response["block"]
    assert "GROUNDING RULE" not in response["rendered_answer"]
    assert f"From the downloaded copy of {FILE_NAME}" in response["block"]
    assert "Source: DOWNLOADED COPY — resource=" + RID in response["block"]
    # Sanitizing presentation does not touch the evidence binding.
    assert response["identity"]["content_sha256"] == "a" * 64
    assert response["meta"]["direct_source_proof"][
        "downloaded_sha256"] == "a" * 64


def test_revoked_authorization_blocks_download(
    durable_db, active_grant, fake_storage,
):
    storage, _sha = fake_storage
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    with patch(
        "core.integrations.token_store.connected_source_grant_state",
        return_value="revoked",
    ):
        result = asyncio.run(background.execute_background_read(job_id))

    assert result["ok"] is False
    assert result["reason"] == "authorization_revoked"
    assert storage.downloads == 0
    job = _job_metadata(job_id)
    assert job["status"] == "failed"
    assert _job_row(job_id).status == "failed"


def test_schedule_refuses_revoked_authorization(durable_db, active_grant):
    with patch(
        "core.integrations.token_store.connected_source_grant_state",
        return_value="revoked",
    ):
        scheduled = _schedule()
    assert scheduled["ok"] is False
    assert scheduled["reason"] == "authorization_revoked"
    assert scheduled["job_id"] is None


def test_original_digest_tampering_fails_closed(
    durable_db, active_grant, fake_storage,
):
    storage, _sha = fake_storage
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    job = _job_metadata(job_id)
    job["original_digest"] = "0" * 64
    _write_job_metadata(job_id, job)

    result = asyncio.run(background.execute_background_read(job_id))

    assert result["ok"] is False
    assert result["reason"] == "original_digest_mismatch"
    assert storage.downloads == 0


def test_restart_recovery_redelivers_persisted_result_without_reread(
    durable_db, active_grant, fake_storage,
):
    storage, _sha = fake_storage
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    first = asyncio.run(background.execute_background_read(job_id))
    assert first["ok"] is True
    assert storage.downloads == 1

    # Simulate a crash after the result was durably committed but before the
    # assistant-row delivery could be seen: remove the delivery and leave the
    # job interrupted.  Recovery must not touch the provider again.
    from core.database import get_db_session
    from core.models import AgentExecution, ChatMessage, DeliveryEvent

    with get_db_session() as db:
        db.query(ChatMessage).filter(
            ChatMessage.conversation_id == "session-bg-620").delete()
        db.query(DeliveryEvent).filter(
            DeliveryEvent.job_id == job_id).delete()
        row = db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        row.status = "failed"
        db.commit()

    async def must_not_read(_job):
        raise AssertionError("recovery must not re-download")

    stats = asyncio.run(background.recover_pending_strict_workdrive_reads(
        read_runner=must_not_read))

    assert stats["reused_result"] == 1
    assert stats["delivered"] == 1
    assert storage.downloads == 1
    rows = _assistant_rows()
    assert len(rows) == 1
    meta = json.loads(rows[0].metadata_json)
    assert meta["pending_file_result"]["background_delivery"]["job_id"] == job_id
    assert _job_row(job_id).status == "completed"


def test_retry_serves_persisted_delivery_without_reading_again(
    durable_db, active_grant, fake_storage,
):
    import integrations.chat_orchestrator as chat

    storage, expected_sha = fake_storage
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    first = asyncio.run(background.execute_background_read(job_id))
    assert first["ok"] is True
    assert storage.downloads == 1

    task = build_pending_task(ASK, FILE_NAME.lower())
    task["status"] = "retrieved"
    task["operation"] = "re-deliver"
    task["resolved_file"] = _identity()
    task["requested_targets"] = list(TARGETS)
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.llm_service = None
    orch.tenant_id = "default"

    async def must_not_read(*args, **kwargs):
        raise AssertionError("retry must not execute a workbook read")

    os.environ["ATOM_620_STRICT_WORKDRIVE_PROOF"] = "1"
    try:
        with patch(
            "core.chat_tool_planner._datasets_named_file_block",
            new=must_not_read,
        ):
            result = asyncio.run(orch._direct_confirmed_file_read(
                task, [], "u1", "session-bg-620", "ws-620",
                execution_id="exec-retry-620"))
    finally:
        os.environ.pop("ATOM_620_STRICT_WORKDRIVE_PROOF", None)

    assert result["ok"] is True
    assert result["served_from_persisted_delivery"] is True
    assert result["read_executed"] is False
    assert result["background_delivery"]["job_id"] == job_id
    assert result["identity"]["content_sha256"] == expected_sha
    assert storage.downloads == 1


def test_restart_recovery_reruns_a_scheduled_job_once(
    durable_db, active_grant, fake_storage,
):
    storage, expected_sha = fake_storage
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    # The process died before the background attempt could start.  The boot
    # sweep reconciles the row to failed; recovery re-runs the durable job.
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        row.status = "failed"
        db.commit()

    stats = asyncio.run(background.recover_pending_strict_workdrive_reads())

    assert stats["rerun"] == 1
    assert stats["delivered"] == 1
    assert storage.downloads == 1
    assert _job_row(job_id).status == "completed"
    marker = json.loads(_assistant_rows()[0].metadata_json)[
        "pending_file_result"]["background_delivery"]
    assert marker["job_id"] == job_id
    assert marker["content_sha256"] == expected_sha


def test_interactive_deadline_schedules_instead_of_failing(
    durable_db, active_grant,
):
    import integrations.chat_orchestrator as chat

    pending = build_pending_task(ASK, FILE_NAME.lower())
    pending["resolved_file"] = _identity()
    pending["requested_targets"] = list(TARGETS)
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.llm_service = None
    orch.tenant_id = "default"

    async def slow_block(*args, **kwargs):
        await asyncio.sleep(5)
        return "must not finish interactively"

    intent = {
        "reader": "datasets",
        "state": "resolved",
        "sources": [{"reader": "datasets",
                     "mention": FILE_NAME.lower()}],
    }
    deadline = SimpleNamespace(remaining=lambda: 5.0)
    os.environ["ATOM_620_STRICT_WORKDRIVE_PROOF"] = "1"
    try:
        with patch(
            "core.named_file_resolution.resolve_named_file_intent",
            return_value=intent,
        ), patch(
            "core.chat_tool_planner._datasets_named_file_block",
            new=slow_block,
        ), patch.object(
            background, "spawn_background_read", return_value=False,
        ) as spawned:
            result = asyncio.run(orch._direct_confirmed_file_read(
                pending, [], "u1", "session-bg-620", "ws-620",
                deadline, execution_id=ORIGIN_EXECUTION))
    finally:
        os.environ.pop("ATOM_620_STRICT_WORKDRIVE_PROOF", None)

    assert result["ok"] is True
    assert result["background_pending"] is True
    assert result["retrieval_complete"] is False
    job_id = result["background_read"]["job_id"]
    assert job_id
    assert job_id != ORIGIN_EXECUTION
    assert spawned.called
    job = _job_metadata(job_id)
    assert job["origin_execution_id"] == ORIGIN_EXECUTION
    assert job["interactive_deadline_exceeded"] is True
    assert job["requested_targets"] == TARGETS
    assert _job_row(job_id).status == "running"


def test_persisted_validation_withholds_wrong_digest(durable_db, active_grant):
    import integrations.chat_orchestrator as chat

    # Shape a background row whose marker no longer matches its scope.
    scope = background.request_scope_from_task(
        session_id="session-bg-620",
        user_id="u1",
        workspace_id="ws-620",
        resource_id=RID,
        file_name=FILE_NAME,
        original_message=ASK,
        requested_targets=TARGETS,
    )
    digest = background.canonical_request_digest(scope)
    row = {
        "rendered": "answer",
        "background_delivery": {
            "schema": background.SCHEMA,
            "job_id": "job-x",
            "execution_id": "job-x",
            "original_digest": digest,
            "request_scope": {**scope, "original_message": "different ask"},
            "content_sha256": "a" * 64,
            "proof_execution_id": "job-x",
            "status": "delivered",
            "user_id": "u1",
        },
        "direct_source_proof": {
            "status": "verified",
            "execution_id": "job-x",
            "downloaded_sha256": "a" * 64,
            "receipt": {"sha256": "a" * 64, "execution_id": "job-x"},
            "materialized": False,
        },
    }
    assert background.persisted_delivery_is_valid(row, user_id="u1") is False

    # Also pin the loader gate: the malformed row is not served.
    from core.database import get_db_session
    from core.models import ChatMessage

    with get_db_session() as db:
        db.add(ChatMessage(
            conversation_id="session-bg-620",
            tenant_id="default",
            role="assistant",
            content="stale",
            metadata_json=json.dumps({"pending_file_result": row}),
        ))
        db.commit()

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    assert orch._load_pending_file_result("session-bg-620") is None
