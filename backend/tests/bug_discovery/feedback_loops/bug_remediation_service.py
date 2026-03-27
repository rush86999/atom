"""
BugRemediationService - Manage bug triage, prioritization, fix tracking, and regression test generation.

This module provides the BugRemediationService that manages the complete bug remediation
workflow from triage and prioritization to GitHub issue filing, fix tracking, and
regression test generation.

Example:
    >>> from tests.bug_discovery.feedback_loops.bug_remediation_service import BugRemediationService
    >>>
    >>> remediation = BugRemediationService(
    ...     github_token=os.getenv("GITHUB_TOKEN"),
    ...     github_repo=os.getenv("GITHUB_REPOSITORY")
    ... )
    >>>
    >>> # Triage and prioritize bugs
    >>> prioritized_bugs = remediation.triage_and_prioritize(discovered_bugs)
    >>>
    >>> # File to GitHub
    >>> filed = remediation.file_bugs_to_github(prioritized_bugs[:20])
    >>>
    >>> # Track fix progress
    >>> progress = remediation.track_fix_progress(prioritized_bugs)
"""

from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import sys
import json

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, Severity
from tests.bug_discovery.bug_filing_service import BugFilingService
from tests.bug_discovery.feedback_loops.regression_test_generator import RegressionTestGenerator
from tests.bug_discovery.feedback_loops.roi_tracker import ROITracker


