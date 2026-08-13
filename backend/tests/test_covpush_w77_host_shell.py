"""Coverage wave 77 — RED tests for core/host_shell_service.py.

Real bug (TDD red->green): the module documents a "5-minute timeout
enforcement" (MAX_TIMEOUT_SECONDS = 300) but never applies it — a caller
passing timeout=3600 gets a 1-hour window, defeating the governance cap.
The constant is only used as a default parameter; it is never enforced
when a caller overrides it. RED: a request with timeout > 300 must be
clamped to 300 before reaching asyncio.wait_for.
"""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

import core.host_shell_service as host_mod
from core.models import AgentStatus


class TestTimeoutCapEnforcement:
    """REAL BUG: MAX_TIMEOUT_SECONDS is never enforced when the caller
    passes a larger timeout. The cap must clamp, not just default."""

    async def _run(self, service, db, requested_timeout):
        seen = {}

        async def recording_wait_for(coro, *args, **kwargs):
            seen["timeout"] = kwargs.get("timeout", args[0] if args else None)
            return await coro

        process = Mock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b"out", b""))
        agent = Mock()
        agent.status = AgentStatus.AUTONOMOUS
        db.query.return_value.filter.return_value.first.return_value = agent

        with patch.object(host_mod.asyncio, "create_subprocess_exec", AsyncMock(return_value=process)), \
                patch.object(host_mod.asyncio, "wait_for", recording_wait_for):
            await service.execute_shell_command(
                agent_id="a1", user_id="u1", command="ls -la",
                timeout=requested_timeout, db=db,
            )
        return seen["timeout"]

    @pytest.mark.asyncio
    async def test_large_timeout_clamped_to_max(self):
        service = host_mod.HostShellService()
        db = Mock()
        used = await self._run(service, db, requested_timeout=3600)
        assert used == 300  # RED: currently passes 3600 straight through

    @pytest.mark.asyncio
    async def test_moderate_timeout_unchanged(self):
        service = host_mod.HostShellService()
        db = Mock()
        used = await self._run(service, db, requested_timeout=120)
        assert used == 120  # within cap: unchanged


def _process(returncode=0, out=b"", err=b""):
    p = Mock()
    p.returncode = returncode
    p.communicate = AsyncMock(return_value=(out, err))
    p.kill = Mock()
    return p


def _autonomous_db(agent_status=None):
    db = Mock()
    agent = Mock()
    agent.status = agent_status or AgentStatus.AUTONOMOUS
    db.query.return_value.filter.return_value.first.return_value = agent
    return db


class TestExecuteShellCommandGuards:
    """execute_shell_command entry-point validation branches."""

    @pytest.mark.asyncio
    async def test_db_required(self):
        with pytest.raises(ValueError, match="Database session required"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="ls", db=None)

    @pytest.mark.asyncio
    async def test_empty_command_rejected(self):
        with pytest.raises(ValueError, match="Empty command"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="   ", db=_autonomous_db())

    @pytest.mark.asyncio
    async def test_unwhitelisted_command_rejected(self):
        with pytest.raises(PermissionError, match="not found in any whitelist"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="sleep 5", db=_autonomous_db())

    @pytest.mark.asyncio
    async def test_blocked_command_rejected(self):
        with pytest.raises(PermissionError, match="blocked for all maturity levels"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="sudo rm -rf /", db=_autonomous_db())

    @pytest.mark.asyncio
    async def test_null_byte_working_directory_rejected(self):
        # Path.resolve() raises ValueError on embedded null bytes -> PermissionError
        with pytest.raises(PermissionError, match="Invalid working directory"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="ls",
                working_directory="/tmp/\x00evil", db=_autonomous_db())

    @pytest.mark.asyncio
    async def test_outside_allowed_dir_rejected(self):
        with pytest.raises(PermissionError, match="not within allowed directories"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="ls",
                working_directory="/etc", db=_autonomous_db())


