"""
Comprehensive tests for TestGeneratorService.

Tests cover:
- TestFileStructureGenerator (structure extraction, test inference)
- ParametrizedTestGenerator (parametrize decorators, combinatorial testing)
- PropertyBasedTestGenerator (Hypothesis strategies, invariants)
- FixtureGenerator (database, API, mock fixtures)
- CoverageAnalyzer (coverage analysis, gap detection)
- TestGeneratorService (orchestration, iterative generation)

Coverage target: >= 80% for TestGeneratorService
"""

import ast
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from pathlib import Path
from sqlalchemy.orm import Session

from core.test_generator_service import (
    TestFileStructureGenerator,
    ParametrizedTestGenerator,
    PropertyBasedTestGenerator,
    FixtureGenerator,
    CoverageAnalyzer,
    TestGeneratorService,
    TestType,
)
from core.autonomous_planning_agent import ImplementationTask, TaskComplexity, AgentType


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
    handler = Mock()
    handler.stream_completion = AsyncMock()
    return handler


@pytest.fixture
def test_generator_service(db_session, mock_byok_handler):
    """Create TestGeneratorService instance."""
    return TestGeneratorService(db_session, mock_byok_handler)


@pytest.fixture
def sample_source_code():
    """Sample Python code for testing."""
    return """
def create_user(name: str, email: str) -> str:
    '''Create a new user.'''
    if not name or not email:
        raise ValueError("Name and email required")
    user_id = generate_id()
    save_user(user_id, name, email)
    return user_id

def get_user(user_id: str) -> dict:
    '''Get user by ID.'''
    return fetch_user(user_id)

class UserService:
    def update_user(self, user_id: str, data: dict) -> bool:
        '''Update user data.'''
        return update_in_db(user_id, data)

    def delete_user(self, user_id: str) -> bool:
        '''Delete user.'''
        return delete_from_db(user_id)
"""


@pytest.fixture
def implementation_task():
    """Sample implementation task."""
    return ImplementationTask(
        id="task-001",
        name="Create OAuth Service",
        agent_type=AgentType.CODER_BACKEND,
        description="Implement OAuth authentication",
        dependencies=[],
        files_to_create=["core/oauth_service.py"],
        files_to_modify=[],
        estimated_time_minutes=60,
        complexity=TaskComplexity.MODERATE,
        can_parallelize=False
    )


# ============================================================================
# TestFileStructureGenerator Tests
# ============================================================================

