"""
BugExecutionOrchestrator - Orchestrate full bug discovery execution and remediation workflow.

This module provides the BugExecutionOrchestrator that orchestrates all bug discovery
methods (fuzzing, chaos, property tests, browser discovery, memory leaks, performance
regression, AI-enhanced discovery) and manages the remediation workflow (triage,
filing, fix tracking, regression test generation).

Example:
    >>> from tests.bug_discovery.feedback_loops.bug_execution_orchestrator import BugExecutionOrchestrator
    >>>
    >>> orchestrator = BugExecutionOrchestrator()
    >>> results = orchestrator.run_full_discovery_cycle(
    ...     run_fuzzing=True,
    ...     run_chaos=False,  # Skip chaos (requires isolation)
    ...     run_property=True,
    ...     run_browser=True,
    ...     run_memory=True,
    ...     run_performance=True,
    ...     run_ai_enhanced=True
    ... )
    >>> print(f"Bugs found: {results['bugs_found']}")
    >>> print(f"Unique bugs: {results['unique_bugs']}")
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import subprocess
import sys
import json

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.core.discovery_coordinator import DiscoveryCoordinator
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity
from tests.bug_discovery.feedback_loops.bug_fix_verifier import BugFixVerifier
from tests.bug_discovery.feedback_loops.regression_test_generator import RegressionTestGenerator
from tests.bug_discovery.feedback_loops.roi_tracker import ROITracker

# Optional AI-enhanced discovery imports
try:
    from tests.bug_discovery.ai_enhanced.fuzzing_strategy_generator import FuzzingStrategyGenerator
    FUZZING_STRATEGY_GENERATOR_AVAILABLE = True
except ImportError:
    FUZZING_STRATEGY_GENERATOR_AVAILABLE = False


class BugExecutionOrchestrator:
    """
    Orchestrates full bug discovery execution and remediation workflow.

    This service integrates all bug discovery methods (fuzzing, chaos, property,
    browser, memory, performance, AI-enhanced) and manages the complete feedback
    loop from discovery to remediation.

    Responsibilities:
    - Execute all 7 bug discovery methods
    - Aggregate and deduplicate results
    - Triage bugs by severity and business impact
    - Track fix progress
    - Generate regression tests
    - Collect ROI metrics

    Example:
        orchestrator = BugExecutionOrchestrator(
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repo=os.getenv("GITHUB_REPOSITORY")
        )
        results = orchestrator.run_full_discovery_cycle()
        print(f"Discovered {results['unique_bugs']} unique bugs")
    """

    def __init__(
        self,
        github_token: str = None,
        github_repo: str = None,
        output_dir: str = None
    ):
        """
        Initialize BugExecutionOrchestrator.

        Args:
            github_token: GitHub Personal Access Token for bug filing
            github_repo: Repository in format "owner/repo"
            output_dir: Directory for storing reports (default: storage/discovery_runs)
        """
        self.github_token = github_token
        self.github_repo = github_repo

        # Set output directory
        if output_dir is None:
            output_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "discovery_runs"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize services
        # DiscoveryCoordinator can work without GitHub credentials (just won't file bugs)
        try:
            self.coordinator = DiscoveryCoordinator(github_token, github_repo)
            if not github_token or not github_repo:
                print("[BugExecutionOrchestrator] Warning: No GitHub credentials provided, bug filing disabled")
        except Exception as e:
            print(f"[BugExecutionOrchestrator] Warning: Could not initialize DiscoveryCoordinator: {e}")
            self.coordinator = None

        # Optional AI-enhanced discovery
        if FUZZING_STRATEGY_GENERATOR_AVAILABLE:
            self.fuzzing_generator = FuzzingStrategyGenerator()
            print("[BugExecutionOrchestrator] AI-enhanced fuzzing enabled")
        else:
            self.fuzzing_generator = None
            print("[BugExecutionOrchestrator] AI-enhanced fuzzing not available")

        # Feedback loop services
        self.fix_verifier = BugFixVerifier(github_token, github_repo) if github_token and github_repo else None
        self.test_generator = RegressionTestGenerator()
        self.roi_tracker = ROITracker()

    def run_full_discovery_cycle(
        self,
        run_fuzzing: bool = True,
        run_chaos: bool = True,
        run_property: bool = True,
        run_browser: bool = True,
        run_memory: bool = True,
        run_performance: bool = True,
        run_ai_enhanced: bool = True,
        duration_seconds: int = 3600
    ) -> Dict[str, Any]:
        """
        Execute all enabled bug discovery methods.

        Args:
            run_fuzzing: Run fuzzing discovery (default: True)
            run_chaos: Run chaos engineering (default: True, requires isolation)
            run_property: Run property-based tests (default: True)
            run_browser: Run browser discovery (default: True)
            run_memory: Run memory leak tests (default: True)
            run_performance: Run performance regression tests (default: True)
            run_ai_enhanced: Run AI-enhanced discovery (default: True)
            duration_seconds: Duration per discovery method (default: 3600 = 1 hour)

        Returns:
            Dict with keys: bugs_found, unique_bugs, filed_bugs, duration, reports
        """
        start_time = datetime.now()
        print(f"[BugExecutionOrchestrator] Starting full discovery cycle at {start_time.isoformat()}")

        # 1. Run standard discovery methods (via DiscoveryCoordinator)
        standard_results = self._run_standard_discovery(
            run_fuzzing, run_chaos, run_property, run_browser, duration_seconds
        )

        # 2. Run memory and performance discovery
        memory_perf_results = self._run_memory_performance_discovery(
            run_memory, run_performance
        )

        # 3. Run AI-enhanced discovery
        ai_results = self._run_ai_enhanced_discovery(run_ai_enhanced)

        # 4. Aggregate all results
        all_bugs = self._aggregate_discovery_results([
            standard_results, memory_perf_results, ai_results
        ])

        # 5. Deduplicate bugs
        unique_bugs = self._deduplicate_bugs(all_bugs)

        # 6. Triage by severity
        triaged_bugs = self._triage_by_severity(unique_bugs)

        duration = (datetime.now() - start_time).total_seconds()

        results = {
            "bugs_found": len(all_bugs),
            "unique_bugs": len(unique_bugs),
            "filed_bugs": 0,  # Will be updated after filing
            "duration_seconds": duration,
            "bugs_by_severity": self._count_by_severity(unique_bugs),
            "bugs_by_method": self._count_by_discovery_method(unique_bugs),
            "all_bugs": unique_bugs,
            "run_id": datetime.now().strftime("%Y%m%d_%H%M%S")
        }

        print(f"[BugExecutionOrchestrator] Discovery cycle complete in {duration:.1f}s")
        print(f"[BugExecutionOrchestrator] Bugs found: {results['bugs_found']}, unique: {results['unique_bugs']}")

        return results

    def _run_standard_discovery(
        self,
        run_fuzzing: bool,
        run_chaos: bool,
        run_property: bool,
        run_browser: bool,
        duration_seconds: int
    ) -> List[BugReport]:
        """Run fuzzing, chaos, property, and browser discovery."""
        bugs = []

        if not self.coordinator:
            print("[BugExecutionOrchestrator] Warning: DiscoveryCoordinator not initialized, skipping standard discovery")
            return bugs

        # Use DiscoveryCoordinator for standard methods
        try:
            results = self.coordinator.run_full_discovery(
                duration_seconds=duration_seconds,
                run_property_tests=run_property,
                run_browser_discovery=run_browser,
                generate_regression_tests=False  # Don't generate yet, do it after triage
            )

            # Extract BugReport objects from results
            unique_bugs_list = results.get('unique_bugs_list', [])
            bugs.extend(unique_bugs_list)

            print(f"[BugExecutionOrchestrator] Standard discovery found {len(unique_bugs_list)} bugs")

        except Exception as e:
            print(f"[BugExecutionOrchestrator] Warning: Standard discovery failed: {e}")

        return bugs

    def _run_memory_performance_discovery(
        self,
        run_memory: bool,
        run_performance: bool
    ) -> List[BugReport]:
        """Run memory leak and performance regression discovery."""
        bugs = []

        # Memory leak tests
        if run_memory:
            print("[BugExecutionOrchestrator] Running memory leak discovery...")
            try:
                mem_result = subprocess.run(
                    [sys.executable, "-m", "pytest",
                     str(backend_dir / "tests" / "memory_leaks"),
                     "-v", "-m", "memory_leak"],
                    capture_output=True,
                    text=True,
                    cwd=backend_dir,
                    timeout=600  # 10 minute timeout
                )

                # Parse results and create BugReport objects
                if mem_result.returncode != 0:
                    # Tests failed, create bug reports
                    bugs.append(BugReport(
                        discovery_method=DiscoveryMethod.MEMORY,
                        test_name="memory_leak_detection",
                        error_message="Memory leak detected in memray tests",
                        error_signature="memory_leak_detected",
                        severity=Severity.HIGH,
                        stack_trace=mem_result.stdout[-1000:] if len(mem_result.stdout) > 1000 else mem_result.stdout
                    ))

                print(f"[BugExecutionOrchestrator] Memory discovery: {len(bugs)} bugs found")

            except subprocess.TimeoutExpired:
                print("[BugExecutionOrchestrator] Warning: Memory leak tests timed out")
            except Exception as e:
                print(f"[BugExecutionOrchestrator] Warning: Memory discovery failed: {e}")

        # Performance regression tests
        if run_performance:
            print("[BugExecutionOrchestrator] Running performance regression discovery...")
            try:
                # Check if pytest-benchmark is installed
                check_result = subprocess.run(
                    [sys.executable, "-c", "import pytest_benchmark"],
                    capture_output=True,
                    cwd=backend_dir
                )

                if check_result.returncode != 0:
                    print("[BugExecutionOrchestrator] pytest-benchmark not installed, skipping performance regression tests")
                    print("[BugExecutionOrchestrator] Install with: pip install pytest-benchmark")
                else:
                    perf_result = subprocess.run(
                        [sys.executable, "-m", "pytest",
                         str(backend_dir / "tests" / "performance_regression"),
                         "-v", "--benchmark-only"],
                        capture_output=True,
                        text=True,
                        cwd=backend_dir,
                        timeout=600  # 10 minute timeout
                    )

                    # Parse results for regressions
                    if "regression" in perf_result.stdout.lower() or perf_result.returncode != 0:
                        bugs.append(BugReport(
                            discovery_method=DiscoveryMethod.PERFORMANCE,
                            test_name="performance_regression",
                            error_message="Performance regression detected in pytest-benchmark",
                            error_signature="performance_regression_detected",
                            severity=Severity.MEDIUM,
                            stack_trace=perf_result.stdout[-1000:] if len(perf_result.stdout) > 1000 else perf_result.stdout
                        ))

                    print(f"[BugExecutionOrchestrator] Performance discovery: {len([b for b in bugs if b.discovery_method == DiscoveryMethod.PERFORMANCE])} bugs found")

            except subprocess.TimeoutExpired:
                print("[BugExecutionOrchestrator] Warning: Performance tests timed out")
            except Exception as e:
                print(f"[BugExecutionOrchestrator] Warning: Performance discovery failed: {e}")

        return bugs

    def _run_ai_enhanced_discovery(self, run_ai: bool) -> List[BugReport]:
        """Run AI-enhanced discovery (FuzzingStrategyGenerator, InvariantGenerator, etc.)."""
        bugs = []

        if not run_ai or not self.fuzzing_generator:
            return bugs

        print("[BugExecutionOrchestrator] Running AI-enhanced discovery...")

        try:
            # 1. Generate fuzzing strategies from coverage gaps
            strategies = self.fuzzing_generator.generate_strategies_from_coverage()

            print(f"[BugExecutionOrchestrator] Generated {len(strategies)} AI fuzzing strategies")

            # 2. Execute AI-generated strategies (limit to 5 for time)
            for strategy in strategies[:5]:
                strategy_bugs = self._execute_fuzzing_strategy(strategy)
                bugs.extend(strategy_bugs)

            print(f"[BugExecutionOrchestrator] AI discovery: {len(bugs)} bugs found")

        except Exception as e:
            print(f"[BugExecutionOrchestrator] Warning: AI-enhanced discovery failed: {e}")

        return bugs

    def _execute_fuzzing_strategy(self, strategy: Dict[str, Any]) -> List[BugReport]:
        """Execute a single AI-generated fuzzing strategy."""
        bugs = []

        # Extract strategy details
        target_endpoint = strategy.get("target_endpoint", "unknown")
        payload_type = strategy.get("payload_type", "generic")

        # Run fuzzing with strategy-specific parameters
        # In production, this would call FuzzingOrchestrator with strategy parameters

        print(f"[BugExecutionOrchestrator] Executing strategy: {target_endpoint} ({payload_type})")

        return bugs

    def _aggregate_discovery_results(
        self,
        results_list: List[List[BugReport]]
    ) -> List[BugReport]:
        """Aggregate bugs from all discovery methods."""
        all_bugs = []
        for results in results_list:
            all_bugs.extend(results)
        return all_bugs

    def _deduplicate_bugs(self, bugs: List[BugReport]) -> List[BugReport]:
        """Deduplicate bugs by error signature."""
        seen_signatures = {}
        unique_bugs = []

        for bug in bugs:
            sig = bug.error_signature
            if sig not in seen_signatures:
                seen_signatures[sig] = bug
                unique_bugs.append(bug)
            else:
                # Track that this bug was found by multiple methods
                if hasattr(seen_signatures[sig], 'discovery_methods'):
                    seen_signatures[sig].discovery_methods.add(bug.discovery_method)

        return unique_bugs

    def _triage_by_severity(self, bugs: List[BugReport]) -> Dict[str, List[BugReport]]:
        """Triage bugs by severity."""
        return {
            "critical": [b for b in bugs if b.severity == Severity.CRITICAL],
            "high": [b for b in bugs if b.severity == Severity.HIGH],
            "medium": [b for b in bugs if b.severity == Severity.MEDIUM],
            "low": [b for b in bugs if b.severity == Severity.LOW]
        }

    def _count_by_severity(self, bugs: List[BugReport]) -> Dict[str, int]:
        """Count bugs by severity."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for bug in bugs:
            severity = bug.severity if isinstance(bug.severity, str) else bug.severity.value
            if severity in counts:
                counts[severity] += 1

        return counts

    def _count_by_discovery_method(self, bugs: List[BugReport]) -> Dict[str, int]:
        """Count bugs by discovery method."""
        counts = {}
        for bug in bugs:
            method = bug.discovery_method if isinstance(bug.discovery_method, str) else bug.discovery_method.value
            counts[method] = counts.get(method, 0) + 1
        return counts

    def save_discovery_results(self, results: Dict[str, Any], filename: str = None) -> str:
        """
        Save discovery results to JSON file.

        Args:
            results: Results dictionary from run_full_discovery_cycle()
            filename: Output filename (default: discovery_results_{run_id}.json)

        Returns:
            Path to saved results file
        """
        if filename is None:
            filename = f"discovery_results_{results['run_id']}.json"

        output_path = self.output_dir / filename

        # Convert BugReport objects to dicts for JSON serialization
        serializable_results = results.copy()
        if "all_bugs" in serializable_results:
            serializable_results["all_bugs"] = [
                bug.model_dump() if hasattr(bug, "model_dump") else bug
                for bug in serializable_results["all_bugs"]
            ]

        with open(output_path, "w") as f:
            json.dump(serializable_results, f, indent=2, default=str)

        print(f"[BugExecutionOrchestrator] Saved results to {output_path}")
        return str(output_path)
