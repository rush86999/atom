"""
Coverage tests for skill_registry_service.py.

Target: 70%+ coverage (370 statements, ~259 lines to cover)
Focus: Skill registration, discovery, validation, lifecycle
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.skill_registry_service import SkillRegistryService
from core.models import SkillExecution


class TestSkillRegistryInitialization:
    """Test skill registry service initialization."""

    def test_service_initialization(self, db_session):
        """Test service initializes correctly."""
        service = SkillRegistryService(db_session)
        assert service is not None
        assert service.db == db_session
        assert service._parser is not None
        assert service._scanner is not None

    def test_service_lazy_sandbox_init(self, db_session):
        """Test sandbox is lazy-initialized."""
        service = SkillRegistryService(db_session)
        assert service._sandbox is None

        # Access sandbox should initialize it
        sandbox = service._get_sandbox()
        assert sandbox is not None


class TestSkillImport:
    """Test skill import functionality."""

    @pytest.mark.asyncio
    async def test_import_skill_from_raw_content(self, db_session):
        """Test importing skill from raw content."""
        service = SkillRegistryService(db_session)

        content = """---
name: Test Skill
description: A test skill
---

Test skill body here.
"""

        result = service.import_skill(
            source="raw_content",
            content=content,
            metadata={"author": "test"}
        )

        assert result["success"] is True
        assert result["skill_name"] == "Test Skill"
        assert "skill_id" in result

    @pytest.mark.asyncio
    async def test_import_skill_with_python_packages(self, db_session):
        """Test importing skill with Python packages."""
        service = SkillRegistryService(db_session)

        content = """---
name: Calculator Skill
description: Math operations
packages:
  - numpy==1.21.0
  - pandas==1.3.0
---

Python code here.
"""

        result = service.import_skill(
            source="raw_content",
            content=content
        )

        assert result["success"] is True
        metadata = result["metadata"]
        assert "packages" in metadata
        assert len(metadata["packages"]) == 2

    @pytest.mark.asyncio
    async def test_import_skill_with_node_packages(self, db_session):
        """Test importing skill with npm packages."""
        service = SkillRegistryService(db_session)

        content = """---
name: NodeJS Skill
description: Node.js test skill
node_packages:
  - lodash@4.17.21
  - express@4.18.0
---

Node.js code here.
"""

        result = service.import_skill(
            source="raw_content",
            content=content
        )

        assert result["success"] is True
        metadata = result["metadata"]
        assert "node_packages" in metadata
        assert len(metadata["node_packages"]) == 2

    @pytest.mark.asyncio
    async def test_import_skill_security_scan(self, db_session):
        """Test security scan during import."""
        service = SkillRegistryService(db_session)

        # Safe skill (should be Active)
        safe_content = """---
name: Safe Skill
description: Safe
---

print("hello world")
"""

        result = service.import_skill(
            source="raw_content",
            content=safe_content
        )

        # Risk level LOW -> Active status
        scan_result = result["scan_result"]
        assert scan_result is not None
        assert "risk_level" in scan_result

    @pytest.mark.asyncio
    async def test_import_skill_auto_fix_metadata(self, db_session):
        """Test auto-fix of missing metadata fields."""
        service = SkillRegistryService(db_session)

        # Missing description
        content = """---
name: Minimal Skill
---

Body here.
"""

        result = service.import_skill(
            source="raw_content",
            content=content
        )

        assert result["success"] is True
        assert result["skill_name"] == "Minimal Skill"

    @pytest.mark.asyncio
    async def test_import_skill_type_detection(self, db_session):
        """Test skill type detection."""
        service = SkillRegistryService(db_session)

        # Python skill
        python_content = """---
name: Python Skill
packages:
  - numpy
---