class TestTestFileStructureGenerator:
    """Test test file structure generation."""

    @pytest.fixture
    def generator(self):
        """Create structure generator."""
        return TestFileStructureGenerator("backend")

    def test_extract_functions_from_source(self, generator, sample_source_code):
        """Test extracting functions from source code."""
        items = generator.extract_testable_items(sample_source_code)

        assert "functions" in items
        assert len(items["functions"]) == 2
        assert items["functions"][0]["name"] == "create_user"
        assert items["functions"][0]["args"] == ["name", "email", "user_id"]
        assert items["functions"][1]["name"] == "get_user"
        assert items["functions"][1]["args"] == ["user_id"]

    def test_extract_classes_from_source(self, generator, sample_source_code):
        """Test extracting classes from source code."""
        items = generator.extract_testable_items(sample_source_code)

        assert "classes" in items
        assert len(items["classes"]) == 1
        assert items["classes"][0]["name"] == "UserService"
        assert len(items["classes"][0]["methods"]) == 2
        assert items["classes"][0]["methods"][0]["name"] == "update_user"
        assert items["classes"][0]["methods"][1]["name"] == "delete_user"

    def test_infer_test_cases_for_create_function(self, generator):
        """Test inferring test cases for create function."""
        function = {"name": "create_user", "args": ["name", "email"]}

        test_cases = generator.infer_test_cases(function)

        assert len(test_cases) == 3
        assert test_cases[0]["name"] == "test_create_user_success"
        assert test_cases[0]["scenario"] == "Valid input"
        assert test_cases[1]["name"] == "test_create_user_duplicate"
        assert test_cases[2]["name"] == "test_create_user_invalid"

    def test_infer_test_cases_for_get_function(self, generator):
        """Test inferring test cases for get function."""
        function = {"name": "get_user", "args": ["user_id"]}

        test_cases = generator.infer_test_cases(function)

        assert len(test_cases) == 3
        assert "test_get_user_found" in [t["name"] for t in test_cases]
        assert "test_get_user_not_found" in [t["name"] for t in test_cases]

    def test_infer_test_cases_for_update_function(self, generator):
        """Test inferring test cases for update function."""
        function = {"name": "update_user", "args": ["user_id", "data"]}

        test_cases = generator.infer_test_cases(function)

        assert len(test_cases) >= 2
        assert any("update" in t["name"] for t in test_cases)

    def test_infer_test_cases_for_delete_function(self, generator):
        """Test inferring test cases for delete function."""
        function = {"name": "delete_user", "args": ["user_id"]}

        test_cases = generator.infer_test_cases(function)

        assert len(test_cases) >= 2
        assert any("delete" in t["name"] for t in test_cases)

    def test_suggest_test_name_convention(self, generator):
        """Test test name follows Atom conventions."""
        test_name = generator.suggest_test_name("login", "success case")

        assert test_name == "test_login_success_case"

    def test_suggest_test_name_with_spaces(self, generator):
        """Test test name with spaces is converted."""
        test_name = generator.suggest_test_name("fetch_data", "Invalid JSON format")

        assert test_name == "test_fetch_data_invalid_json_format"

    def test_infer_test_file_path_core_module(self, generator):
        """Test inferring test file path for core module."""
        structure = generator.generate_test_file_structure("core/oauth_service.py")

        assert "test_file_path" in structure
        assert "test_oauth_service.py" in structure["test_file_path"]

    def test_infer_test_class_name(self, generator):
        """Test inferring test class name."""
        class_name = generator._infer_test_class_name("core/oauth_service.py")

        assert class_name == "TestOauthService"

    def test_infer_fixtures_needed_database_operations(self, generator):
        """Test inferring database fixtures."""
        functions = [{"name": "save_user", "args": ["db_session", "data"]}]
        classes = []

        fixtures = generator._infer_fixtures_needed(functions, classes)

        assert "db_session" in fixtures

    def test_infer_fixtures_needed_api_operations(self, generator):
        """Test inferring API fixtures."""
        functions = [{"name": "handle_request", "args": ["request", "response"]}]
        classes = []

        fixtures = generator._infer_fixtures_needed(functions, classes)

        assert "api_client" in fixtures

    def test_infer_fixtures_needed_none(self, generator):
        """Test no fixtures needed for simple functions."""
        functions = [{"name": "calculate_total", "args": ["items"]}]
        classes = []

        fixtures = generator._infer_fixtures_needed(functions, classes)

        assert len(fixtures) == 0


# ============================================================================
# ParametrizedTestGenerator Tests
# ============================================================================

