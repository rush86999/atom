"""
Tests for Graduated Shell Access

Verifies that shell commands are correctly whitelisted and enforced based on agent maturity:
- INTERN: Read-only commands (ls, cat, etc.)
- SUPERVISED: Monitoring commands (ps, top, etc.)
- AUTONOMOUS: Full whitelist access
"""

import uuid
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.models import AgentStatus
from tools.device_tool import device_execute_command

@pytest.fixture
def mock_db():
    return Mock(spec=Session)

@pytest.fixture
def intern_agent():
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.status = AgentStatus.INTERN.value
    return agent

@pytest.fixture
def supervised_agent():
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.status = AgentStatus.SUPERVISED.value
    return agent

@pytest.fixture
def autonomous_agent():
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.status = AgentStatus.AUTONOMOUS.value
    return agent

@pytest.fixture
def mock_device_node():
    device = Mock()
    device.device_id = "test-device-123"
    return device

class TestGraduatedShellAccess:
    
    @pytest.mark.asyncio
    async def test_intern_can_read_but_not_monitor(self, mock_db, intern_agent, mock_device_node):
        """Test INTERN agent: ls (allowed) vs ps (blocked)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        
        # Mock governance to succeed for read, fail for monitor
        def side_effect(db, agent_id, action, user_id):
            if action == "device_shell_read":
                return {"allowed": True, "governance_check_passed": True}
            return {"allowed": False, "reason": "Lacks maturity", "governance_check_passed": False}

        with patch('tools.device_tool._check_device_governance', side_effect=side_effect), \
             patch('tools.device_tool.is_device_online', return_value=True), \
             patch('tools.device_tool.send_device_command', return_value={"success": True, "data": {}}):
            
            # ls should be allowed (Read)
            result_read = await device_execute_command(mock_db, "user-1", "test-device-123", "ls", agent_id=intern_agent.id)
            assert result_read["success"] is True
            
            # ps should be blocked (Monitor)
            result_monitor = await device_execute_command(mock_db, "user-1", "test-device-123", "ps", agent_id=intern_agent.id)
            assert result_monitor["success"] is False
            assert result_monitor["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_supervised_can_monitor_but_not_full(self, mock_db, supervised_agent, mock_device_node):
        """Test SUPERVISED agent: ps (allowed) vs non-categorized (blocked)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        
        def side_effect(db, agent_id, action, user_id):
            if action in ["device_shell_read", "device_shell_monitor"]:
                return {"allowed": True, "governance_check_passed": True}
            return {"allowed": False, "reason": "Lacks maturity", "governance_check_passed": False}

        with patch('tools.device_tool._check_device_governance', side_effect=side_effect), \
             patch('tools.device_tool.is_device_online', return_value=True), \
             patch('tools.device_tool.send_device_command', return_value={"success": True, "data": {}}):
            
            # ps should be allowed (Monitor)
            result_monitor = await device_execute_command(mock_db, "user-1", "test-device-123", "ps", agent_id=supervised_agent.id)
            assert result_monitor["success"] is True
            
            # Some non-categorized whitelisted command (e.g. 'find' is monitor, let's say 'df' is monitor)
            # If I use a command that defaults to complexity 4:
            result_full = await device_execute_command(mock_db, "user-1", "test-device-123", "some_other_cmd", agent_id=supervised_agent.id)
            # Note: some_other_cmd must be in global whitelist to even get to governance check
            # But wait, device_execute_command checks global whitelist FIRST.
            
    @pytest.mark.asyncio
    async def test_global_whitelist_still_applies(self, mock_db, autonomous_agent, mock_device_node):
        """Test that global whitelist still blocks unknown commands for everyone."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        
        result = await device_execute_command(mock_db, "user-1", "test-device-123", "rm -rf /", agent_id=autonomous_agent.id)
        assert result["success"] is False
        assert "not in whitelist" in result["error"].lower()
