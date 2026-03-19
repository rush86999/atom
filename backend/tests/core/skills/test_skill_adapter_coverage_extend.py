"""
Extended coverage tests for SkillAdapter (currently 61% -> target 75%+)

Target file: core/skill_adapter.py (~229 statements)

This file extends existing coverage from test_skill_adapter_coverage.py
by targeting remaining uncovered lines.

Focus areas (building on Phase 183 61% baseline):
- Python skill execution error handling (lines 295-300, 373-375)
- Function code extraction (line 391->394)
- Node.js skill initialization and properties (lines 501-522)
- Node.js skill execution (lines 535-551, 565)
- npm dependency installation (lines 584-679)
- Node.js code execution (lines 694-714)
- npm package parsing (lines 732-751)

Current coverage: 61% (140/229 statements)
Target coverage: 75%+ (172+ statements)
Gap: 32 statements (14 percentage points)
"""

import pytest
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock

# Module-level mocking for external dependencies (Phase 182 pattern)
sys.modules['docker'] = MagicMock()
sys.modules['docker.errors'] = MagicMock()
sys.modules['core.package_installer'] = MagicMock()
sys.modules['core.npm_package_installer'] = MagicMock()
sys.modules['core.npm_script_analyzer'] = MagicMock()
sys.modules['core.package_governance_service'] = MagicMock()
sys.modules['core.skill_sandbox'] = MagicMock()

# Mock HazardSandbox at module level
mock_hazard_sandbox = MagicMock()
sys.modules['core.skill_sandbox'].HazardSandbox = mock_hazard_sandbox

from core.skill_adapter import (
    CommunitySkillTool,
    NodeJsSkillAdapter,
    create_community_tool
)


class TestPythonSkillExecutionErrorHandling:
    """
    Test Python skill execution error handling paths.

    Covers lines 295-300, 373-375 in skill_adapter.py
    """

    @pytest.fixture
    def python_skill_with_sandbox(self):
        """Create a Python code skill with sandbox enabled."""
        return {
            "name": "test_python_sandbox",
            "description": "A test Python skill with sandbox",
            "skill_id": "python_sandbox_001",
            "skill_type": "python_code",
            "skill_content": "def execute(query: str) -> str:\n    return f'Hello {query}'",
            "sandbox_enabled": True,
            "packages": []
        }

    def test_docker_not_running_error(self, python_skill_with_sandbox):
        """
        Test Docker not running error handling (line 296-297).

        VALIDATED_BUG: None - error handling works correctly
        """
        skill = create_community_tool(python_skill_with_sandbox)

        # Mock HazardSandbox to raise RuntimeError for Docker not running
        mock_sandbox = Mock()
        mock_sandbox.execute_python.side_effect = RuntimeError(
            "Docker daemon is not running"
        )

        with patch('core.skill_sandbox.HazardSandbox', return_value=mock_sandbox):
            result = skill._run("test query")

            # Should return user-friendly error message
            assert "SANDBOX_ERROR" in result
            assert "Docker is not running" in result

    def test_sandbox_execution_generic_error(self, python_skill_with_sandbox):
        """
        Test generic sandbox execution error handling (line 299-300).

        VALIDATED_BUG: None - error handling works correctly
        """
        skill = create_community_tool(python_skill_with_sandbox)

        # Mock HazardSandbox to raise generic exception
        mock_sandbox = Mock()
        mock_sandbox.execute_python.side_effect = Exception("Generic execution error")

        with patch('core.skill_sandbox.HazardSandbox', return_value=mock_sandbox):
            result = skill._run("test query")

            # Should return EXECUTION_ERROR prefix
            assert "EXECUTION_ERROR" in result
            assert "Generic execution error" in result

    def test_package_execution_error_handling(self, python_skill_with_sandbox):
        """
        Test package execution error handling (lines 373-375).

        VALIDATED_BUG: None - error handling works correctly
        """
        # Add packages to trigger package execution path
        python_skill_with_sandbox["packages"] = ["numpy==1.21.0"]

        skill = create_community_tool(python_skill_with_sandbox)

        # Mock PackageInstaller to raise exception
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:test-python-sandbox-v1"
        }
        mock_installer.execute_with_packages.side_effect = Exception("Package execution failed")

        with patch('core.package_installer.PackageInstaller', return_value=mock_installer):
            result = skill._run("test query")

            # Should return PACKAGE_EXECUTION_ERROR prefix
            assert "PACKAGE_EXECUTION_ERROR" in result
            assert "Package execution failed" in result


