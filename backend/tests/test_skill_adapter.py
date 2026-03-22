"""
Tests for CommunitySkillTool - LangChain BaseTool adapter.

Tests cover:
- BaseTool subclass verification
- Factory function functionality
- Prompt-only skill execution with template interpolation
- Python skill execution with sandbox integration
- Pydantic args_schema validation
- Async execution delegation
- Python package support (Phase 35)
"""

import pytest
import sys
from unittest.mock import patch, Mock, MagicMock

# Module-level mocking for PackageInstaller (Phase 182 pattern)
sys.modules['core.package_installer'] = MagicMock()

# Module-level mocking for npm-related imports
sys.modules['core.npm_script_analyzer'] = MagicMock()
sys.modules['core.npm_package_installer'] = MagicMock()
sys.modules['core.package_governance_service'] = MagicMock()

from core.skill_adapter import CommunitySkillTool, CommunitySkillInput, create_community_tool


@pytest.fixture
def prompt_only_skill():
    """Create a prompt-only skill definition."""
    return {
        "name": "test_prompt_skill",
        "description": "A test prompt-only skill",
        "skill_id": "prompt_001",
        "skill_type": "prompt_only",
        "skill_content": "You are a helpful assistant. Answer the following query: {{query}}"
    }


@pytest.fixture
def python_skill():
    """Create a Python code skill definition."""
    return {
        "name": "test_python_skill",
        "description": "A test Python skill",
        "skill_id": "python_001",
        "skill_type": "python_code",
        "skill_content": "def execute():\n    return 'Hello from Python'"
    }


@pytest.fixture
def prompt_skill_no_placeholder():
    """Create a prompt skill without {{query}} placeholder."""
    return {
        "name": "no_placeholder_skill",
        "description": "Skill without query placeholder",
        "skill_id": "no_place_001",
        "skill_type": "prompt_only",
        "skill_content": "This is a static skill content."
    }


class TestCommunitySkillToolBasics:
    """Test basic CommunitySkillTool functionality."""

    def test_community_skill_tool_is_basetool(self, prompt_only_skill):
        """Test that CommunitySkillTool is a LangChain BaseTool subclass."""
        from langchain.tools import BaseTool

        tool = CommunitySkillTool(
            name=prompt_only_skill["name"],
            description=prompt_only_skill["description"],
            skill_id=prompt_only_skill["skill_id"],
            skill_type=prompt_only_skill["skill_type"],
            skill_content=prompt_only_skill["skill_content"]
        )

        assert isinstance(tool, BaseTool)
        assert tool.name == "test_prompt_skill"
        assert tool.description == "A test prompt-only skill"
        assert tool.skill_id == "prompt_001"
        assert tool.skill_type == "prompt_only"

    def test_args_schema_validation(self):
        """Test that args_schema is properly configured."""
        # Check that args_schema is set (access via class.__dict__ to avoid Pydantic issues)
        assert "args_schema" in CommunitySkillTool.model_fields

        # Test Pydantic model
        input_schema = CommunitySkillInput(query="test query")
        assert input_schema.query == "test query"

        # Test extra fields allowed (ConfigDict extra='allow')
        input_schema_extra = CommunitySkillInput(
            query="test",
            extra_field="extra_value"
        )
        assert input_schema_extra.query == "test"


class TestCreateCommunityToolFactory:
    """Test create_community_tool factory function."""

    def test_create_community_tool_factory(self, prompt_only_skill):
        """Test that factory function creates tool correctly."""
        tool = create_community_tool(prompt_only_skill)

        assert isinstance(tool, CommunitySkillTool)
        assert tool.name == "test_prompt_skill"
        assert tool.description == "A test prompt-only skill"
        assert tool.skill_id == "prompt_001"
        assert tool.skill_type == "prompt_only"
        assert tool.sandbox_enabled is False

    def test_factory_with_python_skill(self, python_skill):
        """Test factory with Python code skill."""
        tool = create_community_tool(python_skill)

        assert tool.skill_type == "python_code"
        assert tool.sandbox_enabled is False

    def test_factory_defaults_missing_fields(self):
        """Test that factory provides defaults for missing fields."""
        minimal_skill = {"name": "minimal_skill"}

        tool = create_community_tool(minimal_skill)

        assert tool.name == "minimal_skill"
        assert tool.description == "Execute a community skill"
        assert tool.skill_type == "prompt_only"
        assert tool.skill_id == "minimal_skill"