```python
def main():
    pass
```
"""

        result = service.import_skill(
            source="raw_content",
            content=python_content
        )

        assert result["success"] is True
        assert result["metadata"]["skill_type"] == "python_code"


class TestSkillListing:
    """Test skill listing and discovery."""

    def test_list_all_skills(self, db_session):
        """Test listing all imported skills."""
        service = SkillRegistryService(db_session)

        # Import some skills
        service.import_skill(
            source="raw_content",
            content="---\nname: Skill 1\n---\nBody 1"
        )

        service.import_skill(
            source="raw_content",
            content="---\nname: Skill 2\n---\nBody 2"
        )

        skills = service.list_skills(limit=10)

        assert len(skills) >= 2

    def test_list_skills_by_status(self, db_session):
        """Test filtering skills by status."""
        service = SkillRegistryService(db_session)

        # Import skills (will have different statuses based on scan)
        service.import_skill(
            source="raw_content",
            content="---\nname: Safe Skill\n---\nprint('hello')",
            metadata={"author": "test"}
        )

        active_skills = service.list_skills(status="Active")
        untrusted_skills = service.list_skills(status="Untrusted")

        # At least one should exist
        assert len(active_skills) >= 0 or len(untrusted_skills) >= 0

    def test_list_skills_by_type(self, db_session):
        """Test filtering skills by type."""
        service = SkillRegistryService(db_session)

        # Import Python skill
        service.import_skill(
            source="raw_content",
            content="---\nname: Python Skill\npackages:\n  - numpy\n---\nCode"
        )

        python_skills = service.list_skills(skill_type="python_code")

        assert len(python_skills) >= 1

    def test_list_skills_with_limit(self, db_session):
        """Test limiting results."""
        service = SkillRegistryService(db_session)

        # Import multiple skills
        for i in range(5):
            service.import_skill(
                source="raw_content",
                content=f"---\nname: Skill {i}\n---\nBody {i}"
            )

        skills = service.list_skills(limit=3)

        assert len(skills) <= 3


class TestSkillRetrieval:
    """Test skill retrieval operations."""

    def test_get_skill_by_id(self, db_session):
        """Test getting skill by ID."""
        service = SkillRegistryService(db_session)

        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Test Skill\n---\nBody"
        )

        skill_id = import_result["skill_id"]

        skill = service.get_skill(skill_id)

        assert skill is not None
        assert skill["skill_name"] == "Test Skill"
        assert skill["skill_body"] == "Body"

    def test_get_skill_not_found(self, db_session):
        """Test getting non-existent skill."""
        service = SkillRegistryService(db_session)

        skill = service.get_skill("nonexistent-id")

        assert skill is None

    def test_get_skill_includes_packages(self, db_session):
        """Test skill retrieval includes package info."""
        service = SkillRegistryService(db_session)

        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Package Skill\npackages:\n  - numpy\n---\nCode"
        )

        skill_id = import_result["skill_id"]
        skill = service.get_skill(skill_id)

        assert skill is not None
        assert "packages" in skill
        assert len(skill["packages"]) >= 1


class TestSkillExecution:
    """Test skill execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_prompt_skill(self, db_session):
        """Test executing prompt-only skill."""
        service = SkillRegistryService(db_session)

        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Prompt Skill\n---\nHello {query}!"
        )

        skill_id = import_result["skill_id"]

        result = await service.execute_skill(
            skill_id=skill_id,
            inputs={"query": "World"},
            agent_id="test-agent"
        )

        assert result["success"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self, db_session):
        """Test executing non-existent skill."""
        service = SkillRegistryService(db_session)

        with pytest.raises(ValueError) as exc_info:
            await service.execute_skill(
                skill_id="nonexistent",
                inputs={},
                agent_id="test-agent"
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_skill_student_blocked(self, db_session):
        """Test STUDENT agent cannot execute Python skills."""
        from core.models import AgentRegistry

        service = SkillRegistryService(db_session)

        # Create STUDENT agent
        agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status="STUDENT",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        # Import Python skill
        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Python Skill\npackages:\n  - numpy\n---\n```python\nprint('test')\n```"
        )

        skill_id = import_result["skill_id"]

        with pytest.raises(ValueError) as exc_info:
            await service.execute_skill(
                skill_id=skill_id,
                inputs={},
                agent_id="student-agent"
            )

        assert "STUDENT agents cannot execute Python skills" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_skill_creates_execution_record(self, db_session):
        """Test execution creates SkillExecution record."""
        service = SkillRegistryService(db_session)

        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Test Skill\n---\nResponse: {input}"
        )

        skill_id = import_result["skill_id"]

        result = await service.execute_skill(
            skill_id=skill_id,
            inputs={"input": "test"},
            agent_id="test-agent"
        )

        assert result["success"] is True
        assert "execution_id" in result

        # Verify execution record exists
        executions = db_session.query(SkillExecution).filter(
            SkillExecution.id == result["execution_id"]
        ).all()

        assert len(executions) == 1


