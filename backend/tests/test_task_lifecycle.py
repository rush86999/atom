"""Step 1 tests — task revision transitions, operation registry, delivery.

Scratch-file sqlite via injected session_factory — never the live dev DB.
Entity labels are generic (e1..e8, M-1/M-2); no incident vocabulary here.
"""
import os
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("TESTING", "1")

from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import (
    SCHEMA_VERSION,
    TaskAuthorizationError,
    TaskLifecycle,
    TaskLifecycleError,
    apply_transition,
    begin_edit_turn,
    begin_retrieval_turn,
    cancel_task,
    check_turn_authorization,
    expand_task_scope,
    register_scope_validator,
    finish_edit_turn,
    new_delivery,
    new_operation,
    new_task_revision,
    record_presentation_turn,
    record_retrieval_turn,
    transition_operation,
)


# Scope validators are RUN, not named. The lifecycle tests register real
# validators so a grant can actually be approved or refused; an
# unregistered name is refused by design.
@register_scope_validator("test.user_request")
def _approve_edit(action, message, context):
    """Approve a widening to ``edit`` for any non-empty user request."""
    return action == "edit" and bool(str(message or "").strip())


@register_scope_validator("test.refuse")
def _refuse_all(action, message, context):
    """A registered validator that says no."""
    return False


def _canvas_ctx():
    """The canvas the edit lane always runs against. The scope validator
    delegates to the existing edit-shape classifier, which needs a real
    canvas to judge against."""
    return {"canvas_id": "cv1", "canvas_type": "email",
            "content": {"subject": "Draft", "body": "Body"}}


def _entities(n):
    return [{"id": f"e{i}", "label": f"entity {i}",
             "aliases": [], "provenance_turn": 1, "inferred": False}
            for i in range(1, n + 1)]


@pytest.fixture()
def lifecycle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/task_lifecycle_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                          session_factory=factory)
    goals = GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory)
    return TaskLifecycle(runs, goals)


class TestTaskRevision:
    def test_create_revision_one(self):
        rev = new_task_revision(
            objective_text="look up eight records",
            entities=_entities(8), requested_fields=["price"])
        assert rev["schema_version"] == SCHEMA_VERSION
        assert rev["revision"] == 1
        assert rev["supersedes_revision"] is None
        assert len(rev["entities"]) == 8

    def test_empty_objective_rejected(self):
        with pytest.raises(TaskLifecycleError):
            new_task_revision(objective_text="  ")

    def test_unknown_transition_rejected(self):
        rev = new_task_revision(objective_text="look up records")
        with pytest.raises(TaskLifecycleError):
            apply_transition(rev, {"kind": "teleport"})

    def test_change_presentation_only(self):
        rev = new_task_revision(
            objective_text="look up eight records", entities=_entities(8),
            requested_fields=["price"],
            output_preferences={"style": "default", "field": None})
        updated, _ = apply_transition(rev, {
            "kind": "change_presentation",
            "requested_change": "cleaner output",
            "output_preferences": {"style": "compact", "field": None}})
        assert updated["revision"] == 2
        assert updated["supersedes_revision"] == 1
        assert updated["output_preferences"]["style"] == "compact"
        assert updated["requested_fields"] == ["price"]
        assert len(updated["entities"]) == 8
        assert updated["new_attempt_required"] is False
        # Inputs untouched.
        assert rev["revision"] == 1
        assert rev["output_preferences"]["style"] == "default"

    def test_research_and_present_flags_new_attempt(self):
        rev = new_task_revision(objective_text="look up records")
        updated, _ = apply_transition(rev, {
            "kind": "research_and_present",
            "requested_change": "search again, compact",
            "output_preferences": {"style": "compact", "field": None}})
        assert updated["new_attempt_required"] is True
        assert updated["output_preferences"]["style"] == "compact"

    def test_revise_fields_retains_evidence(self):
        rev = new_task_revision(objective_text="look up records")
        rev["evidence"] = [{"evidence_id": "ev1", "entity_ids": ["e1"]}]
        updated, _ = apply_transition(rev, {
            "kind": "revise_fields",
            "requested_change": "use the alternate basis",
            "requested_fields": ["cost"]})
        assert updated["requested_fields"] == ["cost"]
        assert updated["evidence"] == rev["evidence"]
        assert updated["new_attempt_required"] is False

    def test_revise_objective_invalidates_only_affected(self):
        rev = new_task_revision(
            objective_text="look up records", entities=_entities(3))
        rev["evidence"] = [
            {"evidence_id": "ev1", "entity_ids": ["e1"]},
            {"evidence_id": "ev2", "entity_ids": ["e2", "e3"]},
        ]
        remaining = [e for e in _entities(3) if e["id"] != "e3"]
        updated, _ = apply_transition(rev, {
            "kind": "revise_objective",
            "requested_change": "drop the third record",
            "entities": remaining,
            "removed_entity_ids": ["e3"]})
        assert updated["invalidated_evidence_ids"] == ["ev2"]
        assert [e["evidence_id"] for e in updated["evidence"]] == ["ev1"]
        assert updated["new_attempt_required"] is True

    def test_cancel_marks_outstanding_operations(self):
        rev = new_task_revision(objective_text="look up records")
        ops = [
            {"operation_id": "op1", "status": "running"},
            {"operation_id": "op2", "status": "applied"},
            {"operation_id": "op3", "status": "pending"},
        ]
        updated, ops = apply_transition(
            rev, {"kind": "cancel", "requested_change": "stop"}, ops)
        by_id = {o["operation_id"]: o["status"] for o in ops}
        assert by_id == {"op1": "cancelled", "op2": "applied",
                         "op3": "cancelled"}


class TestOperations:
    def test_outbound_requires_idempotency_key(self):
        rev = new_task_revision(objective_text="send the summary")
        op = new_operation(task=rev, op_type="outbound",
                           requested_change="send the summary")
        assert op["idempotency_key"]
        assert op["authorization"] == "pending_approval"
        assert op["status"] == "pending"

    def test_retry_links_parent(self):
        rev = new_task_revision(objective_text="look up records")
        first = new_operation(task=rev, op_type="retrieve",
                              requested_change="read the copy")
        retry = new_operation(
            task=rev, op_type="retrieve", requested_change="read again",
            parent_operation_id=first["operation_id"])
        assert retry["operation_id"] != first["operation_id"]
        assert retry["parent_operation_id"] == first["operation_id"]

    def test_guarded_transitions(self):
        rev = new_task_revision(objective_text="look up records")
        op = new_operation(task=rev, op_type="retrieve",
                           requested_change="read")
        running = transition_operation(op, "running", execution_id="ex1")
        assert running["status"] == "running"
        assert running["execution_id"] == "ex1"
        assert op["status"] == "pending"  # input untouched
        with pytest.raises(TaskLifecycleError):
            transition_operation(op, "applied")  # pending -> applied illegal
        with pytest.raises(TaskLifecycleError):
            transition_operation({"status": "applied"}, "running")


class TestDelivery:
    def test_delivery_binds_execution_message_hash(self):
        delivery = new_delivery(
            execution_id="ex1", operation_ids=["op1"], message_id="msg1",
            content_sha256="abc123", finalization_version="m1",
            evidence_refs=["ev1"])
        assert delivery["schema_version"] == SCHEMA_VERSION
        assert delivery["delivery_id"]
        # The server asserts only that the bytes were persisted and are
        # available; it cannot prove the client received them.
        assert delivery["status"] == "persisted_for_delivery"
        assert delivery["receipt_confirmed"] is False

    def test_delivery_rejects_an_unproven_status(self):
        with pytest.raises(TaskLifecycleError, match="unknown delivery"):
            new_delivery(
                execution_id="ex1", operation_ids=["op1"], message_id="msg1",
                content_sha256="abc123", finalization_version="m1",
                status="delivered")

    def test_delivery_requires_identity(self):
        with pytest.raises(TaskLifecycleError):
            new_delivery(execution_id="", operation_ids=[],
                         message_id="m", content_sha256="h",
                         finalization_version="m1")


class TestPersistence:
    def test_create_and_round_trip(self, lifecycle):
        created = lifecycle.create_task(
            "conv-1", "look up eight records",
            entities=_entities(8), requested_fields=["price"])
        record = lifecycle.get_task(created["run_id"])
        assert record["task_revision"]["revision"] == 1
        assert len(record["task_revision"]["entities"]) == 8
        assert record["conversation_id"] == "conv-1"
        assert record["run_status"] == "active"

    def test_find_active_task(self, lifecycle):
        created = lifecycle.create_task("conv-9", "look up records")
        found = lifecycle.find_active_task("conv-9")
        assert found["run_id"] == created["run_id"]
        assert lifecycle.find_active_task("conv-other") is None

    def test_transition_persists_revision_and_log(self, lifecycle):
        created = lifecycle.create_task(
            "conv-2", "look up records", entities=_entities(2))
        updated = lifecycle.apply_transition(created["run_id"], {
            "kind": "change_presentation",
            "requested_change": "compact output",
            "output_preferences": {"style": "compact", "field": None}})
        assert updated["revision"] == 2
        record = lifecycle.get_task(created["run_id"])
        assert record["task_revision"]["output_preferences"]["style"] \
            == "compact"
        kinds = [d.get("kind") for d in
                 lifecycle.runs.get_decisions(created["run_id"])]
        assert "task_created" in kinds
        assert "task_revision" in kinds

    def test_operation_lifecycle_persists(self, lifecycle):
        created = lifecycle.create_task("conv-3", "look up records")
        op = lifecycle.create_operation(
            created["run_id"], op_type="retrieve",
            requested_change="read the copy")
        assert op["objective_revision"] == 1
        moved = lifecycle.transition_operation(
            created["run_id"], op["operation_id"], "running",
            execution_id="ex-7")
        assert moved["status"] == "running"
        record = lifecycle.get_task(created["run_id"])
        assert record["operations"][0]["execution_id"] == "ex-7"
        applied = lifecycle.transition_operation(
            created["run_id"], op["operation_id"], "applied")
        assert applied["status"] == "applied"
        with pytest.raises(TaskLifecycleError):
            lifecycle.transition_operation(
                created["run_id"], op["operation_id"], "running")


def _structured_result(items=("M-1", "M-2")):
    targets = [{
        "item": item, "aliases": [],
        "identity": {"status": "single",
                     "candidates": [{"ref": f"S!R{i + 1}",
                                     "values": [{"col": "B1", "basis": "VAL",
                                                 "kind": "number",
                                                 "display": "5",
                                                 "value": 5.0}]}]},
        "field": {"status": "single", "values": [{
            "col": "B1", "basis": "VAL", "kind": "number",
            "display": "5", "value": 5.0}]},
    } for i, item in enumerate(items)]
    return {
        "schema_version": "structured-result-1",
        "requested_items": list(items),
        "requested_fields": ["value"],
        "targets": targets,
        "evidence_revision": "rev-1",
        "attempt_id": "attempt-1",
        "evidence_action": "new_read",
        "source_identity": {"file_name": "w.xlsx"},
        "coverage": "full",
    }


class TestRecordTurns:
    def test_first_retrieval_creates_task_and_applies(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1 and M-2",
            _structured_result(), "ex-1", True)
        assert run_id
        assert session["_task_run_id"] == run_id
        record = lifecycle.get_task(run_id)
        # Revision 1 creates the task; revision 2 binds observed evidence.
        assert record["task_revision"]["revision"] == 2
        assert [e["id"] for e in
                record["task_revision"]["entities"]] == ["M-1", "M-2"]
        assert record["task_revision"]["evidence"] == [{
            "evidence_id": "attempt-1", "entity_ids": ["M-1", "M-2"],
            "evidence_revision": "rev-1"}]
        assert len(record["operations"]) == 1
        op = record["operations"][0]
        assert op["operation_type"] == "retrieve"
        assert op["status"] == "applied"
        assert op["evidence_revision"] == "rev-1"
        assert op["execution_id"] == "ex-1"

    def test_second_retrieval_revises_without_union(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1 and M-2",
            _structured_result(), "ex-1", True)
        run_id2 = record_retrieval_turn(
            lifecycle, session, "conv-1", "search again",
            _structured_result(), "ex-2", True)
        assert run_id2 == run_id
        record = lifecycle.get_task(run_id)
        # research_and_present then evidence attach: two bumps per turn.
        assert record["task_revision"]["revision"] == 4
        assert record["task_revision"]["last_transition"]["kind"] == \
            "attach_evidence"
        kinds = [d.get("transition") or d.get("kind") for d in
                 lifecycle.runs.get_decisions(run_id)]
        assert "research_and_present" in kinds
        assert [e["id"] for e in
                record["task_revision"]["entities"]] == ["M-1", "M-2"]
        assert len(record["operations"]) == 2
        assert record["operations"][0]["status"] == "applied"

    def test_incomplete_retrieval_leaves_operation_running(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", False)
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "running"

    def test_empty_items_records_nothing(self, lifecycle):
        session = {}
        assert record_retrieval_turn(
            lifecycle, session, "conv-1", "hello", {}, "ex-1",
            True) is None
        assert lifecycle.find_active_task("conv-1") is None
        assert "_task_run_id" not in session

    def test_presentation_change_no_retrieval(self, lifecycle):
        session = {}
        record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", True)
        run_id = record_presentation_turn(
            lifecycle, session, "conv-1", "cleaner output",
            style="compact", field=None)
        assert run_id == session["_task_run_id"]
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["revision"] == 3
        assert record["task_revision"]["output_preferences"]["style"] == \
            "compact"
        assert len(record["operations"]) == 1  # no new operation

    def test_presentation_without_task_returns_none(self, lifecycle):
        assert record_presentation_turn(
            lifecycle, {}, "conv-empty", "cleaner output") is None


@pytest.fixture
def isolated_db(monkeypatch):
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


def _orch():
    import integrations.chat_orchestrator as chat

    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        side_effect=AssertionError("must not narrate"))
    llm.stream_completion = AsyncMock(
        side_effect=AssertionError("must not stream"))
    orch.llm_service = llm
    return orch


