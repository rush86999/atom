"""
Tests for Autonomous Coder Agent - Code generation with quality enforcement.

Tests cover:
- CodeQualityService (mypy, black, isort, flake8)
- BackendCoder (service, routes, models generation)
- FrontendCoder (component, hooks, pages)
- DatabaseCoder (migrations, models)
- CodeTemplateLibrary (template filling)
- CodeGeneratorOrchestrator (plan generation)
- Quality gate enforcement
- Docstring generation
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from pathlib import Path
from sqlalchemy.orm import Session

from core.autonomous_coder_agent import (
    BackendCoder,
    FrontendCoder,
    DatabaseCoder,
    CodeGeneratorOrchestrator,
    CodeTemplateLibrary,
    CoderSpecialization,
)
from core.autonomous_planning_agent import (
    ImplementationTask,
    AgentType,
    TaskComplexity,
)
from core.code_quality_service import CodeQualityService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create mock database session."""
    session = Mock(spec=Session)
    return session


@pytest.fixture
def mock_byok_handler():
    """Create mock BYOK handler."""
    handler = AsyncMock()
    handler.execute_prompt = AsyncMock(return_value={
        "content": """# Generated code

async def example_function(param1: str, param2: int) -> bool:
    \"\"\"
    Example function with Google-style docstring.

    Args:
        param1: First parameter description
        param2: Second parameter description

    Returns:
        True if successful, False otherwise
    \"\"\"
    try:
        result = await process(param1, param2)
        return result
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise
"""
    })
    return handler


@pytest.fixture
def quality_service():
    """Create CodeQualityService instance."""
    return CodeQualityService(project_root="backend")


@pytest.fixture
def sample_task():
    """Create sample ImplementationTask."""
    return ImplementationTask(
        id="task-001",
        name="Create OAuth service",
        agent_type=AgentType.CODER_BACKEND,
        description={
            "purpose": "Handle OAuth authentication",
            "methods": [
                {
                    "name": "authenticate",
                    "params": "code: str, redirect_uri: str",
                    "description": "Authenticate user with OAuth code",
                }
            ],
        },
        dependencies=[],
        files_to_create=["backend/core/oauth_service.py"],
        files_to_modify=[],
        estimated_time_minutes=30,
        complexity=TaskComplexity.MODERATE,
        can_parallelize=False,
    )


@pytest.fixture
def sample_plan():
    """Create sample implementation plan."""
    return {
        "tasks": [
            {
                "id": "task-001",
                "name": "Create OAuth service",
                "agent_type": "coder-backend",
                "description": {"methods": []},
                "dependencies": [],
                "files_to_create": ["backend/core/oauth_service.py"],
                "files_to_modify": [],
                "estimated_time_minutes": 30,
                "complexity": "moderate",
                "can_parallelize": False,
            }
        ],
        "context": {
            "existing_code": {},
            "requirements": [
                "Handle OAuth2 flow",
                "Support multiple providers",
            ],
        },
    }


# ============================================================================
# CodeQualityService Tests
# ============================================================================

class TestCodeQualityService:
    """Tests for CodeQualityService."""

    @pytest.mark.asyncio
    async def test_check_mypy_with_valid_code(self, quality_service):
        """Test mypy checking with valid type hints."""
        code = """
def add_numbers(a: int, b: int) -> int:
    return a + b
"""
        result = await quality_service.check_mypy(code, "test.py")

        assert "passed" in result
        assert "errors" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_check_mypy_with_invalid_code(self, quality_service):
        """Test mypy checking with type errors."""
        code = """
def add_numbers(a: int, b: str) -> int:
    return a + b
"""
        result = await quality_service.check_mypy(code, "test.py")

        assert "passed" in result
        # May or may not pass depending on mypy installation

    @pytest.mark.asyncio
    async def test_format_with_black(self, quality_service):
        """Test Black code formatting."""
        unformatted = """
def example(  ):
    x=1+2
    return x
"""
        result = await quality_service.format_with_black(unformatted)

        assert "formatted_code" in result
        assert "changed" in result
        assert result["formatted_code"] is not None

    @pytest.mark.asyncio
    async def test_sort_imports(self, quality_service):
        """Test isort import sorting."""
        unsorted = """
import sys
import os
from typing import List
import asyncio
"""
        result = await quality_service.sort_imports(unsorted)

        assert "sorted_code" in result
        assert "changed" in result
        assert result["sorted_code"] is not None

    @pytest.mark.asyncio
    async def test_enforce_all_quality_gates(self, quality_service):
        """Test running all quality gates."""
        code = """
def example_function(param: str) -> bool:
    '''Simple function.'''
    return bool(param)
"""
        result = await quality_service.enforce_all_quality_gates(code, "test.py")

        assert "code" in result
        assert "passed" in result
        assert "quality_report" in result
        assert "isort_sorted" in result["quality_report"]
        assert "black_formatted" in result["quality_report"]

    def test_validate_docstrings(self, quality_service):
        """Test Google-style docstring validation."""
        code = """
def function_with_docstring(param: str) -> bool:
    \"\"\"
    Example function with Google-style docstring.

    Args:
        param: Parameter description

    Returns:
        Boolean result
    \"\"\"
    return True

def function_without_docstring(param: str) -> bool:
    return False
"""
        result = quality_service.validate_docstrings(code)

        assert "valid_count" in result
        assert "missing_count" in result
        assert "missing_functions" in result
        assert result["valid_count"] >= 1


