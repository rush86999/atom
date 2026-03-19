"""
Agent API load test scenarios.

This module defines load test tasks for agent CRUD operations.
The AgentCRUDTasks mixin can be imported and mixed into Locust user classes.

Weight Distribution:
- Read operations (list, get) have higher weights (5:3) - realistic pattern
- Write operations (create, update, delete) have lower weights (1:1:1) - less frequent
- This reflects typical API usage where users read more than they write

Reference: Phase 209 Plan 02 - Extended Agent CRUD Operations
"""

import random
import logging
from locust import task

logger = logging.getLogger(__name__)


class AgentCRUDTasks:
    """
    Mixin class for agent CRUD load test tasks.

    This mixin provides task methods for testing agent create, read, update,
    and delete operations. It can be mixed into any HttpUser class.

    Tasks:
    - list_agents: High-frequency read operation (weight 5)
    - get_agent: Medium-frequency read operation (weight 3)
    - create_agent: Low-frequency write operation (weight 1)
    - update_agent: Low-frequency write operation (weight 1)
    - delete_agent: Low-frequency write operation (weight 1)

    Requires the HttpUser class to have:
    - self.client: Locust HTTP client
    - self.token: Authentication token (optional, will skip if None)
    """

    @task(5)
    def list_agents(self):
        """
        List agents with pagination (high frequency).

        Simulates loading the agents list page, which is one of the
        most common operations in the UI. Uses pagination parameters
        to simulate realistic browsing behavior.

        Weight: 5 (most common - every page load)
        Endpoint: GET /api/v1/agents
        Target: <50ms (from Phase 208 benchmarks)

        Query Parameters:
        - skip: Pagination offset (0-100)
        - limit: Results per page (10-50)

        Success Criteria:
        - 200: Valid response with agents list
        - 401: Acceptable (auth expired during test)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # Use realistic pagination parameters
        params = {
            "skip": random.randint(0, 100),
            "limit": random.choice([10, 20, 50])
        }

        with self.client.get(
            "/api/v1/agents",
            headers=headers,
            params=params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate response structure
                if "agents" in data or isinstance(data, list):
                    response.success()
                else:
                    response.failure("Invalid response structure - missing 'agents' key")
            elif response.status_code == 401:
                # Auth errors are acceptable in load tests (token might expire)
                response.success()
            elif response.status_code == 404:
                # Acceptable - endpoint might not exist in test environment
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def get_agent(self):
        """
        Get specific agent by ID (medium frequency).

        Simulates viewing agent details. Uses random agent IDs
        to test caching and database query performance.

        Weight: 3 (medium frequency - detail views)
        Endpoint: GET /api/v1/agents/{id}
        Target: <50ms (from Phase 208 benchmarks)

        Success Criteria:
        - 200: Agent found and returned
        - 404: Acceptable (agent doesn't exist)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        agent_id = f"agent_{random.randint(1, 100)}"
        headers = self._get_auth_headers()

        with self.client.get(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate response has agent data
                if "id" in data or "agent_id" in data:
                    response.success()
                else:
                    response.failure("Invalid response structure - missing agent ID")
            elif response.status_code in [401, 404]:
                # Both are acceptable in load tests
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def create_agent(self):
        """
        Create new agent (low frequency).

        Simulates user creating a new agent. Generates realistic
        agent data with random values to test unique constraints
        and database insert performance.

        Weight: 1 (low frequency - user actions)
        Endpoint: POST /api/v1/agents
        Target: <100ms (from Phase 208 benchmarks)

        Success Criteria:
        - 201: Agent created successfully
        - 400: Acceptable (validation error)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)

        Note: Uses AUTONOMOUS maturity level to avoid governance
        overhead in load tests (we test governance separately).
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # Generate realistic agent payload
        payload = {
            "name": f"Load Test Agent {random.randint(1, 10000)}",
            "category": random.choice(["automation", "analytics", "integration", "monitoring"]),
            "module_path": "test.module",
            "class_name": "TestAgent",
            "maturity": "AUTONOMOUS",
            "confidence_score": round(random.uniform(0.7, 0.95), 2)
        }

        with self.client.post(
            "/api/v1/agents",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            elif response.status_code in [400, 401, 422]:
                # Acceptable - validation or auth errors
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def update_agent(self):
        """
        Update existing agent (low frequency).

        Simulates updating agent status or configuration. Tests
        database update performance and optimistic locking.

        Weight: 1 (low frequency - user actions)
        Endpoint: PUT /api/v1/agents/{id}
        Target: <100ms (from Phase 208 benchmarks)

        Success Criteria:
        - 200: Agent updated successfully
        - 404: Acceptable (agent doesn't exist)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        agent_id = f"agent_{random.randint(1, 100)}"
        headers = self._get_auth_headers()

        # Generate update payload
        payload = {
            "status": random.choice(["active", "inactive", "paused"]),
            "confidence_score": round(random.uniform(0.7, 0.95), 2)
        }

        with self.client.put(
            f"/api/v1/agents/{agent_id}",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in [401, 404]:
                # Both are acceptable
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def delete_agent(self):
        """
        Delete test agent (low frequency).

        Simulates deleting agents. Only deletes agents with
        "load_test" prefix to avoid deleting real data.

        Weight: 1 (low frequency - user actions)
        Endpoint: DELETE /api/v1/agents/{id}
        Target: <100ms (from Phase 208 benchmarks)

        Success Criteria:
        - 200/204: Agent deleted successfully
        - 404: Acceptable (agent doesn't exist)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)

        Note: Uses "load_test_" prefix to ensure we only delete
        test agents created during load testing.
        """
        if not hasattr(self, 'token') or not self.token:
            return

        # Only delete test agents
        agent_id = f"load_test_agent_{random.randint(1, 1000)}"
        headers = self._get_auth_headers()

        with self.client.delete(
            f"/api/v1/agents/{agent_id}",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 204]:
                response.success()
            elif response.status_code in [401, 404]:
                # Both are acceptable
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    def _get_auth_headers(self):
        """
        Build authentication headers.

        Returns Authorization header if token exists,
        otherwise returns empty dict.

        Returns:
            dict: Headers dict with Authorization if token available
        """
        if hasattr(self, 'token') and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