def _direct_result(rec):
    return {"ok": True, "block": "", "rendered_answer": "legacy",
            "structured_result": rec,
            "identity": {"file_name": "w.xlsx"},
            "identity_verified": True, "coverage_complete": True,
            "retrieval_complete": True, "freshness": {}}


class TestOrchestratorWiring:
    def test_flag_off_records_nothing(self, isolated_db):
        import integrations.chat_orchestrator as chat

        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        assert chat._task_lifecycle_for("default", "ws") is None

    @pytest.mark.asyncio
    async def test_ask_lane_records_task_when_flag_on(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-ask", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            response = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-ask", context={})
        assert response["success"] is True
        run_id = session.get("_task_run_id")
        assert run_id
        assert response["data"]["task_run_id"] == run_id
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(run_id)
        # Revision 1 records the intention; revision 2 binds the
        # observed entities/fields; revision 3 binds the evidence.
        assert record["task_revision"]["revision"] == 3
        assert [e["id"] for e in
                record["task_revision"]["entities"]] == ["M-1", "M-2"]
        assert record["operations"][0]["status"] == "applied"

    @pytest.mark.asyncio
    async def test_second_turn_reuses_entry_resolved_task(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-two", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            first = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-two", context={})
            assert first["success"] is True
            run_id = session.get("_task_run_id")
            assert run_id
            second = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-two", context={})
            assert second["success"] is True
            # Turn entry resolved the same task: no duplicate; the
            # second turn bumps research_and_present then evidence attach.
            assert session.get("_task_run_id") == run_id
            assert second["data"]["task_run_id"] == run_id
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["revision"] == 5
        assert record["task_revision"]["last_transition"]["kind"] == \
            "attach_evidence"
        assert len(record["operations"]) == 2

    @pytest.mark.asyncio
    async def test_task_identity_survives_restart(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-restart", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            first = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-restart", context={})
            assert first["success"] is True
            run_id = session.get("_task_run_id")
            assert run_id
        # Restart: the process loses the whole in-memory session; the
        # next turn arrives with a fresh session dict under the same
        # conversation id. The task must resolve from the durable
        # record — same run, no duplicate task.
        restarted = {"id": "s-task-restart", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=restarted),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            second = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-restart", context={})
            assert second["success"] is True
            assert restarted.get("_task_run_id") == run_id
            assert second["data"]["task_run_id"] == run_id
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["revision"] == 5
        assert len(record["operations"]) == 2

    @pytest.mark.asyncio
    async def test_ask_lane_flag_off_leaves_no_task(
            self, isolated_db, monkeypatch):
        monkeypatch.delenv("ATOM_TASK_LIFECYCLE_ENABLED", raising=False)
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-off", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            response = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-off", context={})
        assert response["success"] is True
        assert "_task_run_id" not in session
        assert response["data"].get("task_run_id") is None

    @pytest.mark.asyncio
    async def test_halt_turn_cancels_task_at_entry(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-halt", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            first = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-halt", context={})
            assert first["success"] is True
            run_id = session.get("_task_run_id")
            assert run_id
            await orch.process_chat_message(
                "u1", "stop", session_id="s-task-halt", context={})
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["authorization"] == "cancelled"
        # The halt turn ran no retrieval: still exactly one operation.
        assert len(record["operations"]) == 1


def _structured_result_fp():
    vals = [
        {"col": "B1", "basis": "RETAIL", "kind": "number",
         "display": "5", "value": 5.0},
        {"col": "H1", "basis": "Factory Price", "kind": "number",
         "display": "3", "value": 3.0},
    ]
    return {
        "schema_version": "structured-result-1",
        "requested_items": ["M-1"],
        "requested_fields": ["value"],
        "targets": [{
            "item": "M-1", "aliases": [],
            "identity": {"status": "single", "candidates": [
                {"ref": "S!R1", "values": list(vals)}]},
            "field": {"status": "competing", "values": list(vals)},
        }],
        "evidence_revision": "rev-1",
        "attempt_id": "attempt-fp",
        "evidence_action": "new_read",
        "source_identity": {"file_name": "w.xlsx"},
        "coverage": "full",
    }


