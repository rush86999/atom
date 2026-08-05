"""
TDD tests for core/workflow_security.py (R67/R68/R69 critical-tool gates).

Verifies fail-closed semantics: critical MCP tools, orchestrator step types,
email connectors, templated tool names, and AutomationEngine action nodes all
require WORKFLOW_MANAGE.
"""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest
from fastapi import HTTPException

from core import workflow_security as ws
from core.rbac_service import Permission
from core.workflow_security import (
    _has_critical_mcp_tool,
    has_critical_automation_nodes,
    has_critical_definition,
    has_critical_step,
    require_critical_tool,
    require_workflow_executor,
)


class _User:
    def __init__(self, id="u1", role="member"):
        self.id = id
        self.role = role


def test_critical_mcp_tool_detected():
    step = {"service": "mcp", "action": "terminal_command", "parameters": {}}
    assert _has_critical_mcp_tool(step) is True


def test_benign_mcp_tool_not_critical():
    step = {"service": "mcp", "action": "list_tools", "parameters": {}}
    assert _has_critical_mcp_tool(step) is False


def test_missing_or_templated_tool_name_is_critical():
    # Missing tool name on an mcp step → cannot prove benign → critical.
    assert _has_critical_mcp_tool({"service": "mcp", "parameters": {}}) is True
    # Templated tool name → could inject a critical tool at runtime → critical.
    step = {"service": "mcp", "action": "${user.tool}", "parameters": {}}
    assert _has_critical_mcp_tool(step) is True


def test_conductor_step_without_service_key_critical():
    # Conductor steps carry the tool name in parameters, no service key.
    step = {"parameters": {"tool_name": "browser_navigate"}}
    assert _has_critical_mcp_tool(step) is True


def test_orchestrator_step_type_critical():
    steps = [{"step_type": "email_send", "parameters": {}}]
    assert has_critical_step(steps) is True


def test_universal_integration_email_connector_critical():
    steps = [{
        "step_type": "universal_integration",
        "service": "gmail",
        "parameters": {},
    }]
    assert has_critical_step(steps) is True


def test_universal_integration_benign_connector_not_critical():
    steps = [{
        "step_type": "universal_integration",
        "service": "slack",
        "parameters": {},
    }]
    assert has_critical_step(steps) is False


def test_has_critical_definition_handles_list_dict_object():
    assert has_critical_definition(
        [{"step_type": "terminal", "parameters": {}}]
    ) is True
    assert has_critical_definition(
        {"steps": [{"step_type": "terminal", "parameters": {}}]}
    ) is True
    assert has_critical_definition(None) is False


def test_require_workflow_executor_blocks_member():
    step = {"service": "mcp", "action": "terminal_command", "parameters": {}}
    with patch.object(ws.RBACService, "check_permission", return_value=False):
        with pytest.raises(HTTPException) as exc:
            import asyncio
            asyncio.run(require_workflow_executor(_User(role="member"), [step]))
    assert exc.value.status_code == 403


def test_require_workflow_executor_allows_manage():
    step = {"service": "mcp", "action": "terminal_command", "parameters": {}}
    with patch.object(ws.RBACService, "check_permission", return_value=True):
        import asyncio
        asyncio.run(require_workflow_executor(_User(role="team_lead"), [step]))


def test_require_critical_tool_blocks_member():
    with patch.object(ws.RBACService, "check_permission", return_value=False):
        import asyncio
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_critical_tool(_User(), "terminal_command"))
    assert exc.value.status_code == 403


def test_require_critical_tool_allows_benign():
    with patch.object(ws.RBACService, "check_permission", return_value=False):
        import asyncio
        asyncio.run(require_critical_tool(_User(), "list_tools"))


def test_has_critical_automation_nodes():
    defn = {"nodes": [{"config": {"actionType": "send_email"}}]}
    assert has_critical_automation_nodes(defn) is True
    benign = {"nodes": [{"config": {"actionType": "read_file"}}]}
    assert has_critical_automation_nodes(benign) is False
    assert has_critical_automation_nodes(None) is False
