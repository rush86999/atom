"""Coverage-push tests for backend/tools (W75c, part A).

Standalone >=95% statement coverage for:
- tools/atom_cli_skill_wrapper.py
- tools/agent_guidance_canvas_tool.py
- tools/agent_radio_tool.py
- tools/canvas_crud_tool.py
- tools/platform_management_tool.py

Style: mocked deps, zero LLM spend, no network, no real DB.
"""

import importlib
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


def _cm_db():
    """A MagicMock DB that also works as ``with SessionLocal() as db:``."""
    db = MagicMock()
    db.__enter__.return_value = db
    return db


# ============================================================================
# tools/atom_cli_skill_wrapper.py
# ============================================================================

class TestExecuteAtomCliCommand:
    def test_success_with_args(self):
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command
        proc = SimpleNamespace(returncode=0, stdout="Status: RUNNING\nPID: 123", stderr="")
        with patch("tools.atom_cli_skill_wrapper.subprocess.run", return_value=proc) as run:
            res = execute_atom_cli_command("status", ["--port", "3000"])
        assert res["success"] is True and res["returncode"] == 0
        assert res["stdout"] == "Status: RUNNING\nPID: 123"
        cmd = run.call_args.args[0]
        assert cmd == ["atom-os", "status", "--port", "3000"]
        assert run.call_args.kwargs["timeout"] == 30

    def test_success_no_args_no_env(self):
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command
        proc = SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with patch("tools.atom_cli_skill_wrapper.subprocess.run", return_value=proc) as run:
            res = execute_atom_cli_command("stop")
        assert res["success"] is True
        assert run.call_args.args[0] == ["atom-os", "stop"]
        assert run.call_args.kwargs["env"] is None

    def test_cwd_passed_sets_env(self):
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command
        proc = SimpleNamespace(returncode=1, stdout="", stderr="boom")
        with patch("tools.atom_cli_skill_wrapper.subprocess.run", return_value=proc) as run:
            res = execute_atom_cli_command("daemon", cwd="/tmp/x")
        assert res["success"] is False and res["returncode"] == 1
        assert run.call_args.kwargs["cwd"] == "/tmp/x"
        assert "PATH" in run.call_args.kwargs["env"]

    def test_timeout(self):
        import subprocess as _sp
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command
        with patch("tools.atom_cli_skill_wrapper.subprocess.run",
                   side_effect=_sp.TimeoutExpired("atom-os", 30)):
            res = execute_atom_cli_command("daemon")
        assert res["success"] is False and res["returncode"] == -1
        assert "timed out" in res["stderr"]

    def test_generic_exception(self):
        from tools.atom_cli_skill_wrapper import execute_atom_cli_command
        with patch("tools.atom_cli_skill_wrapper.subprocess.run",
                   side_effect=FileNotFoundError("nope")):
            res = execute_atom_cli_command("daemon")
        assert res["success"] is False and res["returncode"] == -1
        assert "nope" in res["stderr"]


class TestIsDaemonRunning:
    def test_running(self):
        from tools.atom_cli_skill_wrapper import is_daemon_running
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": "Status: RUNNING\nPID: 5"}):
            assert is_daemon_running() is True

    def test_not_running(self):
        from tools.atom_cli_skill_wrapper import is_daemon_running
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": "Status: NOT RUNNING"}):
            assert is_daemon_running() is False

    def test_no_match(self):
        from tools.atom_cli_skill_wrapper import is_daemon_running
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": "garbage"}):
            assert is_daemon_running() is False

    def test_unsuccessful(self):
        from tools.atom_cli_skill_wrapper import is_daemon_running
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": False, "stdout": ""}):
            assert is_daemon_running() is False

    def test_exception(self):
        from tools.atom_cli_skill_wrapper import is_daemon_running
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   side_effect=RuntimeError("x")):
            assert is_daemon_running() is False


class TestGetDaemonPid:
    def test_pid_found(self):
        from tools.atom_cli_skill_wrapper import get_daemon_pid
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": "PID: 12345\nStatus: RUNNING"}):
            assert get_daemon_pid() == 12345

    def test_pid_missing(self):
        from tools.atom_cli_skill_wrapper import get_daemon_pid
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": "Status: STOPPED"}):
            assert get_daemon_pid() is None

    def test_unsuccessful(self):
        from tools.atom_cli_skill_wrapper import get_daemon_pid
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": False, "stdout": ""}):
            assert get_daemon_pid() is None

    def test_exception(self):
        from tools.atom_cli_skill_wrapper import get_daemon_pid
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   side_effect=RuntimeError("x")):
            assert get_daemon_pid() is None


class TestWaitForDaemonReady:
    def test_ready_immediately(self):
        from tools.atom_cli_skill_wrapper import wait_for_daemon_ready
        with patch("tools.atom_cli_skill_wrapper.is_daemon_running", return_value=True), \
             patch("tools.atom_cli_skill_wrapper.time.time", return_value=0.0), \
             patch("tools.atom_cli_skill_wrapper.time.sleep") as sleep:
            assert wait_for_daemon_ready() is True
        sleep.assert_not_called()

    def test_timeout(self):
        from tools.atom_cli_skill_wrapper import wait_for_daemon_ready
        clock = [0.0]
        def _clock():
            clock[0] += 0.4
            return clock[0]
        with patch("tools.atom_cli_skill_wrapper.is_daemon_running", return_value=False), \
             patch("tools.atom_cli_skill_wrapper.time.time", side_effect=_clock), \
             patch("tools.atom_cli_skill_wrapper.time.sleep"):
            assert wait_for_daemon_ready(max_wait=3) is False

    def test_ready_after_retry(self):
        from tools.atom_cli_skill_wrapper import wait_for_daemon_ready
        runs = {"n": 0}
        def _running():
            runs["n"] += 1
            return runs["n"] >= 2
        clock = [0.0]
        def _clock():
            clock[0] += 0.2
            return clock[0]
        with patch("tools.atom_cli_skill_wrapper.is_daemon_running", side_effect=_running), \
             patch("tools.atom_cli_skill_wrapper.time.time", side_effect=_clock), \
             patch("tools.atom_cli_skill_wrapper.time.sleep"):
            assert wait_for_daemon_ready(max_wait=10) is True


