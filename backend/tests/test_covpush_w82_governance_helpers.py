# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/governance_helpers.

All governance decisions come from a mocked AgentGovernanceService injected
via core.service_factory.ServiceFactory (the real local-import seam). Agent
maturity lookups use a real in-memory SQLite AgentRegistry. No network, no
LLM spend.

Coverage targets:
- check_agent_permission: granted, denied (raise_on_denied False/True),
  required_status fallback via ActionComplexity (+ raising fallback),
  unexpected exception → internal_error / False, HTTPException passthrough.
- check_agent_action: ActionComplexity enum + raw int.
- get_agent_maturity: found / not found / falsy id / query exception.
- can_agent_perform: allowed / denied (never raises).
- enforce_governance_check: allowed / denied raises.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from core.database import Base
from core.models import AgentRegistry  # noqa: F401

from core.api_governance import ActionComplexity
from core.governance_helpers import (
    can_agent_perform,
    check_agent_action,
    check_agent_permission,
    enforce_governance_check,
    get_agent_maturity,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", status="AUTONOMOUS"):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id="t1",
        category="Test",
        module_path="test",
        class_name="Test",
        status=status,
    )
    db.add(agent)
    db.commit()
    return agent


def _gov(allowed=True, reason="ok", agent_status="AUTONOMOUS", required_status=None):
    gov = MagicMock()
    gov.can_perform_action.return_value = {
        "allowed": allowed,
        "reason": reason,
        "agent_status": agent_status,
        "required_status": required_status,
    }
    return gov


@pytest.fixture()
def mock_gov():
    """Patch ServiceFactory.get_governance_service; yields the mocked service."""
    gov = _gov()
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=gov,
    ):
        yield gov


class TestCheckAgentPermission:
    def test_granted(self, db, mock_gov):
        assert check_agent_permission(db, "agent-1", "update_agent", complexity=3) is True
        mock_gov.can_perform_action.assert_called_once_with("agent-1", "update_agent")

    def test_denied_returns_false(self, db):
        gov = _gov(allowed=False, reason="maturity too low", agent_status="STUDENT",
                   required_status="SUPERVISED")
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov):
            result = check_agent_permission(db, "agent-1", "delete_user", 4, raise_on_denied=False)
        assert result is False

    def test_denied_raises_403(self, db):
        gov = _gov(allowed=False, reason="maturity too low", agent_status="STUDENT",
                   required_status="SUPERVISED")
        real_exc = HTTPException(status_code=403, detail="denied")
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
             patch("core.governance_helpers._router.permission_denied_error", return_value=real_exc) as pde:
            with pytest.raises(HTTPException) as exc_info:
                check_agent_permission(db, "agent-1", "delete_user", 4)
        assert exc_info.value.status_code == 403
        pde.assert_called_once()
        kwargs = pde.call_args.kwargs
        assert kwargs["action"] == "delete_user"
        assert kwargs["resource"] == "agent:agent-1"
        assert kwargs["details"]["current_maturity"] == "STUDENT"
        assert kwargs["details"]["required_maturity"] == "SUPERVISED"
        assert kwargs["details"]["complexity"] == 4

    def test_required_maturity_fallback_from_complexity(self, db):
        gov = _gov(allowed=False, agent_status="STUDENT", required_status=None)
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
             patch("core.governance_helpers._router.permission_denied_error", return_value=HTTPException(403)) as pde:
            with pytest.raises(HTTPException):
                check_agent_permission(db, "agent-1", "delete_user", 4)
        assert pde.call_args.kwargs["details"]["required_maturity"] == "AUTONOMOUS"

    def test_required_maturity_fallback_raises(self, db):
        gov = _gov(allowed=False, agent_status="STUDENT", required_status=None)
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
             patch("core.api_governance.ActionComplexity.get_required_maturity",
                   side_effect=RuntimeError("boom")), \
             patch("core.governance_helpers._router.permission_denied_error", return_value=HTTPException(403)) as pde:
            with pytest.raises(HTTPException):
                check_agent_permission(db, "agent-1", "delete_user", 4)
        assert pde.call_args.kwargs["details"]["required_maturity"] == "UNKNOWN"

    def test_unexpected_error_raises_500(self, db):
        gov = _gov()
        gov.can_perform_action.side_effect = RuntimeError("db exploded")
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
             patch("core.governance_helpers._router.internal_error", return_value=HTTPException(status_code=500)) as ie:
            with pytest.raises(HTTPException) as exc_info:
                check_agent_permission(db, "agent-1", "update_agent", 3)
        assert exc_info.value.status_code == 500
        ie.assert_called_once()

    def test_unexpected_error_returns_false_when_not_raising(self, db):
        gov = _gov()
        gov.can_perform_action.side_effect = RuntimeError("db exploded")
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov):
            assert check_agent_permission(db, "agent-1", "update_agent", 3, raise_on_denied=False) is False

    def test_http_exception_passthrough(self, db):
        gov = _gov()
        gov.can_perform_action.side_effect = HTTPException(status_code=429, detail="ratelimited")
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
             patch("core.governance_helpers._router.internal_error") as ie:
            with pytest.raises(HTTPException) as exc_info:
                check_agent_permission(db, "agent-1", "update_agent", 3)
        assert exc_info.value.status_code == 429
        ie.assert_not_called()

    def test_service_factory_exception(self, db):
        with patch("core.service_factory.ServiceFactory.get_governance_service",
                   side_effect=RuntimeError("factory down")), \
             patch("core.governance_helpers._router.internal_error", return_value=HTTPException(status_code=500)):
            with pytest.raises(HTTPException) as exc_info:
                check_agent_permission(db, "agent-1", "update_agent", 3)
        assert exc_info.value.status_code == 500


