"""Coverage-push tests for backend/tools (W75c, part B).

Standalone >=95% statement coverage for:
- tools/device_tool.py
- tools/mini_app_tool.py
- tools/canvas_tool.py
- tools/registry.py

Style: mocked deps, zero LLM spend, no network, no real DB.
"""

import importlib
import sys
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.feature_flags import FeatureFlags


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


def _gov_flag(value):
    return patch.object(FeatureFlags, "should_enforce_governance",
                        classmethod(lambda cls, feature: value))


# ============================================================================
# tools/device_tool.py
# ============================================================================

class TestDeviceImportErrorBranch:
    def test_websocket_unavailable_import(self):
        import tools.device_tool as mod
        with patch.dict(sys.modules, {"api.device_websocket": None}):
            reloaded = importlib.reload(mod)
            assert reloaded.WEBSOCKET_AVAILABLE is False
        importlib.reload(mod)


class TestDeviceSessionManager:
    def _mgr(self):
        from tools.device_tool import DeviceSessionManager
        return DeviceSessionManager(session_timeout_minutes=1)

    def test_create_and_get(self):
        mgr = self._mgr()
        s = mgr.create_session("u-1", "dev-1", "screen_record", agent_id="a-1",
                               configuration={"k": "v"})
        assert mgr.get_session(s["session_id"]) is s
        assert s["configuration"] == {"k": "v"} and s["status"] == "active"

    def test_get_missing(self):
        mgr = self._mgr()
        assert mgr.get_session("nope") is None

    def test_close_session(self):
        mgr = self._mgr()
        s = mgr.create_session("u-1", "dev-1", "screen_record")
        assert mgr.close_session(s["session_id"]) is True
        assert s["status"] == "closed" and "closed_at" in s
        assert mgr.close_session(s["session_id"]) is False

    def test_cleanup_expired(self):
        mgr = self._mgr()
        s1 = mgr.create_session("u-1", "dev-1", "screen_record")
        s2 = mgr.create_session("u-1", "dev-1", "screen_record")
        old = dict(s1)
        old["last_used"] = datetime(2000, 1, 1)
        mgr.sessions[s1["session_id"]] = old
        assert mgr.cleanup_expired_sessions() == 1
        assert s1["session_id"] not in mgr.sessions
        assert s2["session_id"] in mgr.sessions

    def test_cleanup_no_expired(self):
        mgr = self._mgr()
        mgr.create_session("u-1", "dev-1", "screen_record")
        assert mgr.cleanup_expired_sessions() == 0


class TestDeviceSessionManagerSingleton:
    def test_singleton(self):
        from tools.device_tool import get_device_session_manager
        with patch("tools.device_tool._device_session_manager", None):
            m1 = get_device_session_manager()
            m2 = get_device_session_manager()
            assert m1 is m2


class TestCreateDeviceAudit:
    def test_audit_created(self):
        from tools.device_tool import _create_device_audit
        db = MagicMock()
        audit = _create_device_audit(
            db=db, user_id="u-1", device_node_id="dev-1", action_type="camera_snap",
            action_params={"camera_id": "c"}, success=True,
            result_summary="ok", result_data={"x": 1}, file_path="/tmp/a.png",
            duration_ms=5, agent_id="a-1", agent_execution_id="e-1",
            session_id="s-1", governance_check_passed=True)
        assert audit is not None
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestCheckDeviceGovernance:
    def _gov(self, allowed):
        gov = MagicMock()
        gov.can_perform_action.return_value = {"allowed": allowed, "reason": "r"}
        return gov

    async def test_disabled(self):
        from tools.device_tool import _check_device_governance
        with _gov_flag(False):
            res = await _check_device_governance(MagicMock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is True and res["governance_check_passed"] is True

    async def test_allowed(self):
        from tools.device_tool import _check_device_governance
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service",
                   return_value=self._gov(True)):
            res = await _check_device_governance(MagicMock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is True and res["governance_check_passed"] is True

    async def test_denied(self):
        from tools.device_tool import _check_device_governance
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service",
                   return_value=self._gov(False)):
            res = await _check_device_governance(MagicMock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is False and res["governance_check_passed"] is False

    async def test_exception_fail_open(self):
        from tools.device_tool import _check_device_governance
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service",
                   side_effect=RuntimeError("gov down")):
            res = await _check_device_governance(MagicMock(), "a-1", "device_camera_snap", "u-1")
        assert res["allowed"] is True and res["governance_check_passed"] is False


class _DeviceEnv:
    """Shared fixtures for device function tests."""

    def setup(self):
        self.db = MagicMock()
        self.audit = Mock()
        self.send = AsyncMock(return_value={"success": True, "data": {}, "file_path": "/tmp/x"})
        self._patches = [
            patch("tools.device_tool._create_device_audit", self.audit),
            patch("tools.device_tool.is_device_online", return_value=True),
            patch("tools.device_tool.send_device_command", self.send),
        ]
        for p in self._patches:
            p.start()

    def teardown(self):
        for p in self._patches:
            p.stop()


@pytest.fixture()
def dev_env():
    env = _DeviceEnv()
    env.setup()
    yield env
    env.teardown()


@pytest.fixture()
def gov_allow():
    with _gov_flag(True), \
         patch("core.service_factory.ServiceFactory.get_governance_service") as g:
        g.return_value.can_perform_action.return_value = {"allowed": True, "reason": "ok"}
        yield g


class TestDeviceCameraSnap:
    async def test_governance_blocked(self, dev_env):
        from tools.device_tool import device_camera_snap
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service") as g:
            g.return_value.can_perform_action.return_value = {"allowed": False, "reason": "no"}
            res = await device_camera_snap(dev_env.db, "u-1", "dev-1", agent_id="a-1")
        assert res["success"] is False and res["governance_blocked"] is True

    async def test_no_agent_skips_governance(self, dev_env):
        from tools.device_tool import device_camera_snap
        res = await device_camera_snap(dev_env.db, "u-1", "dev-1")
        assert res["success"] is True

    async def test_ws_unavailable(self, dev_env):
        from tools.device_tool import device_camera_snap
        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            res = await device_camera_snap(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "WebSocket" in res["error"]
        dev_env.audit.assert_called_once()

    async def test_device_offline(self, dev_env):
        from tools.device_tool import device_camera_snap
        with patch("tools.device_tool.is_device_online", return_value=False):
            res = await device_camera_snap(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "not currently connected" in res["error"]

    async def test_response_failure(self, dev_env):
        from tools.device_tool import device_camera_snap
        dev_env.send.return_value = {"success": False, "error": "denied"}
        res = await device_camera_snap(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "denied" in res["error"]

    async def test_success(self, dev_env, gov_allow):
        from tools.device_tool import device_camera_snap
        dev_env.send.return_value = {"success": True, "file_path": "/tmp/s.png",
                                     "data": {"base64_data": "abc"}}
        res = await device_camera_snap(dev_env.db, "u-1", "dev-1", agent_id="a-1",
                                       camera_id="c2", resolution="800x600",
                                       save_path="/tmp")
        assert res["success"] is True
        assert res["file_path"] == "/tmp/s.png" and res["base64_data"] == "abc"
        assert res["camera_id"] == "c2"
        kwargs = dev_env.send.await_args.kwargs
        assert kwargs["command"] == "camera_snap"
        assert kwargs["params"]["camera_id"] == "c2"
        dev_env.audit.assert_called_once()

    async def test_exception_no_governance_info(self, dev_env):
        from tools.device_tool import device_camera_snap
        dev_env.send.side_effect = RuntimeError("boom")
        res = await device_camera_snap(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "boom" in res["error"]


class TestDeviceScreenRecordStart:
    async def test_governance_blocked(self, dev_env):
        from tools.device_tool import device_screen_record_start
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service") as g:
            g.return_value.can_perform_action.return_value = {"allowed": False, "reason": "no"}
            res = await device_screen_record_start(dev_env.db, "u-1", "dev-1", agent_id="a-1")
        assert res["success"] is False and res["governance_blocked"] is True

    async def test_device_not_found(self, dev_env):
        from tools.device_tool import device_screen_record_start
        dev_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await device_screen_record_start(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "not found" in res["error"]

    async def test_duration_exceeds_max(self, dev_env):
        from tools.device_tool import device_screen_record_start
        dev_env.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="d1")
        with patch("tools.device_tool.DEVICE_SCREEN_RECORD_MAX_DURATION", 60):
            res = await device_screen_record_start(dev_env.db, "u-1", "dev-1", duration_seconds=120)
        assert res["success"] is False and "exceeds maximum" in res["error"]

    async def test_success_with_ws(self, dev_env, gov_allow):
        from tools.device_tool import device_screen_record_start
        dev = SimpleNamespace(id="d1")
        dev_env.db.query.return_value.filter.return_value.first.return_value = dev
        res = await device_screen_record_start(dev_env.db, "u-1", "dev-1", agent_id="a-1",
                                               duration_seconds=10, audio_enabled=True,
                                               resolution="1280x720", output_format="webm")
        assert res["success"] is True and res["session_id"]
        assert dev_env.send.await_args.kwargs["params"]["duration_seconds"] == 10
        dev_env.audit.assert_called_once()

    async def test_ws_response_failure_marks_session_failed(self, dev_env):
        from tools.device_tool import device_screen_record_start
        dev_env.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="d1")
        dev_env.send.return_value = {"success": False, "error": "nope"}
        res = await device_screen_record_start(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "nope" in res["error"]

    async def test_ws_unavailable_skips_command(self, dev_env):
        from tools.device_tool import device_screen_record_start
        dev_env.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="d1")
        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            res = await device_screen_record_start(dev_env.db, "u-1", "dev-1")
        assert res["success"] is True
        dev_env.send.assert_not_called()

    async def test_exception(self, dev_env):
        from tools.device_tool import device_screen_record_start
        dev_env.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="d1")
        dev_env.send.side_effect = RuntimeError("boom")
        res = await device_screen_record_start(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "boom" in res["error"]


class TestDeviceScreenRecordStop:
    def _mgr(self, session):
        mgr = MagicMock()
        mgr.get_session.return_value = session
        return mgr

    async def test_session_not_found(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        mgr = self._mgr(None)
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is False and "not found" in res["error"]

    async def test_wrong_user(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        mgr = self._mgr({"user_id": "other", "device_node_id": "d1",
                         "created_at": datetime.now(), "agent_id": None})
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is False and "does not belong" in res["error"]

    async def test_success_with_file(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        created = datetime.now()
        session = {"user_id": "u-1", "device_node_id": "d1", "created_at": created,
                   "agent_id": "a-1"}
        mgr = self._mgr(session)
        dev_env.send.return_value = {"success": True, "file_path": "/tmp/rec.mp4",
                                     "data": {"duration_seconds": 5}}
        db_session = SimpleNamespace(status="active")
        dev_env.db.query.return_value.filter.return_value.first.return_value = db_session
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is True and res["file_path"] == "/tmp/rec.mp4"
        assert res["duration_seconds"] == 5
        assert db_session.status == "closed"
        mgr.close_session.assert_called_once_with("s-1")
        dev_env.audit.assert_called_once()

    async def test_ws_failure_continues(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        created = datetime.now()
        session = {"user_id": "u-1", "device_node_id": "d1", "created_at": created,
                   "agent_id": None}
        mgr = self._mgr(session)
        dev_env.send.return_value = {"success": False, "error": "stop failed"}
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is True
        assert res["file_path"] == f"/tmp/recording_s-1.mp4"

    async def test_ws_exception_continues(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        created = datetime.now()
        session = {"user_id": "u-1", "device_node_id": "d1", "created_at": created,
                   "agent_id": None}
        mgr = self._mgr(session)
        dev_env.send.side_effect = ValueError("boom")
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is True

    async def test_ws_unavailable(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        created = datetime.now()
        session = {"user_id": "u-1", "device_node_id": "d1", "created_at": created,
                   "agent_id": None}
        mgr = self._mgr(session)
        dev_env.db.query.return_value.filter.return_value.first.return_value = None
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr), \
             patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is True
        dev_env.send.assert_not_called()

    async def test_exception(self, dev_env):
        from tools.device_tool import device_screen_record_stop
        created = datetime.now()
        session = {"user_id": "u-1", "device_node_id": "d1", "created_at": created,
                   "agent_id": None}
        mgr = self._mgr(session)
        dev_env.send.side_effect = RuntimeError("boom")
        with patch("tools.device_tool.get_device_session_manager", return_value=mgr):
            res = await device_screen_record_stop(dev_env.db, "u-1", "s-1")
        assert res["success"] is False and "boom" in res["error"]


class TestDeviceGetLocation:
    async def test_governance_blocked(self, dev_env):
        from tools.device_tool import device_get_location
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service") as g:
            g.return_value.can_perform_action.return_value = {"allowed": False, "reason": "no"}
            res = await device_get_location(dev_env.db, "u-1", "dev-1", agent_id="a-1")
        assert res["success"] is False and res["governance_blocked"] is True

    async def test_ws_unavailable(self, dev_env):
        from tools.device_tool import device_get_location
        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            res = await device_get_location(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False

    async def test_offline(self, dev_env):
        from tools.device_tool import device_get_location
        with patch("tools.device_tool.is_device_online", return_value=False):
            res = await device_get_location(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False

    async def test_response_failure(self, dev_env):
        from tools.device_tool import device_get_location
        dev_env.send.return_value = {"success": False, "error": "no gps"}
        res = await device_get_location(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "no gps" in res["error"]

    async def test_success(self, dev_env, gov_allow):
        from tools.device_tool import device_get_location
        dev_env.send.return_value = {"success": True, "data": {"latitude": 1.5, "longitude": 2.5,
                                                               "altitude": 3, "timestamp": "t"}}
        res = await device_get_location(dev_env.db, "u-1", "dev-1", agent_id="a-1",
                                        accuracy="low")
        assert res["success"] is True and res["latitude"] == 1.5
        assert res["accuracy"] == "low"
        assert dev_env.send.await_args.kwargs["params"]["accuracy"] == "low"

    async def test_exception(self, dev_env):
        from tools.device_tool import device_get_location
        dev_env.send.side_effect = RuntimeError("boom")
        res = await device_get_location(dev_env.db, "u-1", "dev-1")
        assert res["success"] is False and "boom" in res["error"]


class TestDeviceSendNotification:
    async def test_governance_blocked(self, dev_env):
        from tools.device_tool import device_send_notification
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service") as g:
            g.return_value.can_perform_action.return_value = {"allowed": False, "reason": "no"}
            res = await device_send_notification(dev_env.db, "u-1", "dev-1", "T", "B",
                                                 agent_id="a-1")
        assert res["success"] is False and res["governance_blocked"] is True

    async def test_ws_unavailable(self, dev_env):
        from tools.device_tool import device_send_notification
        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            res = await device_send_notification(dev_env.db, "u-1", "dev-1", "T", "B")
        assert res["success"] is False

    async def test_offline(self, dev_env):
        from tools.device_tool import device_send_notification
        with patch("tools.device_tool.is_device_online", return_value=False):
            res = await device_send_notification(dev_env.db, "u-1", "dev-1", "T", "B")
        assert res["success"] is False

    async def test_response_failure(self, dev_env):
        from tools.device_tool import device_send_notification
        dev_env.send.return_value = {"success": False, "error": "rejected"}
        res = await device_send_notification(dev_env.db, "u-1", "dev-1", "T", "B")
        assert res["success"] is False and "rejected" in res["error"]

    async def test_success(self, dev_env, gov_allow):
        from tools.device_tool import device_send_notification
        res = await device_send_notification(dev_env.db, "u-1", "dev-1", "Title", "Body",
                                             agent_id="a-1", icon="i", sound="s")
        assert res["success"] is True and res["title"] == "Title"
        kwargs = dev_env.send.await_args.kwargs
        assert kwargs["params"]["icon"] == "i" and kwargs["params"]["sound"] == "s"

    async def test_exception(self, dev_env):
        from tools.device_tool import device_send_notification
        dev_env.send.side_effect = RuntimeError("boom")
        res = await device_send_notification(dev_env.db, "u-1", "dev-1", "T", "B")
        assert res["success"] is False and "boom" in res["error"]


class TestDeviceExecuteCommand:
    def _device(self):
        return SimpleNamespace(id="d1")

    async def test_governance_blocked(self, dev_env):
        from tools.device_tool import device_execute_command
        with _gov_flag(True), \
             patch("core.service_factory.ServiceFactory.get_governance_service") as g:
            g.return_value.can_perform_action.return_value = {"allowed": False, "reason": "no"}
            res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls -la",
                                               agent_id="a-1")
        assert res["success"] is False and res["governance_blocked"] is True

    async def test_governance_read_action(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "cat x.txt",
                                           agent_id="a-1")
        assert res["success"] is True
        assert gov_allow.return_value.can_perform_action.call_args.args[1] == "device_shell_read"

    async def test_governance_monitor_action(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ps aux", agent_id="a-1")
        assert res["success"] is True
        assert gov_allow.return_value.can_perform_action.call_args.args[1] == "device_shell_monitor"

    async def test_device_not_found(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls", agent_id="a-1")
        assert res["success"] is False and "not found" in res["error"]

    async def test_not_whitelisted(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "rm -rf /",
                                           agent_id="a-1")
        assert res["success"] is False and "not in whitelist" in res["error"]

    async def test_timeout_exceeds_max(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls",
                                           agent_id="a-1", timeout_seconds=301)
        assert res["success"] is False and "exceeds maximum" in res["error"]

    async def test_ws_unavailable(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls",
                                               agent_id="a-1")
        assert res["success"] is False

    async def test_offline(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        with patch("tools.device_tool.is_device_online", return_value=False):
            res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls", agent_id="a-1")
        assert res["success"] is False

    async def test_response_failure(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        dev_env.send.return_value = {"success": False, "error": "exec failed"}
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls", agent_id="a-1")
        assert res["success"] is False and "exec failed" in res["error"]

    async def test_success(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        dev_env.send.return_value = {"success": True, "data": {"exit_code": 0,
                                                               "stdout": "out", "stderr": ""}}
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls -la",
                                           agent_id="a-1", working_dir="/tmp",
                                           timeout_seconds=5, environment={"K": "V"})
        assert res["success"] is True and res["exit_code"] == 0
        params = dev_env.send.await_args.kwargs["params"]
        assert params["working_dir"] == "/tmp" and params["timeout_seconds"] == 5
        assert params["environment"] == {"K": "V"}
        dev_env.audit.assert_called_once()

    async def test_exception(self, dev_env, gov_allow):
        from tools.device_tool import device_execute_command
        dev_env.db.query.return_value.filter.return_value.first.return_value = self._device()
        dev_env.send.side_effect = RuntimeError("boom")
        res = await device_execute_command(dev_env.db, "u-1", "dev-1", "ls", agent_id="a-1")
        assert res["success"] is False and "boom" in res["error"]


class TestDeviceInfoHelpers:
    async def test_get_device_info_found(self):
        from tools.device_tool import get_device_info
        db = MagicMock()
        dev = SimpleNamespace(id="1", device_id="d1", name="n", node_type="t",
                              status="online", platform="p", platform_version="1",
                              architecture="a", capabilities=["cam"],
                              capabilities_detailed={}, hardware_info={},
                              last_seen=datetime.now())
        db.query.return_value.filter.return_value.first.return_value = dev
        res = await get_device_info(db, "d1")
        assert res["device_id"] == "d1"

    async def test_get_device_info_last_seen_none(self):
        from tools.device_tool import get_device_info
        db = MagicMock()
        dev = SimpleNamespace(id="1", device_id="d1", name="n", node_type="t",
                              status="online", platform="p", platform_version="1",
                              architecture="a", capabilities=[], capabilities_detailed={},
                              hardware_info={}, last_seen=None)
        db.query.return_value.filter.return_value.first.return_value = dev
        res = await get_device_info(db, "d1")
        assert res["last_seen"] is None

    async def test_get_device_info_missing(self):
        from tools.device_tool import get_device_info
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert await get_device_info(db, "d1") is None

    async def test_list_devices_all(self):
        from tools.device_tool import list_devices
        db = MagicMock()
        dev = SimpleNamespace(id="1", device_id="d1", name="n", node_type="t",
                              status="online", platform="p", capabilities=[],
                              last_seen=None)
        db.query.return_value.filter.return_value.all.return_value = [dev]
        res = await list_devices(db, "u-1")
        assert len(res) == 1 and res[0]["last_seen"] is None

    async def test_list_devices_with_status(self):
        from tools.device_tool import list_devices
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        res = await list_devices(db, "u-1", status="online")
        assert res == []


class TestExecuteDeviceCommandWrapper:
    """Regression tests for the camera/location/notification branches.

    The wrapper previously called the inner functions with nonexistent
    kwargs (``timeout_seconds=`` / ``high_accuracy=``) and omitted
    ``device_node_id`` entirely, so all three branches raised TypeError
    and fell into the generic error path (device actions always failed).
    """

    async def test_camera_branch(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_camera_snap",
                   new=AsyncMock(return_value={"success": True})) as snap:
            res = await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "camera",
                                               {"timeout": 10})
        assert res["success"] is True
        kwargs = snap.await_args.kwargs
        assert kwargs["device_node_id"] == "dev-1" and kwargs["user_id"] == "u-1"

    async def test_location_branch(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_get_location",
                   new=AsyncMock(return_value={"success": True})) as loc:
            res = await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "location",
                                               {"high_accuracy": True})
        assert res["success"] is True
        kwargs = loc.await_args.kwargs
        assert kwargs["device_node_id"] == "dev-1" and kwargs["accuracy"] == "high"

    async def test_location_branch_low_accuracy(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_get_location",
                   new=AsyncMock(return_value={"success": True})) as loc:
            await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "location",
                                         {"high_accuracy": False})
        assert loc.await_args.kwargs["accuracy"] == "low"

    async def test_notification_branch(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_send_notification",
                   new=AsyncMock(return_value={"success": True})) as notif:
            res = await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "notification",
                                               {"title": "T", "body": "B"})
        assert res["success"] is True
        kwargs = notif.await_args.kwargs
        assert kwargs["device_node_id"] == "dev-1" and kwargs["title"] == "T"
        assert kwargs["body"] == "B"

    async def test_notification_defaults(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_send_notification",
                   new=AsyncMock(return_value={"success": True})) as notif:
            await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "notification", {})
        kwargs = notif.await_args.kwargs
        assert kwargs["title"] == "Notification" and kwargs["body"] == ""

    async def test_command_branch(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_execute_command",
                   new=AsyncMock(return_value={"success": True})) as exec_cmd:
            res = await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "command",
                                               {"command": "ls", "working_dir": "/tmp",
                                                "timeout": 5})
        assert res["success"] is True
        kwargs = exec_cmd.await_args.kwargs
        assert kwargs["device_node_id"] == "dev-1" and kwargs["timeout_seconds"] == 5

    async def test_unknown_type(self, dev_env):
        from tools.device_tool import execute_device_command
        res = await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "hack", {})
        assert res["success"] is False and "Unknown command type" in res["error"]

    async def test_exception(self, dev_env):
        from tools.device_tool import execute_device_command
        with patch("tools.device_tool.device_camera_snap",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            res = await execute_device_command(dev_env.db, "u-1", "a-1", "dev-1", "camera", {})
        assert res["success"] is False and "boom" in res["error"]


# ============================================================================
# tools/mini_app_tool.py
# ============================================================================

class _MiniAppEnv:
    def setup(self):
        self.db = MagicMock()
        self.db_patch = _patch_db(self.db)
        self.db_patch.start()
        self.ws = None

    def teardown(self):
        self.db_patch.stop()


@pytest.fixture()
def mini_env():
    env = _MiniAppEnv()
    env.setup()
    yield env
    env.teardown()


def _app(**kw):
    defaults = dict(id="app-1", name="MyApp", version=1, status="draft",
                    is_public=False, is_approved=False, created_by="u-1",
                    tenant_id="default", blueprint_canvas_id="canvas-1",
                    manifest={}, created_at=None)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _ctx(user_id="u-1", **kw):
    ctx = {"user_id": user_id}
    ctx.update(kw)
    return ctx


class TestMiniAppContextHelpers:
    def test_context_user_id_keys(self):
        from tools.mini_app_tool import _context_user_id
        assert _context_user_id(None) is None
        assert _context_user_id({}) is None
        assert _context_user_id({"userId": 42}) == "42"
        assert _context_user_id({"actor_id": "a1"}) == "a1"
        assert _context_user_id({"user": SimpleNamespace(id="u9")}) == "u9"
        assert _context_user_id({"user": SimpleNamespace(id=None)}) is None

    def test_viewer_no_user(self, mini_env):
        from tools.mini_app_tool import _viewer
        v = _viewer({})
        assert v.id is None and v.tenant_id is None and v.workspace_id is None

    def test_viewer_db_lookup(self, mini_env):
        from tools.mini_app_tool import _viewer
        row = SimpleNamespace(tenant_id="t-1", workspace_id="w-1", tier="autonomous")
        mini_env.db.query.return_value.filter.return_value.first.return_value = row
        v = _viewer(_ctx())
        assert v.id == "u-1" and v.tenant_id == "t-1" and v.workspace_id == "w-1"
        assert v.tier == "autonomous"

    def test_viewer_db_lookup_missing_row(self, mini_env):
        from tools.mini_app_tool import _viewer
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        v = _viewer(_ctx())
        assert v.id == "u-1" and v.tenant_id is None

    def test_viewer_db_lookup_exception(self, mini_env):
        from tools.mini_app_tool import _viewer
        mini_env.db.query.side_effect = RuntimeError("db down")
        v = _viewer(_ctx())
        assert v.id == "u-1" and v.tenant_id is None

    def test_require_actor(self, mini_env):
        from tools.mini_app_tool import _require_actor, _auth_error
        v = _require_actor({})
        assert v.id is None
        assert _auth_error()["success"] is False

    def test_context_tier(self, mini_env):
        from tools.mini_app_tool import _context_tier
        assert _context_tier({"tier": "supervised"}) == "supervised"
        assert _context_tier({"tier": None}) == "student"
        assert _context_tier({}) == "student"

    def test_context_tier_from_viewer(self, mini_env):
        from tools.mini_app_tool import _context_tier
        row = SimpleNamespace(tenant_id="t-1", workspace_id=None, tier="AUTONOMOUS")
        mini_env.db.query.return_value.filter.return_value.first.return_value = row
        assert _context_tier({"user_id": "u-1"}) == "autonomous"

    def test_require_tier(self, mini_env):
        from tools.mini_app_tool import _require_tier
        assert _require_tier({"tier": "student"}, "intern") is not None
        assert _require_tier({"tier": "autonomous"}, "intern") is None
        assert _require_tier({"tier": "bogus"}, "intern") is not None

    def test_resolve_record_target(self, mini_env):
        from tools.mini_app_tool import _resolve_record_target
        canvas = SimpleNamespace(id="c-1", mini_app_id="app-1", created_by="u-1")
        mini_env.db.query.return_value.filter.return_value.first.side_effect = [canvas, _app()]
        res = _resolve_record_target(mini_env.db, SimpleNamespace(id="u-1"), "c-1")
        assert res is canvas

    def test_resolve_record_target_not_found(self, mini_env):
        from tools.mini_app_tool import _resolve_record_target
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        assert _resolve_record_target(mini_env.db, SimpleNamespace(id="u-1"), "c-1") is None

    def test_resolve_record_target_not_instance(self, mini_env):
        from tools.mini_app_tool import _resolve_record_target
        canvas = SimpleNamespace(id="c-1", mini_app_id=None, created_by="u-1")
        mini_env.db.query.return_value.filter.return_value.first.return_value = canvas
        assert _resolve_record_target(mini_env.db, SimpleNamespace(id="u-1"), "c-1") is None

    def test_resolve_record_target_not_owner(self, mini_env):
        from tools.mini_app_tool import _resolve_record_target
        canvas = SimpleNamespace(id="c-1", mini_app_id="app-1", created_by="other")
        mini_env.db.query.return_value.filter.return_value.first.side_effect = [canvas, _app(created_by="other")]
        assert _resolve_record_target(mini_env.db, SimpleNamespace(id="u-1"), "c-1") is None

    def test_resolve_record_target_app_owner(self, mini_env):
        from tools.mini_app_tool import _resolve_record_target
        canvas = SimpleNamespace(id="c-1", mini_app_id="app-1", created_by="other")
        mini_env.db.query.return_value.filter.return_value.first.side_effect = [canvas, _app(created_by="u-1")]
        assert _resolve_record_target(mini_env.db, SimpleNamespace(id="u-1"), "c-1") is canvas


class TestMiniAppScaffold:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_scaffold
        res = await mini_app_scaffold({}, {})
        assert res["success"] is False and "Authenticated" in res["error"]

    async def test_no_name(self, mini_env):
        from tools.mini_app_tool import mini_app_scaffold
        res = await mini_app_scaffold({}, _ctx())
        assert res["success"] is False and "name is required" in res["error"]

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_scaffold
        app = _app(name="MyApp")
        mini_env.db.query.return_value.filter.return_value.first.return_value = app
        logic_svc = MagicMock()
        logic_svc.load_logic.return_value = {"source": "print('hi')"}
        with patch("core.mini_app_service.scaffold", return_value=(app, "canvas-1")), \
             patch("core.canvas_logic_service.CanvasLogicService", return_value=logic_svc):
            res = await mini_app_scaffold(
                {"name": "  MyApp  ", "spec": {}, "declared_scopes": ["chat"],
                 "dependencies": ["requests"]}, _ctx())
        assert res["success"] is True and res["app_id"] == "app-1"
        assert res["logic_source"] == "print('hi')"

    async def test_success_empty_spec_base_image(self, mini_env):
        from tools.mini_app_tool import mini_app_scaffold
        app = _app(name="X")
        mini_env.db.query.return_value.filter.return_value.first.return_value = app
        spec = {"base_image": ""}
        with patch("core.mini_app_service.scaffold", return_value=(app, "canvas-1")) as sc, \
             patch("core.canvas_logic_service.CanvasLogicService"):
            res = await mini_app_scaffold({"name": "X", "spec": spec}, _ctx())
        assert res["success"] is True
        assert spec["base_image"] == "python:3.11-slim"
        assert sc.call_args.kwargs["viewer"].id == "u-1"

    async def test_success_fresh_none(self, mini_env):
        from tools.mini_app_tool import mini_app_scaffold
        app = _app(name="X")
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.mini_app_service.scaffold", return_value=(app, "canvas-1")), \
             patch("core.canvas_logic_service.CanvasLogicService"):
            res = await mini_app_scaffold({"name": "X", "spec": {}}, _ctx())
        assert res["success"] is True and res["manifest"] == {}

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_scaffold
        with patch("core.mini_app_service.scaffold", side_effect=RuntimeError("boom")):
            res = await mini_app_scaffold({"name": "X", "spec": {}}, _ctx())
        assert res["success"] is False and "failed" in res["error"]


class TestMiniAppWriteLogic:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        res = await mini_app_write_logic({}, {})
        assert res["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        res = await mini_app_write_logic({}, _ctx())
        assert res["success"] is False and "app_id" in res["error"]

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_write_logic({"app_id": "app-1", "source": "x"}, _ctx())
        assert res["success"] is False and "not found" in res["error"]

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_write_logic({"app_id": "app-1", "source": "x"}, _ctx())
        assert res["success"] is False and "owner" in res["error"]

    async def test_no_blueprint(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(blueprint_canvas_id=None)
        res = await mini_app_write_logic({"app_id": "app-1", "source": "x"}, _ctx())
        assert res["success"] is False and "blueprint" in res["error"]

    async def test_syntax_error(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.syntax_check",
                   side_effect=SyntaxError("bad token")):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "def :("}, _ctx())
        assert res["success"] is False and "SyntaxError" in res["error"]

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        logic_svc = MagicMock()
        with patch("core.mini_app_service.syntax_check") as sc, \
             patch("core.canvas_logic_service.CanvasLogicService", return_value=logic_svc), \
             patch("core.mini_app_service.record_logic_snapshot",
                   return_value={"version": 3}):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"}, _ctx())
        assert res["success"] is True and res["version"] == 3
        sc.assert_called_once_with("x = 1")
        assert logic_svc.save_logic.call_args.kwargs["created_by"] == "u-1"

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_write_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.syntax_check", side_effect=RuntimeError("boom")):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x"}, _ctx())
        assert res["success"] is False


class TestMiniAppDevRun:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        assert (await mini_app_dev_run({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        res = await mini_app_dev_run({}, _ctx())
        assert res["success"] is False and "app_id" in res["error"]

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_dev_run({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_dev_run({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "owner" in res["error"]

    async def test_no_blueprint(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(blueprint_canvas_id=None)
        res = await mini_app_dev_run({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_runtime_error(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.prepare_runtime",
                   side_effect=RuntimeError("unsafe deps")):
            res = await mini_app_dev_run({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "unsafe deps" in res["error"]

    async def test_run_failed(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.prepare_runtime"), \
             patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(return_value={"success": False, "error": "crash"})):
            res = await mini_app_dev_run({"app_id": "app-1", "inputs": {"a": 1}}, _ctx())
        assert res["success"] is False and "crash" in res["error"]

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.prepare_runtime") as prep, \
             patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(return_value={"success": True, "state": {"s": 1},
                                              "version": 2, "state_changed": True,
                                              "proposed_ops": [{"op": "x"}],
                                              "op_results": [{"ok": True}],
                                              "proposed_record_ops": [],
                                              "record_results": [],
                                              "stdout": "hi", "stderr": "", "exit_code": 0})):
            res = await mini_app_dev_run({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["state"] == {"s": 1}
        assert res["state_changed"] is True
        assert prep.call_args[0][0] is not None
        assert prep.call_args[0][1] is mini_env.db

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_dev_run
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.prepare_runtime",
                   side_effect=ValueError("boom")):
            res = await mini_app_dev_run({"app_id": "app-1"}, _ctx())
        assert res["success"] is False


class TestMiniAppPublish:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        assert (await mini_app_publish({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        res = await mini_app_publish({}, _ctx())
        assert res["success"] is False and "app_id" in res["error"]

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_publish({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_publish({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "owner" in res["error"]

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.publish", return_value={"version": 4}):
            res = await mini_app_publish({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["version"] == 4

    async def test_runtime_error(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.publish", side_effect=RuntimeError("rootfs missing")):
            res = await mini_app_publish({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "rootfs" in res["error"]

    async def test_value_error(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.publish", side_effect=ValueError("bad manifest")):
            res = await mini_app_publish({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "bad manifest" in res["error"]

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_publish
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.publish", side_effect=KeyError("boom")):
            res = await mini_app_publish({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "publish failed" in res["error"]


class TestMiniAppInstall:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        assert (await mini_app_install({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        res = await mini_app_install({}, _ctx())
        assert res["success"] is False

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_not_authorized(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "authorized" in res["error"]

    async def test_pending_review(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(
            created_by="other", is_public=True, is_approved=False)
        res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "pending review" in res["error"]

    async def test_public_approved_install(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(
            created_by="other", is_public=True, is_approved=True)
        with patch("core.mini_app_service.install", return_value="instance-1"):
            res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["canvas_id"] == "instance-1"

    async def test_owner_install(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.install", return_value="instance-2"):
            res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and "instance-2" in res["message"]

    async def test_value_error(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.install", side_effect=ValueError("no blueprint")):
            res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "no blueprint" in res["error"]

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_install
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.install", side_effect=RuntimeError("boom")):
            res = await mini_app_install({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "install failed" in res["error"]


class TestMiniAppRun:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_run
        assert (await mini_app_run({}, {}))["success"] is False

    async def test_no_canvas(self, mini_env):
        from tools.mini_app_tool import mini_app_run
        res = await mini_app_run({}, _ctx())
        assert res["success"] is False and "canvas_id" in res["error"]

    async def test_run_persist(self, mini_env):
        from tools.mini_app_tool import mini_app_run
        with patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(return_value={"success": True, "state": {}})) as rs:
            res = await mini_app_run({"canvas_id": "c-1", "inputs": {"a": 1}},
                                     _ctx(agent_id="a-1"))
        assert res["success"] is True
        assert rs.await_args.kwargs["persist"] is True
        assert rs.await_args.kwargs["agent_id"] == "a-1"


class TestMiniAppList:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_list
        assert (await mini_app_list({}, {}))["success"] is False

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_list
        apps = [_app(id="a1", name="One"), _app(id="a2", name="Two", is_public=True)]
        mini_env.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = apps
        res = await mini_app_list({}, _ctx())
        assert res["success"] is True and len(res["apps"]) == 2
        assert res["apps"][0]["id"] == "a1"

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_list
        mini_env.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = RuntimeError("boom")
        res = await mini_app_list({}, _ctx())
        assert res["success"] is False and res["apps"] == []


class TestMiniAppGetState:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        assert (await mini_app_get_state({}, {}))["success"] is False

    async def test_no_canvas(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        res = await mini_app_get_state({}, _ctx())
        assert res["success"] is False and "canvas_id" in res["error"]

    async def test_canvas_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        mini_env.db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [None, None]
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_get_state({"canvas_id": "c-1"}, _ctx())
        assert res["success"] is False

    async def test_not_instance(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        canvas = SimpleNamespace(id="c-1", mini_app_id=None)
        mini_env.db.query.return_value.filter.return_value.first.return_value = canvas
        res = await mini_app_get_state({"canvas_id": "c-1"}, _ctx())
        assert res["success"] is False and "not a mini-app" in res["error"]

    async def test_success_with_row(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        canvas = SimpleNamespace(id="c-1", mini_app_id="app-1")
        row = SimpleNamespace(state={"a": 1}, version=7)
        mini_env.db.query.return_value.filter.return_value.first.return_value = canvas
        mini_env.db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        res = await mini_app_get_state({"canvas_id": "c-1"}, _ctx())
        assert res["success"] is True and res["state"] == {"a": 1} and res["version"] == 7

    async def test_success_no_row(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        canvas = SimpleNamespace(id="c-1", mini_app_id="app-1")
        mini_env.db.query.return_value.filter.return_value.first.return_value = canvas
        mini_env.db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        res = await mini_app_get_state({"canvas_id": "c-1"}, _ctx())
        assert res["success"] is True and res["state"] == {} and res["version"] == 0

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_get_state
        mini_env.db.query.side_effect = RuntimeError("boom")
        res = await mini_app_get_state({"canvas_id": "c-1"}, _ctx())
        assert res["success"] is False


class TestMiniAppSetTests:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        assert (await mini_app_set_tests({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        res = await mini_app_set_tests({"tests": []}, _ctx())
        assert res["success"] is False and "app_id" in res["error"]

    async def test_tests_not_list(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        res = await mini_app_set_tests({"app_id": "app-1", "tests": "nope"}, _ctx())
        assert res["success"] is False and "must be a list" in res["error"]

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_set_tests({"app_id": "app-1", "tests": []}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_set_tests({"app_id": "app-1", "tests": []}, _ctx())
        assert res["success"] is False and "owner" in res["error"]

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        app = _app(manifest={})
        mini_env.db.query.return_value.filter.return_value.first.return_value = app
        with patch("core.mini_app_service.validate_tests"):
            res = await mini_app_set_tests({"app_id": "app-1",
                                            "tests": [{"name": "t1"}]}, _ctx())
        assert res["success"] is True and res["tests"] == 1
        assert app.manifest == {"tests": [{"name": "t1"}]}
        mini_env.db.commit.assert_called_once()

    async def test_value_error(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.validate_tests", side_effect=ValueError("bad shape")):
            res = await mini_app_set_tests({"app_id": "app-1", "tests": [{}]}, _ctx())
        assert res["success"] is False and "bad shape" in res["error"]

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_set_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.validate_tests", side_effect=RuntimeError("boom")):
            res = await mini_app_set_tests({"app_id": "app-1", "tests": []}, _ctx())
        assert res["success"] is False


class TestMiniAppRunTests:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        assert (await mini_app_run_tests({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        res = await mini_app_run_tests({}, _ctx())
        assert res["success"] is False

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_run_tests({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_run_tests({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_no_tests(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(manifest={})
        res = await mini_app_run_tests({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["passed"] == 0
        assert "No acceptance tests" in res["message"]

    async def test_success_all_passed(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(
            manifest={"tests": [{"name": "t1"}, {"name": "t2"}]})
        with patch("core.mini_app_service.run_tests",
                   new=AsyncMock(return_value={"passed": 2, "total": 2,
                                              "results": [{"ok": True}]})):
            res = await mini_app_run_tests({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["all_passed"] is True
        assert "All 2" in res["message"]

    async def test_success_partial(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(
            manifest={"tests": [{"name": "t1"}, {"name": "t2"}]})
        with patch("core.mini_app_service.run_tests",
                   new=AsyncMock(return_value={"passed": 1, "total": 2,
                                              "results": [{"ok": True}, {"ok": False}]})):
            res = await mini_app_run_tests({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["all_passed"] is False
        assert "1/2" in res["message"]

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_run_tests
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(
            manifest={"tests": [{"name": "t1"}]})
        with patch("core.mini_app_service.run_tests", new=AsyncMock(side_effect=RuntimeError("x"))):
            res = await mini_app_run_tests({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "test run failed" in res["error"]


class TestMiniAppLogicHistory:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_logic_history
        assert (await mini_app_logic_history({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_logic_history
        res = await mini_app_logic_history({}, _ctx())
        assert res["success"] is False

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_logic_history
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_logic_history({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_logic_history
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_logic_history({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_logic_history
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.list_logic_history", return_value=[{"v": 1}]):
            res = await mini_app_logic_history({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["history"] == [{"v": 1}]

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_logic_history
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.list_logic_history", side_effect=RuntimeError("x")):
            res = await mini_app_logic_history({"app_id": "app-1"}, _ctx())
        assert res["success"] is False


class TestMiniAppRevertLogic:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        assert (await mini_app_revert_logic({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        res = await mini_app_revert_logic({}, _ctx())
        assert res["success"] is False and "app_id" in res["error"]

    async def test_no_version(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        res = await mini_app_revert_logic({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "version" in res["error"]

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_revert_logic({"app_id": "app-1", "version": 2}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_revert_logic({"app_id": "app-1", "version": 2}, _ctx())
        assert res["success"] is False

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.revert_logic", return_value={"version": 5}) as rv:
            res = await mini_app_revert_logic({"app_id": "app-1", "version": 3}, _ctx())
        assert res["success"] is True and res["version"] == 5
        assert rv.call_args.kwargs["actor_id"] == "u-1"

    async def test_value_error(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.revert_logic", side_effect=ValueError("no such v")):
            res = await mini_app_revert_logic({"app_id": "app-1", "version": 99}, _ctx())
        assert res["success"] is False and "no such v" in res["error"]

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_revert_logic
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.revert_logic", side_effect=RuntimeError("x")):
            res = await mini_app_revert_logic({"app_id": "app-1", "version": 1}, _ctx())
        assert res["success"] is False and "revert failed" in res["error"]


class TestMiniAppStatus:
    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_status
        assert (await mini_app_status({}, {}))["success"] is False

    async def test_no_app_id(self, mini_env):
        from tools.mini_app_tool import mini_app_status
        res = await mini_app_status({}, _ctx())
        assert res["success"] is False

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_status
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        res = await mini_app_status({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_not_owner(self, mini_env):
        from tools.mini_app_tool import mini_app_status
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app(created_by="other")
        res = await mini_app_status({"app_id": "app-1"}, _ctx())
        assert res["success"] is False

    async def test_success(self, mini_env):
        from tools.mini_app_tool import mini_app_status
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.status_probe", return_value={"ready": True}) as sp:
            res = await mini_app_status({"app_id": "app-1"}, _ctx())
        assert res["success"] is True and res["status"] == {"ready": True}
        assert sp.call_args.kwargs["viewer"].id == "u-1"

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_status
        mini_env.db.query.return_value.filter.return_value.first.return_value = _app()
        with patch("core.mini_app_service.status_probe", side_effect=RuntimeError("x")):
            res = await mini_app_status({"app_id": "app-1"}, _ctx())
        assert res["success"] is False and "probe failed" in res["error"]


class TestMiniAppDbQuery:
    USER = SimpleNamespace(tenant_id="t-1", workspace_id=None, tier="autonomous")

    def _target(self, mini_env):
        """Viewer-lookup row first, then canvas, then owning app."""
        mini_env.db.query.return_value.filter.return_value.first.side_effect = [
            self.USER,
            SimpleNamespace(id="c-1", mini_app_id="app-1", created_by="u-1"),
            _app(),
        ]

    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        assert (await mini_app_db_query({}, {}))["success"] is False

    async def test_no_canvas(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        res = await mini_app_db_query({}, _ctx())
        assert res["success"] is False and "canvas_id" in res["error"]

    async def test_bad_op(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        res = await mini_app_db_query({"canvas_id": "c-1", "op": "drop"}, _ctx())
        assert res["success"] is False and "op must be one of" in res["error"]

    async def test_tier_denied(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        res = await mini_app_db_query({"canvas_id": "c-1"}, _ctx(tier="student"))
        assert res["success"] is False and "Requires INTERN" in res["error"]

    async def test_db_disabled(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        with patch("core.mini_app_db_service.db_store_enabled", return_value=False):
            res = await mini_app_db_query({"canvas_id": "c-1"}, _ctx(tier="autonomous"))
        assert res["success"] is False and res["error"] == "db_disabled"

    async def test_target_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True):
            res = await mini_app_db_query({"canvas_id": "c-1"}, _ctx(tier="autonomous"))
        assert res["success"] is False and "not found or not owned" in res["error"]

    async def test_bad_series(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value=None):
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "BAD!"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "series must match" in res["error"]

    async def test_query_bad_filter(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.validate_filter", return_value=False):
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "query"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "filter must be" in res["error"]

    async def test_query_bad_limit(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.validate_filter", return_value=True):
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "query",
                                           "limit": 999999, "order": "sideways"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "limit must be" in res["error"]

    async def test_query_success(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.validate_filter", return_value=True), \
             patch("core.mini_app_db_service.query_records",
                   return_value=[{"id": 1}]) as qr:
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "query",
                                           "filter": {"a": 1}, "limit": 50, "order": "asc"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is True and res["count"] == 1
        assert qr.call_args.kwargs["f"] == {"a": 1}
        assert qr.call_args.kwargs["order"] == "asc"

    async def test_count_bad_filter(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.validate_filter", return_value=False):
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "count"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False

    async def test_count_success(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.validate_filter", return_value=True), \
             patch("core.mini_app_db_service.count_records", return_value=9) as cr:
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "count"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is True and res["count"] == 9
        assert cr.call_args.kwargs["series"] == "s"

    async def test_get_missing_id(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"):
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "get"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "record_id" in res["error"]

    async def test_get_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.get_record", return_value=None):
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "get",
                                           "record_id": "r1"}, _ctx(tier="autonomous"))
        assert res["success"] is False and "record not found" in res["error"]

    async def test_get_success(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="ok"), \
             patch("core.mini_app_db_service.get_record", return_value={"id": 1}) as gr:
            res = await mini_app_db_query({"canvas_id": "c-1", "series": "s", "op": "get",
                                           "record_id": "r1"}, _ctx(tier="autonomous"))
        assert res["success"] is True and res["record"] == {"id": 1}
        assert gr.call_args[0][3] == "r1"

    async def test_list_series(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.list_series", return_value=["a", "b"]) as ls:
            res = await mini_app_db_query({"canvas_id": "c-1", "op": "list_series"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is True and res["series"] == ["a", "b"]
        assert ls.call_args[0][1] == "c-1"

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_db_query
        with patch("core.mini_app_db_service.db_store_enabled", side_effect=RuntimeError("x")):
            res = await mini_app_db_query({"canvas_id": "c-1"}, _ctx(tier="autonomous"))
        assert res["success"] is False and "query failed" in res["error"]


class TestMiniAppDbWrite:
    USER = SimpleNamespace(tenant_id="t-1", workspace_id=None, tier="autonomous")

    def _target(self, mini_env, app=None):
        # viewer lookup, canvas, owning app, then the db_write MiniApp re-query
        mini_env.db.query.return_value.filter.return_value.first.side_effect = [
            self.USER,
            SimpleNamespace(id="c-1", mini_app_id="app-1", created_by="u-1"),
            app if app is not None else _app(),
            app if app is not None else _app(),
        ]

    async def test_no_user(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        assert (await mini_app_db_write({}, {}))["success"] is False

    async def test_no_canvas(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        res = await mini_app_db_write({}, _ctx())
        assert res["success"] is False and "canvas_id" in res["error"]

    async def test_bad_op(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        res = await mini_app_db_write({"canvas_id": "c-1", "op": "truncate"}, _ctx())
        assert res["success"] is False and "op must be one of" in res["error"]

    async def test_tier_denied(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        res = await mini_app_db_write({"canvas_id": "c-1", "op": "append"}, _ctx(tier="intern"))
        assert res["success"] is False and "Requires SUPERVISED" in res["error"]

    async def test_db_disabled(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        with patch("core.mini_app_db_service.db_store_enabled", return_value=False):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and res["error"] == "db_disabled"

    async def test_target_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        mini_env.db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False

    async def test_app_not_found(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        mini_env.db.query.return_value.filter.return_value.first.side_effect = [
            self.USER,
            SimpleNamespace(id="c-1", mini_app_id="app-1", created_by="u-1"), None, None]
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False

    async def test_bad_series(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value=None):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append", "series": "X"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "series must match" in res["error"]

    async def test_db_cfg_disabled(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env, _app(manifest={"db": {"enabled": False}}))
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="s"):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append", "series": "s"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and res["error"] == "db_disabled"

    async def test_invalid_record_op(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="s"), \
             patch("core.mini_app_service._validate_record_op", return_value=None):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append", "series": "s"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "invalid record op" in res["error"]

    async def test_append_success(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="s"), \
             patch("core.mini_app_service._validate_record_op", return_value={"op": "append"}) as vr, \
             patch("core.mini_app_service._execute_record_op",
                   return_value={"ok": True, "id": "r1"}) as er:
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append", "series": "s",
                                           "record_id": "rid", "id": "new-id",
                                           "data": {"a": 1}, "filter": {"x": 1}},
                                          _ctx(tier="autonomous"))
        assert res["success"] is True and res["id"] == "r1"
        op_args = vr.call_args[0][0]
        assert op_args["op"] == "append" and op_args["id"] == "new-id"
        assert er.call_args.kwargs["created_by"] == "u-1"

    async def test_update_many_op(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="s"), \
             patch("core.mini_app_service._validate_record_op", return_value={"op": "update_many"}) as vr, \
             patch("core.mini_app_service._execute_record_op", return_value={"ok": True}):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "update_many", "series": "s",
                                           "data": {"a": 2}, "filter": {"x": 1}},
                                          _ctx(tier="autonomous"))
        assert res["success"] is True
        op_args = vr.call_args[0][0]
        assert op_args["filter"] == {"x": 1} and op_args["data"] == {"a": 2}

    async def test_clear_op(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_service._validate_record_op", return_value={"op": "clear"}), \
             patch("core.mini_app_service._execute_record_op", return_value={"ok": True, "cleared": 3}):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "clear"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is True and res["cleared"] == 3

    async def test_exception(self, mini_env):
        from tools.mini_app_tool import mini_app_db_write
        self._target(mini_env)
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), \
             patch("core.mini_app_db_service.validate_series", return_value="s"), \
             patch("core.mini_app_service._validate_record_op", side_effect=RuntimeError("x")):
            res = await mini_app_db_write({"canvas_id": "c-1", "op": "append", "series": "s"},
                                          _ctx(tier="autonomous"))
        assert res["success"] is False and "write failed" in res["error"]


# ============================================================================
# tools/canvas_tool.py
# ============================================================================

def _canvas_agent(**kw):
    defaults = dict(id="a-1", name="Demo", status="autonomous", maturity_level="AUTONOMOUS")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class _CanvasEnv:
    def setup(self, agent=None, allow=True, governance=True):
        self.db = MagicMock()
        self.ws = AsyncMock()
        self.gov = MagicMock()
        self.gov.can_perform_action.return_value = {"allowed": allow, "reason": "r"}
        self.gov.record_outcome = AsyncMock()
        self.resolver = MagicMock()
        self.resolver.resolve_agent_for_request = AsyncMock(
            return_value=(agent, {}))
        self.execution = SimpleNamespace(id="exec-1")
        self.execution_query = MagicMock()
        self.db.query.return_value.filter.return_value.first.return_value = self.execution_query
        self.db_patch = _patch_db(self.db)
        self.db_patch.start()
        self._patches = [
            _gov_flag(governance),
            patch("tools.canvas_tool.AgentContextResolver", return_value=self.resolver),
            patch("core.service_factory.ServiceFactory.get_governance_service",
                  return_value=self.gov),
            patch("tools.canvas_tool.ws_manager", self.ws),
            patch("tools.canvas_tool.AgentExecution", return_value=self.execution),
        ]
        for p in self._patches:
            p.start()

    def teardown(self):
        for p in self._patches:
            p.stop()
        self.db_patch.stop()


@pytest.fixture()
def canvas_env():
    env = _CanvasEnv()
    env.setup()
    yield env
    env.teardown()


@pytest.fixture()
def canvas_env_blocked():
    env = _CanvasEnv()
    env.setup(agent=_canvas_agent(), allow=False)
    yield env
    env.teardown()


class TestCreateCanvasAudit:
    async def test_success(self):
        from tools.canvas_tool import _create_canvas_audit
        db = MagicMock()
        audit = await _create_canvas_audit(
            db=db, agent_id="a-1", agent_execution_id="e-1", user_id="u-1",
            canvas_id="c-1", session_id="s-1", canvas_type="docs",
            component_type="rich_editor", component_name="editor", action="present",
            governance_check_passed=True, metadata={"k": "v"})
        assert audit is not None
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        assert audit.details_json["k"] == "v"

    async def test_exception_returns_none(self):
        from tools.canvas_tool import _create_canvas_audit
        db = MagicMock()
        db.add.side_effect = RuntimeError("boom")
        assert await _create_canvas_audit(
            db=db, agent_id=None, agent_execution_id=None, user_id="u-1",
            canvas_id=None, session_id=None) is None


class TestPresentChart:
    async def test_governance_off(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await present_chart("u-1", "line_chart", [{"x": 1, "y": 2}],
                                      title="T", agent_id="a-1", session_id="s-1",
                                      color="blue")
            assert res["success"] is True and res["chart_type"] == "line_chart"
            msg = env.ws.broadcast.await_args.args[1]
            assert msg["data"]["component"] == "line_chart"
            assert msg["data"]["data"]["color"] == "blue"
        finally:
            env.teardown()

    async def test_blocked(self, canvas_env_blocked):
        from tools.canvas_tool import present_chart
        res = await present_chart("u-1", "bar_chart", [], agent_id="a-1")
        assert res["success"] is False and "not permitted" in res["error"]

    async def test_success_full_flow(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            res = await present_chart("u-1", "pie_chart", [{"a": 1}], title="P",
                                      agent_id="a-1")
            assert res["success"] is True and res["agent_id"] == "a-1"
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_agent_none_still_presents(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(agent=None)
        try:
            res = await present_chart("u-1", "line_chart", [])
            assert res["success"] is True and res["agent_id"] is None
        finally:
            env.teardown()

    async def test_execution_missing_on_complete(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.execution_query = None
        env.db.query.return_value.filter.return_value.first.return_value = None
        try:
            res = await present_chart("u-1", "line_chart", [])
            assert res["success"] is True
            assert env.gov.record_outcome.await_count == 0
        finally:
            env.teardown()

    async def test_exception_marks_execution_failed(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("ws boom")
        try:
            res = await present_chart("u-1", "line_chart", [])
            assert res["success"] is False and "ws boom" in res["error"]
            assert env.gov.record_outcome.await_count == 1
            assert env.execution_query.status == "failed"
        finally:
            env.teardown()

    async def test_exception_inner_failure_recording(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("ws boom")
        env.gov.record_outcome.side_effect = RuntimeError("inner")
        try:
            res = await present_chart("u-1", "line_chart", [])
            assert res["success"] is False
        finally:
            env.teardown()

    async def test_exception_no_execution(self):
        from tools.canvas_tool import present_chart
        env = _CanvasEnv()
        env.setup(agent=None, governance=False)
        env.ws.broadcast.side_effect = RuntimeError("boom")
        try:
            res = await present_chart("u-1", "line_chart", [])
            assert res["success"] is False
        finally:
            env.teardown()


class TestPresentStatusPanel:
    async def test_governance_off(self):
        from tools.canvas_tool import present_status_panel
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await present_status_panel("u-1", [{"label": "a", "value": 1}],
                                             title="Panel", agent_id="a-1", session_id="s-1")
            assert res["success"] is True
            msg = env.ws.broadcast.await_args.args[1]
            assert msg["data"]["component"] == "status_panel"
        finally:
            env.teardown()

    async def test_blocked(self, canvas_env_blocked):
        from tools.canvas_tool import present_status_panel
        res = await present_status_panel("u-1", [], agent_id="a-1")
        assert res["success"] is False and "not permitted" in res["error"]

    async def test_success_with_agent(self):
        from tools.canvas_tool import present_status_panel
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            res = await present_status_panel("u-1", [{"label": "b", "value": 2}])
            assert res["success"] is True
        finally:
            env.teardown()

    async def test_exception(self):
        from tools.canvas_tool import present_status_panel
        env = _CanvasEnv()
        env.setup(governance=False)
        env.ws.broadcast.side_effect = RuntimeError("boom")
        try:
            res = await present_status_panel("u-1", [])
            assert res["success"] is False
        finally:
            env.teardown()


class TestPresentMarkdown:
    async def test_governance_off(self):
        from tools.canvas_tool import present_markdown
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await present_markdown("u-1", "# Hello", title="Doc",
                                         agent_id="a-1", session_id="s-1")
            assert res["success"] is True and res["canvas_id"]
        finally:
            env.teardown()

    async def test_blocked(self, canvas_env_blocked):
        from tools.canvas_tool import present_markdown
        res = await present_markdown("u-1", "x", agent_id="a-1")
        assert res["success"] is False

    async def test_success_full_flow(self):
        from tools.canvas_tool import present_markdown
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            res = await present_markdown("u-1", "content here", title="T", agent_id="a-1")
            assert res["success"] is True and res["agent_id"] == "a-1"
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_execution_missing(self):
        from tools.canvas_tool import present_markdown
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.db.query.return_value.filter.return_value.first.return_value = None
        try:
            res = await present_markdown("u-1", "x", agent_id="a-1")
            assert res["success"] is True
            assert env.gov.record_outcome.await_count == 0
        finally:
            env.teardown()

    async def test_exception(self):
        from tools.canvas_tool import present_markdown
        env = _CanvasEnv()
        env.setup(governance=False)
        env.ws.broadcast.side_effect = RuntimeError("boom")
        try:
            res = await present_markdown("u-1", "x")
            assert res["success"] is False
        finally:
            env.teardown()


class TestPresentForm:
    async def test_governance_off(self):
        from tools.canvas_tool import present_form
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await present_form("u-1", {"fields": [{"name": "email"}]},
                                     title="Form", agent_id="a-1", session_id="s-1")
            assert res["success"] is True and res["canvas_id"]
            assert res["agent_execution_id"] is None
        finally:
            env.teardown()

    async def test_blocked(self, canvas_env_blocked):
        from tools.canvas_tool import present_form
        res = await present_form("u-1", {}, agent_id="a-1")
        assert res["success"] is False and "not permitted" in res["error"]

    async def test_success_full_flow(self):
        from tools.canvas_tool import present_form
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            res = await present_form("u-1", {"fields": [{"name": "a"}, {"name": "b"}]},
                                     title="F", agent_id="a-1")
            assert res["success"] is True
            assert res["agent_execution_id"] == "exec-1"
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_exception(self):
        from tools.canvas_tool import present_form
        env = _CanvasEnv()
        env.setup(governance=False)
        env.ws.broadcast.side_effect = RuntimeError("boom")
        try:
            res = await present_form("u-1", {})
            assert res["success"] is False
        finally:
            env.teardown()


class TestUpdateCanvas:
    async def test_governance_off(self):
        from tools.canvas_tool import update_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await update_canvas("u-1", "c-1", {"data": [1]}, agent_id="a-1",
                                      session_id="s-1")
            assert res["success"] is True and res["canvas_id"] == "c-1"
            assert res["updated_fields"] == ["data"]
        finally:
            env.teardown()

    async def test_blocked(self, canvas_env_blocked):
        from tools.canvas_tool import update_canvas
        res = await update_canvas("u-1", "c-1", {}, agent_id="a-1")
        assert res["success"] is False and "not permitted" in res["error"]

    async def test_success_full_flow(self):
        from tools.canvas_tool import update_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            res = await update_canvas("u-1", "c-1", {"title": "New", "data": []},
                                      agent_id="a-1")
            assert res["success"] is True
            assert res["updated_fields"] == ["title", "data"]
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_exception_marks_execution_failed(self):
        from tools.canvas_tool import update_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("ws boom")
        try:
            res = await update_canvas("u-1", "c-1", {}, agent_id="a-1")
            assert res["success"] is False
            assert env.execution_query.status == "failed"
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_exception_inner_failure(self):
        from tools.canvas_tool import update_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("ws boom")
        env.gov.record_outcome.side_effect = RuntimeError("inner")
        try:
            res = await update_canvas("u-1", "c-1", {}, agent_id="a-1")
            assert res["success"] is False
        finally:
            env.teardown()


class TestPresentToCanvas:
    async def test_chart_route(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_chart",
                   new=AsyncMock(return_value={"success": True, "r": "chart"})) as pc:
            res = await present_to_canvas(MagicMock(), "u-1", "chart",
                                          {"chart_type": "line_chart", "data": [1]},
                                          title="T", agent_id="a-1", session_id="s-1")
        assert res["success"] is True
        assert pc.await_args.kwargs["chart_type"] == "line_chart"

    async def test_form_route(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_form",
                   new=AsyncMock(return_value={"success": True})) as pf:
            res = await present_to_canvas(MagicMock(), "u-1", "form", {"fields": []})
        assert res["success"] is True
        assert pf.await_args.kwargs["form_schema"] == {"fields": []}

    async def test_markdown_route(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_markdown",
                   new=AsyncMock(return_value={"success": True})) as pm:
            res = await present_to_canvas(MagicMock(), "u-1", "markdown",
                                          {"content": "# X"})
        assert res["success"] is True
        assert pm.await_args.kwargs["content"] == "# X"

    async def test_status_panel_route(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_status_panel",
                   new=AsyncMock(return_value={"success": True})) as ps:
            res = await present_to_canvas(MagicMock(), "u-1", "status_panel",
                                          {"items": [1]})
        assert res["success"] is True
        assert ps.await_args.kwargs["items"] == [1]

    async def test_specialized_route(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_specialized_canvas",
                   new=AsyncMock(return_value={"success": True})) as psc:
            res = await present_to_canvas(MagicMock(), "u-1", "docs",
                                          {"component_type": "rich_editor",
                                           "content": "c"}, title="D")
        assert res["success"] is True
        assert psc.await_args.kwargs["canvas_type"] == "docs"

    async def test_unknown_type(self):
        from tools.canvas_tool import present_to_canvas
        res = await present_to_canvas(MagicMock(), "u-1", "mystery", {})
        assert res["success"] is False and "Unknown canvas type" in res["error"]

    async def test_exception(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_chart",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            res = await present_to_canvas(MagicMock(), "u-1", "chart", {})
        assert res["success"] is False


class TestCloseCanvas:
    async def test_success(self):
        from tools.canvas_tool import close_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await close_canvas("u-1", session_id="s-1")
            assert res["success"] is True
        finally:
            env.teardown()

    async def test_no_session(self):
        from tools.canvas_tool import close_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await close_canvas("u-1")
            assert res["success"] is True
        finally:
            env.teardown()

    async def test_exception(self):
        from tools.canvas_tool import close_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        env.ws.broadcast.side_effect = RuntimeError("boom")
        try:
            res = await close_canvas("u-1")
            assert res["success"] is False
        finally:
            env.teardown()


class TestCanvasExecuteJavascript:
    async def test_no_agent_id(self):
        from tools.canvas_tool import canvas_execute_javascript
        res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id="")
        assert res["success"] is False and "agent_id" in res["error"]

    async def test_governance_off_empty_js(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await canvas_execute_javascript("u-1", "c-1", "  ", agent_id="a-1")
            assert res["success"] is False and "empty" in res["error"]
        finally:
            env.teardown()

    async def test_dangerous_patterns(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent(), governance=False)
        try:
            for code in ["eval('x')", "document.cookie", "window.top", "setTimeout(f)",
                         "localStorage.setItem", "Function('x')", "window.parent",
                         "setInterval(f)", "sessionStorage.foo", "window.location"]:
                res = await canvas_execute_javascript("u-1", "c-1", code, agent_id="a-1")
                assert res["success"] is False, code
        finally:
            env.teardown()

    async def test_blocked_by_governance(self, canvas_env_blocked):
        from tools.canvas_tool import canvas_execute_javascript
        res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id="a-1")
        assert res["success"] is False

    async def test_not_autonomous_status(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent(status="intern"))
        try:
            res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id="a-1")
            assert res["success"] is False and "AUTONOMOUS" in res["error"]
        finally:
            env.teardown()

    async def test_success(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            res = await canvas_execute_javascript("u-1", "c-1", "document.title = 'x';",
                                                  agent_id="a-1", timeout_ms=1000,
                                                  session_id="s-1")
            assert res["success"] is True and res["javascript_length"] > 0
            msg = env.ws.broadcast.await_args.args[1]
            assert msg["type"] == "canvas:execute"
            assert msg["data"]["timeout_ms"] == 1000
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_success_governance_off(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(governance=False)
        try:
            res = await canvas_execute_javascript("u-1", "c-1", "document.title = 'y';",
                                                  agent_id="a-1")
            assert res["success"] is True
            assert env.gov.record_outcome.await_count == 0
        finally:
            env.teardown()

    async def test_exception_marks_execution_failed(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("ws boom")
        try:
            res = await canvas_execute_javascript("u-1", "c-1", "document.title='z';",
                                                  agent_id="a-1")
            assert res["success"] is False
            assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_exception_inner_failure(self):
        from tools.canvas_tool import canvas_execute_javascript
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("ws boom")
        env.gov.record_outcome.side_effect = RuntimeError("inner")
        try:
            res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id="a-1")
            assert res["success"] is False
        finally:
            env.teardown()


class TestPresentSpecializedCanvas:
    def _registry(self, **kw):
        reg = MagicMock()
        reg.validate_canvas_type.return_value = True
        reg.validate_component.return_value = True
        reg.validate_layout.return_value = True
        reg.get_min_maturity.return_value = SimpleNamespace(value="student")
        reg.get_all_types.return_value = {"docs": {}}
        for k, v in kw.items():
            getattr(reg, k).return_value = v
        return reg

    async def test_invalid_canvas_type(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        with patch("tools.canvas_tool.canvas_type_registry", self._registry(validate_canvas_type=False)):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {})
            assert res["success"] is False and "Invalid canvas type" in res["error"]
        env.teardown()

    async def test_invalid_component(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        with patch("tools.canvas_tool.canvas_type_registry",
                   self._registry(validate_component=False)):
            res = await present_specialized_canvas("u-1", "docs", "nope", {})
            assert res["success"] is False and "not supported" in res["error"]
        env.teardown()

    async def test_invalid_layout(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(governance=False)
        with patch("tools.canvas_tool.canvas_type_registry",
                   self._registry(validate_layout=False)):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                   layout="bogus")
            assert res["success"] is False and "not supported" in res["error"]
        env.teardown()

    async def test_blocked_by_governance(self, canvas_env_blocked):
        from tools.canvas_tool import present_specialized_canvas
        env = canvas_env_blocked
        with patch("tools.canvas_tool.canvas_type_registry", self._registry()):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                   agent_id="a-1")
            assert res["success"] is False and "not permitted" in res["error"]

    async def test_maturity_insufficient(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent(status="student"))
        try:
            with patch("tools.canvas_tool.canvas_type_registry",
                       self._registry(get_min_maturity=SimpleNamespace(value="autonomous"))):
                res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                       agent_id="a-1")
                assert res["success"] is False and "insufficient" in res["error"]
        finally:
            env.teardown()

    async def test_success(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        try:
            with patch("tools.canvas_tool.canvas_type_registry", self._registry()):
                res = await present_specialized_canvas(
                    "u-1", "docs", "rich_editor", {"content": "# D"}, title="Doc",
                    agent_id="a-1", session_id="s-1", layout="document")
                assert res["success"] is True and res["canvas_type"] == "docs"
                assert res["layout"] == "document"
                assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_exception(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("boom")
        try:
            with patch("tools.canvas_tool.canvas_type_registry", self._registry()):
                res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                       agent_id="a-1")
                assert res["success"] is False
                assert env.gov.record_outcome.await_count == 1
        finally:
            env.teardown()

    async def test_exception_inner_failure(self):
        from tools.canvas_tool import present_specialized_canvas
        env = _CanvasEnv()
        env.setup(agent=_canvas_agent())
        env.ws.broadcast.side_effect = RuntimeError("boom")
        env.gov.record_outcome.side_effect = RuntimeError("inner")
        try:
            with patch("tools.canvas_tool.canvas_type_registry", self._registry()):
                res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                       agent_id="a-1")
                assert res["success"] is False
        finally:
            env.teardown()


# ============================================================================
# tools/registry.py
# ============================================================================

class TestTypeName:
    def test_empty_annotation(self):
        from tools.registry import _type_name
        import inspect
        assert _type_name(inspect.Parameter.empty) == "Any"

    def test_plain_type(self):
        from tools.registry import _type_name
        assert _type_name(str) == "str"
        assert _type_name(dict) == "dict"

    def test_no_name_falls_back_to_str(self):
        from tools.registry import _type_name
        assert _type_name(None) == "None"


def _simple_fn(a: str, b: int = 3):
    """Docstring for simple fn."""
    return a


def _method_like(self, x: str) -> str:
    """Method-like signature."""
    return x


class _TypedFn:
    def method(self, y: int = 1) -> int:
        """Typed method."""
        return y


class TestToolMetadata:
    def test_defaults(self):
        from tools.registry import ToolMetadata
        m = ToolMetadata(name="t", function=_simple_fn)
        assert m.dependencies == [] and m.parameters == {} and m.examples == []
        assert m.tags == [] and m.cacheable is False
        assert m.maturity_required == "INTERN" and m.complexity == 2
        assert m.registered_at is not None

    def test_provided_values(self):
        from tools.registry import ToolMetadata
        m = ToolMetadata(name="t", function=_simple_fn, version="2.0.0",
                         description="d", category="c", complexity=4,
                         maturity_required="AUTONOMOUS", dependencies=["dep"],
                         parameters={"p": 1}, examples=[{"e": 1}], author="a",
                         tags=["x"], cacheable=True)
        assert m.cacheable is True and m.author == "a"

    def test_to_dict_sig(self):
        from tools.registry import ToolMetadata
        m = ToolMetadata(name="t", function=_simple_fn)
        d = m.to_dict()
        params = d["parameters"]
        assert params["a"]["type"] == "str" and params["a"]["required"] is True
        assert params["b"]["default"] == "3" and params["b"]["required"] is False
        assert d["function_path"] == f"{_simple_fn.__module__}.{_simple_fn.__name__}"
        assert "registered_at" in d

    def test_to_dict_skips_self(self):
        from tools.registry import ToolMetadata
        m = ToolMetadata(name="m", function=_TypedFn().method)
        d = m.to_dict()
        assert "self" not in d["parameters"]
        assert d["parameters"]["y"]["type"] == "int"

    def test_to_dict_no_default(self):
        from tools.registry import ToolMetadata
        m = ToolMetadata(name="m", function=_method_like)
        d = m.to_dict()
        assert "self" not in d["parameters"]
        assert d["parameters"]["x"]["default"] is None
        assert d["parameters"]["x"]["required"] is True


class TestToolRegistryCore:
    def _registry(self):
        from tools.registry import ToolRegistry
        return ToolRegistry()

    def test_register_new_and_duplicate(self):
        reg = self._registry()
        m = reg.register("a", _simple_fn, category="cat1")
        assert reg._tools["a"] is m
        assert reg._categories["cat1"] == ["a"]
        m2 = reg.register("a", _simple_fn, version="2.0.0")
        assert m2 is not None
        assert reg._categories["cat1"] == ["a"]

    def test_register_new_category_existing_tool(self):
        reg = self._registry()
        reg.register("a", _simple_fn, category="cat1")
        reg.register("a", _simple_fn, category="cat2")
        assert reg._categories["cat2"] == ["a"]

    def test_register_docstring_fallback(self):
        reg = self._registry()
        m = reg.register("b", _simple_fn, description="")
        assert m.description == "Docstring for simple fn."

    def test_get_and_get_function(self):
        reg = self._registry()
        reg.register("a", _simple_fn)
        assert reg.get("a").name == "a"
        assert reg.get_function("a") is _simple_fn
        assert reg.get("nope") is None
        assert reg.get_function("nope") is None

    def test_list_all_and_by_category(self):
        reg = self._registry()
        reg.register("a", _simple_fn, category="c1")
        reg.register("b", _simple_fn, category="c1")
        reg.register("c", _simple_fn, category="c2")
        assert set(reg.list_all()) == {"a", "b", "c"}
        assert set(reg.list_by_category("c1")) == {"a", "b"}
        assert reg.list_by_category("missing") == []

    def test_list_by_maturity(self):
        reg = self._registry()
        reg.register("student_tool", _simple_fn, maturity_required="STUDENT")
        reg.register("intern_tool", _simple_fn, maturity_required="INTERN")
        reg.register("autonomous_tool", _simple_fn, maturity_required="AUTONOMOUS")
        student_names = reg.list_by_maturity("STUDENT")
        assert student_names == ["student_tool"]
        intern_names = reg.list_by_maturity("INTERN")
        assert "student_tool" in intern_names and "intern_tool" in intern_names
        assert "autonomous_tool" not in intern_names
        assert reg.list_by_maturity("AUTONOMOUS") == ["student_tool", "intern_tool",
                                                      "autonomous_tool"]

    def test_list_by_maturity_invalid(self):
        reg = self._registry()
        reg.register("a", _simple_fn)
        assert reg.list_by_maturity("GODMODE") == []

    def test_search(self):
        reg = self._registry()
        reg.register("present_chart", _simple_fn, description="visualize data",
                     tags=["canvas", "chart"])
        reg.register("other", _simple_fn, description="nothing")
        assert len(reg.search("present")) == 1
        assert len(reg.search("VISUALIZE")) == 1
        assert len(reg.search("canvas")) == 1
        assert len(reg.search("zzz")) == 0

    def test_get_stats(self):
        reg = self._registry()
        reg.register("low_tool", _simple_fn, complexity=1, maturity_required="STUDENT")
        reg.register("high_tool", _simple_fn, complexity=3, maturity_required="SUPERVISED")
        stats = reg.get_stats()
        assert stats["total_tools"] == 2
        assert stats["categories"]["general"] == 2
        assert stats["complexity_distribution"]["LOW"] == 1
        assert stats["complexity_distribution"]["HIGH"] == 1
        assert stats["maturity_distribution"]["STUDENT"] == 1

    def test_export_all(self):
        reg = self._registry()
        reg.register("a", _simple_fn)
        exported = reg.export_all()
        assert len(exported) == 1 and exported[0]["name"] == "a"

    def test_get_simplified_tools(self):
        reg = self._registry()
        reg.register("req_tool", _simple_fn)
        simplified = reg.get_simplified_tools()
        assert simplified[0]["name"] == "req_tool"
        assert simplified[0]["parameters"]["a"] == "str"
        assert simplified[0]["parameters"]["b"] == "int (optional)"


async def _fake_afn(x=1):
    return x


class TestDiscoverTools:
    def _fake_module(self, **fns):
        mod = SimpleNamespace(**fns)
        return mod

    def test_explicit_modules_register(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        mod = SimpleNamespace(
            fetch_data=_fake_afn,
            create_item=_fake_afn,
            execute_command=_fake_afn,
            deploy_service=_fake_afn,
            update_item=_fake_afn,
            present_item=_fake_afn,
            delete_item=_fake_afn,
            _private_fn=_fake_afn,
            not_coroutine=lambda: 1,
        )
        with patch("tools.registry.importlib.import_module", return_value=mod):
            count = reg.discover_tools(["tools.fake_tool"])
        assert count == 7
        assert reg.get("fetch_data").complexity == 1
        assert reg.get("create_item").complexity == 3
        assert reg.get("update_item").complexity == 3
        assert reg.get("delete_item").complexity == 3
        assert reg.get("execute_command").complexity == 4
        assert reg.get("deploy_service").complexity == 4
        assert reg.get("present_item").complexity == 1
        assert reg.get("present_item").maturity_required == "STUDENT"
        assert reg.get("execute_command").maturity_required == "AUTONOMOUS"
        assert reg.get("_private_fn") is None
        assert reg.get("not_coroutine") is None
        assert reg.get("fetch_data").cacheable is True
        assert reg.get("create_item").cacheable is False

    def test_explicit_modules_skip_existing(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        reg.register("fetch_data", _fake_afn)
        mod = SimpleNamespace(fetch_data=_fake_afn)
        with patch("tools.registry.importlib.import_module", return_value=mod):
            count = reg.discover_tools(["tools.fake_tool"])
        assert count == 0

    def test_module_import_failure_logged(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch("tools.registry.importlib.import_module",
                   side_effect=ImportError("no module")):
            count = reg.discover_tools(["tools.broken_tool"])
        assert count == 0

    def test_default_glob_scan(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        mod = SimpleNamespace(
            get_thing=_fake_afn,
            send_thing=_fake_afn,
            execute_command=_fake_afn,
        )
        with patch("tools.registry.importlib.import_module", return_value=mod):
            count = reg.discover_tools()
        assert count == 3
        assert reg.get("get_thing").cacheable is True
        assert reg.get("send_thing").cacheable is False
        assert reg.get("execute_command").complexity == 4
        assert reg._initialized is True


class TestInitialize:
    def test_already_initialized(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        reg._initialized = True
        with patch.object(reg, "discover_tools") as disc:
            reg.initialize()
        disc.assert_not_called()

    def test_initializes_and_registers(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.object(reg, "discover_tools", return_value=0) as disc, \
             patch.object(reg, "_register_canvas_tools") as rc, \
             patch.object(reg, "_register_browser_tools") as rb, \
             patch.object(reg, "_register_device_tools") as rd, \
             patch.object(reg, "_register_productivity_tools") as rp, \
             patch.object(reg, "_register_memory_tools") as rm, \
             patch.object(reg, "_register_data_tools") as rdata, \
             patch.object(reg, "_register_agent_radio_tools") as rradio:
            reg.initialize()
        disc.assert_called_once_with()
        rc.assert_called_once()
        rb.assert_called_once()
        rd.assert_called_once()
        rp.assert_called_once()
        rm.assert_called_once()
        rdata.assert_called_once()
        rradio.assert_called_once()


class TestRegisterSubRoutines:
    @contextmanager
    def _get_fn(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        fn = Mock()
        fn.__module__ = "tools.fake"
        fn.__name__ = "fake_fn"
        with patch.object(reg, "_get_function", return_value=fn):
            yield reg

    def test_canvas_tools_registered(self):
        with self._get_fn() as reg:
            reg._register_canvas_tools()
        names = list(reg._tools.keys())
        assert len(names) == 8
        assert "present_chart" in names and "list_canvases" in names
        assert reg.get("read_canvas").cacheable is True
        assert reg.get("present_chart").maturity_required == "STUDENT"
        assert reg.get("present_form").complexity == 2
        assert reg.get("update_canvas_content").complexity == 2

    def test_browser_tools_registered(self):
        with self._get_fn() as reg:
            reg._register_browser_tools()
        assert len(reg._tools) == 9
        assert reg.get("browser_execute_script").complexity == 3
        assert reg.get("browser_navigate").complexity == 2

    def test_browser_tools_exception(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.object(reg, "_get_function", side_effect=RuntimeError("boom")):
            reg._register_browser_tools()
        assert len(reg._tools) == 0

    def test_device_tools_registered(self):
        with self._get_fn() as reg:
            reg._register_device_tools()
        assert len(reg._tools) == 6
        assert reg.get("device_camera_snap").maturity_required == "INTERN"
        assert reg.get("device_execute_command").complexity == 4
        assert reg.get("device_screen_record_start").maturity_required == "SUPERVISED"

    def test_device_tools_exception(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.object(reg, "_get_function", side_effect=RuntimeError("boom")):
            reg._register_device_tools()
        assert len(reg._tools) == 0

    def test_productivity_tools_ok(self):
        with self._get_fn() as reg:
            cal = Mock()
            notion = Mock()
            with patch("tools.calendar_tool.register_calendar_tool", cal), \
                 patch("tools.productivity_tool.register_notion_tool", notion):
                reg._register_productivity_tools()
        cal.assert_called_once_with(reg)
        notion.assert_called_once_with(reg)

    def test_productivity_tools_fail(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.dict(sys.modules, {"tools.calendar_tool": None}):
            reg._register_productivity_tools()
        with patch.dict(sys.modules, {"tools.productivity_tool": None}):
            reg._register_productivity_tools()

    def test_memory_tools_ok(self):
        with self._get_fn() as reg:
            mem = Mock()
            with patch("tools.memory_tool.register_memory_tool", mem):
                reg._register_memory_tools()
        mem.assert_called_once_with(reg)

    def test_memory_tools_fail(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.dict(sys.modules, {"tools.memory_tool": None}):
            reg._register_memory_tools()

    def test_data_tools_ok(self):
        with self._get_fn() as reg:
            da = Mock()
            pred = Mock()
            with patch("tools.data_analysis_tool.register_data_analysis_tools", da), \
                 patch("tools.predictive_tools.register_predictive_tools", pred):
                reg._register_data_tools()
        da.assert_called_once_with(reg)
        pred.assert_called_once_with(reg)

    def test_data_tools_fail(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.dict(sys.modules, {"tools.data_analysis_tool": None}):
            reg._register_data_tools()
        with patch.dict(sys.modules, {"tools.predictive_tools": None}):
            reg._register_data_tools()

    def test_radio_tools_ok(self):
        with self._get_fn() as reg:
            radio = Mock()
            with patch("tools.agent_radio_tool.register_agent_radio_tools", radio):
                reg._register_agent_radio_tools()
        radio.assert_called_once_with(reg)

    def test_radio_tools_fail(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        with patch.dict(sys.modules, {"tools.agent_radio_tool": None}):
            reg._register_agent_radio_tools()

    def test_get_function_success(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        fn = reg._get_function("tools.registry", "_type_name")
        assert fn is not None

    def test_get_function_import_failure(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        assert reg._get_function("tools.no_such_module_xyz", "anything") is None

    def test_get_function_missing_attr(self):
        from tools.registry import ToolRegistry
        reg = ToolRegistry()
        assert reg._get_function("tools.registry", "definitely_missing_fn") is None


class TestGetToolRegistry:
    def test_creates_singleton(self):
        from tools.registry import ToolRegistry
        with patch("tools.registry._global_registry", None), \
             patch("tools.registry.ToolRegistry") as TR:
            TR.return_value.initialize = Mock()
            reg = get_registry_unpatched()
        assert reg is not None
        TR.return_value.initialize.assert_called_once()

    def test_returns_existing(self):
        from tools.registry import ToolRegistry
        existing = ToolRegistry()
        with patch("tools.registry._global_registry", existing), \
             patch("tools.registry.ToolRegistry") as TR:
            reg = get_registry_unpatched()
        assert reg is existing
        TR.assert_not_called()


def get_registry_unpatched():
    from tools.registry import get_tool_registry
    return get_tool_registry()
