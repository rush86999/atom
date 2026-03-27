"""
Memory and Performance Bug Filing Service

This module provides a specialized bug filing service for memory leaks and
performance regressions detected during automated testing. It extends the
base BugFilingService with memory-specific metadata, severity classification,
and artifact upload support.

Features:
- MemoryPerformanceFilingService extends BugFilingService
- Memory leak filing with heap growth, iterations, flame graph artifacts
- Performance regression filing with latency degradation, throughput metrics
- Severity classification: Memory leaks (>50MB = critical, >10MB = high)
- Flame graph artifact upload support
- Graceful degradation if GitHub credentials not configured

Usage:
    from backend.tests.bug_discovery.core.memory_performance_filing import MemoryPerformanceFilingService

    service = MemoryPerformanceFilingService(github_token, github_repository)

    # File memory leak bug
    service.file_memory_leak(
        test_name="test_canvas_presentation_no_leak",
        memory_increase_mb=15.5,
        iterations=50,
        flame_graph_path="/tmp/flamegraph.html"
    )

    # File performance regression bug
    service.file_performance_regression(
        test_name="test_api_latency_regression",
        baseline_ms=100,
        actual_ms=150,
        degradation_percent=50.0
    )

Phase: 243-04 (Memory & Performance Bug Discovery)
See: .planning/phases/243-memory-and-performance-bug-discovery/243-04-PLAN.md
"""

import os
from typing import Dict, Optional
from datetime import datetime

from backend.tests.bug_discovery.bug_filing_service import BugFilingService