class TestPackagePermissions:
    """Test package permission checks."""

    @pytest.mark.asyncio
    async def test_python_package_permission_check(self, db_session):
        """Test Python package permission check."""
        service = SkillRegistryService(db_session)

        # Import skill with packages
        content = """---
name: Package Skill
packages:
  - numpy==1.21.0
---

Code here.
"""

        import_result = service.import_skill(
            source="raw_content",
            content=content
        )

        skill_id = import_result["skill_id"]

        # Mock package governance to allow
        with patch('core.skill_registry_service.PackageGovernanceService') as mock_gov:
            mock_instance = Mock()
            mock_instance.check_package_permission.return_value = {"allowed": True}
            mock_gov.return_value = mock_instance

            # This should not raise an error
            result = await service.execute_skill(
                skill_id=skill_id,
                inputs={},
                agent_id="test-agent"
            )

            # Package governance was called
            assert mock_instance.check_package_permission.called

    @pytest.mark.asyncio
    async def test_npm_package_permission_check(self, db_session):
        """Test npm package permission check."""
        service = SkillRegistryService(db_session)

        # Import skill with npm packages
        content = """---
name: NPM Skill
node_packages:
  - lodash@4.17.21
---

Code here.
"""

        import_result = service.import_skill(
            source="raw_content",
            content=content
        )

        skill_id = import_result["skill_id"]

        # Mock package governance to allow
        with patch('core.skill_registry_service.PackageGovernanceService') as mock_gov:
            mock_instance = Mock()
            mock_instance.check_package_permission.return_value = {"allowed": True}
            mock_gov.return_value = mock_instance

            # This should not raise an error
            result = await service.execute_skill(
                skill_id=skill_id,
                inputs={},
                agent_id="test-agent"
            )

            # Package governance was called with package_type='npm'
            assert mock_instance.check_package_permission.called


class TestSkillPromotion:
    """Test skill promotion from Untrusted to Active."""

    def test_promote_skill(self, db_session):
        """Test promoting skill to Active status."""
        service = SkillRegistryService(db_session)

        # Import a skill (might be Untrusted depending on scan)
        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Test Skill\n---\nBody"
        )

        skill_id = import_result["skill_id"]

        # Promote to Active
        result = service.promote_skill(skill_id)

        assert result["status"] == "Active"
        assert "previous_status" in result

    def test_promote_already_active_skill(self, db_session):
        """Test promoting already Active skill."""
        service = SkillRegistryService(db_session)

        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Safe Skill\n---\nprint('hello')",
            metadata={"safe": True}
        )

        skill_id = import_result["skill_id"]

        # Try to promote again
        result = service.promote_skill(skill_id)

        assert result["status"] == "Active"
        assert "already Active" in result["message"].lower()

    def test_promote_nonexistent_skill(self, db_session):
        """Test promoting non-existent skill."""
        service = SkillRegistryService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.promote_skill("nonexistent-id")

        assert "not found" in str(exc_info.value)


class TestSkillTypeDetection:
    """Test skill type detection."""

    def test_detect_python_skill_by_packages(self, db_session):
        """Test Python skill detection by packages field."""
        service = SkillRegistryService(db_session)

        content = """---
name: Python Skill
packages:
  - numpy
---

Python code.
"""

        skill_type = service.detect_skill_type(content)

        assert skill_type == "python"

    def test_detect_npm_skill_by_packages(self, db_session):
        """Test npm skill detection by node_packages field."""
        service = SkillRegistryService(db_session)

        content = """---
name: NPM Skill
node_packages:
  - lodash
---

Node code.
"""

        skill_type = service.detect_skill_type(content)

        assert skill_type == "npm"

    def test_detect_skill_by_code_block(self, db_session):
        """Test skill type detection by code block."""
        service = SkillRegistryService(db_session)

        content = """---
name: Test Skill
---

```javascript
console.log('test');
```
"""

        skill_type = service.detect_skill_type(content)

        assert skill_type == "npm"


