# -*- coding: utf-8 -*-
"""Confirmation reuse for issue-620 durable WorkDrive reads.

A filename confirmation restates the objective's name; it does not authorize
new work.  While the request's background job is still unfinished, the
confirmation must continue THAT job — same job id, same ORIGINAL request
digest, no second live attempt, no second job — and it must do so after a
restart and on a later retry.  A genuinely distinct ask on the same workbook
still gets its own job and its own digest.

Everything here is synthetic: no credentials, network, live workbook, live
replay files, or production database.  ``TESTING=1`` is set before
application imports.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import contextmanager, ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core import workdrive_background_delivery as background
from core.pending_file_task import build_pending_task

RID = "u-confirmation-620"
OTHER_RID = "u-confirmation-other-620"
FILE_NAME = "Synthetic Confirmation Price List.xlsx"
ORIGIN_EXECUTION = "exec-interactive-confirmation-620"
SESSION = "session-confirmation-620"
WORKSPACE = "ws-620"
ASK = (
    "find the prices of U-22 and 622 in Synthetic Confirmation Price List.xlsx"
)
CONFIRMATION = "Synthetic Confirmation Price List.xlsx is correct"
TARGETS = ["U-22", "622"]
DISTINCT_ASK = "check the revision history of the same workbook"


@pytest.fixture()
def durable_db(monkeypatch):
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


def _identity(resource_id: str = RID) -> dict:
    return {
        "service": "zoho_workdrive",
        "file_id": resource_id,
        "resource_id": resource_id,
        "file_name": FILE_NAME,
        "identity_verified": True,
    }


def _schedule(**overrides):
    kwargs = {
        "session_id": SESSION,
        "user_id": "u1",
        "workspace_id": WORKSPACE,
        "execution_id": ORIGIN_EXECUTION,
        "original_message": ASK,
        "query": ASK,
        "mention": FILE_NAME.lower(),
        "resource_id": RID,
        "file_name": FILE_NAME,
        "requested_targets": TARGETS,
        "pending_task": build_pending_task(ASK, FILE_NAME.lower()),
        "identity": _identity(),
        "history": [],
        "canvas": None,
        "tenant_id": "default",
        "spawn": False,
    }
    kwargs.update(overrides)
    return background.schedule_strict_workdrive_read(**kwargs)


def _reuse(**overrides):
    kwargs = {
        "session_id": SESSION,
        "user_id": "u1",
        "workspace_id": WORKSPACE,
        "resource_id": RID,
        "file_name": FILE_NAME,
        "requested_targets": TARGETS,
        "requested_fields": [],
        "attach_job_id": None,
        "confirmation_message": CONFIRMATION,
        "confirmed_mention": FILE_NAME.lower(),
    }
    kwargs.update(overrides)
    return background.reuse_in_flight_workdrive_read(**kwargs)


def _job_rows():
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        return db.query(AgentExecution).filter(
            AgentExecution.triggered_by == background.TRIGGERED_BY).all()


def _job_metadata(job_id: str) -> dict:
    from core.database import get_db_session
    from core.models import AgentExecution

    with get_db_session() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == job_id).first()
        return dict(row.metadata_json or {})[background.JOB_METADATA_KEY]


def test_confirmation_attaches_by_job_id_without_a_second_job(
    durable_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    d1 = scheduled["original_digest"]

    # The confirmation's own words differ (they restate the filename), and it
    # arrives while job #1 is still running.
    reused = _reuse(attach_job_id=job_id)

    assert reused["ok"] is True
    assert reused["reused"] is True
    assert reused["attached"] is True
    assert reused["attach_mode"] == "job_id"
    assert reused["job_id"] == job_id
    # SAME accepted request: the original digest joins, no D2 is minted.
    assert reused["original_digest"] == d1
    assert len(_job_rows()) == 1

    job = _job_metadata(job_id)
    assert job["confirmed_mention"] == FILE_NAME.lower()
    assert job["confirmation_count"] == 1
    assert job["confirmations"][-1]["attach"] == "job_id"
    assert job["confirmations"][-1]["message"] == CONFIRMATION
    # Scope and resource identity are untouched by the confirmation.
    assert job["original_digest"] == d1
    assert job["resource_id"] == RID
    assert job["request_scope"]["original_message"] == ASK
    assert job["request_scope"]["resource_id"] == RID
    assert job["requested_targets"] == TARGETS


def test_confirmation_scan_attaches_after_a_restart(
    durable_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    d1 = scheduled["original_digest"]

    # A restart drops every in-process map; the durable row is the authority.
    background._background_tasks.clear()
    background._live_sessions.clear()

    reused = _reuse(attach_job_id=None)

    assert reused["ok"] is True
    assert reused["job_id"] == job_id
    assert reused["original_digest"] == d1
    assert reused["attach_mode"] == "identity_scan"
    assert len(_job_rows()) == 1
    assert _job_metadata(job_id)["confirmation_count"] == 1


def test_confirmation_attach_survives_the_scheduler_path(
    durable_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    d1 = scheduled["original_digest"]

    # The deadline-time scheduler is the race-safe second line: it must attach
    # too, with the confirmation's words but the job's ORIGINAL digest.
    reused = _schedule(
        original_message=CONFIRMATION,
        query=CONFIRMATION,
        confirmation_turn=True,
        attach_job_id=job_id,
        confirmation_message=CONFIRMATION,
    )

    assert reused["ok"] is True
    assert reused["reused"] is True
    assert reused["attached"] is True
    assert reused["job_id"] == job_id
    assert reused["original_digest"] == d1
    assert len(_job_rows()) == 1
    job = _job_metadata(job_id)
    assert job["request_scope"]["original_message"] == ASK
    assert job["resource_id"] == RID


def test_distinct_followup_still_gets_its_own_job(
    durable_db, active_grant,
):
    scheduled = _schedule()
    d1 = scheduled["original_digest"]

    # An ordinary (non-confirmation) follow-up on the same workbook is a
    # genuinely different ask: it must not be widened into job #1.
    distinct = _schedule(
        original_message=DISTINCT_ASK,
        query=DISTINCT_ASK,
        requested_targets=[],
    )

    assert distinct["ok"] is True
    assert distinct["reused"] is False
    assert distinct["job_id"] != scheduled["job_id"]
    assert distinct["original_digest"] != d1
    assert len(_job_rows()) == 2

    # The scanner agrees: the confirmation identity does not cover the
    # follow-up's different target set.
    refused = _reuse(requested_targets=["U-38"])
    assert refused["ok"] is False
    assert refused["reason"] == "no_in_flight_job"


def test_confirmation_pinning_a_different_resource_does_not_attach(
    durable_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]

    by_id = _reuse(attach_job_id=job_id, resource_id=OTHER_RID,
                   file_name="Other Workbook.xlsx")
    assert by_id["ok"] is False
    assert by_id["reason"] == "no_in_flight_job"
    # The identity fallback must refuse the redirect as well.
    by_scan = _reuse(attach_job_id=None, resource_id=OTHER_RID,
                     file_name="Other Workbook.xlsx")
    assert by_scan["ok"] is False
    assert by_scan["reason"] == "no_in_flight_job"

    job = _job_metadata(job_id)
    assert job.get("confirmation_count") in (None, 0)
    assert job["resource_id"] == RID
    assert len(_job_rows()) == 1


def test_confirmation_does_not_resurrect_a_terminal_job(
    durable_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    background._finish_job(
        job_id, background._JOB_STATUS_COMPLETED, summary="done")

    reused = _reuse(attach_job_id=job_id)
    assert reused["ok"] is False
    assert reused["reason"] == "no_in_flight_job"
    # A completed ask is served by the persisted-delivery path, never a
    # silently re-used terminal job record.
    assert len(_job_rows()) == 1


def _write_synthetic_delivery(job_id: str, digest: str) -> dict:
    """Write job #1's persisted result row (no provider call, no workbook)."""
    sha = "a" * 64
    job = _job_metadata(job_id)
    row = {
        "status": "delivered",
        "target_extraction_version": 3,
        "rendered": "synthetic background answer",
        "identity": {
            "service": background.PROVIDER,
            "resource_id": RID,
            "file_id": RID,
            "file_name": FILE_NAME,
            "content_sha256": sha,
        },
        "structured_result": {"source_identity": {"content_hash": sha}},
        "direct_source_proof": {
            "status": "verified",
            "execution_id": job_id,
            "downloaded_sha256": sha,
            "receipt": {"sha256": sha, "execution_id": job_id},
            "materialized": False,
        },
        background.BACKGROUND_DELIVERY_KEY: {
            "schema": background.SCHEMA,
            "job_id": job_id,
            "execution_id": job_id,
            "user_id": "u1",
            "workspace_id": WORKSPACE,
            "session_id": SESSION,
            "resource_id": RID,
            "original_digest": digest,
            "request_scope": dict(job["request_scope"]),
            "content_sha256": sha,
            "proof_execution_id": job_id,
            "status": "delivered",
        },
    }
    from core.database import get_db_session
    from core.models import ChatMessage

    with get_db_session() as db:
        db.add(ChatMessage(
            conversation_id=SESSION,
            tenant_id="default",
            role="assistant",
            content=row["rendered"],
            metadata_json=json.dumps({"pending_file_result": row}),
        ))
        db.commit()
    return row


def test_attached_confirmation_keeps_the_original_digest_for_retry(
    durable_db, active_grant,
):
    scheduled = _schedule()
    job_id = scheduled["job_id"]
    d1 = scheduled["original_digest"]
    reused = _reuse(attach_job_id=job_id)
    assert reused["original_digest"] == d1

    row = _write_synthetic_delivery(job_id, d1)

    # THE RETRY JOIN: D1 (the job's digest, which the confirmation kept)
    # serves the persisted row without another read...
    served = background.load_persisted_workdrive_delivery(
        SESSION, user_id="u1", expected_original_digest=d1,
        workspace_id=WORKSPACE)
    assert served is not None
    assert served["rendered"] == row["rendered"]

    # ...while a NEW digest minted from the confirmation's own words never
    # sees it.  This is the divergence the reuse removes.
    d_confirmation = background.canonical_request_digest(
        background.request_scope_from_task(
            session_id=SESSION,
            user_id="u1",
            workspace_id=WORKSPACE,
            resource_id=RID,
            file_name=FILE_NAME,
            original_message=CONFIRMATION,
            requested_targets=TARGETS,
        )
    )
    assert d_confirmation != d1
    assert background.load_persisted_workdrive_delivery(
        SESSION, user_id="u1", expected_original_digest=d_confirmation,
        workspace_id=WORKSPACE) is None


