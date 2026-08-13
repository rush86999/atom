# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/governance_wrapper (decorator + service helper).

This module was never imported by any existing test file (0% baseline).
Covers: GovernanceDeniedError fields, GovernableAction registry, the
require_governance async+sync wrappers (non-agent passthrough, mandatory
agent context denial, denied/approved decisions), _check_governance
(agent-not-found, insufficient maturity, cache hit, full check + cache set,
exception fail-closed), and GovernanceAudit.log_governance_check success +
failure. Fully mocked deps, zero LLM spend, no network, no real DB.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from core.governance_wrapper import (
    GovernableAction,
    GovernanceAudit,
    GovernanceDeniedError,
    _check_governance,
    require_governance,
)


# ============================================================================
# GovernanceDeniedError + GovernableAction registry
# ============================================================================

class TestGovernanceDeniedError:
    def test_fields_and_status(self):
        err = GovernanceDeniedError(
            message="denied",
            maturity_level="INTERN",
            required_maturity="SUPERVISED",
            reason="not enough",
        )
        assert err.status_code == 403
        assert err.detail == "denied"
        assert err.maturity_level == "INTERN"
        assert err.required_maturity == "SUPERVISED"
        assert err.reason == "not enough"

    def test_defaults(self):
        err = GovernanceDeniedError(message="nope")
        assert err.maturity_level is None
        assert err.required_maturity is None
        assert err.reason is None


class TestGovernableAction:
    def test_registry_entries(self):
        assert GovernableAction.ACCOUNTING_DELETE == ("accounting_delete", "AUTONOMOUS", "transaction")
        assert GovernableAction.BROWSER_READ == ("browser_read", "INTERN", "page")
        assert GovernableAction.DEVICE_COMMAND == ("device_command", "AUTONOMOUS", "device")
        assert GovernableAction.CANVAS_SUBMIT == ("canvas_submit", "SUPERVISED", "form")


# ============================================================================
# require_governance — async wrapper
# ============================================================================

class TestAsyncWrapper:
    @pytest.mark.asyncio
    async def test_no_agent_allowed_non_agent_runs(self):
        @require_governance("accounting_write", "INTERN", "transaction")
        async def fn(amount=0, agent_id=None):
            return f"ran:{amount}"

        assert await fn(amount=5) == "ran:5"

    @pytest.mark.asyncio
    async def test_no_agent_mandatory_context_denied(self):
        @require_governance("accounting_delete", "AUTONOMOUS", "transaction", allow_non_agent=False)
        async def fn():
            return "ran"

        with pytest.raises(GovernanceDeniedError) as excinfo:
            await fn()
        assert excinfo.value.status_code == 403
        assert "requires an agent context" in excinfo.value.detail

    @pytest.mark.asyncio
    async def test_denied_decision_raises(self):
        @require_governance("accounting_write", "SUPERVISED", "transaction")
        async def fn(agent_id):
            return "ran"

        with patch(
            "core.governance_wrapper._check_governance",
            return_value={
                "allowed": False,
                "agent_maturity": "INTERN",
                "reason": "Agent maturity INTERN < required SUPERVISED",
            },
        ) as check:
            with pytest.raises(GovernanceDeniedError) as excinfo:
                await fn(agent_id="agent-1")

        check.assert_called_once_with(
            agent_id="agent-1",
            action_type="accounting_write",
            minimum_maturity="SUPERVISED",
            resource_type="transaction",
        )
        err = excinfo.value
        assert err.maturity_level == "INTERN"
        assert err.required_maturity == "SUPERVISED"
        assert "not authorized" in err.detail

    @pytest.mark.asyncio
    async def test_denied_unknown_maturity_and_default_reason(self):
        @require_governance("accounting_write", "SUPERVISED")
        async def fn(agent_id):
            return "ran"

        with patch(
            "core.governance_wrapper._check_governance",
            return_value={"allowed": False},
        ):
            with pytest.raises(GovernanceDeniedError) as excinfo:
                await fn(agent_id="agent-1")

        assert excinfo.value.maturity_level == "UNKNOWN"
        assert excinfo.value.reason == "Insufficient maturity level"

    @pytest.mark.asyncio
    async def test_allowed_decision_runs(self, caplog):
        @require_governance("accounting_read", "STUDENT", "transaction")
        async def fn(agent_id):
            return "executed"

        with patch(
            "core.governance_wrapper._check_governance",
            return_value={"allowed": True, "agent_maturity": "AUTONOMOUS"},
        ):
            with caplog.at_level(logging.INFO, logger="core.governance_wrapper"):
                assert await fn(agent_id="agent-1") == "executed"
        assert any("Governance allowed" in r.message for r in caplog.records)