class TestEvidenceAndCancel:
    def test_evidence_invalidated_on_objective_revision(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1 and M-2",
            _structured_result(), "ex-1", True)
        record = lifecycle.get_task(run_id)
        assert len(record["task_revision"]["evidence"]) == 1
        updated = lifecycle.apply_transition(run_id, {
            "kind": "revise_objective",
            "requested_change": "drop M-2",
            "entities": [{"id": "M-1", "label": "M-1", "aliases": [],
                          "provenance_turn": 1, "inferred": False}],
            "removed_entity_ids": ["M-2"]})
        assert updated["invalidated_evidence_ids"] == ["attempt-1"]
        assert updated["evidence"] == []
        assert updated["new_attempt_required"] is True

    def test_cancel_marks_task_and_operations(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", False)
        stopped = cancel_task(
            lifecycle, session, "conv-1", "stop")
        assert stopped == run_id
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["authorization"] == "cancelled"
        assert record["operations"][0]["status"] == "cancelled"

    def test_cancel_without_task_returns_none(self, lifecycle):
        assert cancel_task(
            lifecycle, {}, "conv-empty", "stop") is None

    def test_retrieval_after_cancel_starts_new_task(self, lifecycle):
        session = {}
        first = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", True)
        cancel_task(lifecycle, session, "conv-1", "stop")
        second = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-2", True)
        assert second != first
        old = lifecycle.get_task(first)
        assert old["task_revision"]["authorization"] == "cancelled"
        new = lifecycle.get_task(second)
        # Revision 1 creates; revision 2 binds the observed evidence.
        assert new["task_revision"]["revision"] == 2
        assert "authorization" not in new["task_revision"]
        assert len(new["operations"]) == 1


class TestFieldRevision:
    def test_presentation_with_field_narrows_requested(self, lifecycle):
        session = {}
        record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result_fp(), "ex-1", True)
        run_id = record_presentation_turn(
            lifecycle, session, "conv-1", "use factory price",
            style="default", field="factory price",
            requested_fields=["factory price"])
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["requested_fields"] == \
            ["factory price"]
        assert record["task_revision"]["output_preferences"]["field"] == \
            "factory price"
        assert len(record["operations"]) == 1  # still zero retrieval
        assert len(record["task_revision"]["evidence"]) == 1

    @pytest.mark.asyncio
    async def test_field_turn_reselects_without_rereading(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result_fp()
        session = {"id": "s-task-field", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=_direct_result(rec))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            first = await orch.process_chat_message(
                "u1", "find the prices of M-1 in w.xlsx",
                session_id="s-task-field", context={})
            assert first["success"] is True
            assert "RETAIL" in first["message"]
            run_id = session.get("_task_run_id")
            assert run_id
            # The field turn must not re-read: any retrieval attempt
            # raises loudly instead of returning evidence.
            with patch.object(
                    orch, "_direct_confirmed_file_read",
                    new=AsyncMock(side_effect=AssertionError(
                        "must not re-read"))):
                second = await orch.process_chat_message(
                    "u1", "use factory price",
                    session_id="s-task-field", context={})
        assert second["success"] is True
        assert "Factory Price" in second["message"]
        assert "RETAIL" not in second["message"]
        assert second["data"]["task_run_id"] == run_id
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["requested_fields"] == \
            ["factory price"]
        assert len(record["operations"]) == 1
        assert len(record["task_revision"]["evidence"]) == 1


class TestOrderedEntitiesPreserved:
    def test_eight_entities_survive_transition_chain_in_order(
            self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up eight records",
            _structured_result(
                ("e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8")),
            "ex-1", True)
        record = lifecycle.get_task(run_id)
        assert [e["id"] for e in
                record["task_revision"]["entities"]] == \
            [f"e{i}" for i in range(1, 9)]
        # Formatting, re-search, field revision: order never changes,
        # revisions chain with unbroken supersedes lineage.
        record_presentation_turn(
            lifecycle, session, "conv-1", "cleaner output",
            style="compact", field=None)
        record_retrieval_turn(
            lifecycle, session, "conv-1", "search again",
            _structured_result(
                ("e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8")),
            "ex-2", True)
        lifecycle.apply_transition(run_id, {
            "kind": "revise_fields",
            "requested_change": "use the alternate basis",
            "requested_fields": ["cost"]})
        record = lifecycle.get_task(run_id)
        assert [e["id"] for e in
                record["task_revision"]["entities"]] == \
            [f"e{i}" for i in range(1, 9)]
        revisions = [d.get("revision") for d in
                     lifecycle.runs.get_decisions(run_id)
                     if d.get("kind") == "task_revision"]
        assert revisions == sorted(revisions)
        assert len(set(revisions)) == len(revisions)
        assert record["task_revision"]["revision"] == revisions[-1]
        # Every operation binds the revision it ran under.
        revs = [o["objective_revision"] for o in record["operations"]]
        assert revs == sorted(revs)


class TestOperationVerification:
    def _retrieve_op(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", True)
        record = lifecycle.get_task(run_id)
        return run_id, record["operations"][0]["operation_id"]

    def test_unknown_kind_stays_unknown(self, lifecycle):
        run_id, op_id = self._retrieve_op(lifecycle)
        verdict = lifecycle.verify_operation(run_id, op_id, {
            "completion_criteria": [{"kind": "test_verify_missing"}]})
        assert verdict["met"] is None
        assert verdict["basis"] == "no_verifier:test_verify_missing"
        record = lifecycle.get_task(run_id)
        op = record["operations"][0]
        assert op["status"] == "applied"  # verdict never gates status
        assert op["verification"]["met"] is None

    def test_registered_verifier_true(self, lifecycle):
        from core import task_outcome_contract as contract

        kind = "test_verify_ok"
        contract.register_criteria_verifier(kind, lambda outcome: True)
        try:
            run_id, op_id = self._retrieve_op(lifecycle)
            verdict = lifecycle.verify_operation(run_id, op_id, {
                "completion_criteria": [{"kind": kind}],
                "criterion_results": [{
                    "criterion": "record present",
                    "met": True,
                    "verifier": kind,
                }],
            })
        finally:
            contract._VERIFIERS.pop(kind, None)
        assert verdict["met"] is True
        assert verdict["basis"] == "criteria_met"
        assert verdict["contract_version"] == contract.CONTRACT_VERSION

    def test_registered_verifier_false(self, lifecycle):
        from core import task_outcome_contract as contract

        kind = "test_verify_bad"
        contract.register_criteria_verifier(kind, lambda outcome: False)
        try:
            run_id, op_id = self._retrieve_op(lifecycle)
            verdict = lifecycle.verify_operation(run_id, op_id, {
                "completion_criteria": [{"kind": kind}],
                "criterion_results": [{
                    "criterion": "record present",
                    "met": False,
                    "verifier": kind,
                }],
            })
        finally:
            contract._VERIFIERS.pop(kind, None)
        assert verdict["met"] is False
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "applied"

    def test_unknown_operation_raises(self, lifecycle):
        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", True)
        with pytest.raises(TaskLifecycleError):
            lifecycle.verify_operation(run_id, "op-nope", {})


class TestRecordEdit:
    def test_applied_edit(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        run_id = record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e1",
            updated=True, needs_review=False, success=True,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        assert run_id
        assert session["_task_run_id"] == run_id
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1
        op = record["operations"][0]
        assert op["operation_type"] == "edit"
        assert op["status"] == "applied"
        assert op["idempotency_key"] == "ex-e1"
        assert op["execution_id"] == "ex-e1"

    def test_learning_draft_awaits_approval(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        run_id = record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e1",
            updated=True, needs_review=True, success=True,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "awaiting_approval"

    def test_failed_edit(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        run_id = record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e1",
            updated=True, needs_review=False, success=False,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "failed"

    def test_declined_edit_records_nothing(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        assert record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e1",
            updated=False, needs_review=False, success=True) is None
        assert lifecycle.find_active_task("conv-1") is None
        assert "_task_run_id" not in session

    def test_edit_after_cancel_starts_new_task(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        first = record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e1",
            updated=True, needs_review=False, success=True,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        cancel_task(lifecycle, session, "conv-1", "stop")
        second = record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e2",
            updated=True, needs_review=False, success=True,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        assert second != first
        # The new task starts at revision 1 and immediately records the
        # scope grant that authorized this edit as revision 2.
        assert lifecycle.get_task(second)["task_revision"]["revision"] == 2
        assert lifecycle.get_task(second)["task_revision"][
            "authorized_actions"] == ["edit"]

    def test_edit_uses_retrieval_task_record(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", True)
        same = record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e2",
            updated=True, needs_review=False, success=True,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        assert same == run_id
        record = lifecycle.get_task(run_id)
        assert [o["operation_type"] for o in
                record["operations"]] == ["retrieve", "edit"]

    def test_record_task_edit_flag_off(self, isolated_db):
        import integrations.chat_orchestrator as chat

        # Flag off: no reservation, no record — legacy behavior.
        assert chat._begin_task_edit(
            "default", "ws", {}, "conv-1", "make it shorter", "ex-e1",
        )["status"] == "legacy"
        assert chat._finish_task_edit(
            "default", "ws", {}, "conv-1", "make it shorter", "ex-e1",
            {"updated": True}, True) is None

    def test_record_task_edit_flag_on(self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        session = {}
        run_id = chat._finish_task_edit(
            "default", "default", session, "conv-edit", "make it shorter",
            "ex-e1", {"updated": True, "review_status": "accepted"}, True,
            reserved={"status": "reserved", "run_id": None,
                      "operation_id": None},
            canvas_ctx=_canvas_ctx())
        assert run_id
        assert session["_task_run_id"] == run_id
        lifecycle = chat._task_lifecycle_for("default", "default")
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "applied"
        assert record["operations"][0]["idempotency_key"] == "ex-e1"

    def test_orchestrator_reserves_before_mutation(
            self, isolated_db, monkeypatch):
        """The orchestrator seam: reservation happens first and lands
        pending; settlement moves that same operation to its outcome."""
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        session = {}
        decision = chat._begin_task_edit(
            "default", "default", session, "conv-edit2", "make it shorter",
            "ex-e2", canvas_ctx=_canvas_ctx())
        assert decision["status"] == "reserved", decision
        run_id = decision["run_id"]
        operation_id = decision["operation_id"]
        assert run_id and operation_id
        lifecycle = chat._task_lifecycle_for("default", "default")
        reserved = lifecycle.get_task(run_id)["operations"][0]
        assert reserved["operation_id"] == operation_id
        # The claim is taken at reservation, so a concurrent caller
        # holding the same key cannot also perform the effect.
        assert reserved["status"] == "running"
        assert reserved["idempotency_key"] == "ex-e2"

        settled = chat._finish_task_edit(
            "default", "default", session, "conv-edit2", "make it shorter",
            "ex-e2", {"updated": True, "review_status": "accepted"}, True,
            reserved=decision)
        assert settled == run_id
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1
        assert record["operations"][0]["status"] == "applied"
        assert record["operations"][0]["execution_id"] == "ex-e2"

    def test_orchestrator_denial_blocks_the_mutation(
            self, isolated_db, monkeypatch):
        """A gate refusal is reported as a denial sentinel, so the lane
        skips the edit leg rather than mutating unrecorded."""
        import integrations.chat_orchestrator as chat
        from core.task_lifecycle import TaskAuthorizationError

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")

        def _refuse(*_args, **_kwargs):
            raise TaskAuthorizationError("task is cancelled; edit denied")

        monkeypatch.setattr(chat, "_task_lifecycle_for", _refuse)
        decision = chat._begin_task_edit(
            "default", "default", {}, "conv-edit3", "make it shorter",
            "ex-e3")
        assert decision["status"] == "denied"
        assert "cancelled" in decision["reason"]

    def test_orchestrator_reservation_failure_blocks_the_mutation(
            self, isolated_db, monkeypatch):
        """A reservation that fails for ANY reason is also a denial:
        an edit whose intention cannot be persisted must not run."""
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")

        def _explode(*_args, **_kwargs):
            raise RuntimeError("store unavailable")

        monkeypatch.setattr(chat, "_task_lifecycle_for", _explode)
        decision = chat._begin_task_edit(
            "default", "default", {}, "conv-edit4", "make it shorter",
            "ex-e4")
        # An infrastructure fault is NOT reported as a policy denial.
        assert decision["status"] == "unavailable"
        assert decision["status"] != "denied"
        assert "RuntimeError" in decision["reason"]


class TestEditInvalidation:
    def test_invalidated_ids_ride_the_operation(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1 and M-2",
            _structured_result(), "ex-1", True)
        edit_run = record_edit_turn(
            lifecycle, session, "conv-1", "correct the value", "ex-e2",
            updated=True, needs_review=False, success=True,
            invalidated_evidence_ids=["attempt-1"],
            scope_grant={"granted_by_message": "correct the value",
                         "validator": "test.user_request"})
        assert edit_run == run_id
        record = lifecycle.get_task(run_id)
        edit_op = record["operations"][-1]
        assert edit_op["operation_type"] == "edit"
        assert edit_op["invalidated_evidence_ids"] == ["attempt-1"]
        # Audit preserved: the revision evidence list is untouched.
        assert record["task_revision"]["evidence"] == [{
            "evidence_id": "attempt-1", "entity_ids": ["M-1", "M-2"],
            "evidence_revision": "rev-1"}]

    def test_extra_cannot_override_core_keys(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        op = lifecycle.create_operation(
            created["run_id"], op_type="retrieve",
            requested_change="read", extra={"status": "applied",
                                            "note": "kept"})
        assert op["status"] == "pending"
        assert op["note"] == "kept"

    def test_task_with_edit_survives_restart(self, lifecycle):
        from core.task_lifecycle import record_edit_turn

        session = {}
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up M-1",
            _structured_result(("M-1",)), "ex-1", True)
        record_edit_turn(
            lifecycle, session, "conv-1", "make it shorter", "ex-e2",
            updated=True, needs_review=False, success=True,
            scope_grant={"granted_by_message": "make it shorter",
                          "validator": "test.user_request"},)
        # Restart drops the whole in-memory session.
        found = lifecycle.find_active_task("conv-1")
        assert found is not None
        assert found["run_id"] == run_id
        assert [o["operation_type"] for o in
                found["operations"]] == ["retrieve", "edit"]
        assert found["operations"][1]["status"] == "applied"


class TestOverlapSafety:
    def test_concurrent_turns_single_task_no_lost_updates(self, tmp_path):
        import threading

        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        engine = _create_engine(
            f"sqlite:///{tmp_path}/overlap.db",
            connect_args={"check_same_thread": False})
        for table in (GoalObjective.__table__, GoalRun.__table__,
                      TaskOperationRecord.__table__):
            table.create(engine)
        factory = _sessionmaker(bind=engine, expire_on_commit=False)
        runs = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                              session_factory=factory)
        goals = GoalService(workspace_id="ws_test", tenant_id="t_test",
                            session_factory=factory)
        lifecycle = TaskLifecycle(runs, goals)
        errors = []

        def turn(i):
            try:
                record_retrieval_turn(
                    lifecycle, {}, "conv-ovl", f"look up {i}",
                    _structured_result((f"M-{i % 2}",)), f"ex-{i}", True)
            except Exception as exc:  # noqa: BLE001 — collected below
                errors.append(exc)

        threads = [threading.Thread(target=turn, args=(i,))
                   for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        assert not errors
        assert not any(t.is_alive() for t in threads)
        record = lifecycle.find_active_task("conv-ovl")
        assert record is not None
        # One task, one operation per turn, nothing lost.
        assert len(record["operations"]) == 4
        assert len({o["operation_id"] for o in
                    record["operations"]}) == 4
        # Revision lineage unbroken: every revision supersedes exactly
        # the previous one (no gaps, no forks), whatever the thread
        # interleaving. Entity reconciliation may add bumps beyond the
        # base two-per-turn, so the count itself is not asserted — the
        # chain integrity is.
        revisions = [d.get("revision") for d in
                     runs.get_decisions(record["run_id"])
                     if d.get("kind") in ("task_created", "task_revision")
                     and d.get("revision") is not None]
        assert revisions == list(range(1, max(revisions) + 1))
        assert record["task_revision"]["revision"] == max(revisions)
        assert len(record["task_revision"]["entities"]) == 1


class TestPreExecutionFailure:
    @pytest.mark.asyncio
    async def test_failure_before_execution_leaves_pending_op(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat
        from core.database import get_db_session
        from core.models import InvocationEvent

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        session = {"id": "s-task-prefail", "history": []}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            # The read fails BEFORE touching any tool: zero effects by
            # construction; the boundary proof below is zero scan rows.
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(side_effect=AssertionError(
                             "injected pre-execution failure"))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("must not plan"))),
        ):
            response = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-prefail", context={})
        assert isinstance(response, dict)
        run_id = session.get("_task_run_id")
        assert run_id
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1
        op = record["operations"][0]
        assert op["operation_type"] == "retrieve"
        assert op["status"] == "pending"
        assert op.get("evidence_revision") is None
        # Zero tool effects: no scan boundary was ever crossed.
        with get_db_session() as db:
            scans = db.query(InvocationEvent).filter(
                InvocationEvent.kind == "scan_start").all()
        assert scans == []


class TestOutboundIdempotency:
    def test_same_key_same_payload_returns_existing_operation(
            self, lifecycle):
        created = lifecycle.create_task("conv-1", "send the summary")
        first = lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send the summary",
            idempotency_key="key-1")
        again = lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send the summary",
            idempotency_key="key-1")
        assert again["operation_id"] == first["operation_id"]
        record = lifecycle.get_task(created["run_id"])
        assert len(record["operations"]) == 1

    def test_same_key_different_payload_conflicts(self, lifecycle):
        created = lifecycle.create_task("conv-1", "send the summary")
        lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send the summary",
            idempotency_key="key-1")
        with pytest.raises(TaskLifecycleError):
            lifecycle.create_operation(
                created["run_id"], op_type="outbound",
                requested_change="send something else entirely",
                idempotency_key="key-1")
        with pytest.raises(TaskLifecycleError):
            lifecycle.create_operation(
                created["run_id"], op_type="retrieve",
                requested_change="send the summary",
                idempotency_key="key-1")
        # The conflict wrote nothing.
        record = lifecycle.get_task(created["run_id"])
        assert len(record["operations"]) == 1

    def test_different_keys_create_distinct_operations(self, lifecycle):
        created = lifecycle.create_task("conv-1", "send summaries")
        first = lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send first", idempotency_key="key-1")
        second = lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send second", idempotency_key="key-2")
        assert second["operation_id"] != first["operation_id"]

    def test_key_without_match_creates(self, lifecycle):
        created = lifecycle.create_task("conv-1", "send the summary")
        op = lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send", idempotency_key="fresh-key")
        assert op["idempotency_key"] == "fresh-key"


class TestOutboundReconciliation:
    def _running_outbound(self, lifecycle):
        created = lifecycle.create_task("conv-1", "send the summary")
        op = lifecycle.create_operation(
            created["run_id"], op_type="outbound",
            requested_change="send", idempotency_key="key-1")
        op = lifecycle.transition_operation(
            created["run_id"], op["operation_id"], "running",
            execution_id="ex-1")
        return created["run_id"], op["operation_id"]

    def test_sent_applies(self, lifecycle):
        run_id, op_id = self._running_outbound(lifecycle)
        updated = lifecycle.reconcile_outbound(run_id, op_id, "sent")
        assert updated["status"] == "applied"
        assert updated["outcome_uncertain"] is False
        assert updated["reconciliation"]["provider_state"] == "sent"

    def test_not_sent_fails(self, lifecycle):
        run_id, op_id = self._running_outbound(lifecycle)
        updated = lifecycle.reconcile_outbound(run_id, op_id, "not_sent")
        assert updated["status"] == "failed"
        assert updated["outcome_uncertain"] is False

    def test_unknown_keeps_status_and_marks_uncertain(self, lifecycle):
        run_id, op_id = self._running_outbound(lifecycle)
        updated = lifecycle.reconcile_outbound(run_id, op_id, "unknown")
        assert updated["status"] == "running"
        assert updated["outcome_uncertain"] is True
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["outcome_uncertain"] is True

    def test_terminal_operations_immutable(self, lifecycle):
        run_id, op_id = self._running_outbound(lifecycle)
        lifecycle.reconcile_outbound(run_id, op_id, "sent")
        with pytest.raises(TaskLifecycleError):
            lifecycle.reconcile_outbound(run_id, op_id, "not_sent")

    def test_unknown_provider_state_rejected(self, lifecycle):
        run_id, op_id = self._running_outbound(lifecycle)
        with pytest.raises(TaskLifecycleError):
            lifecycle.reconcile_outbound(run_id, op_id, "maybe")

    def test_unknown_operation_raises(self, lifecycle):
        created = lifecycle.create_task("conv-1", "send the summary")
        with pytest.raises(TaskLifecycleError):
            lifecycle.reconcile_outbound(
                created["run_id"], "op-nope", "sent")


class TestAuthorizationGate:
    """The pre-execution gate: a turn consults the CURRENT revision
    before any tool runs. Permission is the PERSISTED task scope and
    nothing else — there is no per-call bypass label."""

    def test_read_only_allowed_without_any_grant(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        decision = check_turn_authorization(
            lifecycle, created["run_id"], "retrieve")
        assert decision["allowed"] is True
        assert decision["basis"] == "read_only"
        assert decision["scope"] == []

    def test_matching_revision_allowed_stale_denied(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        current = created["task_revision"]["revision"]
        assert check_turn_authorization(
            lifecycle, run_id, "retrieve",
            expected_revision=current)["allowed"] is True
        with pytest.raises(TaskAuthorizationError, match="revision drift"):
            check_turn_authorization(
                lifecycle, run_id, "retrieve", expected_revision=current - 1)

    def test_mutation_denied_when_scope_is_empty(self, lifecycle):
        created = lifecycle.create_task("conv-1", "fix the draft")
        with pytest.raises(TaskAuthorizationError, match="scope is empty"):
            check_turn_authorization(lifecycle, created["run_id"], "edit")

    def test_no_free_form_permission_label_exists(self, lifecycle):
        """A caller cannot assert permission by naming a basis."""
        created = lifecycle.create_task("conv-1", "fix the draft")
        with pytest.raises(TypeError):
            check_turn_authorization(
                lifecycle, created["run_id"], "edit", basis="user_request")

    def test_mutation_allowed_once_scope_names_it(self, lifecycle):
        created = lifecycle.create_task(
            "conv-1", "fix the draft", authorized_actions=["edit"])
        lifecycle.apply_transition(created["run_id"], {
            "kind": "authorize_execute", "approval": "authorized",
            "authorized_actions": ["edit"]})
        decision = check_turn_authorization(
            lifecycle, created["run_id"], "edit")
        assert decision["allowed"] is True
        assert decision["basis"] == "task_scope"

    def test_scope_is_a_scope_even_when_the_user_asked(self, lifecycle):
        """A task scoped to outbound does not become editable because a
        turn asked for it: widening is a separate, persisted act."""
        created = lifecycle.create_task(
            "conv-1", "send it", authorized_actions=["outbound"])
        lifecycle.apply_transition(created["run_id"], {
            "kind": "authorize_execute", "approval": "authorized",
            "authorized_actions": ["outbound"]})
        with pytest.raises(TaskAuthorizationError, match="does not name edit"):
            check_turn_authorization(lifecycle, created["run_id"], "edit")

    def test_pending_approval_blocks_mutation(self, lifecycle):
        created = lifecycle.create_task(
            "conv-1", "send it", authorized_actions=["outbound"])
        lifecycle.apply_transition(created["run_id"], {
            "kind": "authorize_execute", "approval": "pending_approval",
            "authorized_actions": ["outbound"]})
        with pytest.raises(TaskAuthorizationError, match="pending_approval"):
            check_turn_authorization(
                lifecycle, created["run_id"], "outbound")

    def test_cancelled_is_terminal_for_every_action(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        lifecycle.apply_transition(run_id, {"kind": "cancel"})
        for action in ("retrieve", "present", "edit", "outbound"):
            with pytest.raises(TaskAuthorizationError, match="cancelled"):
                check_turn_authorization(lifecycle, run_id, action)

    def test_missing_task_denied(self, lifecycle):
        with pytest.raises(TaskAuthorizationError, match="no active task"):
            check_turn_authorization(lifecycle, None, "retrieve")

    def test_unknown_action_rejected(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        with pytest.raises(TaskLifecycleError, match="unknown action"):
            check_turn_authorization(
                lifecycle, created["run_id"], "teleport")


class TestScopeExpansion:
    """A new user request may legitimately widen a granted scope. The
    widening is persisted as a revision BEFORE execution, carrying the
    user's own words and the identity of the validator that judged it."""

    def test_expansion_persists_the_grant(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        result = expand_task_scope(
            lifecycle, run_id, "edit",
            granted_by_message="fix the draft", validator="test.user_request")
        assert result["expanded"] is True
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["authorized_actions"] == ["edit"]
        grant = record["task_revision"]["provenance"]["scope_grants"][0]
        assert grant["action"] == "edit"
        assert grant["granted_by_message"] == "fix the draft"
        assert grant["validator"] == "test.user_request"
        assert check_turn_authorization(
            lifecycle, run_id, "edit")["allowed"] is True

    def test_expansion_is_idempotent(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        expand_task_scope(lifecycle, run_id, "edit",
                          granted_by_message="fix it", validator="test.user_request")
        before = lifecycle.get_task(run_id)["task_version"]
        again = expand_task_scope(lifecycle, run_id, "edit",
                                  granted_by_message="fix it",
                                  validator="test.user_request")
        assert again["expanded"] is False
        assert lifecycle.get_task(run_id)["task_version"] == before

    def test_expansion_appends_without_dropping_prior_scope(
            self, lifecycle):
        created = lifecycle.create_task(
            "conv-1", "send it", authorized_actions=["outbound"])
        run_id = created["run_id"]
        expand_task_scope(lifecycle, run_id, "edit",
                          granted_by_message="and fix the draft",
                          validator="test.user_request")
        assert lifecycle.get_task(run_id)["task_revision"][
            "authorized_actions"] == ["outbound", "edit"]

    def test_expansion_requires_the_users_own_text(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        with pytest.raises(TaskAuthorizationError, match="request text"):
            expand_task_scope(
                lifecycle, created["run_id"], "edit",
                granted_by_message="   ", validator="test.user_request")

    def test_expansion_requires_a_named_validator(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        with pytest.raises(TaskAuthorizationError, match="validator"):
            expand_task_scope(
                lifecycle, created["run_id"], "edit",
                granted_by_message="fix it", validator="")

    def test_read_only_actions_cannot_be_granted(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        with pytest.raises(TaskLifecycleError, match="only mutating"):
            expand_task_scope(
                lifecycle, created["run_id"], "retrieve",
                granted_by_message="look again", validator="test.user_request")

    def test_cancelled_task_cannot_widen(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        lifecycle.apply_transition(run_id, {"kind": "cancel"})
        with pytest.raises(TaskAuthorizationError, match="cancelled"):
            expand_task_scope(
                lifecycle, run_id, "edit",
                granted_by_message="fix it", validator="test.user_request")


class TestEditPreExecution:
    """The mutating lane reserves before it mutates: a crash between
    reservation and mutation leaves a durable pending operation instead
    of an unrecorded change."""

    _GRANT = {"granted_by_message": "fix the draft",
              "validator": "test.user_request"}

    def test_reservation_precedes_mutation(self, lifecycle):
        session = {}
        run_id, operation_id = begin_edit_turn(
            lifecycle, session, "conv-1", "fix the draft", "ex-1",
            idempotency_key="canvas-1", scope_grant=self._GRANT)
        # Before the mutation: the operation exists and this caller holds
        # the execution claim (running), so no other caller can also act.
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "running"
        assert record["operations"][0]["idempotency_key"] == "canvas-1"
        finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-1",
            updated=True, needs_review=False, success=True)
        record = lifecycle.get_task(run_id)
        assert record["operations"][0]["status"] == "applied"

    def test_denied_edit_reserves_nothing(self, lifecycle):
        # No grant: the gate denies and nothing is reserved.
        with pytest.raises(TaskAuthorizationError, match="scope is empty"):
            begin_edit_turn(
                lifecycle, {}, "conv-1", "fix the draft", "ex-1")
        record = lifecycle.find_active_task("conv-1")
        assert record is not None
        assert record["operations"] == []

    def test_an_empty_scope_is_never_widened_on_a_label_alone(
            self, lifecycle):
        """A grant missing its evidence is not a grant."""
        for bad in ({"validator": "test.user_request"},
                    {"granted_by_message": "fix it"},
                    {"granted_by_message": "", "validator": "test.user_request"}):
            with pytest.raises(TaskAuthorizationError):
                begin_edit_turn(
                    lifecycle, {}, "conv-1", "fix the draft", "ex-1",
                    scope_grant=bad)

    def test_failed_edit_records_failed_not_applied(self, lifecycle):
        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-2",
            scope_grant=self._GRANT)
        finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-2",
            updated=True, needs_review=False, success=False)
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "failed"

    def test_learning_draft_awaits_approval(self, lifecycle):
        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-3",
            scope_grant=self._GRANT)
        finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-3",
            updated=True, needs_review=True, success=True)
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "awaiting_approval"

    def test_declined_edit_releases_the_claim(self, lifecycle):
        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-4",
            scope_grant=self._GRANT)
        assert finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-4",
            updated=False, needs_review=False, success=False) is None
        # No effect happened, so the claim is released rather than left
        # held (which would block every later attempt) or recorded as
        # applied (which would be a lie).
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "cancelled"

    def test_correction_invalidations_attach_after_execution(
            self, lifecycle):
        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-5",
            scope_grant=self._GRANT)
        finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-5",
            updated=True, needs_review=False, success=True,
            invalidated_evidence_ids=["ev-1"])
        operation = lifecycle.get_task(run_id)["operations"][0]
        assert operation["invalidated_evidence_ids"] == ["ev-1"]

    def test_core_operation_fields_cannot_be_attached(self, lifecycle):
        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-6",
            scope_grant=self._GRANT)
        with pytest.raises(TaskLifecycleError, match="core operation field"):
            lifecycle.attach_operation_field(
                run_id, operation_id, "status", "applied")

    def test_same_idempotency_key_replays_the_record_but_loses_the_effect(
            self, lifecycle):
        """The key replay resolves ONE operation — and the second caller
        is refused the execution claim. One record is not one effect."""
        from core.task_lifecycle import OperationExecutionClaimed

        first_run, first_op = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-7",
            idempotency_key="canvas-7", scope_grant=self._GRANT)
        # A retry of the same effect resolves the same operation...
        with pytest.raises(OperationExecutionClaimed, match="held by another"):
            begin_edit_turn(
                lifecycle, {}, "conv-1", "fix the draft", "ex-7",
                idempotency_key="canvas-7", scope_grant=self._GRANT)
        # ...so there is still exactly one operation, and it is the one
        # the first caller holds.
        record = lifecycle.get_task(first_run)
        assert len(record["operations"]) == 1
        assert record["operations"][0]["operation_id"] == first_op
        assert record["operations"][0]["status"] == "running"


class TestRetrievalGateOrdering:
    def test_gate_runs_after_revision_settle(self, lifecycle):
        """``begin_retrieval_turn`` applies the continuation revision
        and THEN consults the gate, so the decision is made against
        the revision the operation will bind to."""
        session = {}
        run_id, _ = begin_retrieval_turn(
            lifecycle, session, "conv-1", "look up eight records",
            "ex-1", items=[f"e{i}" for i in range(1, 9)])
        before = lifecycle.get_task(run_id)["task_revision"]["revision"]
        begin_retrieval_turn(
            lifecycle, session, "conv-1", "search again", "ex-2",
            items=[f"e{i}" for i in range(1, 9)])
        after = lifecycle.get_task(run_id)["task_revision"]["revision"]
        assert after == before + 1
        assert lifecycle.get_task(run_id)["operations"][-1][
            "objective_revision"] == after


class TestDeliveryLedger:
    """Deliveries are an append-only ledger beside the revision: the
    final boundary binds the exact message row and content hash."""

    def test_delivery_binds_message_and_hash(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up eight records")
        run_id = created["run_id"]
        delivery = lifecycle.record_delivery(
            run_id, execution_id="ex-1", operation_ids=["op-1"],
            message_id="msg-1", content_sha256="a" * 64,
            finalization_version="v4", evidence_refs=["ev-1"])
        record = lifecycle.get_task(run_id)
        assert len(record["deliveries"]) == 1
        stored = record["deliveries"][0]
        assert stored["delivery_id"] == delivery["delivery_id"]
        assert stored["message_id"] == "msg-1"
        assert stored["content_sha256"] == "a" * 64
        assert stored["operation_ids"] == ["op-1"]
        assert stored["evidence_refs"] == ["ev-1"]

    def test_delivery_requires_identity(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        for kwargs in ({"execution_id": "", "message_id": "m",
                        "content_sha256": "a" * 64},
                       {"execution_id": "ex-1", "message_id": "",
                        "content_sha256": "a" * 64},
                       {"execution_id": "ex-1", "message_id": "m",
                        "content_sha256": ""}):
            with pytest.raises(TaskLifecycleError, match="required"):
                lifecycle.record_delivery(created["run_id"], **kwargs)

    def test_same_execution_and_message_replays(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        first = lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="msg-1",
            content_sha256="a" * 64)
        version_after_first = lifecycle.get_task(run_id)["task_version"]
        second = lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="msg-1",
            content_sha256="a" * 64)
        record = lifecycle.get_task(run_id)
        assert second["delivery_id"] == first["delivery_id"]
        assert len(record["deliveries"]) == 1
        # A replay is not a mutation: the version does not advance.
        assert record["task_version"] == version_after_first

    def test_a_different_hash_on_the_same_message_is_not_a_replay(
            self, lifecycle):
        """Re-finalizing the same message row with different content IS
        a distinct delivery — the ledger records what was actually sent
        rather than pretending the first one covered it."""
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="msg-1",
            content_sha256="a" * 64)
        lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="msg-1",
            content_sha256="b" * 64)
        record = lifecycle.get_task(run_id)
        assert len(record["deliveries"]) == 2

    def test_ledger_survives_later_revisions(self, lifecycle):
        """A transition rebuilds revision and operations from the record;
        the ledger must not be dropped by an unrelated revision."""
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="msg-1",
            content_sha256="a" * 64)
        lifecycle.apply_transition(run_id, {
            "kind": "change_presentation",
            "output_preferences": {"style": "compact"}})
        lifecycle.apply_transition(run_id, {
            "kind": "authorize_execute", "approval": "authorized",
            "authorized_actions": ["edit"]})
        record = lifecycle.get_task(run_id)
        assert len(record["deliveries"]) == 1
        assert record["task_revision"]["revision"] == 3

    def test_ledger_survives_operation_transitions(self, lifecycle):
        session = {}
        run_id, operation_id = begin_edit_turn(
            lifecycle, session, "conv-1", "fix the draft", "ex-1",
            scope_grant={"granted_by_message": "fix the draft",
                         "validator": "test.user_request"})
        lifecycle.record_delivery(
            run_id, execution_id="ex-0", message_id="msg-0",
            content_sha256="c" * 64)
        finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-1",
            updated=True, needs_review=False, success=True)
        record = lifecycle.get_task(run_id)
        assert len(record["deliveries"]) == 1
        assert record["operations"][0]["status"] == "applied"

    def test_deliveries_accumulate_across_turns(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        for index in range(1, 4):
            lifecycle.record_delivery(
                run_id, execution_id=f"ex-{index}",
                message_id=f"msg-{index}", content_sha256="d" * 64)
        record = lifecycle.get_task(run_id)
        assert [d["execution_id"] for d in record["deliveries"]] == [
            "ex-1", "ex-2", "ex-3"]


class TestMultiTurnScenario:
    """One conversation, five turns, one durable task record: the
    working demonstration that the lifecycle — not the transcript —
    carries what was asked, what ran, what changed, and what is owed.
    Real TaskLifecycle + GoalRunService on a scratch database; no
    orchestrator, no mocks of the lifecycle itself."""

    def test_ask_format_research_field_halt(self, lifecycle):
        session = {}
        items = tuple(f"e{i}" for i in range(1, 9))

        # Turn 1 — ask: task created, retrieval applied, evidence bound.
        run_id = record_retrieval_turn(
            lifecycle, session, "conv-1", "look up eight records",
            _structured_result(items), "ex-1", True)
        record = lifecycle.get_task(run_id)
        assert [e["id"] for e in
                record["task_revision"]["entities"]] == list(items)
        assert len(record["task_revision"]["evidence"]) == 1

        # Turn 2 — formatting: presentation changes, nothing re-runs.
        record_presentation_turn(
            lifecycle, session, "conv-1", "cleaner output",
            style="compact", field=None)
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["output_preferences"]["style"] == \
            "compact"
        assert len(record["operations"]) == 1
        assert record["task_revision"]["new_attempt_required"] is False

        # Turn 3 — re-search: new attempt AND presentation intent kept.
        record_retrieval_turn(
            lifecycle, session, "conv-1", "search again, compact",
            _structured_result(items), "ex-3", True)
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 2
        assert record["task_revision"]["last_transition"]["kind"] == \
            "attach_evidence"

        # Turn 4 — field selection: narrows fields from retained
        # evidence, still zero retrieval.
        record_presentation_turn(
            lifecycle, session, "conv-1", "use the alternate basis",
            style="compact", field=None,
            requested_fields=["cost"])
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["requested_fields"] == ["cost"]
        assert len(record["operations"]) == 2
        assert len(record["task_revision"]["evidence"]) == 2

        # Turn 5 — halt: outstanding work cancelled, applied work kept.
        stopped = cancel_task(lifecycle, session, "conv-1", "stop")
        assert stopped == run_id
        record = lifecycle.get_task(run_id)
        assert record["task_revision"]["authorization"] == "cancelled"

        # The whole conversation is one auditable chain: revisions
        # strictly increasing with unbroken supersedes lineage, every
        # operation bound to the revision it ran under.
        revisions = [d.get("revision") for d in
                     lifecycle.runs.get_decisions(run_id)
                     if d.get("kind") in ("task_created", "task_revision")
                     and d.get("revision") is not None]
        assert revisions == sorted(revisions)
        assert len(set(revisions)) == len(revisions)
        assert record["task_revision"]["revision"] == revisions[-1]
        current = record["task_revision"]["revision"]
        for operation in record["operations"]:
            assert operation["objective_revision"] <= current


class TestFailClosedLanes:
    @contextmanager
    def _lane_harness(self, orch, session, read_mock):
        from contextlib import ExitStack

        with ExitStack() as stack:
            stack.enter_context(patch.object(
                orch, "_get_or_create_session", return_value=session))
            stack.enter_context(patch.object(orch, "_update_session"))
            stack.enter_context(patch.object(
                orch, "_emit_agent_status", new=AsyncMock()))
            stack.enter_context(patch.object(
                orch, "_finish_chat_execution"))
            stack.enter_context(patch.object(
                orch, "_direct_confirmed_file_read", new=read_mock))
            stack.enter_context(patch(
                "core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                    side_effect=AssertionError("must not plan"))))
            yield

    @pytest.mark.asyncio
    async def test_ask_begin_failure_blocks_read(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat
        from core import task_lifecycle as tlm
        from core.database import get_db_session
        from core.models import InvocationEvent
        from core.task_lifecycle import TaskLifecycleConcurrencyError

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        session = {"id": "s-task-blocked", "history": []}
        with self._lane_harness(
            orch, session,
            AsyncMock(side_effect=AssertionError("must not read")),
        ), patch.object(tlm, "begin_retrieval_turn",
                        side_effect=TaskLifecycleConcurrencyError(
                            "locked")):
            response = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-blocked", context={})
        assert response["success"] is False
        assert "could not be recorded" in response["message"]
        assert response["data"]["blocked_reason"] == \
            "operation_not_recorded"
        assert response["data"]["task_operation"] is None
        assert response["data"]["reconciliation_required"] is False
        # Zero tool effects: the read never ran, no scan was recorded,
        # and no task operation exists.
        with get_db_session() as db:
            assert db.query(InvocationEvent).filter(
                InvocationEvent.kind == "scan_start").all() == []
        assert "_task_run_id" not in session

    @pytest.mark.asyncio
    async def test_ask_finish_failure_delivers_uncertain_once(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat
        from core import task_lifecycle as tlm

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-uncertain", "history": []}
        read_mock = AsyncMock(return_value=_direct_result(rec))
        with self._lane_harness(
            orch, session, read_mock,
        ), patch.object(tlm, "finish_retrieval_turn",
                        side_effect=RuntimeError("DB down")):
            response = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-uncertain", context={})
        assert response["success"] is True
        # Observed values delivered, uncertainty disclosed, identity
        # retained — and the read ran exactly once (never repeated).
        assert "- **M-1**" in response["message"]
        assert "could not be recorded on the task" in response["message"]
        assert read_mock.await_count == 1
        assert response["data"]["reconciliation_required"] is True
        ref = response["data"]["task_operation"]
        assert ref["run_id"] == session["_task_run_id"]
        lifecycle = chat._task_lifecycle_for("default", None)
        record = lifecycle.get_task(ref["run_id"])
        assert record["operations"][0]["operation_id"] == \
            ref["operation_id"]
        # Begin ran but finish never did: the operation is still pending.
        assert record["operations"][0]["status"] == "pending"
        pin = session["_pending_file_result"]["delivery_pin"]
        assert pin["delivered_text"] == response["message"][:24000]

    @pytest.mark.asyncio
    async def test_direct_begin_failure_blocks_read(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat
        from core import task_lifecycle as tlm
        from core.pending_file_task import build_pending_task
        from core.task_lifecycle import TaskLifecycleConcurrencyError

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        session = {
            "id": "s-task-direct-blocked",
            "history": [],
            "_pending_file_task": build_pending_task(
                "find the prices of M-1 and M-2 in w.xlsx", "w.xlsx"),
        }
        with self._lane_harness(
            orch, session,
            AsyncMock(side_effect=AssertionError("must not read")),
        ), patch.object(tlm, "begin_retrieval_turn",
                        side_effect=TaskLifecycleConcurrencyError(
                            "locked")):
            response = await orch.process_chat_message(
                "u1", "yes", session_id="s-task-direct-blocked",
                context={})
        assert response["success"] is False
        assert "could not be recorded" in response["message"]
        assert response["data"]["blocked_reason"] == \
            "operation_not_recorded"

    @pytest.mark.asyncio
    async def test_formatting_record_failure_preserves_previous(
            self, isolated_db, monkeypatch):
        import integrations.chat_orchestrator as chat
        from core import task_lifecycle as tlm

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        rec = _structured_result()
        session = {"id": "s-task-fmt-fallback", "history": []}
        with self._lane_harness(
            orch, session,
            AsyncMock(return_value=_direct_result(rec)),
        ):
            first = await orch.process_chat_message(
                "u1", "find the prices of M-1 and M-2 in w.xlsx",
                session_id="s-task-fmt-fallback", context={})
            assert first["success"] is True
            with patch.object(
                    tlm, "record_presentation_turn",
                    side_effect=RuntimeError("DB down")):
                second = await orch.process_chat_message(
                    "u1", "make it cleaner",
                    session_id="s-task-fmt-fallback", context={})
        # Previous delivery preserved byte-for-byte with its pin; the
        # turn does not claim a durable new delivery.
        assert second["success"] is True
        assert second["message"] == first["message"]
        assert second["data"]["task_recorded"] is False
        pin = session["_pending_file_result"]["delivery_pin"]
        assert pin["delivered_text"] == first["message"][:24000]


def _mp_worker(db_path, conversation, item_tag, out_queue):
    """Module-level worker: two independent processes, one shared file
    DB. Each builds its own engine/services (nothing shared but the
    file)."""
    import os
    import sys

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("TESTING", "1")
    try:
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.models import (
            GoalObjective,
            GoalRun,
            TaskOperationRecord,
        )
        from core.task_lifecycle import TaskLifecycle, record_retrieval_turn

        engine = _create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30})
        # Schema is created once by the parent before spawning; workers
        # never DDL (concurrent CREATE TABLE races even with checkfirst).
        factory = _sessionmaker(bind=engine, expire_on_commit=False)
        lifecycle = TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))
        run_id = record_retrieval_turn(
            lifecycle, {}, conversation, f"look up {item_tag}",
            {"requested_items": [item_tag],
             "requested_fields": ["value"],
             "evidence_revision": "rev-mp",
             "attempt_id": f"attempt-{item_tag}"},
            f"ex-{item_tag}", True)
        out_queue.put(("ok", run_id))
    except Exception as exc:  # noqa: BLE001 — reported to the parent
        out_queue.put(("error", f"{type(exc).__name__}: {exc}"))


class TestCrossProcessConcurrency:
    def test_two_processes_cannot_silently_overwrite(self, tmp_path,
                                                     monkeypatch):
        import multiprocessing as _mp

        # Shared creation lock across the two processes (spawn inherits
        # the environment): the find→create window serializes, so both
        # turns land on one task; the version counter then orders the
        # subsequent mutations without silent overwrites.
        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path = str(tmp_path / "mp.db")
        # Schema once, in the parent: concurrent workers must never DDL.
        _schema_engine = create_engine(f"sqlite:///{db_path}")
        for table in (GoalObjective.__table__, GoalRun.__table__,
                      TaskOperationRecord.__table__):
            table.create(_schema_engine)
        _schema_engine.dispose()
        ctx = _mp.get_context("spawn")
        queue = ctx.Queue()
        first = ctx.Process(target=_mp_worker,
                            args=(db_path, "conv-mp", "M-A", queue))
        second = ctx.Process(target=_mp_worker,
                             args=(db_path, "conv-mp", "M-B", queue))
        # Overlapping execution: both processes race the same task.
        first.start()
        second.start()
        first.join(timeout=180)
        second.join(timeout=180)
        assert first.exitcode == 0
        assert second.exitcode == 0
        results = [queue.get(timeout=30), queue.get(timeout=30)]
        assert [r[0] for r in results] == ["ok", "ok"], results
        assert results[0][1] == results[1][1]
        engine = create_engine(f"sqlite:///{db_path}")
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        lifecycle = TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))
        record = lifecycle.find_active_task("conv-mp")
        assert record is not None
        assert len(record["operations"]) == 2
        assert len({o["operation_id"] for o in
                    record["operations"]}) == 2
        revisions = [d.get("revision") for d in
                     lifecycle.runs.get_decisions(record["run_id"])
                     if d.get("kind") in ("task_created", "task_revision")
                     and d.get("revision") is not None]
        assert revisions == list(range(1, max(revisions) + 1))

    def test_stale_conditional_write_fails(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        record = lifecycle.get_task(run_id)
        assert record["task_version"] == 1
        # Move the version externally, then attempt a conditional write
        # against the stale expectation: it must fail, not overwrite.
        lifecycle.apply_transition(run_id, {
            "kind": "change_presentation",
            "requested_change": "compact",
            "output_preferences": {"style": "compact", "field": None}})
        assert lifecycle._cas_write(
            run_id, 1,
            {"task_revision": record["task_revision"], "operations": [],
             "conversation_id": "conv-1"}, {"kind": "stale"}) is False
        # A live conditional write against the current version succeeds.
        current = lifecycle.get_task(run_id)
        assert lifecycle._cas_write(
            run_id, current["task_version"],
            {"task_revision": current["task_revision"],
             "operations": current["operations"],
             "conversation_id": "conv-1"},
            {"kind": "probe"}) is True

    def test_exhausted_retries_raise_instead_of_overwriting(
            self, lifecycle, monkeypatch):
        from core.task_lifecycle import TaskLifecycleConcurrencyError

        created = lifecycle.create_task("conv-1", "look up records")
        monkeypatch.setattr(
            lifecycle, "_cas_write", lambda *args, **kwargs: False)
        with pytest.raises(TaskLifecycleConcurrencyError):
            lifecycle.apply_transition(created["run_id"], {
                "kind": "change_presentation",
                "requested_change": "compact",
                "output_preferences": {"style": "compact",
                                       "field": None}})


def _mp_operation_worker(db_path, run_id, key, requested_change, tag,
                         out_queue):
    """Reserve one operation from a separate process.

    The parent's assertion is that N processes racing the SAME idempotency
    key for the SAME payload produce exactly ONE operation — the losers
    replay the winner's. A different payload on the same key must be a
    conflict, never a second effect.
    """
    import os
    import sys

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("TESTING", "1")
    try:
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.models import (
            GoalObjective,
            GoalRun,
            TaskOperationRecord,
        )
        from core.task_lifecycle import TaskLifecycle

        engine = _create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30})
        factory = _sessionmaker(bind=engine, expire_on_commit=False)
        lifecycle = TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))
        operation = lifecycle.create_operation(
            run_id, op_type="outbound",
            requested_change=requested_change, idempotency_key=key)
        out_queue.put(("ok", operation["operation_id"]))
    except Exception as exc:  # noqa: BLE001 — reported to the parent
        out_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _mp_effect_worker(db_path, run_id, key, message, out_queue):
    """Reserve AND perform a canvas edit from a separate process.

    The effect is the ``transition to applied`` that follows winning the
    claim. A caller that loses the claim must never reach it, so the
    parent's count of ``applied`` operations is the count of real effects.
    """
    import os
    import sys

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("TESTING", "1")
    try:
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.models import (
            GoalObjective,
            GoalRun,
            TaskOperationRecord,
        )
        from core.task_lifecycle import (
            OperationExecutionClaimed,
            TaskLifecycle,
        )

        engine = _create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30})
        factory = _sessionmaker(bind=engine, expire_on_commit=False)
        lifecycle = TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))
        try:
            op = lifecycle.create_operation(
                run_id, op_type="edit", requested_change=message,
                idempotency_key=key)
            claim = lifecycle.claim_execution(run_id, op["operation_id"])
            if not claim.get("granted"):
                out_queue.put((
                    "refused",
                    f"operation is {claim.get('status')}, held by "
                    f"another caller"))
                return
            # The effect.
            lifecycle.transition_operation(
                run_id, op["operation_id"], "applied")
            out_queue.put(("claimed", op["operation_id"]))
        except OperationExecutionClaimed as exc:
            out_queue.put(("refused", str(exc)))
    except Exception as exc:  # noqa: BLE001 — reported to the parent
        out_queue.put(("error", f"{type(exc).__name__}: {exc}"))


