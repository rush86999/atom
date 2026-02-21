"""
Comprehensive tests for RequirementParserService

Tests cover:
- Basic feature request parsing
- User story extraction and validation
- Acceptance criteria extraction (Gherkin format)
- Dependency identification
- Complexity estimation (simple/moderate/complex/advanced)
- Workflow creation and persistence
- BYOK handler integration
- Error handling for invalid inputs
- LLM failure recovery
- Edge cases and boundary conditions

Test coverage target: >= 80% for RequirementParserService
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.requirement_parser_service import RequirementParserService
from core.llm.byok_handler import BYOKHandler
from core.models import AutonomousWorkflow


# ==================== Fixtures ====================

@pytest.fixture
def db_session():
    """Create database session with automatic rollback."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def mock_byok_handler():
    """Create mock BYOK handler with predefined responses."""
    handler = MagicMock(spec=BYOKHandler)
    handler.acomplete = AsyncMock()
    return handler


@pytest.fixture
def sample_llm_response():
    """Sample LLM response for requirement parsing."""
    return """```json
{
  "user_stories": [
    {
      "id": "US-001",
      "title": "Google OAuth2 Login",
      "role": "user",
      "action": "log in with Google account",
      "value": "avoid password management",
      "acceptance_criteria": [
        "Given user is on login page",
        "When user clicks 'Sign in with Google'",
        "Then user should be redirected to Google OAuth",
        "And user should be authenticated upon success"
      ],
      "priority": "high",
      "complexity": "moderate"
    }
  ],
  "dependencies": [
    "OAuth2 client credentials for Google",
    "User session management system"
  ],
  "integration_points": [
    "POST /auth/google/callback",
    "GET /auth/google"
  ],
  "estimated_complexity": "moderate",
  "estimated_time": "4-6 hours"
}
```"""


@pytest.fixture
def sample_feature_request():
    """Sample feature request for testing."""
    return "Add OAuth2 authentication with Google and GitHub providers"


@pytest.fixture
def parser_service(db_session, mock_byok_handler):
    """Create RequirementParserService instance for testing."""
    return RequirementParserService(db_session, mock_byok_handler)


# ==================== Test Cases ====================

@pytest.mark.asyncio
async def test_parse_requirements_simple_feature(parser_service, sample_llm_response):
    """Test parsing a simple feature request."""
    # Mock LLM response
    parser_service.byok_handler.acomplete.return_value = sample_llm_response

    result = await parser_service.parse_requirements(
        feature_request="Add OAuth2 login",
        workspace_id="default"
    )

    # Verify structure
    assert "user_stories" in result
    assert "dependencies" in result
    assert "integration_points" in result
    assert "estimated_complexity" in result

    # Verify user story
    assert len(result["user_stories"]) == 1
    story = result["user_stories"][0]
    assert story["id"] == "US-001"
    assert story["role"] == "user"
    assert story["action"] == "log in with Google account"
    assert story["value"] == "avoid password management"
    assert story["priority"] == "high"
    assert story["complexity"] == "moderate"


@pytest.mark.asyncio
async def test_parse_requirements_with_dependencies(parser_service):
    """Test parsing with dependency extraction."""
    llm_response = """```json
{
  "user_stories": [
    {
      "id": "US-001",
      "title": "OAuth Login",
      "role": "user",
      "action": "log in with OAuth",
      "value": "secure authentication",
      "acceptance_criteria": ["Given user is on login page", "When user clicks OAuth", "Then user is authenticated"],
      "priority": "high",
      "complexity": "moderate"
    }
  ],
  "dependencies": [
    "OAuth2 client credentials",
    "User session management",
    "SSL certificate"
  ],
  "integration_points": [
    "POST /auth/callback",
    "GET /auth/login"
  ],
  "estimated_complexity": "moderate",
  "estimated_time": "4-6 hours"
}
```"""

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Add OAuth login",
        workspace_id="default"
    )

    # Verify dependencies
    assert len(result["dependencies"]) == 3
    assert "OAuth2 client credentials" in result["dependencies"]
    assert "User session management" in result["dependencies"]

    # Verify integration points
    assert len(result["integration_points"]) == 2
    assert "POST /auth/callback" in result["integration_points"]


@pytest.mark.asyncio
async def test_extract_user_stories(parser_service, sample_llm_response):
    """Test user story structure validation."""
    parser_service.byok_handler.acomplete.return_value = sample_llm_response

    result = await parser_service.parse_requirements(
        feature_request="Add OAuth2 login",
        workspace_id="default"
    )

    # Verify user story has required fields
    story = result["user_stories"][0]
    required_fields = ["id", "title", "role", "action", "value", "acceptance_criteria", "priority", "complexity"]
    for field in required_fields:
        assert field in story, f"Missing field: {field}"

    # Verify acceptance criteria format
    assert len(story["acceptance_criteria"]) == 4
    assert any("Given" in criterion for criterion in story["acceptance_criteria"])
    assert any("When" in criterion for criterion in story["acceptance_criteria"])
    assert any("Then" in criterion for criterion in story["acceptance_criteria"])