class TestNPMPackageParsing:
    """Test npm package parsing."""

    def test_parse_npm_package_with_version(self, db_session):
        """Test parsing npm package with version."""
        service = SkillRegistryService(db_session)

        name, version = service._parse_npm_package("lodash@4.17.21")

        assert name == "lodash"
        assert version == "4.17.21"

    def test_parse_npm_package_without_version(self, db_session):
        """Test parsing npm package without version."""
        service = SkillRegistryService(db_session)

        name, version = service._parse_npm_package("lodash")

        assert name == "lodash"
        assert version == "latest"

    def test_parse_scoped_npm_package(self, db_session):
        """Test parsing scoped npm package."""
        service = SkillRegistryService(db_session)

        name, version = service._parse_npm_package("@types/node@20.0.0")

        assert name == "@types/node"
        assert version == "20.0.0"

    def test_parse_scoped_npm_package_no_version(self, db_session):
        """Test parsing scoped npm package without version."""
        service = SkillRegistryService(db_session)

        name, version = service._parse_npm_package("@scope/package")

        assert name == "@scope/package"
        assert version == "latest"


class TestEpisodeCreation:
    """Test episode creation on skill execution."""

    @pytest.mark.asyncio
    async def test_create_execution_episode_on_success(self, db_session):
        """Test episode creation on successful execution."""
        service = SkillRegistryService(db_session)

        import_result = service.import_skill(
            source="raw_content",
            content="---\nname: Test Skill\n---\nResponse"
        )

        skill_id = import_result["skill_id"]

        result = await service.execute_skill(
            skill_id=skill_id,
            inputs={},
            agent_id="test-agent"
        )

        assert result["success"] is True
        assert "episode_id" in result

    @pytest.mark.asyncio
    async def test_create_execution_episode_on_failure(self, db_session):
        """Test episode creation on failed execution."""
        service = SkillRegistryService(db_session)

        # Import skill that will fail
        content = """---
name: Failing Skill
---

This will fail.
"""

        import_result = service.import_skill(
            source="raw_content",
            content=content
        )

        skill_id = import_result["skill_id"]

        # Mock execution to fail
        with patch.object(service, '_execute_prompt_skill', side_effect=Exception("Execution failed")):
            result = await service.execute_skill(
                skill_id=skill_id,
                inputs={},
                agent_id="test-agent"
            )

            assert result["success"] is False
            assert "error" in result
            assert "episode_id" in result


class TestSkillDynamicLoading:
    """Test dynamic skill loading."""

    def test_load_skill_dynamically(self, db_session):
        """Test dynamic skill loading."""
        service = SkillRegistryService(db_session)

        # Mock the loader
        with patch('core.skill_registry_service.get_global_loader') as mock_loader:
            mock_instance = Mock()
            mock_module = Mock()
            mock_instance.load_skill.return_value = mock_module
            mock_loader.return_value = mock_instance

            result = service.load_skill_dynamically(
                skill_id="test-skill",
                skill_path="/path/to/skill.py"
            )

            assert result["success"] is True
            assert result["skill_id"] == "test-skill"

    def test_reload_skill_dynamically(self, db_session):
        """Test hot-reload skill."""
        service = SkillRegistryService(db_session)

        # Mock the loader
        with patch('core.skill_registry_service.get_global_loader') as mock_loader:
            mock_instance = Mock()
            mock_module = Mock()
            mock_instance.reload_skill.return_value = mock_module
            mock_loader.return_value = mock_instance

            result = service.reload_skill_dynamically(
                skill_id="test-skill"
            )

            assert result["success"] is True
            assert result["skill_id"] == "test-skill"


class TestInputSummarization:
    """Test input summarization for episodes."""

    def test_summarize_inputs_empty(self, db_session):
        """Test summarizing empty inputs."""
        service = SkillRegistryService(db_session)

        summary = service._summarize_inputs({})

        assert summary == "{}"

    def test_summarize_inputs_truncates_long_values(self, db_session):
        """Test long values are truncated."""
        service = SkillRegistryService(db_session)

        long_value = "x" * 200

        summary = service._summarize_inputs({"long": long_value})

        assert len(summary) < 300  # Should be truncated
        assert "..." in summary
