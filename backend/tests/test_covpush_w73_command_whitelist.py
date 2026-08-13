# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/command_whitelist decorator + per-command maturity.

Covers the previously-unexercised `whitelisted_command` decorator paths
(agent_id/command/db validation, category/command allow-deny, maturity gates,
BLOCKED category, success passthrough), the per-command maturity override
introduced for the NETWORK category (curl/wget SUPERVISED+ vs diagnostics
INTERN+), and `get_command_category` empty-input handling.

Fully mocked deps (sqlalchemy Session + AgentRegistry query), zero LLM spend,
no network, no real DB.
"""
import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from core.command_whitelist import (
    COMMAND_WHITELIST,
    CommandCategory,
    get_allowed_commands,
    get_command_category,
    validate_command,
    whitelisted_command,
)
from core.models import AgentStatus


@pytest.fixture()
def mock_db():
    """SQLAlchemy-style session mock returning an agent on query."""
    agent = MagicMock()
    agent.id = "agent-1"
    agent.status = AgentStatus.AUTONOMOUS
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = agent
    return session


@pytest.fixture()
def intern_db():
    agent = MagicMock()
    agent.id = "agent-2"
    agent.status = AgentStatus.INTERN
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = agent
    return session


# ============================================================================
# whitelisted_command decorator — validation gates
# ============================================================================

class TestDecoratorValidation:
    async def _run(self, **kwargs):
        @whitelisted_command(
            category=CommandCategory.FILE_READ,
            maturity_levels=["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"],
        )
        async def read_cmd(agent_id, command, db, *a, **k):
            return {"ok": True}

        return await read_cmd(**kwargs)

    @pytest.mark.asyncio
    async def test_missing_agent_id_raises_value_error(self):
        with pytest.raises(ValueError, match="agent_id required"):
            await self._run(command="ls /tmp", db=MagicMock())

    @pytest.mark.asyncio
    async def test_empty_command_raises_value_error(self):
        with pytest.raises(ValueError, match="Empty command"):
            await self._run(agent_id="agent-1", command="   ", db=MagicMock())

    @pytest.mark.asyncio
    async def test_missing_db_raises_value_error(self):
        with pytest.raises(ValueError, match="Database session required"):
            await self._run(agent_id="agent-1", command="ls /tmp")

    @pytest.mark.asyncio
    async def test_invalid_category_raises_value_error(self):
        @whitelisted_command(category=MagicMock(value="bogus"), maturity_levels=["AUTONOMOUS"])
        async def fn(agent_id, command, db):
            return "ran"

        with pytest.raises(ValueError, match="Invalid command category"):
            await fn(agent_id="agent-1", command="ls /tmp", db=MagicMock())


class TestDecoratorAllowDeny:
    @pytest.mark.asyncio
    async def test_command_not_in_category_whitelist(self):
        @whitelisted_command(category=CommandCategory.FILE_READ, maturity_levels=["AUTONOMOUS"])
        async def fn(agent_id, command, db):
            return "ran"

        with pytest.raises(PermissionError, match="not in file_read whitelist"):
            await fn(agent_id="agent-1", command="rm /tmp/x", db=MagicMock())

    @pytest.mark.asyncio
    async def test_agent_not_found_raises_value_error(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        @whitelisted_command(category=CommandCategory.FILE_READ, maturity_levels=["AUTONOMOUS"])
        async def fn(agent_id, command, db):
            return "ran"

        with pytest.raises(ValueError, match="not found"):
            await fn(agent_id="ghost", command="ls /tmp", db=mock_db)

    @pytest.mark.asyncio
    async def test_maturity_insufficient_raises_permission_error(self, intern_db):
        @whitelisted_command(
            category=CommandCategory.FILE_DELETE, maturity_levels=["AUTONOMOUS"]
        )
        async def fn(agent_id, command, db):
            return "ran"

        with pytest.raises(PermissionError, match="not permitted for file_delete"):
            await fn(agent_id="agent-2", command="rm /tmp/x", db=intern_db)

    @pytest.mark.asyncio
    async def test_invalid_maturity_level_strings_skipped(self, mock_db):
        @whitelisted_command(
            category=CommandCategory.FILE_READ,
            maturity_levels=["NONEXISTENT", "AUTONOMOUS"],
        )
        async def fn(agent_id, command, db):
            return "ran"

        assert await fn(agent_id="agent-1", command="ls /tmp", db=mock_db) == "ran"

    @pytest.mark.asyncio
    async def test_blocked_category_raises_permission_error(self, mock_db):
        @whitelisted_command(category=CommandCategory.BLOCKED, maturity_levels=["AUTONOMOUS"])
        async def fn(agent_id, command, db):
            return "ran"

        with pytest.raises(PermissionError, match="blocked for all maturity levels"):
            await fn(agent_id="agent-1", command="chmod 777 /tmp/x", db=mock_db)

    @pytest.mark.asyncio
    async def test_success_passthrough_logs(self, mock_db, caplog):
        @whitelisted_command(
            category=CommandCategory.FILE_READ,
            maturity_levels=["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"],
        )
        async def fn(agent_id, command, db, extra=None):
            return {"ran": extra}

        with caplog.at_level(logging.INFO, logger="core.command_whitelist"):
            result = await fn(agent_id="agent-1", command="ls  -la /tmp", db=mock_db, extra=7)

        assert result == {"ran": 7}
        assert any("Whitelist validation passed" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_command_specific_min_maturity_in_message(self, intern_db):
        @whitelisted_command(category=CommandCategory.NETWORK, maturity_levels=["SUPERVISED", "AUTONOMOUS"])
        async def fn(agent_id, command, db):
            return "ran"

        with pytest.raises(PermissionError, match="Required maturity: SUPERVISED"):
            await fn(agent_id="agent-2", command="curl https://example.com", db=intern_db)


# ============================================================================
# Per-command maturity override (NETWORK: curl/wget SUPERVISED+, diag INTERN+)
# ============================================================================

class TestNetworkPerCommandMaturity:
    def test_curl_wget_categorized_network(self):
        assert get_command_category("curl https://x.io") == CommandCategory.NETWORK
        assert get_command_category("wget https://x.io") == CommandCategory.NETWORK
        assert get_command_category("ping 8.8.8.8") == CommandCategory.NETWORK

    def test_curl_requires_supervised(self):
        intern = validate_command("curl https://x.io", "INTERN")
        assert intern["valid"] is False
        assert intern["maturity_required"] == "SUPERVISED"
        supervised = validate_command("curl https://x.io", "SUPERVISED")
        assert supervised["valid"] is True
        assert validate_command("curl https://x.io", "AUTONOMOUS")["valid"] is True

    def test_wget_requires_supervised(self):
        assert validate_command("wget https://x.io", "STUDENT")["valid"] is False
        assert validate_command("wget https://x.io", "SUPERVISED")["valid"] is True

    def test_diagnostics_available_intern(self):
        assert validate_command("ping 8.8.8.8", "INTERN")["valid"] is True
        assert validate_command("nslookup example.com", "INTERN")["valid"] is True
        assert validate_command("dig example.com", "INTERN")["valid"] is True
        assert validate_command("netstat -an", "INTERN")["valid"] is True

    def test_student_denied_all_network(self):
        assert validate_command("curl https://x.io", "STUDENT")["valid"] is False
        assert validate_command("ping 8.8.8.8", "STUDENT")["valid"] is False

    def test_get_allowed_commands_honors_override(self):
        intern_cmds = get_allowed_commands("INTERN")
        assert "ping" in intern_cmds
        assert "curl" not in intern_cmds
        assert "wget" not in intern_cmds
        supervised_cmds = get_allowed_commands("SUPERVISED")
        assert "curl" in supervised_cmds
        assert "wget" in supervised_cmds

    def test_other_categories_unaffected_by_override(self):
        config = COMMAND_WHITELIST[CommandCategory.FILE_READ]
        assert "command_maturity" not in config
        assert get_allowed_commands("STUDENT") and "ls" in get_allowed_commands("STUDENT")


# ============================================================================
# validate_command remaining branches + get_command_category edge
# ============================================================================

class TestValidateCommandEdges:
    def test_none_maturity_is_not_allowed(self):
        result = validate_command("rm file.txt", None)
        assert result["valid"] is False
        assert result["maturity_required"] == "AUTONOMOUS"

    def test_lowercase_maturity_accepted(self):
        assert validate_command("ls /tmp", "autonomous")["valid"] is True
        assert validate_command("cp a b", "student")["valid"] is False

    def test_unknown_command(self):
        result = validate_command("someunknowncmd x", "AUTONOMOUS")
        assert result["valid"] is False
        assert result["whitelisted"] is False
        assert result["command"] == "someunknowncmd"
        assert "not found in any whitelist" in result["reason"]

    def test_blocked_reports_whitelisted_flag(self):
        result = validate_command("sudo ls", "AUTONOMOUS")
        assert result["valid"] is False
        assert result["blocked"] is True
        assert result["whitelisted"] is True

    def test_empty_and_whitespace_commands(self):
        for bad in ("", "   ", None):
            result = validate_command(bad, "AUTONOMOUS")
            assert result["valid"] is False
            assert result["command"] is None
            assert result["reason"] == "Empty command"

    def test_success_result_shape(self):
        result = validate_command("mkdir dir", "SUPERVISED")
        assert result["valid"] is True
        assert result["maturity_required"] == "SUPERVISED"
        assert result["blocked"] is False


class TestGetCommandCategoryEdges:
    def test_empty_command_returns_none(self):
        assert get_command_category("") is None
        assert get_command_category("   ") is None
        assert get_command_category(None) is None

    def test_unknown_command_returns_none(self):
        assert get_command_category("mystery --flag") is None

    def test_known_commands_map(self):
        assert get_command_category("mkdir x") == CommandCategory.FILE_WRITE
        assert get_command_category("docker ps") == CommandCategory.DEV_OPS
        assert get_command_category("node app.js") == CommandCategory.BUILD_TOOLS
        assert get_command_category("kill 1") == CommandCategory.BLOCKED


class TestDecoratorWrapsSyncFunction:
    @pytest.mark.asyncio
    async def test_decorator_contract_is_async_only(self, mock_db):
        """The decorator wraps any function in an async wrapper and enforces
        the gates before awaiting — decorating a sync function yields a
        coroutine wrapper (callers must supply async functions)."""
        @whitelisted_command(
            category=CommandCategory.FILE_READ,
            maturity_levels=["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"],
        )
        def sync_fn(agent_id, command, db):
            return "sync-ok"

        assert asyncio.iscoroutinefunction(sync_fn)

        with pytest.raises(TypeError):
            await sync_fn(agent_id="agent-1", command="cat x", db=mock_db)