class TestPromptOnlySkillExecution:
    """Test prompt-only skill execution."""

    def test_prompt_only_skill_double_brace_interpolation(self, prompt_only_skill):
        """Test prompt formatting with {{query}} placeholder."""
        tool = create_community_tool(prompt_only_skill)

        result = tool._run("What is the capital of France?")

        assert "What is the capital of France?" in result
        assert "helpful assistant" in result

    def test_prompt_only_skill_single_brace_interpolation(self):
        """Test prompt formatting with {query} placeholder."""
        skill = {
            "name": "single_brace_skill",
            "description": "Skill with single brace placeholder",
            "skill_id": "single_001",
            "skill_type": "prompt_only",
            "skill_content": "Query: {query}"
        }

        tool = create_community_tool(skill)
        result = tool._run("test query")

        assert result == "Query: test query"

    def test_prompt_only_skill_no_placeholder_appends(self, prompt_skill_no_placeholder):
        """Test that query is appended when no placeholder exists."""
        tool = create_community_tool(prompt_skill_no_placeholder)

        result = tool._run("My query")

        assert "This is a static skill content." in result
        assert "My query" in result

    def test_prompt_only_skill_multiple_queries(self, prompt_only_skill):
        """Test multiple executions with different queries."""
        tool = create_community_tool(prompt_only_skill)

        result1 = tool._run("Query 1")
        result2 = tool._run("Query 2")

        assert "Query 1" in result1
        assert "Query 2" in result2
        assert result1 != result2


class TestPythonSkillExecution:
    """Test Python skill execution behavior."""

    def test_python_skill_raises_without_sandbox(self, python_skill):
        """Test that Python skills raise RuntimeError without sandbox."""
        tool = create_community_tool(python_skill)

        with pytest.raises(RuntimeError) as exc_info:
            tool._run("test query")

        assert "sandbox" in str(exc_info.value).lower()
        assert "security" in str(exc_info.value).lower()

    @patch('core.skill_sandbox.HazardSandbox')
    def test_python_skill_with_sandbox_enabled_executes(self, mock_sandbox_class, python_skill):
        """Test that Python skills execute with sandbox when enabled."""
        # Mock the sandbox instance
        mock_sandbox = Mock()
        mock_sandbox.execute_python.return_value = "Execution result: Hello test query"
        mock_sandbox_class.return_value = mock_sandbox

        python_skill["sandbox_enabled"] = True
        python_skill["skill_content"] = "def execute(query: str) -> str:\n    return f'Hello {query}'"
        tool = create_community_tool(python_skill)

        result = tool._run("test query")

        # Verify sandbox was called
        mock_sandbox.execute_python.assert_called_once()
        assert "Hello" in result

    def test_unknown_skill_type_raises_value_error(self):
        """Test that unknown skill type raises ValueError."""
        invalid_skill = {
            "name": "invalid_skill",
            "description": "Invalid skill type",
            "skill_id": "invalid_001",
            "skill_type": "unknown_type",
            "skill_content": "content"
        }

        tool = create_community_tool(invalid_skill)

        with pytest.raises(ValueError) as exc_info:
            tool._run("test query")

        assert "Unknown skill type" in str(exc_info.value)


class TestAsyncExecution:
    """Test async execution delegation."""

    @pytest.mark.asyncio
    async def test_async_delegates_to_sync(self, prompt_only_skill):
        """Test that _arun delegates to _run."""
        tool = create_community_tool(prompt_only_skill)

        result = await tool._arun("async query")

        # Should produce same result as sync _run
        sync_result = tool._run("async query")
        assert result == sync_result

    @pytest.mark.asyncio
    async def test_async_python_skill_raises(self, python_skill):
        """Test that async Python skill execution also raises without sandbox."""
        tool = create_community_tool(python_skill)

        with pytest.raises(RuntimeError) as exc_info:
            await tool._arun("test query")

        assert "sandbox" in str(exc_info.value).lower()
        assert "security" in str(exc_info.value).lower()