# ============================================================================
# require_governance — sync wrapper
# ============================================================================

class TestSyncWrapper:
    def test_no_agent_allowed_non_agent_runs(self):
        @require_governance("integration_read", "STUDENT", "message")
        def fn(agent_id=None):
            return "sync-ran"

        assert fn() == "sync-ran"

    def test_no_agent_mandatory_context_denied(self):
        @require_governance("integration_delete", "AUTONOMOUS", "message", allow_non_agent=False)
        def fn():
            return "ran"

        with pytest.raises(GovernanceDeniedError):
            fn()

    def test_denied_decision_raises(self):
        @require_governance("integration_post", "SUPERVISED", "message")
        def fn(agent_id):
            return "ran"

        with patch(
            "core.governance_wrapper._check_governance",
            return_value={
                "allowed": False,
                "agent_maturity": "INTERN",
                "reason": "insufficient",
            },
        ):
            with pytest.raises(GovernanceDeniedError) as excinfo:
                fn(agent_id="agent-1")

        assert excinfo.value.maturity_level == "INTERN"

    def test_allowed_decision_runs(self, caplog):
        @require_governance("integration_read", "STUDENT", "message")
        def fn(agent_id):
            return "sync-executed"

        with patch(
            "core.governance_wrapper._check_governance",
            return_value={"allowed": True, "agent_maturity": "STUDENT"},
        ):
            with caplog.at_level(logging.INFO, logger="core.governance_wrapper"):
                assert fn(agent_id="agent-1") == "sync-executed"
        assert any("Governance allowed" in r.message for r in caplog.records)


# ============================================================================
# _check_governance
# ============================================================================

def patch_check_deps(agent=None, cache_get=None, gov_result=None, session_raise=None):
    session = MagicMock()
    if session_raise:
        session.query.side_effect = session_raise
    else:
        agent_obj = agent if agent is not None else None
        session.query.return_value.filter.return_value.first.return_value = agent_obj

    # `with get_db_session() as db:` calls __enter__ on the mock *returned* by
    # get_db_session(), not on the function mock itself.
    db_ctx = MagicMock()
    db_ctx.return_value.__enter__.return_value = session
    db_ctx.return_value.__exit__.return_value = False

    cache_cls = MagicMock()
    cache_cls.return_value.get.return_value = cache_get

    gov_cls = MagicMock()
    if gov_result is not None:
        gov_cls.return_value.check_agent_permission.return_value = gov_result

    patchers = [
        patch("core.database.get_db_session", db_ctx),
        patch("core.governance_cache.GovernanceCache", cache_cls),
        patch("core.agent_governance_service.AgentGovernanceService", gov_cls),
    ]
    return patchers, session, cache_cls, gov_cls


class TestCheckGovernance:
    def test_agent_not_found_fail_closed(self):
        patchers, *_ = patch_check_deps(agent=None)
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("ghost", "accounting_read", "STUDENT")
        assert result["allowed"] is False
        assert "not found" in result["reason"]
        assert result["agent_maturity"] is None

    def test_insufficient_maturity(self):
        agent = MagicMock()
        agent.maturity_level = "INTERN"
        patchers, *_ = patch_check_deps(agent=agent)
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("agent-1", "accounting_delete", "AUTONOMOUS", "transaction")
        assert result["allowed"] is False
        assert "maturity INTERN < required AUTONOMOUS" in result["reason"]
        assert result["agent_maturity"] == "INTERN"

    def test_unknown_maturity_denied(self):
        agent = MagicMock()
        agent.maturity_level = "MYSTERY"
        patchers, *_ = patch_check_deps(agent=agent)
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("agent-1", "accounting_write", "SUPERVISED")
        assert result["allowed"] is False

    def test_cache_hit_short_circuits_service(self):
        agent = MagicMock()
        agent.maturity_level = "AUTONOMOUS"
        cached = {"allowed": True, "agent_maturity": "AUTONOMOUS", "reason": None}
        patchers, _, cache_cls, gov_cls = patch_check_deps(agent=agent, cache_get=cached)
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("agent-1", "accounting_delete", "AUTONOMOUS")
        assert result is cached
        cache_cls.return_value.get.assert_called_once_with("agent-1", "accounting_delete")
        gov_cls.return_value.check_agent_permission.assert_not_called()

    def test_full_check_caches_result(self):
        agent = MagicMock()
        agent.maturity_level = "AUTONOMOUS"
        gov_result = MagicMock()
        gov_result.allowed = False
        gov_result.reason = "policy says no"
        patchers, _, cache_cls, gov_cls = patch_check_deps(agent=agent, gov_result=gov_result)
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("agent-1", "accounting_delete", "AUTONOMOUS", "transaction")
        assert result == {
            "allowed": False,
            "agent_maturity": "AUTONOMOUS",
            "reason": "policy says no",
        }
        gov_cls.return_value.check_agent_permission.assert_called_once_with(
            agent_id="agent-1", action_type="accounting_delete", resource_type="transaction"
        )
        cache_cls.return_value.set.assert_called_once_with("agent-1", "accounting_delete", result)

    def test_exception_fail_closed(self):
        patchers, *_ = patch_check_deps(session_raise=RuntimeError("db down"))
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("agent-1", "accounting_read", "STUDENT")
        assert result["allowed"] is False
        assert "db down" in result["reason"]

    def test_cache_get_raises_fail_closed(self):
        agent = MagicMock()
        agent.maturity_level = "AUTONOMOUS"
        patchers, _, cache_cls, _ = patch_check_deps(agent=agent)
        cache_cls.return_value.get.side_effect = ValueError("cache exploded")
        with patchers[0], patchers[1], patchers[2]:
            result = _check_governance("agent-1", "accounting_read", "STUDENT")
        assert result["allowed"] is False
        assert "cache exploded" in result["reason"]


# ============================================================================
# GovernanceAudit
# ============================================================================

class TestGovernanceAudit:
    @staticmethod
    def _patch_db(session):
        db_ctx = MagicMock()
        db_ctx.return_value.__enter__.return_value = session
        db_ctx.return_value.__exit__.return_value = False
        return patch("core.database.get_db_session", db_ctx)

    def test_log_success_path(self):
        session = MagicMock()
        with self._patch_db(session):
            GovernanceAudit.log_governance_check(
                agent_id="agent-1",
                action_type="accounting_write",
                allowed=False,
                agent_maturity="INTERN",
                required_maturity="SUPERVISED",
                reason="denied",
            )

        session.add.assert_called_once()
        session.commit.assert_called_once()
        log = session.add.call_args.args[0]
        assert log.event_type == "governance_check"
        assert log.security_level == "HIGH"
        assert log.success is False
        assert log.error_message == "denied"

    def test_log_allowed_security_normal(self):
        session = MagicMock()
        with self._patch_db(session):
            GovernanceAudit.log_governance_check(
                agent_id="agent-1", action_type="accounting_read",
                allowed=True, agent_maturity="AUTONOMOUS", required_maturity="STUDENT",
            )
        log = session.add.call_args.args[0]
        assert log.security_level == "NORMAL"
        assert log.success is True
        assert "accounting_read" in log.description

    def test_exception_swallowed(self, caplog):
        db_ctx = MagicMock()
        db_ctx.return_value.__enter__.side_effect = RuntimeError("audit db down")

        with caplog.at_level(logging.ERROR, logger="core.governance_wrapper"):
            with patch("core.database.get_db_session", db_ctx):
                GovernanceAudit.log_governance_check(
                    agent_id="agent-1", action_type="x", allowed=True,
                    agent_maturity="AUTONOMOUS", required_maturity="STUDENT",
                )
        assert any("Failed to log governance check" in r.message for r in caplog.records)
