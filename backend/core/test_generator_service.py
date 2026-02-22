"""
Test Generator Service - AI-powered comprehensive test generation.

Automatically creates pytest test suites from generated code with:
- Parametrized tests for multiple scenarios
- Hypothesis property-based tests for edge cases
- Database and API fixtures
- Coverage target enforcement (85% unit, 70% integration)
- Iterative generation until coverage met

Integration:
- Uses ImplementationTask from PlanningAgent as input
- Uses GeneratedCode from CoderAgent for test generation
- Integrates with BYOK handler for LLM test refinement
- Uses pytest-cov for coverage measurement

Performance targets:
- Test file structure generation: <5 seconds
- Parametrized test generation: <3 seconds
- Property-based test generation: <5 seconds
- Coverage analysis: <10 seconds
- Full test suite generation: <30 seconds
"""

import ast
import asyncio
import json
import logging
import os
import re
import subprocess
from enum import Enum
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from core.autonomous_planning_agent import ImplementationTask
from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)


# Coverage target constants
COVERAGE_TARGET_UNIT = 85.0
COVERAGE_TARGET_INTEGRATION = 70.0
COVERAGE_TARGET_E2E = 60.0


# ============================================================================
# Task 1: Test File Structure Generator
# ============================================================================

class TestType(str, Enum):
    """Test classification types."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"


class TestFileStructureGenerator:
    """
    Generate test file structure from source code.

    Analyzes source files to extract functions, classes, and infer test cases.
    Generates pytest-compatible test file structures with proper naming.

    Attributes:
        project_root: Root directory for source code
        tests_root: Root directory for test files

    Example:
        generator = TestFileStructureGenerator("backend")
        structure = generator.generate_test_file_structure("core/oauth_service.py")
        # Returns: {"test_file_path": "tests/test_oauth_service.py", ...}
    """

    def __init__(self, project_root: str = "backend"):
        """
        Initialize test file structure generator.

        Args:
            project_root: Root directory for source code
        """
        self.project_root = Path(project_root)
        self.tests_root = self.project_root / "tests"

    def generate_test_file_structure(
        self,
        source_file: str
    ) -> Dict[str, Any]:
        """
        Analyze source file and generate test structure.

        Args:
            source_file: Path to source file (e.g., "core/oauth_service.py")

        Returns:
            {
                "test_file_path": "tests/test_oauth_service.py",
                "test_class_name": "TestOAuthService",
                "functions_to_test": [
                    {"name": "login", "args": [...], "return_type": "..."}
                ],
                "classes_to_test": [
                    {"name": "OAuthService", "methods": [...]}
                ],
                "fixtures_needed": ["db_session", "mock_oauth_provider"]
            }
        """
        source_path = self.project_root / source_file

        if not source_path.exists():
            logger.warning(f"Source file not found: {source_file}")
            return {}

        with open(source_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Parse source code
        tree = ast.parse(source_code)

        # Extract testable items
        testable_items = self.extract_testable_items(source_code)

        # Generate test file path
        test_file_path = self._infer_test_file_path(source_file)

        # Generate test class name
        test_class_name = self._infer_test_class_name(source_file)

        # Infer fixtures needed
        fixtures_needed = self._infer_fixtures_needed(
            testable_items["functions"],
            testable_items["classes"]
        )

        return {
            "test_file_path": str(test_file_path),
            "test_class_name": test_class_name,
            "functions_to_test": testable_items["functions"],
            "classes_to_test": testable_items["classes"],
            "fixtures_needed": fixtures_needed,
            "source_file": source_file
        }

    def extract_testable_items(
        self,
        source_code: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract functions and classes that need testing.

        Uses AST parsing to find public methods and functions.
        Filters out private/internal items (starting with _).

        Args:
            source_code: Python source code

        Returns:
            {
                "functions": [
                    {"name": "login", "args": ["user", "password"], "return_type": "..."}
                ],
                "classes": [
                    {"name": "OAuthService", "methods": [...]}
                ]
            }
        """
        tree = ast.parse(source_code)

        functions = []
        classes = []

        for node in ast.walk(tree):
            # Extract top-level functions
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions.append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "is_async": ast.iscoroutinefunction(node),
                    "lineno": node.lineno
                })

            # Extract classes and their methods
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        methods.append({
                            "name": item.name,
                            "args": [arg.arg for arg in item.args.args[1:]],  # Skip self
                            "is_async": ast.iscoroutinefunction(item),
                            "lineno": item.lineno
                        })

                if methods or not node.name.startswith("_"):
                    classes.append({
                        "name": node.name,
                        "methods": methods,
                        "lineno": node.lineno
                    })

        return {"functions": functions, "classes": classes}

    def infer_test_cases(
        self,
        function: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Infer test cases from function signature and docstring.

        Analyzes function name, parameters, and docstring to suggest
        test scenarios (success, failure, edge cases).

        Args:
            function: Function metadata from extract_testable_items

        Returns:
            [
                {"name": "test_login_success", "scenario": "Valid credentials"},
                {"name": "test_login_failure", "scenario": "Invalid credentials"}
            ]
        """
        test_cases = []
        func_name = function["name"]

        # Infer test cases from function name patterns
        if "create" in func_name or "add" in func_name or "insert" in func_name:
            test_cases.append({"name": f"test_{func_name}_success", "scenario": "Valid input"})
            test_cases.append({"name": f"test_{func_name}_duplicate", "scenario": "Duplicate entry"})
            test_cases.append({"name": f"test_{func_name}_invalid", "scenario": "Invalid input"})

        elif "get" in func_name or "fetch" in func_name or "find" in func_name:
            test_cases.append({"name": f"test_{func_name}_found", "scenario": "Existing item"})
            test_cases.append({"name": f"test_{func_name}_not_found", "scenario": "Non-existent item"})
            test_cases.append({"name": f"test_{func_name}_multiple", "scenario": "Multiple items"})

        elif "update" in func_name or "modify" in func_name:
            test_cases.append({"name": f"test_{func_name}_success", "scenario": "Valid update"})
            test_cases.append({"name": f"test_{func_name}_not_found", "scenario": "Non-existent item"})
            test_cases.append({"name": f"test_{func_name}_invalid", "scenario": "Invalid data"})

        elif "delete" in func_name or "remove" in func_name:
            test_cases.append({"name": f"test_{func_name}_success", "scenario": "Existing item"})
            test_cases.append({"name": f"test_{func_name}_not_found", "scenario": "Non-existent item"})

        else:
            # Default: success and failure cases
            test_cases.append({"name": f"test_{func_name}_success", "scenario": "Success case"})
            test_cases.append({"name": f"test_{func_name}_failure", "scenario": "Failure case"})

        return test_cases

    def suggest_test_name(
        self,
        function_name: str,
        scenario: str
    ) -> str:
        """
        Generate test name following Atom conventions.

        Pattern: test_{function}_{scenario}

        Args:
            function_name: Name of function being tested
            scenario: Test scenario description

        Returns:
            Test name (e.g., "test_login_success")
        """
        # Convert scenario to snake_case
        scenario_clean = scenario.lower().replace(" ", "_").replace("-", "_")
        scenario_clean = re.sub(r'_+', '_', scenario_clean).strip('_')

        return f"test_{function_name}_{scenario_clean}"

    def _infer_test_file_path(self, source_file: str) -> Path:
        """Infer test file path from source file path."""
        source_path = Path(source_file)

        # Handle different source locations
        if source_path.parts[0] == "core":
            # core/service.py -> tests/test_service.py
            return self.tests_root / f"test_{source_path.name}"
        elif source_path.parts[0] == "api":
            # api/routes.py -> tests/api/test_routes.py
            return self.tests_root / "api" / f"test_{source_path.name}"
        else:
            # Default: tests/{module}/test_{file}.py
            return self.tests_root / source_path.parent / f"test_{source_path.name}"

    def _infer_test_class_name(self, source_file: str) -> str:
        """Infer test class name from source file."""
        source_path = Path(source_file)
        module_name = source_path.stem  # Remove .py

        # Convert to PascalCase
        class_name = "".join(
            word.capitalize() for word in module_name.split("_")
        )

        return f"Test{class_name}"

    def _infer_fixtures_needed(
        self,
        functions: List[Dict[str, Any]],
        classes: List[Dict[str, Any]]
    ) -> List[str]:
        """Infer required fixtures from functions and classes."""
        fixtures = set()

        # Check for database operations
        db_keywords = ["db", "session", "query", "commit", "rollback"]
        for func in functions + [m for cls in classes for m in cls["methods"]]:
            for arg in func.get("args", []):
                if any(keyword in arg.lower() for keyword in db_keywords):
                    fixtures.add("db_session")
                    break

        # Check for API operations
        api_keywords = ["request", "response", "client", "headers"]
        for func in functions + [m for cls in classes for m in cls["methods"]]:
            for arg in func.get("args", []):
                if any(keyword in arg.lower() for keyword in api_keywords):
                    fixtures.add("api_client")
                    break

        # Check for external service calls
        for func in functions + [m for cls in classes for m in cls["methods"]]:
            if "http" in func["name"].lower() or "fetch" in func["name"].lower():
                fixtures.add("mock_http_client")
                break

        return sorted(list(fixtures))


# ============================================================================
# Task 2: Parametrized Test Generator
# ============================================================================

class ParametrizedTestGenerator:
    """
    Generate pytest parametrized tests.

    Creates @pytest.mark.parametrize decorators for testing multiple
    scenarios with a single test function.

    Example:
        generator = ParametrizedTestGenerator()
        test_code = generator.generate_parametrized_test(function, scenarios)
    """

    def generate_parametrized_test(
        self,
        function: Dict[str, Any],
        scenarios: List[Dict[str, Any]]
    ) -> str:
        """
        Generate parametrized test code.

        Args:
            function: Function metadata
            scenarios: List of test scenarios with parameters

        Returns:
            Parametrized test code as string

        Example output:
            ```python
            @pytest.mark.parametrize("provider,expected_url", [
                ("google", "https://accounts.google.com/..."),
                ("github", "https://github.com/login/..."),
                ("microsoft", "https://login.microsoftonline.com/...")
            ])
            def test_oauth_redirect_urls(provider, expected_url):
                service = OAuthService()
                url = service.get_authorization_url(provider)
                assert url.startswith(expected_url)
            ```
        """
        if not scenarios:
            return ""

        # Extract parameter names from first scenario
        param_names = list(scenarios[0].keys())

        # Generate parameter values
        param_values = []
        for scenario in scenarios:
            row = [scenario[name] for name in param_names]
            param_values.append(row)

        # Generate decorator
        decorator = self.generate_parametrize_decorator(
            ", ".join(param_names),
            param_values
        )

        # Generate test function
        func_name = f"test_{function['name']}_parametrized"
        args = ", ".join(param_names)

        test_code = f"""
{decorator}
def {func_name}({args}):
    \"\"\"Test {function['name']} with multiple scenarios.\"\"\"
    # TODO: Implement test logic
    pass
"""

        return test_code.strip()

    def generate_test_cases_matrix(
        self,
        parameters: Dict[str, List[Any]],
        outcome_template: str
    ) -> List[Dict[str, Any]]:
        """
        Generate test case matrix from parameter combinations.

        Creates cartesian product of all parameter values.

        Args:
            parameters: Dict of parameter names to value lists
            outcome_template: Template string for expected outcome

        Returns:
            List of test case dictionaries

        Example:
            parameters = {"provider": ["google", "github"], "scope": ["read", "write"]}
            -> Returns 4 combinations: (google, read), (google, write), (github, read), (github, write)
        """
        param_names = list(parameters.keys())
        param_values = [parameters[name] for name in param_names]

        test_cases = []
        for combination in product(*param_values):
            case = dict(zip(param_names, combination))
            test_cases.append(case)

        return test_cases

    def generate_idfn(
        self,
        parameters: Dict[str, Any]
    ) -> str:
        """
        Generate idfn for parametrized test names.

        Creates readable test case IDs for pytest output.

        Args:
            parameters: Single parameter combination

        Returns:
            Readable test ID string

        Example:
            {"provider": "google", "scope": "read"} -> "google-read"
        """
        parts = []
        for key, value in parameters.items():
            parts.append(f"{key}-{value}")

        return "-".join(parts)

    def generate_parametrize_decorator(
        self,
        param_names: str,
        param_values: List[List[Any]]
    ) -> str:
        """
        Generate @pytest.mark.parametrize decorator code.

        Args:
            param_names: Comma-separated parameter names
            param_values: List of parameter value tuples

        Returns:
            Decorator code as string
        """
        # Format parameter values as Python list
        formatted_values = []
        for row in param_values:
            formatted_row = []
            for value in row:
                if isinstance(value, str):
                    formatted_row.append(f'"{value}"')
                elif value is None:
                    formatted_row.append("None")
                elif value is True:
                    formatted_row.append("True")
                elif value is False:
                    formatted_row.append("False")
                else:
                    formatted_row.append(str(value))
            formatted_values.append(f"({', '.join(formatted_row)})")

        values_str = f"[{', '.join(formatted_values)}]"

        return f'@pytest.mark.parametrize("{param_names}", {values_str})'


# ============================================================================
# Task 3: Hypothesis Property-Based Test Generator
# ============================================================================

class PropertyBasedTestGenerator:
    """
    Generate Hypothesis property-based tests.

    Creates property-based tests using hypothesis.strategies for
    comprehensive edge case and invariant testing.

    Example:
        generator = PropertyBasedTestGenerator()
        test_code = generator.generate_property_test(function, invariants)
    """

    def generate_property_test(
        self,
        function: Dict[str, Any],
        invariants: List[str]
    ) -> str:
        """
        Generate property-based test using Hypothesis.

        Args:
            function: Function metadata
            invariants: List of property invariants to test

        Returns:
            Property test code as string

        Example output:
            ```python
            from hypothesis import given, strategies as st

            @given(st.text(min_size=1), st.text(min_size=1))
            def test_user_creation(name, email):
                user = User(name=name, email=email)
                assert user.name == name
                assert user.email == email
                assert user.id is not None  # Auto-generated
            ```
        """
        if not function.get("args"):
            return ""

        # Generate strategies for each argument
        strategies = []
        for arg in function["args"]:
            strategy = self.infer_strategy(arg, {})
            strategies.append(strategy)

        # Generate test code
        func_name = f"test_{function['name']}_property"
        args_str = ", ".join(function["args"])
        strategies_str = ", ".join(strategies)
        given_decorator = f"@given({strategies_str})"

        # Generate invariant assertions
        assertions = []
        for invariant in invariants:
            assertions.append(f"    # {invariant}")

        if not assertions:
            assertions.append("    # TODO: Add property invariants")

        test_code = f"""
from hypothesis import given, strategies as st

{given_decorator}
def {func_name}({args_str}):
    \"\"\"Property-based test for {function['name']}.\"\"\"
{chr(10).join(assertions)}
"""

        return test_code.strip()

    def infer_strategy(
        self,
        param_type: str,
        constraints: Dict[str, Any]
    ) -> str:
        """
        Infer Hypothesis strategy from parameter type.

        Args:
            param_type: Parameter name or type hint
            constraints: Additional constraints (min_length, etc.)

        Returns:
            Strategy code as string

        Mapping:
        - str/email -> st.email() or st.text()
        - int/id -> st.integers()
        - float/amount -> st.floats()
        - bool/enabled -> st.booleans()
        - List/items -> st.lists()
        - Dict/data -> st.dictionaries()
        """
        param_lower = param_type.lower()

        # String types
        if "email" in param_lower:
            return "st.email()"
        elif "name" in param_lower or "text" in param_lower:
            min_size = constraints.get("min_length", 1)
            return f"st.text(min_size={min_size})"
        elif "url" in param_lower:
            return "st.url()"
        elif "uuid" in param_lower or "id" in param_lower:
            return "st.uuid()"

        # Numeric types
        elif "count" in param_lower or "num" in param_lower:
            min_val = constraints.get("min", 0)
            return f"st.integers(min_value={min_val})"
        elif "amount" in param_lower or "price" in param_lower:
            return "st.floats(min_value=0, allow_infinity=False, allow_nan=False)"
        elif "rate" in param_lower or "ratio" in param_lower:
            return "st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)"

        # Boolean types
        elif "enabled" in param_lower or "disabled" in param_lower or "is_" in param_lower:
            return "st.booleans()"

        # Collection types
        elif "ids" in param_lower or "items" in param_lower or "list" in param_lower:
            return "st.lists(st.uuid())"
        elif "data" in param_lower or "dict" in param_lower or "config" in param_lower:
            return "st.dictionaries(st.text(), st.text())"

        # Default: text
        else:
            return "st.text()"

    def generate_property_test_invariants(
        self,
        function: Dict[str, Any]
    ) -> List[str]:
        """
        Generate property invariants for function.

        Args:
            function: Function metadata

        Returns:
            List of invariant descriptions

        Common invariants:
        - Idempotency: f(f(x)) == f(x)
        - Commutativity: f(a, b) == f(b, a)
        - Identity: f(x, identity) == x
        - Round-trip: decode(encode(x)) == x
        """
        invariants = []
        func_name = function["name"].lower()

        # Detect idempotency invariants
        if "update" in func_name or "set" in func_name or "add" in func_name:
            invariants.append("Idempotency: Calling twice with same input should have same effect")

        # Detect commutativity invariants
        if "merge" in func_name or "combine" in func_name:
            invariants.append("Commutativity: Order of arguments should not matter")

        # Detect identity invariants
        if "delete" in func_name or "remove" in func_name:
            invariants.append("Identity: Deleting non-existent should be safe")

        # Detect round-trip invariants
        if "encode" in func_name or "decode" in func_name or "parse" in func_name:
            invariants.append("Round-trip: decode(encode(x)) == x")

        # Default invariants
        if not invariants:
            invariants.append("Output should match expected type")
            invariants.append("Function should not raise exceptions for valid input")

        return invariants

    def generate_property_test_code(
        self,
        function_name: str,
        strategies: List[str],
        invariants: List[str]
    ) -> str:
        """
        Generate complete property test code.

        Combines strategies and invariants into test.

        Args:
            function_name: Name of function to test
            strategies: List of hypothesis strategies
            invariants: List of invariant assertions

        Returns:
            Complete property test code
        """
        # Extract argument names from strategies (simplified)
        args = [f"arg{i}" for i in range(len(strategies))]

        test_code = f"""
from hypothesis import given, strategies as st

@given({', '.join(strategies)})
def test_{function_name}_properties({', '.join(args)}):
    \"\"\"
    Property-based test for {function_name}.

    Invariants:
    {chr(10).join(f'    - {inv}' for inv in invariants)}
    \"\"\"
    # TODO: Implement property checks
    result = {function_name}({', '.join(args)})

    # Add invariant assertions here
    # assert result is not None
"""

        return test_code.strip()


# ============================================================================
# Task 4: Fixture Generator for Database and API
# ============================================================================

class FixtureGenerator:
    """
    Generate pytest fixtures for database and API mocking.

    Creates reusable fixtures following Atom's test patterns.

    Example:
        generator = FixtureGenerator()
        fixture_code = generator.generate_db_fixture(["User", "OAuthToken"])
    """

    def generate_db_fixture(
        self,
        models: List[str]
    ) -> str:
        """
        Generate database session fixture.

        Args:
            models: List of model names to import

        Returns:
            Database fixture code

        Example output:
            ```python
            @pytest.fixture
            def db_session():
                \"\"\"Create test database session with rollback.\"\"\"
                from core.database import SessionLocal, Base
                from core.models import OAuthService, User

                engine = create_engine("sqlite:///:memory:")
                Base.metadata.create_all(engine)
                Session = sessionmaker(bind=engine)

                session = Session()
                try:
                    yield session
                finally:
                    session.rollback()
                    session.close()
            ```
        """
        imports = ", ".join([f'"{m}"' for m in models])

        fixture_code = f"""
@pytest.fixture
def db_session():
    \"\"\"
    Create test database session with automatic rollback.

    Provides a clean database state for each test.
    Changes are rolled back after test completion.
    \"\"\"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    from core.models import {imports}

    # Use in-memory SQLite for fast isolated tests
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
"""

        return fixture_code.strip()

    def generate_mock_fixture(
        self,
        external_service: str,
        methods: List[str]
    ) -> str:
        """
        Generate mock fixture for external service.

        Args:
            external_service: Name of service being mocked
            methods: List of method names to mock

        Returns:
            Mock fixture code

        Example for OAuth provider:
            ```python
            @pytest.fixture
            def mock_oauth_provider(monkeypatch):
                async def mock_exchange(*args, **kwargs):
                    return {"access_token": "test_token", "expires_in": 3600}
                monkeypatch.setattr(OAuthService, "exchange_code", mock_exchange)
            ```
        """
        service_name = external_service.replace(" ", "_").lower()

        # Generate mock methods
        mock_methods = []
        for method in methods:
            mock_method = f"""
    async def mock_{method}(*args, **kwargs):
        return {{"{method}": "mock_response"}}
"""
            mock_methods.append(mock_method.strip())

        fixture_code = f"""
@pytest.fixture
def mock_{service_name}(monkeypatch):
    \"\"\"
    Mock {external_service} for testing.

    Prevents actual API calls during tests.
    \"\"\"
    from unittest.mock import AsyncMock

{chr(10).join(mock_methods)}

    # Apply mocks
    # TODO: Update with actual service import
    # monkeypatch.setattr({external_service}, "{methods[0]}", mock_{methods[0]})

    return {{
{chr(10).join(f'        "{m}": mock_{m},' for m in methods)}
    }}
"""

        return fixture_code.strip()

    def generate_test_data_factory(
        self,
        model: Dict[str, Any]
    ) -> str:
        """
        Generate test data factory for model.

        Uses factory_boy patterns if available, otherwise simple fixture.

        Args:
            model: Model schema with field definitions

        Returns:
            Factory fixture code
        """
        model_name = model.get("name", "Model")
        fields = model.get("fields", {})

        # Generate factory attributes
        factory_attrs = []
        for field_name, field_type in fields.items():
            if "email" in field_name.lower():
                factory_attrs.append(f'        {field_name}="test@example.com"')
            elif "name" in field_name.lower():
                factory_attrs.append(f'        {field_name}="Test {field_name}"')
            elif "id" in field_name.lower():
                factory_attrs.append(f'        {field_name}=uuid.uuid4()')
            elif "enabled" in field_name.lower() or "active" in field_name.lower():
                factory_attrs.append(f'        {field_name}=True')
            else:
                factory_attrs.append(f'        {field_name}=None')

        fixture_code = f"""
@pytest.fixture
def {model_name.lower()}_factory(db_session):
    \"\"\"
    Factory for creating test {model_name} instances.

    Usage:
        def test_something({model_name.lower()}_factory):
            item = {model_name.lower()}_factory()
    \"\"\"
    import uuid
    from core.models import {model_name}

    def create(**kwargs):
        defaults = {{
{chr(10).join(factory_attrs)}
        }}
        defaults.update(kwargs)

        item = {model_name}(**defaults)
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        return item

    return create
"""

        return fixture_code.strip()

    def generate_api_client_fixture(
        self,
        routes: List[str]
    ) -> str:
        """
        Generate FastAPI TestClient fixture.

        Args:
            routes: List of route prefixes to test

        Returns:
            API client fixture code

        Example:
            ```python
            @pytest.fixture
            def api_client():
                from fastapi.testclient import TestClient
                from main import app
                return TestClient(app)
            ```
        """
        routes_str = ", ".join([f'"{r}"' for r in routes])

        fixture_code = f"""
@pytest.fixture
def api_client():
    \"\"\"
    FastAPI TestClient for API testing.

    Provides a test client that can make HTTP requests
    to the application without running a server.

    Routes: {routes_str}
    \"\"\"
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


@pytest.fixture
def authenticated_api_client(api_client, db_session):
    \"\"\"
    Authenticated API client for testing protected endpoints.

    Creates a test user and returns client with auth headers.
    \"\"\"
    import uuid
    from core.models import User

    # Create test user
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        name="Test User"
    )
    db_session.add(user)
    db_session.commit()

    # Add auth header
    api_client.headers.update({
        "Authorization": f"Bearer test-token-{user.id}"
    })

    return api_client