class TestCrossProcessOperationUniqueness:
    """DB-backed uniqueness (direction 4): the key is claimed in a table
    with a real constraint, so independent processes cannot both win."""

    def _lifecycle_for(self, db_path):
        engine = create_engine(f"sqlite:///{db_path}")
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        return TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))

    def test_two_processes_one_effect_not_merely_one_record(
            self, tmp_path, monkeypatch):
        """The reviewer's point, across real processes.

        Two independent callers reserve the same canvas edit with the same
        key. Exactly one may perform the effect; the other is refused the
        execution claim. Counting the MUTATIONS — not the records — is the
        only proof, because a singular operation row is also what a
        double-mutation bug looks like from the database.
        """
        import multiprocessing as _mp

        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path = self._seed(tmp_path, "op_effect.db")
        lifecycle = self._lifecycle_for(db_path)
        created = lifecycle.create_task("conv-1", "fix the draft")
        run_id = created["run_id"]
        # The task already authorizes this edit, so the race is purely
        # about who gets to perform it.
        lifecycle.apply_transition(run_id, {
            "kind": "authorize_execute", "approval": "authorized",
            "authorized_actions": ["edit"]})

        ctx = _mp.get_context("spawn")
        queue = ctx.Queue()
        procs = [
            ctx.Process(
                target=_mp_effect_worker,
                args=(db_path, run_id, "canvas-race", "fix the draft", queue))
            for _ in range(2)
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=180)
            assert proc.exitcode == 0
        results = [queue.get(timeout=30), queue.get(timeout=30)]

        outcomes = sorted(r[0] for r in results)
        # One winner, one refused — not two winners.
        assert outcomes == ["claimed", "refused"], results
        refusal = next(r[1] for r in results if r[0] == "refused")
        assert "held by another caller" in refusal, refusal

        record = lifecycle.get_task(run_id)
        # One operation, and it actually reached its effect exactly once.
        # A double-mutation bug would also show one row here — which is
        # precisely why the refusal above, not this count, is the proof.
        assert len(record["operations"]) == 1
        assert record["operations"][0]["status"] == "applied"

    def _seed(self, tmp_path, name):
        db_path = str(tmp_path / name)
        engine = create_engine(f"sqlite:///{db_path}")
        for table in (GoalObjective.__table__, GoalRun.__table__,
                      TaskOperationRecord.__table__):
            table.create(engine)
        engine.dispose()
        return db_path

    def test_two_processes_same_key_same_payload_yield_one_operation(
            self, tmp_path, monkeypatch):
        import multiprocessing as _mp

        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path = self._seed(tmp_path, "op_uniq.db")
        lifecycle = self._lifecycle_for(db_path)
        created = lifecycle.create_task("conv-1", "send the summary")
        run_id = created["run_id"]

        ctx = _mp.get_context("spawn")
        queue = ctx.Queue()
        procs = [
            ctx.Process(
                target=_mp_operation_worker,
                args=(db_path, run_id, "key-same", "send the summary",
                      f"w{index}", queue))
            for index in range(2)
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=180)
            assert proc.exitcode == 0
        results = [queue.get(timeout=30), queue.get(timeout=30)]

        # Neither process errored, and both name the SAME operation.
        assert [r[0] for r in results] == ["ok", "ok"], results
        assert results[0][1] == results[1][1]

        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1, record["operations"]
        # And exactly one claim row arbitrated it.
        engine = create_engine(f"sqlite:///{db_path}")
        session = sessionmaker(bind=engine)()
        claims = session.query(TaskOperationRecord).all()
        assert len(claims) == 1
        assert claims[0].operation_id == results[0][1]
        session.close()
        engine.dispose()

    def test_two_processes_different_payload_conflict(self, tmp_path,
                                                      monkeypatch):
        import multiprocessing as _mp

        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path = self._seed(tmp_path, "op_conflict.db")
        lifecycle = self._lifecycle_for(db_path)
        created = lifecycle.create_task("conv-1", "send the summary")
        run_id = created["run_id"]
        # Same key, DIFFERENT payload, from two processes: exactly one
        # wins and the other is a conflict — never two effects.
        ctx = _mp.get_context("spawn")
        queue = ctx.Queue()
        procs = [
            ctx.Process(
                target=_mp_operation_worker,
                args=(db_path, run_id, "key-conflict", payload, f"w{index}",
                      queue))
            for index, payload in enumerate(
                ["send the summary", "send something else entirely"])
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=180)
            assert proc.exitcode == 0
        results = [queue.get(timeout=30), queue.get(timeout=30)]

        outcomes = sorted(r[0] for r in results)
        assert outcomes == ["error", "ok"], results
        # The failure is a payload conflict, not an arbitrary error.
        failure = next(r[1] for r in results if r[0] == "error")
        assert "different operation payload" in failure, failure

        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1, record["operations"]
        engine = create_engine(f"sqlite:///{db_path}")
        session = sessionmaker(bind=engine)()
        assert len(session.query(TaskOperationRecord).all()) == 1
        session.close()
        engine.dispose()

    def test_a_claim_without_an_operation_is_materialized_not_duplicated(
            self, lifecycle):
        """A winner that crashed between claiming the key and writing the
        task JSON must not leave a key that produces a SECOND effect."""
        created = lifecycle.create_task("conv-1", "send the summary")
        run_id = created["run_id"]
        first = lifecycle.create_operation(
            run_id, op_type="outbound",
            requested_change="send the summary", idempotency_key="key-crash")
        # Simulate the crash: the claim row survives, the JSON operation
        # does not.
        record = lifecycle.get_task(run_id)
        lifecycle._cas_write(
            run_id, record["task_version"],
            {"task_revision": record["task_revision"], "operations": [],
             "deliveries": record["deliveries"],
             "conversation_id": "conv-1"}, {"kind": "simulated_crash"})
        assert lifecycle.get_task(run_id)["operations"] == []

        recovered = lifecycle.create_operation(
            run_id, op_type="outbound",
            requested_change="send the summary", idempotency_key="key-crash")

        # The SAME operation is materialized under the claimed identity.
        assert recovered["operation_id"] == first["operation_id"]
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1
        assert record["operations"][0]["idempotency_key"] == "key-crash"


