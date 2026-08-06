# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/governance_wrapper.py (service-layer governance
decorator; zero test references before this file).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core import governance_wrapper as gw
from core.governance_wrapper import (
    GovernableAction,
    GovernanceAudit,
    GovernanceDeniedError,
    _check_governance,
    require_governance,
)


class TestGovernableAction:
    def test_action_contracts(self):
        assert GovernableAction.ACCOUNTING_READ[1] == "STUDENT"
        assert GovernableAction.ACCOUNTING_DELETE[1] == "AUTONOMOUS"
        assert GovernableAction.BROWSER_AUTOMATE[1] == "AUTONOMOUS"
        assert GovernableAction.CANVAS_PRESENT[1] == "INTERN"

    def test_maturity_tiers_cover_all_levels(self):
        tiers = {a[1] for a in vars(GovernableAction).values() if isinstance(a, tuple)}
        assert tiers == {"STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"}


class TestAsyncDecorator:
    def test_allowed_without_agent_id(self):
        @require_governance("accounting_read", "STUDENT")
        async def read(agent_id=None):
            return "ok"

        assert self._run(read()) == "ok"

    def _run(self, coro):
        import asyncio

        return asyncio.get_event_loop_policy().get_event_loop().run_until_complete(coro)

    def test_allowed_with_agent_and_check_pass(self):
        @require_governance("accounting_write", "INTERN")
        async def write(agent_id=None):
            return "ok"

        with patch.object(gw, "_check_governance", return_value={"allowed": True}) as check:
            assert self._run(write(agent_id="agent-1")) == "ok"
            check.assert_called_once_with(
                agent_id="agent-1", action_type="accounting_write",
                minimum_maturity="INTERN", resource_type=None,
            )

    def test_denied_raises_governance_denied(self):
        @require_governance("accounting_delete", "AUTONOMOUS")
        async def delete_thing(agent_id=None):
            return "no"

        with patch.object(
            gw, "_check_governance",
            return_value={"allowed": False, "agent_maturity": "STUDENT", "reason": "too young"},
        ):
            with pytest.raises(GovernanceDeniedError) as excinfo:
                self._run(delete_thing(agent_id="agent-1"))
        assert excinfo.value.status_code == 403
        assert excinfo.value.maturity_level == "STUDENT"
        assert excinfo.value.required_maturity == "AUTONOMOUS"

    def test_missing_agent_id_rejected_when_required(self):
        @require_governance("accounting_write", "INTERN", allow_non_agent=False)
        async def write(agent_id=None):
            return "no"

        with pytest.raises(GovernanceDeniedError):
            self._run(write())


class TestSyncDecorator:
    def test_sync_allowed(self):
        @require_governance("accounting_read", "STUDENT")
        def read(agent_id=None):
            return "ok"

        with patch.object(gw, "_check_governance", return_value={"allowed": True}):
            assert read(agent_id="a1") == "ok"

    def test_sync_denied_raises(self):
        @require_governance("accounting_read", "STUDENT")
        def read(agent_id=None):
            return "no"

        with patch.object(gw, "_check_governance", return_value={"allowed": False}):
            with pytest.raises(GovernanceDeniedError):
                read(agent_id="a1")

    def test_sync_preserves_function_name(self):
        @require_governance("accounting_read", "STUDENT")
        def read(agent_id=None):
            return "ok"

        assert read.__name__ == "read"


class TestCheckGovernance:
    def test_agent_not_found_fails_closed(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            result = _check_governance("missing", "accounting_read", "STUDENT")
        assert result["allowed"] is False
        assert "not found" in result["reason"]

    def test_insufficient_maturity_fails_closed(self):
        agent = MagicMock()
        agent.maturity_level = "STUDENT"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            result = _check_governance("a1", "accounting_delete", "AUTONOMOUS")
        assert result["allowed"] is False
        assert "STUDENT" in result["reason"]

    def test_exception_fails_closed(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            result = _check_governance("a1", "accounting_read", "STUDENT")
        assert result["allowed"] is False

    def test_sufficient_maturity_defers_to_service(self):
        agent = MagicMock()
        agent.maturity_level = "SUPERVISED"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        cm = MagicMock()
        cm.__enter__.return_value = db
        service_result = MagicMock()
        service_result.allowed = True
        service_result.reason = None
        with patch("core.database.get_db_session", return_value=cm):
            with patch("core.agent_governance_service.AgentGovernanceService") as svc:
                svc.return_value.check_agent_permission.return_value = service_result
                result = _check_governance("a1", "accounting_read", "STUDENT")
        assert result["allowed"] is True


class TestGovernanceAudit:
    def test_log_governance_check_commits(self):
        db = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db
        with patch("core.database.get_db_session", return_value=cm):
            GovernanceAudit.log_governance_check(
                agent_id="a1", action_type="read", allowed=True,
                agent_maturity="INTERN", required_maturity="STUDENT",
            )
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_log_governance_check_swallows_errors(self):
        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("db down")
        with patch("core.database.get_db_session", return_value=cm):
            GovernanceAudit.log_governance_check(
                agent_id="a1", action_type="read", allowed=True,
                agent_maturity="INTERN", required_maturity="STUDENT",
            )
