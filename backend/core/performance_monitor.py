"""
Performance Monitor - Benchmark tracking and regression detection.

Provides:
- Context manager for timing operations
- Benchmark result storage
- Regression detection against historical baselines
- Performance report generation

Reference: Phase 60 Plan 06 - Performance Benchmarking
"""

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Performance targets from Phase 60 requirements
PERFORMANCE_TARGETS = {
    "package_installation_seconds": 5.0,
    "skill_loading_seconds": 1.0,
    "marketplace_search_ms": 100,
    "hot_reload_seconds": 1.0,
    "workflow_validation_ms": 50,
    "dependency_resolution_ms": 500
}

# Baseline file for historical comparison
BASELINE_FILE = Path(__file__).parent.parent / "tests" / "performance_baselines.json"


@contextmanager
def measure_performance(operation_name: str):
    """
    Context manager for measuring operation performance.

    Example:
        with measure_performance("package_install") as timer:
            installer.install_packages(...)
        print(f"Duration: {timer.duration}s")
    """
    start_time = time.perf_counter()
    timer = PerformanceTimer(operation_name, start_time)

    try:
        yield timer
    finally:
        timer.duration = time.perf_counter() - start_time
        logger.info(f"{operation_name} completed in {timer.duration:.3f}s")


class PerformanceTimer:
    """Timer object for performance measurement."""

    def __init__(self, operation_name: str, start_time: float):
        self.operation_name = operation_name
        self.start_time = start_time
        self.duration: Optional[float] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.duration is None:
            self.duration = time.perf_counter() - self.start_time

    def meets_target(self, target_key: str) -> bool:
        """Check if duration meets performance target."""
        target = PERFORMANCE_TARGETS.get(target_key)
        if target is None:
            return True
        return self.duration <= target

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "operation": self.operation_name,
            "duration_seconds": self.duration,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class PerformanceMonitor:
    """
    Track and analyze performance metrics.

    Stores benchmark results and detects regressions.
    """

    def __init__(self):
        """Initialize performance monitor."""
        self.measurements: List[Dict[str, Any]] = []
        self.baselines = self._load_baselines()

    def record_measurement(self, operation: str, duration: float, metadata: Dict[str, Any] = None):
        """
        Record a performance measurement.

        Args:
            operation: Operation name
            duration: Duration in seconds
            metadata: Additional context (package count, file size, etc.)
        """
        measurement = {
            "operation": operation,
            "duration_seconds": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        self.measurements.append(measurement)
        logger.debug(f"Recorded {operation}: {duration:.3f}s")

    def check_regression(self, operation: str, current_duration: float) -> Dict[str, Any]:
        """
        Check for performance regression against baseline.

        Regression defined as: current > baseline * 1.5 (50% slower)
        """
        baseline = self.baselines.get(operation)
        if not baseline:
            return {"regression": False, "reason": "No baseline available"}

        threshold = baseline * 1.5
        is_regression = current_duration > threshold

        return {
            "regression": is_regression,
            "baseline": baseline,
            "current": current_duration,
            "threshold": threshold,
            "percent_change": ((current_duration - baseline) / baseline) * 100
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all measurements."""
        if not self.measurements:
            return {"total": 0, "operations": {}}

        summary = {"total": len(self.measurements), "operations": {}}

        for measurement in self.measurements:
            op = measurement["operation"]
            if op not in summary["operations"]:
                summary["operations"][op] = {
                    "count": 0,
                    "total_duration": 0,
                    "min": float('inf'),
                    "max": 0
                }

            op_summary = summary["operations"][op]
            op_summary["count"] += 1
            op_summary["total_duration"] += measurement["duration_seconds"]
            op_summary["min"] = min(op_summary["min"], measurement["duration_seconds"])
            op_summary["max"] = max(op_summary["max"], measurement["duration_seconds"])

        # Calculate averages
        for op_summary in summary["operations"].values():
            op_summary["avg"] = op_summary["total_duration"] / op_summary["count"]

        return summary

    def save_baselines(self):
        """Save current measurements as new baselines."""
        baselines = {}

        for measurement in self.measurements:
            op = measurement["operation"]
            if op not in baselines:
                baselines[op] = measurement["duration_seconds"]
            else:
                # Use average
                baselines[op] = (baselines[op] + measurement["duration_seconds"]) / 2

        with open(BASELINE_FILE, 'w') as f:
            json.dump({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "baselines": baselines
            }, f, indent=2)

        logger.info(f"Saved baselines to {BASELINE_FILE}")

    def _load_baselines(self) -> Dict[str, float]:
        """Load historical baselines from file."""
        if not BASELINE_FILE.exists():
            return {}

        try:
            with open(BASELINE_FILE, 'r') as f:
                data = json.load(f)
                return data.get("baselines", {})
        except Exception as e:
            logger.warning(f"Failed to load baselines: {e}")
            return {}


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor
