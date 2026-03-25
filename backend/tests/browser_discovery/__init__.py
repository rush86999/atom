"""
Browser discovery tests for automated UI bug detection.

Test Categories:
- BROWSER-01: Intelligent exploration agent (DFS, BFS, random walk)
- BROWSER-02: Console error detection (JavaScript errors, exceptions)
- BROWSER-03: Accessibility violations (axe-core, WCAG 2.1 AA)
- BROWSER-04: Broken link detection (404s, redirect loops)
- BROWSER-05: Visual regression testing (Percy integration)
- BROWSER-06: Form filling edge cases (null bytes, XSS, SQL injection)
- BROWSER-07: API-first authentication (10-100x faster than UI login)

See: README.md for usage instructions and fixture documentation.
"""

__all__ = [
    "test_console_errors",
    "test_accessibility",
    "test_broken_links",
    "test_form_filling",
    "test_visual_regression",
    "test_exploration_agent",
]

import pytest
pytest_plugins = ["tests.browser_discovery.conftest"]