def test_confirmed_mention_never_enters_the_scheduled_scope(
    durable_db, active_grant,
):
    import integrations.chat_orchestrator as chat

    pending = build_pending_task(ASK, FILE_NAME.lower())
    pending["resolved_file"] = _identity()
    pending["requested_targets"] = list(TARGETS)
    # Retry bookkeeping names a different tentative file; the pinned identity
    # and the accepted ask (not the confirmation's words) define the scope.
    pending["confirmed_mention"] = "a different tentative name.xlsx"
    pending["confirmation_turn"] = True
    pending["confirmation_message"] = CONFIRMATION

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.tenant_id = "default"
    scheduled = orch._schedule_strict_workdrive_background_read(
        pending,
        message=ASK,
        user_id="u1",
        session_id=SESSION,
        workspace_id=WORKSPACE,
        execution_id=ORIGIN_EXECUTION,
        spawn=False,
    )

    job = _job_metadata(scheduled["job_id"])
    assert job["resource_id"] == RID
    assert job["file_name"] == FILE_NAME
    assert job["original_message"] == ASK
    assert job["request_scope"]["file_name"] == FILE_NAME.lower()
    assert job["request_scope"]["original_message"] == ASK
    assert "tentative name" not in job["request_scope"]["original_message"]


class _NeverCalledReads:
    def __init__(self):
        self.live_reads = 0

    async def block(self, *args, **kwargs):
        self.live_reads += 1
        raise AssertionError("a confirmation must not start a live read")


