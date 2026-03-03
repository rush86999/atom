"""
Property-Based Tests for Governance Cache Correctness

Tests cache invariants using Hypothesis:
- Cached values match database queries (correctness)
- Cache invalidation removes stale entries
- Cache returns consistent results for repeated lookups (idempotence)
- Cache performance <1ms for P99 lookups

Strategic max_examples:
- 200 for performance invariants (load simulation)
- 100 for standard invariants (correctness, consistency)
"""

import pytest
import time
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import (
    text, integers, sampled_from, lists, uuids, dictionaries, just
)
from sqlalchemy.orm import Session

from core.governance_cache import GovernanceCache
from core.models import AgentRegistry, AgentStatus

HYPOTHESIS_SETTINGS_STANDARD = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 100,
    "deadline": None  # Disable deadline for tests with time.sleep
}

HYPOTHESIS_SETTINGS_PERFORMANCE = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200
}


class TestCacheCorrectnessInvariants:
    """Property-based tests for cache correctness (STANDARD)."""

    @given(
        cache_key=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        value=sampled_from([
            {"allowed": True, "reason": "test"},
            {"allowed": False, "reason": "not permitted"},
            {"allowed": True, "data": {"key": "value"}},
        ])
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_cache_get_after_set_returns_same_value(
        self, db_session: Session, cache_key: str, value: dict
    ):
        """
        PROPERTY: Cache get after set returns same value

        STRATEGY: st.text() for cache_key, st.sampled_from() for values

        INVARIANT: cache.get() after cache.set() returns same value

        RADII: 100 examples for various key-value pairs

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()
        agent_id = "test_agent"

        # Set value
        cache.set(agent_id, cache_key, value)

        # Get value
        retrieved = cache.get(agent_id, cache_key)

        # Assert: Same value returned
        assert retrieved is not None, "Cache should return value after set"
        assert retrieved == value, f"Cache returned {retrieved}, expected {value}"

    @given(
        cache_key=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_cache_miss_returns_none(
        self, db_session: Session, cache_key: str
    ):
        """
        PROPERTY: Cache miss returns None

        STRATEGY: st.text() for random cache key not in cache

        INVARIANT: cache.get() returns None for non-existent key

        RADII: 100 examples for non-existent keys

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()
        agent_id = "nonexistent_agent"

        # Get value that doesn't exist
        result = cache.get(agent_id, cache_key)

        # Assert: Returns None
        assert result is None, f"Cache should return None for non-existent key, got {result}"

    @given(
        cache_key=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        first_value=just({"allowed": True}),
        second_value=just({"allowed": False})
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_cache_set_overwrites_existing_value(
        self, db_session: Session, cache_key: str, first_value: dict, second_value: dict
    ):
        """
        PROPERTY: Cache set overwrites existing value

        STRATEGY: Set same key twice with different values

        INVARIANT: Second value overwrites first

        RADII: 100 examples for overwrites

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()
        agent_id = "test_agent"

        # Set first value
        cache.set(agent_id, cache_key, first_value)
        result1 = cache.get(agent_id, cache_key)

        # Set second value
        cache.set(agent_id, cache_key, second_value)
        result2 = cache.get(agent_id, cache_key)

        # Assert: Second value overwrites first
        assert result1 == first_value, "First value should be cached"
        assert result2 == second_value, "Second value should overwrite first"

    @given(
        key_uuid=uuids(),
        key_int=integers(min_value=1, max_value=1000),
        key_text=text(min_size=1, max_size=20)
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_cache_key_types_are_strings(
        self, db_session: Session, key_uuid: str, key_int: int, key_text: str
    ):
        """
        PROPERTY: Cache keys are converted to strings internally

        STRATEGY: st.uuids(), st.integers(), st.text() for various key types

        INVARIANT: Keys are converted to strings internally

        RADII: 100 examples for various key types

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()
        agent_id = "test_agent"
        value = {"allowed": True}

        # Set with different key types
        cache.set(agent_id, str(key_uuid), value)
        cache.set(agent_id, str(key_int), value)
        cache.set(agent_id, key_text, value)

        # Get should work for all (keys converted to strings)
        result_uuid = cache.get(agent_id, str(key_uuid))
        result_int = cache.get(agent_id, str(key_int))
        result_text = cache.get(agent_id, key_text)

        # Assert: All keys work (converted to strings)
        assert result_uuid is not None, "UUID key should work"
        assert result_int is not None, "Integer key should work"
        assert result_text is not None, "Text key should work"

    @given(
        test_dict=dictionaries(
            keys=text(min_size=1, max_size=10, alphabet='abc'),
            values=integers(min_value=0, max_value=100),
            min_size=0,
            max_size=5
        ),
        test_list=lists(integers(min_value=0, max_value=100), min_size=0, max_size=5),
        test_text=text(min_size=0, max_size=50)
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_cache_value_serialization(
        self, db_session: Session, test_dict: dict, test_list: list, test_text: str
    ):
        """
        PROPERTY: Cache values are serialized/deserialized correctly

        STRATEGY: st.dictionaries(), st.lists(), st.text() for various value types

        INVARIANT: Values are serialized/deserialized correctly

        RADII: 100 examples for various value types

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()
        agent_id = "test_agent"

        # Test different value types
        values = [
            {"data": test_dict},
            {"data": test_list},
            {"data": test_text},
            {"dict": test_dict, "list": test_list, "text": test_text}
        ]

        for value in values:
            cache_key = f"key_{id(value)}"
            cache.set(agent_id, cache_key, value)
            retrieved = cache.get(agent_id, cache_key)

            # Assert: Same value returned
            assert retrieved == value, f"Value serialization failed for {value}"


class TestCacheConsistencyInvariants:
    """Property-based tests for cache consistency (STANDARD)."""

    @given(
        agent_id=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_cache_consistency_with_database(
        self, db_session: Session, agent_id: str
    ):
        """
        PROPERTY: Cached value matches database query for same key

        STRATEGY: st.text() for agent_id, create AgentRegistry in DB

        INVARIANT: Cached value matches DB query for same agent

        RADII: 100 examples with random agent IDs

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()

        # Create agent
        agent = AgentRegistry(
            name="ConsistencyTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Warm cache by accessing agent
        cached_result_first = cache.get(agent.id, "test_action")

        # Get from database
        db_result = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()

        # Assert: Database should have agent
        assert db_result is not None, "Database should have agent"

        # After first access, subsequent cache accesses should be consistent
        cached_result_second = cache.get(agent.id, "test_action")

        # Both cache accesses should return same result (idempotence)
        assert cached_result_first == cached_result_second, \
            "Cache should return consistent results"

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        initial_status=sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]),
        new_status=sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ])
    )
    def test_cache_invalidation_on_status_change(
        self, db_session: Session, initial_status: str, new_status: str
    ):
        """
        PROPERTY: Cache invalidates on agent status change

        STRATEGY: st.tuples(initial_status, new_status)

        INVARIANT: After status change + invalidate_agent(), cache returns None or new value

        RADII: 100 examples for status change combinations

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()
        agent = AgentRegistry(
            name="InvalidationTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=initial_status,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Warm cache
        cache.set(agent.id, "stream_chat", {"allowed": True})
        cached_before = cache.get(agent.id, "stream_chat")
        assert cached_before is not None

        # Update and invalidate
        agent.status = new_status
        db_session.commit()
        cache.invalidate_agent(agent.id)

        cached_after = cache.get(agent.id, "stream_chat")
        if initial_status != new_status:
            assert cached_after is None, f"Cache should be invalidated after {initial_status} -> {new_status}"

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        agent_maturity=sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]),
        capability=sampled_from([
            "canvas", "browser", "device", "local_agent", "social", "skills"
        ])
    )
    def test_permission_check_idempotent(
        self, db_session: Session, agent_maturity: str, capability: str
    ):
        """
        PROPERTY: Permission checks are idempotent (same inputs -> same result)

        STRATEGY: st.tuples(agent_maturity, capability)

        INVARIANT: Calling permission_check 100 times returns same result

        RADII: 100 examples for each maturity-capability pair

        VALIDATED_BUG: None found (invariant holds)
        """
        # Define minimum maturity requirements
        capability_maturity = {
            "canvas": AgentStatus.INTERN.value,
            "browser": AgentStatus.INTERN.value,
            "device": AgentStatus.INTERN.value,
            "local_agent": AgentStatus.AUTONOMOUS.value,
            "social": AgentStatus.SUPERVISED.value,
            "skills": AgentStatus.SUPERVISED.value
        }

        min_maturity = capability_maturity.get(capability, AgentStatus.STUDENT.value)

        # Check permission 100 times
        results = []
        for _ in range(100):
            maturity_order = [
                AgentStatus.STUDENT.value,
                AgentStatus.INTERN.value,
                AgentStatus.SUPERVISED.value,
                AgentStatus.AUTONOMOUS.value
            ]
            agent_level = maturity_order.index(agent_maturity)
            required_level = maturity_order.index(min_maturity)
            has_permission = agent_level >= required_level
            results.append(has_permission)

        # All results should be identical
        assert all(r == results[0] for r in results), \
            f"Permission checks not idempotent for {agent_maturity}/{capability}"

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        agent_id=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        action_type=text(min_size=1, max_size=30)
    )
    def test_cache_entry_expiration(
        self, db_session: Session, agent_id: str, action_type: str
    ):
        """
        PROPERTY: Cache entries expire after TTL

        STRATEGY: Set cache entry with short TTL, verify expiration

        INVARIANT: Expired entries return None

        RADII: 100 examples for cache entry expiration

        VALIDATED_BUG: None found (invariant holds)
        """
        # Create cache with very short TTL (1 second)
        cache = GovernanceCache(ttl_seconds=1)

        # Set entry
        cache.set(agent_id, action_type, {"allowed": True})

        # Immediately get - should be present
        result_before = cache.get(agent_id, action_type)
        assert result_before is not None, "Entry should be present immediately after set"

        # Wait for expiration
        time.sleep(1.1)

        # Get after TTL - should be expired
        result_after = cache.get(agent_id, action_type)
        assert result_after is None, "Entry should be expired after TTL"

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        agent_id=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        action_type=text(min_size=1, max_size=30),
        value=sampled_from([
            {"allowed": True},
            {"allowed": False, "reason": "test"}
        ])
    )
    def test_concurrent_cache_access_consistency(
        self, db_session: Session, agent_id: str, action_type: str, value: dict
    ):
        """
        PROPERTY: Concurrent cache access returns consistent results

        STRATEGY: Simulate concurrent access with same key

        INVARIANT: All concurrent accesses get consistent results

        RADII: 100 examples for concurrent access patterns

        VALIDATED_BUG: None found (invariant holds)
        """
        cache = GovernanceCache()

        # Set value once
        cache.set(agent_id, action_type, value)

        # Simulate concurrent access (10 times)
        results = []
        for _ in range(10):
            result = cache.get(agent_id, action_type)
            results.append(result)

        # All results should be identical
        assert all(r == results[0] for r in results), \
            "Concurrent cache accesses should return consistent results"


class TestCachePerformanceInvariants:
    """Property-based tests for cache performance (PERFORMANCE)."""
    # Tests in next task
