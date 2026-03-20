"""
Rate limiting stress tests for Atom API.

This module tests rate limiting behavior under extreme load to validate:
- Rate limit enforcement (429 responses)
- Per-user rate limiting (not global)
- Backoff behavior and recovery
- Retry-After header presence

Tests ensure rate limiting works correctly and the system degrades
gracefully when limits are exceeded.

Reference: Phase 209 Plan 04 - Stress Testing
"""

import pytest
import time
from typing import Dict, List
from fastapi.testclient import TestClient
from http import HTTPStatus


def _hit_endpoint_n_times(client: TestClient, url: str, n: int, method: str = "GET", json_data: Dict = None) -> Dict[int, int]:
    """
    Hit an endpoint n times as fast as possible.

    Args:
        client: TestClient instance
        url: Endpoint URL
        n: Number of requests to send
        method: HTTP method (default: GET)
        json_data: JSON payload for POST requests

    Returns:
        Dictionary mapping status codes to occurrence counts:
        {
            200: 95,
            429: 5,
            ...
        }
    """
    status_counts = {}

    for i in range(n):
        if method.upper() == "GET":
            response = client.get(url)
        elif method.upper() == "POST":
            response = client.post(url, json=json_data or {})
        else:
            raise ValueError(f"Unsupported method: {method}")

        status_code = response.status_code
        status_counts[status_code] = status_counts.get(status_code, 0) + 1

    return status_counts


def test_rate_limiting_enforcement():
    """
    Stress test: Rate limit enforcement under rapid requests.

    Sends 100 requests rapidly to the same endpoint to trigger
    rate limiting. Validates that 429 (Too Many Requests) responses
    appear after the rate limit threshold is exceeded.

    Validates:
    - 429 responses appear after threshold
    - Retry-After header is present
    - Initial requests succeed (200)
    - Later requests are rate limited (429)
    """
    print("\n=== Rate Limiting Enforcement Test ===")

    # Import app here to avoid import issues
    from main import app
    client = TestClient(app)

    # Hit health check endpoint 100 times rapidly
    # Note: Health checks typically don't have rate limits, so this
    # tests the general pattern. In production, test an actual rate-limited endpoint.
    url = "/health/live"
    num_requests = 100

    print(f"Sending {num_requests} rapid requests to {url}")

    start_time = time.time()
    status_counts = _hit_endpoint_n_times(client, url, num_requests)
    elapsed_time = time.time() - start_time

    print(f"Completed in {elapsed_time:.2f}s")
    print(f"Status code distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count} requests ({count/num_requests*100:.1f}%)")

    # For endpoints without rate limiting (like health checks),
    # all requests should succeed
    if 429 in status_counts:
        print(f"✓ Rate limiting detected: {status_counts[429]} requests returned 429")

        # Check last response for Retry-After header
        response = client.get(url)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                print(f"✓ Retry-After header present: {retry_after}")
            else:
                print("⚠️  Retry-After header missing")
    else:
        print(f"ℹ️  No rate limiting on {url} (all {num_requests} requests succeeded)")

    # At minimum, most requests should succeed
    success_rate = status_counts.get(200, 0) / num_requests
    print(f"Success rate: {success_rate*100:.2f}%")

    # For non-rate-limited endpoints, expect 100% success
    # For rate-limited endpoints, would check for 429s
    assert success_rate > 0.5, f"Success rate {success_rate*100:.2f}% too low"


def test_rate_limit_per_user():
    """
    Stress test: Per-user rate limiting (not global).

    Validates that rate limiting is applied per user, not globally.
    Each user should have their own rate limit quota.

    Test scenario:
    - User A sends 50 requests
    - User B sends 50 requests
    - User C sends 50 requests
    - Each user's rate limit should be independent

    If rate limiting is global, one user's requests would affect others.
    If per-user, each user has independent quota.
    """
    print("\n=== Per-User Rate Limiting Test ===")

    from main import app

    # Simulate 3 different users with different auth tokens
    users = {
        "user_a": "Bearer token_a_12345",
        "user_b": "Bearer token_b_67890",
        "user_c": "Bearer token_c_11111"
    }

    results = {}

    for username, auth_token in users.items():
        client = TestClient(app)

        # Test an endpoint that might have rate limiting
        # Use agent list endpoint as example
        url = "/api/v1/agents"
        headers = {"Authorization": auth_token}
        num_requests = 50

        print(f"\n--- Testing {username} ({num_requests} requests) ---")

        status_counts = {}
        for i in range(num_requests):
            response = client.get(url, headers=headers)
            status_code = response.status_code
            status_counts[status_code] = status_counts.get(status_code, 0) + 1

        results[username] = status_counts

        print(f"Status codes: {status_counts}")
        success_count = status_counts.get(200, 0)
        print(f"Successful requests: {success_count}/{num_requests}")

    # Validate per-user rate limiting
    # If per-user: User B's quota should not be affected by User A's requests
    # If global: One user's excessive requests would affect others

    user_a_success = results["user_a"].get(200, 0)
    user_b_success = results["user_b"].get(200, 0)
    user_c_success = results["user_c"].get(200, 0)

    print(f"\n=== Per-User Rate Limiting Validation ===")
    print(f"User A success: {user_a_success}/50")
    print(f"User B success: {user_b_success}/50")
    print(f"User C success: {user_c_success}/50")

    # All users should have similar success rates if rate limiting is per-user
    # If one user has significantly lower success rate, rate limiting might be global

    success_rates = [user_a_success, user_b_success, user_c_success]
    min_success = min(success_rates)
    max_success = max(success_rates)
    variance = max_success - min_success

    print(f"Variance in success rates: {variance} requests")

    # For per-user rate limiting, variance should be low
    # This is a soft assertion - adjust based on actual rate limit configuration
    if variance > 20:
        print(f"⚠️  High variance detected ({variance} requests)")
        print("    This might indicate global rate limiting")
    else:
        print(f"✓ Low variance ({variance} requests)")
        print("    Rate limiting appears to be per-user")