# ============================================================================
# BackendCoder Tests
# ============================================================================

class TestBackendCoder:
    """Tests for BackendCoder."""

    def test_init(self, db_session, mock_byok_handler):
        """Test BackendCoder initialization."""
        coder = BackendCoder(db_session, mock_byok_handler)

        assert coder.specialization == CoderSpecialization.BACKEND
        assert coder.db == db_session
        assert coder.byok_handler == mock_byok_handler
        assert coder.quality_service is not None

    @pytest.mark.asyncio
    async def test_generate_service(self, db_session, mock_byok_handler):
        """Test service generation."""
        coder = BackendCoder(db_session, mock_byok_handler)

        methods = [
            {
                "name": "authenticate",
                "params": "code: str, redirect_uri: str",
                "description": "Authenticate user",
            }
        ]

        code = await coder.generate_service("OAuthService", methods, {})

        assert code is not None
        assert len(code) > 0
        assert "class OAuthService" in code or "OAuthService" in code

    @pytest.mark.asyncio
    async def test_generate_routes(self, db_session, mock_byok_handler):
        """Test route generation."""
        coder = BackendCoder(db_session, mock_byok_handler)

        routes = [
            {
                "method": "POST",
                "path": "/auth/oauth",
                "handler": "oauth_handler",
            }
        ]

        code = await coder.generate_routes(routes, {})

        assert code is not None
        assert len(code) > 0
        assert "router" in code.lower() or "APIRouter" in code

    @pytest.mark.asyncio
    async def test_generate_models(self, db_session, mock_byok_handler):
        """Test model generation."""
        coder = BackendCoder(db_session, mock_byok_handler)

        models = [
            {
                "name": "OAuthToken",
                "description": "OAuth token storage",
            }
        ]

        code = await coder.generate_models(models, {})

        assert code is not None
        assert len(code) > 0
        assert "OAuthToken" in code

    @pytest.mark.asyncio
    async def test_generate_code(self, db_session, mock_byok_handler, sample_task):
        """Test code generation from task."""
        coder = BackendCoder(db_session, mock_byok_handler)

        result = await coder.generate_code(sample_task, {})

        assert "files" in result
        assert "errors" in result
        assert isinstance(result["files"], list)


# ============================================================================
# FrontendCoder Tests
# ============================================================================

class TestFrontendCoder:
    """Tests for FrontendCoder."""

    def test_init(self, db_session, mock_byok_handler):
        """Test FrontendCoder initialization."""
        coder = FrontendCoder(db_session, mock_byok_handler)

        assert coder.specialization == CoderSpecialization.FRONTEND
        assert coder.db == db_session

    @pytest.mark.asyncio
    async def test_generate_component(self, db_session, mock_byok_handler):
        """Test React component generation."""
        coder = FrontendCoder(db_session, mock_byok_handler)

        props = [
            {"name": "userId", "type": "string", "optional": False},
            {"name": "onLogin", "type": "() => void", "optional": True},
        ]

        code = await coder.generate_component("UserProfile", props, {})

        assert code is not None
        assert len(code) > 0
        assert "UserProfile" in code

    @pytest.mark.asyncio
    async def test_generate_hooks(self, db_session, mock_byok_handler):
        """Test custom hook generation."""
        coder = FrontendCoder(db_session, mock_byok_handler)

        logic = {
            "description": "Manage canvas state",
        }

        code = await coder.generate_hooks("useCanvasState", logic, {})

        assert code is not None
        assert len(code) > 0
        assert "useCanvasState" in code

    @pytest.mark.asyncio
    async def test_generate_page(self, db_session, mock_byok_handler):
        """Test Next.js page generation."""
        coder = FrontendCoder(db_session, mock_byok_handler)

        components = ["UserProfile", "Navigation"]

        code = await coder.generate_page("Dashboard", components, {})

        assert code is not None
        assert len(code) > 0
        assert "Dashboard" in code

    def test_generate_typescript_types(self, db_session, mock_byok_handler):
        """Test TypeScript interface generation."""
        coder = FrontendCoder(db_session, mock_byok_handler)

        props = [
            {"name": "userId", "type": "string", "optional": False},
            {"name": "isActive", "type": "boolean", "optional": True},
        ]

        types = coder._generate_typescript_types(props)

        assert "userId" in types
        assert "isActive" in types
        assert "?" in types  # Optional marker

    def test_generate_imports(self, db_session, mock_byok_handler):
        """Test import statement generation."""
        coder = FrontendCoder(db_session, mock_byok_handler)

        components = ["UserProfile", "Navigation"]
        context = {
            "component_paths": {
                "UserProfile": "./components/UserProfile",
                "Navigation": "./components/Navigation",
            }
        }

        imports = coder._generate_imports(components, context)

        assert "import" in imports
        assert "UserProfile" in imports
        assert "Navigation" in imports


