"""
Main Locust file for load testing Atom API endpoints.

This module defines Locust user scenarios for load testing critical API endpoints.
Each user class simulates realistic user behavior with authentication, wait times,
and weighted task frequencies.

Reference: Phase 209 Plan 01 - Locust Load Testing Infrastructure
Reference: Phase 209 Plan 02 - Extended Scenario Mixins
"""

from locust import HttpUser, task, between, events
import logging
import random

# Import scenario mixins for modular load testing
import sys
from pathlib import Path
# Add scenarios directory to path for imports
scenarios_dir = Path(__file__).parent / "scenarios"
sys.path.insert(0, str(scenarios_dir))

from agent_api import AgentCRUDTasks
from workflow_api import WorkflowExecutionTasks
from governance_api import GovernanceCheckTasks

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


class AgentAPIUser(HttpUser, AgentCRUDTasks):
    """
    Agent API load test scenario.

    Simulates realistic agent API usage patterns including listing agents,
    retrieving specific agents, creating, updating, and deleting agents.

    Behavior:
    - List agents (high frequency - every page load)
    - Get single agent (medium frequency - agent detail view)
    - Create/update/delete agents (low frequency - user actions)
    - Wait time: 1-3 seconds between tasks

    Weights: 5:3:1:1:1 (list:get:create:update:delete)

    From Phase 208 benchmarks:
    - Agent list operations: <50ms target
    - Agent get operations: <50ms target
    - Agent create/update/delete: <100ms target

    Uses AgentCRUDTasks mixin for task implementations.
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


class WorkflowExecutionUser(HttpUser, WorkflowExecutionTasks):
    """
    Workflow execution load test scenario.

    Simulates workflow execution heavy users. Focuses on workflow API
    endpoints with longer wait times to simulate realistic workflow
    execution duration.

    Behavior:
    - List workflows (medium frequency - browsing)
    - Execute workflows (high frequency - primary action)
    - Execute parallel workflows (low frequency - advanced users)
    - Test error workflows (low frequency - edge case testing)
    - Check workflow status (medium frequency - monitoring)
    - Query workflow analytics (low frequency - reporting)
    - Wait time: 2-5 seconds (longer for workflows)

    Weights: 3:2:1:1:1:1 (list:simple:parallel:error:status:analytics)

    From Phase 208 benchmarks:
    - Workflow execution: <100ms target
    - Workflow list: <50ms target

    Uses WorkflowExecutionTasks mixin for task implementations.
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


class GovernanceCheckUser(HttpUser, GovernanceCheckTasks):
    """
    Governance check load test scenario.

    Simulates governance permission checks which are critical for
    agent authorization. These checks should be very fast due to
    caching (<1ms target from Phase 208).

    Behavior:
    - Check permissions for all maturity levels (high frequency)
    - Get cache stats (medium frequency - monitoring)
    - Invalidate cache (low frequency - admin operations)
    - Wait time: 1-3 seconds

    Weights: 4:3:2:2:3:1 (student:intern:supervised:autonomous:stats:invalidate)

    From Phase 208 benchmarks:
    - Cached governance checks: <1ms target
    - Cache stats: <50ms target

    Uses GovernanceCheckTasks mixin for task implementations.
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


class ComprehensiveUser(HttpUser, AgentCRUDTasks, WorkflowExecutionTasks, GovernanceCheckTasks):
    """
    Comprehensive power user load test scenario.

    Simulates advanced users who interact with all major API endpoints.
    This combines all scenario mixins to test the system under realistic
    mixed load patterns.

    Behavior:
    - Agent CRUD operations (list, get, create, update, delete)
    - Workflow execution (simple, parallel, error handling, status, analytics)
    - Governance checks (all 4 maturity levels, cache operations)
    - Wait time: 1-4 seconds (mixed usage patterns)

    Weights: Combined from all mixins
    - Agent operations: 5:3:1:1:1 (list:get:create:update:delete)
    - Workflow operations: 3:2:1:1:1:1 (list:simple:parallel:error:status:analytics)
    - Governance operations: 4:3:2:2:3:1 (student:intern:supervised:autonomous:stats:invalidate)

    Use Case:
    - Testing overall system performance under mixed load
    - Simulating power users who use multiple features
    - Validating that different subsystems don't interfere with each other

    From Phase 208 benchmarks:
    - All operations should meet their individual targets
    - No performance degradation when features are used together

    Uses all three mixins (AgentCRUDTasks, WorkflowExecutionTasks, GovernanceCheckTasks).
    """

    wait_time = between(1, 4)
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