def test_direct_read_attaches_before_any_live_attempt(durable_db, active_grant):
    import integrations.chat_orchestrator as chat

    scheduled = _schedule()
    job_id = scheduled["job_id"]
    d1 = scheduled["original_digest"]

    pending = build_pending_task(ASK, FILE_NAME.lower())
    pending["resolved_file"] = _identity()
    pending["requested_targets"] = list(TARGETS)
    pending["operation"] = "re-run"  # pending → confirmation is stamped as re-run
    pending["confirmation_turn"] = True
    pending["confirmation_message"] = CONFIRMATION
    pending["background_job_id"] = job_id

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.llm_service = None
    orch.tenant_id = "default"
    reads = _NeverCalledReads()

    os.environ["ATOM_620_STRICT_WORKDRIVE_PROOF"] = "1"
    try:
        with patch(
            "core.chat_tool_planner._datasets_named_file_block",
            new=reads.block,
        ):
            result = asyncio.run(orch._direct_confirmed_file_read(
                pending, [], "u1", SESSION, WORKSPACE,
                SimpleNamespace(remaining=lambda: 5.0),
                execution_id="exec-confirmation-2"))
    finally:
        os.environ.pop("ATOM_620_STRICT_WORKDRIVE_PROOF", None)

    assert reads.live_reads == 0
    assert result["ok"] is True
    assert result["background_pending"] is True
    assert result["read_executed"] is False
    assert result["background_read"]["job_id"] == job_id
    assert result["background_read"]["original_digest"] == d1
    assert result["background_read"]["attach_mode"] == "job_id"
    assert len(_job_rows()) == 1


def test_retry_after_attach_serves_job_one_delivery_without_reading(
    durable_db, active_grant,
):
    """The retry after job #1 finished: the confirmation's carried job id
    selects job #1's persisted row — no live read, no second job, no
    dependence on the confirmation's wording."""
    import integrations.chat_orchestrator as chat

    scheduled = _schedule()
    job_id = scheduled["job_id"]
    d1 = scheduled["original_digest"]
    background._finish_job(
        job_id, background._JOB_STATUS_COMPLETED, summary="done")
    _write_synthetic_delivery(job_id, d1)

    # The in-memory carrier can still say "pending" after the background
    # delivery (the durable row is authoritative); a bare confirmation then
    # resumes as re-run. It must still serve job #1's row.
    pending = build_pending_task(ASK, FILE_NAME.lower())
    pending["status"] = "pending"
    pending["operation"] = "re-run"
    pending["resolved_file"] = _identity()
    pending["requested_targets"] = list(TARGETS)
    pending["confirmation_turn"] = True
    pending["confirmation_message"] = CONFIRMATION
    pending["background_job_id"] = job_id

    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    orch.llm_service = None
    orch.tenant_id = "default"
    reads = _NeverCalledReads()

    with patch(
        "core.chat_tool_planner._datasets_named_file_block",
        new=reads.block,
    ):
        result = asyncio.run(orch._direct_confirmed_file_read(
            pending, [], "u1", SESSION, WORKSPACE,
            execution_id="exec-confirmation-retry"))

    assert reads.live_reads == 0
    assert result["ok"] is True
    assert result["served_from_persisted_delivery"] is True
    assert result["read_executed"] is False
    assert result["background_delivery"]["job_id"] == job_id
    assert len(_job_rows()) == 1


def test_direct_task_words_never_replace_a_confirmation_ask():
    import integrations.chat_orchestrator as chat

    confirmation_task = build_pending_task(ASK, FILE_NAME.lower())
    confirmation_task["confirmation_turn"] = True
    assert chat._direct_task_uses_turn_words(
        confirmation_task, CONFIRMATION) is False

    # A turn that names its own work still replaces the executed words.
    ordinary = build_pending_task(ASK, FILE_NAME.lower())
    assert chat._direct_task_uses_turn_words(
        ordinary, "find the prices of U-38 and 700") is True
    assert chat._direct_task_uses_turn_words(
        {**ordinary, "revised_targets": ["U-38"]},
        "anything at all") is True