class TestMockDaemonResponse:
    def test_success_and_failure(self):
        from tools.atom_cli_skill_wrapper import mock_daemon_response
        res = mock_daemon_response(stdout="Status: RUNNING", returncode=0)
        assert res == {"success": True, "stdout": "Status: RUNNING",
                       "stderr": "", "returncode": 0}
        res2 = mock_daemon_response(stderr="err", returncode=2)
        assert res2["success"] is False and res2["returncode"] == 2


class TestBuildCommandArgs:
    def test_all_branches(self):
        from tools.atom_cli_skill_wrapper import build_command_args
        args = build_command_args(port=8000, host="0.0.0.0", workers=4,
                                  host_mount=True, dev=True, foreground=True)
        assert args == ["--port", "8000", "--host", "0.0.0.0", "--workers", "4",
                        "--host-mount", "--dev", "--foreground"]

    def test_empty(self):
        from tools.atom_cli_skill_wrapper import build_command_args
        assert build_command_args() == []

    def test_partial(self):
        from tools.atom_cli_skill_wrapper import build_command_args
        assert build_command_args(port=3000) == ["--port", "3000"]


# ============================================================================
# tools/agent_guidance_canvas_tool.py
# ============================================================================

class TestAgentGuidanceSystem:
    @pytest.fixture(autouse=True)
    def _env(self):
        self.db = _cm_db()
        self.resolver = MagicMock()
        self.gov = MagicMock()
        self.ws = AsyncMock()
        with patch("tools.agent_guidance_canvas_tool.AgentContextResolver",
                   return_value=self.resolver), \
             patch("tools.agent_guidance_canvas_tool.AgentGovernanceService",
                   return_value=self.gov), \
             patch("tools.agent_guidance_canvas_tool.ws_manager", self.ws), \
             patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", True), \
             patch("tools.agent_guidance_canvas_tool.EMERGENCY_GOVERNANCE_BYPASS", False):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            self.sys = AgentGuidanceSystem(self.db)
            yield

    def _agent(self, **kw):
        return SimpleNamespace(id="a-1", name="Demo", workspace_id="ws-1",
                               maturity_level="INTERN", **kw)

    def _tracker(self, **kw):
        defaults = dict(id="t-1", tenant_id="default", agent_id="a-1", user_id="u-1",
                        workspace_id="ws-1", operation_type="browser_automate",
                        operation_id="op-1", current_step="Init", total_steps=None,
                        current_step_index=0, status="running", progress=0,
                        what_explanation="w", why_explanation="y", next_steps="n",
                        operation_metadata={}, logs=[])
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    async def test_start_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            op_id = await self.sys.start_operation("u-1", "a-1", "browser_automate", {})
        assert op_id

    async def test_start_blocked_by_governance(self):
        self.db.query.return_value.filter.return_value.first.return_value = self._agent()
        self.gov.can_perform_action.return_value = {"allowed": False, "reason": "no"}
        res = await self.sys.start_operation("u-1", "a-1", "browser_automate", {"what": "x"})
        assert res["success"] is False and "no" in res["error"]
        self.ws.broadcast.assert_not_called()

    async def test_start_success_with_agent(self):
        self.db.query.return_value.filter.return_value.first.return_value = self._agent()
        self.gov.can_perform_action.return_value = {"allowed": True}
        op_id = await self.sys.start_operation("u-1", "a-1", "browser_automate",
                                               {"what": "w", "why": "y", "next": "n"},
                                               total_steps=3, metadata={"k": "v"})
        assert op_id
        self.db.add.assert_called()
        self.db.commit.assert_called()
        self.ws.broadcast.assert_awaited_once()
        payload = self.ws.broadcast.await_args.args[1]["data"]["data"]
        assert payload["agent_name"] == "Demo" and payload["operation_id"] == op_id

    async def test_start_success_no_agent(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        op_id = await self.sys.start_operation("u-1", "a-1", "browser_automate", {})
        assert op_id
        payload = self.ws.broadcast.await_args.args[1]["data"]["data"]
        assert payload["agent_name"] == "Agent"

    async def test_start_exception_returns_uuid(self):
        self.db.query.side_effect = RuntimeError("db down")
        op_id = await self.sys.start_operation("u-1", "a-1", "browser_automate", {})
        assert op_id

    async def test_start_audit_failure_still_returns(self):
        self.db.query.return_value.filter.return_value.first.return_value = self._agent()
        self.gov.can_perform_action.return_value = {"allowed": True}
        self.db.commit.side_effect = [None, RuntimeError("audit fail")]
        op_id = await self.sys.start_operation("u-1", "a-1", "browser_automate", {})
        assert op_id

    async def test_update_step_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            await self.sys.update_step("u-1", "op-1", "step")
        self.ws.broadcast.assert_not_called()

    async def test_update_step_tracker_missing(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        await self.sys.update_step("u-1", "op-1", "step")
        self.db.commit.assert_not_called()

    async def test_update_step_with_log_and_progress(self):
        tracker = self._tracker(logs=[])
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.update_step("u-1", "op-1", "Step 2", progress=50,
                                   add_log={"level": "info", "message": "m"})
        assert tracker.current_step == "Step 2" and tracker.progress == 50
        assert len(tracker.logs) == 1
        self.ws.broadcast.assert_awaited_once()
        updates = self.ws.broadcast.await_args.args[1]["data"]["updates"]
        assert updates["logs"] is not None

    async def test_update_step_calculated_progress(self):
        tracker = self._tracker(total_steps=10, current_step_index=1, progress=0)
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.update_step("u-1", "op-1", None)
        assert tracker.progress == 20
        assert self.db.commit.call_count == 2

    async def test_update_step_exception(self):
        tracker = self._tracker()
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        self.db.commit.side_effect = RuntimeError("x")
        await self.sys.update_step("u-1", "op-1", "s")

    async def test_update_context_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            await self.sys.update_context("u-1", "op-1", what="a")

    async def test_update_context_missing_tracker(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        await self.sys.update_context("u-1", "op-1", what="a")
        self.db.commit.assert_not_called()

    async def test_update_context_success(self):
        tracker = self._tracker()
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.update_context("u-1", "op-1", what="new-w", why="new-y", next_steps="new-n")
        assert tracker.what_explanation == "new-w"
        self.ws.broadcast.assert_awaited_once()

    async def test_update_context_partial(self):
        tracker = self._tracker()
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.update_context("u-1", "op-1", what="only")
        assert tracker.what_explanation == "only" and tracker.why_explanation == "y"

    async def test_update_context_exception(self):
        tracker = self._tracker()
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        self.db.commit.side_effect = RuntimeError("x")
        await self.sys.update_context("u-1", "op-1", what="a")

    async def test_complete_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            await self.sys.complete_operation("u-1", "op-1")

    async def test_complete_missing_tracker(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        await self.sys.complete_operation("u-1", "op-1")

    async def test_complete_success(self):
        tracker = self._tracker(completed_at=None, progress=40)
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.complete_operation("u-1", "op-1", status="completed",
                                          final_message="Done")
        assert tracker.status == "completed" and tracker.progress == 100
        assert tracker.current_step == "Done"
        self.ws.broadcast.assert_awaited_once()

    async def test_complete_failed_status(self):
        tracker = self._tracker(completed_at=None, progress=10)
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.complete_operation("u-1", "op-1", status="failed")
        assert tracker.progress == 10

    async def test_complete_exception(self):
        tracker = self._tracker()
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        self.db.commit.side_effect = RuntimeError("x")
        await self.sys.complete_operation("u-1", "op-1")

    async def test_add_log_entry_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            await self.sys.add_log_entry("u-1", "op-1", "info", "m")
        self.ws.broadcast.assert_not_called()

    async def test_add_log_entry(self):
        tracker = self._tracker()
        self.db.query.return_value.filter.return_value.first.return_value = tracker
        await self.sys.add_log_entry("u-1", "op-1", "error", "msg")
        assert len(tracker.logs) == 1 and tracker.logs[0]["level"] == "error"

    async def test_create_audit_success(self):
        await self.sys._create_audit("a-1", "u-1", "op-1", "start_operation", True, {})
        self.db.add.assert_called_once()
        self.db.commit.assert_called_once()

    async def test_create_audit_exception_rolls_back(self):
        self.db.add.side_effect = RuntimeError("x")
        await self.sys._create_audit("a-1", "u-1", "op-1", "start_operation", True, {})
        self.db.rollback.assert_called_once()

    def test_get_agent_guidance_system(self):
        from tools.agent_guidance_canvas_tool import get_agent_guidance_system
        svc = get_agent_guidance_system(MagicMock())
        assert svc is not None


class TestAgentGuidanceBypass:
    @pytest.fixture(autouse=True)
    def _env(self):
        self.db = _cm_db()
        self.ws = AsyncMock()
        with patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager", self.ws), \
             patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", True), \
             patch("tools.agent_guidance_canvas_tool.EMERGENCY_GOVERNANCE_BYPASS", True):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            self.sys = AgentGuidanceSystem(self.db)
            yield

    async def test_start_skips_governance_query(self):
        op_id = await self.sys.start_operation("u-1", "a-1", "browser_automate", {})
        assert op_id
        self.db.query.assert_not_called()


# ============================================================================
# tools/agent_radio_tool.py
# ============================================================================

class TestRegisterAgentRadioTools:
    def test_register_with_registry(self):
        from tools.agent_radio_tool import register_agent_radio_tools
        registry = MagicMock()
        register_agent_radio_tools(registry)
        assert registry.register.call_count == 4
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert names == ["radio.create_thread", "radio.send_message",
                         "radio.wait_for_mention", "radio.read_inbox"]
        maturities = [c.kwargs["maturity_required"] for c in registry.register.call_args_list]
        assert maturities[:2] == ["INTERN", "INTERN"]
        assert maturities[2:] == ["STUDENT", "STUDENT"]
        complexities = [c.kwargs["complexity"] for c in registry.register.call_args_list]
        assert complexities == [2, 2, 1, 1]

    def test_register_default_registry(self):
        import importlib as _il
        import tools.agent_radio_tool as radiotool
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            _il.reload(radiotool)
            radiotool.register_agent_radio_tools()
        assert registry.register.call_count == 4


# ============================================================================
# tools/canvas_crud_tool.py
# ============================================================================

class TestVerifyCanvasOwner:
    def test_not_found(self):
        from tools.canvas_crud_tool import _verify_canvas_owner
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        assert _verify_canvas_owner(db, "c-1", "u-1") is False

    def test_not_owner(self):
        from tools.canvas_crud_tool import _verify_canvas_owner
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            created_by="u-2")
        assert _verify_canvas_owner(db, "c-1", "u-1") is False

    def test_owner(self):
        from tools.canvas_crud_tool import _verify_canvas_owner
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            created_by="u-1")
        assert _verify_canvas_owner(db, "c-1", "u-1") is True


class TestReadCanvas:
    async def _run(self, audit, owner="u-1"):
        db = _cm_db()
        f = db.query.return_value.filter.return_value
        f.first.return_value = SimpleNamespace(created_by=owner)
        f.order_by.return_value.first.return_value = audit
        import tools.canvas_crud_tool as mod
        with _patch_db(db):
            return await mod.read_canvas("u-1", "c-1")

    async def test_not_owner(self):
        import tools.canvas_crud_tool as mod
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            created_by="other")
        with _patch_db(db):
            res = await mod.read_canvas("u-1", "c-1")
        assert res["success"] is False and "not found" in res["error"]

    async def test_no_audit(self):
        res = await self._run(None)
        assert res["success"] is False

    async def test_deleted_canvas(self):
        audit = SimpleNamespace(action_type="delete", canvas_type="docs",
                                details_json={"content": "x"}, created_at=datetime.now())
        res = await self._run(audit)
        assert res["success"] is False and res.get("deleted") is True

    async def test_success_with_content(self):
        created = datetime.now()
        audit = SimpleNamespace(action_type="present", canvas_type="docs",
                                details_json={"content": "hello", "title": "T"},
                                created_at=created)
        res = await self._run(audit)
        assert res["success"] is True and res["content"] == "hello"
        assert res["canvas_type"] == "docs" and res["title"] == "T"
        assert res["created_at"] == created.isoformat()

    async def test_success_empty_content_preserved(self):
        audit = SimpleNamespace(action_type="present", canvas_type="email",
                                details_json={"content": ""}, created_at=None)
        res = await self._run(audit)
        assert res["success"] is True and res["content"] == ""
        assert res["created_at"] is None

    async def test_success_content_falls_back_to_details(self):
        audit = SimpleNamespace(action_type="present", canvas_type="generic",
                                details_json={"data": [1, 2]}, created_at=None)
        res = await self._run(audit)
        assert res["success"] is True and res["content"] == [1, 2]

    async def test_exception(self):
        import tools.canvas_crud_tool as mod
        with _patch_db(MagicMock(query=MagicMock(side_effect=RuntimeError("boom")))):
            res = await mod.read_canvas("u-1", "c-1")
        assert res["success"] is False