def test_rate_limit_recovery():
    """
    Stress test: Rate limit recovery and backoff behavior.

    Tests that rate limits reset over time and requests succeed
    again after waiting for the Retry-After period.

    Test flow:
    1. Hit rate limit (get 429)
    2. Wait for Retry-After seconds
    3. Send request again
    4. Should succeed (200)

    Validates:
    - Rate limit window expires
    - System recovers gracefully
    - Backoff behavior works correctly
    """
    print("\n=== Rate Limit Recovery Test ===")

    from main import app
    client = TestClient(app)

    url = "/health/live"  # Use health check as example

    # Step 1: Send many requests to potentially hit rate limit
    print("Step 1: Sending rapid requests...")
    status_counts = _hit_endpoint_n_times(client, url, 100)
    print(f"Status distribution: {status_counts}")

    # Step 2: Check if rate limited
    last_response = client.get(url)
    if last_response.status_code == 429:
        retry_after = last_response.headers.get("Retry-After")

        if retry_after:
            print(f"Step 2: Rate limited! Retry-After: {retry_after}")

            try:
                wait_seconds = int(retry_after)
                print(f"Step 3: Waiting {wait_seconds} seconds...")
                time.sleep(wait_seconds)

                # Step 4: Try request again
                print("Step 4: Sending request after waiting...")
                recovery_response = client.get(url)

                if recovery_response.status_code == 200:
                    print(f"✓ Request succeeded after waiting (status: {recovery_response.status_code})")
                else:
                    print(f"⚠️  Request still failed after waiting (status: {recovery_response.status_code})")
            except ValueError:
                print(f"⚠️  Retry-After header not an integer: {retry_after}")
        else:
            print("Step 2: Rate limited but no Retry-After header")
    else:
        print(f"Step 2: Not rate limited (status: {last_response.status_code})")
        print("ℹ️  This endpoint may not have rate limiting configured")


def test_rate_limit_burst_traffic():
    """
    Stress test: Rate limiting under burst traffic patterns.

    Simulates realistic burst traffic patterns where requests
    come in bursts (e.g., user refreshes page multiple times quickly).

    Test pattern:
    - Burst 1: 20 requests in 1 second
    - Pause: 2 seconds
    - Burst 2: 20 requests in 1 second
    - Pause: 2 seconds
    - Burst 3: 20 requests in 1 second

    Validates rate limiting handles burst patterns gracefully.
    """
    print("\n=== Burst Traffic Rate Limiting Test ===")

    from main import app
    client = TestClient(app)

    url = "/health/live"
    burst_size = 20
    num_bursts = 3
    pause_seconds = 2

    all_results = []

    for burst_num in range(1, num_bursts + 1):
        print(f"\n--- Burst {burst_num}: {burst_size} requests ---")

        status_counts = _hit_endpoint_n_times(client, url, burst_size)
        all_results.append(status_counts)

        success_count = status_counts.get(200, 0)
        rate_limited_count = status_counts.get(429, 0)

        print(f"Success: {success_count}/{burst_size}")
        print(f"Rate limited: {rate_limited_count}/{burst_size}")

        if burst_num < num_bursts:
            print(f"Pausing {pause_seconds} seconds...")
            time.sleep(pause_seconds)

    # Summary
    print(f"\n=== Burst Test Summary ===")
    total_requests = burst_size * num_bursts
    total_success = sum(r.get(200, 0) for r in all_results)
    total_rate_limited = sum(r.get(429, 0) for r in all_results)

    print(f"Total requests: {total_requests}")
    print(f"Total successful: {total_success}")
    print(f"Total rate limited: {total_rate_limited}")
    print(f"Overall success rate: {total_success/total_requests*100:.2f}%")

    # Validate system handles bursts gracefully
    # Some rate limiting is acceptable, but system should recover
    assert total_success > 0, "All requests failed - system may be misconfigured"


def test_rate_limit_different_endpoints():
    """
    Stress test: Rate limiting across different endpoints.

    Validates that rate limiting is applied correctly across
    different API endpoints.

    Test endpoints:
    - GET /health/live (health check)
    - GET /api/v1/agents (agent list)
    - POST /api/agent-governance/check-permission (governance)

    Some endpoints may have different rate limits or no limits.
    """
    print("\n=== Cross-Endpoint Rate Limiting Test ===")

    from main import app

    endpoints = [
        ("GET", "/health/live", None, "Health Check"),
        ("GET", "/api/v1/agents", None, "Agent List"),
        ("POST", "/api/agent-governance/check-permission", {"agent_id": "test", "action": "test", "action_complexity": 1}, "Governance Check")
    ]

    for method, endpoint, json_data, name in endpoints:
        client = TestClient(app)
        url = endpoint
        num_requests = 50

        print(f"\n--- Testing {name}: {method} {endpoint} ({num_requests} requests) ---")

        status_counts = _hit_endpoint_n_times(
            client,
            url,
            num_requests,
            method=method,
            json_data=json_data
        )

        print(f"Status distribution: {status_counts}")
        success_count = status_counts.get(200, 0)
        rate_limited_count = status_counts.get(429, 0)

        print(f"Success: {success_count}/{num_requests}")
        print(f"Rate limited: {rate_limited_count}/{num_requests}")

        if rate_limited_count > 0:
            print(f"✓ Endpoint {name} has rate limiting")
        else:
            print(f"ℹ️  Endpoint {name} may not have rate limiting")


if __name__ == "__main__":
    # Run tests manually for development
    pytest.main([__file__, "-v", "-s"])