@pytest.mark.asyncio
async def test_normal_entry_timeout_and_filename_confirmation_share_one_job(
    durable_db, active_grant, monkeypatch,
):
    """The NORMAL chat entry, not a helper-only path.

    The first ask's interactive read times out and becomes job #1.  Its scope
    must carry the canonical ask, all six requested targets, and the accepted
    ``price`` field even though the live ask task was built before the task
    row existed.  A later plain filename confirmation must attach to that same
    job and digest without widening its targets/fields or queuing job #2.
    """
    import integrations.chat_orchestrator as chat
    from core.pending_file_task import FILE_TASK_SESSION_KEY

    ask = (
        "find the prices of No. 381, No. 622, No. 700, No. 710, "
        "No. 720 and No. 730 in Synthetic Confirmation Price List.xlsx"
    )
    confirmation = (
        "yes, Synthetic Confirmation Price List.xlsx is correct"
    )
    targets = ["381", "622", "700", "710", "720", "730"]
    session = {"id": "session-normal-entry-620", "messages": []}

    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m",
        "provider": "p"})
    orch.llm_service = llm

    async def _interactive_deadline(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setenv("ATOM_620_STRICT_WORKDRIVE_PROOF", "1")
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            orch, "_get_or_create_session", return_value=session))
        stack.enter_context(patch.object(
            orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)))
        stack.enter_context(patch.object(
            orch, "_start_chat_execution", return_value="exec-entry-620"))
        stack.enter_context(patch.object(
            orch, "_record_chat_step", new=AsyncMock()))
        stack.enter_context(patch.object(
            orch, "_emit_agent_status", new=AsyncMock()))
        stack.enter_context(patch.object(orch, "_finish_chat_execution"))
        stack.enter_context(patch.object(orch, "_update_session"))
        stack.enter_context(patch(
            "core.chat_mini_app_authoring.try_handle",
            new=AsyncMock(return_value=None)))
        stack.enter_context(patch.object(
            orch, "_try_zoho_crm_write", new=AsyncMock()))
        stack.enter_context(patch.object(
            orch, "_route_to_features", new=AsyncMock(return_value={})))
        stack.enter_context(patch.object(
            orch, "_get_qwen_response", new=AsyncMock(return_value={
                "success": True, "message": "qwen",
                "session_id": session["id"]})))
        stack.enter_context(patch(
            "core.turn_decision.interpret_turn_request",
            new=AsyncMock(return_value=None)))
        stack.enter_context(patch(
            "core.chat_tool_planner._datasets_named_file_block",
            new=_interactive_deadline))
        # The durable job row is what this test proves; do not execute a
        # provider read in the test process.
        stack.enter_context(patch.object(
            background, "spawn_background_read", return_value=False))

        first = await orch.process_chat_message(
            "u1", ask, session["id"],
            context={"workspace_id": WORKSPACE})
        rows = _job_rows()
        assert len(rows) == 1, (
            "the timed-out original ask must schedule exactly one job; "
            f"response was {first!r}")
        job_id = str(rows[0].id)
        job = _job_metadata(job_id)
        digest = job["original_digest"]

        # The FIRST job carries the canonical accepted scope, including the
        # field the later confirmation derives from the same original ask.
        assert job["original_message"] == ask
        assert job["request_scope"]["original_message"] == ask
        assert job["requested_targets"] == targets
        assert job["request_scope"]["requested_targets"] == targets
        assert job["requested_fields"] == ["price"]
        assert job["request_scope"]["requested_fields"] == ["price"]
        assert job["resource_id"] == ""
        task = session[FILE_TASK_SESSION_KEY]
        assert task["background_job_id"] == job_id
        assert task["requested_targets"] == targets
        assert task["requested_fields"] == ["price"]

        second = await orch.process_chat_message(
            "u1", confirmation, session["id"],
            context={"workspace_id": WORKSPACE})

    assert second["success"] is True
    assert second["data"]["background_pending"] is True
    attached = second["data"]["background_read"]
    assert attached["reused"] is True
    assert attached["attached"] is True
    assert attached["attach_mode"] == "job_id"
    assert attached["job_id"] == job_id
    assert attached["original_digest"] == digest
    assert len(_job_rows()) == 1, "the confirmation must not queue job #2"

    # Attaching does not widen what job #1 was authorized to read.
    job = _job_metadata(job_id)
    assert job["request_scope"]["original_message"] == ask
    assert job["request_scope"]["requested_targets"] == targets
    assert job["request_scope"]["requested_fields"] == ["price"]
    assert job["requested_targets"] == targets
    assert job["requested_fields"] == ["price"]
    assert job["original_digest"] == digest


