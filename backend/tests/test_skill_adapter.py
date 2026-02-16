"""
Tests for CommunitySkillTool - LangChain BaseTool adapter.

Tests cover:
- BaseTool subclass verification
- Factory function functionality
- Prompt-only skill execution with template interpolation
- Python skill execution (NotImplementedError without sandbox)
- Pydantic args_schema validation
- Async execution delegation
"""

import pytest

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

    @patch('core.skill_adapter.HazardSandbox')
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
        """Test that async Python skill execution also raises."""
        tool = create_community_tool(python_skill)

        with pytest.raises(NotImplementedError):
            await tool._arun("test query")


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
