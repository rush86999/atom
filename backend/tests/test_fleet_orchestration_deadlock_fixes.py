"""
Test suite for Fleet Orchestration deadlock fix verification.

GREEN PHASE: These tests verify the deadlock fixes are applied.
"""

import pytest
import asyncio
import inspect
from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
from core.fleet_orchestration.distributed_blackboard_service import FleetStateNotifier


class TestFleetOrchestrationDeadlockFixes:
    """Tests for verifying the deadlock fixes."""

    def test_timeout_constants_exist(self):
        """
        Test that timeout constants are now defined.

        GREEN PHASE: After the fix, timeout constants should exist.
        """
        from core.fleet_orchestration.fleet_coordinator_service import (
            DEFAULT_TASK_TIMEOUT_SECONDS,
            DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS,
            DEFAULT_DB_TIMEOUT_SECONDS
        )

        # Verify constants are defined
        assert DEFAULT_TASK_TIMEOUT_SECONDS > 0, \
            "Fix applied: DEFAULT_TASK_TIMEOUT_SECONDS is defined"
        assert DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS > 0, \
            "Fix applied: DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS is defined"
        assert DEFAULT_DB_TIMEOUT_SECONDS > 0, \
            "Fix applied: DEFAULT_DB_TIMEOUT_SECONDS is defined"

    def test_asyncio_gather_timeout_protection(self):
        """
        Test that asyncio.gather now has timeout protection.

        GREEN PHASE: After the fix, gather should be wrapped with wait_for.
        """
        source = inspect.getsource(FleetCoordinatorService.execute_parallel_task)

        # Verify the fix - asyncio.wait_for should wrap asyncio.gather
        assert 'asyncio.wait_for(' in source, \
            "Fix applied: asyncio.wait_for wraps gather"
        assert 'asyncio.gather(' in source, \
            "Fix applied: asyncio.gather is used"

    def test_redis_listener_timeout_protection(self):
        """
        Test that Redis listener now has timeout protection.

        GREEN PHASE: After the fix, listener should have timeout check.
        """
        from core.fleet_orchestration.distributed_blackboard_service import DEFAULT_LISTENER_TIMEOUT_SECONDS

        # Verify timeout constant exists
        assert DEFAULT_LISTENER_TIMEOUT_SECONDS > 0, \
            "Fix applied: DEFAULT_LISTENER_TIMEOUT_SECONDS defined"

        # Check source code for timeout mechanism
        source = inspect.getsource(FleetStateNotifier.subscribe_to_fleet)

        # Verify timeout parameter
        assert 'timeout_seconds' in source, \
            "Fix applied: subscribe_to_fleet has timeout_seconds parameter"

        # Verify timeout checking in listener
        assert 'elapsed' in source and 'listener_timeout' in source, \
            "Fix applied: Listener has timeout checking logic"

    def test_llm_decomposition_timeout_protection(self):
        """
        Test that LLM decomposition now has timeout protection.

        GREEN PHASE: After the fix, decompose_task should be wrapped with wait_for.
        """
        source = inspect.getsource(FleetCoordinatorService.decompose_and_execute)

        # Verify the fix - asyncio.wait_for should wrap decompose_task
        assert 'asyncio.wait_for(' in source, \
            "Fix applied: asyncio.wait_for wraps decompose_task"
        assert 'decompose_task(' in source, \
            "Fix applied: decompose_task is called"

        # Verify error handling for timeout
        assert 'TimeoutError' in source, \
            "Fix applied: TimeoutError raised on timeout"

    def test_lazy_initialization_lock_protection(self):
        """
        Test that lazy initialization now has lock protection.

        GREEN PHASE: After the fix, lazy initialization should use asyncio.Lock.
        """
        source = inspect.getsource(FleetCoordinatorService.__init__)

        # Verify lock initialization
        assert '_init_lock' in source and 'asyncio.Lock()' in source, \
            "Fix applied: _init_lock is initialized as asyncio.Lock"

        # Check decompose_and_execute uses lock
        source = inspect.getsource(FleetCoordinatorService.decompose_and_execute)

        # Verify async with lock pattern
        assert 'async with self._init_lock:' in source, \
            "Fix applied: Lazy initialization uses lock protection"

    def test_timeout_constant_values_are_reasonable(self):
        """
        Test that timeout constants have reasonable values.

        GREEN PHASE: Timeout values should be neither too short nor too long.
        """
        from core.fleet_orchestration.fleet_coordinator_service import (
            DEFAULT_TASK_TIMEOUT_SECONDS,
            DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS,
            DEFAULT_DB_TIMEOUT_SECONDS
        )
        from core.fleet_orchestration.distributed_blackboard_service import DEFAULT_LISTENER_TIMEOUT_SECONDS

        # Task timeout should be between 1 minute and 1 hour
        assert 60 <= DEFAULT_TASK_TIMEOUT_SECONDS <= 3600, \
            f"Fix applied: Task timeout {DEFAULT_TASK_TIMEOUT_SECONDS}s is reasonable"

        # LLM decomposition timeout should be between 30 seconds and 10 minutes
        assert 30 <= DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS <= 600, \
            f"Fix applied: Decomposition timeout {DEFAULT_DECOMPOSITION_TIMEOUT_SECONDS}s is reasonable"

        # DB timeout should be between 5 seconds and 5 minutes
        assert 5 <= DEFAULT_DB_TIMEOUT_SECONDS <= 300, \
            f"Fix applied: DB timeout {DEFAULT_DB_TIMEOUT_SECONDS}s is reasonable"

        # Listener timeout should be at least 5 minutes
        assert DEFAULT_LISTENER_TIMEOUT_SECONDS >= 300, \
            f"Fix applied: Listener timeout {DEFAULT_LISTENER_TIMEOUT_SECONDS}s is reasonable"

    def test_gather_timeout_error_handling(self):
        """
        Test that gather timeout is properly handled.

        GREEN PHASE: After the fix, timeout should be caught and logged.
        """
        source = inspect.getsource(FleetCoordinatorService.execute_parallel_task)

        # Verify timeout exception handling
        assert 'except asyncio.TimeoutError:' in source, \
            "Fix applied: TimeoutError is caught"
        assert 'logger.error' in source and 'timeout' in source.lower(), \
            "Fix applied: Timeout is logged as error"

    def test_decomposition_timeout_error_handling(self):
        """
        Test that decomposition timeout is properly handled.

        GREEN PHASE: After the fix, timeout should raise descriptive error.
        """
        source = inspect.getsource(FleetCoordinatorService.decompose_and_execute)

        # Verify timeout exception handling and descriptive error
        assert 'except asyncio.TimeoutError:' in source, \
            "Fix applied: TimeoutError is caught"
        assert 'logger.error' in source and 'decomposition' in source.lower() and 'timeout' in source.lower(), \
            "Fix applied: Decomposition timeout is logged as error"
        assert 'raise TimeoutError(' in source, \
            "Fix applied: Descriptive TimeoutError is raised"

    def test_redis_listener_closes_on_timeout(self):
        """
        Test that Redis listener closes connection on timeout.

        GREEN PHASE: After the fix, listener should close pubsub on timeout.
        """
        source = inspect.getsource(FleetStateNotifier.subscribe_to_fleet)

        # Verify pubsub close on timeout
        assert 'await pubsub.close()' in source, \
            "Fix applied: pubsub.close() called on timeout"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