class TestUpdateCanvasContent:
    def _audit(self, **kw):
        defaults = dict(action_type="present", canvas_type="docs",
                        details_json={"title": "Old"}, tenant_id="default",
                        created_at=datetime.now())
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    async def _run(self, first, ws_raise=None):
        db = _cm_db()
        f = db.query.return_value.filter.return_value
        f.first.return_value = SimpleNamespace(created_by="u-1")
        f.order_by.return_value.first.return_value = first
        ws = AsyncMock()
        if ws_raise:
            ws.broadcast.side_effect = ws_raise
        import tools.canvas_crud_tool as mod
        with _patch_db(db), patch("core.websockets.manager", ws):
            return await mod.update_canvas_content("u-1", "c-1", "new content",
                                                   canvas_type="docs", title="New")

    async def test_not_owner(self):
        import tools.canvas_crud_tool as mod
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            created_by="other")
        with _patch_db(db):
            res = await mod.update_canvas_content("u-1", "c-1", "x")
        assert res["success"] is False

    async def test_no_latest(self):
        res = await self._run(None)
        assert res["success"] is False

    async def test_deleted(self):
        res = await self._run(self._audit(action_type="delete"))
        assert res["success"] is False and "deleted" in res["error"]

    async def test_success(self):
        res = await self._run(self._audit())
        assert res["success"] is True
        assert res["canvas_type"] == "docs"

    async def test_ws_broadcast_failure_skipped(self):
        res = await self._run(self._audit(), ws_raise=RuntimeError("ws down"))
        assert res["success"] is True

    async def test_exception(self):
        import tools.canvas_crud_tool as mod
        db = _cm_db()
        db.query.side_effect = RuntimeError("boom")
        with _patch_db(db), patch("core.websockets.manager", AsyncMock()):
            res = await mod.update_canvas_content("u-1", "c-1", "x")
        assert res["success"] is False