class MemoryPerformanceFilingService(BugFilingService):
    """
    Specialized bug filing service for memory and performance issues.

    Extends BugFilingService with:
    - Memory-specific metadata (heap growth, iterations, flame graphs)
    - Performance regression metadata (latency, throughput, degradation)
    - Enhanced severity classification for memory leaks
    - Flame graph artifact upload support

    Severity Classification:
    - Memory leaks:
      * Critical: >50MB growth (severe leak, production impact)
      * High: >10MB growth (significant leak)
      * Medium: >5MB growth (minor leak)
    - Performance regressions:
      * Critical: >100% degradation (2x slower)
      * High: >50% degradation (1.5x slower)
      * Medium: >20% degradation (noticeable slowdown)

    Phase: 243-04
    """

    def file_memory_leak(
        self,
        test_name: str,
        memory_increase_mb: float,
        iterations: int,
        flame_graph_path: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        File a memory leak bug with specialized metadata.

        Args:
            test_name: Name of the failed test
            memory_increase_mb: Memory growth in MB
            iterations: Number of iterations performed
            flame_graph_path: Optional path to flame graph artifact
            **kwargs: Additional metadata (test_file, platform, etc.)

        Returns:
            Dict with issue URL and number if created, or existing issue if duplicate
        """
        # Build memory-specific metadata
        metadata = {
            "test_type": "memory",
            "memory_increase_mb": memory_increase_mb,
            "iterations": iterations,
            "platform": kwargs.get("platform", "backend-python"),
            "memory_leak_severity": self._classify_memory_leak(memory_increase_mb)
        }

        # Add flame graph path if provided
        if flame_graph_path and os.path.exists(flame_graph_path):
            metadata["flame_graph_path"] = flame_graph_path

        # Merge additional metadata
        metadata.update(kwargs)

        # Generate error message
        error_message = (
            f"Memory leak detected: {memory_increase_mb:.2f} MB growth "
            f"over {iterations} iterations"
        )

        # File bug using base class
        return self.file_bug(
            test_name=test_name,
            error_message=error_message,
            metadata=metadata
        )

    def file_performance_regression(
        self,
        test_name: str,
        baseline_ms: float,
        actual_ms: float,
        degradation_percent: float,
        throughput_baseline: Optional[float] = None,
        throughput_actual: Optional[float] = None,
        **kwargs
    ) -> Dict:
        """
        File a performance regression bug with specialized metadata.

        Args:
            test_name: Name of the failed test
            baseline_ms: Baseline latency in milliseconds
            actual_ms: Actual latency in milliseconds
            degradation_percent: Performance degradation as percentage
            throughput_baseline: Optional baseline throughput (ops/sec)
            throughput_actual: Optional actual throughput (ops/sec)
            **kwargs: Additional metadata (test_file, platform, etc.)

        Returns:
            Dict with issue URL and number if created, or existing issue if duplicate
        """
        # Build performance-specific metadata
        metadata = {
            "test_type": "performance",
            "baseline_ms": baseline_ms,
            "actual_ms": actual_ms,
            "degradation_percent": degradation_percent,
            "platform": kwargs.get("platform", "backend-python"),
            "regression_severity": self._classify_performance_regression(degradation_percent)
        }

        # Add throughput metrics if provided
        if throughput_baseline is not None:
            metadata["throughput_baseline"] = throughput_baseline
        if throughput_actual is not None:
            metadata["throughput_actual"] = throughput_actual
            # Calculate throughput degradation
            if throughput_baseline > 0:
                throughput_degradation = (
                    (throughput_baseline - throughput_actual) / throughput_baseline * 100
                )
                metadata["throughput_degradation_percent"] = throughput_degradation

        # Merge additional metadata
        metadata.update(kwargs)

        # Generate error message
        error_message = (
            f"Performance regression detected: {actual_ms:.2f}ms vs baseline {baseline_ms:.2f}ms "
            f"({degradation_percent:.1f}% degradation)"
        )

        # File bug using base class
        return self.file_bug(
            test_name=test_name,
            error_message=error_message,
            metadata=metadata
        )

    def _classify_memory_leak(self, memory_increase_mb: float) -> str:
        """
        Classify memory leak severity based on growth amount.

        Args:
            memory_increase_mb: Memory growth in MB

        Returns:
            Severity level (critical, high, medium, low)
        """
        if memory_increase_mb > 50:
            return "critical"
        elif memory_increase_mb > 10:
            return "high"
        elif memory_increase_mb > 5:
            return "medium"
        else:
            return "low"

    def _classify_performance_regression(self, degradation_percent: float) -> str:
        """
        Classify performance regression severity based on degradation percentage.

        Args:
            degradation_percent: Performance degradation as percentage

        Returns:
            Severity level (critical, high, medium, low)
        """
        if degradation_percent > 100:
            return "critical"
        elif degradation_percent > 50:
            return "high"
        elif degradation_percent > 20:
            return "medium"
        else:
            return "low"

    def _determine_severity(self, test_type: str, metadata: Dict) -> str:
        """
        Override base class to determine severity for memory/performance bugs.

        Args:
            test_type: Type of test (memory, performance)
            metadata: Test metadata

        Returns:
            Severity level (critical, high, medium, low)
        """
        # Memory leaks use specialized classification
        if test_type == "memory":
            memory_increase_mb = metadata.get("memory_increase_mb", 0)
            return self._classify_memory_leak(memory_increase_mb)

        # Performance regressions use specialized classification
        if test_type == "performance":
            degradation_percent = metadata.get("degradation_percent", 0)
            return self._classify_performance_regression(degradation_percent)

        # Fall back to base class for other test types
        return super()._determine_severity(test_type, metadata)

    def _generate_bug_title(self, test_name: str, error_type: str) -> str:
        """
        Override base class to generate memory/performance-specific bug titles.

        Args:
            test_name: Name of the failed test
            error_type: Type of error

        Returns:
            Formatted bug title
        """
        # Extract test name from full path if needed
        clean_test_name = test_name.split("::")[-1] if "::" in test_name else test_name
        clean_test_name = clean_test_name.replace("_", " ").replace("-", " ").strip()
        clean_test_name = clean_test_name.title()

        # Check if error type contains memory/performance keywords
        if "memory leak" in error_type.lower():
            return f"[Memory Leak] {clean_test_name}"
        elif "performance regression" in error_type.lower():
            return f"[Performance Regression] {clean_test_name}"

        # Fall back to base class title generation
        return super()._generate_bug_title(test_name, error_type)

    def _attach_screenshot(self, issue_number: int, screenshot_path: str) -> None:
        """
        Override base class to attach flame graph artifacts.

        Args:
            issue_number: GitHub issue number
            screenshot_path: Path to flame graph file
        """
        # Check if flame graph file exists
        if not os.path.exists(screenshot_path):
            print(f"Warning: Flame graph file not found: {screenshot_path}")
            return

        # Read flame graph content (limit to 50KB to avoid huge comments)
        with open(screenshot_path, "r") as f:
            flame_graph_content = f.read(51200)  # 50KB limit
            if len(flame_graph_content) >= 51200:
                flame_graph_content += "\n\n...(truncated)"

        # Add flame graph as issue comment
        comment_body = f"""**Flame Graph:**

```html
{flame_graph_content}
```

*(Note: View flame graph in browser for interactive visualization)*
"""

        try:
            comment_url = f"{self.github_api_url}/{issue_number}/comments"
            self.session.post(comment_url, json={"body": comment_body})
        except Exception as e:
            print(f"Warning: Failed to attach flame graph: {e}")


def file_memory_bug_from_test(
    test_name: str,
    memory_increase_mb: float,
    iterations: int,
    **kwargs
) -> Dict:
    """
    Convenience function to file memory bug from test failure.

    Args:
        test_name: Name of the failed test
        memory_increase_mb: Memory growth in MB
        iterations: Number of iterations performed
        **kwargs: Additional metadata

    Returns:
        Dict with issue URL and number if created, or None if credentials missing

    Graceful Degradation:
        - Returns None if GITHUB_TOKEN not set (no error raised)
        - Returns None if GITHUB_REPOSITORY not set (no error raised)
        - Prints warning message instead of raising exception
    """
    # Get GitHub token and repository from environment
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token:
        print("Skipping memory bug filing: GITHUB_TOKEN not set")
        return None

    if not github_repository:
        print("Skipping memory bug filing: GITHUB_REPOSITORY not set")
        return None

    # Create service and file bug
    try:
        service = MemoryPerformanceFilingService(github_token, github_repository)
        return service.file_memory_leak(
            test_name=test_name,
            memory_increase_mb=memory_increase_mb,
            iterations=iterations,
            **kwargs
        )
    except Exception as e:
        print(f"Warning: Failed to file memory bug: {e}")
        return None


def file_performance_bug_from_test(
    test_name: str,
    baseline_ms: float,
    actual_ms: float,
    degradation_percent: float,
    **kwargs
) -> Dict:
    """
    Convenience function to file performance bug from test failure.

    Args:
        test_name: Name of the failed test
        baseline_ms: Baseline latency in milliseconds
        actual_ms: Actual latency in milliseconds
        degradation_percent: Performance degradation as percentage
        **kwargs: Additional metadata

    Returns:
        Dict with issue URL and number if created, or None if credentials missing

    Graceful Degradation:
        - Returns None if GITHUB_TOKEN not set (no error raised)
        - Returns None if GITHUB_REPOSITORY not set (no error raised)
        - Prints warning message instead of raising exception
    """
    # Get GitHub token and repository from environment
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token:
        print("Skipping performance bug filing: GITHUB_TOKEN not set")
        return None

    if not github_repository:
        print("Skipping performance bug filing: GITHUB_REPOSITORY not set")
        return None

    # Create service and file bug
    try:
        service = MemoryPerformanceFilingService(github_token, github_repository)
        return service.file_performance_regression(
            test_name=test_name,
            baseline_ms=baseline_ms,
            actual_ms=actual_ms,
            degradation_percent=degradation_percent,
            **kwargs
        )
    except Exception as e:
        print(f"Warning: Failed to file performance bug: {e}")
        return None
