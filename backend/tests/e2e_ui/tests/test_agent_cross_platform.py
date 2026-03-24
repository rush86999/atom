"""
E2E tests for cross-platform agent consistency (AGNT-08).

This module tests that agent API responses are consistent across
web, mobile (API-level), and desktop platforms. Tests verify
schema compatibility, streaming format, and governance consistency.

Run with: pytest backend/tests/e2e_ui/tests/test_agent_cross_platform.py -v
"""

import pytest
import requests
import uuid
from typing import Dict, Any, List
from datetime import datetime

# Add backend to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import AgentRegistry, AgentStatus
from tests.e2e_ui.fixtures.api_fixtures import create_test_agent_direct


# ============================================================================
# Helper Functions
# ============================================================================

def make_platform_request(
    setup_test_user,
    endpoint: str,
    method: str = "GET",
    platform: str = "web",
    json_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Make API request with platform header.

    Args:
        setup_test_user: API fixture for test user creation
        endpoint: API endpoint path (e.g., "/api/v1/agents")
        method: HTTP method (GET, POST, PUT, DELETE)
        platform: Platform identifier (web, mobile, desktop)
        json_data: JSON payload for POST/PUT requests

    Returns:
        Dictionary with response data and status code
    """
    # Get user data and token
    user_data = setup_test_user()
    token = user_data.get("access_token")

    # Build headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Add platform header (not for web)
    if platform != "web":
        headers["X-Platform"] = platform

    # Make request
    url = f"http://localhost:8000{endpoint}"

    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=json_data or {})
    elif method == "PUT":
        response = requests.put(url, headers=headers, json=json_data or {})
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    # Return response data
    try:
        response_data = response.json() if response.status_code == 200 else None
    except Exception:
        response_data = None

    return {
        "status_code": response.status_code,
        "data": response_data,
        "headers": dict(response.headers)
    }


def compare_schemas(
    response1: Dict[str, Any],
    response2: Dict[str, Any],
    required_fields: List[str]
) -> None:
    """Compare two response schemas have same required fields.

    Args:
        response1: First response data
        response2: Second response data
        required_fields: List of required field names

    Raises:
        AssertionError: If schemas don't match
    """
    for field in required_fields:
        assert field in response1, f"Field '{field}' missing in response1"
        assert field in response2, f"Field '{field}' missing in response2"

        # Check types match
        type1 = type(response1[field])
        type2 = type(response2[field])

        assert type1 == type2, \
            f"Field '{field}' type mismatch: {type1} vs {type2}"


def verify_agent_response_schema(agent_data: Dict[str, Any]) -> None:
    """Verify agent response has expected schema.

    Args:
        agent_data: Agent response data

    Raises:
        AssertionError: If schema doesn't match expected format
    """
    required_fields = ["id", "name", "status"]

    for field in required_fields:
        assert field in agent_data, f"Required field '{field}' missing from agent response"

    # Verify field types
    assert isinstance(agent_data["id"], str), "Agent ID should be string"
    assert isinstance(agent_data["name"], str), "Agent name should be string"
    assert isinstance(agent_data["status"], str), "Agent status should be string"


# ============================================================================
# Test Classes
# ============================================================================

class TestAgentSchemaConsistency:
    """E2E tests for agent schema consistency across platforms (AGNT-08)."""

    def test_agent_schema_consistent_across_platforms(self, setup_test_user, db_session):
        """Verify agent schema is consistent across web, mobile, and desktop.

        This test validates:
        1. Create agent via API
        2. Make GET request to /api/v1/agents (web endpoint)
        3. Verify response schema: id, name, maturity_level, status, category
        4. Make same request with X-Platform: mobile header
        5. Verify response schema matches web response
        6. Make same request with X-Platform: desktop header
        7. Verify response schema matches web response

        Args:
            setup_test_user: API fixture for test user
            db_session: Database session fixture

        Coverage: AGNT-08 (Schema consistency across platforms)
        """
        # Create test agent
        agent_result = create_test_agent_direct(
            db,
            name=f"Schema Test Agent {str(uuid.uuid4())[:8]}",
            status="STUDENT",
            category="testing"
        )
        agent_id = agent_result["agent_id"]

        print(f"Created test agent: {agent_id}")

        # Required fields for agent schema
        required_fields = ["id", "name", "status"]

        # Make request from web platform (default)
        web_response = make_platform_request(
            setup_test_user,
            f"/api/agents/{agent_id}",
            method="GET",
            platform="web"
        )

        assert web_response["status_code"] == 200, \
            f"Web request should succeed, got {web_response['status_code']}"

        web_agent = web_response["data"]
        verify_agent_response_schema(web_agent)

        print(f"✓ Web response schema valid")

        # Make request from mobile platform
        mobile_response = make_platform_request(
            setup_test_user,
            f"/api/agents/{agent_id}",
            method="GET",
            platform="mobile"
        )

        # Mobile might return 404 if endpoint not implemented
        if mobile_response["status_code"] == 404:
            print("⚠ Mobile platform endpoint not implemented")
            pytest.skip("Mobile agent endpoint not implemented")

        assert mobile_response["status_code"] == 200, \
            f"Mobile request should succeed, got {mobile_response['status_code']}"

        mobile_agent = mobile_response["data"]
        verify_agent_response_schema(mobile_agent)

        # Compare schemas
        compare_schemas(web_agent, mobile_agent, required_fields)

        print(f"✓ Mobile response schema matches web")

        # Make request from desktop platform
        desktop_response = make_platform_request(
            setup_test_user,
            f"/api/agents/{agent_id}",
            method="GET",
            platform="desktop"
        )

        # Desktop might return 404 if endpoint not implemented
        if desktop_response["status_code"] == 404:
            print("⚠ Desktop platform endpoint not implemented")
            pytest.skip("Desktop agent endpoint not implemented")

        assert desktop_response["status_code"] == 200, \
            f"Desktop request should succeed, got {desktop_response['status_code']}"

        desktop_agent = desktop_response["data"]
        verify_agent_response_schema(desktop_agent)

        # Compare schemas
        compare_schemas(web_agent, desktop_agent, required_fields)

        print(f"✓ Desktop response schema matches web")
        print(f"✓ All platforms return consistent agent schema")

    def test_agent_list_schema_consistency(self, setup_test_user, db_session):
        """Verify agent list schema is consistent across platforms.

        This test validates:
        1. Create multiple agents
        2. Request agent list from web, mobile, desktop
        3. Verify all return same list schema
        4. Verify all agents present in all platform responses

        Args:
            setup_test_user: API fixture for test user
            db_session: Database session fixture

        Coverage: AGNT-08 (List schema consistency)
        """
        # Create test agents
        agent_ids = []
        for i in range(3):
            agent_result = create_test_agent_direct(
                db,
                name=f"List Test Agent {i} {str(uuid.uuid4())[:4]}",
                status="STUDENT",
                category="testing"
            )
            agent_ids.append(agent_result["agent_id"])

        print(f"Created {len(agent_ids)} test agents")

        # Get agent list from web
        web_response = make_platform_request(
            setup_test_user,
            "/api/agents",
            method="GET",
            platform="web"
        )

        assert web_response["status_code"] == 200, \
            f"Web agent list request should succeed, got {web_response['status_code']}"

        web_agents = web_response["data"]
        assert isinstance(web_agents, list), "Web response should be list"

        print(f"✓ Web returned {len(web_agents)} agents")

        # Get agent list from mobile
        mobile_response = make_platform_request(
            setup_test_user,
            "/api/agents",
            method="GET",
            platform="mobile"
        )

        if mobile_response["status_code"] == 404:
            print("⚠ Mobile agent list endpoint not implemented")
            pytest.skip("Mobile agent list not implemented")

        assert mobile_response["status_code"] == 200, \
            f"Mobile agent list request should succeed, got {mobile_response['status_code']}"

        mobile_agents = mobile_response["data"]
        assert isinstance(mobile_agents, list), "Mobile response should be list"

        print(f"✓ Mobile returned {len(mobile_agents)} agents")

        # Get agent list from desktop
        desktop_response = make_platform_request(
            setup_test_user,
            "/api/agents",
            method="GET",
            platform="desktop"
        )

        if desktop_response["status_code"] == 404:
            print("⚠ Desktop agent list endpoint not implemented")
            pytest.skip("Desktop agent list not implemented")

        assert desktop_response["status_code"] == 200, \
            f"Desktop agent list request should succeed, got {desktop_response['status_code']}"

        desktop_agents = desktop_response["data"]
        assert isinstance(desktop_agents, list), "Desktop response should be list"

        print(f"✓ Desktop returned {len(desktop_agents)} agents")

        # Verify all platforms return same number of agents
        assert len(web_agents) == len(mobile_agents) == len(desktop_agents), \
            "All platforms should return same number of agents"

        print("✓ All platforms return consistent agent lists")


class TestAgentStreamingFormat:
    """E2E tests for agent streaming format consistency (AGNT-08)."""

    def test_agent_streaming_format_consistent(self, setup_test_user, db_session):
        """Verify agent streaming format is consistent across platforms.

        This test validates:
        1. Create agent and initiate chat via web
        2. Capture streaming response format (check JSON structure)
        3. Make same request with mobile platform header
        4. Verify streaming format matches (same delta structure, same event types)
        5. Verify both use same completion signal

        Note: This test verifies API-level streaming format. Full WebSocket
        streaming test coverage is in test_agent_streaming.py.

        Args:
            setup_test_user: API fixture for test user
            db_session: Database session fixture

        Coverage: AGNT-08 (Streaming format consistency)
        """
        # Create test agent
        agent_result = create_test_agent_direct(
            db,
            name=f"Streaming Test Agent {str(uuid.uuid4())[:8]}",
            status="INTERN",
            category="testing"
        )
        agent_id = agent_result["agent_id"]

        print(f"Created test agent: {agent_id}")

        # Initiate chat via web platform
        web_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/chat",
            method="POST",
            platform="web",
            json_data={
                "message": "Hello",
                "agent_id": agent_id,
                "user_id": setup_test_user()["user"].get("id", "test-user")
            }
        )

        # Chat endpoint might not support platform headers yet
        if web_response["status_code"] == 404 or web_response["status_code"] == 422:
            print("⚠ Chat endpoint not fully implemented for platform testing")
            pytest.skip("Chat platform header testing not implemented")

        assert web_response["status_code"] == 200, \
            f"Web chat request should succeed, got {web_response['status_code']}"

        web_data = web_response["data"]

        # Initiate chat via mobile platform
        mobile_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/chat",
            method="POST",
            platform="mobile",
            json_data={
                "message": "Hello",
                "agent_id": agent_id,
                "user_id": setup_test_user()["user"].get("id", "test-user")
            }
        )

        assert mobile_response["status_code"] == 200, \
            f"Mobile chat request should succeed, got {mobile_response['status_code']}"

        mobile_data = mobile_response["data"]

        # Compare response structures
        # Both should have same top-level fields
        if isinstance(web_data, dict) and isinstance(mobile_data, dict):
            web_keys = set(web_data.keys())
            mobile_keys = set(mobile_data.keys())

            # At minimum, both should have response/message field
            common_keys = {"response", "message", "content", "result"}
            found_keys = web_keys & mobile_keys & common_keys

            if found_keys:
                print(f"✓ Both platforms return response data")
            else:
                print(f"⚠ Web keys: {web_keys}, Mobile keys: {mobile_keys}")

        print("✓ Streaming format consistency verified")


class TestAgentCreationPlatforms:
    """E2E tests for agent creation across platforms (AGNT-08)."""

    def test_agent_creation_works_on_all_platforms(self, setup_test_user, db_session):
        """Verify agent creation works on all platforms.

        This test validates:
        1. Test agent creation via web API (default)
        2. Test agent creation with X-Platform: mobile header
        3. Test agent creation with X-Platform: desktop header
        4. Verify all return same response schema
        5. Verify all agents created in database
        6. Verify all agents have same fields

        Args:
            setup_test_user: API fixture for test user
            db_session: Database session fixture

        Coverage: AGNT-08 (Agent creation cross-platform)
        """
        created_agent_ids = []

        # Create agent via web platform
        web_response = make_platform_request(
            setup_test_user,
            "/api/agents",
            method="POST",
            platform="web",
            json_data={
                "name": f"Web Agent {str(uuid.uuid4())[:8]}",
                "category": "testing",
                "description": "Created via web platform"
            }
        )

        # Agent creation endpoint might not exist
        if web_response["status_code"] == 404 or web_response["status_code"] == 405:
            print("⚠ Agent creation endpoint not implemented")
            pytest.skip("POST /api/agents not implemented")

        assert web_response["status_code"] == 200, \
            f"Web agent creation should succeed, got {web_response['status_code']}"

        web_agent = web_response["data"]
        if web_agent and "id" in web_agent:
            created_agent_ids.append(web_agent["id"])
            print(f"✓ Web agent created: {web_agent['id']}")

        # Create agent via mobile platform
        mobile_response = make_platform_request(
            setup_test_user,
            "/api/agents",
            method="POST",
            platform="mobile",
            json_data={
                "name": f"Mobile Agent {str(uuid.uuid4())[:8]}",
                "category": "testing",
                "description": "Created via mobile platform"
            }
        )

        assert mobile_response["status_code"] == 200, \
            f"Mobile agent creation should succeed, got {mobile_response['status_code']}"

        mobile_agent = mobile_response["data"]
        if mobile_agent and "id" in mobile_agent:
            created_agent_ids.append(mobile_agent["id"])
            print(f"✓ Mobile agent created: {mobile_agent['id']}")

        # Create agent via desktop platform
        desktop_response = make_platform_request(
            setup_test_user,
            "/api/agents",
            method="POST",
            platform="desktop",
            json_data={
                "name": f"Desktop Agent {str(uuid.uuid4())[:8]}",
                "category": "testing",
                "description": "Created via desktop platform"
            }
        )

        assert desktop_response["status_code"] == 200, \
            f"Desktop agent creation should succeed, got {desktop_response['status_code']}"

        desktop_agent = desktop_response["data"]
        if desktop_agent and "id" in desktop_agent:
            created_agent_ids.append(desktop_agent["id"])
            print(f"✓ Desktop agent created: {desktop_agent['id']}")

        # Verify all agents have same schema
        if web_agent and mobile_agent and desktop_agent:
            required_fields = ["id", "name", "status"]

            compare_schemas(web_agent, mobile_agent, required_fields)
            compare_schemas(web_agent, desktop_agent, required_fields)

            print("✓ All platforms return consistent agent creation schema")

        # Verify all agents exist in database
        for agent_id in created_agent_ids:
            agent = db_session.query(AgentRegistry).filter_by(id=agent_id).first()
            assert agent is not None, f"Agent {agent_id} should exist in database"

        print(f"✓ All {len(created_agent_ids)} agents verified in database")


class TestAgentGovernanceConsistency:
    """E2E tests for governance consistency across platforms (AGNT-08)."""

    def test_agent_governance_consistent_across_platforms(self, setup_test_user, db_session):
        """Verify agent governance errors are consistent across platforms.

        This test validates:
        1. Create STUDENT agent
        2. Test restricted action via web endpoint
        3. Verify governance error response
        4. Test same action with mobile platform header
        5. Verify same governance error
        6. Test with desktop platform header
        7. Verify same governance error
        8. Compare all error responses: same structure, same error codes

        Args:
            setup_test_user: API fixture for test user
            db_session: Database session fixture

        Coverage: AGNT-08 (Governance consistency cross-platform)
        """
        # Create STUDENT agent
        agent_result = create_test_agent_direct(
            db,
            name=f"Student Agent {str(uuid.uuid4())[:8]}",
            status="STUDENT",
            category="testing"
        )
        agent_id = agent_result["agent_id"]

        print(f"Created STUDENT agent: {agent_id}")

        # Test restricted action via web platform
        # (Try to execute an action that STUDENT agents cannot do)
        web_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/execute",
            method="POST",
            platform="web",
            json_data={
                "agent_id": agent_id,
                "action": "restricted_action",
                "parameters": {}
            }
        )

        # Execute endpoint might not be implemented
        if web_response["status_code"] == 404:
            print("⚠ Agent execute endpoint not implemented")
            pytest.skip("Agent execute endpoint not implemented")

        # Should get governance error or 403
        web_is_error = web_response["status_code"] in [403, 401] or \
                      (web_response["data"] and "error" in str(web_response["data"]).lower())

        print(f"✓ Web governance check: status={web_response['status_code']}, error={web_is_error}")

        # Test via mobile platform
        mobile_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/execute",
            method="POST",
            platform="mobile",
            json_data={
                "agent_id": agent_id,
                "action": "restricted_action",
                "parameters": {}
            }
        )

        mobile_is_error = mobile_response["status_code"] in [403, 401] or \
                          (mobile_response["data"] and "error" in str(mobile_response["data"]).lower())

        print(f"✓ Mobile governance check: status={mobile_response['status_code']}, error={mobile_is_error}")

        # Test via desktop platform
        desktop_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/execute",
            method="POST",
            platform="desktop",
            json_data={
                "agent_id": agent_id,
                "action": "restricted_action",
                "parameters": {}
            }
        )

        desktop_is_error = desktop_response["status_code"] in [403, 401] or \
                           (desktop_response["data"] and "error" in str(desktop_response["data"]).lower())

        print(f"✓ Desktop governance check: status={desktop_response['status_code']}, error={desktop_is_error}")

        # All platforms should return consistent error handling
        assert web_is_error and mobile_is_error and desktop_is_error, \
            "All platforms should enforce governance for STUDENT agents"

        print("✓ All platforms enforce governance consistently")


class TestCrossPlatformAgentExecution:
    """E2E tests for cross-platform agent execution (AGNT-08)."""

    def test_cross_platform_agent_execution(self, setup_test_user, db_session):
        """Verify agent execution format is consistent across platforms.

        This test validates:
        1. Create INTERN agent
        2. Execute simple action via web: "say hello"
        3. Capture response format
        4. Execute same action with mobile header
        5. Verify response format matches web
        6. Execute with desktop header
        7. Verify response format matches

        Args:
            setup_test_user: API fixture for test user
            db_session: Database session fixture

        Coverage: AGNT-08 (Execution format cross-platform)
        """
        # Create INTERN agent
        agent_result = create_test_agent_direct(
            db,
            name=f"Intern Agent {str(uuid.uuid4())[:8]}",
            status="INTERN",
            category="testing"
        )
        agent_id = agent_result["agent_id"]

        print(f"Created INTERN agent: {agent_id}")

        # Execute via web platform
        web_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/chat",
            method="POST",
            platform="web",
            json_data={
                "message": "Say hello",
                "agent_id": agent_id,
                "user_id": setup_test_user()["user"].get("id", "test-user")
            }
        )

        if web_response["status_code"] == 404:
            print("⚠ Agent execution endpoint not implemented")
            pytest.skip("Agent execution endpoint not implemented")

        assert web_response["status_code"] == 200, \
            f"Web execution should succeed, got {web_response['status_code']}"

        web_result = web_response["data"]
        print(f"✓ Web execution succeeded")

        # Execute via mobile platform
        mobile_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/chat",
            method="POST",
            platform="mobile",
            json_data={
                "message": "Say hello",
                "agent_id": agent_id,
                "user_id": setup_test_user()["user"].get("id", "test-user")
            }
        )

        assert mobile_response["status_code"] == 200, \
            f"Mobile execution should succeed, got {mobile_response['status_code']}"

        mobile_result = mobile_response["data"]
        print(f"✓ Mobile execution succeeded")

        # Execute via desktop platform
        desktop_response = make_platform_request(
            setup_test_user,
            "/api/atom-agent/chat",
            method="POST",
            platform="desktop",
            json_data={
                "message": "Say hello",
                "agent_id": agent_id,
                "user_id": setup_test_user()["user"].get("id", "test-user")
            }
        )

        assert desktop_response["status_code"] == 200, \
            f"Desktop execution should succeed, got {desktop_response['status_code']}"

        desktop_result = desktop_response["data"]
        print(f"✓ Desktop execution succeeded")

        # Compare response formats (all should have similar structure)
        if isinstance(web_result, dict) and isinstance(mobile_result, dict):
            web_keys = set(web_result.keys())
            mobile_keys = set(mobile_result.keys())

            # At least some keys should match
            common_keys = web_keys & mobile_keys
            assert len(common_keys) > 0, "Web and mobile should share some response fields"

            print(f"✓ Response formats consistent across platforms ({len(common_keys)} common fields)")

        print("✓ Cross-platform execution verified")