class TestErrorHandling:
    """Test error handling in skill execution."""

    def test_template_formatting_error_returns_error_message(self):
        """Test that template formatting errors are caught and return error message."""
        # Create a skill with invalid format string
        bad_skill = {
            "name": "bad_format_skill",
            "description": "Skill with bad format",
            "skill_id": "bad_001",
            "skill_type": "prompt_only",
            "skill_content": "Query: {query} {missing}"
        }

        tool = create_community_tool(bad_skill)

        # Should not raise, but return error message
        result = tool._run("test")

        assert "ERROR" in result
        assert "Failed to format prompt" in result


class TestPydanticValidation:
    """Test Pydantic validation for skill inputs."""

    def test_community_skill_input_requires_query(self):
        """Test that CommunitySkillInput requires query field."""
        with pytest.raises(Exception):  # ValidationError
            CommunitySkillInput()

    def test_community_skill_input_accepts_query(self):
        """Test that CommunitySkillInput accepts query successfully."""
        input_obj = CommunitySkillInput(query="test query")

        assert input_obj.query == "test query"

    def test_community_skill_input_allows_extra_fields(self):
        """Test that extra fields are allowed (extra='allow')."""
        input_obj = CommunitySkillInput(
            query="test",
            extra_field="value",
            another_extra=123
        )

        assert input_obj.query == "test"
        # Extra fields are stored in model
        assert hasattr(input_obj, 'model_extra')


class TestPythonPackageSkills:
    """Test Python package support (Phase 35)."""

    @pytest.fixture
    def package_skill(self):
        """Create a Python skill with packages."""
        return {
            "name": "numpy_skill",
            "description": "A skill with numpy package",
            "skill_id": "numpy_001",
            "skill_type": "python_code",
            "skill_content": "def execute(query: str) -> str:\n    return f'Processed: {query}'",
            "packages": ["numpy==1.21.0", "pandas>=1.3.0"]
        }

    def test_packages_attribute_stored(self, package_skill):
        """Test that packages list is stored on tool creation."""
        tool = create_community_tool(package_skill)

        assert tool.packages == ["numpy==1.21.0", "pandas>=1.3.0"]
        assert len(tool.packages) == 2

    def test_packages_empty_by_default(self, prompt_only_skill):
        """Test that packages default to empty list."""
        tool = create_community_tool(prompt_only_skill)

        assert tool.packages == []

    @patch('core.package_installer.PackageInstaller')
    def test_package_execution_workflow(self, mock_installer_class, package_skill):
        """Test _execute_python_skill_with_packages() calls PackageInstaller."""
        # Mock PackageInstaller instance
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:testing-v1",
            "vulnerabilities": []
        }
        mock_installer.execute_with_packages.return_value = "Execution result: Processed test query"
        mock_installer_class.return_value = mock_installer

        tool = create_community_tool(package_skill)

        result = tool._run("test query")

        # Verify install_packages was called
        mock_installer.install_packages.assert_called_once()
        call_args = mock_installer.install_packages.call_args
        assert call_args[1]["skill_id"] == "skill-numpy_skill"
        assert call_args[1]["requirements"] == ["numpy==1.21.0", "pandas>=1.3.0"]
        assert call_args[1]["scan_for_vulnerabilities"] is True

        # Verify execute_with_packages was called
        mock_installer.execute_with_packages.assert_called_once()
        assert "Execution result" in result

    @patch('core.package_installer.PackageInstaller')
    def test_package_installation_failure_handling(self, mock_installer_class, package_skill):
        """Test error message when install_packages fails."""
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": False,
            "error": "Failed to build Docker image: disk full"
        }
        mock_installer_class.return_value = mock_installer

        tool = create_community_tool(package_skill)

        result = tool._run("test query")

        assert "PACKAGE_INSTALLATION_ERROR" in result
        assert "Failed to build Docker image: disk full" in result

        # Verify execute_with_packages was not called
        mock_installer.execute_with_packages.assert_not_called()

    @patch('core.package_installer.PackageInstaller')
    def test_vulnerability_logging(self, mock_installer_class, package_skill):
        """Test vulnerabilities are logged but execution proceeds."""
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:testing-v1",
            "vulnerabilities": [
                {"package": "numpy", "severity": "HIGH", "cve": "CVE-2021-1234"}
            ]
        }
        mock_installer.execute_with_packages.return_value = "Execution result"
        mock_installer_class.return_value = mock_installer

        tool = create_community_tool(package_skill)

        result = tool._run("test query")

        # Should proceed despite vulnerabilities
        assert "Execution result" in result
        mock_installer.execute_with_packages.assert_called_once()

    @patch('core.package_installer.PackageInstaller')
    def test_code_extraction_for_packages(self, mock_installer_class, package_skill):
        """Test _extract_function_code() adds execution wrapper."""
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:testing-v1"
        }
        mock_installer.execute_with_packages.return_value = "Result"
        mock_installer_class.return_value = mock_installer

        tool = create_community_tool(package_skill)

        # Execute to trigger code extraction
        tool._run("test query")

        # Verify execute_with_packages was called with wrapped code
        call_args = mock_installer.execute_with_packages.call_args
        code_arg = call_args[1]["code"]

        # Should contain execution wrapper
        assert "result = execute(query)" in code_arg
        assert "print(result)" in code_arg

    def test_package_skill_without_sandbox_raises(self, package_skill):
        """Test RuntimeError when sandbox_enabled=False with packages."""
        # Remove packages to trigger normal Python skill path
        package_skill["packages"] = []
        package_skill["sandbox_enabled"] = False

        tool = create_community_tool(package_skill)

        # Should raise RuntimeError for Python skill without sandbox
        with pytest.raises(RuntimeError) as exc_info:
            tool._run("test query")

        assert "sandbox" in str(exc_info.value).lower()
        assert "security" in str(exc_info.value).lower()