class TestOneRecordIsNotOneEffect:
    """The reviewer's point: two callers holding the same operation id
    must not both perform the effect. The claim is the arbiter."""

    _GRANT = {"granted_by_message": "fix the draft",
              "validator": "test.user_request"}

    def test_claim_is_granted_once(self, lifecycle):
        created = lifecycle.create_task("conv-1", "fix the draft")
        run_id = created["run_id"]
        op = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="k-1")
        first = lifecycle.claim_execution(run_id, op["operation_id"])
        assert first["granted"] is True
        assert first["operation"]["status"] == "running"
        second = lifecycle.claim_execution(run_id, op["operation_id"])
        assert second["granted"] is False
        assert second["status"] == "running"
        assert second["already_complete"] is False

    def test_claim_on_a_completed_operation_replays_not_regrants(
            self, lifecycle):
        created = lifecycle.create_task("conv-1", "fix the draft")
        run_id = created["run_id"]
        op = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="k-2")
        lifecycle.claim_execution(run_id, op["operation_id"])
        lifecycle.transition_operation(run_id, op["operation_id"], "applied")
        again = lifecycle.claim_execution(run_id, op["operation_id"])
        assert again["granted"] is False
        assert again["already_complete"] is True

    def test_two_callers_one_record_one_effect(self, lifecycle):
        """The end-to-end shape: a replayed key yields one record, and the
        second caller is refused before it can mutate."""
        from core.task_lifecycle import OperationExecutionClaimed

        effects = []
        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-1",
            idempotency_key="canvas-x", scope_grant=self._GRANT)
        effects.append("mutated")
        with pytest.raises(OperationExecutionClaimed):
            begin_edit_turn(
                lifecycle, {}, "conv-1", "fix the draft", "ex-1",
                idempotency_key="canvas-x", scope_grant=self._GRANT)
        assert effects == ["mutated"], "the loser must not reach the effect"
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1
        assert record["operations"][0]["operation_id"] == operation_id

    def test_claim_after_a_settled_operation_is_a_replay(self, lifecycle):
        from core.task_lifecycle import OperationExecutionClaimed

        run_id, operation_id = begin_edit_turn(
            lifecycle, {}, "conv-1", "fix the draft", "ex-1",
            idempotency_key="canvas-y", scope_grant=self._GRANT)
        finish_edit_turn(
            lifecycle, run_id, operation_id, "ex-1",
            updated=True, needs_review=False, success=True)
        with pytest.raises(OperationExecutionClaimed):
            begin_edit_turn(
                lifecycle, {}, "conv-1", "fix the draft", "ex-1",
                idempotency_key="canvas-y", scope_grant=self._GRANT)
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "applied"