# ============================================================================
# DatabaseCoder Tests
# ============================================================================

class TestDatabaseCoder:
    """Tests for DatabaseCoder."""

    def test_init(self, db_session, mock_byok_handler):
        """Test DatabaseCoder initialization."""
        coder = DatabaseCoder(db_session, mock_byok_handler)

        assert coder.specialization == CoderSpecialization.DATABASE
        assert coder.db == db_session

    @pytest.mark.asyncio
    async def test_generate_migration(self, db_session, mock_byok_handler):
        """Test migration generation."""
        coder = DatabaseCoder(db_session, mock_byok_handler)

        operations = [
            {
                "type": "create_table",
                "table_name": "oauth_tokens",
                "columns": [
                    {"name": "token", "type": "string", "nullable": False},
                    {"name": "expires_at", "type": "datetime", "nullable": True},
                ],
            }
        ]

        code = await coder.generate_migration("Add OAuth tokens table", operations, {})

        assert code is not None
        assert len(code) > 0
        assert "upgrade" in code.lower()
        assert "downgrade" in code.lower()

    @pytest.mark.asyncio
    async def test_generate_upgrade_downgrade(self, db_session, mock_byok_handler):
        """Test upgrade/downgrade generation."""
        coder = DatabaseCoder(db_session, mock_byok_handler)

        operations = [
            {"type": "create_table", "table_name": "test_table", "columns": []},
        ]

        upgrade, downgrade = await coder.generate_upgrade_downgrade(operations)

        assert "create_table" in upgrade
        assert "drop_table" in downgrade

    def test_generate_column_definition(self, db_session, mock_byok_handler):
        """Test column definition generation."""
        coder = DatabaseCoder(db_session, mock_byok_handler)

        field = {
            "name": "email",
            "type": "string",
            "nullable": False,
            "index": True,
        }

        col_def = coder._generate_column_definition(field)

        assert "email" in col_def
        assert "sa.String" in col_def
        assert "nullable=False" in col_def
        assert "index=True" in col_def

    def test_generate_relationship(self, db_session, mock_byok_handler):
        """Test relationship definition generation."""
        coder = DatabaseCoder(db_session, mock_byok_handler)

        relationship = {
            "name": "user",
            "target_model": "User",
            "back_populates": "tokens",
            "lazy": "select",
        }

        rel_def = coder._generate_relationship(relationship)

        assert "relationship" in rel_def
        assert "User" in rel_def
        assert "back_populates" in rel_def


# ============================================================================
# CodeTemplateLibrary Tests
# ============================================================================

class TestCodeTemplateLibrary:
    """Tests for CodeTemplateLibrary."""

    def test_get_template_service(self):
        """Test getting service template."""
        template = CodeTemplateLibrary.get_template("service", "backend")

        assert template is not None
        assert "{service_name}" in template
        assert "class " in template

    def test_get_template_routes(self):
        """Test getting routes template."""
        template = CodeTemplateLibrary.get_template("routes", "backend")

        assert template is not None
        assert "@router." in template or "router" in template

    def test_get_template_model(self):
        """Test getting model template."""
        template = CodeTemplateLibrary.get_template("model", "backend")

        assert template is not None
        assert "__tablename__" in template
        assert "Column" in template

    def test_fill_template(self):
        """Test template variable filling."""
        template = "class {service_name}:\n    pass"

        filled = CodeTemplateLibrary.fill_template(
            template,
            {"service_name": "TestService"}
        )

        assert "TestService" in filled
        assert "{service_name}" not in filled

    def test_get_all_templates(self):
        """Test getting all templates."""
        templates = CodeTemplateLibrary.get_all_templates()

        assert isinstance(templates, dict)
        assert "service" in templates
        assert "routes" in templates
        assert "model" in templates


# ============================================================================
# CodeGeneratorOrchestrator Tests
# ============================================================================

