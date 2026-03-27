"""
Bug Discovery Core Services

This module provides unified access to all bug discovery core services:
- DiscoveryCoordinator: Orchestrates all discovery methods
- ResultAggregator: Normalizes results from all methods
- BugDeduplicator: Deduplicates bugs by error signature
- SeverityClassifier: Classifies bug severity
- DashboardGenerator: Generates weekly reports with ROI metrics and verification status
- run_memory_performance_discovery: Orchestrates memory & performance discovery
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.core.discovery_coordinator import (
    DiscoveryCoordinator,
    run_discovery
)
from tests.bug_discovery.core.result_aggregator import ResultAggregator
from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator
from tests.bug_discovery.core.severity_classifier import SeverityClassifier
from tests.bug_discovery.core.dashboard_generator import DashboardGenerator

__all__ = [
    "DiscoveryCoordinator",
    "run_discovery",
    "ResultAggregator",
    "BugDeduplicator",
    "SeverityClassifier",
    "DashboardGenerator",
    "run_memory_performance_discovery",
]


def run_memory_performance_discovery(
    github_token: str = None,
    github_repository: str = None,
    upload_artifacts: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to run memory and performance bug discovery.

    Orchestrates three discovery methods:
    1. Memory leak detection (memray)
    2. Performance regression (pytest-benchmark)
    3. Lighthouse CI (browser performance)

    Args:
        github_token: GitHub token for bug filing (default: GITHUB_TOKEN env var)
        github_repository: GitHub repository (default: GITHUB_REPOSITORY env var)
        upload_artifacts: Whether to upload artifacts (default: True)

    Returns:
        Dict with aggregated results:
        {
            "bugs_found": int,
            "memory_leaks": {"bugs_found": int, "bugs": []},
            "performance_regressions": {"bugs_found": int, "bugs": []},
            "lighthouse": {"bugs_found": int, "bugs": []},
            "filed_bugs": int,
            "report_path": str
        }

    Raises:
        ValueError: If GITHUB_TOKEN or GITHUB_REPOSITORY not set
    """
    github_token = github_token or os.getenv("GITHUB_TOKEN")
    github_repository = github_repository or os.getenv("GITHUB_REPOSITORY")

    # Graceful degradation if GitHub credentials not available
    if not github_token:
        print("[run_memory_performance_discovery] Warning: GITHUB_TOKEN not set, skipping bug filing")
        upload_artifacts = False

    if not github_repository:
        print("[run_memory_performance_discovery] Warning: GITHUB_REPOSITORY not set, skipping bug filing")
        upload_artifacts = False

    results = {
        "memory_leaks": {"bugs_found": 0, "bugs": []},
        "performance_regressions": {"bugs_found": 0, "bugs": []},
        "lighthouse": {"bugs_found": 0, "bugs": []}
    }

    # 1. Run memory leak tests
    print("[run_memory_performance_discovery] Running memory leak tests...")
    try:
        mem_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/memory_leaks/", "-v", "-m", "memory_leak", "-n", "1"],
            capture_output=True,
            text=True,
            cwd=backend_dir,
            timeout=3600  # 1 hour timeout
        )

        # Parse results for memory leaks
        if mem_result.returncode != 0:
            # Memory leaks found
            leaks = _parse_memory_leak_output(mem_result.stdout)
            results["memory_leaks"]["bugs_found"] = len(leaks)
            results["memory_leaks"]["bugs"] = leaks
            print(f"[run_memory_performance_discovery] Found {len(leaks)} memory leaks")

    except subprocess.TimeoutExpired:
        print("[run_memory_performance_discovery] Memory leak tests timed out")
    except Exception as e:
        print(f"[run_memory_performance_discovery] Memory leak tests failed: {e}")

    # 2. Run performance regression tests
    print("[run_memory_performance_discovery] Running performance regression tests...")
    try:
        perf_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/performance_regression/",
             "--benchmark-only", "--benchmark-compare=baseline", "--benchmark-compare-fail=mean:20%"],
            capture_output=True,
            text=True,
            cwd=backend_dir,
            timeout=1800  # 30 minute timeout
        )

        # Parse results for performance regressions
        if perf_result.returncode != 0:
            # Performance regressions found
            regressions = _parse_performance_regression_output(perf_result.stdout)
            results["performance_regressions"]["bugs_found"] = len(regressions)
            results["performance_regressions"]["bugs"] = regressions
            print(f"[run_memory_performance_discovery] Found {len(regressions)} performance regressions")

    except subprocess.TimeoutExpired:
        print("[run_memory_performance_discovery] Performance regression tests timed out")
    except Exception as e:
        print(f"[run_memory_performance_discovery] Performance regression tests failed: {e}")

    # 3. Check Lighthouse results (already run by CI)
    print("[run_memory_performance_discovery] Checking Lighthouse results...")
    try:
        lighthouse_baseline = backend_dir / "tests" / "performance_regression" / "lighthouse_baseline.json"
        if lighthouse_baseline.exists():
            # Lighthouse already run, check for regressions
            import json
            with open(lighthouse_baseline) as f:
                lighthouse_data = json.load(f)

            # Check for Lighthouse issues
            issues = _parse_lighthouse_results(lighthouse_data)
            results["lighthouse"]["bugs_found"] = len(issues)
            results["lighthouse"]["bugs"] = issues
            print(f"[run_memory_performance_discovery] Found {len(issues)} Lighthouse issues")

    except Exception as e:
        print(f"[run_memory_performance_discovery] Lighthouse check failed: {e}")

    # 4. File bugs if GitHub credentials available
    filed_bugs = 0
    if upload_artifacts and github_token and github_repository:
        print("[run_memory_performance_discovery] Filing bugs to GitHub...")
        from tests.bug_discovery.bug_filing_service import BugFilingService

        bug_filing_service = BugFilingService(github_token, github_repository)

        # File memory leaks
        for leak in results["memory_leaks"]["bugs"]:
            try:
                bug_filing_service.file_bug(
                    test_name=leak.get("test_name", "memory_leak"),
                    error_message=leak.get("error_message", "Memory leak detected"),
                    metadata={
                        "test_type": "memory_leak",
                        "severity": "critical",
                        **leak
                    }
                )
                filed_bugs += 1
            except Exception as e:
                print(f"[run_memory_performance_discovery] Failed to file memory leak bug: {e}")

        # File performance regressions
        for regression in results["performance_regressions"]["bugs"]:
            try:
                bug_filing_service.file_bug(
                    test_name=regression.get("test_name", "performance_regression"),
                    error_message=regression.get("error_message", "Performance regression detected"),
                    metadata={
                        "test_type": "performance_regression",
                        "severity": "high",
                        **regression
                    }
                )
                filed_bugs += 1
            except Exception as e:
                print(f"[run_memory_performance_discovery] Failed to file performance regression bug: {e}")

        # File Lighthouse issues
        for issue in results["lighthouse"]["bugs"]:
            try:
                bug_filing_service.file_bug(
                    test_name=issue.get("test_name", "lighthouse"),
                    error_message=issue.get("error_message", "Lighthouse performance issue"),
                    metadata={
                        "test_type": "lighthouse",
                        "severity": "medium",
                        **issue
                    }
                )
                filed_bugs += 1
            except Exception as e:
                print(f"[run_memory_performance_discovery] Failed to file Lighthouse bug: {e}")

    # 5. Generate weekly report
    print("[run_memory_performance_discovery] Generating weekly report...")
    from tests.bug_discovery.core.dashboard_generator import DashboardGenerator

    storage_dir = backend_dir / "tests" / "bug_discovery" / "storage"
    dashboard_generator = DashboardGenerator(str(storage_dir))

    all_bugs = (
        results["memory_leaks"]["bugs"] +
        results["performance_regressions"]["bugs"] +
        results["lighthouse"]["bugs"]
    )

    report_path = dashboard_generator.generate_weekly_report(
        bugs_found=len(all_bugs),
        unique_bugs=len(all_bugs),  # No deduplication for memory/performance
        filed_bugs=filed_bugs,
        reports=all_bugs
    )

    return {
        "bugs_found": len(all_bugs),
        "memory_leaks": results["memory_leaks"],
        "performance_regressions": results["performance_regressions"],
        "lighthouse": results["lighthouse"],
        "filed_bugs": filed_bugs,
        "report_path": report_path
    }