class TestCLISkillExecution:
    """Test CLI skill execution for atom-* prefixed skills."""

    @pytest.fixture
    def cli_skill(self):
        """Create a CLI skill definition."""
        return {
            "name": "atom-daemon",
            "description": "Start Atom daemon",
            "skill_id": "atom-daemon",
            "skill_type": "prompt_only",
            "skill_content": "Daemon management"
        }

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_executes_command(self, mock_execute, cli_skill):
        """Test that CLI skills execute atom-cli commands."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started on port 8000",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start daemon")

        assert "Command executed successfully" in result
        assert "Daemon started on port 8000" in result
        mock_execute.assert_called_once()

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_parses_port_argument(self, mock_execute, cli_skill):
        """Test CLI argument parsing for port flag."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start daemon on port 3000")

        # Verify port was parsed and passed
        call_args = mock_execute.call_args
        assert call_args[0][0] == "daemon"
        assert "--port" in call_args[0][1]
        assert "3000" in call_args[0][1]

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_parses_host_argument(self, mock_execute, cli_skill):
        """Test CLI argument parsing for host flag."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start with host localhost")

        call_args = mock_execute.call_args
        assert "--host" in call_args[0][1]
        assert "localhost" in call_args[0][1]

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_parses_workers_argument(self, mock_execute, cli_skill):
        """Test CLI argument parsing for workers flag."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("workers 4")

        call_args = mock_execute.call_args
        args = call_args[0][1]
        # Args should be a list containing workers flag
        assert args is not None
        assert "--workers" in args
        assert "4" in args

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_boolean_flags(self, mock_execute, cli_skill):
        """Test CLI argument parsing for boolean flags."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start with host mount in dev mode foreground")

        call_args = mock_execute.call_args
        args = call_args[0][1]
        assert "--host-mount" in args
        assert "--dev" in args
        assert "--foreground" in args

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_config_show_daemon(self, mock_execute):
        """Test atom-config with --show-daemon flag."""
        config_skill = {
            "name": "atom-config",
            "description": "Show daemon configuration",
            "skill_id": "atom-config",
            "skill_type": "prompt_only",
            "skill_content": "Config management"
        }

        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon config: ...",
            "stderr": ""
        }

        tool = create_community_tool(config_skill)
        result = tool._run("Show daemon configuration")

        call_args = mock_execute.call_args
        args = call_args[0][1]
        assert "--show-daemon" in args

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_command_failure(self, mock_execute, cli_skill):
        """Test CLI skill command failure handling."""
        mock_execute.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Docker daemon not running"
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start daemon")

        assert "Command failed" in result
        assert "Docker daemon not running" in result

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_success_with_stderr(self, mock_execute, cli_skill):
        """Test CLI skill success with stderr warnings."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": "Warning: low memory"
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start daemon")

        assert "Command executed successfully" in result
        assert "Daemon started" in result
        assert "Warnings:" in result
        assert "Warning: low memory" in result

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_exception_handling(self, mock_execute, cli_skill):
        """Test CLI skill exception handling."""
        mock_execute.side_effect = Exception("Subprocess failed")

        tool = create_community_tool(cli_skill)
        result = tool._run("Start daemon")

        assert "ERROR" in result
        assert "Failed to execute CLI skill" in result

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_no_arguments(self, mock_execute, cli_skill):
        """Test CLI skill with no arguments."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Status: running",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Check status")

        # Should call with None for args
        call_args = mock_execute.call_args
        assert call_args[0][1] is None

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_port_equals_syntax(self, mock_execute, cli_skill):
        """Test CLI argument parsing with port=3000 syntax."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start on port=3000")

        call_args = mock_execute.call_args
        args = call_args[0][1]
        assert args is not None
        assert "--port" in args
        assert "3000" in args

    @patch('core.skill_adapter.execute_atom_cli_command')
    def test_cli_skill_dev_flag(self, mock_execute, cli_skill):
        """Test CLI argument parsing for dev flag."""
        mock_execute.return_value = {
            "success": True,
            "stdout": "Daemon started in dev mode",
            "stderr": ""
        }

        tool = create_community_tool(cli_skill)
        result = tool._run("Start in development mode")

        call_args = mock_execute.call_args
        args = call_args[0][1]
        assert args is not None
        assert "--dev" in args


