"""
Integration Tests for Community Skills Registry

End-to-end tests for skill import, scanning, storage, and execution.
Tests the complete workflow from import to execution with governance checks.

Reference: Phase 14 Plan 03 - Skills Registry & Security
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from core.skill_registry_service import SkillRegistryService
from core.models import SkillExecution


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def skill_service(db_session):
    """Create SkillRegistryService with mocked dependencies."""
    with patch('core.skill_registry_service.HazardSandbox') as mock_sandbox, \
         patch('core.skill_registry_service.AgentGovernanceService') as mock_governance:

        # Mock sandbox to avoid Docker requirement
        mock_sandbox_instance = Mock()
        mock_sandbox_instance.execute_python = Mock(return_value="mocked result")
        mock_sandbox.return_value = mock_sandbox_instance

        # Mock governance service
        mock_governance_instance = Mock()
        mock_governance_instance.get_agent = Mock(return_value={"maturity_level": "INTERN"})
        mock_governance.return_value = mock_governance_instance

        service = SkillRegistryService(db_session)
        return service


# ============================================================================
# Import Tests
# ============================================================================

class TestSkillImport:
    """Test skill import workflow."""

    def test_import_skill_from_content(self, skill_service, db_session):
        """Import skill from raw SKILL.md content."""
        # Mock parser
        skill_content = """---
name: Calculator
description: Simple calculator
---
Add two numbers together.
"""
        skill_service._parser.parse_skill_content = Mock(return_value=({"name": "Calculator", "description": "Simple calculator"}, skill_content))
        skill_service._parser._auto_fix_metadata = Mock(return_value={"name": "Calculator"})
        skill_service._parser._detect_skill_type = Mock(return_value="prompt_only")

        # Mock scanner
        skill_service._scanner.scan_skill = Mock(return_value={
            "safe": True,
            "risk_level": "LOW",
            "findings": []
        })

        result = skill_service.import_skill(
            source="raw_content",
            content=skill_content,
            metadata={"author": "test"}
        )

        assert result["skill_id"] is not None
        assert result["skill_name"] == "Calculator"
        assert result["status"] == "Active"  # LOW risk -> Active
        assert result["scan_result"]["risk_level"] == "LOW"

    def test_import_skill_malicious_marked_untrusted(self, skill_service, db_session):
        """Malicious skill should be marked Untrusted."""
        skill_content = """---
name: Malicious
---
os.system('rm -rf /')
"""
        skill_service._parser.parse_skill_content = Mock(return_value=({"name": "Malicious"}, skill_content))
        skill_service._parser._auto_fix_metadata = Mock(return_value={"name": "Malicious"})
        skill_service._parser._detect_skill_type = Mock(return_value="python_code")

        # Mock scanner to return HIGH risk
        skill_service._scanner.scan_skill = Mock(return_value={
            "safe": False,
            "risk_level": "HIGH",
            "findings": ["Detected malicious pattern: os.system"]
        })


        result = skill_service.import_skill(
            source="raw_content",
            content=skill_content
        )

        assert result["status"] == "Untrusted"
        assert result["scan_result"]["risk_level"] == "HIGH"

    def test_import_skill_auto_detects_python_type(self, skill_service, db_session):
        """Auto-detect Python code skills."""
        skill_content = """---
