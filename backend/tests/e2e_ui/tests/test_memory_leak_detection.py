"""
Memory leak detection tests using CDP heap snapshots.

These tests detect memory leaks in critical user flows by comparing
heap snapshots before and after operations. Tests use repeated operations
to amplify small leaks and make them detectable.

Test Coverage:
- Agent execution memory leaks (10 consecutive executions)
- Canvas presentation memory leaks (20 present/close cycles)
- Session persistence memory leaks (10 page navigation cycles)
- Event listener memory leaks (repeated add/remove)
"""

import pytest
from typing import Dict, Any

# Import memory fixtures
from backend.tests.e2e_ui.fixtures.memory_fixtures import (
    compare_heap_snapshots,
    get_heap_snapshot,
    memory_stats,
)


# ============================================================================
# Agent Execution Memory Leak Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.memory
def test_memory_leak_agent_execution(cdp_session, authenticated_page_api, db_session):
    """Test for memory leaks during repeated agent execution.

    This test executes the same agent 10 times and compares heap snapshots
    before and after to detect memory leaks. Agent execution should clean up
    properly after each run.

    Leak Thresholds:
    - leak_detected must be False
    - size_increase_bytes < 10MB (acceptable growth)

    Args:
        cdp_session: CDP session fixture for heap snapshots
        authenticated_page_api: Authenticated page fixture
        db_session: Database session fixture
    """
    # Import here to avoid circular dependencies
    from backend.tests.e2e_ui.fixtures.test_data_factory import AgentFactory
    from core.models import AgentRegistry

    # Create test agent
    agent = AgentFactory.create_agent(
        db_session,
        name="Memory Test Agent",
        description="Agent for memory leak testing",
        maturity_level="INTERN",
        config={
            "llm_provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7,
        }
    )

    # Take initial heap snapshot
    before_snapshot = get_heap_snapshot(cdp_session)
    initial_stats = memory_stats(cdp_session)

    print(f"\n[Memory] Initial heap usage: {initial_stats['percentage_used']:.2f}%")
    print(f"[Memory] Initial heap size: {before_snapshot['js_heap_size_used'] / (1024*1024):.2f} MB")

    # Execute agent 10 times (repeated execution amplifies leaks)
    for i in range(10):
        try:
            # Navigate to agent execution page
            authenticated_page_api.goto(f"http://localhost:3001/agents/{agent.id}")

            # Execute agent via API
            response = authenticated_page_api.request.post(
                f"http://localhost:8000/api/v1/agents/{agent.id}/execute",
                headers={"Content-Type": "application/json"},
                data={"query": f"Test query {i}"}
            )

            # Wait for response (don't care about result, just execution)
            # Small delay to allow async cleanup
            authenticated_page_api.wait_for_timeout(100)

        except Exception as e:
            # Agent execution might fail, we're testing memory not functionality
            print(f"[Warning] Agent execution {i} failed: {e}")
            continue

    # Take final heap snapshot
    after_snapshot = get_heap_snapshot(cdp_session)
    final_stats = memory_stats(cdp_session)

    print(f"[Memory] Final heap usage: {final_stats['percentage_used']:.2f}%")
    print(f"[Memory] Final heap size: {after_snapshot['js_heap_size_used'] / (1024*1024):.2f} MB")

    # Compare snapshots
    result = compare_heap_snapshots(before_snapshot, after_snapshot)

    print(f"\n[Memory Leak Detection Results]")
    print(f"  Size increase: {result['size_increase_mb']:.2f} MB")
    print(f"  Estimated detached nodes: {result['detached_nodes']}")
    print(f"  Leak detected: {result['leak_detected']}")

    # Assertions: No significant memory leak
    assert not result['leak_detected'], (
        f"Memory leak detected: {result['size_increase_mb']:.2f} MB growth, "
        f"{result['detached_nodes']} estimated detached nodes"
    )

    assert result['size_increase_bytes'] < 10 * 1024 * 1024, (
        f"Excessive memory growth: {result['size_increase_mb']:.2f} MB "
        f"(threshold: 10 MB)"
    )