@pytest.mark.asyncio
async def test_extract_acceptance_criteria_gherkin(parser_service):
    """Test Gherkin format validation for acceptance criteria."""
    llm_response = """```json
{
  "user_stories": [
    {
      "id": "US-001",
      "title": "User Login",
      "role": "user",
      "action": "log into the system",
      "value": "access personalized content",
      "acceptance_criteria": [
        "Given user is on login page",
        "When user enters valid credentials",
        "Then user should be redirected to dashboard",
        "And user should see welcome message"
      ],
      "priority": "high",
      "complexity": "simple"
    }
  ],
  "dependencies": [],
  "integration_points": [],
  "estimated_complexity": "simple",
  "estimated_time": "1-2 hours"
}
```"""

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Add user login",
        workspace_id="default"
    )

    # Verify Gherkin format
    criteria = result["user_stories"][0]["acceptance_criteria"]
    assert "Given user is on login page" in criteria
    assert "When user enters valid credentials" in criteria
    assert "Then user should be redirected to dashboard" in criteria
    assert "And user should see welcome message" in criteria


@pytest.mark.asyncio
async def test_estimate_complexity_simple(parser_service):
    """Test complexity estimation for simple features."""
    llm_response = """```json
{
  "user_stories": [
    {
      "id": "US-001",
      "title": "Simple Feature",
      "role": "user",
      "action": "perform simple action",
      "value": "simple value",
      "acceptance_criteria": [],
      "priority": "low",
      "complexity": "simple"
    }
  ],
  "dependencies": ["Single dependency"],
  "integration_points": [],
  "estimated_complexity": "simple",
  "estimated_time": "1-2 hours"
}
```"""

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Simple feature",
        workspace_id="default"
    )

    # Verify simple complexity
    assert result["estimated_complexity"] == "simple"


@pytest.mark.asyncio
async def test_estimate_complexity_moderate(parser_service):
    """Test complexity estimation for moderate features."""
    llm_response = """```json
{
  "user_stories": [
    {
      "id": "US-001",
      "title": "Moderate Feature",
      "role": "user",
      "action": "perform moderate action",
      "value": "moderate value",
      "acceptance_criteria": [],
      "priority": "medium",
      "complexity": "moderate"
    },
    {
      "id": "US-002",
      "title": "Another Moderate Feature",
      "role": "admin",
      "action": "perform admin action",
      "value": "admin value",
      "acceptance_criteria": [],
      "priority": "medium",
      "complexity": "moderate"
    }
  ],
  "dependencies": ["Dependency 1", "Dependency 2", "Dependency 3"],
  "integration_points": ["API endpoint 1", "API endpoint 2"],
  "estimated_complexity": "moderate",
  "estimated_time": "4-6 hours"
}
```"""

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Moderate feature",
        workspace_id="default"
    )

    # Verify moderate complexity
    assert result["estimated_complexity"] == "moderate"


@pytest.mark.asyncio
async def test_estimate_complexity_complex(parser_service):
    """Test complexity estimation for complex features."""
    # Create 7 user stories (5-10 is complex threshold) as valid JSON
    llm_response = """```json
{
  "user_stories": [
    {"id": "US-001", "title": "Complex Feature 1", "role": "user", "action": "complex action 1", "value": "complex value 1", "acceptance_criteria": [], "priority": "high", "complexity": "complex"},
    {"id": "US-002", "title": "Complex Feature 2", "role": "user", "action": "complex action 2", "value": "complex value 2", "acceptance_criteria": [], "priority": "high", "complexity": "complex"},
    {"id": "US-003", "title": "Complex Feature 3", "role": "user", "action": "complex action 3", "value": "complex value 3", "acceptance_criteria": [], "priority": "high", "complexity": "complex"},
    {"id": "US-004", "title": "Complex Feature 4", "role": "user", "action": "complex action 4", "value": "complex value 4", "acceptance_criteria": [], "priority": "high", "complexity": "complex"},
    {"id": "US-005", "title": "Complex Feature 5", "role": "user", "action": "complex action 5", "value": "complex value 5", "acceptance_criteria": [], "priority": "high", "complexity": "complex"},
    {"id": "US-006", "title": "Complex Feature 6", "role": "user", "action": "complex action 6", "value": "complex value 6", "acceptance_criteria": [], "priority": "high", "complexity": "complex"},
    {"id": "US-007", "title": "Complex Feature 7", "role": "user", "action": "complex action 7", "value": "complex value 7", "acceptance_criteria": [], "priority": "high", "complexity": "complex"}
  ],
  "dependencies": ["Dep 1", "Dep 2", "Dep 3", "Dep 4", "Dep 5", "Dep 6", "Dep 7"],
  "integration_points": ["API 1", "API 2", "API 3", "API 4", "API 5"],
  "estimated_complexity": "complex",
  "estimated_time": "1-2 days"
}
```"""

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Complex feature",
        workspace_id="default"
    )

    # Verify complex complexity
    assert result["estimated_complexity"] == "complex"


