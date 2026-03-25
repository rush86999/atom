"""
ROI Tracker for Bug Discovery Automation.

This module tracks and calculates ROI metrics for automated bug discovery,
comparing manual QA costs vs automation costs, and demonstrating business value.

Example:
    tracker = ROITracker()
    tracker.record_discovery_run(
        bugs_found=42,
        unique_bugs=35,
        filed_bugs=30,
        duration_seconds=3600,
        by_method={"fuzzing": 20, "chaos": 10, "property": 8, "browser": 4},
        by_severity={"critical": 2, "high": 10, "medium": 15, "low": 15}
    )
    roi_report = tracker.generate_roi_report(weeks=4)
    print(f"ROI: {roi_report['roi_ratio']:.1f}x")
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Add backend to path for imports
import sys
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


class ROITracker:
    """
    Track ROI metrics for bug discovery automation.

    Metrics collected:
    - Bugs found (by method, severity)
    - Time to discovery (automation vs manual QA)
    - Time to fix (from filed to closed)
    - Cost avoidance (bugs prevented from production)
    - Manual QA cost vs automation cost

    Example:
        tracker = ROITracker()
        tracker.record_discovery_run(
            bugs_found=42,
            unique_bugs=35,
            filed_bugs=30,
            duration_seconds=3600,
            by_method={"fuzzing": 20, "chaos": 10, "property": 8, "browser": 4},
            by_severity={"critical": 2, "high": 10, "medium": 15, "low": 15}
        )
        roi_report = tracker.generate_roi_report(weeks=4)
        print(f"ROI: {roi_report['roi_ratio']:.1f}x")
    """

    # Default cost assumptions (configurable via __init__)
    DEFAULT_MANUAL_QA_HOURLY_RATE = 75.0  # $/hour
    DEFAULT_DEVELOPER_HOURLY_RATE = 100.0  # $/hour
    DEFAULT_BUG_PRODUCTION_COST = 10000.0  # Average cost of production bug
    DEFAULT_MANUAL_QA_HOURS_PER_BUG = 2.0  # Hours to manually find and report a bug

    def __init__(
        self,
        db_path: str = None,
        manual_qa_hourly_rate: float = None,
        developer_hourly_rate: float = None,
        bug_production_cost: float = None,
        manual_qa_hours_per_bug: float = None
    ):
        """
        Initialize ROITracker.

        Args:
            db_path: Path to SQLite database (default: backend/tests/bug_discovery/storage/metrics.db)
            manual_qa_hourly_rate: Cost per hour for manual QA (default: $75)
            developer_hourly_rate: Cost per hour for developer time (default: $100)
            bug_production_cost: Average cost of bug reaching production (default: $10,000)
            manual_qa_hours_per_bug: Hours to manually find/report a bug (default: 2.0)
        """
        if db_path is None:
            db_path = backend_dir / "tests" / "bug_discovery" / "storage" / "metrics.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Cost assumptions
        self.manual_qa_hourly_rate = manual_qa_hourly_rate or self.DEFAULT_MANUAL_QA_HOURLY_RATE
        self.developer_hourly_rate = developer_hourly_rate or self.DEFAULT_DEVELOPER_HOURLY_RATE
        self.bug_production_cost = bug_production_cost or self.DEFAULT_BUG_PRODUCTION_COST
        self.manual_qa_hours_per_bug = manual_qa_hours_per_bug or self.DEFAULT_MANUAL_QA_HOURS_PER_BUG

        # Initialize database schema
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with metrics schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Discovery runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                bugs_found INTEGER NOT NULL,
                unique_bugs INTEGER NOT NULL,
                filed_bugs INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                by_method TEXT NOT NULL,
                by_severity TEXT NOT NULL,
                automation_cost REAL NOT NULL
            )
        """)

        # Bug fixes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bug_fixes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bug_id TEXT NOT NULL,
                issue_number INTEGER NOT NULL,
                filed_at TEXT NOT NULL,
                fixed_at TEXT NOT NULL,
                fix_duration_hours REAL NOT NULL,
                severity TEXT NOT NULL,
                discovery_method TEXT NOT NULL
            )
        """)

        # ROI summary table (aggregated weekly)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roi_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL UNIQUE,
                bugs_found INTEGER NOT NULL,
                bugs_fixed INTEGER NOT NULL,
                hours_saved REAL NOT NULL,
                cost_saved REAL NOT NULL,
                automation_cost REAL NOT NULL,
                roi REAL NOT NULL,
                bugs_prevented INTEGER NOT NULL,
                cost_avoidance REAL NOT NULL,
                total_savings REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def record_discovery_run(
        self,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        duration_seconds: float,
        by_method: Dict[str, int],
        by_severity: Dict[str, int]
    ):
        """
        Record bug discovery run metrics.

        Args:
            bugs_found: Total bugs found (including duplicates)
            unique_bugs: Unique bugs after deduplication
            filed_bugs: Bugs filed to GitHub
            duration_seconds: Discovery run duration
            by_method: Bugs by discovery method (e.g., {"fuzzing": 10, "chaos": 5})
            by_severity: Bugs by severity (e.g., {"critical": 2, "high": 8})
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate automation cost (developer time)
        automation_cost = (duration_seconds / 3600) * self.developer_hourly_rate

        cursor.execute("""
            INSERT INTO discovery_runs (
                timestamp, bugs_found, unique_bugs, filed_bugs,
                duration_seconds, by_method, by_severity, automation_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            bugs_found,
            unique_bugs,
            filed_bugs,
            duration_seconds,
            json.dumps(by_method),
            json.dumps(by_severity),
            automation_cost
        ))

        conn.commit()
        conn.close()

    def record_fixes(
        self,
        bug_ids: List[str],
        issue_numbers: List[int],
        filed_dates: List[str],
        fix_duration_hours: float,
        severity: str = "medium",
        discovery_method: str = "unknown"
    ):
        """
        Record bug fix metrics.

        Args:
            bug_ids: List of bug IDs
            issue_numbers: List of GitHub issue numbers
            filed_dates: List of filed dates (ISO format)
            fix_duration_hours: Average time to fix (hours)
            severity: Bug severity (default: "medium")
            discovery_method: How bug was discovered (default: "unknown")
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for bug_id, issue_number, filed_date in zip(bug_ids, issue_numbers, filed_dates):
            cursor.execute("""
                INSERT INTO bug_fixes (
                    bug_id, issue_number, filed_at, fixed_at, fix_duration_hours, severity, discovery_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                bug_id,
                issue_number,
                filed_date,
                datetime.utcnow().isoformat(),
                fix_duration_hours,
                severity,
                discovery_method
            ))

        conn.commit()
        conn.close()

    def generate_roi_report(
        self,
        weeks: int = 4,
        include_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Generate ROI report for last N weeks.

        Args:
            weeks: Number of weeks to include in report (default: 4)
            include_breakdown: Include detailed breakdown by method/severity

        Returns:
            Dict with ROI metrics (bugs_found, bugs_fixed, hours_saved, cost_saved, roi_ratio)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate week start date
        week_start = (datetime.utcnow() - timedelta(weeks=weeks)).isoformat()

        # Aggregate discovery metrics
        cursor.execute("""
            SELECT
                SUM(bugs_found) as total_bugs_found,
                SUM(unique_bugs) as total_unique_bugs,
                SUM(filed_bugs) as total_filed_bugs,
                SUM(duration_seconds) as total_duration_seconds,
                SUM(automation_cost) as total_automation_cost
            FROM discovery_runs
            WHERE timestamp >= ?
        """, (week_start,))

        discovery_row = cursor.fetchone()

        # Aggregate fix metrics
        cursor.execute("""
            SELECT
                COUNT(*) as total_fixed_bugs,
                AVG(fix_duration_hours) as avg_fix_duration_hours
            FROM bug_fixes
            WHERE fixed_at >= ?
        """, (week_start,))

        fix_row = cursor.fetchone()

        conn.close()

        # Extract values
        total_bugs_found = discovery_row[0] or 0
        total_unique_bugs = discovery_row[1] or 0
        total_filed_bugs = discovery_row[2] or 0
        total_duration_seconds = discovery_row[3] or 0
        total_automation_cost = discovery_row[4] or 0
        total_fixed_bugs = fix_row[0] or 0
        avg_fix_duration_hours = fix_row[1] or 0

        # Calculate ROI metrics
        manual_qa_hours = total_bugs_found * self.manual_qa_hours_per_bug
        automation_hours = total_duration_seconds / 3600
        hours_saved = manual_qa_hours - automation_hours

        # Cost calculations
        manual_qa_cost = manual_qa_hours * self.manual_qa_hourly_rate
        cost_saved = manual_qa_cost - total_automation_cost

        # Bugs prevented from production (10% assumption)
        bugs_prevented = int(total_bugs_found * 0.1)
        cost_avoidance = bugs_prevented * self.bug_production_cost

        # Total savings
        total_savings = cost_saved + cost_avoidance

        # ROI ratio (savings / cost)
        roi_ratio = total_savings / total_automation_cost if total_automation_cost > 0 else 0

        report = {
            "period_weeks": weeks,
            "period_start": week_start,
            "period_end": datetime.utcnow().isoformat(),
            "bugs_found": total_bugs_found,
            "unique_bugs": total_unique_bugs,
            "filed_bugs": total_filed_bugs,
            "bugs_fixed": total_fixed_bugs,
            "manual_qa_hours": manual_qa_hours,
            "automation_hours": automation_hours,
            "hours_saved": hours_saved,
            "manual_qa_cost": manual_qa_cost,
            "automation_cost": total_automation_cost,
            "cost_saved": cost_saved,
            "bugs_prevented": bugs_prevented,
            "cost_avoidance": cost_avoidance,
            "total_savings": total_savings,
            "roi_ratio": roi_ratio,
            "avg_fix_duration_hours": avg_fix_duration_hours,
            "cost_assumptions": {
                "manual_qa_hourly_rate": self.manual_qa_hourly_rate,
                "developer_hourly_rate": self.developer_hourly_rate,
                "bug_production_cost": self.bug_production_cost,
                "manual_qa_hours_per_bug": self.manual_qa_hours_per_bug
            }
        }

        # Add breakdown if requested
        if include_breakdown:
            report["breakdown"] = self._get_breakdown(week_start)

        return report

    def _get_breakdown(self, since: str) -> Dict[str, Any]:
        """Get detailed breakdown by method and severity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # By method breakdown
        cursor.execute("""
            SELECT by_method FROM discovery_runs WHERE timestamp >= ?
        """, (since,))

        method_counts = {}
        for (by_method_json,) in cursor.fetchall():
            by_method = json.loads(by_method_json)
            for method, count in by_method.items():
                method_counts[method] = method_counts.get(method, 0) + count

        # By severity breakdown
        cursor.execute("""
            SELECT by_severity FROM discovery_runs WHERE timestamp >= ?
        """, (since,))

        severity_counts = {}
        for (by_severity_json,) in cursor.fetchall():
            by_severity = json.loads(by_severity_json)
            for severity, count in by_severity.items():
                severity_counts[severity] = severity_counts.get(severity, 0) + count

        conn.close()

        return {
            "by_method": method_counts,
            "by_severity": severity_counts
        }

    def get_weekly_trends(
        self,
        weeks: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get weekly trend data for charts.

        Args:
            weeks: Number of weeks to include

        Returns:
            List of weekly data points
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        trends = []
        for i in range(weeks):
            week_start = (datetime.utcnow() - timedelta(weeks=i+1)).isoformat()
            week_end = (datetime.utcnow() - timedelta(weeks=i)).isoformat()

            cursor.execute("""
                SELECT
                    SUM(bugs_found) as bugs_found,
                    SUM(unique_bugs) as unique_bugs,
                    SUM(filed_bugs) as filed_bugs,
                    SUM(automation_cost) as automation_cost
                FROM discovery_runs
                WHERE timestamp >= ? AND timestamp < ?
            """, (week_start, week_end))

            row = cursor.fetchone()
            trends.append({
                "week_start": week_start,
                "week_end": week_end,
                "bugs_found": row[0] or 0,
                "unique_bugs": row[1] or 0,
                "filed_bugs": row[2] or 0,
                "automation_cost": row[3] or 0
            })

        conn.close()
        return list(reversed(trends))

    def save_weekly_summary(self, report: Dict[str, Any]):
        """
        Save weekly ROI summary to database.

        Args:
            report: ROI report from generate_roi_report()
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate week start (Monday of current week)
        today = datetime.utcnow().date()
        week_start = (today - timedelta(days=today.weekday())).isoformat()

        try:
            cursor.execute("""
                INSERT INTO roi_summary (
                    week_start, bugs_found, bugs_fixed, hours_saved, cost_saved,
                    automation_cost, roi, bugs_prevented, cost_avoidance, total_savings, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                week_start,
                report["bugs_found"],
                report["bugs_fixed"],
                report["hours_saved"],
                report["cost_saved"],
                report["automation_cost"],
                report["roi_ratio"],
                report["bugs_prevented"],
                report["cost_avoidance"],
                report["total_savings"],
                datetime.utcnow().isoformat()
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            # Week already exists, update instead
            cursor.execute("""
                UPDATE roi_summary SET
                    bugs_found = ?, bugs_fixed = ?, hours_saved = ?, cost_saved = ?,
                    automation_cost = ?, roi = ?, bugs_prevented = ?, cost_avoidance = ?, total_savings = ?
                WHERE week_start = ?
            """, (
                report["bugs_found"],
                report["bugs_fixed"],
                report["hours_saved"],
                report["cost_saved"],
                report["automation_cost"],
                report["roi_ratio"],
                report["bugs_prevented"],
                report["cost_avoidance"],
                report["total_savings"],
                week_start
            ))
            conn.commit()

        conn.close()