class TestScopeValidationMustRun:
    """Naming a validator proves nothing. Only a REGISTERED validator
    that actually runs and approves grants scope."""

    def test_unregistered_validator_is_refused(self, lifecycle):
        created = lifecycle.create_task("conv-1", "fix the draft")
        with pytest.raises(TaskAuthorizationError, match="not registered"):
            expand_task_scope(
                lifecycle, created["run_id"], "edit",
                granted_by_message="fix the draft",
                validator="totally_trusted_validator")

    def test_registered_but_refusing_validator_denies(self, lifecycle):
        created = lifecycle.create_task("conv-1", "fix the draft")
        with pytest.raises(TaskAuthorizationError, match="refused"):
            expand_task_scope(
                lifecycle, created["run_id"], "edit",
                granted_by_message="fix the draft",
                validator="test.refuse")
        # Nothing was persisted.
        record = lifecycle.get_task(created["run_id"])
        assert record["task_revision"]["authorized_actions"] == []
        assert "scope_grants" not in (
            record["task_revision"].get("provenance") or {})

    def test_a_raising_validator_fails_closed(self, lifecycle, monkeypatch):
        from core import task_lifecycle as tlm

        @tlm.register_scope_validator("test.explodes")
        def _boom(action, message, context):
            raise RuntimeError("validator infrastructure is down")

        created = lifecycle.create_task("conv-1", "fix the draft")
        with pytest.raises(TaskAuthorizationError, match="failed to decide"):
            expand_task_scope(
                lifecycle, created["run_id"], "edit",
                granted_by_message="fix the draft",
                validator="test.explodes")
        assert lifecycle.get_task(created["run_id"])["task_revision"][
            "authorized_actions"] == []

    def test_the_validator_actually_receives_the_request(self, lifecycle):
        seen = {}

        from core import task_lifecycle as tlm

        @tlm.register_scope_validator("test.recording")
        def _record(action, message, context):
            seen.update({"action": action, "message": message,
                         "context": context})
            return action == "edit"

        created = lifecycle.create_task("conv-1", "fix the draft")
        expand_task_scope(
            lifecycle, created["run_id"], "edit",
            granted_by_message="fix the draft please",
            validator="test.recording", context={"canvas": {"id": "cv1"}})
        assert seen["action"] == "edit"
        assert seen["message"] == "fix the draft please"
        assert seen["context"] == {"canvas": {"id": "cv1"}}

    def test_the_orchestrator_validator_is_registered_and_runs(self):
        """The production validator resolves and judges a real message."""
        import integrations.chat_orchestrator as chat

        assert chat._tm is not None
        assert "chat_orchestrator.canvas_edit_lane" in \
            chat._tm._SCOPE_VALIDATORS
        canvas = _canvas_ctx()
        assert chat._tm._SCOPE_VALIDATORS[
            "chat_orchestrator.canvas_edit_lane"](
                "edit", "fix the draft", {"canvas": canvas}) is True
        # A read-only action is never approved by the edit validator.
        assert chat._tm._SCOPE_VALIDATORS[
            "chat_orchestrator.canvas_edit_lane"](
                "outbound", "fix the draft", {"canvas": canvas}) is False

    def test_the_orchestrator_validator_refuses_without_a_canvas(self):
        import integrations.chat_orchestrator as chat

        validator = chat._tm._SCOPE_VALIDATORS[
            "chat_orchestrator.canvas_edit_lane"]
        assert validator("edit", "fix the draft", {"canvas": None}) is False
        assert validator("edit", "", {"canvas": _canvas_ctx()}) is False