EIGHT_ITEM_ASK = (
    "find the prices of these 8 machines in Synthetic Confirmation "
    "Price List.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, "
    "SLE16-8 and U-38"
)
EIGHT_ITEM_TARGETS = [
    "381", "U-22", "622", "SLE24-16", "GSL48-16", "GSL24-16",
    "SLE16-8", "U-38",
]
EIGHT_ITEM_CONFIRMATION = (
    "yes, Synthetic Confirmation Price List.xlsx is correct"
)


@pytest.mark.asyncio
async def test_normal_entry_comma_list_keeps_bare_numeric_ids(
    durable_db, active_grant, monkeypatch,
):
    """The signed-in ask's exact shape: eight comma-separated identifiers,
    two of them bare numerics.

    The count ('8') and the filename year ('2019') are not identifiers; '381'
    and '622' are.  The background job and the later filename confirmation
    must both retain all eight, in order, with no widened/narrowed scope.
    """
    import integrations.chat_orchestrator as chat
    from core.pending_file_task import FILE_TASK_SESSION_KEY

    session = {"id": SESSION, "messages": []}

    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m",
        "provider": "p"})
    orch.llm_service = llm

    async def _interactive_deadline(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setenv("ATOM_620_STRICT_WORKDRIVE_PROOF", "1")
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            orch, "_get_or_create_session", return_value=session))
        stack.enter_context(patch.object(
            orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)))
        stack.enter_context(patch.object(
            orch, "_start_chat_execution", return_value="exec-entry-620"))
        stack.enter_context(patch.object(
            orch, "_record_chat_step", new=AsyncMock()))
        stack.enter_context(patch.object(
            orch, "_emit_agent_status", new=AsyncMock()))
        stack.enter_context(patch.object(orch, "_finish_chat_execution"))
        stack.enter_context(patch.object(orch, "_update_session"))
        stack.enter_context(patch(
            "core.chat_mini_app_authoring.try_handle",
            new=AsyncMock(return_value=None)))
        stack.enter_context(patch.object(
            orch, "_try_zoho_crm_write", new=AsyncMock()))
        stack.enter_context(patch.object(
            orch, "_route_to_features", new=AsyncMock(return_value={})))
        stack.enter_context(patch.object(
            orch, "_get_qwen_response", new=AsyncMock(return_value={
                "success": True, "message": "qwen",
                "session_id": session["id"]})))
        stack.enter_context(patch(
            "core.turn_decision.interpret_turn_request",
            new=AsyncMock(return_value=None)))
        stack.enter_context(patch(
            "core.chat_tool_planner._datasets_named_file_block",
            new=_interactive_deadline))
        stack.enter_context(patch.object(
            background, "spawn_background_read", return_value=False))

        first = await orch.process_chat_message(
            "u1", EIGHT_ITEM_ASK, session["id"],
            context={"workspace_id": WORKSPACE})
        rows = _job_rows()
        assert len(rows) == 1, (
            "the timed-out eight-item ask must schedule exactly one job; "
            f"response was {first!r}")
        job_id = str(rows[0].id)
        job = _job_metadata(job_id)
        digest = job["original_digest"]
        assert job["requested_targets"] == EIGHT_ITEM_TARGETS
        assert job["request_scope"]["requested_targets"] == EIGHT_ITEM_TARGETS
        assert job["requested_fields"] == ["price"]
        assert "8" not in job["requested_targets"]
        assert "2019" not in job["requested_targets"]
        task = session[FILE_TASK_SESSION_KEY]
        assert task["background_job_id"] == job_id
        assert task["requested_targets"] == EIGHT_ITEM_TARGETS

        second = await orch.process_chat_message(
            "u1", EIGHT_ITEM_CONFIRMATION, session["id"],
            context={"workspace_id": WORKSPACE})

    assert second["success"] is True
    assert second["data"]["background_pending"] is True
    attached = second["data"]["background_read"]
    assert attached["reused"] is True
    assert attached["attached"] is True
    assert attached["job_id"] == job_id
    assert attached["original_digest"] == digest
    assert len(_job_rows()) == 1

    job = _job_metadata(job_id)
    assert job["requested_targets"] == EIGHT_ITEM_TARGETS
    assert job["request_scope"]["requested_targets"] == EIGHT_ITEM_TARGETS
    assert job["original_digest"] == digest
    task = session[FILE_TASK_SESSION_KEY]
    assert task["background_job_id"] == job_id
    assert task["requested_targets"] == EIGHT_ITEM_TARGETS