@pytest.mark.asyncio
async def test_estimate_complexity_advanced(parser_service):
    """Test complexity estimation for advanced features."""
    # Create 11 user stories (10+ is advanced threshold)
    stories = []
    for i in range(11):
        stories.append({
            "id": f"US-{i+1:03d}",
            "title": f"Advanced Feature {i+1}",
            "role": "user",
            "action": f"advanced action {i+1}",
            "value": f"advanced value {i+1}",
            "acceptance_criteria": [],
            "priority": "high",
            "complexity": "advanced"
        })

    llm_response = f"""```json
{{
  "user_stories": {stories},
  "dependencies": ["Dep {i}" for i in range(12)],
  "integration_points": ["API {i}" for i in range(10)],
  "estimated_complexity": "advanced",
  "estimated_time": "2+ days"
}}
```"""

    # Fix the invalid JSON (Python list comprehension doesn't work in JSON)
    llm_response = """```json
{
  "user_stories": [
    {"id": "US-001", "title": "Advanced Feature 1", "role": "user", "action": "advanced action 1", "value": "advanced value 1", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-002", "title": "Advanced Feature 2", "role": "user", "action": "advanced action 2", "value": "advanced value 2", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-003", "title": "Advanced Feature 3", "role": "user", "action": "advanced action 3", "value": "advanced value 3", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-004", "title": "Advanced Feature 4", "role": "user", "action": "advanced action 4", "value": "advanced value 4", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-005", "title": "Advanced Feature 5", "role": "user", "action": "advanced action 5", "value": "advanced value 5", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-006", "title": "Advanced Feature 6", "role": "user", "action": "advanced action 6", "value": "advanced value 6", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-007", "title": "Advanced Feature 7", "role": "user", "action": "advanced action 7", "value": "advanced value 7", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-008", "title": "Advanced Feature 8", "role": "user", "action": "advanced action 8", "value": "advanced value 8", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-009", "title": "Advanced Feature 9", "role": "user", "action": "advanced action 9", "value": "advanced value 9", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-010", "title": "Advanced Feature 10", "role": "user", "action": "advanced action 10", "value": "advanced value 10", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"},
    {"id": "US-011", "title": "Advanced Feature 11", "role": "user", "action": "advanced action 11", "value": "advanced value 11", "acceptance_criteria": [], "priority": "high", "complexity": "advanced"}
  ],
  "dependencies": ["Dep 1", "Dep 2", "Dep 3", "Dep 4", "Dep 5", "Dep 6", "Dep 7", "Dep 8", "Dep 9", "Dep 10", "Dep 11", "Dep 12"],
  "integration_points": ["API 1", "API 2", "API 3", "API 4", "API 5", "API 6", "API 7", "API 8", "API 9", "API 10"],
  "estimated_complexity": "advanced",
  "estimated_time": "2+ days"
}
```"""

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Advanced feature",
        workspace_id="default"
    )

    # Verify advanced complexity
    assert result["estimated_complexity"] == "advanced"


@pytest.mark.asyncio
async def test_create_workflow_persistence(db_session, mock_byok_handler):
    """Test database record creation for parsed requirements."""
    parser_service = RequirementParserService(db_session, mock_byok_handler)

    parsed_requirements = {
        "user_stories": [
            {
                "id": "US-001",
                "title": "Test Story",
                "role": "user",
                "action": "test action",
                "value": "test value",
                "acceptance_criteria": [],
                "priority": "high",
                "complexity": "simple"
            }
        ],
        "dependencies": [],
        "integration_points": [],
        "estimated_complexity": "simple",
        "estimated_time": "1-2 hours"
    }

    # Note: This test may fail if database tables don't exist yet
    # In production, run: alembic upgrade head
    try:
        workflow = await parser_service.create_workflow(
            feature_request="Test feature",
            workspace_id="default",
            parsed_requirements=parsed_requirements
        )

        # Verify workflow created
        assert workflow.id is not None
        assert workflow.feature_request == "Test feature"
        assert workflow.workspace_id == "default"
        assert workflow.status == "pending"
        assert workflow.user_stories == parsed_requirements["user_stories"]
        assert workflow.started_at is not None
    except Exception as e:
        # Skip test if migration hasn't been run
        if "no such table" in str(e).lower() or "foreign key" in str(e).lower():
            pytest.skip(f"Database migration not run: {e}")
        else:
            raise


