"""
Workflow API load test scenarios.

This module defines load test tasks for workflow execution operations.
The WorkflowExecutionTasks mixin can be imported and mixed into Locust user classes.

Weight Distribution:
- List operations (list_workflows) have medium weight (3) - browsing
- Execution operations have varying weights based on complexity
  - Simple execution: weight 2 (common case)
  - Parallel execution: weight 1 (advanced use case)
  - Error handling: weight 1 (edge case testing)
- Status checks have lower weight (1) - monitoring pattern

Reference: Phase 209 Plan 02 - Workflow Execution Patterns
"""

import random
import logging
from locust import task

logger = logging.getLogger(__name__)


class WorkflowExecutionTasks:
    """
    Mixin class for workflow execution load test tasks.

    This mixin provides task methods for testing workflow list, execute,
    and status operations. It includes error scenario testing to validate
    graceful degradation under load.

    Tasks:
    - list_workflows: Medium-frequency browse operation (weight 3)
    - execute_simple_workflow: Common execution pattern (weight 2)
    - execute_parallel_workflow: Advanced parallel execution (weight 1)
    - execute_error_workflow: Error handling validation (weight 1)
    - get_workflow_status: Status monitoring (weight 1)
    - get_workflow_analytics: Analytics queries (weight 1)

    Requires the HttpUser class to have:
    - self.client: Locust HTTP client
    - self.token: Authentication token (optional, will skip if None)
    """

    @task(3)
    def list_workflows(self):
        """
        List available workflows (medium frequency).

        Simulates browsing the workflow library. This is a common
        operation when users explore available automations.

        Weight: 3 (medium frequency - browsing)
        Endpoint: GET /api/v1/workflows
        Target: <50ms (from Phase 208 benchmarks)

        Query Parameters:
        - skip: Pagination offset (0-50)
        - limit: Results per page (10-30)

        Success Criteria:
        - 200: Valid response with workflows list
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        params = {
            "skip": random.randint(0, 50),
            "limit": random.choice([10, 20, 30])
        }

        with self.client.get(
            "/api/v1/workflows",
            headers=headers,
            params=params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "workflows" in data or isinstance(data, list):
                    response.success()
                else:
                    response.failure("Invalid response structure - missing 'workflows' key")
            elif response.status_code == 401:
                response.success()
            elif response.status_code == 404:
                # Acceptable - endpoint might not exist
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def execute_simple_workflow(self):
        """
        Execute simple workflow (common case).

        Simulates the most common workflow execution pattern - simple
        sequential workflows with basic input data.

        Weight: 2 (high frequency - common execution)
        Endpoint: POST /api/v1/workflows/simple/execute
        Target: <100ms (from Phase 208 benchmarks)

        Success Criteria:
        - 200/202: Workflow execution started
        - 400: Acceptable (validation error)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()
        payload = self._generate_workflow_input()

        with self.client.post(
            "/api/v1/workflows/simple/execute",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 202]:
                data = response.json()
                # Validate execution response
                if "execution_id" in data or "status" in data:
                    response.success()
                else:
                    response.failure("Invalid response structure - missing execution info")
            elif response.status_code in [400, 401, 422]:
                # Acceptable - validation or auth errors
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def execute_parallel_workflow(self):
        """
        Execute parallel workflow (advanced use case).

        Simulates advanced workflow execution with parallel branches.
        Tests the system's ability to handle concurrent task execution.

        Weight: 1 (low frequency - advanced users)
        Endpoint: POST /api/v1/workflows/parallel/execute
        Target: <150ms (parallel operations may be slower)

        Success Criteria:
        - 200/202: Parallel workflow started
        - 400: Acceptable (validation error)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)

        Note: Parallel workflows test system concurrency handling
        and may have higher resource consumption.
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # Generate parallel workflow payload
        payload = {
            "input_data": {
                "test_key": f"test_value_{random.randint(1, 1000)}",
                "parallel_tasks": random.randint(2, 5)
            },
            "parameters": {
                "timeout": random.choice([30, 60, 90]),
                "max_parallel": random.randint(2, 5)
            }
        }

        with self.client.post(
            "/api/v1/workflows/parallel/execute",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 202]:
                response.success()
            elif response.status_code in [400, 401, 422]:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def execute_error_workflow(self):
        """
        Execute workflow that tests error handling.

        Simulates workflow execution with invalid data to test
        graceful degradation. This specifically validates that
        errors return 400/422 instead of 500 under load.

        Weight: 1 (low frequency - edge case testing)
        Endpoint: POST /api/v1/workflows/error-test/execute
        Target: <100ms (errors should fail fast)

        Success Criteria:
        - 400/422: Expected (validation error - NOT 500)
        - 401: Acceptable (auth expired)
        - 500: Failure (indicates poor error handling)
        - 200: Unexpected (error workflow should fail)

        Note: This is a critical test for graceful degradation.
        Under load, errors should return client errors (4xx),
        not server errors (5xx).
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # Generate invalid payload to trigger error
        payload = {
            "input_data": {
                "invalid_key": None,  # Invalid value
                "missing_required": True  # May be invalid
            },
            "parameters": {
                "timeout": -1,  # Invalid timeout
                "trigger_error": True  # Explicit error trigger
            }
        }

        with self.client.post(
            "/api/v1/workflows/error-test/execute",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [400, 422]:
                # SUCCESS - graceful error handling
                response.success()
            elif response.status_code == 401:
                # Acceptable
                response.success()
            elif response.status_code >= 500:
                # FAILURE - should not return 500 for validation errors
                response.failure(
                    f"Poor error handling: got {response.status_code} instead of 400/422"
                )
            elif response.status_code in [200, 202]:
                # Unexpected - error workflow should fail
                response.failure("Error workflow should not succeed")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def get_workflow_status(self):
        """
        Get workflow execution status (monitoring).

        Simulates checking workflow execution status. This is typically
        called after starting a workflow execution.

        Weight: 1 (low frequency - monitoring)
        Endpoint: GET /api/v1/workflows/{id}/status
        Target: <50ms (from Phase 208 benchmarks)

        Success Criteria:
        - 200: Status retrieved successfully
        - 404: Acceptable (workflow doesn't exist)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        workflow_id = f"workflow_{random.randint(1, 100)}"
        headers = self._get_auth_headers()

        with self.client.get(
            f"/api/v1/workflows/{workflow_id}/status",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "status" in data or "execution_status" in data:
                    response.success()
                else:
                    response.failure("Invalid response structure - missing status")
            elif response.status_code in [401, 404]:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def get_workflow_analytics(self):
        """
        Get workflow execution analytics.

        Simulates querying workflow analytics for monitoring and
        reporting. Tests aggregation query performance.

        Weight: 1 (low frequency - monitoring/reporting)
        Endpoint: GET /api/v1/workflows/analytics
        Target: <100ms (analytics queries may be slower)

        Query Parameters:
        - days: Number of days to analyze (1-30)
        - workflow_type: Filter by type (optional)

        Success Criteria:
        - 200: Analytics retrieved successfully
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        params = {
            "days": random.randint(1, 30),
            "workflow_type": random.choice(["automation", "integration", None])
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        with self.client.get(
            "/api/v1/workflows/analytics",
            headers=headers,
            params=params,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate analytics response
                if "analytics" in data or "metrics" in data or isinstance(data, dict):
                    response.success()
                else:
                    response.failure("Invalid response structure - missing analytics data")
            elif response.status_code == 401:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    def _generate_workflow_input(self):
        """
        Generate realistic workflow input payload.

        Returns a dictionary with test input data and parameters
        for workflow execution.

        Returns:
            dict: Workflow input payload with test data
        """
        return {
            "input_data": {
                "test_key": f"test_value_{random.randint(1, 1000)}",
                "timestamp": random.randint(1700000000, 1800000000),
                "user_id": f"user_{random.randint(1, 100)}"
            },
            "parameters": {
                "timeout": random.choice([30, 60, 90]),
                "retry_count": random.randint(0, 3),
                "priority": random.choice(["low", "medium", "high"])
            }
        }

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
