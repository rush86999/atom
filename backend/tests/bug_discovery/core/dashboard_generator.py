"""
DashboardGenerator service for weekly bug discovery reports.

This module provides the DashboardGenerator that produces HTML and JSON
reports with bug trends (found, fixed, regression rate) for weekly
discovery runs.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
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

    def _render_html_template(
        self,
        week_date: str,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        regression_rate: float,
        by_method: Dict[str, int],
        by_severity: Dict[str, int],
        top_bugs: List[BugReport]
    ) -> str:
        """Render HTML template with report data."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Weekly Bug Discovery Report - {week_date}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #0366d6; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .card {{ border: 1px solid #e1e4e8; padding: 20px; border-radius: 6px; flex: 1; text-align: center; }}
        .card h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; }}
        .card .value {{ font-size: 36px; font-weight: bold; }}
        .card.critical .value {{ color: #d32f2f; }}
        .card.high .value {{ color: #f57c00; }}
        .card.medium .value {{ color: #fbc02d; }}
        .card.low .value {{ color: #388e3c; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #e1e4e8; padding: 12px; text-align: left; }}
        th {{ background-color: #f6f8fa; font-weight: 600; }}
        .critical {{ color: #d32f2f; font-weight: bold; }}
        .high {{ color: #f57c00; }}
        .medium {{ color: #fbc02d; }}
        .low {{ color: #388e3c; }}
        .timestamp {{ color: #666; font-size: 12px; text-align: right; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Weekly Bug Discovery Report - {week_date}</h1>

        <div class="summary">
            <div class="card critical">
                <h3>Bugs Found</h3>
                <div class="value">{bugs_found}</div>
            </div>
            <div class="card high">
                <h3>Unique Bugs</h3>
                <div class="value">{unique_bugs}</div>
            </div>
            <div class="card medium">
                <h3>Bugs Filed</h3>
                <div class="value">{filed_bugs}</div>
            </div>
            <div class="card low">
                <h3>Regression Rate</h3>
                <div class="value">{regression_rate:.1f}%</div>
            </div>
        </div>

        <h2>Bugs by Discovery Method</h2>
        <table>
            <tr><th>Method</th><th>Count</th></tr>
            {self._render_table_rows(by_method)}
        </table>

        <h2>Bugs by Severity</h2>
        <table>
            <tr><th>Severity</th><th>Count</th></tr>
            {self._render_table_rows(by_severity)}
        </table>

        <h2>Top {len(top_bugs)} Bugs</h2>
        <table>
            <tr><th>Test</th><th>Method</th><th>Severity</th><th>Error</th></tr>
            {self._render_bug_rows(top_bugs)}
        </table>

        <div class="timestamp">
            Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC |
            Powered by Atom Bug Discovery Pipeline v8.0
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
