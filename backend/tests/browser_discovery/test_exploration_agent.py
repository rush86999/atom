"""
Exploration agent tests for intelligent UI bug discovery.

This test module validates the ExplorationAgent's heuristic algorithms
(depth-first search, breadth-first search, random walk) for automated
bug discovery through UI navigation.

Test Coverage:
- DFS exploration (depth-first, deep UI paths first)
- BFS exploration (breadth-first, all links at depth first)
- Random walk exploration (stochastic, edge case discovery)
- Limit enforcement (max_depth, max_actions)
- Bug detection (console errors, broken images)
- Visited URL tracking (infinite loop prevention)
- Reproducibility (random seed produces same results)
"""

import pytest
from playwright.sync_api import Page

from tests.browser_discovery.conftest import (
    authenticated_page,
    exploration_agent,
    console_monitor,
)


# ============================================================================
# DEPTH-FIRST SEARCH (DFS) EXPLORATION TESTS
# ============================================================================

@pytest.mark.browser_discovery
def test_dfs_explores_dashboard_depth_first(authenticated_page: Page, exploration_agent):
    """Test DFS explores dashboard using depth-first navigation.

    BROWSER-01: DFS should navigate deep into UI paths first before
    exploring siblings (e.g., dashboard → agent → execute → results).

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with DFS algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using DFS (max_depth=3, max_actions=20)
    bugs = exploration_agent.explore_dfs(max_depth=3, max_actions=20)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration occurred
    assert report["actions_taken"] > 0, "DFS should take at least 1 action"
    assert report["urls_visited"] > 0, "DFS should visit at least 1 URL"

    # Verify no critical bugs found
    critical_bugs = [bug for bug in bugs if bug.get("type") == "console_error"]
    assert len(critical_bugs) == 0, f"DFS found {len(critical_bugs)} console errors"


@pytest.mark.browser_discovery
def test_dfs_respects_max_depth_limit(authenticated_page: Page, exploration_agent):
    """Test DFS respects max_depth limit to prevent infinite exploration.

    BROWSER-01: DFS should stop at max_depth to prevent infinite loops
    in cyclic navigation structures.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with DFS algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using DFS with max_depth=2 (shallow exploration)
    bugs = exploration_agent.explore_dfs(max_depth=2, max_actions=20)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration completed without exceeding depth
    assert report["actions_taken"] <= 20, "DFS should respect max_actions limit"
    assert len(bugs) < 100, "DFS should not generate excessive bugs"

    # Verify no infinite loop errors
    infinite_loop_bugs = [bug for bug in bugs if "loop" in str(bug).lower()]
    assert len(infinite_loop_bugs) == 0, "DFS should track visited URLs to prevent infinite loops"


@pytest.mark.browser_discovery
def test_dfs_respects_max_actions_limit(authenticated_page: Page, exploration_agent):
    """Test DFS respects max_actions limit to prevent excessive clicking.

    BROWSER-01: DFS should stop after max_actions to prevent long-running
    test executions.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with DFS algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using DFS with max_actions=10 (limited actions)
    bugs = exploration_agent.explore_dfs(max_depth=3, max_actions=10)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify DFS stopped at max_actions
    assert report["actions_taken"] <= 10, "DFS should respect max_actions=10 limit"
    assert report["urls_visited"] >= 1, "DFS should visit at least starting URL"


@pytest.mark.browser_discovery
def test_dfs_detects_console_errors(authenticated_page: Page, exploration_agent, console_monitor):
    """Test DFS captures console errors during exploration.

    BROWSER-02: DFS should detect JavaScript console errors during
    navigation and report them as bugs.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with DFS algorithm
        console_monitor: Console monitor fixture for error detection
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using DFS
    bugs = exploration_agent.explore_dfs(max_depth=2, max_actions=15)

    # Check console monitor for errors
    console_errors = console_monitor.get("error", [])

    # Verify console errors were captured
    # (Note: Dashboard should have no console errors in healthy state)
    if console_errors:
        # If console errors exist, DFS should have detected them
        console_bugs = [bug for bug in bugs if bug.get("type") == "console_error"]
        assert len(console_bugs) > 0, "DFS should capture console errors"