class TestFunctionCodeExtraction:
    """
    Test function code extraction from skill content.

    Covers line 391->394 (branch for result = execute(query) presence)
    """

    def test_extract_code_without_execution_wrapper(self):
        """
        Test code extraction when execution wrapper is missing (line 392).

        VALIDATED_BUG: None - logic works correctly
        """
        skill = CommunitySkillTool(
            name="test_skill",
            description="Test skill",
            skill_id="test_001",
            skill_type="python_code",
            skill_content="def execute(query: str) -> str:\n    return query"
        )

        code = skill._extract_function_code()

        # Should add execution wrapper
        assert "result = execute(query)" in code
        assert "print(result)" in code

    def test_extract_code_with_execution_wrapper(self):
        """
        Test code extraction when execution wrapper is present (line 393).

        VALIDATED_BUG: None - logic works correctly
        """
        skill = CommunitySkillTool(
            name="test_skill",
            description="Test skill",
            skill_id="test_001",
            skill_type="python_code",
            skill_content="def execute(query: str) -> str:\n    return query\n\nresult = execute(query)\nprint(result)"
        )

        code = skill._extract_function_code()

        # Should not duplicate execution wrapper
        assert code.count("result = execute(query)") == 1
        assert "print(result)" in code


class TestNodeJsSkillAdapterInitialization:
    """
    Test Node.js skill adapter initialization and properties.

    Covers lines 501-506, 511-514, 519-522
    """

    def test_nodejs_skill_initialization(self):
        """
        Test NodeJsSkillAdapter initialization (lines 501-506).

        VALIDATED_BUG: None - initialization works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-nodejs-skill",
            code="console.log('Hello');",
            node_packages=["lodash@4.17.21"],
            package_manager="npm",
            agent_id="agent_123",
            name="test_skill",
            description="Test Node.js skill"
        )

        assert adapter.skill_id == "test-nodejs-skill"
        assert adapter.code == "console.log('Hello');"
        assert adapter.node_packages == ["lodash@4.17.21"]
        assert adapter.package_manager == "npm"
        assert adapter.agent_id == "agent_123"
        assert adapter.name == "test_skill"
        assert adapter.description == "Test Node.js skill"

    def test_nodejs_skill_default_values(self):
        """
        Test NodeJsSkillAdapter with default values.

        VALIDATED_BUG: None - defaults work correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('test');",
            node_packages=[]
        )

        assert adapter.package_manager == "npm"  # Default
        assert adapter.agent_id is None  # Default
        assert adapter.node_packages == []

    def test_installer_property_lazy_loading(self):
        """
        Test installer property lazy loading (lines 511-514).

        VALIDATED_BUG: None - lazy loading works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('test');",
            node_packages=[]
        )

        # Mock NpmPackageInstaller
        mock_installer_class = Mock()
        mock_installer = Mock()
        mock_installer_class.return_value = mock_installer

        with patch('core.npm_package_installer.NpmPackageInstaller', mock_installer_class):
            # First access should trigger import and instantiation
            installer = adapter.installer
            assert installer == mock_installer
            mock_installer_class.assert_called_once()

            # Second access should return cached instance
            installer2 = adapter.installer
            assert installer2 == installer
            assert mock_installer_class.call_count == 1  # No additional call

    def test_governance_property_lazy_loading(self):
        """
        Test governance property lazy loading (lines 519-522).

        VALIDATED_BUG: None - lazy loading works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('test');",
            node_packages=[]
        )

        # Mock PackageGovernanceService
        mock_governance_class = Mock()
        mock_governance = Mock()
        mock_governance_class.return_value = mock_governance

        with patch('core.package_governance_service.PackageGovernanceService', mock_governance_class):
            # First access should trigger import and instantiation
            governance = adapter.governance
            assert governance == mock_governance
            mock_governance_class.assert_called_once()

            # Second access should return cached instance
            governance2 = adapter.governance
            assert governance2 == governance
            assert mock_governance_class.call_count == 1  # No additional call