class TestDeleteCanvas:
    def _audit(self, **kw):
        defaults = dict(action_type="present", canvas_type="docs",
                        details_json={}, tenant_id="default", created_at=datetime.now())
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    async def _run(self, first, ws_raise=None):
        db = _cm_db()
        f = db.query.return_value.filter.return_value
        f.first.return_value = SimpleNamespace(created_by="u-1")
        f.order_by.return_value.first.return_value = first
        ws = AsyncMock()
        if ws_raise:
            ws.broadcast.side_effect = ws_raise
        import tools.canvas_crud_tool as mod
        with _patch_db(db), patch("core.websockets.manager", ws):
            return await mod.delete_canvas("u-1", "c-1")

    async def test_not_owner(self):
        import tools.canvas_crud_tool as mod
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            created_by="other")
        with _patch_db(db), patch("core.websockets.manager", AsyncMock()):
            res = await mod.delete_canvas("u-1", "c-1")
        assert res["success"] is False

    async def test_no_latest(self):
        res = await self._run(None)
        assert res["success"] is False

    async def test_already_deleted(self):
        res = await self._run(self._audit(action_type="delete"))
        assert res["success"] is False and "already" in res["error"]

    async def test_success(self):
        res = await self._run(self._audit())
        assert res["success"] is True

    async def test_ws_broadcast_failure_skipped(self):
        res = await self._run(self._audit(), ws_raise=RuntimeError("ws down"))
        assert res["success"] is True

    async def test_exception(self):
        import tools.canvas_crud_tool as mod
        db = _cm_db()
        db.query.side_effect = RuntimeError("boom")
        with _patch_db(db), patch("core.websockets.manager", AsyncMock()):
            res = await mod.delete_canvas("u-1", "c-1")
        assert res["success"] is False