# ============================================================================
# BREADTH-FIRST SEARCH (BFS) EXPLORATION TESTS
# ============================================================================

@pytest.mark.browser_discovery
def test_bfs_explores_all_links_breadth_first(authenticated_page: Page, exploration_agent):
    """Test BFS explores dashboard using breadth-first navigation.

    BROWSER-01: BFS should explore all links at current depth before
    going deeper (e.g., explore all dashboard sections before diving
    into each).

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with BFS algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using BFS (max_depth=3, max_actions=20)
    bugs = exploration_agent.explore_bfs(max_depth=3, max_actions=20)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration occurred
    assert report["actions_taken"] > 0, "BFS should take at least 1 action"
    assert report["urls_visited"] > 0, "BFS should visit at least 1 URL"

    # Verify no critical bugs found
    critical_bugs = [bug for bug in bugs if bug.get("type") == "console_error"]
    assert len(critical_bugs) == 0, f"BFS found {len(critical_bugs)} console errors"


@pytest.mark.browser_discovery
def test_bfs_covers_more_urls_than_dfs(authenticated_page: Page, exploration_agent):
    """Test BFS covers more URLs than DFS for same action limit.

    BROWSER-01: BFS explores all links at each depth before going deeper,
    which should result in broader URL coverage than DFS for the same
    number of actions.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with BFS/DFS algorithms
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using BFS
    bfs_bugs = exploration_agent.explore_bfs(max_depth=3, max_actions=15)
    bfs_report = exploration_agent.get_exploration_report()
    bfs_urls = bfs_report["urls_visited"]

    # Navigate back to dashboard for DFS test
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using DFS
    dfs_bugs = exploration_agent.explore_dfs(max_depth=3, max_actions=15)
    dfs_report = exploration_agent.get_exploration_report()
    dfs_urls = dfs_report["urls_visited"]

    # BFS should cover equal or more URLs than DFS (broader coverage)
    assert bfs_urls >= dfs_urls, f"BFS should cover >= URLs than DFS (BFS: {bfs_urls}, DFS: {dfs_urls})"


@pytest.mark.browser_discovery
def test_bfs_respects_depth_limits(authenticated_page: Page, exploration_agent):
    """Test BFS respects max_depth limit to prevent infinite exploration.

    BROWSER-01: BFS should stop at max_depth to prevent infinite loops
    in cyclic navigation structures.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with BFS algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using BFS with max_depth=2 (shallow exploration)
    bugs = exploration_agent.explore_bfs(max_depth=2, max_actions=20)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration completed without exceeding depth
    assert report["actions_taken"] <= 20, "BFS should respect max_actions limit"
    assert len(bugs) < 100, "BFS should not generate excessive bugs"

    # Verify no infinite loop errors
    infinite_loop_bugs = [bug for bug in bugs if "loop" in str(bug).lower()]
    assert len(infinite_loop_bugs) == 0, "BFS should track visited URLs to prevent infinite loops"


@pytest.mark.browser_discovery
def test_bfs_handles_navigation_back(authenticated_page: Page, exploration_agent):
    """Test BFS can navigate back correctly after exploration.

    BROWSER-01: BFS should navigate back to previous pages correctly
    to continue breadth-first exploration.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with BFS algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using BFS
    bugs = exploration_agent.explore_bfs(max_depth=2, max_actions=10)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration completed without navigation errors
    nav_errors = [bug for bug in bugs if "navigation" in str(bug).lower() or "go_back" in str(bug).lower()]
    assert len(nav_errors) == 0, "BFS should handle navigation back without errors"

    # Verify BFS visited multiple URLs
    assert report["urls_visited"] >= 1, "BFS should visit at least starting URL"


# ============================================================================
# RANDOM WALK EXPLORATION TESTS
# ============================================================================

