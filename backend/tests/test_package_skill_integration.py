"""
Package Skill Integration Tests

Test coverage for end-to-end package workflow:
- SkillParser extracts packages from SKILL.md
- CommunitySkillTool uses packages during execution
- SkillRegistryService executes skills with packages
- Permission checks prevent unauthorized package usage
- Vulnerability scanning blocks insecure packages
- Error handling for invalid packages and installation failures

Reference: Phase 35 Plan 06 - Skill Integration
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from core.skill_parser import SkillParser
from core.skill_adapter import CommunitySkillTool, create_community_tool
from core.skill_registry_service import SkillRegistryService
from tests.factories import AgentFactory


@pytest.fixture
def skill_with_packages():
    """Create test SKILL.md with packages."""
    content = '''---
name: Data Processing Skill
description: Processes data using numpy and pandas
packages:
  - numpy==1.21.0
  - pandas>=1.3.0
  - requests
---

```python
import numpy as np
import pandas as pd

def execute(query: str) -> str:
    data = np.array([1, 2, 3])
    return f"Processed {len(data)} items with numpy and pandas"
```
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def skill_without_packages():
    """Create test SKILL.md without packages."""
    content = '''---
name: Simple Skill
description: A simple skill without packages
---

```python
def execute(query: str) -> str:
    return f"Simple: {query}"
```
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def skill_with_invalid_packages():
    """Create test SKILL.md with invalid package format."""
    content = '''---
name: Invalid Skill
description: Skill with invalid package format
packages:
  - numpy==1.21.0
  - invalid-package-format!!!
  - pandas>=1.3.0
---

```python
def execute(query: str) -> str:
    return "Test"
```
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    os.unlink(path)


class TestSkillParserPackageExtraction:
    """SkillParser extracts packages from frontmatter."""

    def test_extract_packages_from_skill(self, skill_with_packages):
        """Test that SkillParser extracts packages from SKILL.md frontmatter."""
        parser = SkillParser()
        metadata, body = parser.parse_skill_file(skill_with_packages)

        assert "packages" in metadata
        assert len(metadata["packages"]) == 3
        assert "numpy==1.21.0" in metadata["packages"]
        assert "pandas>=1.3.0" in metadata["packages"]
        assert "requests" in metadata["packages"]

    def test_skill_without_packages_has_empty_list(self, skill_without_packages):
        """Test that skills without packages have empty list."""
        parser = SkillParser()
        metadata, body = parser.parse_skill_file(skill_without_packages)

        assert "packages" in metadata
        assert len(metadata["packages"]) == 0
        assert metadata["packages"] == []

    def test_invalid_package_format_is_filtered(self, skill_with_invalid_packages):
        """Test that invalid package formats are filtered out."""
        parser = SkillParser()
        metadata, body = parser.parse_skill_file(skill_with_invalid_packages)

        # Should filter out invalid package
        assert "numpy==1.21.0" in metadata["packages"]
        assert "pandas>=1.3.0" in metadata["packages"]
        assert "invalid-package-format!!!" not in metadata["packages"]
        assert len(metadata["packages"]) == 2  # Only 2 valid packages

    def test_packages_field_type_validation(self):
        """Test that non-list packages field is handled gracefully."""
        content = '''---
name: Type Error Skill
packages: "not-a-list"
---

Test skill.
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            path = f.name

        parser = SkillParser()
        metadata, body = parser.parse_skill_file(path)

        # Should return empty list for invalid type
        assert metadata["packages"] == []

        os.unlink(path)


class TestCommunitySkillToolWithPackages:
    """CommunitySkillTool executes with packages."""

    def test_tool_accepts_packages_parameter(self):
        """Test that CommunitySkillTool accepts packages parameter."""
        tool = CommunitySkillTool(
            name='test-skill',
            description='Test skill with packages',
            skill_type='python_code',
            code='print(query)',
            skill_id='test-skill',
            packages=['numpy==1.21.0', 'pandas>=1.3.0']
        )

        assert tool.packages == ['numpy==1.21.0', 'pandas>=1.3.0']
        assert len(tool.packages) == 2

    @patch('core.package_installer.PackageInstaller.install_packages')
    @patch('core.package_installer.PackageInstaller.execute_with_packages')
    def test_tool_with_packages_installs_and_executes(
        self,
        mock_execute,
        mock_install,
        skill_with_packages
    ):
        """Test that tool with packages installs and executes correctly."""
        parser = SkillParser()
        metadata, body = parser.parse_skill_file(skill_with_packages)

        # Extract Python code
        code_blocks = parser.extract_python_code(body)
        code = code_blocks[0]

        # Mock installation
        mock_install.return_value = {
            "success": True,
            "image_tag": "atom-skill:data-processing-skill-v1",
            "vulnerabilities": []
        }

        # Mock execution
        mock_execute.return_value = "Processed 3 items with numpy and pandas"

        tool = CommunitySkillTool(
            name="Data Processing Skill",
            description="Processes data",
            skill_type="python_code",
            skill_content=code,
            skill_id="data-processing-skill",
            packages=metadata["packages"]
        )

        output = tool._run(query="test")

        assert "Processed 3 items" in output
        mock_install.assert_called_once()
        mock_execute.assert_called_once()

    @patch('core.package_installer.PackageInstaller.install_packages')
    def test_tool_with_packages_handles_installation_failure(self, mock_install):
        """Test that tool handles installation failures gracefully."""
        mock_install.return_value = {
            "success": False,
            "error": "Docker daemon not running",
            "image_tag": None
        }

        tool = CommunitySkillTool(
            name="Test Skill",
            description="Test",
            skill_type="python_code",
            skill_content="print('test')",
            skill_id="test-skill",
            packages=["numpy==1.21.0"]
        )

        output = tool._run(query="test")

        assert "PACKAGE_INSTALLATION_ERROR" in output
        assert "Docker daemon not running" in output

    @patch('core.skill_adapter.HazardSandbox')
    def test_tool_without_packages_uses_default_sandbox(self, mock_sandbox):
        """Test that tool without packages uses default sandbox."""
        # Setup mock
        mock_instance = MagicMock()
        mock_sandbox.return_value = mock_instance
        mock_instance.execute_python.return_value = "hello"

        tool = CommunitySkillTool(
            name="Simple Skill",
            description="Simple skill",
            skill_type="python_code",
            skill_content="print('hello')",
            skill_id="simple-skill",
            packages=[]
        )

        output = tool._run(query="test")

        assert "hello" in output
        # Should use sandbox, not installer
        mock_instance.execute_python.assert_called_once()


class TestCreateCommunityToolWithPackages:
    """Factory function creates tools with packages."""

    def test_factory_extracts_packages_from_parsed_skill(self, skill_with_packages):
        """Test that factory function extracts packages from parsed skill."""
        parser = SkillParser()
        metadata, body = parser.parse_skill_file(skill_with_packages)

        # Extract Python code
        code_blocks = parser.extract_python_code(body)
        code = code_blocks[0]

        tool = create_community_tool({
            "name": metadata["name"],
            "description": metadata["description"],
            "skill_type": metadata["skill_type"],
            "skill_content": code,
            "skill_id": "data-processing-skill",
            "packages": metadata["packages"]
        })

        assert tool.packages == metadata["packages"]
        assert len(tool.packages) == 3

    def test_factory_handles_missing_packages_gracefully(self):
        """Test that factory handles missing packages field."""
        tool = create_community_tool({
            "name": "Simple Skill",
            "description": "Simple",
            "skill_type": "prompt_only",
            "skill_content": "Hello {{query}}",
            "skill_id": "simple-skill"
            # No packages field
        })

        assert tool.packages == []


class TestSkillRegistryServicePackageIntegration:
    """SkillRegistryService executes skills with packages."""

    @patch('core.skill_registry_service.AgentGovernanceService.get_agent_capabilities')
    @patch('core.skill_registry_service.HazardSandbox')
    @patch('core.package_installer.PackageInstaller.install_packages')
    @patch('core.package_installer.PackageInstaller.execute_with_packages')
    @patch('core.package_governance_service.PackageGovernanceService.check_package_permission')
    @pytest.mark.asyncio
    async def test_execute_skill_with_packages(
        self,
        mock_permission,
        mock_execute,
        mock_install,
        mock_sandbox,
        mock_agent_caps,
        skill_with_packages,
        db_session: Session
    ):
        """Test that execute_skill handles packages correctly."""
        # Create autonomous agent
        agent = AgentFactory(status="AUTONOMOUS", _session=db_session)
        db_session.commit()

        # Mock agent capabilities
        mock_agent_caps.return_value = {
            "maturity_level": "AUTONOMOUS",
            "allowed_actions": ["presentations", "streaming", "state_changes", "deletions"]
        }

        # Mock permissions allowed
        mock_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        # Mock installation
        mock_install.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-v1",
            "vulnerabilities": []
        }

        # Mock execution
        mock_execute.return_value = "Processed 3 items"

        # Import skill with packages
        service = SkillRegistryService(db_session)
        import_result = service.import_skill(
            source="raw_content",
            content=f'''---
name: Data Processing Skill
packages:
  - numpy==1.21.0
  - pandas>=1.3.0
---

```python
def execute(query: str) -> str:
    return "Processed 3 items"
```
'''
        )

        skill_id = import_result["skill_id"]

        # Execute skill
        result = await service.execute_skill(
            skill_id=skill_id,
            inputs={"query": "test"},
            agent_id=agent.id
        )

        assert result["success"] == True
        assert "Processed 3 items" in result["result"]

    @patch('core.skill_registry_service.AgentGovernanceService.get_agent_capabilities')
    @patch('core.skill_registry_service.HazardSandbox')
    @patch('core.package_governance_service.PackageGovernanceService.check_package_permission')
    @patch('core.package_governance_service.PackageGovernanceService', autospec=True)
    @pytest.mark.asyncio
    async def test_execute_skill_with_packages_permission_denied(
        self,
        mock_pkg_gov_service,
        mock_permission,
        mock_sandbox,
        mock_agent_caps,
        skill_with_packages,
        db_session: Session
    ):
        """Test that execute_skill blocks unauthorized package usage."""
        # Create student agent
        agent = AgentFactory(status="AUTONOMOUS", _session=db_session)  # Use AUTONOMOUS to pass maturity check
        db_session.commit()

        # Mock agent capabilities
        mock_agent_caps.return_value = {
            "maturity_level": "AUTONOMOUS",
            "allowed_actions": ["presentations", "streaming", "state_changes", "deletions"]
        }

        # Mock permission denied
        mock_permission.return_value = {
            "allowed": False,
            "maturity_required": "INTERN",
            "reason": "Package numpy requires INTERN maturity"
        }

        # Import skill with packages
        service = SkillRegistryService(db_session)
        import_result = service.import_skill(
            source="raw_content",
            content=open(skill_with_packages).read()
        )

        skill_id = import_result["skill_id"]

        # Execute skill - should fail permission check
        result = await service.execute_skill(
            skill_id=skill_id,
            inputs={"query": "test"},
            agent_id=agent.id
        )

        assert result["success"] == False
        assert "Package permission denied" in result["error"]

    @patch('core.skill_registry_service.AgentGovernanceService.get_agent_capabilities')
    @patch('core.skill_registry_service.HazardSandbox')
    @patch('core.package_installer.PackageInstaller.install_packages')
    @pytest.mark.asyncio
    async def test_execute_skill_with_packages_installation_failure(
        self,
        mock_install,
        mock_sandbox,
        mock_agent_caps,
        skill_with_packages,
        db_session: Session
    ):
        """Test that execute_skill handles installation failures."""
        # Create autonomous agent
        agent = AgentFactory(status="AUTONOMOUS", _session=db_session)
        db_session.commit()

        # Mock agent capabilities to pass maturity check
        mock_agent_caps.return_value = {
            "maturity_level": "AUTONOMOUS",
            "allowed_actions": ["presentations", "streaming", "state_changes", "deletions"]
        }

        # Mock installation failure
        mock_install.return_value = {
            "success": False,
            "error": "Network error during package installation",
            "image_tag": None
        }

        # Import skill with packages
        service = SkillRegistryService(db_session)
        import_result = service.import_skill(
            source="raw_content",
            content=open(skill_with_packages).read()
        )

        skill_id = import_result["skill_id"]

        # Execute skill - should fail installation
        result = await service.execute_skill(
            skill_id=skill_id,
            inputs={"query": "test"},
            agent_id=agent.id
        )

        assert result["success"] == False
        assert "Package installation failed" in result["error"]


class TestEndToEndPackageWorkflow:
    """End-to-end tests for package workflow."""

    @patch('core.skill_registry_service.HazardSandbox')
    @patch('core.package_installer.PackageInstaller.install_packages')
    @patch('core.package_installer.PackageInstaller.execute_with_packages')
    @patch('core.package_governance_service.PackageGovernanceService.check_package_permission')
    @pytest.mark.asyncio
    async def test_full_package_workflow(
        self,
        mock_permission,
        mock_execute,
        mock_install,
        mock_sandbox,
        db_session: Session
    ):
        """Test full workflow: import → permission check → install → execute."""
        # Create autonomous agent
        agent = AgentFactory(status="AUTONOMOUS", _session=db_session)
        db_session.commit()

        # Mock permission allowed
        mock_permission.return_value = {
            "allowed": True,
            "maturity_required": "INTERN",
            "reason": None
        }

        # Mock installation
        mock_install.return_value = {
            "success": True,
            "image_tag": "atom-skill:workflow-test-v1",
            "vulnerabilities": []
        }

        # Mock execution
        mock_execute.return_value = "Workflow test successful"

        # Step 1: Import skill with packages
        service = SkillRegistryService(db_session)
        import_result = service.import_skill(
            source="raw_content",
            content='''---
name: Workflow Test Skill
description: Test full package workflow
packages:
  - requests==2.31.0
---

```python
import requests

def execute(query: str) -> str:
    return "Workflow test successful"
```
'''
        )

        # Accept either Active or Untrusted (depends on security scanner)
        assert import_result["status"] in ["Active", "Untrusted"]
        assert "packages" in import_result["metadata"]

        # Step 2: Execute skill
        result = await service.execute_skill(
            skill_id=import_result["skill_id"],
            inputs={"query": "test"},
            agent_id=agent.id
        )

        assert result["success"] == True
        assert "Workflow test successful" in result["result"]

        # Verify workflow: permission check → install → execute
        assert mock_permission.called
        assert mock_install.called
        assert mock_execute.called