@pytest.mark.asyncio
async def test_llm_integration_with_byok(parser_service):
    """Test BYOK handler integration for LLM calls."""
    parser_service.byok_handler.acomplete.return_value = """```json
{
  "user_stories": [],
  "dependencies": [],
  "integration_points": [],
  "estimated_complexity": "simple",
  "estimated_time": "1 hour"
}
```"""

    await parser_service.parse_requirements(
        feature_request="Test feature",
        workspace_id="default"
    )

    # Verify BYOK handler was called
    assert parser_service.byok_handler.acomplete.called
    call_args = parser_service.byok_handler.acomplete.call_args

    # Verify parameters
    assert "prompt" in call_args.kwargs
    assert "system_prompt" in call_args.kwargs
    assert "temperature" in call_args.kwargs
    assert call_args.kwargs["temperature"] == 0.0  # Deterministic


@pytest.mark.asyncio
async def test_error_handling_invalid_input(parser_service):
    """Test error handling for invalid feature request."""
    with pytest.raises(ValueError, match="Feature request cannot be empty"):
        await parser_service.parse_requirements(
            feature_request="",
            workspace_id="default"
        )

    with pytest.raises(ValueError, match="Feature request cannot be empty"):
        await parser_service.parse_requirements(
            feature_request="   ",
            workspace_id="default"
        )


@pytest.mark.asyncio
async def test_error_handling_llm_failure(parser_service):
    """Test error handling when LLM call fails."""
    # Mock LLM failure
    parser_service.byok_handler.acomplete.side_effect = Exception("LLM API error")

    with pytest.raises(Exception, match="Failed to get LLM response"):
        await parser_service.parse_requirements(
            feature_request="Test feature",
            workspace_id="default"
        )


@pytest.mark.asyncio
async def test_json_markdown_extraction(parser_service):
    """Test JSON extraction from markdown code blocks."""
    llm_response = """
    Here's the parsed requirements:

    ```json
    {
      "user_stories": [
        {
          "id": "US-001",
          "title": "Test",
          "role": "user",
          "action": "test action",
          "value": "test value",
          "acceptance_criteria": [],
          "priority": "medium",
          "complexity": "simple"
        }
      ],
      "dependencies": [],
      "integration_points": [],
      "estimated_complexity": "simple",
      "estimated_time": "1 hour"
    }
    ```

    Let me know if you need any changes!
    """

    parser_service.byok_handler.acomplete.return_value = llm_response

    result = await parser_service.parse_requirements(
        feature_request="Test feature",
        workspace_id="default"
    )

    # Verify JSON was extracted from markdown
    assert "user_stories" in result
    assert len(result["user_stories"]) == 1


@pytest.mark.asyncio
async def test_time_estimation_parsing(parser_service):
    """Test time estimation parsing to seconds."""
    parsed_requirements = {
        "user_stories": [],
        "dependencies": [],
        "integration_points": [],
        "estimated_complexity": "moderate",
        "estimated_time": "4-6 hours"
    }

    # Test hour range
    duration = parser_service._estimate_duration("4-6 hours")
    assert duration is not None
    # Average of 4 and 6 = 5, 5 * 3600 = 18000 seconds
    expected = 5 * 3600
    assert duration == expected

    # Test single value
    duration = parser_service._estimate_duration("2 hours")
    expected = 2 * 3600
    assert duration == expected

    # Test days
    duration = parser_service._estimate_duration("1-2 days")
    expected = 1.5 * 86400
    assert duration == expected


@pytest.mark.asyncio
async def test_context_in_prompt(parser_service):
    """Test that context is properly included in LLM prompt."""
    parser_service.byok_handler.acomplete.return_value = """```json
{
  "user_stories": [],
  "dependencies": [],
  "integration_points": [],
  "estimated_complexity": "simple",
  "estimated_time": "1 hour"
}
```"""

    context = {
        "priority": "high",
        "deadline": "2026-03-01",
        "constraints": ["Must use OAuth2"]
    }

    await parser_service.parse_requirements(
        feature_request="Test feature",
        workspace_id="default",
        context=context
    )

    # Verify context was included in prompt
    call_args = parser_service.byok_handler.acomplete.call_args
    prompt = call_args.kwargs["prompt"]
    assert "priority" in prompt
    assert "high" in prompt
    assert "deadline" in prompt
    assert "2026-03-01" in prompt


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=backend/core/requirement_parser_service", "--cov-report=term-missing"])