class TestSandboxErrorHandling:
    """Test sandbox execution error handling."""

    @patch('core.skill_sandbox.HazardSandbox')
    def test_sandbox_docker_not_running(self, mock_sandbox_class, python_skill):
        """Test error message when Docker daemon is not running."""
        mock_sandbox = Mock()
        mock_sandbox.execute_python.side_effect = RuntimeError("Docker daemon is not running")
        mock_sandbox_class.return_value = mock_sandbox

        python_skill["sandbox_enabled"] = True
        tool = create_community_tool(python_skill)

        result = tool._run("test query")

        assert "SANDBOX_ERROR" in result
        assert "Docker is not running" in result

    @patch('core.skill_sandbox.HazardSandbox')
    def test_sandbox_general_execution_error(self, mock_sandbox_class, python_skill):
        """Test general sandbox execution error."""
        mock_sandbox = Mock()
        mock_sandbox.execute_python.side_effect = Exception("Code syntax error")
        mock_sandbox_class.return_value = mock_sandbox

        python_skill["sandbox_enabled"] = True
        tool = create_community_tool(python_skill)

        result = tool._run("test query")

        assert "EXECUTION_ERROR" in result


class TestPackageInstallationErrorPaths:
    """Test error handling in package installation."""

    @patch('core.package_installer.PackageInstaller')
    def test_execute_with_packages_exception(self, mock_installer_class):
        """Test exception handling in _execute_python_skill_with_packages."""
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:testing-v1"
        }
        mock_installer.execute_with_packages.side_effect = Exception("Execution failed")
        mock_installer_class.return_value = mock_installer

        package_skill = {
            "name": "numpy_skill",
            "description": "Skill with packages",
            "skill_id": "numpy_001",
            "skill_type": "python_code",
            "skill_content": "def execute(query: str) -> str:\n    return f'Processed: {query}'",
            "packages": ["numpy==1.21.0"]
        }

        tool = create_community_tool(package_skill)
        result = tool._run("test query")

        assert "PACKAGE_EXECUTION_ERROR" in result
        assert "Execution failed" in result

    @patch('core.package_installer.PackageInstaller')
    def test_extract_function_code_no_wrapper_needed(self, mock_installer_class):
        """Test _extract_function_code when wrapper already exists."""
        mock_installer = Mock()
        mock_installer.install_packages.return_value = {
            "success": True,
            "image_tag": "atom-skill:testing-v1"
        }
        mock_installer.execute_with_packages.return_value = "Result"
        mock_installer_class.return_value = mock_installer

        package_skill = {
            "name": "wrapped_skill",
            "description": "Skill with execution wrapper",
            "skill_id": "wrapped_001",
            "skill_type": "python_code",
            "skill_content": "def execute(query: str) -> str:\n    return query\n\nresult = execute(query)\nprint(result)",
            "packages": ["numpy"]
        }

        tool = create_community_tool(package_skill)
        tool._run("test query")

        # Verify code wasn't modified (wrapper already present)
        call_args = mock_installer.execute_with_packages.call_args
        code = call_args[1]["code"]
        assert code.count("result = execute(query)") == 1  # Only one occurrence