class TestParametrizedTestGenerator:
    """Test parametrized test generation."""

    @pytest.fixture
    def generator(self):
        """Create parametrized test generator."""
        return ParametrizedTestGenerator()

    def test_generate_parametrized_test_oauth_providers(self, generator):
        """Test generating parametrized test for OAuth providers."""
        function = {"name": "get_authorization_url", "args": ["provider"]}
        scenarios = [
            {"provider": "google", "expected_url": "https://accounts.google.com/o/oauth2"},
            {"provider": "github", "expected_url": "https://github.com/login/oauth"},
            {"provider": "microsoft", "expected_url": "https://login.microsoftonline.com"}
        ]

        test_code = generator.generate_parametrized_test(function, scenarios)

        assert "@pytest.mark.parametrize" in test_code
        assert "provider,expected_url" in test_code
        assert "test_get_authorization_url_parametrized" in test_code
        assert '"google"' in test_code
        assert '"github"' in test_code
        assert '"microsoft"' in test_code

    def test_generate_test_cases_matrix_cartesian_product(self, generator):
        """Test generating test case matrix (cartesian product)."""
        parameters = {
            "provider": ["google", "github"],
            "scope": ["read", "write"]
        }

        test_cases = generator.generate_test_cases_matrix(
            parameters,
            "Expected outcome"
        )

        assert len(test_cases) == 4  # 2 providers * 2 scopes
        assert test_cases[0] == {"provider": "google", "scope": "read"}
        assert test_cases[3] == {"provider": "github", "scope": "write"}

    def test_generate_test_cases_matrix_single_parameter(self, generator):
        """Test generating matrix with single parameter."""
        parameters = {"status": ["active", "inactive", "pending"]}

        test_cases = generator.generate_test_cases_matrix(parameters, "status")

        assert len(test_cases) == 3
        assert test_cases[0]["status"] == "active"
        assert test_cases[1]["status"] == "inactive"
        assert test_cases[2]["status"] == "pending"

    def test_generate_idfn_readable_names(self, generator):
        """Test generating readable test IDs."""
        parameters = {"provider": "google", "scope": "read"}

        test_id = generator.generate_idfn(parameters)

        assert test_id == "provider-google-scope-read"

    def test_generate_parametrize_decorator(self, generator):
        """Test generating parametrize decorator."""
        param_names = "provider,scope"
        param_values = [
            ["google", "read"],
            ["github", "write"]
        ]

        decorator = generator.generate_parametrize_decorator(param_names, param_values)

        assert '@pytest.mark.parametrize("provider,scope"' in decorator
        assert '("google", "read")' in decorator
        assert '("github", "write")' in decorator

    def test_generate_parametrize_decorator_with_none(self, generator):
        """Test decorator with None values."""
        param_names = "value"
        param_values = [[None], [1], ["text"]]

        decorator = generator.generate_parametrize_decorator(param_names, param_values)

        assert "None" in decorator
        assert '"1"' in decorator
        assert '"text"' in decorator


# ============================================================================
# PropertyBasedTestGenerator Tests
# ============================================================================