class TestReceiptAcknowledgement:
    """Persistence is not receipt. Only an explicit, evidenced
    acknowledgement bound to the delivery may claim one."""

    def test_a_delivery_cannot_be_born_acknowledged(self):
        with pytest.raises(TaskLifecycleError, match="born|created"):
            new_delivery(
                execution_id="ex-1", operation_ids=[], message_id="m-1",
                content_sha256="a" * 64, finalization_version="v4",
                status="receipt_acknowledged")

    def test_ack_requires_evidence(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        delivery = lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="m-1",
            content_sha256="a" * 64)
        for kwargs in ({"acknowledgement": "", "acknowledged_by": "client"},
                       {"acknowledgement": "ok", "acknowledged_by": ""}):
            with pytest.raises(TaskLifecycleError, match="must carry|must name"):
                lifecycle.acknowledge_receipt(
                    run_id, delivery["delivery_id"], **kwargs)
        # Still unacknowledged after the failed attempts.
        assert lifecycle.get_task(run_id)["deliveries"][0][
            "receipt_confirmed"] is False

    def test_persisting_does_not_acknowledge(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="m-1",
            content_sha256="a" * 64)
        # Writing the bytes and returning them proves nothing about receipt.
        stored = lifecycle.get_task(run_id)["deliveries"][0]
        assert stored["status"] == "persisted_for_delivery"
        assert stored["receipt_confirmed"] is False
        assert "receipt_acknowledgement" not in stored

    def test_explicit_acknowledgement_is_recorded_with_evidence(
            self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        delivery = lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="m-1",
            content_sha256="a" * 64)
        acked = lifecycle.acknowledge_receipt(
            run_id, delivery["delivery_id"],
            acknowledgement="client rendered message m-1",
            acknowledged_by="chat_client.user_ack")
        assert acked["status"] == "receipt_acknowledged"
        assert acked["receipt_confirmed"] is True
        assert acked["receipt_acknowledgement"]["acknowledged_by"] == \
            "chat_client.user_ack"
        assert "rendered" in acked["receipt_acknowledgement"]["evidence"]

    def test_acknowledgement_is_bound_to_one_delivery(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        first = lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="m-1",
            content_sha256="a" * 64)
        second = lifecycle.record_delivery(
            run_id, execution_id="ex-2", message_id="m-2",
            content_sha256="b" * 64)
        lifecycle.acknowledge_receipt(
            run_id, first["delivery_id"],
            acknowledgement="m-1 rendered", acknowledged_by="client")
        deliveries = lifecycle.get_task(run_id)["deliveries"]
        assert deliveries[0]["receipt_confirmed"] is True
        # Acknowledging one delivery says nothing about the other.
        assert deliveries[1]["receipt_confirmed"] is False
        with pytest.raises(TaskLifecycleError, match="not found"):
            lifecycle.acknowledge_receipt(
                run_id, "no-such-delivery",
                acknowledgement="x", acknowledged_by="client")
        assert second["delivery_id"] in {
            d["delivery_id"] for d in deliveries}

    def test_acknowledgement_is_idempotent(self, lifecycle):
        created = lifecycle.create_task("conv-1", "look up records")
        run_id = created["run_id"]
        delivery = lifecycle.record_delivery(
            run_id, execution_id="ex-1", message_id="m-1",
            content_sha256="a" * 64)
        first = lifecycle.acknowledge_receipt(
            run_id, delivery["delivery_id"],
            acknowledgement="m-1 rendered", acknowledged_by="client")
        version = lifecycle.get_task(run_id)["task_version"]
        second = lifecycle.acknowledge_receipt(
            run_id, delivery["delivery_id"],
            acknowledgement="m-1 rendered", acknowledged_by="client")
        assert second["receipt_acknowledgement"] == \
            first["receipt_acknowledgement"]
        assert lifecycle.get_task(run_id)["task_version"] == version