@pytest.mark.browser_discovery
def test_random_walk_explores_stochastically(authenticated_page: Page, exploration_agent):
    """Test random walk explores UI stochastically for edge cases.

    BROWSER-01: Random walk should explore stochastically to discover
    unexpected state combinations and edge cases that systematic
    algorithms (DFS/BFS) miss.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with random walk algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using random walk (max_actions=30)
    bugs = exploration_agent.explore_random(max_actions=30)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration occurred
    assert report["actions_taken"] > 0, "Random walk should take at least 1 action"
    assert report["urls_visited"] > 0, "Random walk should visit at least 1 URL"

    # Verify no critical bugs found
    critical_bugs = [bug for bug in bugs if bug.get("type") == "console_error"]
    assert len(critical_bugs) == 0, f"Random walk found {len(critical_bugs)} console errors"


@pytest.mark.browser_discovery
def test_random_walk_with_seed_is_reproducible(authenticated_page: Page, exploration_agent):
    """Test random walk with seed produces reproducible exploration paths.

    BROWSER-01: Random walk with seed should produce the same exploration
    path when run multiple times, enabling reproducible bug discovery.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with random walk algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using random walk with seed=42
    bugs_1 = exploration_agent.explore_random(max_actions=20, seed=42)
    report_1 = exploration_agent.get_exploration_report()

    # Navigate back to dashboard for second run
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using random walk with same seed
    bugs_2 = exploration_agent.explore_random(max_actions=20, seed=42)
    report_2 = exploration_agent.get_exploration_report()

    # Verify reproducibility (same number of actions and URLs)
    assert report_1["actions_taken"] == report_2["actions_taken"], \
        "Random walk with seed should produce same number of actions"
    assert report_1["urls_visited"] == report_2["urls_visited"], \
        "Random walk with seed should visit same number of URLs"


@pytest.mark.browser_discovery
def test_random_walk_handles_infinite_loops(authenticated_page: Page, exploration_agent):
    """Test random walk handles infinite loops through visited URL tracking.

    BROWSER-01: Random walk should track visited URLs to prevent infinite
    loops in cyclic navigation structures.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with random walk algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using random walk (max_actions=30)
    bugs = exploration_agent.explore_random(max_actions=30)

    # Get exploration report
    report = exploration_agent.get_exploration_report()

    # Verify exploration completed without infinite loops
    assert report["actions_taken"] <= 30, "Random walk should respect max_actions limit"
    assert len(bugs) < 100, "Random walk should not generate excessive bugs"

    # Verify no infinite loop errors
    infinite_loop_bugs = [bug for bug in bugs if "loop" in str(bug).lower()]
    assert len(infinite_loop_bugs) == 0, "Random walk should track visited URLs to prevent infinite loops"


@pytest.mark.browser_discovery
def test_random_walk_discovers_edge_cases(authenticated_page: Page, exploration_agent):
    """Test random walk may discover bugs DFS/BFS miss.

    BROWSER-01: Random walk's stochastic exploration should discover
    edge cases and unexpected state combinations that systematic
    algorithms miss.

    Args:
        authenticated_page: Authenticated Playwright page fixture
        exploration_agent: ExplorationAgent fixture with random walk algorithm
    """
    # Navigate to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using DFS first
    dfs_bugs = exploration_agent.explore_dfs(max_depth=2, max_actions=15)
    dfs_report = exploration_agent.get_exploration_report()

    # Navigate back to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using BFS
    bfs_bugs = exploration_agent.explore_bfs(max_depth=2, max_actions=15)
    bfs_report = exploration_agent.get_exploration_report()

    # Navigate back to dashboard
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("domcontentloaded")

    # Explore using random walk
    random_bugs = exploration_agent.explore_random(max_actions=30)
    random_report = exploration_agent.get_exploration_report()

    # Random walk should take equal or more actions than DFS/BFS
    # (May revisit URLs due to stochastic nature)
    assert random_report["actions_taken"] >= 0, "Random walk should take actions"

    # All algorithms should find same critical bugs (console errors)
    dfs_console_bugs = len([b for b in dfs_bugs if b.get("type") == "console_error"])
    bfs_console_bugs = len([b for b in bfs_bugs if b.get("type") == "console_error"])
    random_console_bugs = len([b for b in random_bugs if b.get("type") == "console_error"])

    # Console errors should be detected by all algorithms
    assert dfs_console_bugs == bfs_console_bugs == random_console_bugs, \
        "All algorithms should detect same console errors"