class TestPropertyBasedTestGenerator:
    """Test property-based test generation."""

    @pytest.fixture
    def generator(self):
        """Create property-based test generator."""
        return PropertyBasedTestGenerator()

    def test_infer_strategy_for_email(self, generator):
        """Test inferring strategy for email parameter."""
        strategy = generator.infer_strategy("user_email", {})

        assert strategy == "st.email()"

    def test_infer_strategy_for_name(self, generator):
        """Test inferring strategy for name parameter."""
        strategy = generator.infer_strategy("user_name", {})

        assert "st.text(" in strategy
        assert "min_size=1" in strategy

    def test_infer_strategy_for_id(self, generator):
        """Test inferring strategy for ID parameter."""
        strategy = generator.infer_strategy("user_id", {})

        assert "st.uuid()" in strategy

    def test_infer_strategy_for_count(self, generator):
        """Test inferring strategy for count parameter."""
        strategy = generator.infer_strategy("item_count", {"min": 0})

        assert "st.integers(" in strategy
        assert "min_value=0" in strategy

    def test_infer_strategy_for_amount(self, generator):
        """Test inferring strategy for amount parameter."""
        strategy = generator.infer_strategy("total_amount", {})

        assert "st.floats(" in strategy
        assert "min_value=0" in strategy

    def test_infer_strategy_for_boolean(self, generator):
        """Test inferring strategy for boolean parameter."""
        strategy = generator.infer_strategy("is_enabled", {})

        assert strategy == "st.booleans()"

    def test_infer_strategy_for_list(self, generator):
        """Test inferring strategy for list parameter."""
        strategy = generator.infer_strategy("item_ids", {})

        assert "st.lists(" in strategy

    def test_infer_strategy_for_dict(self, generator):
        """Test inferring strategy for dict parameter."""
        strategy = generator.infer_strategy("metadata", {})

        assert "st.dictionaries(" in strategy

    def test_generate_property_invariants_for_idempotent_function(self, generator):
        """Test generating invariants for idempotent function."""
        function = {"name": "update_user_settings", "args": ["user_id", "settings"]}

        invariants = generator.generate_property_test_invariants(function)

        assert len(invariants) > 0
        assert any("Idempotency" in inv for inv in invariants)

    def test_generate_property_invariants_for_commutative_function(self, generator):
        """Test generating invariants for commutative function."""
        function = {"name": "merge_tags", "args": ["tags1", "tags2"]}

        invariants = generator.generate_property_test_invariants(function)

        assert len(invariants) > 0
        assert any("Commutativity" in inv for inv in invariants)

    def test_generate_property_invariants_for_delete_function(self, generator):
        """Test generating invariants for delete function."""
        function = {"name": "delete_cache", "args": ["cache_key"]}

        invariants = generator.generate_property_test_invariants(function)

        assert len(invariants) > 0
        assert any("Identity" in inv for inv in invariants)

    def test_generate_property_invariants_for_encode_function(self, generator):
        """Test generating invariants for encode function."""
        function = {"name": "encode_token", "args": ["data"]}

        invariants = generator.generate_property_test_invariants(function)

        assert len(invariants) > 0
        assert any("Round-trip" in inv for inv in invariants)

    def test_generate_property_test(self, generator):
        """Test generating complete property test."""
        function = {"name": "create_user", "args": ["name", "email"]}
        invariants = ["Output should match expected type", "Function should not raise"]

        test_code = generator.generate_property_test(function, invariants)

        assert "@given" in test_code
        assert "test_create_user_property" in test_code
        assert "hypothesis" in test_code.lower()

    def test_generate_property_test_code_complete(self, generator):
        """Test generating complete property test with invariants."""
        function_name = "hash_password"
        strategies = ["st.text(min_size=8)", "st.text()"]
        invariants = ["Hash should be deterministic", "Hash should be different for different inputs"]

        test_code = generator.generate_property_test_code(
            function_name,
            strategies,
            invariants
        )

        assert "@given" in test_code
        assert f"test_{function_name}_properties" in test_code
        assert "deterministic" in test_code


# ============================================================================
# FixtureGenerator Tests
# ============================================================================

class TestFixtureGenerator:
    """Test fixture generation."""

    @pytest.fixture
    def generator(self):
        """Create fixture generator."""
        return FixtureGenerator()

    def test_generate_db_fixture(self, generator):
        """Test generating database session fixture."""
        models = ["User", "OAuthToken"]

        fixture_code = generator.generate_db_fixture(models)

        assert "@pytest.fixture" in fixture_code
        assert "def db_session():" in fixture_code
        assert "sqlite:///:memory:" in fixture_code
        assert "User" in fixture_code
        assert "OAuthToken" in fixture_code
        assert "rollback()" in fixture_code

    def test_generate_mock_fixture_oauth_provider(self, generator):
        """Test generating mock fixture for OAuth provider."""
        service = "OAuthProvider"
        methods = ["exchange_code", "refresh_token"]

        fixture_code = generator.generate_mock_fixture(service, methods)

        assert "@pytest.fixture" in fixture_code
        assert "def mock_oauthprovider(" in fixture_code
        assert "async def mock_exchange_code" in fixture_code
        assert "async def mock_refresh_token" in fixture_code

    def test_generate_test_data_factory(self, generator):
        """Test generating test data factory."""
        model = {
            "name": "User",
            "fields": {
                "id": "uuid",
                "email": "email",
                "name": "str",
                "is_active": "bool"
            }
        }

        fixture_code = generator.generate_test_data_factory(model)

        assert "@pytest.fixture" in fixture_code
        assert "def user_factory(" in fixture_code
        assert "def create(**kwargs):" in fixture_code
        assert 'email="test@example.com"' in fixture_code
        assert "uuid.uuid4()" in fixture_code

    def test_generate_api_client_fixture(self, generator):
        """Test generating API client fixture."""
        routes = ["/api/auth", "/api/users"]

        fixture_code = generator.generate_api_client_fixture(routes)

        assert "@pytest.fixture" in fixture_code
        assert "def api_client():" in fixture_code
        assert "TestClient" in fixture_code
        assert "authenticated_api_client" in fixture_code
        assert "Authorization" in fixture_code