class TestListCanvases:
    # Re-contracted 2026-08-30 for the list/discovery rewrite of
    # tools.canvas_crud_tool.list_canvases (latest-per-canvas via a
    # ROW_NUMBER() window + Python-side search/paging). The previous
    # mock-chain (filter/order_by/all on a Magic db) no longer matches the
    # implementation's query shape, so these now run against real
    # CanvasAudit rows on the test session. Intent unchanged: dedupe
    # latest-wins, deleted skip/include, type filter, empty, exception.

    def _audit(self, canvas_id, action_type, canvas_type="docs", details=None,
               created_at=None, user_id="u-1"):
        return SimpleNamespace(canvas_id=canvas_id, action_type=action_type,
                               canvas_type=canvas_type,
                               details_json=details if details is not None else {"title": "T"},
                               created_at=created_at,
                               user_id=user_id)

    async def _run(self, audits, canvas_type=None, include_deleted=False, db_session=None):
        import uuid as _uuid

        from core.models import CanvasAudit

        for a in audits:
            db_session.add(CanvasAudit(
                id=f"a-{_uuid.uuid4()}",
                canvas_id=a.canvas_id,
                tenant_id="t-1",
                canvas_type=a.canvas_type,
                action_type=a.action_type,
                user_id=a.user_id,
                details_json=a.details_json,
                created_at=a.created_at,  # may be None — serialization must cope
            ))
        db_session.commit()

        @contextmanager
        def _sess():
            yield db_session

        import tools.canvas_crud_tool as mod
        with patch("core.database.get_db_session", _sess):
            return await mod.list_canvases("u-1", canvas_type=canvas_type,
                                           include_deleted=include_deleted)

    async def test_empty(self, db_session):
        res = await self._run([], db_session=db_session)
        assert res["success"] is True and res["count"] == 0

    async def test_dedupe_and_skip_deleted(self, db_session):
        base = datetime(2026, 1, 1)
        audits = [self._audit("c-1", "present", details={"title": "A"}, created_at=base),
                  self._audit("c-1", "update", details={"title": "B"},
                              created_at=base.replace(day=2)),
                  self._audit("c-2", "delete", details={}, created_at=base.replace(day=3))]
        res = await self._run(audits, db_session=db_session)
        assert res["success"] is True and res["count"] == 1
        assert res["canvases"][0]["canvas_id"] == "c-1"
        assert res["canvases"][0]["title"] == "B"

    async def test_include_deleted(self, db_session):
        audits = [self._audit("c-2", "delete", details={})]
        res = await self._run(audits, include_deleted=True, db_session=db_session)
        assert res["count"] == 1 and res["canvases"][0]["deleted"] is True

    async def test_type_filter_and_none_created_at(self, db_session):
        # The old mock-suite asserted last_updated is None when the source
        # row's created_at is None — unreachable via the ORM (server_default
        # func.now() stamps every insert), so the re-contract asserts the
        # real behavior: the canvas lists under its type filter with a
        # server-stamped last_updated. The None-serialization guard itself
        # is unchanged in list_canvases (`isoformat() if created_at else None`).
        audits = [self._audit("c-1", "present", canvas_type="sheets",
                              created_at=None)]
        res = await self._run(audits, canvas_type="sheets", db_session=db_session)
        assert res["count"] == 1
        assert res["canvases"][0]["last_updated"] is not None

    async def test_exception(self):
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("boom")
        import tools.canvas_crud_tool as mod
        with _patch_db(db):
            res = await mod.list_canvases("u-1")
        assert res["success"] is False


# ============================================================================
# tools/platform_management_tool.py
# ============================================================================

class TestPlatformSettings:
    def _db(self):
        db = _cm_db()
        s1 = SimpleNamespace(setting_key="k1", setting_value="v1")
        db.query.return_value.filter.return_value.all.return_value = [s1]
        return db

    async def test_get_settings(self):
        from tools.platform_management_tool import get_platform_settings
        db = self._db()
        with patch("core.database.SessionLocal", return_value=db):
            res = await get_platform_settings({"workspace_id": "ws-1"})
        assert res == {"k1": "v1"}

    async def test_get_settings_default_ws(self):
        from tools.platform_management_tool import get_platform_settings
        db = self._db()
        with patch("core.database.SessionLocal", return_value=db):
            res = await get_platform_settings(None)
        assert res == {"k1": "v1"}

    async def test_get_settings_error(self):
        from tools.platform_management_tool import get_platform_settings
        db = _cm_db()
        db.query.side_effect = RuntimeError("boom")
        with patch("core.database.SessionLocal", return_value=db):
            res = await get_platform_settings(None)
        assert "error" in res

    async def test_update_existing(self):
        from tools.platform_management_tool import update_platform_setting
        setting = SimpleNamespace(setting_key="k", setting_value="old")
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = setting
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_platform_setting("k", "new", {"workspace_id": "ws-1"})
        assert "successfully updated" in msg and setting.setting_value == "new"

    async def test_update_create(self):
        from tools.platform_management_tool import update_platform_setting
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.TenantSetting") as TS:
            msg = await update_platform_setting("k", "v")
        assert "successfully updated" in msg
        TS.assert_called_once_with(tenant_id="default", setting_key="k", setting_value="v")

    async def test_update_error(self):
        from tools.platform_management_tool import update_platform_setting
        db = _cm_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("boom")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_platform_setting("k", "v")
        assert msg.startswith("Error")


