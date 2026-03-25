"""
Feedback loops package for bug discovery automation.

This package provides services for closing the feedback loop:
- RegressionTestGenerator: Convert bugs to pytest test files
- BugFixVerifier: Verify fixes and close GitHub issues
- ROITracker: Track ROI metrics for bug discovery automation
"""

from tests.bug_discovery.feedback_loops.regression_test_generator import RegressionTestGenerator

__all__ = [
    "RegressionTestGenerator",
]