# ============================================================================
# Canvas Presentation Memory Leak Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.memory
def test_memory_leak_canvas_cycles(cdp_session, authenticated_page_api, db_session):
    """Test for memory leaks during rapid canvas present/close cycles.

    This test presents and closes canvas 20 times using different canvas types
    (chart, sheet, form, docs) to detect DOM and canvas-related memory leaks.

    Leak Thresholds:
    - detached_nodes < 500 (some DOM nodes expected from rapid cycling)
    - size_increase_bytes < 5MB

    Args:
        cdp_session: CDP session fixture for heap snapshots
        authenticated_page_api: Authenticated page fixture
        db_session: Database session fixture
    """
    # Import here to avoid circular dependencies
    from backend.tests.e2e_ui.fixtures.test_data_factory import CanvasFactory
    from core.models import Canvas

    # Create test canvases of different types
    canvas_types = [
        ("chart", {"type": "line", "title": "Test Chart"}),
        ("sheet", {"rows": 10, "cols": 5, "data": [[1, 2, 3, 4, 5]]}),
        ("form", {"fields": [{"name": "test", "type": "text"}]}),
        ("docs", {"content": "# Test Document\n\nTest content here."}),
    ]

    canvases = []
    for canvas_type, config in canvas_types:
        canvas = CanvasFactory.create_canvas(
            db_session,
            type=canvas_type,
            title=f"Memory Test {canvas_type.title()}",
            config=config
        )
        canvases.append(canvas)

    # Take initial heap snapshot
    before_snapshot = get_heap_snapshot(cdp_session)
    initial_stats = memory_stats(cdp_session)

    print(f"\n[Memory] Initial heap usage: {initial_stats['percentage_used']:.2f}%")

    # Present and close canvas 20 times (rapid cycling)
    for i in range(20):
        for canvas in canvases:
            try:
                # Navigate to canvas page
                authenticated_page_api.goto(f"http://localhost:3001/canvas/{canvas.id}")

                # Present canvas via API
                response = authenticated_page_api.request.post(
                    f"http://localhost:8000/api/v1/canvas/{canvas.id}/present",
                    headers={"Content-Type": "application/json"}
                )

                # Close canvas (navigate away)
                authenticated_page_api.goto("http://localhost:3001/dashboard")

                # Small delay to allow cleanup
                authenticated_page_api.wait_for_timeout(50)

            except Exception as e:
                print(f"[Warning] Canvas cycle {i} failed: {e}")
                continue

    # Take final heap snapshot
    after_snapshot = get_heap_snapshot(cdp_session)
    final_stats = memory_stats(cdp_session)

    print(f"[Memory] Final heap usage: {final_stats['percentage_used']:.2f}%")

    # Compare snapshots
    result = compare_heap_snapshots(before_snapshot, after_snapshot)

    print(f"\n[Canvas Memory Leak Detection Results]")
    print(f"  Size increase: {result['size_increase_mb']:.2f} MB")
    print(f"  Estimated detached nodes: {result['detached_nodes']}")

    # Assertions: No significant canvas-related memory leak
    # Some DOM nodes expected from rapid cycling, but <500 is acceptable
    assert result['detached_nodes'] < 500, (
        f"Too many detached DOM nodes: {result['detached_nodes']} "
        f"(threshold: 500)"
    )

    assert result['size_increase_bytes'] < 5 * 1024 * 1024, (
        f"Excessive memory growth: {result['size_increase_mb']:.2f} MB "
        f"(threshold: 5 MB)"
    )


# ============================================================================
# Session Persistence Memory Leak Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.memory
def test_memory_leak_session_persistence(cdp_session, authenticated_page_api):
    """Test for memory leaks during page navigation cycles.

    This test simulates a user navigating between pages (dashboard -> agents ->
    canvas -> workflows) 10 times to detect session-related memory leaks.

    Leak Thresholds:
    - size_increase_bytes < 8MB

    Args:
        cdp_session: CDP session fixture for heap snapshots
        authenticated_page_api: Authenticated page fixture
    """
    # Take initial heap snapshot
    before_snapshot = get_heap_snapshot(cdp_session)
    initial_stats = memory_stats(cdp_session)

    print(f"\n[Memory] Initial heap usage: {initial_stats['percentage_used']:.2f}%")

    # Navigate between pages 10 times
    pages = [
        "http://localhost:3001/dashboard",
        "http://localhost:3001/agents",
        "http://localhost:3001/workflows",
    ]

    for i in range(10):
        for page_url in pages:
            try:
                authenticated_page_api.goto(page_url)
                authenticated_page_api.wait_for_load_state("networkidle")
                # Small delay to simulate user reading time
                authenticated_page_api.wait_for_timeout(100)
            except Exception as e:
                print(f"[Warning] Navigation to {page_url} failed: {e}")
                continue

    # Take final heap snapshot
    after_snapshot = get_heap_snapshot(cdp_session)
    final_stats = memory_stats(cdp_session)

    print(f"[Memory] Final heap usage: {final_stats['percentage_used']:.2f}%")

    # Compare snapshots
    result = compare_heap_snapshots(before_snapshot, after_snapshot)

    print(f"\n[Session Memory Leak Detection Results]")
    print(f"  Size increase: {result['size_increase_mb']:.2f} MB")
    print(f"  Heap usage change: {result['percentage_used_after'] - result['percentage_used_before']:.2f}%")

    # Assertion: No significant session-related memory leak
    assert result['size_increase_bytes'] < 8 * 1024 * 1024, (
        f"Excessive memory growth: {result['size_increase_mb']:.2f} MB "
        f"(threshold: 8 MB)"
    )


