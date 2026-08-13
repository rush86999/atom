"""Coverage wave 64i — core/execution_state_manager.py to >=95% (TDD).

The module is NOT dead code: it is wired into workflow_engine.py
(WorkflowEngine.__init__ -> get_state_manager()), workflow_endpoints.py
(durable-engine fallback at /debug/state paths) and is the base class of
enhanced_execution_state_manager.py (99% covered in wave 36).

Baseline: 42% (the stale tests/test_execution_state_manager.py suite has
1 fail + 6 errors from infra, not logic). This suite mocks
get_async_db_session with a fake async session — no real DB, no network.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import core.execution_state_manager as esm
from core.execution_state_manager import ExecutionStateManager, get_state_manager


class _FakeSession:
    """Async context manager stand-in for the SQLAlchemy async session."""

    def __init__(self, scalar=None):
        self.scalar_value = scalar
        self.committed = 0
        self.added = []
        self.executes = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *args, **kwargs):
        self.executes.append((args, kwargs))
        return self

    def scalar_one_or_none(self):
        return self.scalar_value

    async def commit(self):
        self.committed += 1

    def add(self, obj):
        self.added.append(obj)


def _session_for(scalar=None):
    return _FakeSession(scalar=scalar)


def _patch_session(session):
    return patch.object(esm, "get_async_db_session", return_value=session)


def _make_execution_row(**overrides):
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    fields = dict(
        execution_id="exec-1",
        workflow_id="wf-1",
        status="PENDING",
        version=1,
        input_data='{"a": 1}',
        steps='{"s1": {"status": "done"}}',
        outputs='{"s1": {"x": 1}}',
        context='{"k": "v"}',
        created_at=now,
        updated_at=now,
        error=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestCreateExecution:
    @pytest.mark.asyncio
    async def test_creates_and_commits(self):
        session = _session_for()
        manager = ExecutionStateManager()
        with _patch_session(session):
            execution_id = await manager.create_execution("wf-1", {"a": 1})
        assert execution_id
        assert session.committed == 1
        assert len(session.added) == 1
        row = session.added[0]
        assert row.workflow_id == "wf-1"
        assert row.status == "PENDING"
        assert row.version == 1
        assert row.execution_id == execution_id
        assert row.created_at is not None
        assert row.updated_at is not None


class TestUpdateStepStatus:
    @pytest.mark.asyncio
    async def test_execution_not_found_raises(self):
        session = _session_for(scalar=None)
        manager = ExecutionStateManager()
        with _patch_session(session):
            with pytest.raises(ValueError, match="not found"):
                await manager.update_step_status("missing", "s1", "completed")

    @pytest.mark.asyncio
    async def test_updates_existing_step_with_output_and_error(self):
        session = _session_for(scalar=_make_execution_row())
        manager = ExecutionStateManager()
        with _patch_session(session):
            await manager.update_step_status(
                "exec-1", "s1", "failed", output={"partial": 1}, error="boom")
        assert session.committed == 1
        # version increment + serialized steps/outputs
        stmt = session.executes[-1][0][0]
        values = {c.name: getattr(v, "value", v) for c, v in stmt._values.items()}
        import json
        steps = json.loads(values["steps"])
        assert steps["s1"]["status"] == "failed"
        assert steps["s1"]["error"] == "boom"
        assert steps["s1"]["output"] == {"partial": 1}
        assert json.loads(values["outputs"]) == {"s1": {"partial": 1}}
        assert values["version"] is not None  # WorkflowExecution.version + 1

    @pytest.mark.asyncio
    async def test_creates_new_step_entry(self):
        session = _session_for(scalar=_make_execution_row())
        manager = ExecutionStateManager()
        with _patch_session(session):
            await manager.update_step_status("exec-1", "s2", "running")
        import json
        values = {c.name: getattr(v, "value", v) for c, v in session.executes[-1][0][0]._values.items()}
        steps = json.loads(values["steps"])
        assert "s2" in steps
        assert steps["s2"]["status"] == "running"
        assert "created_at" in steps["s2"]
        assert "updated_at" in steps["s2"]


class TestUpdateExecutionStatus:
    @pytest.mark.asyncio
    async def test_updates_status(self):
        session = _session_for()
        manager = ExecutionStateManager()
        with _patch_session(session):
            await manager.update_execution_status("exec-1", "COMPLETED")
        assert session.committed == 1
        values = {c.name: getattr(v, "value", v) for c, v in session.executes[-1][0][0]._values.items()}
        assert values["status"] == "COMPLETED"
        assert values["error"] is None

    @pytest.mark.asyncio
    async def test_updates_status_with_error(self):
        session = _session_for()
        manager = ExecutionStateManager()
        with _patch_session(session):
            await manager.update_execution_status("exec-1", "FAILED", error="err")
        values = {c.name: getattr(v, "value", v) for c, v in session.executes[-1][0][0]._values.items()}
        assert values["status"] == "FAILED"
        assert values["error"] == "err"


class TestUpdateExecutionInputs:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        session = _session_for(scalar=None)
        manager = ExecutionStateManager()
        with _patch_session(session):
            with pytest.raises(ValueError, match="not found"):
                await manager.update_execution_inputs("missing", {"b": 2})

    @pytest.mark.asyncio
    async def test_merges_inputs(self):
        session = _session_for(scalar=_make_execution_row())
        manager = ExecutionStateManager()
        with _patch_session(session):
            await manager.update_execution_inputs("exec-1", {"b": 2})
        values = {c.name: getattr(v, "value", v) for c, v in session.executes[-1][0][0]._values.items()}
        import json
        assert json.loads(values["input_data"]) == {"a": 1, "b": 2}


class TestGetExecutionState:
    @pytest.mark.asyncio
    async def test_not_found_returns_none(self):
        session = _session_for(scalar=None)
        manager = ExecutionStateManager()
        with _patch_session(session):
            assert await manager.get_execution_state("missing") is None

    @pytest.mark.asyncio
    async def test_deserializes_full_state(self):
        row = _make_execution_row()
        session = _session_for(scalar=row)
        manager = ExecutionStateManager()
        with _patch_session(session):
            state = await manager.get_execution_state("exec-1")
        assert state["execution_id"] == "exec-1"
        assert state["workflow_id"] == "wf-1"
        assert state["status"] == "PENDING"
        assert state["version"] == 1
        assert state["input_data"] == {"a": 1}
        assert state["steps"] == {"s1": {"status": "done"}}
        assert state["outputs"] == {"s1": {"x": 1}}
        assert state["context"] == {"k": "v"}
        assert state["created_at"].startswith("2026-01-01T12:00")
        assert state["error"] is None

    @pytest.mark.asyncio
    async def test_empty_json_fields_become_empty_dicts(self):
        row = _make_execution_row(input_data=None, steps="", outputs=None,
                                  context=None, created_at=None, updated_at=None)
        session = _session_for(scalar=row)
        manager = ExecutionStateManager()
        with _patch_session(session):
            state = await manager.get_execution_state("exec-1")
        assert state["input_data"] == {}
        assert state["steps"] == {}
        assert state["outputs"] == {}
        assert state["context"] == {}
        assert state["created_at"] is None
        assert state["updated_at"] is None

    @pytest.mark.asyncio
    async def test_bad_json_returns_none(self):
        row = _make_execution_row(input_data="not-json{")
        session = _session_for(scalar=row)
        manager = ExecutionStateManager()
        with _patch_session(session):
            assert await manager.get_execution_state("exec-1") is None


class TestGetStepOutput:
    @pytest.mark.asyncio
    async def test_missing_execution_returns_none(self):
        session = _session_for(scalar=None)
        manager = ExecutionStateManager()
        with _patch_session(session):
            assert await manager.get_step_output("missing", "s1") is None

    @pytest.mark.asyncio
    async def test_returns_step_output(self):
        session = _session_for(scalar=_make_execution_row())
        manager = ExecutionStateManager()
        with _patch_session(session):
            assert await manager.get_step_output("exec-1", "s1") == {"x": 1}

    @pytest.mark.asyncio
    async def test_missing_step_returns_none(self):
        session = _session_for(scalar=_make_execution_row())
        manager = ExecutionStateManager()
        with _patch_session(session):
            assert await manager.get_step_output("exec-1", "nope") is None


class TestSingleton:
    def test_get_state_manager_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr(esm, "_state_manager", None)
        first = get_state_manager()
        second = get_state_manager()
        assert first is second
        assert isinstance(first, ExecutionStateManager)

    def test_get_state_manager_returns_existing(self, monkeypatch):
        existing = ExecutionStateManager()
        monkeypatch.setattr(esm, "_state_manager", existing)
        assert get_state_manager() is existing