class TestUpdateTenantProfile:
    def _ws(self, tenant_id="t-1"):
        return SimpleNamespace(tenant_id=tenant_id)

    def _tenant(self, **kw):
        defaults = dict(id="t-1", name="N", billing_email="b@c", metadata_json={},
                        budget_limit_usd=10.0)
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    async def _run(self, ws, tenant, **kwargs):
        from tools.platform_management_tool import update_tenant_profile
        db = _cm_db()
        db.query.return_value.filter.return_value.first.side_effect = [ws, tenant]
        with patch("core.database.SessionLocal", return_value=db):
            return await update_tenant_profile(context={"workspace_id": "ws-1"}, **kwargs)

    async def test_no_workspace_default_tenant_missing(self):
        from tools.platform_management_tool import update_tenant_profile
        db = _cm_db()
        db.query.return_value.filter.return_value.first.side_effect = [None, None]
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant_profile(name="X")
        assert "not found" in msg

    async def test_tenant_missing_non_default(self):
        from tools.platform_management_tool import update_tenant_profile
        db = _cm_db()
        db.query.return_value.filter.return_value.first.side_effect = [self._ws(), None]
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant_profile(name="X")
        assert "not found" in msg

    async def test_no_updates(self):
        msg = await self._run(self._ws(), self._tenant())
        assert msg == "No updates provided."

    async def test_full_update(self):
        tenant = self._tenant()
        msg = await self._run(self._ws(), tenant, name="New", billing_email="n@c",
                              logo_url="http://x", primary_color="#fff",
                              budget_limit_usd=99.0)
        assert "name" in msg and "budget_limit_usd" in msg
        assert tenant.metadata_json == {"logo_url": "http://x", "primary_color": "#fff"}

    async def test_metadata_missing(self):
        tenant = self._tenant(metadata_json=None)
        msg = await self._run(self._ws(), tenant, logo_url="http://x")
        assert "logo_url" in msg

    async def test_error(self):
        from tools.platform_management_tool import update_tenant_profile
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("boom")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant_profile(name="X")
        assert msg.startswith("Error")


class TestSetByokApiKey:
    async def test_no_tenant(self):
        from tools.platform_management_tool import set_byok_api_key
        msg = await set_byok_api_key("openai", "sk-x")
        assert "Could not resolve" in msg

    async def test_success(self):
        from tools.platform_management_tool import set_byok_api_key
        db = _cm_db()
        manager = MagicMock()
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.byok_endpoints.BYOKManager", return_value=manager):
            msg = await set_byok_api_key("openai", "sk-x", {"workspace_id": "ws-1"})
        assert "Successfully" in msg
        manager.store_api_key.assert_called_once()
        kwargs = manager.store_api_key.call_args.kwargs
        assert kwargs["provider_id"] == "openai" and kwargs["environment"] == "production"

    async def test_value_error(self):
        from tools.platform_management_tool import set_byok_api_key
        db = _cm_db()
        manager = MagicMock()
        manager.store_api_key.side_effect = ValueError("bad provider")
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.byok_endpoints.BYOKManager", return_value=manager):
            msg = await set_byok_api_key("nope", "x", {"workspace_id": "ws-1"})
        assert "invalid provider" in msg
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    async def test_generic_error(self):
        from tools.platform_management_tool import set_byok_api_key
        db = _cm_db()
        manager = MagicMock()
        manager.store_api_key.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.byok_endpoints.BYOKManager", return_value=manager):
            msg = await set_byok_api_key("openai", "x", {"workspace_id": "ws-1"})
        assert msg == "Error setting BYOK API key"


class TestListTenantMembers:
    async def test_no_workspace(self):
        from tools.platform_management_tool import list_tenant_members
        msg = await list_tenant_members(None)
        assert "Could not resolve" in msg

    async def test_workspace_not_found(self):
        from tools.platform_management_tool import list_tenant_members
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await list_tenant_members({"workspace_id": "ws-1"})
        assert "not found" in msg

    async def test_no_members(self):
        from tools.platform_management_tool import list_tenant_members
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            tenant_id="t-1")
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("core.database.SessionLocal", return_value=db):
            msg = await list_tenant_members({"workspace_id": "ws-1"})
        assert "No members" in msg

    async def test_members(self):
        from tools.platform_management_tool import list_tenant_members
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            tenant_id="t-1")
        m1 = SimpleNamespace(name="Alice", email="a@b.c", id="u-1", role="admin",
                             status="active")
        m2 = SimpleNamespace(name=None, email="b@b.c", id="u-2", role=None,
                             status=None)
        db.query.return_value.filter.return_value.all.return_value = [m1, m2]
        with patch("core.database.SessionLocal", return_value=db):
            msg = await list_tenant_members({"workspace_id": "ws-1"})
        assert "Alice" in msg and "b@b.c" in msg

    async def test_error(self):
        from tools.platform_management_tool import list_tenant_members
        db = _cm_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await list_tenant_members({"workspace_id": "ws-1"})
        assert msg == "Error listing tenant members"


class TestManageTenantMember:
    def _db(self):
        return _cm_db()

    async def test_user_not_found(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "update_role", role="admin")
        assert "not found" in msg

    async def test_update_role_no_role(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "update_role")
        assert "role is required" in msg

    async def test_update_role(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        user = SimpleNamespace(role="member", is_active=True)
        db.query.return_value.filter.return_value.first.return_value = user
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "update_role", role="admin")
        assert user.role == "admin" and "role updated" in msg

    async def test_deactivate(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        user = SimpleNamespace(role="member", is_active=True)
        db.query.return_value.filter.return_value.first.return_value = user
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "deactivate")
        assert user.is_active is False and "deactivated" in msg

    async def test_reactivate(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        user = SimpleNamespace(role="member", is_active=False)
        db.query.return_value.filter.return_value.first.return_value = user
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "reactivate")
        assert user.is_active is True and "reactivated" in msg

    async def test_unknown_action(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "explode")
        assert "Unknown action" in msg

    async def test_error(self):
        from tools.platform_management_tool import manage_tenant_member
        db = self._db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_tenant_member("u-1", "update_role", role="admin")
        assert msg == "Error managing tenant member"
        db.rollback.assert_called_once()


