"""
Coverage-driven tests for skill_registry_service.py (0% -> 75%+ target)

Tests cover skill registration, discovery, validation, versioning, and metadata management.
Uses mock-based testing for file system, skill loader, and external dependencies.

Target: 75%+ coverage (280+ of 370 statements)
Baseline: 0% coverage
"""
import datetime
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.skill_registry_service import SkillRegistryService
from core.models import SkillExecution


class TestSkillRegistryServiceCoverage:
    """Coverage-driven tests for skill_registry_service.py (0% -> 75%+ target)"""

    @pytest.mark.parametrize("skill_type,source_path", [
        ("builtin", "skills/builtin/"),
        ("community", "skills/community/"),
        ("custom", "skills/custom/"),
    ])
    def test_import_skill_types(self, skill_type, source_path, db_session, monkeypatch):
        """Cover skill import (lines 93-219) - different skill types"""
        # Mock frontmatter
        mock_post = Mock()
        mock_post.metadata = {
            "name": f"test_{skill_type}_skill",
            "description": "Test skill description",
            "skill_type": skill_type,
            "packages": [],
            "node_packages": []
        }
        mock_post.content = "# Test skill body"

        import frontmatter
        monkeypatch.setattr(frontmatter, 'loads', Mock(return_value=mock_post))

        # Mock parser methods
        monkeypatch.setattr('core.skill_registry_service.SkillParser._auto_fix_metadata', Mock(return_value=mock_post.metadata))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._extract_packages', Mock(return_value=[]))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._extract_node_packages', Mock(return_value=[]))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._extract_package_manager', Mock(return_value="pip"))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._detect_skill_type', Mock(return_value="prompt_only"))

        # Mock scanner
        mock_scanner_instance = Mock()
        mock_scanner_instance.scan_skill.return_value = {"risk_level": "LOW"}
        monkeypatch.setattr('core.skill_registry_service.SkillSecurityScanner', Mock(return_value=mock_scanner_instance))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.import_skill(
            source="raw_content",
            content="---\nname: test_skill\n---\nTest body",
            metadata={"imported_by": "test_user"}
        )

        assert result["status"] == "Active"
        assert result["skill_name"] == f"test_{skill_type}_skill"
        assert "scan_result" in result

    @pytest.mark.parametrize("risk_level,expected_status", [
        ("LOW", "Active"),
        ("MEDIUM", "Untrusted"),
        ("HIGH", "Untrusted"),
        ("CRITICAL", "Untrusted"),
    ])
    def test_import_skill_risk_levels(self, risk_level, expected_status, db_session, monkeypatch):
        """Cover security scan handling (lines 166-178)"""
        # Mock frontmatter
        mock_post = Mock()
        mock_post.metadata = {"name": "test_skill", "packages": [], "node_packages": []}
        mock_post.content = "# Test"

        import frontmatter
        monkeypatch.setattr(frontmatter, 'loads', Mock(return_value=mock_post))

        # Mock parser
        monkeypatch.setattr('core.skill_registry_service.SkillParser._auto_fix_metadata', Mock(return_value=mock_post.metadata))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._extract_packages', Mock(return_value=[]))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._extract_node_packages', Mock(return_value=[]))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._extract_package_manager', Mock(return_value="pip"))
        monkeypatch.setattr('core.skill_registry_service.SkillParser._detect_skill_type', Mock(return_value="prompt_only"))

        # Mock scanner with different risk levels
        mock_scanner_instance = Mock()
        mock_scanner_instance.scan_skill.return_value = {"risk_level": risk_level}
        monkeypatch.setattr('core.skill_registry_service.SkillSecurityScanner', Mock(return_value=mock_scanner_instance))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.import_skill(
            source="raw_content",
            content="---\nname: test\n---\nBody"
        )

        assert result["status"] == expected_status

    def test_import_skill_with_packages(self, db_session, monkeypatch):
        """Cover Python package extraction (lines 140-142)"""
        # Mock frontmatter
        mock_post = Mock()
        mock_post.metadata = {"name": "python_skill", "packages": ["numpy==1.21.0"]}
        mock_post.content = "```python\nimport numpy\n```"

        import frontmatter
        monkeypatch.setattr(frontmatter, 'loads', Mock(return_value=mock_post))

        # Mock parser
        mock_parser_instance = Mock()
        mock_parser_instance._auto_fix_metadata.return_value = mock_post.metadata
        mock_parser_instance._extract_packages.return_value = ["numpy==1.21.0"]
        mock_parser_instance._extract_node_packages.return_value = []
        mock_parser_instance._extract_package_manager.return_value = "pip"
        mock_parser_instance._detect_skill_type.return_value = "python_code"
        monkeypatch.setattr('core.skill_registry_service.SkillParser', Mock(return_value=mock_parser_instance))

        # Mock scanner
        mock_scanner_instance = Mock()
        mock_scanner_instance.scan_skill.return_value = {"risk_level": "LOW"}
        monkeypatch.setattr('core.skill_registry_service.SkillSecurityScanner', Mock(return_value=mock_scanner_instance))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.import_skill(
            source="raw_content",
            content="---\nname: python_skill\npackages:\n  - numpy==1.21.0\n---\n```python\n```"
        )

        assert result["status"] == "Active"
        # Check packages are stored
        assert "packages" in result["metadata"]

    def test_import_skill_with_npm_packages(self, db_session, monkeypatch):
        """Cover npm package extraction (lines 144-150)"""
        # Mock frontmatter
        mock_post = Mock()
        mock_post.metadata = {"name": "node_skill", "node_packages": ["lodash@4.17.21"]}
        mock_post.content = "```javascript\nconsole.log('test');\n```"

        import frontmatter
        monkeypatch.setattr(frontmatter, 'loads', Mock(return_value=mock_post))

        # Mock parser
        mock_parser_instance = Mock()
        mock_parser_instance._auto_fix_metadata.return_value = mock_post.metadata
        mock_parser_instance._extract_packages.return_value = []
        mock_parser_instance._extract_node_packages.return_value = ["lodash@4.17.21"]
        mock_parser_instance._extract_package_manager.return_value = "npm"
        mock_parser_instance._detect_skill_type.return_value = "python_code"
        monkeypatch.setattr('core.skill_registry_service.SkillParser', Mock(return_value=mock_parser_instance))

        # Mock scanner
        mock_scanner_instance = Mock()
        mock_scanner_instance.scan_skill.return_value = {"risk_level": "LOW"}
        monkeypatch.setattr('core.skill_registry_service.SkillSecurityScanner', Mock(return_value=mock_scanner_instance))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.import_skill(
            source="raw_content",
            content="---\nname: node_skill\nnode_packages:\n  - lodash@4.17.21\n---\n```javascript\n```"
        )

        assert result["status"] == "Active"
        assert "node_packages" in result["metadata"]

    @pytest.mark.parametrize("status,skill_type,limit,expected_min", [
        (None, None, 100, 0),  # No filters
        ("Active", None, 10, 0),  # Status filter
        (None, "prompt_only", 5, 0),  # Type filter
        ("Untrusted", "python_code", 20, 0),  # Both filters
    ])
    def test_list_skills_filters(self, status, skill_type, limit, expected_min, db_session):
        """Cover skill listing (lines 220-269)"""
        # Create test skills
        for i in range(3):
            skill = SkillExecution(
                id=f"skill-{i}",
                agent_id="system",
                tenant_id="system",
                workspace_id="default",
                skill_id=f"community_skill_{i}",
                status="Active" if i < 2 else "Untrusted",
                input_params={
                    "skill_name": f"skill_{i}",
                    "skill_type": "prompt_only" if i < 2 else "python_code"
                },
                skill_source="community",
                security_scan_result={"risk_level": "LOW"}
            )
            db_session.add(skill)
        db_session.commit()

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.list_skills(status=status, skill_type=skill_type, limit=limit)

        assert len(result) >= expected_min
        assert len(result) <= limit

    def test_get_skill_found(self, db_session):
        """Cover skill retrieval (lines 271-306) - skill found"""
        # Create test skill
        skill = SkillExecution(
            id="test-skill-id",
            agent_id="system",
            tenant_id="system",
            workspace_id="default",
            skill_id="community_test_skill",
            status="Active",
            input_params={
                "skill_name": "test_skill",
                "skill_type": "prompt_only",
                "skill_body": "# Test body",
                "skill_metadata": {"description": "Test"}
            },
            skill_source="community",
            security_scan_result={"risk_level": "LOW"}
        )
        db_session.add(skill)
        db_session.commit()

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.get_skill("test-skill-id")

        assert result is not None
        assert result["skill_name"] == "test_skill"
        assert result["skill_type"] == "prompt_only"
        assert result["status"] == "Active"

    def test_get_skill_not_found(self, db_session):
        """Cover skill retrieval (lines 271-306) - skill not found"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.get_skill("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("skill_type,agent_maturity,should_block", [
        ("prompt_only", "STUDENT", False),  # Prompt skills allowed
        ("python_code", "STUDENT", True),  # Python blocked for STUDENT
        ("python_code", "INTERN", False),  # Python allowed for INTERN+
        ("python_code", "AUTONOMOUS", False),  # Python allowed for AUTONOMOUS
    ])
    async def test_execute_skill_governance(self, skill_type, agent_maturity, should_block, db_session, monkeypatch):
        """Cover governance checks (lines 350-366)"""
        # Create test skill
        skill = SkillExecution(
            id="test-skill-id",
            agent_id="system",
            tenant_id="system",
            workspace_id="default",
            skill_id="community_test_skill",
            status="Active",
            input_params={
                "skill_name": "test_skill",
                "skill_type": skill_type,
                "skill_body": "# Test body",
                "skill_metadata": {},
                "packages": [],
                "node_packages": []
            },
            skill_source="community",
            security_scan_result={"risk_level": "LOW"},
            sandbox_enabled=(skill_type == "python_code")
        )
        db_session.add(skill)
        db_session.commit()

        # Mock governance service
        mock_governance_instance = Mock()
        mock_governance_instance.get_agent_capabilities.return_value = {
            "maturity_level": agent_maturity
        } if agent_maturity != "STUDENT" or skill_type != "python_code" else None
        monkeypatch.setattr('core.skill_registry_service.AgentGovernanceService', Mock(return_value=mock_governance_instance))

        # Mock execution methods
        monkeypatch.setattr('core.skill_registry_service.SkillRegistryService._execute_prompt_skill', Mock(return_value="Prompt result"))
        monkeypatch.setattr('core.skill_registry_service.SkillRegistryService._create_execution_episode', AsyncMock(return_value="episode-id"))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        if should_block:
            with pytest.raises(ValueError, match="STUDENT agents cannot execute Python skills"):
                await registry.execute_skill("test-skill-id", {"query": "test"}, agent_id="test-agent")
        else:
            result = await registry.execute_skill("test-skill-id", {"query": "test"}, agent_id="test-agent")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_prompt_skill(self, db_session, monkeypatch):
        """Cover prompt skill execution (lines 527-549)"""
        # Create test skill
        skill = SkillExecution(
            id="test-skill-id",
            agent_id="system",
            tenant_id="system",
            workspace_id="default",
            skill_id="community_test_skill",
            status="Active",
            input_params={
                "skill_name": "test_skill",
                "skill_type": "prompt_only",
                "skill_body": "# Test prompt\n{{query}}",
                "skill_metadata": {"description": "Test"},
                "packages": [],
                "node_packages": []
            },
            skill_source="community",
            security_scan_result={"risk_level": "LOW"},
            sandbox_enabled=False
        )
        db_session.add(skill)
        db_session.commit()

        # Mock governance and tool creation
        monkeypatch.setattr('core.skill_registry_service.AgentGovernanceService', Mock())
        monkeypatch.setattr('core.skill_registry_service.SkillRegistryService._create_execution_episode', AsyncMock(return_value="episode-id"))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = await registry.execute_skill("test-skill-id", {"query": "test query"})

        assert result["success"] is True

    def test_execute_python_skill_sandbox_disabled(self, db_session):
        """Cover Python skill execution (lines 551-579) - sandbox disabled error"""
        skill_data = {
            "skill_name": "test_skill",
            "skill_type": "python_code",
            "skill_body": "```python\nprint('test')\n```",
            "sandbox_enabled": False
        }

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        with pytest.raises(ValueError, match="requires sandbox execution"):
            registry._execute_python_skill(skill_data, {"input": "test"})

    @pytest.mark.asyncio
    async def test_execute_python_skill_no_code(self, db_session, monkeypatch):
        """Cover Python skill execution (lines 570-571) - no code found"""
        skill_data = {
            "skill_name": "test_skill",
            "skill_type": "python_code",
            "skill_body": "No code here",
            "sandbox_enabled": True,
            "skill_id": "test-id"
        }

        # Mock parser
        monkeypatch.setattr('core.skill_registry_service.SkillParser.extract_python_code', Mock(return_value=[]))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        with pytest.raises(ValueError, match="No Python code found"):
            registry._execute_python_skill(skill_data, {"input": "test"})

    @pytest.mark.asyncio
    async def test_execute_python_skill_with_packages(self, db_session, monkeypatch):
        """Cover Python package execution (lines 581-668)"""
        # Mock package installer
        mock_installer_instance = Mock()
        mock_installer_instance.install_packages.return_value = {
            "success": True,
            "image_tag": "skill-test-skill:latest",
            "vulnerabilities": []
        }
        mock_installer_instance.execute_with_packages.return_value = "Execution result"
        monkeypatch.setattr('core.skill_registry_service.PackageInstaller', Mock(return_value=mock_installer_instance))

        # Mock parser
        monkeypatch.setattr('core.skill_registry_service.SkillParser.extract_python_code', Mock(return_value=["print('test')"]))

        skill_data = {
            "skill_name": "test_skill",
            "skill_type": "python_code",
            "skill_body": "```python\nprint('test')\n```",
            "sandbox_enabled": True,
            "skill_id": "test-id",
            "skill_metadata": {"packages": ["numpy"]}
        }

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = await registry._execute_python_skill_with_packages(
            skill_data, {"input": "test"}, ["numpy"], "test-agent"
        )

        assert result == "Execution result"

    @pytest.mark.asyncio
    async def test_execute_python_skill_package_install_failure(self, db_session, monkeypatch):
        """Cover Python package execution (lines 630-635) - install failure"""
        # Mock package installer failure
        mock_installer_instance = Mock()
        mock_installer_instance.install_packages.return_value = {
            "success": False,
            "error": "Installation failed"
        }
        monkeypatch.setattr('core.skill_registry_service.PackageInstaller', Mock(return_value=mock_installer_instance))

        # Mock parser
        monkeypatch.setattr('core.skill_registry_service.SkillParser.extract_python_code', Mock(return_value=["print('test')"]))

        skill_data = {
            "skill_name": "test_skill",
            "skill_type": "python_code",
            "skill_body": "```python\nprint('test')\n```",
            "sandbox_enabled": True,
            "skill_id": "test-id",
            "skill_metadata": {"packages": ["numpy"]}
        }

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        with pytest.raises(ValueError, match="Package installation failed"):
            await registry._execute_python_skill_with_packages(
                skill_data, {"input": "test"}, ["numpy"], "test-agent"
            )

    @pytest.mark.asyncio
    async def test_execute_nodejs_skill_with_packages(self, db_session, monkeypatch):
        """Cover Node.js package execution (lines 670-759)"""
        # Mock npm installer
        mock_installer_instance = Mock()
        mock_installer_instance.execute_with_packages.return_value = "Node.js result"
        monkeypatch.setattr('core.skill_registry_service.NpmPackageInstaller', Mock(return_value=mock_installer_instance))

        # Mock install dependencies
        async def mock_install(*args, **kwargs):
            return {
                "success": True,
                "image_tag": "skill-test:latest",
                "vulnerabilities": []
            }

        monkeypatch.setattr('core.skill_registry_service.SkillRegistryService._install_npm_dependencies_for_skill', mock_install)

        skill_data = {
            "skill_name": "test_skill",
            "skill_type": "python_code",
            "skill_body": "```javascript\nconsole.log('test');\n```",
            "sandbox_enabled": True,
            "skill_id": "test-id",
            "skill_metadata": {"node_packages": ["lodash"]}
        }

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = await registry._execute_nodejs_skill_with_packages(
            skill_data, {"input": "test"}, ["lodash"], "npm", "test-agent"
        )

        assert result == "Node.js result"

    @pytest.mark.asyncio
    async def test_execute_nodejs_skill_no_code(self, db_session):
        """Cover Node.js execution (lines 739-741) - no code found"""
        skill_data = {
            "skill_name": "test_skill",
            "skill_type": "python_code",
            "skill_body": "No JavaScript code here",
            "sandbox_enabled": True,
            "skill_id": "test-id"
        }

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        with pytest.raises(ValueError, match="No Node.js code found"):
            await registry._execute_nodejs_skill_with_packages(
                skill_data, {"input": "test"}, ["lodash"], "npm", "test-agent"
            )

    @pytest.mark.parametrize("package_spec,expected_name,expected_version", [
        ("lodash@4.17.21", "lodash", "4.17.21"),
        ("express", "express", "latest"),
        ("@scope/name@^1.0.0", "@scope/name", "^1.0.0"),
        ("@scope/name", "@scope/name", "latest"),
    ])
    def test_parse_npm_package(self, package_spec, expected_name, expected_version, db_session):
        """Cover npm package parsing (lines 926-953)"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        name, version = registry._parse_npm_package(package_spec)

        assert name == expected_name
        assert version == expected_version

    @pytest.mark.parametrize("skill_content,expected_type", [
        ("node_packages:\n  - lodash", "npm"),
        ("python_packages:\n  - numpy", "python"),
        ("packages:\n  - numpy", "python"),
        ("```javascript\nconsole.log('test');\n```", "npm"),
        ("```python\nprint('test')\n```", "python"),
        ("Code file: skill.js", "npm"),
        ("Code file: skill.py", "python"),
    ])
    def test_detect_skill_type(self, skill_content, expected_type, db_session, monkeypatch):
        """Cover skill type detection (lines 955-1007)"""
        # Mock frontmatter
        mock_post = Mock()
        mock_post.content = skill_content

        import frontmatter
        monkeypatch.setattr(frontmatter, 'loads', Mock(return_value=mock_post))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.detect_skill_type(skill_content)

        assert result == expected_type

    def test_summarize_inputs(self, db_session):
        """Cover input summarization (lines 1009-1030)"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        # Test empty inputs
        result = registry._summarize_inputs({})
        assert result == "{}"

        # Test long value truncation
        long_value = "x" * 200
        result = registry._summarize_inputs({"key": long_value})
        assert "..." in result
        assert len(result) < 300

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error,expected_segment_type", [
        (None, "skill_success"),
        (Exception("Test error"), "skill_failure"),
    ])
    async def test_create_execution_episode(self, error, expected_segment_type, db_session):
        """Cover episode creation (lines 1032-1092)"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        episode_id = await registry._create_execution_episode(
            skill_name="test_skill",
            agent_id="test-agent",
            inputs={"query": "test"},
            result="success" if error is None else None,
            error=error,
            execution_time=1.5
        )

        assert episode_id is not None

    def test_promote_skill_success(self, db_session):
        """Cover skill promotion (lines 1171-1215) - success"""
        # Create test skill
        skill = SkillExecution(
            id="test-skill-id",
            agent_id="system",
            tenant_id="system",
            workspace_id="default",
            skill_id="community_test_skill",
            status="Untrusted",
            input_params={
                "skill_name": "test_skill",
                "skill_type": "prompt_only"
            },
            skill_source="community",
            security_scan_result={"risk_level": "MEDIUM"}
        )
        db_session.add(skill)
        db_session.commit()

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.promote_skill("test-skill-id")

        assert result["status"] == "Active"
        assert result["previous_status"] == "Untrusted"

    def test_promote_skill_already_active(self, db_session):
        """Cover skill promotion (lines 1196-1202) - already Active"""
        # Create test skill
        skill = SkillExecution(
            id="test-skill-id",
            agent_id="system",
            tenant_id="system",
            workspace_id="default",
            skill_id="community_test_skill",
            status="Active",
            input_params={"skill_name": "test_skill"},
            skill_source="community",
            security_scan_result={"risk_level": "LOW"}
        )
        db_session.add(skill)
        db_session.commit()

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.promote_skill("test-skill-id")

        assert result["status"] == "Active"
        assert result["previous_status"] == "Active"
        assert "already Active" in result["message"]

    def test_promote_skill_not_found(self, db_session):
        """Cover skill promotion (lines 1188-1194) - not found"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        with pytest.raises(ValueError, match="Skill not found"):
            registry.promote_skill("nonexistent-id")

    def test_load_skill_dynamically(self, db_session, monkeypatch):
        """Cover dynamic skill loading (lines 1094-1134)"""
        # Mock loader
        mock_loader_instance = Mock()
        mock_module = Mock()
        mock_loader_instance.load_skill.return_value = mock_module
        monkeypatch.setattr('core.skill_registry_service.get_global_loader', Mock(return_value=mock_loader_instance))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.load_skill_dynamically("skill-id", "/path/to/skill.py")

        assert result["success"] is True
        assert result["skill_id"] == "skill-id"

    def test_reload_skill_dynamically(self, db_session, monkeypatch):
        """Cover dynamic skill reloading (lines 1136-1169)"""
        # Mock loader
        mock_loader_instance = Mock()
        mock_module = Mock()
        mock_loader_instance.reload_skill.return_value = mock_module
        monkeypatch.setattr('core.skill_registry_service.get_global_loader', Mock(return_value=mock_loader_instance))

        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        result = registry.reload_skill_dynamically("skill-id")

        assert result["success"] is True
        assert result["skill_id"] == "skill-id"
        assert "reloaded_at" in result

    def test_extract_nodejs_code_with_fence(self, db_session):
        """Cover Node.js code extraction (lines 761-795) - with fence"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        skill_body = "```javascript\nconsole.log('test');\nreturn 'done';\n```"
        code = registry._extract_nodejs_code(skill_body)

        assert "console.log('test');" in code
        assert "return 'done';" in code
        assert "```" not in code

    def test_extract_nodejs_code_without_fence(self, db_session):
        """Cover Node.js code extraction (lines 761-795) - without fence"""
        from core.skill_registry_service import SkillRegistryService
        registry = SkillRegistryService(db_session)

        skill_body = "console.log('test');\nreturn 'done';"
        code = registry._extract_nodejs_code(skill_body)

        assert code == skill_body
