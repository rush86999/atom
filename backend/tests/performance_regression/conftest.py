"""
Performance Regression Test Fixtures

Provides fixtures for performance regression detection:
- performance_baseline: Loads historical baseline measurements from JSON
- check_regression: Validates current performance against baseline with threshold
- update_baseline: Helper to update baseline when performance improves

Usage:
    def test_api_latency(benchmark, check_regression):
        response = benchmark(make_api_call)

        # Check against baseline (20% threshold)
        check_regression(benchmark.stats.stats.mean, "api_get_agents_latency")

Reference: Phase 243 Plan 02 - Performance Regression Detection
"""

import json
from pathlib import Path
from typing import Dict, Any

import pytest


@pytest.fixture(scope="session")
def performance_baseline() -> Dict[str, float]:
    """
    Load performance baseline from JSON file.

    Returns dictionary of baseline measurements keyed by metric name.
    Returns empty dict if baseline file doesn't exist (first run).

    Baseline format:
    {
        "generated_at": "2026-03-25T00:00:00Z",
        "baselines": {
            "api_get_agents_latency": 0.050,
            "api_health_check_latency": 0.005,
            "db_agent_query": 0.010,
            "cache_hit_rate": 0.95,
            "cache_get_latency": 0.001
        }
    }

    Returns:
        Dict[str, float]: Baseline measurements
    """
    baseline_file = Path(__file__).parent.parent / "performance_baseline.json"

    if not baseline_file.exists():
        # No baseline yet - return empty dict
        return {}

    try:
        with open(baseline_file, "r") as f:
            data = json.load(f)
            return data.get("baselines", {})
    except (json.JSONDecodeError, IOError) as e:
        # Log warning but don't fail - tests will run without baseline
        print(f"Warning: Could not load baseline file: {e}")
        return {}


@pytest.fixture(scope="function")
def check_regression(performance_baseline: Dict[str, float]) -> callable:
    """
    Create regression checker function.

    Validates current performance value against historical baseline.
    Fails test if performance degrades beyond threshold (20% by default).

    Args:
        performance_baseline: Loaded baseline measurements

    Returns:
        callable: Function that checks regression

    Example:
        def test_api_latency(benchmark, check_regression):
            response = benchmark(make_api_call)
            check_regression(benchmark.stats.stats.mean, "api_get_agents_latency")
    """
    def _check(
        current_value: float,
        metric_name: str,
        threshold: float = 0.2
    ) -> None:
        """
        Check if current value regresses against baseline.

        Args:
            current_value: Current performance measurement (seconds for latency,
                          count for hit rate, etc.)
            metric_name: Name of metric to check against baseline
            threshold: Regression threshold as decimal (0.2 = 20%)

        Raises:
            AssertionError: If performance regresses beyond threshold

        Note:
            - Skips check if no baseline exists (first run)
            - Fails if current_value > baseline * (1 + threshold)
            - For hit rates (higher is better), inverts the check
        """
        if metric_name not in performance_baseline:
            # No baseline - skip check (first run or new metric)
            return

        baseline = performance_baseline[metric_name]

        # Detect if this is a hit rate (higher is better)
        # Hit rates are typically 0-1, latencies are >0
        if baseline <= 1.0 and current_value <= 1.0:
            # Hit rate - check for degradation (lower is worse)
            regression_threshold = baseline * (1 - threshold)
            if current_value < regression_threshold:
                percent_change = ((current_value - baseline) / baseline) * 100
                raise AssertionError(
                    f"Performance regression: {metric_name} = {current_value:.4f} "
                    f"(baseline: {baseline:.4f}, threshold: {regression_threshold:.4f}, "
                    f"change: {percent_change:.1f}%)"
                )
        else:
            # Latency - check for increase (higher is worse)
            regression_threshold = baseline * (1 + threshold)
            if current_value > regression_threshold:
                percent_change = ((current_value - baseline) / baseline) * 100
                raise AssertionError(
                    f"Performance regression: {metric_name} = {current_value:.4f}s "
                    f"(baseline: {baseline:.4f}s, threshold: {regression_threshold:.4f}s, "
                    f"change: +{percent_change:.1f}%)"
                )

    return _check


@pytest.fixture(scope="session")
def baseline_file_path() -> Path:
    """
    Get path to performance baseline file.

    Returns:
        Path: Path to performance_baseline.json
    """
    return Path(__file__).parent.parent / "performance_baseline.json"


def update_baseline_on_improvement(
    metric_name: str,
    current_value: float,
    baseline_value: float,
    improvement_threshold: float = 0.1
) -> bool:
    """
    Check if performance improved enough to update baseline.

    Args:
        metric_name: Name of metric
        current_value: Current performance value
        baseline_value: Existing baseline value
        improvement_threshold: Improvement threshold (0.1 = 10%)

    Returns:
        bool: True if baseline should be updated

    Note:
        For hit rates (higher is better), checks if current > baseline * (1 + threshold)
        For latencies (lower is better), checks if current < baseline * (1 - threshold)
    """
    # Detect hit rate vs latency
    if baseline_value <= 1.0 and current_value <= 1.0:
        # Hit rate - improvement means higher value
        improvement_threshold_value = baseline_value * (1 + improvement_threshold)
        return current_value > improvement_threshold_value
    else:
        # Latency - improvement means lower value
        improvement_threshold_value = baseline_value * (1 - improvement_threshold)
        return current_value < improvement_threshold_value


class BaselineUpdater:
    """
    Helper class to update baseline file with new measurements.

    Used by CI/CD scripts to auto-update baselines when performance improves.
    """

    def __init__(self, baseline_path: Path = None):
        """
        Initialize baseline updater.

        Args:
            baseline_path: Path to baseline file (defaults to performance_baseline.json)
        """
        if baseline_path is None:
            baseline_path = Path(__file__).parent.parent / "performance_baseline.json"
        self.baseline_path = baseline_path

    def load_baselines(self) -> Dict[str, Any]:
        """Load existing baselines from file."""
        if not self.baseline_path.exists():
            return {
                "generated_at": None,
                "baselines": {}
            }

        with open(self.baseline_path, "r") as f:
            return json.load(f)

    def save_baselines(self, data: Dict[str, Any]) -> None:
        """
        Save baselines to file.

        Args:
            data: Baseline data with 'generated_at' and 'baselines' keys
        """
        from datetime import datetime

        data["generated_at"] = datetime.utcnow().isoformat() + "Z"

        with open(self.baseline_path, "w") as f:
            json.dump(data, f, indent=2)

    def update_metric(self, metric_name: str, value: float) -> None:
        """
        Update single metric in baseline.

        Args:
            metric_name: Name of metric to update
            value: New baseline value
        """
        data = self.load_baselines()
        data["baselines"][metric_name] = value
        self.save_baselines(data)

    def update_metrics(self, metrics: Dict[str, float]) -> None:
        """
        Update multiple metrics in baseline.

        Args:
            metrics: Dictionary of metric names to values
        """
        data = self.load_baselines()
        data["baselines"].update(metrics)
        self.save_baselines(data)
