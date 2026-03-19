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