class TestCheckAgentAction:
    def test_with_enum(self, db):
        gov = _gov()
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov):
            assert check_agent_action(db, "agent-1", "delete_user", ActionComplexity.CRITICAL) is True
        gov.can_perform_action.assert_called_once_with("agent-1", "delete_user")

    def test_with_raw_int(self, db):
        gov = _gov()
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov):
            assert check_agent_action(db, "agent-1", "delete_user", 4) is True


class TestGetAgentMaturity:
    def test_success(self, db):
        _make_agent(db, status="SUPERVISED")
        assert get_agent_maturity(db, "agent-1") == "SUPERVISED"

    def test_not_found(self, db):
        assert get_agent_maturity(db, "ghost") is None

    def test_falsy_agent_id(self, db):
        assert get_agent_maturity(db, None) is None
        assert get_agent_maturity(db, "") is None

    def test_query_exception(self, db):
        class BoomDB:
            def query(self, model):
                raise RuntimeError("db down")

        assert get_agent_maturity(BoomDB(), "agent-1") is None


class TestCanAgentPerform:
    def test_allowed(self, db):
        gov = _gov(allowed=True)
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov):
            assert can_agent_perform(db, "agent-1", 3) is True
        gov.can_perform_action.assert_called_once_with("agent-1", "complexity_3")

    def test_denied_never_raises(self, db):
        gov = _gov(allowed=False, agent_status="STUDENT")
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov):
            assert can_agent_perform(db, "agent-1", 4) is False


class TestEnforceGovernanceCheck:
    def test_allowed(self, db, mock_gov):
        enforce_governance_check(db, "agent-1", "update_agent", 3)

    def test_denied_raises(self, db):
        gov = _gov(allowed=False)
        with patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
             patch("core.governance_helpers._router.permission_denied_error",
                   return_value=HTTPException(status_code=403)):
            with pytest.raises(HTTPException) as exc_info:
                enforce_governance_check(db, "agent-1", "update_agent", 3)
        assert exc_info.value.status_code == 403