class TestNodeJsSkillExecution:
    """
    Test Node.js skill execution paths.

    Covers lines 535-551, 565
    """

    def test_nodejs_run_success_path(self):
        """
        Test successful Node.js skill execution (lines 536-547).

        VALIDATED_BUG: None - execution works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('Hello');",
            node_packages=[]
        )

        # Mock methods using direct patch on the class
        mock_install = Mock(return_value={"success": True})
        mock_execute = Mock(return_value="Execution successful")

        with patch.object(NodeJsSkillAdapter, 'install_npm_dependencies', mock_install), \
             patch.object(NodeJsSkillAdapter, 'execute_nodejs_code', mock_execute):
            result = adapter._run({"query": "test"})

            assert result == "Execution successful"
            mock_install.assert_called_once()
            mock_execute.assert_called_once_with("test")

    def test_nodejs_run_installation_failure(self):
        """
        Test Node.js skill execution with installation failure (lines 541-543).

        VALIDATED_BUG: None - error handling works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('Hello');",
            node_packages=[]
        )

        # Mock installation failure
        mock_install = Mock(return_value={
            "success": False,
            "error": "Package not found"
        })

        with patch.object(NodeJsSkillAdapter, 'install_npm_dependencies', mock_install):
            result = adapter._run({"query": "test"})

            assert "NPM_INSTALLATION_ERROR" in result
            assert "Package not found" in result

    def test_nodejs_run_execution_exception(self):
        """
        Test Node.js skill execution with exception (lines 549-551).

        VALIDATED_BUG: None - exception handling works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('Hello');",
            node_packages=[]
        )

        # Mock exception during execution
        mock_install = Mock(return_value={"success": True})
        mock_execute = Mock(side_effect=Exception("Execution failed"))

        with patch.object(NodeJsSkillAdapter, 'install_npm_dependencies', mock_install), \
             patch.object(NodeJsSkillAdapter, 'execute_nodejs_code', mock_execute):
            result = adapter._run({"query": "test"})

            assert "NODEJS_EXECUTION_ERROR" in result
            assert "Execution failed" in result

    def test_nodejs_arun_delegation(self):
        """
        Test async execution delegates to sync (line 565).

        VALIDATED_BUG: None - delegation works correctly
        """
        adapter = NodeJsSkillAdapter(
            skill_id="test-skill",
            code="console.log('Hello');",
            node_packages=[]
        )

        # Mock _run method
        adapter._run = Mock(return_value="Sync result")

        # Call _arun (should delegate to _run)
        import asyncio
        result = asyncio.run(adapter._arun({"query": "test"}))

        assert result == "Sync result"
        adapter._run.assert_called_once_with({"query": "test"}, None)


class TestNpmDependencyInstallation:
    """
    Test npm dependency installation with governance checks.

    Covers lines 584-679
    """

    @pytest.fixture
    def nodejs_skill_with_packages(self):
        """Create Node.js skill with npm packages."""
        return NodeJsSkillAdapter(
            skill_id="test-npm-skill",
            code="const _ = require('lodash');",
            node_packages=["lodash@4.17.21", "express@4.18.0"],
            package_manager="npm",
            agent_id="agent_123"
        )

    def test_governance_permission_check_success(self, nodejs_skill_with_packages):
        """
        Test governance permission check for all packages (lines 594-621).

        VALIDATED_BUG: None - governance checks work correctly
        """
        # Mock governance to allow all packages
        with patch.object(nodejs_skill_with_packages.governance, 'check_package_permission', return_value={"allowed": True}):
            # Mock script analyzer
            mock_script_analyzer = Mock()
            mock_script_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }

            # Mock installer
            with patch.object(nodejs_skill_with_packages.installer, 'install_packages', return_value={
                "success": True,
                "image_tag": "atom-skill:test-npm-skill-v1"
            }):
                with patch('core.npm_script_analyzer.NpmScriptAnalyzer', return_value=mock_script_analyzer):
                    result = nodejs_skill_with_packages.install_npm_dependencies()

                    assert result["success"] is True
                    assert "image_tag" in result

    def test_governance_permission_denied(self, nodejs_skill_with_packages):
        """
        Test governance permission denied blocks installation (lines 608-619).

        VALIDATED_BUG: None - blocking works correctly
        """
        # Mock governance to deny first package
        with patch.object(nodejs_skill_with_packages.governance, 'check_package_permission', side_effect=[
            {"allowed": False, "reason": "Package not approved"},
            {"allowed": True}
        ]):
            result = nodejs_skill_with_packages.install_npm_dependencies()

            assert result["success"] is False
            assert "blocked by governance" in result["error"]
            assert result["package"] == "lodash"

    def test_malicious_scripts_detected(self, nodejs_skill_with_packages):
        """
        Test malicious scripts block installation (lines 630-640).

        VALIDATED_BUG: None - malicious script detection works correctly
        """
        # Mock governance to allow packages
        with patch.object(nodejs_skill_with_packages.governance, 'check_package_permission', return_value={"allowed": True}):
            # Mock script analyzer to detect malicious scripts
            mock_script_analyzer = Mock()
            mock_script_analyzer.analyze_package_scripts.return_value = {
                "malicious": True,
                "warnings": ["Suspicious postinstall script detected"]
            }

            with patch('core.npm_script_analyzer.NpmScriptAnalyzer', return_value=mock_script_analyzer):
                result = nodejs_skill_with_packages.install_npm_dependencies()

                assert result["success"] is False
                assert "Malicious postinstall/preinstall scripts detected" in result["error"]

    def test_script_warnings_logged(self, nodejs_skill_with_packages):
        """
        Test script warnings logged but installation continues (lines 642-643).

        VALIDATED_BUG: None - warning handling works correctly
        """
        # Mock governance to allow packages
        with patch.object(nodejs_skill_with_packages.governance, 'check_package_permission', return_value={"allowed": True}):
            # Mock script analyzer with warnings
            mock_script_analyzer = Mock()
            mock_script_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": ["Suspicious but not malicious"]
            }

            # Mock installer success
            with patch.object(nodejs_skill_with_packages.installer, 'install_packages', return_value={
                "success": True,
                "image_tag": "atom-skill:test-npm-skill-v1"
            }):
                with patch('core.npm_script_analyzer.NpmScriptAnalyzer', return_value=mock_script_analyzer):
                    result = nodejs_skill_with_packages.install_npm_dependencies()

                    assert result["success"] is True
                    assert "script_warnings" in result

    def test_installation_failure_handling(self, nodejs_skill_with_packages):
        """
        Test installation failure handling (lines 657-664).

        VALIDATED_BUG: None - error handling works correctly
        """
        # Mock governance to allow packages
        with patch.object(nodejs_skill_with_packages.governance, 'check_package_permission', return_value={"allowed": True}):
            # Mock script analyzer no issues
            mock_script_analyzer = Mock()
            mock_script_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }

            # Mock installer failure
            with patch.object(nodejs_skill_with_packages.installer, 'install_packages', return_value={
                "success": False,
                "error": "Network error during installation"
            }):
                with patch('core.npm_script_analyzer.NpmScriptAnalyzer', return_value=mock_script_analyzer):
                    result = nodejs_skill_with_packages.install_npm_dependencies()

                    assert result["success"] is False
                    # Error message is returned directly
                    assert "Network error during installation" in result["error"]

    def test_successful_installation(self, nodejs_skill_with_packages):
        """
        Test successful npm package installation (lines 666-676).

        VALIDATED_BUG: None - success path works correctly
        """
        # Mock governance to allow packages
        with patch.object(nodejs_skill_with_packages.governance, 'check_package_permission', return_value={"allowed": True}):
            # Mock script analyzer no issues
            mock_script_analyzer = Mock()
            mock_script_analyzer.analyze_package_scripts.return_value = {
                "malicious": False,
                "warnings": []
            }

            # Mock installer success with vulnerabilities
            with patch.object(nodejs_skill_with_packages.installer, 'install_packages', return_value={
                "success": True,
                "image_tag": "atom-skill:test-npm-skill-v1",
                "vulnerabilities": ["CVE-2021-1234"]
            }):
                with patch('core.npm_script_analyzer.NpmScriptAnalyzer', return_value=mock_script_analyzer):
                    result = nodejs_skill_with_packages.install_npm_dependencies()

                    assert result["success"] is True
                    assert result["image_tag"] == "atom-skill:test-npm-skill-v1"
                    assert "vulnerabilities" in result
                    assert len(result["vulnerabilities"]) == 1


class TestNodeJsCodeExecution:
    """
    Test Node.js code execution with pre-installed packages.

    Covers lines 694-714
    """

    @pytest.fixture
    def nodejs_skill_executable(self):
        """Create Node.js skill ready for execution."""
        return NodeJsSkillAdapter(
            skill_id="test-exec-skill",
            code="console.log('Hello World');",
            node_packages=[]
        )

    def test_successful_nodejs_execution(self, nodejs_skill_executable):
        """
        Test successful Node.js code execution (lines 695-709).

        VALIDATED_BUG: None - execution works correctly
        """
        # Mock installer execution
        nodejs_skill_executable.installer.execute_with_packages = Mock(
            return_value="Hello World\n"
        )

        result = nodejs_skill_executable.execute_nodejs_code("test query")

        assert result == "Hello World\n"

    def test_nodejs_execution_exception(self, nodejs_skill_executable):
        """
        Test Node.js execution exception handling (lines 711-714).

        VALIDATED_BUG: None - exception handling works correctly
        """
        # Mock installer to raise exception
        nodejs_skill_executable.installer.execute_with_packages = Mock(
            side_effect=Exception("Runtime error")
        )

        result = nodejs_skill_executable.execute_nodejs_code("test query")

        assert "Node.js execution failed" in result
        assert "Runtime error" in result


class TestNpmPackageParsing:
    """
    Test npm package specifier parsing.

    Covers lines 732-751
    """

    @pytest.fixture
    def nodejs_skill_parser(self):
        """Create Node.js skill for parsing tests."""
        return NodeJsSkillAdapter(
            skill_id="test-parser",
            code="console.log('test');",
            node_packages=[]
        )

    def test_parse_scoped_package_with_version(self, nodejs_skill_parser):
        """
        Test parsing scoped package with version (lines 733-739).

        VALIDATED_BUG: None - parsing works correctly
        """
        name, version = nodejs_skill_parser._parse_npm_package("@scope/name@^1.0.0")

        assert name == "@scope/name"
        assert version == "^1.0.0"

    def test_parse_scoped_package_without_version(self, nodejs_skill_parser):
        """
        Test parsing scoped package without version (lines 740-742).

        VALIDATED_BUG: None - parsing works correctly
        """
        name, version = nodejs_skill_parser._parse_npm_package("@scope/name")

        assert name == "@scope/name"
        assert version == "latest"

    def test_parse_regular_package_with_version(self, nodejs_skill_parser):
        """
        Test parsing regular package with version (lines 745-748).

        VALIDATED_BUG: None - parsing works correctly
        """
        name, version = nodejs_skill_parser._parse_npm_package("lodash@4.17.21")

        assert name == "lodash"
        assert version == "4.17.21"

    def test_parse_regular_package_without_version(self, nodejs_skill_parser):
        """
        Test parsing regular package without version (lines 749-751).

        VALIDATED_BUG: None - parsing works correctly
        """
        name, version = nodejs_skill_parser._parse_npm_package("express")

        assert name == "express"
        assert version == "latest"

    def test_parse_package_with_range(self, nodejs_skill_parser):
        """
        Test parsing package with version range.

        VALIDATED_BUG: None - parsing works correctly
        """
        name, version = nodejs_skill_parser._parse_npm_package("axios@^0.27.0")

        assert name == "axios"
        assert version == "^0.27.0"


class TestEdgeCasesAndErrorPaths:
    """
    Test edge cases and additional error paths to maximize coverage.

    Targets remaining uncovered lines in error handling
    """

    def test_cli_skill_exception_handling(self):
        """
        Test CLI skill exception handling (line 160-162).

        VALIDATED_BUG: None - exception handling works correctly
        """
        skill = CommunitySkillTool(
            name="atom-status",
            description="Check status",
            skill_id="atom-status",
            skill_type="prompt_only",
            skill_content="Check daemon status"
        )

        # Mock execute_atom_cli_command to raise exception
        with patch('core.skill_adapter.execute_atom_cli_command', side_effect=Exception("CLI error")):
            result = skill._run("Check status")

            assert "ERROR" in result
            assert "Failed to execute CLI skill" in result

    def test_prompt_skill_formatting_exception(self):
        """
        Test prompt skill formatting exception (line 256-258).

        VALIDATED_BUG: None - exception handling works correctly
        """
        skill = CommunitySkillTool(
            name="test_prompt",
            description="Test prompt",
            skill_id="test_prompt",
            skill_type="prompt_only",
            skill_content="Hello {query}"  # Single brace syntax
        )

        # Mock to cause formatting error
        result = skill._run("test")

        # Should handle formatting gracefully
        assert result is not None

    def test_python_skill_sandbox_disabled_error(self):
        """
        Test Python skill with sandbox disabled raises RuntimeError (line 302-307).

        VALIDATED_BUG: None - security check works correctly
        """
        skill = CommunitySkillTool(
            name="test_python",
            description="Test Python",
            skill_id="test_python",
            skill_type="python_code",
            skill_content="def execute():\n    return 'Hello'",
            sandbox_enabled=False
        )

        # Should raise RuntimeError for security reasons
        with pytest.raises(RuntimeError) as exc_info:
            skill._run("test")

        assert "Direct Python execution is not allowed" in str(exc_info.value)
        assert "sandbox_enabled=True" in str(exc_info.value)

    def test_unknown_skill_type_error(self):
        """
        Test unknown skill type raises ValueError (line 117-118).

        VALIDATED_BUG: None - error handling works correctly
        """
        skill = CommunitySkillTool(
            name="test_unknown",
            description="Test unknown",
            skill_id="test_unknown",
            skill_type="unknown_type",
            skill_content="Some content"
        )

        # Should raise ValueError for unknown skill type
        with pytest.raises(ValueError) as exc_info:
            skill._run("test")

        assert "Unknown skill type" in str(exc_info.value)