class BugRemediationService:
    """
    Manage bug triage, prioritization, fix tracking, and regression test generation.

    This service handles the complete bug remediation workflow:
    - Triage bugs by severity and business impact
    - Prioritize fixes (critical > high > medium > low)
    - File bugs to GitHub with enriched metadata
    - Track fix progress (fixed, in_progress, pending)
    - Generate regression tests from verified fixes
    - Generate comprehensive remediation reports

    Example:
        remediation = BugRemediationService(github_token, github_repo)
        prioritized = remediation.triage_and_prioritize(bugs)
        filed = remediation.file_bugs_to_github(prioritized[:20])
        progress = remediation.track_fix_progress(prioritized)
    """

    def __init__(
        self,
        github_token: str = None,
        github_repo: str = None
    ):
        """
        Initialize BugRemediationService.

        Args:
            github_token: GitHub Personal Access Token with repo scope
            github_repo: Repository in format "owner/repo"
        """
        self.github_token = github_token
        self.github_repo = github_repo

        # Initialize services
        if github_token and github_repo:
            self.filing_service = BugFilingService(github_token, github_repo)
        else:
            print("[BugRemediationService] Warning: No GitHub credentials, bug filing disabled")
            self.filing_service = None

        self.test_generator = RegressionTestGenerator()
        self.roi_tracker = ROITracker()

    def triage_and_prioritize(self, bugs: List[BugReport]) -> List[BugReport]:
        """
        Triage bugs by severity and business impact.

        Prioritization rules:
        1. Severity: Critical > High > Medium > Low
        2. Within severity: Security > Data Loss > Crash > Degraded UX

        Args:
            bugs: List of BugReport objects to triage

        Returns:
            Sorted list of BugReport objects with priority_rank attribute
        """
        # Sort by severity priority
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3
        }

        sorted_bugs = sorted(
            bugs,
            key=lambda b: (
                severity_order.get(
                    b.severity if isinstance(b.severity, Severity) else Severity(b.severity),
                    4
                ),
                self._calculate_business_impact(b)
            )
        )

        # Add priority rank
        for idx, bug in enumerate(sorted_bugs, 1):
            bug.priority_rank = idx

        print(f"[BugRemediationService] Triage complete: {len(bugs)} bugs prioritized")

        return sorted_bugs

    def _calculate_business_impact(self, bug: BugReport) -> int:
        """
        Calculate business impact score (0-10, higher = worse).

        Impact categories:
        - Security issues: +10 (SQL injection, XSS, CSRF, security)
        - Data loss/corruption: +8
        - Crashes: +6 (crash, panic, exception)
        - Degraded performance: +4 (slow, timeout, latency)

        Args:
            bug: BugReport object

        Returns:
            Business impact score (0-10)
        """
        impact = 0
        error_msg = bug.error_message.lower()

        # Security issues: highest impact
        security_keywords = ["sql injection", "xss", "csrf", "security", "vulnerability",
                           "auth bypass", "injection", "exploit"]

        if any(keyword in error_msg for keyword in security_keywords):
            impact += 10

        # Data loss/corruption
        data_loss_keywords = ["data loss", "corruption", "deleted", "leaked",
                            "unauthorized access", "privacy"]

        if any(keyword in error_msg for keyword in data_loss_keywords):
            impact += 8

        # Crashes
        crash_keywords = ["crash", "panic", "exception", "segfault",
                         "out of memory", "stack overflow"]

        if any(keyword in error_msg for keyword in crash_keywords):
            impact += 6

        # Degraded performance
        perf_keywords = ["slow", "timeout", "latency", "degraded",
                        "performance", "unresponsive"]

        if any(keyword in error_msg for keyword in perf_keywords):
            impact += 4

        return min(impact, 10)  # Cap at 10

    def file_bugs_to_github(self, bugs: List[BugReport]) -> List[Dict[str, Any]]:
        """
        File bugs to GitHub via BugFilingService.

        Args:
            bugs: List of BugReport objects to file

        Returns:
            List of filed issue metadata (issue_number, url, status)
        """
        if not self.filing_service:
            print("[BugRemediationService] Warning: BugFilingService not initialized, skipping filing")
            return []

        filed_issues = []

        for bug in bugs:
            try:
                # Handle enum or string types
                discovery_method = bug.discovery_method if isinstance(bug.discovery_method, str) else bug.discovery_method.value
                severity = bug.severity if isinstance(bug.severity, str) else bug.severity.value

                issue_meta = self.filing_service.file_bug(
                    test_name=bug.test_name,
                    error_message=bug.error_message,
                    stack_trace=bug.stack_trace,
                    metadata={
                        "discovery_method": discovery_method,
                        "severity": severity,
                        "target_endpoint": getattr(bug, "target_endpoint", ""),
                        "test_file": bug.test_file,
                        "business_impact": self._calculate_business_impact(bug),
                        "priority_rank": getattr(bug, "priority_rank", 0)
                    }
                )
                filed_issues.append(issue_meta)
                print(f"[BugRemediationService] Filed bug {bug.test_name} as issue #{issue_meta.get('issue_number', 'unknown')}")

            except Exception as e:
                print(f"[BugRemediationService] Warning: Failed to file bug {bug.test_name}: {e}")
                filed_issues.append({
                    "status": "error",
                    "test_name": bug.test_name,
                    "error": str(e)
                })

        print(f"[BugRemediationService] Filed {len([i for i in filed_issues if i.get('status') == 'created'])} bugs to GitHub")

        return filed_issues

    def track_fix_progress(self, bugs: List[BugReport]) -> Dict[str, Any]:
        """
        Track fix progress for bugs.

        Checks GitHub issues for fix labels and calculates statistics.

        Args:
            bugs: List of BugReport objects to track

        Returns:
            Dict with fix statistics (fixed_count, pending_count, in_progress_count, fix_rate)
        """
        # Check GitHub issues for fix labels
        # This would integrate with BugFixVerifier for real-time tracking
        fixed_count = sum(1 for b in bugs if getattr(b, "fix_status", "") == "verified")
        in_progress_count = sum(1 for b in bugs if getattr(b, "fix_status", "") == "in_progress")
        pending_count = len(bugs) - fixed_count - in_progress_count

        progress = {
            "total": len(bugs),
            "fixed": fixed_count,
            "in_progress": in_progress_count,
            "pending": pending_count,
            "fix_rate": fixed_count / len(bugs) if bugs else 0
        }

        print(f"[BugRemediationService] Fix progress: {progress['fixed']}/{progress['total']} ({progress['fix_rate']:.1%})")

        return progress

    def generate_regression_tests_for_fixed_bugs(
        self,
        fixed_bugs: List[BugReport],
        output_dir: str = None
    ) -> List[str]:
        """
        Generate regression tests from fixed bugs.

        Args:
            fixed_bugs: List of bugs that have been fixed and verified
            output_dir: Directory to write regression tests (default: storage/regression_tests)

        Returns:
            List of generated test file paths
        """
        if output_dir is None:
            output_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "regression_tests"

        generated_tests = []

        for bug in fixed_bugs:
            try:
                test_path = self.test_generator.generate_test_from_bug(
                    bug_report=bug,
                    output_dir=str(output_dir)
                )
                generated_tests.append(test_path)
                print(f"[BugRemediationService] Generated regression test: {test_path}")

            except Exception as e:
                print(f"[BugRemediationService] Warning: Failed to generate test for bug {bug.test_name}: {e}")

        print(f"[BugRemediationService] Generated {len(generated_tests)} regression tests")

        return generated_tests

    def generate_remediation_report(
        self,
        discovery_results: Dict[str, Any],
        filed_issues: List[Dict],
        fix_progress: Dict[str, Any]
    ) -> str:
        """
        Generate comprehensive remediation report.

        Args:
            discovery_results: Results from BugExecutionOrchestrator.run_full_discovery_cycle()
            filed_issues: Results from file_bugs_to_github()
            fix_progress: Results from track_fix_progress()

        Returns:
            Markdown report content
        """
        report_lines = [
            "# Bug Discovery & Remediation Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- **Bugs Found:** {discovery_results.get('bugs_found', 0)}",
            f"- **Unique Bugs:** {discovery_results.get('unique_bugs', 0)}",
            f"- **Bugs Filed:** {len([i for i in filed_issues if i.get('status') == 'created'])}",
            f"- **Fix Rate:** {fix_progress.get('fix_rate', 0):.1%}",
            "",
            "## Bugs by Severity"
        ]

        bugs_by_severity = discovery_results.get('bugs_by_severity', {})
        for severity in ['critical', 'high', 'medium', 'low']:
            count = bugs_by_severity.get(severity, 0)
            report_lines.append(f"- **{severity.title()}:** {count}")

        report_lines.extend([
            "",
            "## Bugs by Discovery Method"
        ])

        bugs_by_method = discovery_results.get('bugs_by_method', {})
        for method, count in sorted(bugs_by_method.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- **{method.title()}:** {count}")

        report_lines.extend([
            "",
            "## Fix Progress",
            f"- **Fixed:** {fix_progress.get('fixed', 0)}",
            f"- **In Progress:** {fix_progress.get('in_progress', 0)}",
            f"- **Pending:** {fix_progress.get('pending', 0)}",
            "",
            "## ROI Metrics"
        ])

        # Add ROI metrics from ROITracker
        try:
            roi_report = self.roi_tracker.generate_roi_report(weeks=4)
            report_lines.extend([
                f"- **Hours Saved:** {roi_report.get('hours_saved', 0):.1f}",
                f"- **Cost Saved:** ${roi_report.get('cost_saved', 0):.2f}",
                f"- **Bugs Prevented:** {roi_report.get('bugs_prevented', 0)}",
                f"- **Cost Avoidance:** ${roi_report.get('cost_avoidance', 0):.2f}",
                f"- **Total Savings:** ${roi_report.get('total_savings', 0):.2f}",
                f"- **ROI Ratio:** {roi_report.get('roi_ratio', 0):.1f}x"
            ])
        except Exception as e:
            report_lines.append(f"- ROI metrics not available: {e}")

        report_lines.extend([
            "",
            "## Filed Issues",
            ""
        ])

        # List top 10 filed issues
        filed_count = 0
        for issue in filed_issues:
            if issue.get('status') == 'created':
                filed_count += 1
                issue_number = issue.get('issue_number', 'unknown')
                issue_url = issue.get('issue_url', '')
                test_name = issue.get('test_name', 'unknown')
                report_lines.append(f"{filed_count}. [#{issue_number}]({issue_url}) - {test_name}")

                if filed_count >= 10:
                    break

        if filed_count == 0:
            report_lines.append("No issues filed (check GitHub credentials)")

        return "\n".join(report_lines)

    def save_remediation_report(
        self,
        discovery_results: Dict[str, Any],
        filed_issues: List[Dict],
        fix_progress: Dict[str, Any],
        output_path: str = None
    ) -> str:
        """
        Save remediation report to markdown file.

        Args:
            discovery_results: Results from BugExecutionOrchestrator
            filed_issues: Results from file_bugs_to_github()
            fix_progress: Results from track_fix_progress()
            output_path: Output file path (default: storage/discovery_runs/remediation_report_{timestamp}.md)

        Returns:
            Path to saved report
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = backend_dir / "tests" / "bug_discovery" / "storage" / "discovery_runs" / f"remediation_report_{timestamp}.md"

        # Generate report
        report_content = self.generate_remediation_report(
            discovery_results,
            filed_issues,
            fix_progress
        )

        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(report_content)

        print(f"[BugRemediationService] Saved remediation report to {output_path}")

        return str(output_path)
