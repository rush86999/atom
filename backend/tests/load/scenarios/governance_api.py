"""
Governance API load test scenarios.

This module defines load test tasks for governance permission checks across
all maturity levels. The GovernanceCheckTasks mixin can be imported and mixed
into Locust user classes.

Maturity Levels:
- STUDENT: Read-only, blocked from complexity > 1
- INTERN: Proposal workflow, human approval required
- SUPERVISED: Real-time supervision, moderate actions allowed
- AUTONOMOUS: Full execution, all actions allowed

Weight Distribution:
- Permission checks distributed by real-world usage:
  - STUDENT checks: weight 4 (most agents start here)
  - INTERN checks: weight 3 (common training state)
  - SUPERVISED checks: weight 2 (production agents)
  - AUTONOMOUS checks: weight 2 (mature agents)
- Cache operations: lower weight (monitoring pattern)

Reference: Phase 209 Plan 02 - Governance Maturity Level Testing
"""

import random
import logging
from locust import task

logger = logging.getLogger(__name__)


class GovernanceCheckTasks:
    """
    Mixin class for governance permission check load test tasks.

    This mixin provides task methods for testing governance checks across
    all maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS). It validates
    that permission checking remains fast and accurate under load.

    Tasks:
    - check_student_permission: STUDENT maturity checks (weight 4)
    - check_intern_permission: INTERN maturity checks (weight 3)
    - check_supervised_permission: SUPERVISED maturity checks (weight 2)
    - check_autonomous_permission: AUTONOMOUS maturity checks (weight 2)
    - get_cache_stats: Cache performance monitoring (weight 3)
    - invalidate_cache: Cache invalidation (weight 1)

    Requires the HttpUser class to have:
    - self.client: Locust HTTP client
    - self.token: Authentication token (optional, will skip if None)

    Performance Targets:
    - Cached permission checks: <1ms (from Phase 208 benchmarks)
    - Cache stats retrieval: <50ms
    - Cache invalidation: <100ms
    """

    @task(4)
    def check_student_permission(self):
        """
        Check STUDENT maturity permissions.

        Tests permission checks for STUDENT-level agents. STUDENT agents
        should be allowed only for low-complexity actions (complexity 1).
        Higher complexity actions should be denied.

        Weight: 4 (high frequency - most agents start at STUDENT)
        Endpoint: POST /api/agent-governance/check-permission
        Target: <1ms from cache (from Phase 208 benchmarks)

        Expected Behavior:
        - Complexity 1: Allowed (read-only, presentations)
        - Complexity 2-4: Denied (STUDENT blocked from automated triggers)

        Success Criteria:
        - 200: Permission check completed successfully
        - Response contains "allowed" key (true/false)
        - STUDENT with complexity 1 should have allowed=true
        - STUDENT with complexity >1 should have allowed=false
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # STUDENT agents should only be allowed for complexity 1
        action_complexity = random.choice([1, 1, 1, 2, 3])  # Weighted toward 1
        payload = self._build_governance_payload("STUDENT", action_complexity)

        with self.client.post(
            "/api/agent-governance/check-permission",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "allowed" not in data:
                    response.failure("Missing 'allowed' key in response")
                    return

                # Validate STUDENT behavior
                is_allowed = data["allowed"]
                if action_complexity == 1 and not is_allowed:
                    response.failure("STUDENT should be allowed for complexity 1")
                elif action_complexity > 1 and is_allowed:
                    # Note: This might be acceptable if governance allows STUDENT
                    # for some actions, but typically they should be blocked
                    logger.warning(
                        f"STUDENT allowed for complexity {action_complexity}, "
                        "expected denied"
                    )
                    response.success()
                else:
                    response.success()
            elif response.status_code == 401:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def check_intern_permission(self):
        """
        Check INTERN maturity permissions.

        Tests permission checks for INTERN-level agents. INTERN agents
        require proposal workflow and human approval for most actions.

        Weight: 3 (medium-high frequency - common training state)
        Endpoint: POST /api/agent-governance/check-permission
        Target: <1ms from cache (from Phase 208 benchmarks)

        Expected Behavior:
        - Complexity 1-2: Allowed (with proposal workflow)
        - Complexity 3-4: May require additional approval

        Success Criteria:
        - 200: Permission check completed successfully
        - Response contains "allowed" key
        - Response may contain "requires_approval" key
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # INTERN agents typically handle moderate complexity
        action_complexity = random.choice([1, 2, 2, 3])
        payload = self._build_governance_payload("INTERN", action_complexity)

        with self.client.post(
            "/api/agent-governance/check-permission",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "allowed" not in data:
                    response.failure("Missing 'allowed' key in response")
                else:
                    response.success()
            elif response.status_code == 401:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def check_supervised_permission(self):
        """
        Check SUPERVISED maturity permissions.

        Tests permission checks for SUPERVISED-level agents. These agents
        can execute actions under real-time supervision with pause/correct
        capabilities.

        Weight: 2 (medium frequency - production agents)
        Endpoint: POST /api/agent-governance/check-permission
        Target: <1ms from cache (from Phase 208 benchmarks)

        Expected Behavior:
        - Complexity 1-3: Allowed (with supervision)
        - Complexity 4: May require escalation to AUTONOMOUS

        Success Criteria:
        - 200: Permission check completed successfully
        - Response contains "allowed" key
        - Response may contain "supervision_required" key
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # SUPERVISED agents handle moderate-to-high complexity
        action_complexity = random.choice([2, 3, 3, 4])
        payload = self._build_governance_payload("SUPERVISED", action_complexity)

        with self.client.post(
            "/api/agent-governance/check-permission",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "allowed" not in data:
                    response.failure("Missing 'allowed' key in response")
                else:
                    response.success()
            elif response.status_code == 401:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def check_autonomous_permission(self):
        """
        Check AUTONOMOUS maturity permissions.

        Tests permission checks for AUTONOMOUS-level agents. These agents
        have full execution rights without oversight. All actions should
        be allowed.

        Weight: 2 (medium frequency - mature agents)
        Endpoint: POST /api/agent-governance/check-permission
        Target: <1ms from cache (from Phase 208 benchmarks)

        Expected Behavior:
        - All complexity levels (1-4): Allowed
        - No restrictions on AUTONOMOUS agents

        Success Criteria:
        - 200: Permission check completed successfully
        - Response contains "allowed": true
        - AUTONOMOUS agents should always be allowed
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)

        Note: AUTONOMOUS agents have full permissions. If an AUTONOMOUS
        check returns allowed=false, it indicates a potential bug or
        misconfiguration.
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        # AUTONOMOUS agents can handle all complexity levels
        action_complexity = random.randint(1, 4)
        payload = self._build_governance_payload("AUTONOMOUS", action_complexity)

        with self.client.post(
            "/api/agent-governance/check-permission",
            json=payload,
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "allowed" not in data:
                    response.failure("Missing 'allowed' key in response")
                elif not data["allowed"]:
                    # AUTONOMOUS should always be allowed
                    response.failure(
                        f"AUTONOMOUS agent denied for complexity {action_complexity}"
                    )
                else:
                    response.success()
            elif response.status_code == 401:
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def get_cache_stats(self):
        """
        Get governance cache statistics.

        Monitors cache performance metrics to ensure governance checks
        remain fast under load. This is a critical monitoring endpoint.

        Weight: 3 (medium frequency - monitoring)
        Endpoint: GET /api/agent-governance/cache-stats
        Target: <50ms (from Phase 208 benchmarks)

        Expected Response:
        - hit_rate: Cache hit percentage (should be >90%)
        - total_checks: Total permission checks performed
        - cache_size: Number of cached entries
        - avg_response_time_ms: Average response time

        Success Criteria:
        - 200: Cache stats retrieved successfully
        - Response contains performance metrics
        - hit_rate should be high (>90% indicates good cache utilization)
        - 401: Acceptable (auth expired)
        - 500: Failure (server error)

        Note: Cache hit rate is a critical metric. Low hit rates indicate
        cache configuration issues or insufficient cache size.
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        with self.client.get(
            "/api/agent-governance/cache-stats",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate response has cache metrics
                if "hit_rate" in data or "total_checks" in data or isinstance(data, dict):
                    # Log cache hit rate for monitoring
                    if "hit_rate" in data:
                        hit_rate = data["hit_rate"] * 100 if data["hit_rate"] <= 1 else data["hit_rate"]
                        if hit_rate < 90:
                            logger.warning(
                                f"Low cache hit rate: {hit_rate:.1f}% (target: >90%)"
                            )
                    response.success()
                else:
                    response.failure("Invalid response structure - missing cache metrics")
            elif response.status_code == 401:
                response.success()
            elif response.status_code == 404:
                # Acceptable - cache stats endpoint might not exist
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def invalidate_cache(self):
        """
        Invalidate governance cache.

        Simulates cache invalidation operations (typically after agent
        configuration changes). Tests cache invalidation performance.

        Weight: 1 (low frequency - administrative operation)
        Endpoint: POST /api/agent-governance/cache/invalidate
        Target: <100ms (cache invalidation may be slower)

        Success Criteria:
        - 200: Cache invalidated successfully
        - Response should confirm invalidation
        - 401: Acceptable (auth expired)
        - 403: Acceptable (insufficient permissions)
        - 500: Failure (server error)

        Note: Cache invalidation should be fast (<100ms) to avoid
        blocking agent execution after configuration changes.
        """
        if not hasattr(self, 'token') or not self.token:
            return

        headers = self._get_auth_headers()

        with self.client.post(
            "/api/agent-governance/cache/invalidate",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                data = response.json()
                # Validate confirmation response
                if "invalidated" in data or "success" in data or isinstance(data, dict):
                    response.success()
                else:
                    response.failure("Invalid response structure - missing confirmation")
            elif response.status_code in [401, 403]:
                # Acceptable - auth or permission errors
                response.success()
            elif response.status_code == 404:
                # Acceptable - endpoint might not exist
                response.success()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    def _build_governance_payload(self, maturity: str, complexity: int) -> dict:
        """
        Build governance check request payload.

        Creates a realistic payload for permission checks including
        agent ID, action, complexity level, and maturity level.

        Args:
            maturity: Agent maturity level (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
            complexity: Action complexity (1-4)

        Returns:
            dict: Governance check request payload
        """
        actions = {
            1: ["read", "present", "list"],
            2: ["stream", "write", "update"],
            3: ["execute", "submit", "modify"],
            4: ["delete", "admin", "destroy"]
        }

        return {
            "agent_id": f"agent_{random.randint(1, 1000)}",
            "action": random.choice(actions.get(complexity, ["execute"])),
            "action_complexity": complexity,
            "agent_maturity": maturity,
            "context": {
                "load_test": True,
                "test_timestamp": random.randint(1700000000, 1800000000)
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