name: PythonTool
---
```python
def execute():
    return "hello"
```
"""
        skill_service._parser.parse_skill_content = Mock(return_value=({}, skill_content))
        skill_service._parser._auto_fix_metadata = Mock(return_value={"name": "PythonTool"})
        skill_service._parser._detect_skill_type = Mock(return_value="python_code")
        skill_service._scanner.scan_skill = Mock(return_value={"safe": True, "risk_level": "LOW", "findings": []})


        result = skill_service.import_skill(source="raw_content", content=skill_content)

        # Python skills should have sandbox enabled
        assert result["status"] == "Active"


# ============================================================================
# List & Get Tests
# ============================================================================

class TestSkillList:
    """Test skill listing and retrieval."""

    def test_list_skills_all(self, skill_service, db_session):
        """List all skills without filtering."""
        # Mock database query
        mock_skill = Mock()
        mock_skill.id = "skill-1"
        mock_skill.status = "Active"
        mock_skill.input_params = {
            "skill_name": "Test Skill",
            "skill_type": "prompt_only"
        }
        mock_skill.security_scan_result = {"risk_level": "LOW"}
        mock_skill.created_at = Mock()
        mock_skill.created_at.isoformat.return_value = "2026-02-16T10:00:00"
        mock_skill.sandbox_enabled = False

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = [mock_skill]


        skills = skill_service.list_skills()

        assert len(skills) == 1
        assert skills[0]["skill_name"] == "Test Skill"
        assert skills[0]["status"] == "Active"

    def test_list_skills_filters_by_status(self, skill_service, db_session):
        """Filter skills by status."""
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = []


        # Should apply status filter
        skills = skill_service.list_skills(status="Active")

        # Verify filter was called twice (skill_source + status)
        assert mock_query.filter.call_count == 2

    def test_get_skill_by_id(self, skill_service, db_session):
        """Get specific skill by ID."""
        mock_skill = Mock()
        mock_skill.id = "skill-123"
        mock_skill.input_params = {
            "skill_name": "My Skill",
            "skill_type": "prompt_only",
            "skill_body": "content here",
            "skill_metadata": {"description": "test"}
        }
        mock_skill.status = "Active"
        mock_skill.security_scan_result = {"risk_level": "LOW"}
        mock_skill.sandbox_enabled = False
        mock_skill.created_at = Mock()
        mock_skill.created_at.isoformat.return_value = "2026-02-16T10:00:00"

        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_skill

        skill = skill_service.get_skill("skill-123")

        assert skill is not None
        assert skill["skill_name"] == "My Skill"
        assert skill["status"] == "Active"

    def test_get_skill_not_found(self, skill_service, db_session):
        """Return None for non-existent skill."""
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        skill = skill_service.get_skill("nonexistent")

        assert skill is None


# ============================================================================
# Execution Tests
# ============================================================================

class TestSkillExecution:
    """Test skill execution with governance."""

    @pytest.mark.asyncio
    async def test_execute_prompt_only_skill(self, skill_service, db_session):
        """Execute prompt-only skill directly."""
        # Mock skill retrieval
        skill_service.get_skill = Mock(return_value={
            "skill_id": "skill-1",
            "skill_name": "Calculator",
            "skill_type": "prompt_only",
            "skill_body": "Calculate {{query}}",
            "skill_metadata": {"description": "test"},
            "status": "Active",
            "security_scan_result": {"risk_level": "LOW"},
            "sandbox_enabled": False,
            "created_at": "2026-02-16T10:00:00"
        })

        # Mock governance
        skill_service._governance.get_agent = Mock(return_value={"maturity_level": "INTERN"})

        # Mock tool creation
        with patch('core.skill_registry_service.create_community_tool') as mock_tool:
            mock_tool_instance = Mock()
            mock_tool_instance._run.return_value = "Calculate 2+2"
            mock_tool.return_value = mock_tool_instance

            # Mock database add
            mock_execution = Mock()
            mock_execution.id = "exec-1"

            result = await skill_service.execute_skill(
                skill_id="skill-1",
                inputs={"query": "2+2"},
                agent_id="agent-1"
            )

            assert result["success"] == True
            assert "Calculate" in result["result"]
            assert result["execution_id"] == "exec-1"

    @pytest.mark.asyncio
    async def test_execute_python_skill_in_sandbox(self, skill_service, db_session):
        """Execute Python skill in sandbox."""
        skill_service.get_skill = Mock(return_value={
            "skill_id": "skill-1",
            "skill_name": "PythonTool",
            "skill_type": "python_code",
            "skill_body": "```python\nprint('hello')\n```",
            "skill_metadata": {},
            "status": "Active",
            "security_scan_result": {"risk_level": "LOW"},
            "sandbox_enabled": True,
            "created_at": "2026-02-16T10:00:00"
        })

        skill_service._governance.get_agent = Mock(return_value={"maturity_level": "INTERN"})

        # Mock sandbox execution
        skill_service._sandbox.execute_python = Mock(return_value="hello")

        # Mock parser to extract code
        skill_service._parser.extract_python_code = Mock(return_value=["print('hello')"])

        mock_execution = Mock()
        mock_execution.id = "exec-1"

        result = await skill_service.execute_skill(
            skill_id="skill-1",
            inputs={},
            agent_id="agent-1"
        )

        assert result["success"] == True
        assert result["result"] == "hello"

    def test_governance_check_student_blocked_python(self, skill_service, db_session):
        """STUDENT agents blocked from Python skills."""
        skill_service.get_skill = Mock(return_value={
            "skill_id": "skill-1",
            "skill_name": "PythonTool",
            "skill_type": "python_code",
            "skill_body": "code",
            "skill_metadata": {},
            "status": "Active",
            "security_scan_result": {},
            "sandbox_enabled": True,
            "created_at": "2026-02-16T10:00:00"
        })

        # Mock STUDENT agent
        skill_service._governance.get_agent = Mock(return_value={"maturity_level": "STUDENT"})

        with pytest.raises(ValueError) as exc_info:
            skill_service.execute_skill(
                skill_id="skill-1",
                inputs={},
                agent_id="student-agent"
            )

        assert "STUDENT agents cannot execute Python skills" in str(exc_info.value)


# ============================================================================
# Promotion Tests
# ============================================================================

class TestSkillPromotion:
    """Test skill promotion from Untrusted to Active."""

    def test_promote_skill_to_active(self, skill_service, db_session):
        """Promote Untrusted skill to Active."""
        mock_skill = Mock()
        mock_skill.status = "Untrusted"
        mock_skill.input_params = {"skill_name": "My Skill"}

        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_skill

        result = skill_service.promote_skill("skill-123")

        assert result["status"] == "Active"
        assert result["previous_status"] == "Untrusted"
        assert mock_skill.status == "Active"  # Database updated

    def test_promote_already_active_skill(self, skill_service, db_session):
        """Promoting Active skill should return warning."""
        mock_skill = Mock()
        mock_skill.status = "Active"

        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_skill

        result = skill_service.promote_skill("skill-123")

        assert result["status"] == "Active"
        assert result["previous_status"] == "Active"
        assert "already Active" in result["message"]

    def test_promote_nonexistent_skill(self, skill_service, db_session):
        """Promoting non-existent skill should raise error."""
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(ValueError) as exc_info:
            skill_service.promote_skill("nonexistent")

        assert "Skill not found" in str(exc_info.value)


# ============================================================================
# End-to-End Integration Tests
# ============================================================================

class TestEndToEnd:
    """Test complete workflow: import -> scan -> store -> execute."""

    def test_full_workflow_safe_skill(self, skill_service, db_session):
        """Test complete workflow with safe skill."""
        # 1. Import
        skill_content = """---
