"""
DashboardGenerator service for weekly bug discovery reports.

This module provides the DashboardGenerator that produces HTML and JSON
reports with bug trends (found, fixed, regression rate) for weekly
discovery runs.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter

# Add backend to path for imports
import sys
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, Severity


class DashboardGenerator:
    """
    Generate weekly bug discovery dashboard reports.

    Produces HTML and JSON reports with:
    - Bugs found (by discovery method, severity)
    - Bugs fixed (from historical data)
    - Regression rate (bugs reintroduced after fix)
    - Trend analysis (week-over-week comparison)
    """

    def __init__(self, storage_dir: str = None):
        """
        Initialize DashboardGenerator.

        Args:
            storage_dir: Directory for storing reports and database
        """
        if storage_dir is None:
            backend_dir = Path(__file__).parent.parent.parent.parent
            storage_dir = backend_dir / "tests" / "bug_discovery" / "storage"

        self.storage_dir = Path(storage_dir)
        self.reports_dir = self.storage_dir / "reports"
        self.db_path = self.storage_dir / "bug_reports.db"

        # Create directories
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_weekly_report(
        self,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        reports: List[BugReport]
    ) -> str:
        """
        Generate weekly HTML report.

        Args:
            bugs_found: Total bugs found (including duplicates)
            unique_bugs: Unique bugs after deduplication
            filed_bugs: Bugs filed to GitHub
            reports: List of BugReport objects

        Returns:
            Path to generated HTML report
        """
        # Calculate statistics
        by_method = self._group_by_method(reports)
        by_severity = self._group_by_severity(reports)

        # Calculate regression rate
        regression_rate = self._calculate_regression_rate(reports)

        # Get top bugs by severity
        top_bugs = sorted(reports, key=lambda b: b.get_severity_score(), reverse=True)[:10]

        # Render HTML template
        html_content = self._render_html_template(
            week_date=datetime.utcnow().strftime("%Y-%m-%d"),
            bugs_found=bugs_found,
            unique_bugs=unique_bugs,
            filed_bugs=filed_bugs,
            regression_rate=regression_rate,
            by_method=by_method,
            by_severity=by_severity,
            top_bugs=top_bugs
        )

        # Save report
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        report_path = self.reports_dir / f"weekly-{timestamp}.html"
        with open(report_path, "w") as f:
            f.write(html_content)

        # Save JSON report
        json_path = self.reports_dir / f"weekly-{timestamp}.json"
        self._save_json_report(json_path, {
            "week_date": timestamp,
            "bugs_found": bugs_found,
            "unique_bugs": unique_bugs,
            "filed_bugs": filed_bugs,
            "regression_rate": regression_rate,
            "by_method": by_method,
            "by_severity": by_severity,
            "bugs": [r.dict() for r in reports]
        })

        return str(report_path)

    def _group_by_method(self, reports: List[BugReport]) -> Dict[str, int]:
        """Group bugs by discovery method."""
        method_counts = Counter()
        for report in reports:
            # Handle both enum and string types (use_enum_values=True in BugReport)
            method = report.discovery_method if isinstance(report.discovery_method, str) else report.discovery_method.value
            method_counts[method] += 1
        return dict(method_counts)

    def _group_by_severity(self, reports: List[BugReport]) -> Dict[str, int]:
        """Group bugs by severity."""
        severity_counts = Counter()
        for report in reports:
            # Handle both enum and string types (use_enum_values=True in BugReport)
            severity = report.severity if isinstance(report.severity, str) else report.severity.value
            severity_counts[severity] += 1
        return dict(severity_counts)

    def generate_weekly_report_with_roi(
        self,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        reports: List[BugReport],
        roi_data: Dict[str, Any],
        verification_status: Dict[str, Any] = None
    ) -> str:
        """
        Generate weekly HTML report with ROI metrics and verification status.

        Args:
            bugs_found: Total bugs found (including duplicates)
            unique_bugs: Unique bugs after deduplication
            filed_bugs: Bugs filed to GitHub
            reports: List of BugReport objects
            roi_data: ROI data from ROITracker.generate_roi_report()
            verification_status: Optional verification status from BugFixVerifier

        Returns:
            Path to generated HTML report
        """
        # Calculate statistics
        by_method = self._group_by_method(reports)
        by_severity = self._group_by_severity(reports)

        # Calculate regression rate (enhanced version)
        regression_rate = self._calculate_regression_rate_with_db(reports)

        # Get top bugs by severity
        top_bugs = sorted(reports, key=lambda b: b.get_severity_score(), reverse=True)[:10]

        # Calculate effectiveness metrics
        effectiveness = self._calculate_effectiveness_metrics(
            bugs_found=bugs_found,
            duration_seconds=roi_data.get("automation_hours", 0) * 3600,
            unique_bugs=unique_bugs
        )

        # Render HTML template with ROI section
        html_content = self._render_html_template_with_roi(
            week_date=datetime.utcnow().strftime("%Y-%m-%d"),
            bugs_found=bugs_found,
            unique_bugs=unique_bugs,
            filed_bugs=filed_bugs,
            regression_rate=regression_rate,
            by_method=by_method,
            by_severity=by_severity,
            top_bugs=top_bugs,
            roi_data=roi_data,
            verification_status=verification_status,
            effectiveness=effectiveness
        )

        # Save report
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        report_path = self.reports_dir / f"weekly-{timestamp}.html"
        with open(report_path, "w") as f:
            f.write(html_content)

        # Save JSON report with ROI data
        json_path = self.reports_dir / f"weekly-{timestamp}.json"
        self._save_json_report(json_path, {
            "week_date": timestamp,
            "bugs_found": bugs_found,
            "unique_bugs": unique_bugs,
            "filed_bugs": filed_bugs,
            "regression_rate": regression_rate,
            "by_method": by_method,
            "by_severity": by_severity,
            "bugs": [r.dict() for r in reports],
            "roi": roi_data,
            "verification": verification_status,
            "effectiveness": effectiveness
        })

        return str(report_path)

    def _calculate_regression_rate(self, reports: List[BugReport]) -> float:
        """
        Calculate regression rate (bugs reintroduced after fix).

        For now, returns 0.0 as placeholder. In future implementation,
        this will check bug signatures against historical database.

        Args:
            reports: List of BugReport objects

        Returns:
            Regression rate as percentage (0.0 - 100.0)
        """
        # TODO: Implement historical bug signature tracking
        # 1. Load previous week bug signatures from SQLite database
        # 2. Check if any current bugs match previous weeks (were reintroduced)
        # 3. Calculate regression rate = (reintroduced_bugs / total_bugs) * 100
        return 0.0

    def _calculate_regression_rate_with_db(self, reports: List[BugReport]) -> float:
        """
        Calculate regression rate by comparing bug signatures with historical database.

        A bug is considered a regression if its error_signature was found in a previous week.

        Args:
            reports: List of BugReport objects

        Returns:
            Regression rate as percentage (0.0 - 100.0)
        """
        if not reports:
            return 0.0

        # Connect to metrics database
        if not self.db_path.exists():
            return 0.0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get bug signatures from this week
            current_signatures = set(r.error_signature for r in reports)

            # Get signatures from previous runs (older than 7 days)
            one_week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            cursor.execute("""
                SELECT DISTINCT error_signature
                FROM (
                    -- Assuming we store signatures in discovery_runs metadata
                    -- This is a simplified query - actual implementation depends on schema
                    SELECT json_extract(metadata, '$.error_signatures') as error_signatures
                    FROM discovery_runs
                    WHERE timestamp < ?
                )
                WHERE error_signatures IS NOT NULL
            """, (one_week_ago,))

            previous_signatures = set(row[0] for row in cursor.fetchall() if row[0])

            conn.close()

            # Count regressions (current bugs that were seen before)
            regressions = len(current_signatures & previous_signatures)

            # Calculate regression rate
            regression_rate = (regressions / len(current_signatures)) * 100 if current_signatures else 0.0

            return round(regression_rate, 1)

        except Exception as e:
            print(f"[DashboardGenerator] Warning: Could not calculate regression rate: {e}")
            return 0.0

    def _calculate_effectiveness_metrics(
        self,
        bugs_found: int,
        duration_seconds: float,
        unique_bugs: int
    ) -> Dict[str, Any]:
        """
        Calculate effectiveness metrics for bug discovery automation.

        Args:
            bugs_found: Total bugs found
            duration_seconds: Discovery run duration
            unique_bugs: Unique bugs after deduplication

        Returns:
            Dict with effectiveness metrics
        """
        if duration_seconds <= 0:
            duration_seconds = 1  # Prevent division by zero

        # Bugs found per hour
        bugs_per_hour = (bugs_found / (duration_seconds / 3600)) if duration_seconds > 0 else 0

        # Unique bug rate (percentage of unique bugs)
        unique_rate = (unique_bugs / bugs_found * 100) if bugs_found > 0 else 0

        # Deduplication effectiveness
        dedup_effectiveness = ((bugs_found - unique_bugs) / bugs_found * 100) if bugs_found > 0 else 0

        return {
            "bugs_per_hour": round(bugs_per_hour, 2),
            "unique_rate": round(unique_rate, 1),
            "dedup_effectiveness": round(dedup_effectiveness, 1),
            "total_time_hours": round(duration_seconds / 3600, 2)
        }

    def _render_html_template_with_roi(
        self,
        week_date: str,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        regression_rate: float,
        by_method: Dict[str, int],
        by_severity: Dict[str, int],
        top_bugs: List[BugReport],
        roi_data: Dict[str, Any],
        verification_status: Dict[str, Any] = None,
        effectiveness: Dict[str, Any] = None
    ) -> str:
        """Render HTML template with ROI metrics section."""

        # Extract ROI values
        hours_saved = roi_data.get("hours_saved", 0)
        cost_saved = roi_data.get("cost_saved", 0)
        bugs_prevented = roi_data.get("bugs_prevented", 0)
        roi_ratio = roi_data.get("roi_ratio", 0)
        automation_cost = roi_data.get("automation_cost", 0)
        manual_qa_cost = roi_data.get("manual_qa_cost", 0)

        # Extract effectiveness values
        if effectiveness is None:
            effectiveness = {}

        bugs_per_hour = effectiveness.get("bugs_per_hour", 0)
        unique_rate = effectiveness.get("unique_rate", 0)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Weekly Bug Discovery Report - {week_date}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #0366d6; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; border-bottom: 1px solid #e1e4e8; padding-bottom: 5px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .card {{ border: 1px solid #e1e4e8; padding: 20px; border-radius: 6px; flex: 1; min-width: 200px; text-align: center; }}
        .card h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; }}
        .card .value {{ font-size: 36px; font-weight: bold; }}
        .card.critical .value {{ color: #d32f2f; }}
        .card.high .value {{ color: #f57c00; }}
        .card.medium .value {{ color: #fbc02d; }}
        .card.low .value {{ color: #388e3c; }}
        .card.roi-card {{ border: 2px solid #4caf50; background: #e8f5e9; }}
        .roi-positive {{ color: #4caf50; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #e1e4e8; padding: 12px; text-align: left; }}
        th {{ background-color: #f6f8fa; font-weight: 600; }}
        .critical {{ color: #d32f2f; font-weight: bold; }}
        .high {{ color: #f57c00; }}
        .medium {{ color: #fbc02d; }}
        .low {{ color: #388e3c; }}
        .timestamp {{ color: #666; font-size: 12px; text-align: right; margin-top: 30px; }}
        .trend-up {{ color: #4caf50; }}
        .trend-down {{ color: #d32f2f; }}
        .small {{ font-size: 12px; color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Weekly Bug Discovery Report - {week_date}</h1>

        <!-- Bug Discovery Summary -->
        <div class="summary">
            <div class="card critical">
                <h3>Bugs Found</h3>
                <div class="value">{bugs_found}</div>
                <p class="small">{bugs_per_hour} bugs/hour</p>
            </div>
            <div class="card high">
                <h3>Unique Bugs</h3>
                <div class="value">{unique_bugs}</div>
                <p class="small">{unique_rate}% unique rate</p>
            </div>
            <div class="card medium">
                <h3>Bugs Filed</h3>
                <div class="value">{filed_bugs}</div>
                <p class="small">GitHub issues created</p>
            </div>
            <div class="card low">
                <h3>Regression Rate</h3>
                <div class="value">{regression_rate:.1f}%</div>
                <p class="small">Bugs reintroduced</p>
            </div>
        </div>

        <!-- ROI Metrics Section -->
        <h2>ROI Metrics (Last 4 Weeks)</h2>
        <div class="summary">
            <div class="card roi-card">
                <h3>Hours Saved</h3>
                <div class="value roi-positive">{hours_saved:.0f}h</div>
                <p>Manual QA: {roi_data.get("manual_qa_hours", 0):.0f}h &rarr; Automation: {roi_data.get("automation_hours", 0):.0f}h</p>
            </div>
            <div class="card roi-card">
                <h3>Cost Saved</h3>
                <div class="value roi-positive">${cost_saved:,.0f}</div>
                <p>Manual QA: ${manual_qa_cost:,.0f} &rarr; Automation: ${automation_cost:,.0f}</p>
            </div>
            <div class="card roi-card">
                <h3>Bugs Prevented</h3>
                <div class="value roi-positive">{bugs_prevented}</div>
                <p>Cost Avoidance: ${roi_data.get("cost_avoidance", 0):,.0f}</p>
            </div>
            <div class="card roi-card">
                <h3>ROI Ratio</h3>
                <div class="value roi-positive">{roi_ratio:.1f}x</div>
                <p>Every $1 spent saves ${roi_ratio:.2f}</p>
            </div>
        </div>

        {self._render_fix_verification_section(verification_status) if verification_status else ''}

        <h2>Bugs by Discovery Method</h2>
        <table>
            <tr><th>Method</th><th>Count</th><th>% of Total</th></tr>
            {self._render_method_rows(by_method, bugs_found)}
        </table>

        <h2>Bugs by Severity</h2>
        <table>
            <tr><th>Severity</th><th>Count</th><th>% of Total</th></tr>
            {self._render_severity_rows(by_severity, bugs_found)}
        </table>

        <h2>Top {len(top_bugs)} Bugs</h2>
        <table>
            <tr><th>Test</th><th>Method</th><th>Severity</th><th>Error</th></tr>
            {self._render_bug_rows(top_bugs)}
        </table>

        <div class="timestamp">
            Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC |
            Powered by Atom Bug Discovery Pipeline v8.0 |
            Feedback Loops & ROI Tracking (Phase 245)
        </div>
    </div>
</body>
</html>"""

    def _render_table_rows(self, data: Dict[str, int]) -> str:
        """Render table rows from dict."""
        rows = ""
        for key, value in data.items():
            rows += f'<tr><td>{key}</td><td>{value}</td></tr>\n'
        return rows

    def _render_fix_verification_section(self, verification_status: Dict[str, Any]) -> str:
        """Render fix verification status section."""
        if not verification_status:
            return ""

        return f"""
        <h2>Bug Fix Verification</h2>
        <table>
            <tr><th>Week</th><th>Fixed</th><th>Verified</th><th>Pending</th><th>Regression Rate</th></tr>
            <tr>
                <td>This Week</td>
                <td>{verification_status.get('fixed', 0)}</td>
                <td class="low">{verification_status.get('verified', 0)}</td>
                <td class="high">{verification_status.get('pending', 0)}</td>
                <td>{verification_status.get('regression_rate', 0):.1f}%</td>
            </tr>
        </table>
        """

    def _render_method_rows(self, by_method: Dict[str, int], total: int) -> str:
        """Render discovery method table rows with percentages."""
        rows = ""
        for method, count in by_method.items():
            percentage = (count / total * 100) if total > 0 else 0
            rows += f'<tr><td>{method}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>\n'
        return rows

    def _render_severity_rows(self, by_severity: Dict[str, int], total: int) -> str:
        """Render severity table rows with percentages."""
        rows = ""
        for severity, count in by_severity.items():
            percentage = (count / total * 100) if total > 0 else 0
            severity_class = severity
            rows += f'<tr><td class="{severity_class}">{severity}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>\n'
        return rows

    def _render_bug_rows(self, bugs: List[BugReport]) -> str:
        """Render bug table rows."""
        rows = ""
        for bug in bugs:
            # Handle both enum and string types (use_enum_values=True in BugReport)
            severity_class = bug.severity if isinstance(bug.severity, str) else bug.severity.value
            discovery_method = bug.discovery_method if isinstance(bug.discovery_method, str) else bug.discovery_method.value
            severity = bug.severity if isinstance(bug.severity, str) else bug.severity.value
            error_msg = bug.error_message[:100] + "..." if len(bug.error_message) > 100 else bug.error_message
            rows += f'<tr><td>{bug.test_name}</td><td>{discovery_method}</td><td class="{severity_class}">{severity}</td><td>{error_msg}</td></tr>\n'
        return rows

    def _save_json_report(self, path: Path, data: Dict[str, Any]):
        """Save JSON report for CI artifact upload."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