# ============================================================================
# CoverageAnalyzer Tests
# ============================================================================

class TestCoverageAnalyzer:
    """Test coverage analysis."""

    @pytest.fixture
    def generator(self):
        """Create coverage analyzer."""
        return CoverageAnalyzer("backend")

    def test_estimate_coverage_from_test_cases(self, generator):
        """Test estimating coverage from test count."""
        test_cases = [
            {"name": "test_1"},
            {"name": "test_2"},
            {"name": "test_3"},
            {"name": "test_4"},
            {"name": "test_5"}
        ]

        coverage = generator.estimate_coverage_from_tests(test_cases)

        # 5 tests * 10-15 lines = 50-75 lines / 200 avg file = 25-37.5%
        assert 20 <= coverage <= 40

    def test_estimate_coverage_no_tests(self, generator):
        """Test estimating coverage with no tests."""
        coverage = generator.estimate_coverage_from_tests([])

        assert coverage == 0.0

    def test_estimate_coverage_many_tests(self, generator):
        """Test estimating coverage with many tests."""
        # Generate 20 tests
        test_cases = [{"name": f"test_{i}"} for i in range(20)]

        coverage = generator.estimate_coverage_from_tests(test_cases)

        # 20 tests * 10-15 lines = 200-300 lines / 200 avg = 100-150% (capped at 100)
        assert coverage >= 100

    def test_check_coverage_target_met_unit(self, generator):
        """Test checking unit coverage target."""
        assert generator.check_coverage_target_met(85.0, "unit") is True
        assert generator.check_coverage_target_met(84.9, "unit") is False
        assert generator.check_coverage_target_met(90.0, "unit") is True

    def test_check_coverage_target_met_integration(self, generator):
        """Test checking integration coverage target."""
        assert generator.check_coverage_target_met(70.0, "integration") is True
        assert generator.check_coverage_target_met(69.9, "integration") is False
        assert generator.check_coverage_target_met(80.0, "integration") is True

    def test_check_coverage_target_met_default(self, generator):
        """Test checking default coverage target."""
        assert generator.check_coverage_target_met(80.0, "other") is True
        assert generator.check_coverage_target_met(79.9, "other") is False

    def test_generate_coverage_target_tests(self, generator):
        """Test generating tests for coverage gaps."""
        coverage_gaps = [
            {"line": 15, "covered": False},
            {"line": 45, "covered": False},
            {"line": 120, "covered": False}
        ]

        suggestions = generator.generate_coverage_target_tests(coverage_gaps)

        assert len(suggestions) == 3
        assert "test_line_15" in suggestions[0]
        assert "test_line_45" in suggestions[1]
        assert "test_line_120" in suggestions[2]

    @pytest.mark.asyncio
    async def test_analyze_coverage_missing_file(self, generator):
        """Test analyzing coverage for missing file."""
        result = await generator.analyze_coverage(
            "nonexistent.py",
            "tests/test_nonexistent.py"
        )

        assert result["coverage_percent"] == 0.0
        assert result["covered_lines"] == []
        assert result["uncovered_lines"] == []


# ============================================================================
# TestGeneratorService Tests
# ============================================================================

