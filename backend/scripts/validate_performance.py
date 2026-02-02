#!/usr/bin/env python3
"""
Performance Validation Script for Atom Platform

Validates that performance targets are met after code changes.
Tests governance cache, database queries, and API response times.
"""

import asyncio
import sys
import time
import statistics
from datetime import datetime
from typing import Dict, List, Tuple
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.governance_cache import governance_cache
    from core.agent_governance_service import AgentGovernanceService
    from core.database import SessionLocal, get_db_session
    from core.models import AgentRegistry
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the backend directory")
    sys.exit(1)


# Performance targets (from CLAUDE.md)
PERFORMANCE_TARGETS = {
    "governance_cache_check_p99": 1.0,  # <1ms
    "governance_cache_check_avg": 0.5,  # <0.5ms
    "agent_resolution_avg": 50.0,       # <50ms
    "database_query_avg": 100.0,        # <100ms
}


class PerformanceValidator:
    """Validate performance targets are met"""

    def __init__(self):
        self.results = {}
        self.passed = 0
        self.failed = 0

    def record_result(self, test_name: str, value: float, target: float, unit: str = "ms"):
        """Record a test result"""
        passed = value <= target
        status = "✓ PASS" if passed else "✗ FAIL"

        self.results[test_name] = {
            "value": value,
            "target": target,
            "unit": unit,
            "passed": passed
        }

        if passed:
            self.passed += 1
            print(f"{status}: {test_name} = {value:.3f}{unit} (target: ≤{target}{unit})")
        else:
            self.failed += 1
            print(f"{status}: {test_name} = {value:.3f}{unit} (target: ≤{target}{unit}) ⚠️")

    async def test_governance_cache_performance(self, iterations: int = 1000):
        """Test governance cache check performance"""
        print("\n🔍 Testing Governance Cache Performance...")

        with get_db_session() as db:
            # Get a test agent
            agent = db.query(AgentRegistry).first()
            if not agent:
                print("⚠️  No agents found, skipping governance cache test")
                return

            action_type = "present_canvas"

            # Warm up cache
            for _ in range(10):
                governance_cache.can_perform_action(
                    db=db,
                    agent_id=agent.id,
                    action_type=action_type
                )

            # Measure performance
            timings = []
            for _ in range(iterations):
                start = time.perf_counter()
                governance_cache.can_perform_action(
                    db=db,
                    agent_id=agent.id,
                    action_type=action_type
                )
                end = time.perf_counter()
                timings.append((end - start) * 1000)  # Convert to ms

            # Calculate statistics
            avg_time = statistics.mean(timings)
            p50_time = statistics.median(timings)
            p95_time = statistics.quantiles(timings, n=20)[18]  # 95th percentile
            p99_time = statistics.quantiles(timings, n=100)[98]  # 99th percentile

            print(f"  Iterations: {iterations}")
            print(f"  Avg: {avg_time:.4f}ms")
            print(f"  P50: {p50_time:.4f}ms")
            print(f"  P95: {p95_time:.4f}ms")
            print(f"  P99: {p99_time:.4f}ms")

            self.record_result(
                "governance_cache_check_p99",
                p99_time,
                PERFORMANCE_TARGETS["governance_cache_check_p99"]
            )
            self.record_result(
                "governance_cache_check_avg",
                avg_time,
                PERFORMANCE_TARGETS["governance_cache_check_avg"]
            )

            return avg_time, p99_time

    async def test_agent_resolution_performance(self, iterations: int = 100):
        """Test agent resolution performance"""
        print("\n🔍 Testing Agent Resolution Performance...")

        with get_db_session() as db:
            from core.agent_context_resolver import AgentContextResolver

            resolver = AgentContextResolver(db)

            # Warm up
            for _ in range(10):
                resolver.resolve_agent_context(agent_id="test-agent")

            # Measure performance
            timings = []
            for _ in range(iterations):
                start = time.perf_counter()
                resolver.resolve_agent_context(agent_id="test-agent")
                end = time.perf_counter()
                timings.append((end - start) * 1000)  # Convert to ms

            avg_time = statistics.mean(timings)
            p99_time = statistics.quantiles(timings, n=100)[98] if len(timings) >= 100 else max(timings)

            print(f"  Iterations: {iterations}")
            print(f"  Avg: {avg_time:.4f}ms")
            print(f"  P99: {p99_time:.4f}ms")

            self.record_result(
                "agent_resolution_avg",
                avg_time,
                PERFORMANCE_TARGETS["agent_resolution_avg"]
            )

            return avg_time

    async def test_database_query_performance(self, iterations: int = 50):
        """Test database query performance"""
        print("\n🔍 Testing Database Query Performance...")

        timings = []

        for _ in range(iterations):
            with get_db_session() as db:
                start = time.perf_counter()
                # Simulate typical query
                agents = db.query(AgentRegistry).limit(10).all()
                end = time.perf_counter()
                timings.append((end - start) * 1000)  # Convert to ms

        avg_time = statistics.mean(timings)
        p99_time = statistics.quantiles(timings, n=100)[98] if len(timings) >= 100 else max(timings)

        print(f"  Iterations: {iterations}")
        print(f"  Avg: {avg_time:.4f}ms")
        print(f"  P99: {p99_time:.4f}ms")

        self.record_result(
            "database_query_avg",
            avg_time,
            PERFORMANCE_TARGETS["database_query_avg"]
        )

        return avg_time

    async def run_all_tests(self):
        """Run all performance validation tests"""
        print("=" * 60)
        print("Atom Platform Performance Validation")
        print(f"Started at: {datetime.now().isoformat()}")
        print("=" * 60)

        try:
            await self.test_governance_cache_performance()
            await self.test_agent_resolution_performance()
            await self.test_database_query_performance()
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Print summary
        print("\n" + "=" * 60)
        print("Performance Validation Summary")
        print("=" * 60)
        print(f"Tests Passed: {self.passed}")
        print(f"Tests Failed: {self.failed}")
        print("=" * 60)

        if self.failed == 0:
            print("✅ All performance targets met!")
            return True
        else:
            print("⚠️  Some performance targets not met")
            return False


async def main():
    """Main entry point"""
    validator = PerformanceValidator()
    success = await validator.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