"""

        return fixture_code.strip()


# ============================================================================
# Task 5: Coverage Analyzer and Gap Detector
# ============================================================================

class CoverageAnalyzer:
    """
    Analyze coverage and identify test gaps.

    Runs pytest-cov and parses coverage reports to identify
    uncovered lines and branches for targeted test generation.

    Attributes:
        project_root: Root directory for coverage analysis

    Example:
        analyzer = CoverageAnalyzer("backend")
        coverage = await analyzer.analyze_coverage("core/service.py", "tests/test_service.py")
    """

    def __init__(self, project_root: str = "backend"):
        """
        Initialize coverage analyzer.

        Args:
            project_root: Root directory for source code
        """
        self.project_root = Path(project_root)

    async def analyze_coverage(
        self,
        source_file: str,
        test_file: str
    ) -> Dict[str, Any]:
        """
        Run coverage analysis and identify gaps.

        Args:
            source_file: Path to source file
            test_file: Path to test file

        Returns:
            {
                "coverage_percent": float,
                "covered_lines": [int],
                "uncovered_lines": [int],
                "missing_branches": [str],
                "suggested_tests": [
                    {"line": int, "reason": str, "test_name": str}
                ]
            }
        """
        # Run pytest with coverage
        coverage_data = await self.run_coverage_report([test_file])

        if not coverage_data:
            return {
                "coverage_percent": 0.0,
                "covered_lines": [],
                "uncovered_lines": [],
                "missing_branches": [],
                "suggested_tests": []
            }

        # Extract coverage for specific source file
        source_path = str(source_file)
        file_coverage = coverage_data.get("files", {}).get(source_path, {})

        covered_lines = file_coverage.get("executed_lines", [])
        uncovered_lines = file_coverage.get("missing_lines", [])
        summary = file_coverage.get("summary", {})

        coverage_percent = summary.get("percent_covered", 0.0)

        # Identify missing branches
        missing_branches = self._identify_missing_branches(file_coverage)

        # Generate suggested tests
        suggested_tests = self.generate_coverage_target_tests([
            {"line": line, "covered": False} for line in uncovered_lines
        ])

        return {
            "coverage_percent": coverage_percent,
            "covered_lines": covered_lines,
            "uncovered_lines": uncovered_lines,
            "missing_branches": missing_branches,
            "suggested_tests": suggested_tests
        }

    def generate_coverage_target_tests(
        self,
        coverage_gaps: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate tests to fill coverage gaps.

        Creates tests for uncovered branches and lines.

        Args:
            coverage_gaps: List of uncovered lines/branches

        Returns:
            List of test suggestions

        Example:
            [
                "test_line_45 handles empty list case",
                "test_line_78 handles connection error"
            ]
        """
        suggestions = []

        for gap in coverage_gaps:
            line = gap.get("line", 0)

            # Infer test scenario from line number
            if line < 20:
                scenario = "initialization/setup"
            elif line < 50:
                scenario = "input validation"
            elif line < 100:
                scenario = "main logic"
            else:
                scenario = "edge case or error handling"

            suggestions.append(
                f"test_line_{line}_{scenario.replace(' ', '_')}"
            )

        return suggestions

    def estimate_coverage_from_tests(
        self,
        test_cases: List[Dict[str, Any]]
    ) -> float:
        """
        Estimate coverage from test case count.

        Heuristic: Each test covers ~10-15 lines on average.
        Adjusts based on test complexity.

        Args:
            test_cases: List of test case metadata

        Returns:
            Estimated coverage percentage
        """
        if not test_cases:
            return 0.0

        # Count total test cases
        total_tests = len(test_cases)

        # Estimate lines covered (10-15 per test)
        min_lines = total_tests * 10
        max_lines = total_tests * 15

        # Assume average file is ~200 lines
        avg_file_lines = 200

        # Calculate coverage percentage
        min_coverage = (min_lines / avg_file_lines) * 100
        max_coverage = (max_lines / avg_file_lines) * 100

        # Return average
        return (min_coverage + max_coverage) / 2

    async def run_coverage_report(
        self,
        test_files: List[str]
    ) -> Dict[str, Any]:
        """
        Run pytest with coverage and parse results.

        Executes: pytest --cov=source --cov-report=json
        Returns parsed coverage.json content.

        Args:
            test_files: List of test files to run

        Returns:
            Parsed coverage data from coverage.json
        """
        try:
            # Run pytest with coverage
            cmd = [
                "pytest",
                *test_files,
                "--cov=.",
                "--cov-report=json",
                "--cov-report=term",
                "-v"
            ]

            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.warning(f"Coverage run failed: {result.stderr}")
                return {}

            # Parse coverage.json
            coverage_file = self.project_root / "coverage.json"
            if not coverage_file.exists():
                logger.warning("coverage.json not generated")
                return {}

            with open(coverage_file, 'r') as f:
                coverage_data = json.load(f)

            return coverage_data

        except subprocess.TimeoutExpired:
            logger.error("Coverage run timed out")
            return {}
        except Exception as e:
            logger.error(f"Error running coverage: {e}")
            return {}

    def check_coverage_target_met(
        self,
        coverage_percent: float,
        target_type: str  # "unit", "integration", or "e2e"
    ) -> bool:
        """
        Check if coverage meets target for given type.

        Args:
            coverage_percent: Current coverage percentage
            target_type: 'unit', 'integration', or 'e2e'

        Returns:
            True if target met, False otherwise

        Targets:
        - Unit tests: 85%
        - Integration tests: 70%
        - E2E tests: 60%
        """
        if target_type == "unit":
            return coverage_percent >= COVERAGE_TARGET_UNIT
        elif target_type == "integration":
            return coverage_percent >= COVERAGE_TARGET_INTEGRATION
        elif target_type == "e2e":
            return coverage_percent >= COVERAGE_TARGET_E2E
        else:
            # Unknown target type, use conservative 80%
            return coverage_percent >= 80.0

    def _identify_missing_branches(
        self,
        file_coverage: Dict[str, Any]
    ) -> List[str]:
        """Identify missing branches from coverage data."""
        missing_branches = []

        # Check for partial branch coverage
        branches = file_coverage.get("missing_branches", {})
        for line, branches_missing in branches.items():
            for branch in branches_missing:
                missing_branches.append(f"Line {line}: {branch}")

        return missing_branches