class TestManageWorkspace:
    async def test_no_tenant_id(self):
        from tools.platform_management_tool import manage_workspace
        msg = await manage_workspace("W")
        assert "Could not resolve tenant" in msg

    async def test_tenant_from_workspace_lookup(self):
        from tools.platform_management_tool import manage_workspace
        db_temp = _cm_db()
        db_temp.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=MagicMock()) as sl:
            sl.side_effect = [db_temp, MagicMock()]
            msg = await manage_workspace("W", context={"workspace_id": "ws-1"})
        assert "Could not resolve tenant" in msg

    async def test_tenant_from_workspace_found(self):
        from tools.platform_management_tool import manage_workspace
        db_temp = _cm_db()
        db_temp.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            tenant_id="t-1")
        db = _cm_db()
        ws = SimpleNamespace(id="ws-new")
        db.add.side_effect = lambda obj: None
        with patch("core.database.SessionLocal", side_effect=[db_temp, db]) as sl:
            msg = await manage_workspace("W", description="d", is_startup=True,
                                         context={"workspace_id": "ws-1"})
        assert "created" in msg

    async def test_create_direct(self):
        from tools.platform_management_tool import manage_workspace
        db = _cm_db()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_workspace("W", context={"tenant_id": "t-1"})
        assert "created" in msg

    async def test_update_missing_id(self):
        from tools.platform_management_tool import manage_workspace
        with patch("core.database.SessionLocal", return_value=MagicMock()):
            msg = await manage_workspace("W", action="update", context={"tenant_id": "t-1"})
        assert "workspace_id is required" in msg

    async def test_update_not_found(self):
        from tools.platform_management_tool import manage_workspace
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_workspace("W", action="update", workspace_id="w-1",
                                         context={"tenant_id": "t-1"})
        assert "not found" in msg

    async def test_update_success(self):
        from tools.platform_management_tool import manage_workspace
        db = _cm_db()
        ws = SimpleNamespace(name="Old")
        db.query.return_value.filter.return_value.first.return_value = ws
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_workspace("New", action="update", workspace_id="w-1",
                                         description="d", context={"tenant_id": "t-1"})
        assert "updated" in msg and ws.name == "New" and ws.description == "d"

    async def test_unknown_action(self):
        from tools.platform_management_tool import manage_workspace
        with patch("core.database.SessionLocal", return_value=MagicMock()):
            msg = await manage_workspace("W", action="explode", context={"tenant_id": "t-1"})
        assert "Unknown action" in msg

    async def test_error(self):
        from tools.platform_management_tool import manage_workspace
        db = _cm_db()
        db.add.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_workspace("W", context={"tenant_id": "t-1"})
        assert msg == "Error managing workspace"


class TestManageTeam:
    def _db(self):
        return _cm_db()

    def _team_db(self, team_id="team-1"):
        """DB where the Team row gets its id assigned at flush (like the ORM)."""
        db = _cm_db()
        added = {}

        def _add(obj):
            added["obj"] = obj

        def _flush():
            added["obj"].id = team_id

        db.add.side_effect = _add
        db.flush.side_effect = _flush
        return db

    async def test_no_tenant(self):
        from tools.platform_management_tool import manage_team
        msg = await manage_team("T")
        assert "Could not resolve" in msg

    async def test_create(self):
        from tools.platform_management_tool import manage_team
        db = self._team_db()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_team("T", context={"workspace_id": "ws-1"})
        assert "created" in msg and "team-1" in msg

    async def test_update_missing_id(self):
        from tools.platform_management_tool import manage_team
        with patch("core.database.SessionLocal", return_value=self._db()):
            msg = await manage_team("T", action="update", context={"workspace_id": "ws-1"})
        assert "team_id is required" in msg

    async def test_update_not_found(self):
        from tools.platform_management_tool import manage_team
        db = self._db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_team("T", action="update", team_id="t-1",
                                    context={"workspace_id": "ws-1"})
        assert "not found" in msg

    async def test_update_success(self):
        from tools.platform_management_tool import manage_team
        db = self._db()
        team = SimpleNamespace(id="t-1", name="Old")
        db.query.return_value.filter.return_value.first.return_value = team
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_team("New", action="update", team_id="t-1",
                                    context={"workspace_id": "ws-1"})
        assert "updated" in msg and team.name == "New"

    async def test_unknown_action(self):
        from tools.platform_management_tool import manage_team
        with patch("core.database.SessionLocal", return_value=self._db()):
            msg = await manage_team("T", action="explode", context={"workspace_id": "ws-1"})
        assert "Unknown action" in msg

    async def test_add_members(self):
        from tools.platform_management_tool import manage_team
        db = self._team_db()
        db.query.return_value.filter.return_value.first.side_effect = [
            SimpleNamespace(id="u-1"), None]
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_team("T", context={"workspace_id": "ws-1"},
                                    add_members=["u-1"])
        assert "Added 1 members" in msg
        db.execute.assert_called_once()

    async def test_add_members_user_missing(self):
        from tools.platform_management_tool import manage_team
        db = self._team_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_team("T", context={"workspace_id": "ws-1"},
                                    add_members=["ghost"])
        assert "Added 0 members" in msg

    async def test_error(self):
        from tools.platform_management_tool import manage_team
        db = self._db()
        db.add.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await manage_team("T", context={"workspace_id": "ws-1"})
        assert msg == "Error managing team"


