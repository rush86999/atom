"""
Main Locust file for load testing Atom API endpoints.

This module defines Locust user scenarios for load testing critical API endpoints.
Each user class simulates realistic user behavior with authentication, wait times,
and weighted task frequencies.

Reference: Phase 209 Plan 01 - Locust Load Testing Infrastructure
"""

from locust import HttpUser, task, between, events
import logging
import random

logger = logging.getLogger(__name__)


class AtomAPIUser(HttpUser):
    """
    Base API user with authentication and health check tasks.

    This user simulates basic API interactions including authentication
    and health checks. All other user classes extend this base class.

    Behavior:
    - Authenticates on start using test credentials
    - Performs health checks (low frequency - monitoring)
    - Wait time: 1-3 seconds between tasks

    Authentication:
    - POST /api/v1/auth/login with test credentials
    - Stores access token for authenticated requests
    - Gracefully handles auth failures (continues without token)
    """

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """
        Authenticate when user starts.

        Called once when each user starts. Attempts to authenticate
        with test credentials and stores the access token if successful.
        Logs warning but continues if authentication fails.
        """
        self.login()

    def login(self):
        """
        Authenticate and store access token.

        Attempts to login with test credentials. If authentication succeeds,
        stores the access token in self.token for use in authenticated requests.
        If authentication fails, sets self.token to None and logs a warning.

        Note: Some endpoints don't require authentication, so load tests
        can continue even without a valid token.
        """
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "load_test@example.com",
                "password": "test_password_123"
            }
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            logger.info(f"User authenticated successfully: {self.token[:20] if self.token else 'None'}...")
        else:
            self.token = None
            logger.warning(
                f"Login failed with status {response.status_code}, "
                "proceeding without authentication"
            )

    @task(1)
    def health_check(self):
        """
        Health check endpoint (low frequency).

        Simulates monitoring systems checking application health.
        This is a lightweight endpoint that should respond quickly
        even under high load.

        Weight: 1 (low frequency - monitoring systems)
        Endpoint: GET /health/live
        """
        with self.client.get("/health/live", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: status {response.status_code}")


class AgentAPIUser(HttpUser):
    """
    Agent API load test scenario.

    Simulates realistic agent API usage patterns including listing agents,
    retrieving specific agents, and creating new agents.

    Behavior:
    - List agents (high frequency - every page load)
    - Get single agent (medium frequency - agent detail view)
    - Create agent (low frequency - user action)
    - Wait time: 1-3 seconds between tasks

    Weights: 5:3:1 (list:get:create)

    From Phase 208 benchmarks:
    - Agent list operations: <50ms target
    - Agent get operations: <50ms target
    - Agent creation: <100ms target
    """

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate before running tasks."""
        self.login()

    def login(self):
        """Authenticate and store access token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "load_test@example.com",
                "password": "test_password_123"
            }
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            self.token = None
            logger.warning("AgentAPIUser login failed, proceeding without auth")

    @task(5)
    def list_agents(self):
        """
        List agents (high frequency).

        Simulates loading the agents list page, which is one of the
        most common operations in the UI.

        Weight: 5 (most common - every page load)
        Endpoint: GET /api/v1/agents
        Target: <50ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        with self.client.get("/api/v1/agents", headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate response structure
                if "agents" in data or isinstance(data, list):
                    response.success()
                else:
                    response.failure("Invalid response structure")
            elif response.status_code == 401:
                # Auth errors are acceptable in load tests (token might expire)
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def get_agent(self):
        """
        Get specific agent (medium frequency).

        Simulates viewing agent details.

        Weight: 3 (medium frequency - detail views)
        Endpoint: GET /api/v1/agents/{id}
        Target: <50ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        agent_id = f"agent_{random.randint(1, 100)}"
        headers = {"Authorization": f"Bearer {self.token}"}

        self.client.get(f"/api/v1/agents/{agent_id}", headers=headers)

    @task(1)
    def create_agent(self):
        """
        Create new agent (low frequency).

        Simulates user creating a new agent.

        Weight: 1 (low frequency - user actions)
        Endpoint: POST /api/v1/agents
        Target: <100ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        self.client.post(
            "/api/v1/agents",
            json={
                "name": f"Load Test Agent {random.randint(1, 10000)}",
                "category": "test",
                "module_path": "test.module",
                "class_name": "TestClass",
                "maturity": "AUTONOMOUS"
            },
            headers=headers
        )


class WorkflowExecutionUser(HttpUser):
    """
    Workflow execution load test scenario.

    Simulates workflow execution heavy users. Focuses on workflow API
    endpoints with longer wait times to simulate realistic workflow
    execution duration.

    Behavior:
    - Execute workflow (high frequency - primary action)
    - List workflows (medium frequency)
    - Wait time: 2-5 seconds (longer for workflows)

    Weights: 2:1 (execute:list)

    From Phase 208 benchmarks:
    - Workflow execution: <100ms target
    - Workflow list: <50ms target
    """

    wait_time = between(2, 5)
    host = "http://localhost:8000"

    def on_start(self):
        """Initialize with authentication."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "load_test@example.com",
                "password": "test_password_123"
            }
        )
        self.token = response.json().get("access_token") if response.status_code == 200 else None

    @task(2)
    def execute_workflow(self):
        """
        Execute workflow (primary action).

        Simulates executing a workflow with test data.

        Weight: 2 (high frequency - primary action)
        Endpoint: POST /api/v1/workflows/{id}/execute
        Target: <100ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        workflow_id = f"test_workflow_{random.randint(1, 20):03d}"
        headers = {"Authorization": f"Bearer {self.token}"}

        self.client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json={"input_data": {"test": "value"}},
            headers=headers
        )

    @task(1)
    def list_workflows(self):
        """
        List workflows.

        Simulates browsing available workflows.

        Weight: 1 (medium frequency)
        Endpoint: GET /api/v1/workflows
        Target: <50ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/api/v1/workflows", headers=headers)


