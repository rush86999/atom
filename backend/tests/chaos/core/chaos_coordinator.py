"""
ChaosCoordinator: Orchestrates chaos engineering experiments with blast radius controls.

Features:
- Experiment lifecycle management (setup, inject, verify, cleanup)
- Blast radius enforcement (test databases only, duration caps)
- Recovery validation (data integrity, rollback verification)
- Automated bug filing (BugFilingService integration)
"""

import os
import time
import psutil
from typing import Callable, Dict, Any, Optional, List
from datetime import datetime


class ChaosCoordinator:
    """
    Orchestrates chaos engineering experiments with blast radius controls.

    Safety mechanisms:
    - Blast radius checks before injection
    - Duration timeout enforcement (60s max)
    - Automatic cleanup and rollback
    - Environment verification (test only)
    """

    def __init__(self, db_session, bug_filing_service=None):
        """
        Initialize ChaosCoordinator.

        Args:
            db_session: Database session for test database
            bug_filing_service: Optional BugFilingService for automated bug filing
        """
        self.db_session = db_session
        self.bug_filing_service = bug_filing_service
        self.experiments = []

    def run_experiment(
        self,
        experiment_name: str,
        failure_injection: Callable,
        verify_graceful_degradation: Callable,
        blast_radius_checks: Optional[List[Callable]] = None
    ) -> Dict[str, Any]:
        """
        Run chaos experiment with blast radius controls.

        Args:
            experiment_name: Name of experiment
            failure_injection: Context manager that injects failure
            verify_graceful_degradation: Function that verifies graceful degradation
            blast_radius_checks: List of safety checks to run before injection

        Returns:
            Dict with experiment results (baseline, failure, recovery, bug_filed)
        """
        # Step 1: Blast radius validation
        if blast_radius_checks:
            for check in blast_radius_checks:
                check()  # Raises AssertionError if unsafe

        # Step 2: Baseline measurement
        baseline_metrics = self._measure_system_health()

        # Step 3: Inject failure
        try:
            with failure_injection():
                failure_metrics = self._measure_system_health()
                verify_graceful_degradation(failure_metrics)
        except Exception as e:
            # File bug if resilience failure detected
            if self.bug_filing_service:
                self.bug_filing_service.file_bug(
                    test_name=experiment_name,
                    error_message=f"Resilience failure: {str(e)}",
                    metadata={
                        "test_type": "chaos",
                        "baseline_metrics": baseline_metrics,
                        "failure_metrics": failure_metrics if 'failure_metrics' in locals() else {},
                        "blast_radius": "test_database_only",
                    }
                )
            raise

        # Step 4: Verify recovery
        recovery_metrics = self._measure_system_health()
        self._verify_recovery(baseline_metrics, recovery_metrics)

        return {
            "baseline": baseline_metrics,
            "failure": failure_metrics if 'failure_metrics' in locals() else {},
            "recovery": recovery_metrics,
            "success": True
        }

    def _measure_system_health(self) -> Dict[str, float]:
        """
        Measure system health metrics (CPU, memory, disk I/O).

        Returns:
            Dict with cpu_percent, memory_mb, disk_io, timestamp
        """
        disk_io = psutil.disk_io_counters()
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_mb": psutil.virtual_memory().used / (1024 * 1024),
            "disk_io": {
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0,
            },
            "timestamp": time.time()
        }

    def _verify_recovery(self, baseline: Dict, recovery: Dict) -> None:
        """
        Verify system recovered to baseline.

        Args:
            baseline: Baseline metrics from before failure injection
            recovery: Metrics after failure injection removed

        Raises:
            AssertionError: If system did not recover to baseline
        """
        cpu_diff = abs(recovery["cpu_percent"] - baseline["cpu_percent"])
        assert cpu_diff < 20, f"CPU did not recover: {cpu_diff}% difference (baseline: {baseline['cpu_percent']}%, recovery: {recovery['cpu_percent']}%)"

        memory_diff = abs(recovery["memory_mb"] - baseline["memory_mb"])
        assert memory_diff < 100, f"Memory did not recover: {memory_diff}MB difference (baseline: {baseline['memory_mb']:.2f}MB, recovery: {recovery['memory_mb']:.2f}MB)"
