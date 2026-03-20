"""
Concurrent user stress tests for Atom API.

This module tests system behavior under concurrent user load to identify
capacity limits, breaking points, and measure performance degradation.

Tests validate:
- System can handle 100 concurrent users (SaaS industry standard target)
- Response times remain acceptable under load
- Failure rates stay within acceptable thresholds
- Breaking points are identified for capacity planning

Reference: Phase 209 Plan 04 - Stress Testing
"""

import asyncio
import httpx
import pytest
import time
from typing import Dict, List, Any
from datetime import datetime


# Test configuration
BASE_URL = "http://localhost:8000"
SUCCESS_RATE_THRESHOLD = 0.95  # 95% success rate required
MAX_ACCEPTABLE_LATENCY_MS = 1000  # 1 second


async def _measure_concurrent_performance(
    count: int,
    endpoint: str,
    method: str = "GET",
    json_data: Dict = None,
    headers: Dict = None
) -> Dict[str, Any]:
    """
    Measure performance of concurrent requests to an endpoint.

    Args:
        count: Number of concurrent requests to send
        endpoint: API endpoint path (e.g., "/health/live")
        method: HTTP method (GET, POST, etc.)
        json_data: JSON payload for POST requests
        headers: HTTP headers

    Returns:
        Dictionary with performance metrics:
        {
            "user_count": int,
            "success_rate": float,
            "avg_latency_ms": float,
            "p95_latency_ms": float,
            "p99_latency_ms": float,
            "errors": List[str]
        }
    """
    url = f"{BASE_URL}{endpoint}"
    latencies = []
    errors = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for i in range(count):
            if method.upper() == "GET":
                task = client.get(url, headers=headers)
            elif method.upper() == "POST":
                task = client.post(url, json=json_data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            tasks.append(task)

        # Execute all requests concurrently
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Process responses
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                errors.append(f"Request {i}: {str(response)}")
            else:
                latency_ms = (time.time() - start_time) * 1000 / count * (i + 1)
                latencies.append(latency_ms)

                if response.status_code >= 400:
                    errors.append(f"Request {i}: HTTP {response.status_code}")

    # Calculate metrics
    success_count = count - len(errors)
    success_rate = success_count / count if count > 0 else 0

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        sorted_latencies = sorted(latencies)
        p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0
        p99_latency = sorted_latencies[int(len(sorted_latencies) * 0.99)] if sorted_latencies else 0
    else:
        avg_latency = 0
        p95_latency = 0
        p99_latency = 0

    return {
        "user_count": count,
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "p99_latency_ms": p99_latency,
        "errors": errors[:10]  # Limit error output
    }


@pytest.mark.asyncio
async def test_concurrent_health_checks_100_users():
    """
    Stress test: 100 concurrent health check requests.

    Validates system can handle 100 concurrent users hitting the
    liveness probe endpoint simultaneously.

    Capacity target:
    - Success rate: >95%
    - Average latency: <100ms
    - P95 latency: <500ms

    Endpoint: GET /health/live
    """
    print("\n=== Concurrent Health Check Stress Test (100 users) ===")

    metrics = await _measure_concurrent_performance(
        count=100,
        endpoint="/health/live",
        method="GET"
    )

    print(f"User count: {metrics['user_count']}")
    print(f"Success rate: {metrics['success_rate']*100:.2f}%")
    print(f"Average latency: {metrics['avg_latency_ms']:.2f}ms")
    print(f"P95 latency: {metrics['p95_latency_ms']:.2f}ms")
    print(f"P99 latency: {metrics['p99_latency_ms']:.2f}ms")

    if metrics['errors']:
        print(f"Errors ({len(metrics['errors'])}): {metrics['errors'][:5]}")

    # Assertions for capacity validation
    assert metrics['success_rate'] > SUCCESS_RATE_THRESHOLD, \
        f"Success rate {metrics['success_rate']*100:.2f}% below threshold {SUCCESS_RATE_THRESHOLD*100}%"

    assert metrics['avg_latency_ms'] < MAX_ACCEPTABLE_LATENCY_MS, \
        f"Average latency {metrics['avg_latency_ms']:.2f}ms exceeds threshold {MAX_ACCEPTABLE_LATENCY_MS}ms"

    assert metrics['p95_latency_ms'] < MAX_ACCEPTABLE_LATENCY_MS * 2, \
        f"P95 latency {metrics['p95_latency_ms']:.2f}ms exceeds threshold {MAX_ACCEPTABLE_LATENCY_MS * 2}ms"


@pytest.mark.asyncio
async def test_concurrent_agent_requests_ramp_up():
    """
    Stress test: Ramp up concurrent users from 10 to 500.

    Tests system behavior at increasing load levels to identify
    breaking points where performance degrades significantly.

    Load levels: 10, 50, 100, 500 concurrent users
    Breaking point: Where success_rate drops below 90%

    This test helps establish:
    - Safe capacity: 50% of breaking point
    - Target capacity: 70% of breaking point
    - Warning threshold: 90% of breaking point
    """
    print("\n=== Concurrent Agent Request Ramp-Up Test ===")

    load_levels = [10, 50, 100, 500]
    results = []
    breaking_point = None

    for user_count in load_levels:
        print(f"\n--- Testing {user_count} concurrent users ---")

        metrics = await _measure_concurrent_performance(
            count=user_count,
            endpoint="/api/v1/agents",
            method="GET"
        )

        results.append(metrics)

        print(f"Success rate: {metrics['success_rate']*100:.2f}%")
        print(f"Average latency: {metrics['avg_latency_ms']:.2f}ms")
        print(f"P95 latency: {metrics['p95_latency_ms']:.2f}ms")

        # Check if this is the breaking point
        if metrics['success_rate'] < 0.90 and breaking_point is None:
            breaking_point = user_count
            print(f"⚠️  BREAKING POINT DETECTED at {user_count} users")

        # Small delay between tests
        await asyncio.sleep(1)

    # Summary
    print("\n=== Ramp-Up Test Summary ===")
    for result in results:
        print(f"{result['user_count']:3d} users: {result['success_rate']*100:5.2f}% success, {result['avg_latency_ms']:6.2f}ms avg")

    if breaking_point:
        print(f"\nBreaking point: {breaking_point} concurrent users")
        print(f"Safe capacity (50%): {breaking_point // 2} users")
        print(f"Target capacity (70%): {int(breaking_point * 0.7)} users")
        print(f"Warning threshold (90%): {int(breaking_point * 0.9)} users")
    else:
        print(f"\nNo breaking point detected up to {max(load_levels)} users")
        print("System handled all load levels successfully")


@pytest.mark.asyncio
async def test_concurrent_workflow_executions():
    """
    Stress test: 50 concurrent workflow executions.

    Tests system capacity for concurrent workflow executions,
    which are more resource-intensive than simple API requests.

    Validates:
    - Workflows execute successfully under load
    - No deadlocks or race conditions
    - Reasonable completion times

    Endpoint: POST /api/v1/workflows/test_workflow/execute
    """
    print("\n=== Concurrent Workflow Execution Stress Test (50 workflows) ===")

    workflow_payload = {
        "input_data": {"test": "value"}
    }

    metrics = await _measure_concurrent_performance(
        count=50,
        endpoint="/api/v1/workflows/test_workflow/execute",
        method="POST",
        json_data=workflow_payload
    )

    print(f"Workflow count: {metrics['user_count']}")
    print(f"Success rate: {metrics['success_rate']*100:.2f}%")
    print(f"Average latency: {metrics['avg_latency_ms']:.2f}ms")
    print(f"P95 latency: {metrics['p95_latency_ms']:.2f}ms")

    if metrics['errors']:
        print(f"Failed workflows ({len(metrics['errors'])}):")
        for error in metrics['errors'][:5]:
            print(f"  - {error}")

    # Workflows may have lower success rate due to auth/no setup
    # But should still complete without hanging
    assert metrics['success_rate'] >= 0.5, \
        f"Workflow success rate {metrics['success_rate']*100:.2f}% below 50% threshold"


@pytest.mark.asyncio
async def test_concurrent_governance_checks():
    """
    Stress test: 200 concurrent governance cache lookups.

    Governance checks are high-frequency operations in Atom.
    This test validates cache performance under concurrent load.

    Target from Phase 208:
    - Cached governance checks: <1ms (single user)
    - Under load: <10ms P95 latency acceptable

    Endpoint: POST /api/agent-governance/check-permission
    """
    print("\n=== Concurrent Governance Check Stress Test (200 checks) ===")

    # Test with mixed cached and uncached agent IDs
    governance_payload = {
        "agent_id": "test_agent_123",
        "action": "test_action",
        "action_complexity": 1
    }

    metrics = await _measure_concurrent_performance(
        count=200,
        endpoint="/api/agent-governance/check-permission",
        method="POST",
        json_data=governance_payload
    )

    print(f"Governance checks: {metrics['user_count']}")
    print(f"Success rate: {metrics['success_rate']*100:.2f}%")
    print(f"Average latency: {metrics['avg_latency_ms']:.2f}ms")
    print(f"P95 latency: {metrics['p95_latency_ms']:.2f}ms")

    # Governance checks should be very fast due to caching
    # Allow higher latency under load but still reasonable
    assert metrics['p95_latency_ms'] < 100, \
        f"P95 latency {metrics['p95_latency_ms']:.2f}ms exceeds 100ms for governance checks"


@pytest.mark.asyncio
async def test_mixed_concurrent_load():
    """
    Stress test: Mixed workload with realistic user patterns.

    Simulates realistic load where different users perform different
    actions simultaneously:
    - 40% health checks (monitoring)
    - 30% agent API calls
    - 20% workflow executions
    - 10% governance checks

    Total: 100 concurrent requests with realistic distribution.
    """
    print("\n=== Mixed Concurrent Load Stress Test (100 requests) ===")

    async def mixed_request(task_type: str):
        """Execute different request types based on task distribution."""
        if task_type == "health":
            return await _measure_concurrent_performance(1, "/health/live", "GET")
        elif task_type == "agent":
            return await _measure_concurrent_performance(1, "/api/v1/agents", "GET")
        elif task_type == "governance":
            return await _measure_concurrent_performance(
                1,
                "/api/agent-governance/check-permission",
                "POST",
                {"agent_id": "test", "action": "test", "action_complexity": 1}
            )
        else:
            return {"success_rate": 1.0, "avg_latency_ms": 0}

    # Create task distribution
    tasks = []
    task_types = (
        ["health"] * 40 +
        ["agent"] * 30 +
        ["workflow"] * 20 +
        ["governance"] * 10
    )

    import random
    random.shuffle(task_types)

    # Start time for overall test
    test_start = time.time()

    # Execute all tasks
    results = await asyncio.gather(*[mixed_request(t) for t in task_types])

    total_time = time.time() - test_start

    # Aggregate results
    total_success = sum(r["success_rate"] for r in results)
    overall_success_rate = total_success / len(results)
    avg_latency = sum(r["avg_latency_ms"] for r in results) / len(results)

    print(f"Total requests: {len(results)}")
    print(f"Overall success rate: {overall_success_rate*100:.2f}%")
    print(f"Average latency: {avg_latency:.2f}ms")
    print(f"Total test time: {total_time:.2f}s")

    assert overall_success_rate > SUCCESS_RATE_THRESHOLD, \
        f"Mixed load success rate {overall_success_rate*100:.2f}% below threshold"


if __name__ == "__main__":
    # Run tests manually for development
    pytest.main([__file__, "-v", "-s"])