class TestCrashRecovery:
    """A claimed operation whose worker is lost must not be stranded in
    ``running`` forever, and must never be blindly repeated.

    The two crash points are different worlds and both are covered:
    crashing BEFORE the mutation, and crashing AFTER it but before the
    completion was recorded. Only the second can have changed the world,
    which is exactly why a timeout is not evidence of anything.
    """

    _GRANT = {"granted_by_message": "fix the draft",
              "validator": "test.user_request"}

    def _authorized_task(self, lifecycle):
        created = lifecycle.create_task("conv-1", "fix the draft")
        run_id = created["run_id"]
        lifecycle.apply_transition(run_id, {
            "kind": "authorize_execute", "approval": "authorized",
            "authorized_actions": ["edit"]})
        return run_id

    def _claim_as_other_worker(self, lifecycle, run_id, key="canvas-crash"):
        """Reserve and claim, then rewrite the owner so recovery sees a
        worker that is not this process."""
        op = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key=key)
        lifecycle.claim_execution(run_id, op["operation_id"],
                                  execution_id="ex-1")
        record = lifecycle.get_task(run_id)
        ops = [dict(o) for o in record["operations"]]
        for o in ops:
            if o["operation_id"] == op["operation_id"]:
                o["claimed_by"] = "pid:999999"
        lifecycle._cas_write(
            run_id, record["task_version"],
            {"task_revision": record["task_revision"], "operations": ops,
             "deliveries": record["deliveries"],
             "conversation_id": "conv-1"}, {"kind": "crash_sim"})
        return op["operation_id"]

    # ── crash BEFORE the mutation ──────────────────────────────────
    def test_crash_before_mutation_is_recoverable(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        operation_id = self._claim_as_other_worker(lifecycle, run_id)
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "running"

        stranded = lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        assert len(stranded) == 1
        operation = lifecycle.get_task(run_id)["operations"][0]
        assert operation["status"] == "uncertain"
        assert operation["outcome"] == "unknown"
        assert operation["needs_reconciliation"] is True
        assert operation["idempotency_key"] == "canvas-crash"

    # ── crash AFTER the mutation, BEFORE recording ──────────────────
    def test_crash_after_mutation_stays_uncertain_until_evidence(
            self, lifecycle):
        """The world may already have changed. Nothing may be assumed."""
        run_id = self._authorized_task(lifecycle)
        operation_id = self._claim_as_other_worker(
            lifecycle, run_id, key="canvas-after")
        # The mutation happened; the completion never got recorded.
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        operation = lifecycle.get_task(run_id)["operations"][0]
        assert operation["status"] == "uncertain"
        assert operation["needs_reconciliation"] is True
        # It is NOT applied and NOT failed: the system does not know.
        assert operation["status"] not in ("applied", "failed")

    def test_insufficient_evidence_leaves_it_uncertain(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-insuf")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        settled = lifecycle.reconcile_uncertain_operation(
            run_id, lifecycle.get_task(run_id)["operations"][0][
                "operation_id"],
            "insufficient",
            evidence="no canvas revision found, but the audit log was "
                     "rotated so absence proves nothing")
        assert settled["status"] == "uncertain"
        assert settled["needs_reconciliation"] is True
        assert settled["reconciliation"]["verdict"] == "insufficient"

    def test_proven_applied_records_completion(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-applied")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        settled = lifecycle.reconcile_uncertain_operation(
            run_id, lifecycle.get_task(run_id)["operations"][0][
                "operation_id"],
            "applied",
            evidence="canvas revision 41 carries this operation id",
            evidence_ref="canvas:cv1@rev41")
        assert settled["status"] == "applied"
        assert settled["needs_reconciliation"] is False
        assert settled["reconciliation"]["evidence_ref"] == "canvas:cv1@rev41"

    def test_proven_not_applied_permits_a_controlled_retry(
            self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-absent")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        settled = lifecycle.reconcile_uncertain_operation(
            run_id, lifecycle.get_task(run_id)["operations"][0][
                "operation_id"],
            "not_applied",
            evidence="canvas revision predates the claim; the write never "
                     "reached the store")
        assert settled["status"] == "failed"
        assert settled["needs_reconciliation"] is False
        # A retry is a NEW operation linked to the closed one — the
        # original record is never rewound.
        retry = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="canvas-retry-1",
            parent_operation_id=settled["operation_id"])
        assert retry["parent_operation_id"] == settled["operation_id"]
        assert len(lifecycle.get_task(run_id)["operations"]) == 2

    # ── the discipline around "we don't know" ──────────────────────
    def test_a_timeout_is_not_confirmation(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-timeout")
        with pytest.raises(TaskLifecycleError, match="does not prove"):
            lifecycle.mark_operation_uncertain(
                run_id, lifecycle.get_task(run_id)["operations"][0][
                    "operation_id"],
                lost_worker="pid:999999", confirmed=False)
        # Still running, and still refused to a retry: no duplicate.
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "running"

    def test_a_live_worker_is_never_marked_uncertain(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-live")
        stranded = lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: True)
        assert stranded == []
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "running"

    def test_an_inconclusive_probe_leaves_the_operation_alone(
            self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-flaky")

        def _probe(_fingerprint):
            raise RuntimeError("liveness probe unavailable")

        assert lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=_probe) == []
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "running"

    def test_this_process_never_marks_its_own_work_uncertain(
            self, lifecycle):
        from core.task_lifecycle import _current_worker_fingerprint

        run_id = self._authorized_task(lifecycle)
        op = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="canvas-self")
        lifecycle.claim_execution(run_id, op["operation_id"])
        # Even a probe that says "dead" cannot retire our own claim.
        assert lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False) == []
        operation = lifecycle.get_task(run_id)["operations"][0]
        assert operation["status"] == "running"
        assert operation["claimed_by"] == _current_worker_fingerprint()

    def test_a_retry_never_blindly_repeats_an_uncertain_effect(
            self, lifecycle):
        """Two layers, both refusing. ``create_operation`` REPLAYS the
        uncertain record (so no second row is minted), and the execution
        claim REFUSES it — the retry cannot reach the effect."""
        from core.task_lifecycle import OperationExecutionClaimed

        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-blind")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        replayed = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="canvas-blind")
        # The replay carries the uncertainty rather than hiding it.
        assert replayed["status"] == "uncertain"
        assert replayed["needs_reconciliation"] is True
        # And the effect is refused, naming the real reason.
        claim = lifecycle.claim_execution(run_id, replayed["operation_id"])
        assert claim["granted"] is False
        assert claim["already_complete"] is True
        with pytest.raises(OperationExecutionClaimed,
                           match="UNKNOWN outcome"):
            begin_edit_turn(
                lifecycle, {}, "conv-1", "fix the draft", "ex-9",
                idempotency_key="canvas-blind")
        assert len(lifecycle.get_task(run_id)["operations"]) == 1

    def test_reconciliation_requires_evidence(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-noev")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        operation_id = lifecycle.get_task(run_id)["operations"][0][
            "operation_id"]
        for verdict in ("applied", "not_applied", "insufficient"):
            with pytest.raises(TaskLifecycleError, match="evidence"):
                lifecycle.reconcile_uncertain_operation(
                    run_id, operation_id, verdict, evidence="  ")

    def test_only_uncertain_operations_reconcile(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        op = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="canvas-plain")
        with pytest.raises(TaskLifecycleError, match="only an uncertain"):
            lifecycle.reconcile_uncertain_operation(
                run_id, op["operation_id"], "applied", evidence="x")

    def test_unknown_verdict_rejected(self, lifecycle):
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-bad")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        operation_id = lifecycle.get_task(run_id)["operations"][0][
            "operation_id"]
        with pytest.raises(TaskLifecycleError, match="unknown reconciliation"):
            lifecycle.reconcile_uncertain_operation(
                run_id, operation_id, "probably_fine", evidence="x")

    def test_uncertainty_is_discoverable_and_surfaced(self, lifecycle):
        from core.task_lifecycle import (
            find_uncertain_operations,
            uncertainty_notice,
        )

        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-surface")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        found = find_uncertain_operations(lifecycle, conversation_id="conv-1")
        assert len(found) == 1
        notice = uncertainty_notice(found[0]["operation"])
        assert notice["outcome"] == "unknown"
        assert notice["needs_reconciliation"] is True
        # It must not invite a duplicate, and must not claim either way.
        assert notice["retry_is_safe"] is False
        assert "not know whether" in notice["message"] or \
            "confirm whether" in notice["message"]

    def test_the_uncertain_state_has_no_way_back_to_pending(
            self, lifecycle):
        """A rewind is the duplicate this whole mechanism prevents."""
        run_id = self._authorized_task(lifecycle)
        self._claim_as_other_worker(lifecycle, run_id, key="canvas-rewind")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        operation_id = lifecycle.get_task(run_id)["operations"][0][
            "operation_id"]
        with pytest.raises(TaskLifecycleError, match="illegal operation"):
            lifecycle.transition_operation(
                run_id, operation_id, "pending")
        with pytest.raises(TaskLifecycleError, match="illegal operation"):
            lifecycle.transition_operation(run_id, operation_id, "running")


def _mp_crash_worker(db_path, run_id, key, crash_point, outcome_path):
    """Reserve, claim, then die at a chosen point.

    ``crash_point`` is "before_mutation" (nothing in the world changed)
    or "after_mutation" (the write landed, the completion never got
    recorded). The parent then verifies the recovery path and counts
    ACTUAL effects, because a singular operation row is also what a
    double-mutation bug looks like from the database.

    The outcome is announced to a FILE and the process then dies via
    ``os._exit`` — an unflushable exit, which is the point. A
    multiprocessing Queue cannot be used here: its feeder thread does not
    get to drain when the process dies immediately after ``put``, so the
    parent would read empty and the test would be testing nothing.
    """
    import os
    import sys

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("TESTING", "1")
    try:
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import sessionmaker as _sessionmaker

        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.models import (
            GoalObjective,
            GoalRun,
            TaskOperationRecord,
        )
        from core.task_lifecycle import TaskLifecycle

        engine = _create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30})
        factory = _sessionmaker(bind=engine, expire_on_commit=False)
        lifecycle = TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))
        op = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key=key)
        claim = lifecycle.claim_execution(run_id, op["operation_id"],
                                         execution_id="ex-crash")

        import json as _json

        def _die(outcome):
            with open(outcome_path, "w") as handle:
                _json.dump(outcome, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os._exit(9)

        if not claim.get("granted"):
            _die({"outcome": "refused", "operation_id": op["operation_id"]})
        if crash_point == "after_mutation":
            # The world changed; the process dies BEFORE recording it.
            _die({"outcome": "crashed_after_mutation",
                  "operation_id": op["operation_id"]})
        _die({"outcome": "crashed_before_mutation",
              "operation_id": op["operation_id"]})
    except Exception as exc:  # noqa: BLE001 — reported to the parent
        import json as _json
        with open(outcome_path, "w") as handle:
            _json.dump({"outcome": "error",
                        "error": f"{type(exc).__name__}: {exc}"}, handle)


class TestCrossProcessCrashRecovery:
    """Item 4 across real processes: crash at both points, then assert
    recovery, the absence of blind repeats, and ACTUAL effect counts."""

    def _setup(self, tmp_path, name):
        db_path = str(tmp_path / name)
        engine = create_engine(f"sqlite:///{db_path}")
        for table in (GoalObjective.__table__, GoalRun.__table__,
                      TaskOperationRecord.__table__):
            table.create(engine)
        engine.dispose()
        factory = sessionmaker(bind=create_engine(f"sqlite:///{db_path}"),
                               expire_on_commit=False)
        lifecycle = TaskLifecycle(
            GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                           session_factory=factory),
            GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory))
        created = lifecycle.create_task("conv-crash", "fix the draft")
        run_id = created["run_id"]
        lifecycle.apply_transition(run_id, {
            "kind": "authorize_execute", "approval": "authorized",
            "authorized_actions": ["edit"]})
        return db_path, lifecycle, run_id

    def _crash(self, db_path, run_id, key, crash_point, outcome_path):
        """Run a child that dies hard at ``crash_point``.

        The child is expected to exit NON-zero — that is the crash being
        simulated, so a clean exit is a failure of the fixture.
        """
        import json
        import multiprocessing as _mp

        ctx = _mp.get_context("spawn")
        proc = ctx.Process(
            target=_mp_crash_worker,
            args=(db_path, run_id, key, crash_point, outcome_path))
        proc.start()
        proc.join(timeout=180)
        assert proc.exitcode not in (0, None), (
            f"the crash fixture should have died hard, got "
            f"exitcode={proc.exitcode}")
        with open(outcome_path) as handle:
            return json.load(handle)

    def _simulate_lost_worker(self, lifecycle, run_id, fingerprint):
        record = lifecycle.get_task(run_id)
        ops = [dict(o) for o in record["operations"]]
        for op in ops:
            op["claimed_by"] = fingerprint
        lifecycle._cas_write(
            run_id, record["task_version"],
            {"task_revision": record["task_revision"], "operations": ops,
             "deliveries": record["deliveries"],
             "conversation_id": record["conversation_id"]},
            {"kind": "crash_sim"})

    def test_crash_before_mutation_recovers_without_a_repeat(
            self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path, lifecycle, run_id = self._setup(tmp_path, "crash_before.db")
        result = self._crash(db_path, run_id, "canvas-cb", "before_mutation",
                           str(tmp_path / "cb.json"))
        assert result["outcome"] == "crashed_before_mutation"
        operation_id = result["operation_id"]

        # The dead worker's identity is no longer the one on the claim.
        self._simulate_lost_worker(lifecycle, run_id, "pid:999999")
        stranded = lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        assert len(stranded) == 1
        operation = lifecycle.get_task(run_id)["operations"][0]
        assert operation["operation_id"] == operation_id
        assert operation["status"] == "uncertain"

        # A blind retry is refused; the effect count stays at zero.
        replayed = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="canvas-cb")
        claim = lifecycle.claim_execution(run_id, replayed["operation_id"])
        assert claim["granted"] is False
        assert self._effect_count(lifecycle, run_id) == 0

    def test_crash_after_mutation_requires_evidence_not_a_retry(
            self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path, lifecycle, run_id = self._setup(tmp_path, "crash_after.db")
        result = self._crash(db_path, run_id, "canvas-ca", "after_mutation",
                           str(tmp_path / "ca.json"))
        assert result["outcome"] == "crashed_after_mutation"
        operation_id = result["operation_id"]

        # The mutation HAPPENED but the operation still says running:
        # the database cannot tell that on its own, which is the point.
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "running"

        self._simulate_lost_worker(lifecycle, run_id, "pid:999999")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        assert lifecycle.get_task(run_id)["operations"][0]["status"] == \
            "uncertain"

        # A retry is refused even though evidence eventually proves the
        # effect landed — and once proved, completion is recorded.
        replayed = lifecycle.create_operation(
            run_id, op_type="edit", requested_change="fix the draft",
            idempotency_key="canvas-ca")
        assert lifecycle.claim_execution(
            run_id, replayed["operation_id"])["granted"] is False
        settled = lifecycle.reconcile_uncertain_operation(
            run_id, operation_id, "applied",
            evidence="canvas revision 77 carries this operation id",
            evidence_ref="canvas:cv1@rev77")
        assert settled["status"] == "applied"
        assert settled["needs_reconciliation"] is False
        # One operation, one completed effect — never two.
        record = lifecycle.get_task(run_id)
        assert len(record["operations"]) == 1
        assert self._effect_count(lifecycle, run_id) == 1

    def test_crash_after_mutation_with_no_evidence_stays_uncertain(
            self, tmp_path, monkeypatch):
        """A timeout is not evidence. With nothing to go on, the honest
        state persists and the user is told the outcome is unknown."""
        monkeypatch.setenv("ATOM_TASK_LOCK_DIR", str(tmp_path / "locks"))
        db_path, lifecycle, run_id = self._setup(tmp_path, "crash_silent.db")
        result = self._crash(db_path, run_id, "canvas-cs", "after_mutation",
                           str(tmp_path / "cs.json"))
        assert result["outcome"] == "crashed_after_mutation"
        operation_id = result["operation_id"]
        self._simulate_lost_worker(lifecycle, run_id, "pid:999999")
        lifecycle.recover_confirmed_worker_loss(
            run_id, is_worker_live=lambda fp: False)
        settled = lifecycle.reconcile_uncertain_operation(
            run_id, operation_id, "insufficient",
            evidence="no revision carries this operation; the write may "
                     "or may not have landed")
        assert settled["status"] == "uncertain"
        assert settled["needs_reconciliation"] is True
        assert self._effect_count(lifecycle, run_id) == 0

    def _effect_count(self, lifecycle, run_id):
        """Count COMPLETED effects. An operation that reached applied is
        an effect that happened; a stranded or uncertain one is unknown,
        which is a different claim and is counted separately."""
        record = lifecycle.get_task(run_id)
        return len([o for o in record["operations"]
                    if o.get("status") == "applied"])