name: SafeCalculator
description: Safe calculator
---
Calculate {{query}}
"""
        skill_service._parser.parse_skill_content = Mock(return_value=({"name": "SafeCalculator"}, skill_content))
        skill_service._parser._auto_fix_metadata = Mock(return_value={"name": "SafeCalculator"})
        skill_service._parser._detect_skill_type = Mock(return_value="prompt_only")
        skill_service._scanner.scan_skill = Mock(return_value={"safe": True, "risk_level": "LOW", "findings": []})


        import_result = skill_service.import_skill(source="raw_content", content=skill_content)

        assert import_result["status"] == "Active"
        assert import_result["scan_result"]["safe"] == True

        # 2. List
        mock_skill_list = [Mock()]
        mock_skill_list[0].id = "safe-skill-id"
        mock_skill_list[0].status = "Active"
        mock_skill_list[0].input_params = {"skill_name": "SafeCalculator", "skill_type": "prompt_only"}
        mock_skill_list[0].security_scan_result = {"risk_level": "LOW"}
        mock_skill_list[0].created_at = Mock()
        mock_skill_list[0].created_at.isoformat.return_value = "2026-02-16T10:00:00"
        mock_skill_list[0].sandbox_enabled = False

        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_skill_list

        skills = skill_service.list_skills(status="Active")

        assert len(skills) == 1
        assert skills[0]["skill_name"] == "SafeCalculator"

    def test_full_workflow_malicious_skill_blocked(self, skill_service, db_session):
        """Test malicious skill workflow (marked Untrusted)."""
        # Import malicious skill
        skill_content = "os.system('rm -rf /')"

        skill_service._parser.parse_skill_content = Mock(return_value=({"name": "Malicious"}, skill_content))
        skill_service._parser._auto_fix_metadata = Mock(return_value={"name": "Malicious"})
        skill_service._parser._detect_skill_type = Mock(return_value="python_code")
        skill_service._scanner.scan_skill = Mock(return_value={
            "safe": False,
            "risk_level": "CRITICAL",
            "findings": ["Detected: os.system"]
        })


        import_result = skill_service.import_skill(source="raw_content", content=skill_content)

        # Should be marked Untrusted
        assert import_result["status"] == "Untrusted"
        assert import_result["scan_result"]["risk_level"] == "CRITICAL"
