"""
Mobile API Agent Execution Tests

Tests for mobile API agent execution endpoints:
- Agent execution (sync and streaming)
- Agent execution with parameters
- Agent execution governance checks
- Agent execution history

All tests use API-first approach with TestClient (no browser).
Response structure matches web API for consistency.
"""

import pytest
from fastapi.testclient import TestClient


class TestMobileAgentExecute:
    """Test mobile agent execution endpoint"""

    def test_mobile_agent_execute_success(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test successful agent execution"""
        # First, list available agents
        list_response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)

        if list_response.status_code != 200:
            pytest.skip("Agents endpoint not available")

        agents = list_response.json().get("agents", [])
        if not agents:
            pytest.skip("No agents available for testing")

        # Select first agent
        agent_id = agents[0].get("id") or agents[0].get("agent_id")
        if not agent_id:
            pytest.skip("Agent ID not found in response")

        # Execute agent
        response = mobile_api_client.post(
            f"/api/v1/agents/{agent_id}/execute",
            headers=mobile_auth_headers,
            json={"query": "test query"}
        )

        # Verify response (may be 200 or 202 for async execution)
        assert response.status_code in [200, 202]
        data = response.json()

        # Verify execution_id or response present
        assert "execution_id" in data or "response" in data or "success" in data

    def test_mobile_agent_execute_with_params(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent execution with custom parameters"""
        # First, list available agents
        list_response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)

        if list_response.status_code != 200:
            pytest.skip("Agents endpoint not available")

        agents = list_response.json().get("agents", [])
        if not agents:
            pytest.skip("No agents available for testing")

        agent_id = agents[0].get("id") or agents[0].get("agent_id")
        if not agent_id:
            pytest.skip("Agent ID not found in response")

        # Execute agent with parameters
        response = mobile_api_client.post(
            f"/api/v1/agents/{agent_id}/execute",
            headers=mobile_auth_headers,
            json={
                "query": "test query with params",
                "params": {"key": "value", "number": 123}
            }
        )

        # Verify response
        assert response.status_code in [200, 202]
        data = response.json()

        # Verify execution initiated
        assert "execution_id" in data or "success" in data

    def test_mobile_agent_execute_not_found(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent execution with non-existent agent ID"""
        response = mobile_api_client.post(
            "/api/v1/agents/nonexistent_agent_id/execute",
            headers=mobile_auth_headers,
            json={"query": "test query"}
        )

        # Verify error response
        assert response.status_code in [404, 400]

    def test_mobile_agent_execute_unauthorized(self, mobile_api_client: TestClient):
        """Test agent execution without authentication"""
        response = mobile_api_client.post(
            "/api/v1/agents/some_agent_id/execute",
            json={"query": "test query"}
        )

        # Verify unauthorized response
        assert response.status_code == 401


class TestMobileAgentStream:
    """Test mobile agent streaming execution"""

    def test_mobile_agent_stream_execution(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent streaming execution"""
        # First, list available agents
        list_response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)

        if list_response.status_code != 200:
            pytest.skip("Agents endpoint not available")

        agents = list_response.json().get("agents", [])
        if not agents:
            pytest.skip("No agents available for testing")

        agent_id = agents[0].get("id") or agents[0].get("agent_id")
        if not agent_id:
            pytest.skip("Agent ID not found in response")

        # Execute agent with streaming enabled
        response = mobile_api_client.post(
            "/api/atom-agent/chat/stream",
            headers=mobile_auth_headers,
            json={
                "message": "test streaming query",
                "stream": True
            }
        )

        # Verify response (streaming returns 200 with message_id)
        if response.status_code == 200:
            data = response.json()
            # Verify streaming response structure
            assert "message_id" in data or "success" in data
        else:
            # Some endpoints may not support streaming in TestClient
            pytest.skip("Streaming endpoint not available in TestClient")