# ============================================================================
# Task 6: Main TestGeneratorService Orchestration
# ============================================================================

class TestGeneratorService:
    """
    Main service for automated test generation.

    Orchestrates all test generation components:
    - Structure generation
    - Parametrized tests
    - Property-based tests
    - Fixtures
    - Coverage analysis

    Attributes:
        db: Database session
        byok_handler: BYOK handler for LLM access
        structure_generator: Test file structure generator
        parametrized_generator: Parametrized test generator
        property_generator: Property-based test generator
        fixture_generator: Fixture generator
        coverage_analyzer: Coverage analyzer

    Example:
        service = TestGeneratorService(db, byok_handler)
        result = await service.generate_tests(
            ["core/oauth_service.py"],
            implementation_context
        )
    """

    def __init__(
        self,
        db: Session,
        byok_handler: BYOKHandler
    ):
        """
        Initialize test generator service.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
        """
        self.db = db
        self.byok_handler = byok_handler
        self.structure_generator = TestFileStructureGenerator()
        self.parametrized_generator = ParametrizedTestGenerator()
        self.property_generator = PropertyBasedTestGenerator()
        self.fixture_generator = FixtureGenerator()
        self.coverage_analyzer = CoverageAnalyzer()

    async def generate_tests(
        self,
        source_files: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete test suite for source files.

        Args:
            source_files: List of source file paths
            context: Implementation context from coder agent

        Returns:
            {
                "test_files": [
                    {"path": str, "code": str, "estimated_coverage": float}
                ],
                "fixtures": [{"name": str, "code": str}],
                "total_estimated_coverage": float,
                "test_count": int
            }
        """
        test_files = []
        all_fixtures = []
        total_test_count = 0

        for source_file in source_files:
            # Generate test file structure
            structure = self.structure_generator.generate_test_file_structure(
                source_file
            )

            if not structure:
                logger.warning(f"Could not generate structure for {source_file}")
                continue

            # Generate fixtures
            fixtures = self._generate_fixtures_for_structure(structure)
            all_fixtures.extend(fixtures)

            # Generate test cases
            test_cases = self._generate_test_cases_for_structure(
                structure,
                context
            )

            # Assemble test file
            test_file_content = self.generate_test_file_content(
                structure,
                [f["name"] for f in fixtures],
                test_cases
            )

            # Estimate coverage
            estimated_coverage = self.coverage_analyzer.estimate_coverage_from_tests(
                test_cases
            )

            test_files.append({
                "path": structure["test_file_path"],
                "code": test_file_content,
                "estimated_coverage": estimated_coverage,
                "test_count": len(test_cases)
            })

            total_test_count += len(test_cases)

        # Calculate total estimated coverage
        total_estimated_coverage = sum(
            tf["estimated_coverage"] for tf in test_files
        ) / max(len(test_files), 1)

        return {
            "test_files": test_files,
            "fixtures": all_fixtures,
            "total_estimated_coverage": total_estimated_coverage,
            "test_count": total_test_count
        }

    async def generate_tests_for_task(
        self,
        task: ImplementationTask,
        generated_code: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Generate tests for a single implementation task.

        Analyzes generated code and creates comprehensive tests.

        Args:
            task: Implementation task
            generated_code: Dict of file paths to generated code

        Returns:
            Test generation result with files and coverage info
        """
        source_files = list(generated_code.keys())

        context = {
            "task_id": task.id,
            "task_name": task.name,
            "description": task.description
        }

        return await self.generate_tests(source_files, context)

    def generate_test_file_content(
        self,
        structure: Dict[str, Any],
        fixtures: List[str],
        test_cases: List[str]
    ) -> str:
        """
        Assemble complete test file content.

        Combines imports, fixtures, test cases into file.

        Args:
            structure: Test file structure metadata
            fixtures: List of fixture names to include
            test_cases: List of test case code strings

        Returns:
            Complete test file content
        """
        lines = []

        # Add file docstring
        lines.append(f'"""')
        lines.append(f'Tests for {structure["source_file"]}')
        lines.append(f'"""')
        lines.append("")

        # Add imports
        lines.append("import pytest")
        lines.append("from unittest.mock import Mock, AsyncMock")
        lines.append("")

        # Add module imports
        if structure["source_file"].startswith("core/"):
            module_name = structure["source_file"].replace("/", ".").replace(".py", "")
            lines.append(f"from {module_name} import *")
            lines.append("")

        # Add test class
        if structure["test_class_name"]:
            lines.append(f"class {structure['test_class_name']}:")
            lines.append(f'    """Test {structure["source_file"]}."""')
            lines.append("")

            # Indent test cases
            for test_case in test_cases:
                for line in test_case.split("\n"):
                    lines.append(f"    {line}")
                lines.append("")
        else:
            # Module-level tests
            for test_case in test_cases:
                lines.append(test_case)
                lines.append("")

        return "\n".join(lines)

    async def generate_until_coverage_target(
        self,
        source_file: str,
        target_coverage: float = 0.85
    ) -> Dict[str, Any]:
        """
        Generate tests iteratively until coverage target met.

        Loop:
        1. Generate initial tests
        2. Run coverage
        3. Identify gaps
        4. Generate targeted tests for gaps
        5. Repeat until target met or max iterations (5)

        Args:
            source_file: Source file to test
            target_coverage: Target coverage percentage (0.0-1.0)

        Returns:
            Final test suite and coverage achieved
        """
        max_iterations = 5
        all_tests = []

        for iteration in range(max_iterations):
            # Generate tests for current iteration
            if iteration == 0:
                result = await self.generate_tests(
                    [source_file],
                    {"iteration": iteration}
                )
            else:
                # Generate targeted tests for coverage gaps
                result = await self._generate_gap_filling_tests(
                    source_file,
                    result["coverage_gaps"]
                )

            all_tests.extend(result.get("test_files", []))

            # Run coverage analysis
            test_file = result["test_files"][0]["path"]
            coverage_data = await self.coverage_analyzer.analyze_coverage(
                source_file,
                test_file
            )

            current_coverage = coverage_data.get("coverage_percent", 0.0)

            # Check if target met
            if current_coverage >= target_coverage * 100:
                logger.info(f"Target coverage {target_coverage*100}% reached in iteration {iteration+1}")
                break

            # Store coverage gaps for next iteration
            result["coverage_gaps"] = coverage_data.get("suggested_tests", [])

        return {
            "test_files": all_tests,
            "final_coverage": coverage_data.get("coverage_percent", 0.0),
            "target_met": coverage_data.get("coverage_percent", 0.0) >= target_coverage * 100,
            "iterations": iteration + 1
        }

    async def refine_tests_with_llm(
        self,
        generated_tests: str,
        source_code: str
    ) -> str:
        """
        Use LLM to refine and improve generated tests.

        Ask LLM to review for edge cases and missing scenarios.

        Args:
            generated_tests: Generated test code
            source_code: Source code being tested

        Returns:
            Refined test code
        """
        prompt = f"""Review and improve these pytest tests:

Generated Tests:
{generated_tests}

Source Code:
{source_code}

Task:
1. Identify missing edge cases
2. Add assertions for error conditions
3. Improve test descriptions
4. Add parametrized tests where appropriate
5. Ensure all tests follow pytest best practices

Return only the improved test code, no explanations.
"""

        try:
            response = await self.byok_handler.stream_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4",
                temperature=0.0
            )

            # Extract LLM response
            refined_tests = ""
            async for chunk in response:
                if "choices" in chunk and chunk["choices"]:
                    refined_tests += chunk["choices"][0].get("content", "")

            return refined_tests or generated_tests

        except Exception as e:
            logger.error(f"LLM refinement failed: {e}")
            return generated_tests

    def _generate_fixtures_for_structure(
        self,
        structure: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate fixtures needed for test structure."""
        fixtures = []

        for fixture_name in structure.get("fixtures_needed", []):
            if fixture_name == "db_session":
                code = self.fixture_generator.generate_db_fixture(
                    [cls["name"] for cls in structure["classes_to_test"]]
                )
                fixtures.append({"name": fixture_name, "code": code})

            elif fixture_name == "api_client":
                code = self.fixture_generator.generate_api_client_fixture([])
                fixtures.append({"name": fixture_name, "code": code})

        return fixtures

    def _generate_test_cases_for_structure(
        self,
        structure: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate test cases for structure."""
        test_cases = []

        # Generate tests for functions
        for func in structure["functions_to_test"]:
            inferred = self.structure_generator.infer_test_cases(func)
            for test_case in inferred:
                test_cases.append(f'def {test_case["name"]}():\n    """{test_case["scenario"]}"""\n    pass')

        # Generate tests for class methods
        for cls in structure["classes_to_test"]:
            for method in cls["methods"]:
                inferred = self.structure_generator.infer_test_cases(method)
                for test_case in inferred:
                    test_name = f'test_{cls["name"].lower()}_{test_case["name"]}'
                    test_cases.append(f'def {test_name}():\n    """{test_case["scenario"]}"""\n    pass')

        return test_cases

    async def _generate_gap_filling_tests(
        self,
        source_file: str,
        coverage_gaps: List[str]
    ) -> Dict[str, Any]:
        """Generate targeted tests to fill coverage gaps."""
        # Simplified implementation
        test_cases = [f"def {gap}():\n    pass" for gap in coverage_gaps]

        return {
            "test_files": [{
                "path": f"tests/{Path(source_file).stem}_gap_filling.py",
                "code": "\n".join(test_cases),
                "estimated_coverage": 10.0
            }],
            "coverage_gaps": coverage_gaps
        }