class GovernanceCheckUser(HttpUser):
    """
    Governance check load test scenario.

    Simulates governance permission checks which are critical for
    agent authorization. These checks should be very fast due to
    caching (<1ms target from Phase 208).

    Behavior:
    - Check permission (high frequency - every agent action)
    - Get cache stats (low frequency - monitoring)
    - Wait time: 1-3 seconds

    Weights: 4:2 (check:stats)

    From Phase 208 benchmarks:
    - Cached governance checks: <1ms target
    - Cache stats: <50ms target
    """

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Initialize with authentication."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "load_test@example.com",
                "password": "test_password_123"
            }
        )
        self.token = response.json().get("access_token") if response.status_code == 200 else None

    @task(4)
    def check_permission(self):
        """
        Check governance permission.

        Simulates checking if an agent has permission to perform an action.
        This is a high-frequency operation that should be cached.

        Weight: 4 (high frequency - every agent action)
        Endpoint: POST /api/agent-governance/check-permission
        Target: <1ms from cache (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        self.client.post(
            "/api/agent-governance/check-permission",
            json={
                "agent_id": f"agent_{random.randint(1, 100)}",
                "action": "test_action",
                "action_complexity": random.randint(1, 4)
            },
            headers=headers
        )

    @task(2)
    def get_cache_stats(self):
        """
        Get governance cache statistics.

        Simulates monitoring cache performance.

        Weight: 2 (low frequency - monitoring)
        Endpoint: GET /api/agent-governance/cache-stats
        Target: <50ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/api/agent-governance/cache-stats", headers=headers)


class EpisodeAPIUser(HttpUser):
    """
    Episode API load test scenario.

    Simulates episode retrieval operations for episodic memory system.
    Episodes are used for agent learning and context retrieval.

    Behavior:
    - List episodes (high frequency)
    - Get episode (medium frequency)
    - Wait time: 1-3 seconds

    Weights: 3:2 (list:get)

    From Phase 208 benchmarks:
    - Episode list: <50ms target
    - Episode get: <50ms target
    """

    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Initialize with authentication."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "load_test@example.com",
                "password": "test_password_123"
            }
        )
        self.token = response.json().get("access_token") if response.status_code == 200 else None

    @task(3)
    def list_episodes(self):
        """
        List episodes.

        Simulates browsing episode history for agent learning.

        Weight: 3 (high frequency)
        Endpoint: GET /api/v1/episodes
        Target: <50ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        with self.client.get("/api/v1/episodes", headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in [401, 403]:
                # Auth errors are acceptable
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def get_episode(self):
        """
        Get specific episode.

        Simulates retrieving episode details for context.

        Weight: 2 (medium frequency)
        Endpoint: GET /api/v1/episodes/{id}
        Target: <50ms (from Phase 208 benchmarks)
        """
        if not self.token:
            return

        episode_id = f"test_episode_{random.randint(1, 50):03d}"
        headers = {"Authorization": f"Bearer {self.token}"}

        self.client.get(f"/api/v1/episodes/{episode_id}", headers=headers)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Log test completion.

    Called when load test completes. Logs summary statistics.
    """
    from locust.runners import MasterRunner

    if isinstance(environment.runner, MasterRunner):
        logger.info("Load test completed")
        logger.info(f"Total requests: {environment.runner.stats.total.num_requests}")
        logger.info(f"Failures: {environment.runner.stats.total.num_failures}")
        logger.info(f"RPS: {environment.runner.stats.total.total_rps}")
        logger.info(f"Avg response time: {environment.runner.stats.total.avg_response_time}ms")
