"""
Autonomous Coder Agent - Code generation with quality enforcement.

Generates type-safe, well-documented code from implementation plans.
Supports backend (Python), frontend (React/TypeScript), and database (SQL) code.

Integration:
- Uses ImplementationTask from PlanningAgent as input
- Integrates with BYOK handler for LLM code generation
- Uses CodeQualityService for automatic quality enforcement
- Generates code following Atom patterns and standards

Performance targets:
- Code generation: <30 seconds per file
- Quality gate iteration: <1 minute (max 3 iterations)
- Service generation: <1 minute
- Migration generation: <30 seconds
"""

import asyncio
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.autonomous_planning_agent import (
    AgentType,
    ImplementationTask,
    TaskComplexity,
)
from core.code_quality_service import CodeQualityService
from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)


# ============================================================================
# Task 2: CoderAgent Base Class and Specializations
# ============================================================================

class CoderSpecialization(str, Enum):
    """Coder specialization types."""
    BACKEND = "coder-backend"
    FRONTEND = "coder-frontend"
    DATABASE = "coder-database"


class CoderAgent:
    """
    Base class for autonomous code generation agents.

    Generates code from implementation tasks with automatic
    quality enforcement and Atom pattern adherence.

    Attributes:
        db: Database session for persistence
        byok_handler: LLM handler for code generation
        quality_service: Code quality checking service
        specialization: Agent specialization type
        code_templates: Loaded code template library

    Example:
        coder = BackendCoder(db, byok_handler)
        result = await coder.generate_code(task, context)
        if result["quality_passed"]:
            print(f"Generated {len(result['files'])} files")
    """

    def __init__(
        self,
        db: Session,
        byok_handler: BYOKHandler,
        quality_service: CodeQualityService,
        specialization: CoderSpecialization,
    ):
        """
        Initialize coder agent.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
            quality_service: Code quality service
            specialization: Agent specialization type
        """
        self.db = db
        self.byok_handler = byok_handler
        self.quality_service = quality_service
        self.specialization = specialization
        self.code_templates = self._load_templates()

    async def generate_code(
        self,
        task: ImplementationTask,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate code for an implementation task.

        Routes to specialized generation method based on task type.
        Applies quality gates before returning generated code.

        Args:
            task: ImplementationTask from PlanningAgent
            context: Codebase context, existing code patterns

        Returns:
            {
                "files": [
                    {
                        "path": str,
                        "code": str,
                        "language": str,  # python, typescript, sql
                        "quality_checks": {
                            "mypy_passed": bool,
                            "black_formatted": bool,
                            "docstrings_complete": bool
                        }
                    }
                ],
                "errors": [str],
                "warnings": [str]
            }
        """
        logger.info(f"Generating code for task: {task.name}")

        try:
            # Extract file requirements from task
            files_to_create = task.files_to_create
            files_to_modify = task.files_to_modify

            generated_files = []
            all_errors = []
            all_warnings = []

            # Generate each file
            for file_path in files_to_create:
                logger.info(f"Generating file: {file_path}")

                # Determine language from file extension
                language = self._detect_language(file_path)

                # Generate code for this file
                code_result = await self._generate_file_code(
                    task, file_path, language, context
                )

                if code_result["errors"]:
                    all_errors.extend(code_result["errors"])
                    continue

                # Apply quality gates
                quality_result = await self._enforce_quality_gates(
                    code_result["code"], file_path
                )

                generated_files.append({
                    "path": file_path,
                    "code": quality_result["code"],
                    "language": language,
                    "quality_checks": quality_result["quality_report"],
                })

                all_warnings.extend(quality_result["warnings"])

            return {
                "files": generated_files,
                "errors": all_errors,
                "warnings": all_warnings,
            }

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return {
                "files": [],
                "errors": [str(e)],
                "warnings": [],
            }

    def _load_templates(self) -> Dict[str, str]:
        """
        Load code templates for common patterns.

        Returns template library with Atom code patterns.

        Returns:
            Dict mapping template names to template strings
        """
        return CodeTemplateLibrary.get_all_templates()

    async def _generate_with_llm(
        self,
        prompt: str,
        code_context: str,
    ) -> str:
        """
        Generate code using LLM via BYOK handler.

        Uses Anthropic Claude for best code generation quality.

        Args:
            prompt: Code generation prompt with requirements
            code_context: Existing code patterns for consistency

        Returns:
            Generated code string
        """
        logger.info("Generating code with LLM")

        try:
            # Build full prompt with context
            full_prompt = f"""{prompt}

Context from existing codebase:
{code_context}

Generate production-ready code that:
1. Follows Atom coding standards
2. Uses Google-style docstrings
3. Has complete type hints
4. Includes proper error handling
5. Follows existing patterns

Return only the code, no explanations."""

            # Generate using BYOK handler
            # Use Anthropic for best code quality
            response = await self.byok_handler.execute_prompt(
                prompt=full_prompt,
                provider="anthropic",
                model="claude-4-sonnet-20250514",
                cognitive_tier=None,  # Use default
            )

            return response.get("content", "")

        except Exception as e:
            logger.error(f"LLM code generation failed: {e}")
            raise

    async def _enforce_quality_gates(
        self,
        code: str,
        file_path: str,
    ) -> Dict[str, Any]:
        """
        Apply quality gates and iterate until passing.

        Runs mypy, black, isort; fixes issues; retries.
        Max iterations: 3

        Args:
            code: Generated code to validate
            file_path: File path for module resolution

        Returns:
            {
                "code": str,  # Code after quality fixes
                "quality_report": dict,
                "warnings": [str]
            }
        """
        logger.info(f"Enforcing quality gates for {file_path}")

        max_iterations = 3
        current_code = code

        for iteration in range(max_iterations):
            logger.info(f"Quality gate iteration {iteration + 1}/{max_iterations}")

            # Run all quality checks
            result = await self.quality_service.enforce_all_quality_gates(
                current_code, file_path
            )

            if result["passed"]:
                logger.info("Quality gates passed!")
                return {
                    "code": result["code"],
                    "quality_report": result["quality_report"],
                    "warnings": result["warnings"],
                }

            # Check if blocking errors remain
            if result["errors"]:
                # Try to fix errors automatically
                current_code = await self._fix_quality_errors(
                    result["code"], result["errors"]
                )
            else:
                # Just warnings, use current code
                current_code = result["code"]

        # Max iterations reached, return best effort
        logger.warning(f"Quality gates did not pass after {max_iterations} iterations")
        return {
            "code": current_code,
            "quality_report": result["quality_report"],
            "warnings": result["warnings"],
        }

    async def _fix_quality_errors(
        self,
        code: str,
        errors: List[str],
    ) -> str:
        """
        Attempt to fix quality errors automatically.

        Uses LLM to generate fixes for type errors and other issues.

        Args:
            code: Code with errors
            errors: List of error messages

        Returns:
            Fixed code string
        """
        logger.info(f"Attempting to fix {len(errors)} quality errors")

        try:
            prompt = f"""Fix these quality errors in the code:

Errors:
{chr(10).join(errors[:10])}  # Limit to first 10

Code:
{code}

Return only the fixed code, no explanations."""

            response = await self._generate_with_llm(prompt, "")
            return response if response else code

        except Exception as e:
            logger.error(f"Error fixing failed: {e}")
            return code

    async def add_docstrings(self, code: str) -> str:
        """
        Add Google-style docstrings to functions missing them.

        Uses LLM to generate docstrings from function signatures.

        Args:
            code: Code without complete docstrings

        Returns:
            Code with docstrings added
        """
        logger.info("Adding docstrings to generated code")

        try:
            # Check which functions need docstrings
            validation = self.quality_service.validate_docstrings(code)

            if validation["missing_count"] == 0:
                return code  # All functions have docstrings

            prompt = f"""Add Google-style docstrings to these functions:

Functions missing docstrings: {', '.join(validation['missing_functions'][:10])}

Code:
{code}

Generate docstrings that include:
1. Summary line (one sentence)
2. Args section (if has parameters)
3. Returns section (if returns value)
4. Raises section (if raises exceptions)

Return only the code with docstrings added."""

            response = await self._generate_with_llm(prompt, "")
            return response if response else code

        except Exception as e:
            logger.error(f"Docstring generation failed: {e}")
            return code

    def _detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file path.

        Args:
            file_path: File path to analyze

        Returns:
            Language string (python, typescript, sql, etc.)
        """
        suffix = Path(file_path).suffix.lower()

        language_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".sql": "sql",
        }

        return language_map.get(suffix, "text")

    async def _generate_file_code(
        self,
        task: ImplementationTask,
        file_path: str,
        language: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate code for a specific file.

        Args:
            task: Implementation task
            file_path: File to generate
            language: Programming language
            context: Codebase context

        Returns:
            {
                "code": str,
                "errors": [str]
            }
        """
        # Build generation prompt
        prompt = self._build_generation_prompt(task, file_path, language, context)

        # Get existing code context
        code_context = context.get("existing_code", {}).get(file_path, "")

        # Generate code
        try:
            code = await self._generate_with_llm(prompt, code_context)
            return {"code": code, "errors": []}
        except Exception as e:
            logger.error(f"File code generation failed: {e}")
            return {"code": "", "errors": [str(e)]}

    def _build_generation_prompt(
        self,
        task: ImplementationTask,
        file_path: str,
        language: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Build code generation prompt.

        Args:
            task: Implementation task
            file_path: File to generate
            language: Programming language
            context: Codebase context

        Returns:
            Prompt string for LLM
        """
        return f"""Generate {language} code for this file:

File: {file_path}
Task: {task.name}
Description: {task.description}
Complexity: {task.complexity.value}

Requirements:
{chr(10).join(f'- {req}' for req in context.get('requirements', []))}

Generate complete, production-ready code that:
1. Follows Atom coding standards
2. Has complete type hints
3. Uses Google-style docstrings
4. Includes proper error handling
5. Follows existing code patterns

Return only the code, no explanations."""


class BackendCoder(CoderAgent):
    """
    Specializes in backend Python code generation.

    Generates FastAPI services, routes, models, and migrations.
    Enforces Python quality standards (mypy, black, isort).

    Example:
        coder = BackendCoder(db, byok_handler)
        service_code = await coder.generate_service(
            "OAuthService",
            methods,
            context
        )
    """

    def __init__(self, db: Session, byok_handler: BYOKHandler):
        """
        Initialize backend coder.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
        """
        quality_service = CodeQualityService(project_root="backend")
        super().__init__(db, byok_handler, quality_service, CoderSpecialization.BACKEND)

    async def generate_service(
        self,
        service_name: str,
        methods: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """
        Generate a service class with methods.

        Args:
            service_name: Name of service (e.g., "OAuthService")
            methods: List of method definitions
            context: Existing code patterns

        Returns:
            Complete service file content
        """
        logger.info(f"Generating service: {service_name}")

        prompt = f"""Generate a Python service class:

Service Name: {service_name}

Methods:
{chr(10).join(f'- {m.get("name", "")}({m.get("params", "")}): {m.get("description", "")}' for m in methods)}

Follow this pattern:
1. Google-style module docstring
2. Import statements (standard, third-party, local)
3. Service class with __init__
4. Methods with Google-style docstrings
5. Type hints on all functions
6. Error handling with try/except
7. Logging with logger instance

Return only the code, no explanations."""

        existing_patterns = context.get("existing_services", "")
        return await self._generate_with_llm(prompt, existing_patterns)

    async def generate_routes(
        self,
        routes: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """
        Generate FastAPI routes.

        Args:
            routes: List of route definitions (path, method, handler)
            context: Existing route patterns

        Returns:
            Complete routes file content
        """
        logger.info(f"Generating {len(routes)} routes")

        prompt = f"""Generate FastAPI routes:

Routes:
{chr(10).join(f'{r.get("method", "GET").upper()} {r.get("path", "/")}: {r.get("handler", "")}' for r in routes)}

Follow this pattern:
1. Import FastAPI, Depends, status
2. Import service classes
3. APIRouter instance
4. Route handlers with:
   - Type hints
   - Google-style docstrings
   - Error handling
   - Proper status codes
5. Pydantic models for request/response

Return only the code, no explanations."""

        existing_patterns = context.get("existing_routes", "")
        return await self._generate_with_llm(prompt, existing_patterns)

    async def generate_models(
        self,
        models: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """
        Generate SQLAlchemy model definitions.

        Args:
            models: List of model definitions
            context: Existing model patterns

        Returns:
            Model code with proper relationships and indexes
        """
        logger.info(f"Generating {len(models)} models")

        prompt = f"""Generate SQLAlchemy models:

Models:
{chr(10).join(f'- {m.get("name", "")}: {m.get("description", "")}' for m in models)}

Follow this pattern:
1. Import Column, Integer, String, Boolean, DateTime, ForeignKey, relationship
2. Import declarative_base
3. Model class with __tablename__
4. Columns with types and constraints
5. Relationships with back_populates
6. Indexes on frequently queried columns
7. __repr__ method for debugging

Return only the code, no explanations."""

        existing_patterns = context.get("existing_models", "")
        return await self._generate_with_llm(prompt, existing_patterns)

    async def _generate_file_code(
        self,
        task: ImplementationTask,
        file_path: str,
        language: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate backend file code.

        Routes to specialized methods based on file type.

        Args:
            task: Implementation task
            file_path: File to generate
            language: Programming language
            context: Codebase context

        Returns:
            Generated code with any errors
        """
        # Determine file type
        if "service" in file_path.lower():
            # Extract service name from task
            service_name = Path(file_path).stem
            code = await self.generate_service(
                service_name,
                task.description.get("methods", []),
                context,
            )
            return {"code": code, "errors": []}

        elif "routes" in file_path.lower():
            # Extract routes from task
            routes = task.description.get("routes", [])
            code = await self.generate_routes(routes, context)
            return {"code": code, "errors": []}

        elif "models" in file_path.lower():
            # Extract models from task
            models = task.description.get("models", [])
            code = await self.generate_models(models, context)
            return {"code": code, "errors": []}

        else:
            # Use base implementation
            return await super()._generate_file_code(task, file_path, language, context)


# ============================================================================
# Task 5: Code Template Library
# ============================================================================

class CodeTemplateLibrary:
    """
    Library of code templates following Atom patterns.

    Provides reusable templates for common code patterns
    to ensure consistency across generated code.

    Example:
        template = CodeTemplateLibrary.get_template("service", "backend")
        filled = CodeTemplateLibrary.fill_template(template, variables)
    """

    # Backend templates
    SERVICE_TEMPLATE = """
\"\"\"{service_name} service for {purpose}.

This service handles {responsibilities}.
\"\"\"

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class {service_name}:
    \"\"\"Service for {service_description}.\"\"\"

    def __init__(self, db: Session):
        \"\"\"
        Initialize service.

        Args:
            db: Database session
        \"\"\"
        self.db = db

    async def {method_name}(
        self,
        {params}
    ) -> {return_type}:
        \"\"\"
        {method_description}

        Args:
            {arg_descriptions}

        Returns:
            {return_description}

        Raises:
            {raises}
        \"\"\"
        try:
            # Implementation
            pass
        except Exception as e:
            logger.error(f\"Operation failed: {{e}}\")
            raise
"""

    ROUTES_TEMPLATE = """
\"\"\"{route_name} routes.

{route_description}.
\"\"\"

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from core.database import get_db
from {service_import} import {service_name}

router = APIRouter(prefix=\"{route_prefix}\", tags=[\"{tag_name}\"])


@router.{method_lowercase}(\"{path}\", response_model={response_model})
async def {handler_name}(
    {params},
    db: Session = Depends(get_db)
):
    \"\"\"
    {handler_description}.

    Args:
        {param_descriptions}

    Returns:
        {return_description}

    Raises:
        HTTPException: If {error_condition}
    \"\"\"
    try:
        service = {service_name}(db)
        result = await service.{service_method}({service_args})
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
"""

    MODEL_TEMPLATE = """
\"\"\"{model_name} model.

{model_description}.
\"\"\"

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class {model_name}(Base):
    \"\"\"
    {model_description}.

    Attributes:
        {attributes}
    \"\"\"
    __tablename__ = \"{table_name}\"

    id = Column(Integer, primary_key=True, index=True)
{columns}

    {relationships}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f\"<{self.__class__.__name__}(id={{self.id}})>\"
"""

    @classmethod
    def get_template(cls, template_type: str, specialization: str) -> str:
        """
        Get template by type and specialization.

        Args:
            template_type: Type of template (service, routes, model, etc.)
            specialization: Coder specialization (backend, frontend, database)

        Returns:
            Template string
        """
        template_key = f"{template_type.upper()}_TEMPLATE"
        return getattr(cls, template_key, "")

    @classmethod
    def fill_template(cls, template: str, variables: Dict[str, Any]) -> str:
        """
        Fill template with variables.

        Args:
            template: Template string with {variable} placeholders
            variables: Dict of variable names to values

        Returns:
            Filled template string
        """
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return template

    @classmethod
    def get_all_templates(cls) -> Dict[str, str]:
        """
        Get all available templates.

        Returns:
            Dict mapping template names to template strings
        """
        return {
            "service": cls.SERVICE_TEMPLATE,
            "routes": cls.ROUTES_TEMPLATE,
            "model": cls.MODEL_TEMPLATE,
        }
