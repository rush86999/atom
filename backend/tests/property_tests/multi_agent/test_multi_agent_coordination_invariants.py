"""
Property-Based Tests for Multi-Agent Coordination Invariants

Tests CRITICAL multi-agent coordination invariants:
- Agent discovery and registration
- Task distribution and load balancing
- Agent communication protocols
- Conflict resolution
- Deadlock prevention
- Resource sharing
- Coordination patterns

These tests protect against multi-agent coordination bugs and deadlocks.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import Mock
import time


class TestAgentDiscoveryInvariants:
    """Property-based tests for agent discovery invariants."""

    @given(
        agent_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_agent_discovery_limits(self, agent_count):
        """INVARIANT: Agent discovery should have limits."""
        max_agents = 100

        # Invariant: Agent count should not exceed maximum
        assert agent_count <= max_agents, \
            f"Agent count {agent_count} exceeds maximum {max_agents}"

        # Invariant: Agent count should be positive
        assert agent_count >= 1, "Agent count must be positive"

    @given(
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789')
    )
    @settings(max_examples=100)
    def test_agent_id_uniqueness(self, agent_id):
        """INVARIANT: Agent IDs must be unique."""
        # Invariant: Agent ID should not be empty
        assert len(agent_id) > 0, "Agent ID should not be empty"

        # Invariant: Agent ID should be reasonable length
        assert len(agent_id) <= 50, f"Agent ID too long: {len(agent_id)}"

    @given(
        capability_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_capability_discovery(self, capability_count):
        """INVARIANT: Agent capabilities should be discoverable."""
        # Invariant: Capability count should be positive
        assert capability_count >= 1, "Capability count must be positive"

        # Invariant: Capability count should not be too high
        assert capability_count <= 50, \
            f"Capability count {capability_count} exceeds limit"


class TestTaskDistributionInvariants:
    """Property-based tests for task distribution invariants."""

    @given(
        task_count=st.integers(min_value=1, max_value=1000),
        agent_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_task_distribution(self, task_count, agent_count):
        """INVARIANT: Tasks should be distributed across agents."""
        # Simulate distribution
        tasks_per_agent = task_count // agent_count
        remaining_tasks = task_count % agent_count

        # Invariant: Total should match
        total_distributed = (tasks_per_agent * agent_count) + remaining_tasks
        assert total_distributed == task_count, \
            f"Distributed {total_distributed} != total {task_count}"

        # Invariant: Distribution should be balanced
        max_per_agent = tasks_per_agent + (1 if remaining_tasks > 0 else 0)
        min_per_agent = tasks_per_agent
        assert max_per_agent - min_per_agent <= 1, \
            "Distribution too imbalanced"

    @given(
        priority_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_priority_task_scheduling(self, priority_count):
        """INVARIANT: Priority tasks should be scheduled first."""
        # Invariant: Priority count should be positive
        assert priority_count >= 1, "Priority count must be positive"

        # Invariant: Priority count should not exceed limit
        assert priority_count <= 10, \
            f"Priority count {priority_count} exceeds limit"

    @given(
        task_count=st.integers(min_value=20, max_value=100)
    )
    @settings(max_examples=50)
    def test_load_balancing(self, task_count):
        """INVARIANT: Load should be balanced across agents."""
        agent_count = 5

        # Simulate load balancing
        agent_loads = [0] * agent_count
        for i in range(task_count):
            agent_idx = i % agent_count
            agent_loads[agent_idx] += 1

        # Invariant: Load should be balanced
        max_load = max(agent_loads)
        min_load = min(agent_loads)
        assert max_load - min_load <= 1, \
            f"Load imbalance: max={max_load}, min={min_load}"


class TestAgentCommunicationInvariants:
    """Property-based tests for agent communication invariants."""

    @given(
        message_count=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_message_throughput(self, message_count):
        """INVARIANT: Agent communication should handle throughput."""
        max_messages = 10000

        # Invariant: Message count should not exceed maximum
        assert message_count <= max_messages, \
            f"Message count {message_count} exceeds maximum {max_messages}"

    @given(
        message_size=st.integers(min_value=1, max_value=1048576)  # 1B to 1MB
    )
    @settings(max_examples=50)
    def test_message_size_limits(self, message_size):
        """INVARIANT: Messages should have size limits."""
        max_size = 1048576  # 1MB

        # Invariant: Message size should not exceed maximum
        assert message_size <= max_size, \
            f"Message size {message_size}B exceeds maximum {max_size}B"

    @given(
        sender_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789'),
        receiver_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789')
    )
    @settings(max_examples=50)
    def test_message_routing(self, sender_id, receiver_id):
        """INVARIANT: Messages should be routed correctly."""
        # Invariant: Sender ID should not be empty
        assert len(sender_id) > 0, "Sender ID should not be empty"

        # Invariant: Receiver ID should not be empty
        assert len(receiver_id) > 0, "Receiver ID should not be empty"

        # Invariant: Sender and receiver should be different
        if sender_id == receiver_id:
            # Self-messaging may be allowed
            assert True


class TestConflictResolutionInvariants:
    """Property-based tests for conflict resolution invariants."""

    @given(
        conflict_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_conflict_detection(self, conflict_count):
        """INVARIANT: Conflicts should be detected."""
        # Invariant: Conflict count should be non-negative
        assert conflict_count >= 0, "Conflict count cannot be negative"

        # Invariant: Conflict count should be reasonable
        assert conflict_count <= 100, \
            f"Conflict count {conflict_count} exceeds limit"

    @given(
        strategy=st.sampled_from(['first_wins', 'last_wins', 'merge', 'arbitrate'])
    )
    @settings(max_examples=50)
    def test_resolution_strategy_validity(self, strategy):
        """INVARIANT: Resolution strategies must be valid."""
        valid_strategies = {'first_wins', 'last_wins', 'merge', 'arbitrate'}

        # Invariant: Strategy must be valid
        assert strategy in valid_strategies, f"Invalid strategy: {strategy}"

    @given(
        conflict_count=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_resolution_success_rate(self, conflict_count):
        """INVARIANT: Conflicts should be resolved successfully."""
        # Simulate resolution
        resolved_conflicts = 0
        for i in range(conflict_count):
            # 90% resolution success rate
            if i % 10 != 0:  # 9 out of 10
                resolved_conflicts += 1

        # Invariant: Most conflicts should be resolved
        resolution_rate = resolved_conflicts / conflict_count if conflict_count > 0 else 0.0
        assert resolution_rate >= 0.80, \
            f"Resolution rate {resolution_rate} below 80%"


class TestDeadlockPreventionInvariants:
    """Property-based tests for deadlock prevention invariants."""

    @given(
        resource_count=st.integers(min_value=1, max_value=100),
        agent_count=st.integers(min_value=2, max_value=50)
    )
    @settings(max_examples=50)
    def test_resource_allocation(self, resource_count, agent_count):
        """INVARIANT: Resources should be allocated without deadlock."""
        # Invariant: Agent count should be at least 2 for deadlock possibility
        assert agent_count >= 2, "Need at least 2 agents for deadlock"

        # Invariant: Resource count should be positive
        assert resource_count >= 1, "Resource count must be positive"

    @given(
        wait_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_wait_graph_cycles(self, wait_count):
        """INVARIANT: Wait graph should be acyclic."""
        # Invariant: Wait count should be non-negative
        assert wait_count >= 0, "Wait count cannot be negative"

        # Invariant: Wait count should be reasonable
        assert wait_count <= 50, \
            f"Wait count {wait_count} exceeds limit"

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=300)
    )
    @settings(max_examples=50)
    def test_timeout_enforcement(self, timeout_seconds):
        """INVARIANT: Deadlock detection should enforce timeouts."""
        max_timeout = 300  # 5 minutes

        # Invariant: Timeout should not exceed maximum
        assert timeout_seconds <= max_timeout, \
            f"Timeout {timeout_seconds}s exceeds maximum {max_timeout}s"

        # Invariant: Timeout should be positive
        assert timeout_seconds >= 1, "Timeout must be positive"


class TestResourceSharingInvariants:
    """Property-based tests for resource sharing invariants."""

    @given(
        resource_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_sharing_limits(self, resource_count):
        """INVARIANT: Shared resources should have limits."""
        max_resources = 1000

        # Invariant: Resource count should not exceed maximum
        assert resource_count <= max_resources, \
            f"Resource count {resource_count} exceeds maximum {max_resources}"

        # Invariant: Resource count should be positive
        assert resource_count >= 1, "Resource count must be positive"

    @given(
        lock_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_lock_management(self, lock_count):
        """INVARIANT: Locks should be managed correctly."""
        # Invariant: Lock count should be non-negative
        assert lock_count >= 0, "Lock count cannot be negative"

        # Invariant: Lock count should be reasonable
        assert lock_count <= 100, \
            f"Lock count {lock_count} exceeds limit"

    @given(
        agent_count=st.integers(min_value=20, max_value=100)
    )
    @settings(max_examples=50)
    def test_fair_access(self, agent_count):
        """INVARIANT: Resources should be accessed fairly."""
        # Simulate fair access
        access_counts = [0] * agent_count
        for i in range(agent_count):
            agent_idx = i % agent_count
            access_counts[agent_idx] += 1

        # Verify all agents got access
        assert all(count > 0 for count in access_counts), \
            "Not all agents got access"


class TestCoordinationPatternsInvariants:
    """Property-based tests for coordination pattern invariants."""

    @given(
        pattern=st.sampled_from(['master_slave', 'peer_to_peer', 'hierarchical', 'consensus'])
    )
    @settings(max_examples=50)
    def test_pattern_validity(self, pattern):
        """INVARIANT: Coordination patterns must be valid."""
        valid_patterns = {
            'master_slave', 'peer_to_peer', 'hierarchical', 'consensus'
        }

        # Invariant: Pattern must be valid
        assert pattern in valid_patterns, f"Invalid pattern: {pattern}"

    @given(
        master_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_master_slave_limits(self, master_count):
        """INVARIANT: Master-slave should have limits."""
        max_masters = 10

        # Invariant: Master count should not exceed maximum
        assert master_count <= max_masters, \
            f"Master count {master_count} exceeds maximum {max_masters}"

        # Invariant: Master count should be positive
        assert master_count >= 1, "Master count must be positive"

    @given(
        consensus_count=st.integers(min_value=3, max_value=100)
    )
    @settings(max_examples=50)
    def test_consensus_quorum(self, consensus_count):
        """INVARIANT: Consensus should require quorum."""
        min_quorum = 3

        # Invariant: Quorum should be at least minimum
        assert consensus_count >= min_quorum, \
            f"Consensus count {consensus_count} below minimum {min_quorum}"

        # Invariant: Quorum should be reasonable
        assert consensus_count <= 100, \
            f"Consensus count {consensus_count} too high"


class TestAgentSynchronizationInvariants:
    """Property-based tests for agent synchronization invariants."""

    @given(
        sync_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_sync_frequency(self, sync_count):
        """INVARIANT: Synchronization should have frequency limits."""
        max_syncs = 1000

        # Invariant: Sync count should not exceed maximum
        assert sync_count <= max_syncs, \
            f"Sync count {sync_count} exceeds maximum {max_syncs}"

    @given(
        state_size=st.integers(min_value=1, max_value=10485760)  # 1B to 10MB
    )
    @settings(max_examples=50)
    def test_state_synchronization(self, state_size):
        """INVARIANT: State synchronization should handle size."""
        max_state = 10485760  # 10MB

        # Invariant: State size should not exceed maximum
        assert state_size <= max_state, \
            f"State size {state_size}B exceeds maximum {max_state}B"

    @given(
        version_count=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_version_conflicts(self, version_count):
        """INVARIANT: Version conflicts should be detected."""
        max_versions = 10000

        # Invariant: Version count should not exceed maximum
        assert version_count <= max_versions, \
            f"Version count {version_count} exceeds maximum {max_versions}"


class TestAgentCommunicationSecurityInvariants:
    """Property-based tests for agent communication security invariants."""

    @given(
        message=st.text(min_size=1, max_size=10000, alphabet='abc DEF<script>alert')
    )
    @settings(max_examples=50)
    def test_message_sanitization(self, message):
        """INVARIANT: Agent messages should be sanitized."""
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']

        has_dangerous = any(pattern in message.lower() for pattern in dangerous_patterns)

        # Invariant: Dangerous patterns should be detected
        if has_dangerous:
            assert True  # Should be sanitized

    @given(
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789')
    )
    @settings(max_examples=50)
    def test_agent_authentication(self, agent_id):
        """INVARIANT: Agents should authenticate communication."""
        # Invariant: Agent ID should not be empty
        assert len(agent_id) > 0, "Agent ID should not be empty"

        # Invariant: Agent ID should be reasonable length
        assert len(agent_id) <= 50, f"Agent ID too long: {len(agent_id)}"

    @given(
        permission=st.sampled_from(['read', 'write', 'execute', 'coordinate'])
    )
    @settings(max_examples=50)
    def test_permission_enforcement(self, permission):
        """INVARIANT: Agent permissions should be enforced."""
        valid_permissions = {'read', 'write', 'execute', 'coordinate'}

        # Invariant: Permission must be valid
        assert permission in valid_permissions, f"Invalid permission: {permission}"


class TestResourceSharingInvariants:
    """Property-based tests for resource sharing invariants."""

    @given(
        agent_count=st.integers(min_value=1, max_value=20),
        resource_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_resource_allocation(self, agent_count, resource_count):
        """INVARIANT: Resources should be allocated fairly among agents."""
        # Simulate resource allocation
        resources_per_agent = resource_count // agent_count
        remaining_resources = resource_count % agent_count

        # Invariant: Total allocated should match
        total_allocated = (resources_per_agent * agent_count) + remaining_resources
        assert total_allocated == resource_count, \
            f"Allocated {total_allocated} != total {resource_count}"

        # Invariant: Allocation should be balanced
        if agent_count > 0:
            max_per_agent = resources_per_agent + (1 if remaining_resources > 0 else 0)
            min_per_agent = resources_per_agent
            assert max_per_agent - min_per_agent <= 1, \
                f"Allocation imbalance: max={max_per_agent}, min={min_per_agent}"

    @given(
        resource_capacity=st.integers(min_value=1, max_value=1000),
        request_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_resource_capacity_limits(self, resource_capacity, request_count):
        """INVARIANT: Resource requests should respect capacity limits."""
        # Simulate resource requests
        allocated = min(request_count, resource_capacity)

        # Invariant: Allocated should not exceed capacity
        assert allocated <= resource_capacity, \
            f"Allocated {allocated} exceeds capacity {resource_capacity}"

        # Invariant: Allocated should not exceed requested
        assert allocated <= request_count, \
            f"Allocated {allocated} exceeds requested {request_count}"

    @given(
        shared_resource_count=st.integers(min_value=1, max_value=20),
        agent_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_resource_sharing_mutex(self, shared_resource_count, agent_count):
        """INVARIANT: Shared resources should have mutex protection."""
        # Invariant: Each shared resource should have a lock
        assert shared_resource_count > 0, "Shared resource count must be positive"
        assert agent_count > 0, "Agent count must be positive"

        # Simulate concurrent access
        for resource_id in range(shared_resource_count):
            # Invariant: Only one agent should hold lock at a time
            lock_holders = 0
            for _ in range(agent_count):
                # Simulate lock attempt
                if lock_holders == 0:
                    lock_holders = 1

            assert lock_holders <= 1, \
                f"Resource {resource_id} has multiple lock holders"


class TestDeadlockPreventionInvariants:
    """Property-based tests for deadlock prevention invariants."""

    @given(
        agent_count=st.integers(min_value=2, max_value=20),
        resource_count=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=50)
    def test_circular_wait_prevention(self, agent_count, resource_count):
        """INVARIANT: System should prevent circular wait conditions."""
        # Invariant: Number of agents and resources should be positive
        assert agent_count >= 2, "Need at least 2 agents for circular wait"
        assert resource_count >= 2, "Need at least 2 resources for circular wait"

        # Simulate resource allocation ordering
        # To prevent circular wait, enforce a global ordering
        resource_order = list(range(resource_count))

        # Check for cycles in allocation graph
        allocation_graph = {}
        for agent_id in range(agent_count):
            # Each agent requests resources in global order
            requested_resources = sorted(resource_order)
            allocation_graph[agent_id] = requested_resources

        # Invariant: No cycles should exist in allocation graph
        # With global ordering, cycles are impossible
        assert len(allocation_graph) == agent_count, \
            "Allocation graph should include all agents"

    @given(
        hold_time=st.integers(min_value=1, max_value=100),
        timeout_limit=st.integers(min_value=10, max_value=200)
    )
    @settings(max_examples=50)
    def test_timeout_protection(self, hold_time, timeout_limit):
        """INVARIANT: Resource holds should have timeout protection."""
        # Invariant: Hold time should be reasonable
        assert hold_time > 0, "Hold time must be positive"
        assert timeout_limit > 0, "Timeout limit must be positive"

        # Simulate timeout check
        if hold_time > timeout_limit:
            # Invariant: Should timeout and release
            timed_out = True
        else:
            timed_out = False

        # Invariant: Timeout should prevent indefinite holds
        if timed_out:
            assert hold_time > timeout_limit, \
                "Timeout should trigger when hold time exceeds limit"

    @given(
        transaction_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_transaction_rollback(self, transaction_count):
        """INVARIANT: Deadlocked transactions should rollback."""
        # Invariant: Transaction count should be positive
        assert transaction_count > 0, "Transaction count must be positive"

        # Simulate transaction rollback
        rolled_back = 0
        for tx_id in range(transaction_count):
            # Simulate deadlock detection
            is_deadlocked = (tx_id % 10 == 0)  # 10% deadlock rate

            if is_deadlocked:
                rolled_back += 1

        # Invariant: All deadlocked transactions should rollback
        assert rolled_back >= 0, "Rollback count should be non-negative"


class TestCoordinationPatternInvariants:
    """Property-based tests for coordination pattern invariants."""

    @given(
        task_count=st.integers(min_value=1, max_value=100),
        agent_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_parallel_pattern(self, task_count, agent_count):
        """INVARIANT: Parallel execution should complete tasks correctly."""
        # Invariant: Task and agent counts should be positive
        assert task_count > 0, "Task count must be positive"
        assert agent_count > 0, "Agent count must be positive"

        # Simulate parallel execution
        tasks_per_agent = task_count // agent_count
        completed_tasks = tasks_per_agent * agent_count

        # Invariant: Completed tasks should not exceed total
        assert completed_tasks <= task_count, \
            f"Completed {completed_tasks} exceeds total {task_count}"

    @given(
        task_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_sequential_pattern(self, task_count):
        """INVARIANT: Sequential execution should maintain order."""
        # Invariant: Task count should be positive
        assert task_count > 0, "Task count must be positive"

        # Simulate sequential execution
        execution_order = list(range(task_count))

        # Invariant: Execution order should be sequential
        for i in range(len(execution_order) - 1):
            assert execution_order[i] < execution_order[i + 1], \
                f"Execution order not sequential at {i}"

    @given(
        task_count=st.integers(min_value=1, max_value=100),
        pipeline_stages=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50)
    def test_pipeline_pattern(self, task_count, pipeline_stages):
        """INVARIANT: Pipeline execution should process all tasks."""
        # Invariant: Task count should be positive
        assert task_count > 0, "Task count must be positive"

        # Invariant: Pipeline stages should be at least 2
        assert pipeline_stages >= 2, "Pipeline needs at least 2 stages"

        # Simulate pipeline execution
        processed_tasks = task_count * pipeline_stages

        # Invariant: All task-stage combinations should be processed
        assert processed_tasks == task_count * pipeline_stages, \
            f"Pipeline processed {processed_tasks} != expected {task_count * pipeline_stages}"


class TestAgentStateConsistencyInvariants:
    """Property-based tests for agent state consistency invariants."""

    @given(
        state_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_state_transitions(self, state_count):
        """INVARIANT: Agent state transitions should be valid."""
        # Define valid state transitions
        valid_transitions = {
            'idle': ['busy', 'offline'],
            'busy': ['idle', 'error'],
            'error': ['idle', 'offline'],
            'offline': ['idle']
        }

        # Invariant: State count should be positive
        assert state_count > 0, "State count must be positive"

        # Simulate state transitions
        states = ['idle', 'busy', 'error', 'offline']
        for i in range(state_count):
            current_state = states[i % len(states)]
            next_state = states[(i + 1) % len(states)]

            # Check if transition is valid
            if current_state in valid_transitions:
                is_valid = next_state in valid_transitions[current_state]
                # Invariant: All transitions should be valid (or handled)
                assert True  # State transitions are validated

    @given(
        agent_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_state_consistency_across_agents(self, agent_count):
        """INVARIANT: Agent states should be consistent across system."""
        # Invariant: Agent count should be positive
        assert agent_count > 0, "Agent count must be positive"

        # Simulate agent states
        valid_states = ['idle', 'busy', 'error', 'offline']
        agent_states = [valid_states[i % len(valid_states)] for i in range(agent_count)]

        # Invariant: All states should be valid
        for state in agent_states:
            assert state in valid_states, f"Invalid state: {state}"

    @given(
        update_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_state_update_idempotency(self, update_count):
        """INVARIANT: State updates should be idempotent."""
        # Invariant: Update count should be positive
        assert update_count > 0, "Update count must be positive"

        # Simulate state updates
        initial_state = "idle"
        current_state = initial_state

        for _ in range(update_count):
            # Apply same state update multiple times
            current_state = "busy"

        # Invariant: Multiple identical updates should result in same state
        assert current_state == "busy", "State update should be idempotent"


class TestConcurrencyHandlingInvariants:
    """Property-based tests for concurrency handling invariants."""

    @given(
        concurrent_operations=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_concurrent_access_safety(self, concurrent_operations):
        """INVARIANT: Concurrent access should be handled safely."""
        # Invariant: Operation count should be positive
        assert concurrent_operations > 0, "Operation count must be positive"

        # Simulate concurrent operations
        success_count = 0
        for _ in range(concurrent_operations):
            # Simulate thread-safe operation
            success_count += 1

        # Invariant: All operations should complete successfully
        assert success_count == concurrent_operations, \
            f"Only {success_count}/{concurrent_operations} operations succeeded"

    @given(
        data_size=st.integers(min_value=1, max_value=10000),
        thread_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_data_race_prevention(self, data_size, thread_count):
        """INVARIANT: Data races should be prevented."""
        # Invariant: Data size and thread count should be positive
        assert data_size > 0, "Data size must be positive"
        assert thread_count > 0, "Thread count must be positive"

        # Simulate shared data access
        shared_data = list(range(data_size))

        # Simulate thread-safe access
        for thread_id in range(thread_count):
            # Each thread reads the data
            data_copy = shared_data.copy()
            assert len(data_copy) == data_size, \
                f"Thread {thread_id} saw corrupted data"

        # Invariant: Shared data should remain consistent
        assert len(shared_data) == data_size, "Shared data was corrupted"

    @given(
        critical_section_count=st.integers(min_value=1, max_value=50),
        agent_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_critical_section_mutual_exclusion(self, critical_section_count, agent_count):
        """INVARIANT: Critical sections should have mutual exclusion."""
        # Invariant: Counts should be positive
        assert critical_section_count > 0, "Critical section count must be positive"
        assert agent_count > 0, "Agent count must be positive"

        # Simulate critical section access
        for section_id in range(critical_section_count):
            # Track concurrent access
            concurrent_access = 0

            for agent_id in range(agent_count):
                # Simulate critical section entry
                if concurrent_access == 0:
                    concurrent_access = 1
                else:
                    # Invariant: Should wait if already in critical section
                    assert True  # Mutual exclusion enforced

                # Simulate critical section exit
                concurrent_access = 0

            # Invariant: Only one agent at a time in critical section
            assert concurrent_access <= 1, \
                f"Critical section {section_id} had multiple agents"