@pytest.mark.asyncio
async def test_normal_entry_go_after_saved_delivery_is_served(
    durable_db, active_grant, monkeypatch,
):
    """The third turn is exactly 'go' after the job's result was persisted.

    The timeout turn leaves an honest 'nothing was read' acknowledgement on
    the session.  That carrier must not shadow the saved delivery: 'go'
    serves the persisted result deterministically — same job identity, no
    live read, no model/feature routing.
    """
    import integrations.chat_orchestrator as chat
    from core.pending_file_task import FILE_TASK_SESSION_KEY

    session = {"id": SESSION, "messages": []}

    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m",
        "provider": "p"})
    orch.llm_service = llm
    qwen = AsyncMock(return_value={
        "success": True, "message": "automatic model routing",
        "session_id": session["id"]})
    feature_routes = AsyncMock(return_value={})

    async def _interactive_deadline(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setenv("ATOM_620_STRICT_WORKDRIVE_PROOF", "1")
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            orch, "_get_or_create_session", return_value=session))
        stack.enter_context(patch.object(
            orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)))
        stack.enter_context(patch.object(
            orch, "_start_chat_execution", return_value="exec-entry-620"))
        stack.enter_context(patch.object(
            orch, "_record_chat_step", new=AsyncMock()))
        stack.enter_context(patch.object(
            orch, "_emit_agent_status", new=AsyncMock()))
        stack.enter_context(patch.object(orch, "_finish_chat_execution"))
        stack.enter_context(patch.object(orch, "_update_session"))
        stack.enter_context(patch(
            "core.chat_mini_app_authoring.try_handle",
            new=AsyncMock(return_value=None)))
        stack.enter_context(patch.object(
            orch, "_try_zoho_crm_write", new=AsyncMock()))
        stack.enter_context(patch.object(
            orch, "_route_to_features", new=feature_routes))
        stack.enter_context(patch.object(
            orch, "_get_qwen_response", new=qwen))
        stack.enter_context(patch(
            "core.turn_decision.interpret_turn_request",
            new=AsyncMock(return_value=None)))
        stack.enter_context(patch(
            "core.chat_tool_planner._datasets_named_file_block",
            new=_interactive_deadline))
        stack.enter_context(patch.object(
            background, "spawn_background_read", return_value=False))

        await orch.process_chat_message(
            "u1", EIGHT_ITEM_ASK, session["id"],
            context={"workspace_id": WORKSPACE})
        rows = _job_rows()
        assert len(rows) == 1
        job_id = str(rows[0].id)
        digest = _job_metadata(job_id)["original_digest"]

        attached = await orch.process_chat_message(
            "u1", EIGHT_ITEM_CONFIRMATION, session["id"],
            context={"workspace_id": WORKSPACE})
        assert attached["data"]["background_pending"] is True

        # The result arrives after the confirmation.  The session still
        # carries the timeout turn's rendered-but-unservable ack.
        background._finish_job(
            job_id, background._JOB_STATUS_COMPLETED, summary="done")
        _write_synthetic_delivery(job_id, digest)
        task = session[FILE_TASK_SESSION_KEY]
        task["status"] = "retrieved"
        assert (session.get("_pending_file_result") or {}).get(
            "status") == "incomplete"

        qwen.reset_mock()
        feature_routes.reset_mock()
        third = await orch.process_chat_message(
            "u1", "go", session["id"],
            context={"workspace_id": WORKSPACE})

    assert third["success"] is True
    assert third["model"] == "deterministic"
    assert third["data"]["deterministic_delivery"] is True
    assert "synthetic background answer" in third["message"]
    qwen.assert_not_awaited()
    feature_routes.assert_not_awaited()
    assert len(_job_rows()) == 1, "'go' must not queue another read"

    job = _job_metadata(job_id)
    assert job["original_digest"] == digest
    assert job["requested_targets"] == EIGHT_ITEM_TARGETS
    task = session[FILE_TASK_SESSION_KEY]
    assert task["background_job_id"] == job_id
    assert task["requested_targets"] == EIGHT_ITEM_TARGETS
    assert task["status"] == "delivered"