class TestNodeJsSkillAdapter:
    """Test Node.js skill adapter with npm packages."""

    @pytest.fixture
    def nodejs_skill(self):
        """Create a Node.js skill definition."""
        return {
            "skill_id": "nodejs_001",
            "code": "console.log('Hello from Node.js')",
            "node_packages": ["lodash@4.17.21"],
            "package_manager": "npm",
            "agent_id": "test_agent"
        }

    def test_nodejs_skill_initialization(self, nodejs_skill):
        """Test NodeJsSkillAdapter initialization."""
        from core.skill_adapter import NodeJsSkillAdapter

        adapter = NodeJsSkillAdapter(
            skill_id=nodejs_skill["skill_id"],
            code=nodejs_skill["code"],
            node_packages=nodejs_skill["node_packages"],
            package_manager=nodejs_skill["package_manager"],
            agent_id=nodejs_skill["agent_id"]
        )

        assert adapter.skill_id == "nodejs_001"
        assert adapter.code == "console.log('Hello from Node.js')"
        assert adapter.node_packages == ["lodash@4.17.21"]
        assert adapter.package_manager == "npm"
        assert adapter.agent_id == "test_agent"

    def test_parse_npm_package(self, nodejs_skill):
        """Test _parse_npm_package method."""
        from core.skill_adapter import NodeJsSkillAdapter

        adapter = NodeJsSkillAdapter(**nodejs_skill)

        # Test with version
        name, version = adapter._parse_npm_package("lodash@4.17.21")
        assert name == "lodash"
        assert version == "4.17.21"

        # Test without version (defaults to 'latest')
        name, version = adapter._parse_npm_package("express")
        assert name == "express"
        assert version == "latest"

    def test_nodejs_skill_basetool(self, nodejs_skill):
        """Test that NodeJsSkillAdapter is a BaseTool."""
        from core.skill_adapter import NodeJsSkillAdapter
        from langchain.tools import BaseTool

        adapter = NodeJsSkillAdapter(
            skill_id=nodejs_skill["skill_id"],
            code=nodejs_skill["code"],
            node_packages=nodejs_skill["node_packages"],
            agent_id=nodejs_skill["agent_id"]
        )

        assert isinstance(adapter, BaseTool)
        assert adapter.name == "nodejs_skill"

    def test_nodejs_skill_run_method(self, nodejs_skill):
        """Test NodeJsSkillAdapter _run method."""
        from core.skill_adapter import NodeJsSkillAdapter

        adapter = NodeJsSkillAdapter(
            skill_id=nodejs_skill["skill_id"],
            code=nodejs_skill["code"],
            node_packages=nodejs_skill["node_packages"],
            agent_id=nodejs_skill["agent_id"]
        )

        # Test that _run returns error message (since npm packages are mocked)
        result = adapter._run({"query": "test"})
        # Should return an error about npm packages since modules are mocked
        assert isinstance(result, str)