# ============================================================================
# Event Listener Memory Leak Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.memory
def test_memory_leak_event_listeners(cdp_session, authenticated_page_api):
    """Test for memory leaks from event listeners not being removed.

    This test adds and removes event listeners repeatedly to verify
    that listeners are properly cleaned up and don't leak memory.

    Leak Thresholds:
    - detached_nodes < 200 (DOM nodes with lingering handlers)

    Args:
        cdp_session: CDP session fixture for heap snapshots
        authenticated_page_api: Authenticated page fixture
    """
    # Take initial heap snapshot
    before_snapshot = get_heap_snapshot(cdp_session)
    initial_stats = memory_stats(cdp_session)

    print(f"\n[Memory] Initial heap usage: {initial_stats['percentage_used']:.2f}%")

    # Navigate to a page with interactive elements
    authenticated_page_api.goto("http://localhost:3001/dashboard")

    # Add and remove event listeners repeatedly
    for i in range(20):
        try:
            # Add event listeners
            authenticated_page_api.evaluate("""() => {
                // Add click listeners to multiple elements
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                buttons.forEach(btn => {
                    btn.addEventListener('click', function handler() {
                        console.log('Click event', i);
                    });
                });
            }""")

            # Remove event listeners (by cloning nodes)
            authenticated_page_api.evaluate("""() => {
                // Remove all event listeners by cloning nodes
                const buttons = document.querySelectorAll('button, a, [role="button"]');
                buttons.forEach(btn => {
                    const clone = btn.cloneNode(true);
                    btn.parentNode.replaceChild(clone, btn);
                });
            }""")

            # Small delay to allow garbage collection
            authenticated_page_api.wait_for_timeout(50)

        except Exception as e:
            print(f"[Warning] Event listener cycle {i} failed: {e}")
            continue

    # Take final heap snapshot
    after_snapshot = get_heap_snapshot(cdp_session)
    final_stats = memory_stats(cdp_session)

    print(f"[Memory] Final heap usage: {final_stats['percentage_used']:.2f}%")

    # Compare snapshots
    result = compare_heap_snapshots(before_snapshot, after_snapshot)

    print(f"\n[Event Listener Memory Leak Detection Results]")
    print(f"  Size increase: {result['size_increase_mb']:.2f} MB")
    print(f"  Estimated detached nodes: {result['detached_nodes']}")

    # Assertion: No significant event listener leak
    # Some nodes expected, but <200 is acceptable
    assert result['detached_nodes'] < 200, (
        f"Too many detached DOM nodes with event handlers: {result['detached_nodes']} "
        f"(threshold: 200)"
    )


# ============================================================================
# Helper Functions
# ============================================================================

@pytest.mark.e2e
@pytest.mark.memory
def test_memory_stats_helper(cdp_session):
    """Test the memory_stats helper function.

    This test verifies that the memory_stats helper correctly retrieves
    memory metrics from the browser and calculates derived metrics.

    Args:
        cdp_session: CDP session fixture
    """
    stats = memory_stats(cdp_session)

    # Verify all required keys exist
    assert "js_heap_used_size" in stats
    assert "js_heap_total_size" in stats
    assert "js_heap_size_limit" in stats
    assert "percentage_used" in stats
    assert "available_bytes" in stats

    # Verify values are reasonable
    assert stats["js_heap_used_size"] > 0, "Heap used size should be positive"
    assert stats["js_heap_size_limit"] > 0, "Heap limit should be positive"
    assert 0 <= stats["percentage_used"] <= 100, "Percentage should be 0-100"
    assert stats["available_bytes"] >= 0, "Available bytes should be non-negative"

    print(f"\n[Memory Stats]")
    print(f"  Used: {stats['js_heap_used_size'] / (1024*1024):.2f} MB")
    print(f"  Total: {stats['js_heap_total_size'] / (1024*1024):.2f} MB")
    print(f"  Limit: {stats['js_heap_size_limit'] / (1024*1024):.2f} MB")
    print(f"  Usage: {stats['percentage_used']:.2f}%")
    print(f"  Available: {stats['available_bytes'] / (1024*1024):.2f} MB")
