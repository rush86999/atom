"""
Memory Leak Detection Tests

This package contains memory leak detection tests using Bloomberg's memray profiler.
These tests detect Python-level memory leaks in long-running backend operations.

Test Categories:
- Agent execution leaks: Memory growth during repeated agent execution
- Governance cache leaks: Unbounded cache growth and LRU eviction issues
- LLM streaming leaks: Memory accumulation during token generation

Requirements:
- Python 3.11+ (memray requirement)
- memray>=1.12.0 (install with: pip install memray)

Usage:
    # Run all memory leak tests (requires memray)
    pytest backend/tests/memory_leaks/ -v -m memory_leak

    # Run specific test file
    pytest backend/tests/memory_leaks/test_agent_execution_leaks.py -v

    # Skip gracefully if memray not installed
    pytest backend/tests/memory_leaks/ -v  # Tests will skip with pytest.skip

CI/CD Integration:
    - Marked with @pytest.mark.memory_leak and @pytest.mark.slow
    - Run weekly in CI pipeline (Sunday 2 AM UTC) via pytest marker selection
    - Tests skip gracefully if memray unavailable (no CI failure)

Performance Targets:
    - Agent execution: <10MB memory growth over 100 iterations
    - Governance cache: <5MB memory growth (LRU eviction working)
    - LLM streaming: <15MB memory growth over 1000 tokens

Phase: 243-01 (Memory & Performance Bug Discovery)
See: .planning/phases/243-memory-and-performance-bug-discovery/243-01-PLAN.md
"""
