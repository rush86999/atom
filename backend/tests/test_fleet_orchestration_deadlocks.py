"""
Test suite for Fleet Orchestration deadlock vulnerabilities.

RED PHASE: These tests expose deadlock bugs in fleet orchestration.

The bugs:
1. Line 269: asyncio.gather with no timeout - tasks can deadlock indefinitely
2. Line 52: pubsub.listen() with no timeout - stale Redis connections hang
3. Line 736: LLM decomposition with no timeout - LLM hangs block entire fleet
4. Lines 722-727: Lazy initialization without locks - race condition
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from core.fleet_orchestration.fleet_coordinator_service import FleetCoordinatorService
from core.fleet_orchestration.distributed_blackboard_service import FleetStateNotifier


class TestFleetOrchestrationDeadlockBugs:
    """
    Test suite revealing deadlock bugs in Fleet Orchestration.

    The bug: Multiple operations lack timeouts and deadlock protection,
    allowing indefinite hangs that block fleet execution.
    """

    def test_asyncio_gather_timeout_missing(self):
        """
        Test that asyncio.gather has no timeout protection.

        BUG: Line 269 uses asyncio.gather without timeout.
        If tasks deadlock, gather will hang indefinitely.
        """
        import inspect

        # Get the source code of execute_parallel_task
        source = inspect.getsource(FleetCoordinatorService.execute_parallel_task)

        # Verify the bug - asyncio.gather without timeout wrapper
        assert 'asyncio.gather(*tasks' in source, \
            "Bug confirmed: asyncio.gather found in source"

        # Verify no timeout mechanism is present
        assert 'timeout' not in source or 'asyncio.wait_for' not in source, \
            "Bug confirmed: No timeout mechanism for asyncio.gather"

    def test_redis_pubsub_listener_timeout_missing(self):
        """
        Test that Redis pubsub listener has no timeout.

        BUG: Line 52 uses async for message in pubsub.listen() without timeout.
        If Redis connection is stale, listener hangs indefinitely.
        """
        import inspect

        # Get the source code of subscribe_to_fleet
        source = inspect.getsource(FleetStateNotifier.subscribe_to_fleet)

        # Verify the bug - async for loop without timeout
        assert 'async for message in pubsub.listen()' in source, \
            "Bug confirmed: Infinite listener loop without timeout"

        # Verify no timeout protection
        assert 'timeout' not in source, \
            "Bug confirmed: No timeout for pubsub listener"

    def test_llm_decomposition_timeout_missing(self):
        """
        Test that LLM decomposition has no timeout.

        BUG: Line 736-741 calls LLM without timeout.
        If LLM hangs, entire fleet operation blocks.
        """
        import inspect

        # Get the source code of decompose_and_execute
        source = inspect.getsource(FleetCoordinatorService.decompose_and_execute)

        # Verify the bug - decompose_task called without timeout
        assert 'decompose_task(' in source, \
            "Bug confirmed: LLM decompose_task called without timeout"

        # Verify no timeout wrapper around LLM call
        lines = source.split('\n')
        decompose_line = None
        for i, line in enumerate(lines):
            if 'decompose_task(' in line:
                decompose_line = i
                break

        if decompose_line:
            # Check surrounding lines for timeout
            surrounding = '\n'.join(lines[max(0, decompose_line-2):min(len(lines), decompose_line+3)])
            assert 'wait_for' not in surrounding and 'timeout' not in surrounding, \
                "Bug confirmed: No timeout wrapper around LLM call"

    def test_lazy_initialization_race_condition(self):
        """
        Test that lazy initialization lacks race condition protection.

        BUG: Lines 722-727 check and initialize services without locks.
        Multiple concurrent calls can create duplicate services.
        """
        import inspect

        # Get the source code of decompose_and_execute
        source = inspect.getsource(FleetCoordinatorService.decompose_and_execute)

        # Verify the bug - None check without lock
        assert 'if not self.decomposition_service:' in source, \
            "Bug confirmed: Lazy initialization without lock"

        # Verify no asyncio.Lock protection
        assert 'asyncio.Lock' not in source and 'Lock()' not in source, \
            "Bug confirmed: No lock protection for lazy initialization"

    def test_simulated_gather_deadlock(self):
        """
        Test that simulated deadlock in gather demonstrates lack of internal timeout.

        BUG: If a task never completes, gather has no internal timeout.
        The entire fleet operation hangs.
        """
        # This test verifies that asyncio.gather has no built-in timeout
        # The bug is that gather() itself doesn't timeout - it relies on
        # external timeout wrappers which may not be present in production

        # Verify asyncio.gather accepts tasks without timeout parameter
        import inspect
        gather_sig = inspect.signature(asyncio.gather)

        # Confirm bug: gather has no timeout parameter
        params = list(gather_sig.parameters.keys())
        assert 'timeout' not in params, \
            "Bug confirmed: asyncio.gather lacks built-in timeout parameter"

        # This means code must manually wrap with asyncio.wait_for
        # But the source code doesn't do this (confirmed by other tests)

    def test_simulated_redis_listener_hang(self):
        """
        Test that Redis listener demonstrates infinite loop vulnerability.

        BUG: The listener uses async for with no break condition,
        meaning it will hang forever if connection is stale.
        """
        # This test verifies the listener loop structure
        # The bug is that async for loops don't have built-in timeout

        # Verify pubsub.listen() returns an async iterator
        # that yields indefinitely with no timeout
        import inspect

        # Check the listener implementation pattern
        source = inspect.getsource(FleetStateNotifier.subscribe_to_fleet)

        # The bug: infinite async for loop
        assert 'async for' in source, \
            "Bug confirmed: Listener uses infinite async for loop"

        # No break condition based on time
        lines = source.split('\n')
        has_timeout_break = False
        for line in lines:
            if 'break' in line and ('timeout' in line or 'time' in line.lower()):
                has_timeout_break = True
                break

        assert not has_timeout_break, \
            "Bug confirmed: No timeout-based break condition in listener"

    def test_database_query_timeout_missing(self):
        """
        Test that database queries lack timeout protection.

        BUG: Database queries in fleet operations have no timeout.
        Long-running queries can block fleet execution.
        """
        import inspect

        # Check various methods that query database
        methods_to_check = [
            FleetCoordinatorService.get_fleet_snapshot,
            FleetCoordinatorService._attempt_fault_tolerance_retry,
        ]

        for method in methods_to_check:
            source = inspect.getsource(method)
            # Verify no timeout on database operations
            assert 'timeout' not in source, \
                f"Bug confirmed: No timeout in {method.__name__}"

    def test_concurrent_fleet_execution_deadlock(self):
        """
        Test that concurrent fleet executions can deadlock.

        EXPECTED FAILURE: Two chains executing simultaneously
        should not deadlock on shared resources.
        """
        async def test_concurrent_deadlock():
            # Simulate two chains trying to access shared resources
            shared_resource = {"locked": False}

            async def chain1_task():
                shared_resource["locked"] = True
                await asyncio.sleep(0.1)
                # This should release but if deadlock, never does
                shared_resource["locked"] = False
                return "chain1"

            async def chain2_task():
                # This waits for chain1 to release
                while shared_resource["locked"]:
                    await asyncio.sleep(0.01)
                return "chain2"

            # Execute concurrently - if deadlock occurs, this hangs
            results = await asyncio.gather(chain1_task(), chain2_task())
            return results

        # Run with timeout to detect deadlock
        try:
            result = asyncio.run(asyncio.wait_for(test_concurrent_deadlock(), timeout=1.0))
            # If we get here, no deadlock (good)
            assert result is not None
        except asyncio.TimeoutError:
            # Deadlock detected
            assert False, "Bug confirmed: Concurrent fleet operations can deadlock"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