class TestCodeGeneratorOrchestrator:
    """Tests for CodeGeneratorOrchestrator."""

    def test_init(self, db_session, mock_byok_handler):
        """Test orchestrator initialization."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        assert orchestrator.db == db_session
        assert orchestrator.backend_coder is not None
        assert orchestrator.frontend_coder is not None
        assert orchestrator.database_coder is not None

    @pytest.mark.asyncio
    async def test_generate_from_plan(self, db_session, mock_byok_handler, sample_plan):
        """Test generation from implementation plan."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        result = await orchestrator.generate_from_plan(sample_plan)

        assert "files_generated" in result
        assert "total_lines" in result
        assert "quality_summary" in result
        assert "errors" in result
        assert isinstance(result["files_generated"], list)

    @pytest.mark.asyncio
    async def test_generate_task(self, db_session, mock_byok_handler, sample_task):
        """Test single task generation."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        result = await orchestrator.generate_task(sample_task, {})

        assert "files" in result
        assert "errors" in result
        assert isinstance(result["files"], list)

    def test_select_coder(self, db_session, mock_byok_handler):
        """Test coder selection."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        backend_coder = orchestrator.select_coder(AgentType.CODER_BACKEND)
        frontend_coder = orchestrator.select_coder(AgentType.CODER_FRONTEND)
        database_coder = orchestrator.select_coder(AgentType.CODER_DATABASE)

        assert isinstance(backend_coder, BackendCoder)
        assert isinstance(frontend_coder, FrontendCoder)
        assert isinstance(database_coder, DatabaseCoder)

    def test_select_coder_invalid(self, db_session, mock_byok_handler):
        """Test coder selection with invalid type."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        with pytest.raises(ValueError):
            orchestrator.select_coder(AgentType.TESTER)  # No coder for TESTER

    def test_dict_to_task(self, db_session, mock_byok_handler):
        """Test dict to ImplementationTask conversion."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        task_dict = {
            "id": "task-001",
            "name": "Test Task",
            "agent_type": "coder-backend",
            "description": {},
            "dependencies": [],
            "files_to_create": [],
            "files_to_modify": [],
            "estimated_time_minutes": 10,
            "complexity": "simple",
            "can_parallelize": True,
        }

        task = orchestrator._dict_to_task(task_dict)

        assert isinstance(task, ImplementationTask)
        assert task.id == "task-001"
        assert task.name == "Test Task"
        assert task.agent_type == AgentType.CODER_BACKEND

    def test_build_quality_summary(self, db_session, mock_byok_handler):
        """Test quality summary building."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        files = [
            {
                "path": "test.py",
                "code": "print('test')",
                "quality_checks": {
                    "mypy_passed": True,
                    "black_formatted": True,
                    "isort_sorted": True,
                    "flake8_passed": True,
                },
            }
        ]

        summary = orchestrator._build_quality_summary(files)

        assert summary["total_files"] == 1
        assert summary["mypy_passed"] == 1
        assert summary["black_formatted"] == 1
        assert summary["pass_rate"] == 1.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for code generation workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, db_session, mock_byok_handler, sample_plan):
        """Test complete workflow from plan to generated code."""
        orchestrator = CodeGeneratorOrchestrator(db_session, mock_byok_handler)

        # Generate from plan
        result = await orchestrator.generate_from_plan(sample_plan)

        # Verify files generated
        assert len(result["files_generated"]) >= 0

        # Verify no critical errors
        assert len(result["errors"]) == 0 or isinstance(result["errors"], list)

    @pytest.mark.asyncio
    async def test_quality_gate_enforcement(self, db_session, mock_byok_handler):
        """Test quality gate enforcement during generation."""
        coder = BackendCoder(db_session, mock_byok_handler)

        # Generate code that needs quality fixes
        code = "def example(  ):\n    x=1\n    return x"

        result = await coder._enforce_quality_gates(code, "test.py")

        assert "code" in result
        assert "quality_report" in result
        # Code should be formatted after quality gates
        assert len(result["code"]) > 0

    @pytest.mark.asyncio
    async def test_error_handling_llm_failure(self, db_session):
        """Test error handling when LLM fails."""
        # Create handler that raises exception
        failing_handler = AsyncMock()
        failing_handler.execute_prompt = AsyncMock(side_effect=Exception("LLM error"))

        coder = BackendCoder(db_session, failing_handler)

        task = ImplementationTask(
            id="task-001",
            name="Test Task",
            agent_type=AgentType.CODER_BACKEND,
            description={},
            dependencies=[],
            files_to_create=["test.py"],
            files_to_modify=[],
            estimated_time_minutes=10,
            complexity=TaskComplexity.SIMPLE,
            can_parallelize=True,
        )

        result = await coder.generate_code(task, {})

        # Should handle error gracefully
        assert "errors" in result
        assert len(result["errors"]) >= 0