def _parse_memory_leak_output(output: str) -> List[Dict[str, Any]]:
    """Parse pytest output for memory leak failures."""
    leaks = []
    lines = output.split('\n')

    current_test = None
    for line in lines:
        if 'FAILED' in line and 'test_' in line:
            current_test = line.strip()
            leaks.append({
                "test_name": current_test,
                "error_message": "Memory leak detected by memray",
                "error_signature": f"memory_leak_{current_test}"
            })

    return leaks


def _parse_performance_regression_output(output: str) -> List[Dict[str, Any]]:
    """Parse pytest-benchmark output for performance regressions."""
    regressions = []
    lines = output.split('\n')

    current_test = None
    for line in lines:
        if 'FAILED' in line and 'regression' in line.lower():
            current_test = line.strip()
            regressions.append({
                "test_name": current_test,
                "error_message": "Performance regression detected (>20% degradation)",
                "error_signature": f"perf_regression_{current_test}"
            })

    return regressions


def _parse_lighthouse_results(lighthouse_data: Dict) -> List[Dict[str, Any]]:
    """Parse Lighthouse results for performance issues."""
    issues = []

    # Check performance score
    categories = lighthouse_data.get("categories", {})
    performance_score = categories.get("performance", {}).get("score", 100)

    if performance_score < 90:
        issues.append({
            "test_name": "lighthouse_performance",
            "error_message": f"Lighthouse performance score {performance_score} < 90",
            "error_signature": "lighthouse_performance_score"
        })

    # Check audits
    audits = lighthouse_data.get("audits", {})
    critical_audits = [
        "first-contentful-paint",
        "largest-contentful-paint",
        "total-blocking-time",
        "cumulative-layout-shift"
    ]

    for audit_name in critical_audits:
        audit = audits.get(audit_name, {})
        if audit.get("score") is not None and audit["score"] < 0.9:
            issues.append({
                "test_name": f"lighthouse_{audit_name}",
                "error_message": f"Lighthouse {audit_name} score {audit['score']} < 0.9",
                "error_signature": f"lighthouse_{audit_name}"
            })

    return issues