class TestCategoryRouting:
    """execute_shell_command routes to per-category methods."""

    @pytest.mark.asyncio
    async def test_write_command_routes(self):
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(return_value=_process())):
            result = await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="mkdir -p /tmp/xx", db=_autonomous_db())
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_delete_command_routes(self):
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(return_value=_process())):
            result = await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="rm -f /tmp/xx", db=_autonomous_db())
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_build_command_routes(self):
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(return_value=_process(out=b"built"))):
            result = await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="make all", db=_autonomous_db())
        assert result["stdout"] == "built"

    @pytest.mark.asyncio
    async def test_devops_command_routes(self):
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(return_value=_process(out=b"git log"))):
            result = await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="git status", db=_autonomous_db())
        assert result["stdout"] == "git log"

    @pytest.mark.asyncio
    async def test_network_command_routes(self):
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(return_value=_process())):
            result = await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="ping -c 1 127.0.0.1", db=_autonomous_db())
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_write_blocked_for_student(self):
        with pytest.raises(PermissionError, match="not permitted"):
            await host_mod.host_shell_service.execute_shell_command(
                agent_id="a1", user_id="u1", command="mkdir -p /tmp/xx",
                db=_autonomous_db(agent_status=AgentStatus.STUDENT))

    @pytest.mark.asyncio
    async def test_unsupported_general_category(self):
        with pytest.raises(PermissionError, match="Unsupported command category"):
            await host_mod.host_shell_service.execute_general_command(
                agent_id="a1", user_id="u1", command="ls",
                category=host_mod.CommandCategory.FILE_READ, db=_autonomous_db())


class TestExecuteInternal:
    """_execute_command_internal audit + failure branches."""

    @pytest.mark.asyncio
    async def test_agent_not_found_internal(self):
        # The whitelist decorator queries the agent first (returns it), then
        # _execute_command_internal queries again — second lookup returns None.
        db = Mock()
        agent = Mock()
        agent.status = AgentStatus.AUTONOMOUS
        db.query.return_value.filter.return_value.first.side_effect = [agent, None]
        with pytest.raises(PermissionError, match="not found"):
            await host_mod.host_shell_service.execute_read_command(
                agent_id="ghost", user_id="u1", command="ls", db=db)

    @pytest.mark.asyncio
    async def test_subprocess_failure_re_raises_and_audits(self):
        db = _autonomous_db()
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            with pytest.raises(RuntimeError, match="boom"):
                await host_mod.host_shell_service.execute_read_command(
                    agent_id="a1", user_id="u1", command="ls", db=db)
        # audit row recorded the failure
        session = db.add.call_args[0][0]
        assert session.exit_code == -1
        assert "boom" in session.stderr
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_timeout_process_lookup_error_after_kill(self):
        db = _autonomous_db()
        p = _process()
        p.communicate = AsyncMock(side_effect=[
            asyncio.TimeoutError,
            ProcessLookupError("no such process"),
        ])
        with patch.object(host_mod.asyncio, "create_subprocess_exec", AsyncMock(return_value=p)):
            result = await host_mod.host_shell_service.execute_read_command(
                agent_id="a1", user_id="u1", command="ls", timeout=1, db=db)
        assert result["timed_out"] is True
        assert result["exit_code"] == -1
        p.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_os_error_after_kill(self):
        db = _autonomous_db()
        p = _process()
        p.communicate = AsyncMock(side_effect=[
            asyncio.TimeoutError,
            OSError("broken pipe"),
        ])
        with patch.object(host_mod.asyncio, "create_subprocess_exec", AsyncMock(return_value=p)):
            result = await host_mod.host_shell_service.execute_read_command(
                agent_id="a1", user_id="u1", command="ls", timeout=1, db=db)
        assert result["timed_out"] is True
        assert result["stdout"] == ""

    @pytest.mark.asyncio
    async def test_timeout_unexpected_error_after_kill(self):
        db = _autonomous_db()
        p = _process()
        p.communicate = AsyncMock(side_effect=[
            asyncio.TimeoutError,
            RuntimeError("weird"),
        ])
        with patch.object(host_mod.asyncio, "create_subprocess_exec", AsyncMock(return_value=p)):
            result = await host_mod.host_shell_service.execute_read_command(
                agent_id="a1", user_id="u1", command="ls", timeout=1, db=db)
        assert result["timed_out"] is True
        assert result["stdout"] == ""

    @pytest.mark.asyncio
    async def test_success_path_records_duration(self):
        db = _autonomous_db()
        with patch.object(host_mod.asyncio, "create_subprocess_exec",
                          AsyncMock(return_value=_process(out=b"hello", err=b"warn"))):
            result = await host_mod.host_shell_service.execute_read_command(
                agent_id="a1", user_id="u1", command="ls", db=db)
        assert result["stdout"] == "hello"
        assert result["stderr"] == "warn"
        assert result["maturity_level"] == AgentStatus.AUTONOMOUS
        assert result["duration_seconds"] >= 0
        session = db.add.call_args[0][0]
        assert session.command_whitelist_valid is True
        assert session.working_directory is None
        assert session.exit_code == 0


class TestValidateCommandBranches:
    def test_maturity_none_not_valid(self):
        result = host_mod.host_shell_service.validate_command("ls", None)
        assert result["valid"] is False

    def test_lowercase_maturity_accepted(self):
        result = host_mod.host_shell_service.validate_command("ls", "intern")
        assert result["valid"] is True