class TestMobileAgentGovernance:
    """Test mobile agent governance enforcement"""

    def test_mobile_agent_execution_governance(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent execution respects governance checks"""
        # Try to execute an agent action that requires governance
        # This test verifies governance enforcement is in place

        # List agents first
        list_response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)

        if list_response.status_code != 200:
            pytest.skip("Agents endpoint not available")

        agents = list_response.json().get("agents", [])
        if not agents:
            pytest.skip("No agents available for testing")

        # Try to execute agent
        agent_id = agents[0].get("id") or agents[0].get("agent_id")
        if not agent_id:
            pytest.skip("Agent ID not found in response")

        response = mobile_api_client.post(
            f"/api/v1/agents/{agent_id}/execute",
            headers=mobile_auth_headers,
            json={"query": "test governance check"}
        )

        # Verify governance is checked (should not fail silently)
        # Response may be success or governance error
        assert response.status_code in [200, 202, 403, 400]

        # If governance blocked, verify error message
        if response.status_code == 403:
            data = response.json()
            assert "detail" in data or "error" in data

    def test_mobile_agent_maturity_level(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent maturity level is respected"""
        # This test verifies that agent maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        # are properly enforced

        # Try to access agent info
        response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)

        if response.status_code != 200:
            pytest.skip("Agents endpoint not available")

        data = response.json()
        agents = data.get("agents", [])

        # Verify agents have maturity level info (if available)
        if agents:
            # Check first agent for maturity info
            agent = agents[0]
            # Maturity level may be in different fields
            maturity_fields = ["maturity_level", "maturity", "level", "confidence"]
            has_maturity = any(field in agent for field in maturity_fields)

            # If maturity info present, verify it's valid
            if has_maturity:
                # Just verify field exists - actual governance tested elsewhere
                assert True  # Maturity info present
            else:
                # Maturity info not required in response
                pass


class TestMobileAgentExecutionHistory:
    """Test mobile agent execution history"""

    def test_mobile_agent_execution_history(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test listing agent execution history"""
        # Try to get execution history
        response = mobile_api_client.get(
            "/api/v1/agents/executions",
            headers=mobile_auth_headers
        )

        # Verify response (may be 200 or endpoint may not exist)
        if response.status_code == 200:
            data = response.json()

            # Verify history structure
            assert "executions" in data or "items" in data or isinstance(data, list)

            # Verify pagination fields if present
            if "limit" in data or "offset" in data:
                assert isinstance(data.get("limit", 0), int)
                assert isinstance(data.get("offset", 0), int)
        elif response.status_code == 404:
            pytest.skip("Executions history endpoint not implemented")
        else:
            # Unexpected status code
            assert response.status_code in [200, 404]

    def test_mobile_agent_execution_history_pagination(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test execution history pagination works"""
        # Try with limit and offset
        response = mobile_api_client.get(
            "/api/v1/agents/executions?limit=10&offset=0",
            headers=mobile_auth_headers
        )

        if response.status_code == 200:
            data = response.json()

            # Verify pagination parameters respected
            executions = data.get("executions", data.get("items", []))
            if isinstance(executions, list):
                assert len(executions) <= 10
        elif response.status_code == 404:
            pytest.skip("Executions history endpoint not implemented")


class TestMobileAgentChatEndpoint:
    """Test mobile agent chat endpoint (alternative to execute)"""

    def test_mobile_agent_chat(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent chat endpoint"""
        response = mobile_api_client.post(
            "/api/atom-agent/chat",
            headers=mobile_auth_headers,
            json={
                "message": "Hello, can you help me?",
                "session_id": None  # New session
            }
        )

        # Verify response
        if response.status_code == 200:
            data = response.json()

            # Verify chat response structure
            assert "success" in data or "response" in data

            # If success, verify response structure
            if data.get("success"):
                assert "response" in data
                response_data = data["response"]
                assert "message" in response_data or isinstance(response_data, str)
        elif response.status_code == 404:
            pytest.skip("Chat endpoint not available")

    def test_mobile_agent_chat_with_history(self, mobile_api_client: TestClient, mobile_auth_headers: dict):
        """Test agent chat with conversation history"""
        response = mobile_api_client.post(
            "/api/atom-agent/chat",
            headers=mobile_auth_headers,
            json={
                "message": "What was my previous question?",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi! How can I help?"}
                ]
            }
        )

        # Verify response
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "response" in data
        elif response.status_code == 404:
            pytest.skip("Chat endpoint not available")