class TestTestGeneratorService:
    """Test main service orchestration."""

    @pytest.mark.asyncio
    async def test_generate_tests_empty_source_files(self, test_generator_service):
        """Test generating tests with no source files."""
        result = await test_generator_service.generate_tests([], {})

        assert result["test_files"] == []
        assert result["fixtures"] == []
        assert result["test_count"] == 0

    @pytest.mark.asyncio
    async def test_generate_tests_for_task(
        self,
        test_generator_service,
        implementation_task
    ):
        """Test generating tests for implementation task."""
        generated_code = {
            "core/oauth_service.py": """
def login(provider, code):
    '''OAuth login.'''
    return exchange_code(provider, code)

class OAuthService:
    def get_user_info(self, token):
        '''Get user info from token.'''
        return fetch_user_info(token)
"""
        }

        with patch.object(
            test_generator_service.structure_generator,
            'generate_test_file_structure'
        ) as mock_structure:
            mock_structure.return_value = {
                "test_file_path": "tests/test_oauth_service.py",
                "test_class_name": "TestOauthService",
                "functions_to_test": [{"name": "login", "args": ["provider", "code"]}],
                "classes_to_test": [],
                "fixtures_needed": [],
                "source_file": "core/oauth_service.py"
            }

            result = await test_generator_service.generate_tests_for_task(
                implementation_task,
                generated_code
            )

            assert "test_files" in result
            assert "fixtures" in result
            assert "test_count" in result

    @pytest.mark.asyncio
    async def test_generate_test_file_content(self, test_generator_service):
        """Test assembling test file content."""
        structure = {
            "test_file_path": "tests/test_service.py",
            "test_class_name": "TestService",
            "source_file": "core/service.py",
            "functions_to_test": [],
            "classes_to_test": [],
            "fixtures_needed": []
        }

        fixtures = ["db_session", "api_client"]
        test_cases = [
            "def test_login_success():\n    pass",
            "def test_login_failure():\n    pass"
        ]

        content = test_generator_service.generate_test_file_content(
            structure,
            fixtures,
            test_cases
        )

        assert "import pytest" in content
        assert "class TestService:" in content
        assert "test_login_success" in content
        assert "test_login_failure" in content

    @pytest.mark.asyncio
    async def test_refine_tests_with_llm(
        self,
        test_generator_service,
        mock_byok_handler
    ):
        """Test LLM-based test refinement."""
        generated_tests = "def test_login():\n    pass"
        source_code = "def login():\n    return True"

        # Mock LLM response
        mock_byok_handler.stream_completion = AsyncMock()
        mock_response = AsyncMock()
        mock_response.__aiter__ = Mock(return_value=iter([
            {"choices": [{"content": "def test_login():\n    assert True"}]}
        ]))
        mock_byok_handler.stream_completion.return_value = mock_response

        refined = await test_generator_service.refine_tests_with_llm(
            generated_tests,
            source_code
        )

        # Should return refined or original
        assert isinstance(refined, str)

    @pytest.mark.asyncio
    async def test_refine_tests_with_llm_error_fallback(
        self,
        test_generator_service,
        mock_byok_handler
    ):
        """Test LLM refinement falls back on error."""
        generated_tests = "def test_login():\n    pass"
        source_code = "def login():\n    return True"

        # Mock LLM error
        mock_byok_handler.stream_completion.side_effect = Exception("LLM error")

        refined = await test_generator_service.refine_tests_with_llm(
            generated_tests,
            source_code
        )

        # Should return original on error
        assert refined == generated_tests

    @pytest.mark.asyncio
    async def test_generate_until_coverage_target(
        self,
        test_generator_service
    ):
        """Test iterative test generation until coverage target."""
        # Mock coverage analysis
        with patch.object(
            test_generator_service.coverage_analyzer,
            'analyze_coverage'
        ) as mock_analyze:
            # Return increasing coverage
            mock_analyze.side_effect = [
                {"coverage_percent": 50.0, "uncovered_lines": [10, 20, 30], "suggested_tests": ["test_line_10"]},
                {"coverage_percent": 75.0, "uncovered_lines": [30], "suggested_tests": ["test_line_30"]},
                {"coverage_percent": 90.0, "uncovered_lines": [], "suggested_tests": []}
            ]

            result = await test_generator_service.generate_until_coverage_target(
                "core/service.py",
                target_coverage=0.85
            )

            assert result["final_coverage"] >= 85.0
            assert result["target_met"] is True
            assert result["iterations"] <= 5

    @pytest.mark.asyncio
    async def test_generate_fixtures_for_structure(self, test_generator_service):
        """Test generating fixtures for test structure."""
        structure = {
            "fixtures_needed": ["db_session", "api_client"],
            "classes_to_test": [{"name": "User"}],
            "source_file": "core/user_service.py"
        }

        fixtures = test_generator_service._generate_fixtures_for_structure(structure)

        assert len(fixtures) == 2
        assert fixtures[0]["name"] == "db_session"
        assert fixtures[1]["name"] == "api_client"

    @pytest.mark.asyncio
    async def test_generate_test_cases_for_structure(self, test_generator_service):
        """Test generating test cases for structure."""
        structure = {
            "functions_to_test": [
                {"name": "create_user", "args": ["name", "email"]}
            ],
            "classes_to_test": [
                {
                    "name": "UserService",
                    "methods": [
                        {"name": "update_user", "args": ["user_id", "data"]}
                    ]
                }
            ]
        }

        test_cases = test_generator_service._generate_test_cases_for_structure(
            structure,
            {}
        )

        assert len(test_cases) > 0
        assert any("create_user" in case for case in test_cases)
        assert any("userservice" in case.lower() for case in test_cases)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for test generation workflow."""

    @pytest.mark.asyncio
    async def test_end_to_end_test_generation(self, test_generator_service):
        """Test complete test generation workflow."""
        # Create temporary source file
        source_code = """