class TestPlatformStubs:
    async def test_create_tenant(self):
        from tools.platform_management_tool import create_tenant
        db = _cm_db()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await create_tenant("T")
        assert "created" in msg

    async def test_create_tenant_error(self):
        from tools.platform_management_tool import create_tenant
        db = _cm_db()
        db.add.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await create_tenant("T")
        assert msg == "Error creating tenant"

    async def test_update_tenant(self):
        from tools.platform_management_tool import update_tenant
        db = _cm_db()
        tenant = SimpleNamespace(id="t-1", name="Old")
        db.query.return_value.filter.return_value.first.return_value = tenant
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant("t-1", name="New")
        assert "updated" in msg and tenant.name == "New"

    async def test_update_tenant_not_found(self):
        from tools.platform_management_tool import update_tenant
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant("t-1")
        assert "not found" in msg

    async def test_update_tenant_no_name(self):
        from tools.platform_management_tool import update_tenant
        db = _cm_db()
        tenant = SimpleNamespace(id="t-1", name="Old")
        db.query.return_value.filter.return_value.first.return_value = tenant
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant("t-1")
        assert "updated" in msg

    async def test_update_tenant_error(self):
        from tools.platform_management_tool import update_tenant
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_tenant("t-1")
        assert msg == "Error updating tenant"

    async def test_delete_tenant(self):
        from tools.platform_management_tool import delete_tenant
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t-1")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_tenant("t-1")
        assert "deleted" in msg
        db.delete.assert_called_once()

    async def test_delete_tenant_not_found(self):
        from tools.platform_management_tool import delete_tenant
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_tenant("t-1")
        assert "not found" in msg

    async def test_delete_tenant_error(self):
        from tools.platform_management_tool import delete_tenant
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_tenant("t-1")
        assert msg == "Error deleting tenant"

    async def test_create_workspace(self):
        from tools.platform_management_tool import create_workspace
        db = _cm_db()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await create_workspace("W", "t-1")
        assert "created" in msg

    async def test_create_workspace_error(self):
        from tools.platform_management_tool import create_workspace
        db = _cm_db()
        db.add.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await create_workspace("W", "t-1")
        assert msg == "Error creating workspace"

    async def test_update_workspace(self):
        from tools.platform_management_tool import update_workspace
        db = _cm_db()
        ws = SimpleNamespace(id="w-1", name="Old")
        db.query.return_value.filter.return_value.first.return_value = ws
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_workspace("w-1", name="New")
        assert "updated" in msg and ws.name == "New"

    async def test_update_workspace_not_found(self):
        from tools.platform_management_tool import update_workspace
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_workspace("w-1")
        assert "not found" in msg

    async def test_update_workspace_error(self):
        from tools.platform_management_tool import update_workspace
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_workspace("w-1")
        assert msg == "Error updating workspace"

    async def test_delete_workspace(self):
        from tools.platform_management_tool import delete_workspace
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="w-1")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_workspace("w-1")
        assert "deleted" in msg

    async def test_delete_workspace_not_found(self):
        from tools.platform_management_tool import delete_workspace
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_workspace("w-1")
        assert "not found" in msg

    async def test_delete_workspace_error(self):
        from tools.platform_management_tool import delete_workspace
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_workspace("w-1")
        assert msg == "Error deleting workspace"

    async def test_create_team(self):
        from tools.platform_management_tool import create_team
        db = _cm_db()
        with patch("core.database.SessionLocal", return_value=db):
            msg = await create_team("T", "w-1")
        assert "created" in msg

    async def test_create_team_error(self):
        from tools.platform_management_tool import create_team
        db = _cm_db()
        db.add.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await create_team("T", "w-1")
        assert msg == "Error creating team"

    async def test_update_team(self):
        from tools.platform_management_tool import update_team
        db = _cm_db()
        team = SimpleNamespace(id="t-1", name="Old")
        db.query.return_value.filter.return_value.first.return_value = team
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_team("t-1", name="New")
        assert "updated" in msg and team.name == "New"

    async def test_update_team_not_found(self):
        from tools.platform_management_tool import update_team
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_team("t-1")
        assert "not found" in msg

    async def test_update_team_error(self):
        from tools.platform_management_tool import update_team
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await update_team("t-1")
        assert msg == "Error updating team"

    async def test_delete_team(self):
        from tools.platform_management_tool import delete_team
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="t-1")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_team("t-1")
        assert "deleted" in msg

    async def test_delete_team_not_found(self):
        from tools.platform_management_tool import delete_team
        db = _cm_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_team("t-1")
        assert "not found" in msg

    async def test_delete_team_error(self):
        from tools.platform_management_tool import delete_team
        db = _cm_db()
        db.query.return_value.filter.side_effect = RuntimeError("x")
        with patch("core.database.SessionLocal", return_value=db):
            msg = await delete_team("t-1")
        assert msg == "Error deleting team"

    async def test_add_member_to_workspace(self):
        from tools.platform_management_tool import add_member_to_workspace
        msg = await add_member_to_workspace("u-1", "w-1")
        assert "added" in msg

    async def test_remove_member_from_workspace(self):
        from tools.platform_management_tool import remove_member_from_workspace
        msg = await remove_member_from_workspace("u-1", "w-1")
        assert "removed" in msg

    async def test_add_member_to_team(self):
        from tools.platform_management_tool import add_member_to_team
        msg = await add_member_to_team("u-1", "t-1")
        assert "added" in msg

    async def test_remove_member_from_team(self):
        from tools.platform_management_tool import remove_member_from_team
        msg = await remove_member_from_team("u-1", "t-1")
        assert "removed" in msg