def calculate_discount(price, discount_percent):
    '''Calculate discounted price.'''
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid discount percent")
    return price * (1 - discount_percent / 100)

def apply_tax(price, tax_rate):
    '''Apply tax to price.'''
    return price * (1 + tax_rate)
"""

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__ = Mock(return_value=mock_open)
                mock_open.return_value.__exit__ = Mock(return_value=False)
                mock_open.return_value.read.return_value = source_code

                # Generate tests
                result = await test_generator_service.generate_tests(
                    ["core/pricing.py"],
                    {"task": "pricing"}
                )

        assert "test_files" in result
        assert "test_count" in result
        assert result["test_count"] >= 0

    def test_generated_tests_are_valid_python(self, test_generator_service):
        """Test that generated test code is valid Python."""
        structure = {
            "test_file_path": "tests/test_service.py",
            "test_class_name": "TestService",
            "source_file": "core/service.py",
            "functions_to_test": [],
            "classes_to_test": [],
            "fixtures_needed": []
        }

        test_cases = [
            "def test_example():\n    assert True",
            "def test_addition():\n    assert 1 + 1 == 2"
        ]

        content = test_generator_service.generate_test_file_content(
            structure,
            [],
            test_cases
        )

        # Should be valid Python (no syntax errors)
        try:
            ast.parse(content)
            assert True
        except SyntaxError:
            pytest.fail("Generated test code has syntax errors")


# ============================================================================
# Coverage Target Achievement Tests
# ============================================================================

class TestCoverageTargetAchievement:
    """Test coverage target achievement."""

    @pytest.mark.asyncio
    async def test_85_percent_coverage_target_achievable(self, test_generator_service):
        """Test that 85% unit test coverage is achievable."""
        # Generate many test cases
        test_cases = [{"name": f"test_{i}"} for i in range(15)]

        coverage = test_generator_service.coverage_analyzer.estimate_coverage_from_tests(
            test_cases
        )

        # 15 tests * 10-15 lines = 150-225 lines / 200 avg = 75-112%
        assert coverage >= 85.0

    @pytest.mark.asyncio
    async def test_70_percent_integration_coverage_target_achievable(
        self,
        test_generator_service
    ):
        """Test that 70% integration test coverage is achievable."""
        test_cases = [{"name": f"test_integration_{i}"} for i in range(12)]

        coverage = test_generator_service.coverage_analyzer.estimate_coverage_from_tests(
            test_cases
        )

        # 12 tests * 10-15 lines = 120-180 lines / 200 avg = 60-90%
        assert coverage >= 70.0
