#!/usr/bin/env python
"""
Flaky Test Tracker - SQLite Quarantine Database

Tracks flaky tests with failure history, timestamps, and reliability scoring.
Provides persistent storage for flaky test detection across CI/CD runs.

Usage:
    from backend.tests.scripts.flaky_test_tracker import FlakyTestTracker

    tracker = FlakyTestTracker(Path('flaky_tests.db'))
    tracker.record_flaky_test('tests/test_foo.py::test_bar', 'backend', 10, 3, 'flaky', [...])
    quarantined = tracker.get_quarantined_tests('backend')
    reliability = tracker.get_test_reliability_score('tests/test_foo.py::test_bar', 'backend')

Database Schema:
    - flaky_tests table with indexed lookups on (test_path, platform)
    - Tracks first_detected, last_detected, failure_history (JSON)
    - Supports platform filtering and reliability scoring
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class FlakyTestTracker:
    """Track flaky tests in SQLite database with failure history."""

    def __init__(self, db_path: Path):
        """Initialize database and create schema if needed.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_schema()

    def _create_schema(self):
        """Create flaky_tests table and indexes if not exists."""
        # Create main table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS flaky_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_path TEXT NOT NULL,
                platform TEXT NOT NULL,
                first_detected TEXT NOT NULL,
                last_detected TEXT NOT NULL,
                total_runs INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                flaky_rate REAL NOT NULL DEFAULT 0.0,
                avg_execution_time REAL DEFAULT 0.0,
                max_execution_time REAL DEFAULT 0.0,
                classification TEXT NOT NULL,
                failure_history TEXT NOT NULL,
                quarantine_reason TEXT,
                issue_url TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Check if columns exist for migration pattern
        cursor = self.conn.execute("PRAGMA table_info(flaky_tests)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add execution time columns if they don't exist (migration)
        if 'avg_execution_time' not in columns:
            self.conn.execute("ALTER TABLE flaky_tests ADD COLUMN avg_execution_time REAL DEFAULT 0.0")
        if 'max_execution_time' not in columns:
            self.conn.execute("ALTER TABLE flaky_tests ADD COLUMN max_execution_time REAL DEFAULT 0.0")

        # Create indexes for fast lookup
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_path_platform
            ON flaky_tests(test_path, platform)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_flaky_rate
            ON flaky_tests(flaky_rate DESC)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_classification
            ON flaky_tests(classification)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_max_execution_time
            ON flaky_tests(max_execution_time DESC)
        """)

        self.conn.commit()

    def record_flaky_test(
        self,
        test_path: str,
        platform: str,
        total_runs: int,
        failure_count: int,
        classification: str,
        failure_history: List[Dict],
        execution_times: Optional[List[float]] = None,
        quarantine_reason: Optional[str] = None
    ) -> int:
        """Record or update a flaky test in the database.

        Args:
            test_path: Full test identifier (e.g., tests/test_foo.py::test_bar)
            platform: Platform name (backend/frontend/mobile/desktop)
            total_runs: Total number of test runs executed
            failure_count: Number of failures observed
            classification: Test classification (stable/flaky/broken)
            failure_history: List of failure details (JSON-serializable)
            execution_times: Optional list of execution times per run (seconds)
            quarantine_reason: Optional reason for quarantine

        Returns:
            test_id: Database ID of the inserted/updated record
        """
        flaky_rate = failure_count / total_runs if total_runs > 0 else 0.0

        # Calculate execution time statistics
        if execution_times and len(execution_times) > 0:
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
        else:
            avg_time = 0.0
            max_time = 0.0

        now = datetime.utcnow().isoformat()

        # Check if test already exists
        cursor = self.conn.execute(
            "SELECT id, failure_history, total_runs, failure_count, avg_execution_time, max_execution_time FROM flaky_tests "
            "WHERE test_path = ? AND platform = ?",
            (test_path, platform)
        )
        row = cursor.fetchone()

        if row:
            # Update existing record
            test_id, existing_history_json, existing_runs, existing_failures, existing_avg_time, existing_max_time = row
            existing_history = json.loads(existing_history_json)
            merged_history = existing_history + failure_history

            # Aggregate statistics
            new_total_runs = existing_runs + total_runs
            new_failure_count = existing_failures + failure_count
            new_flaky_rate = new_failure_count / new_total_runs if new_total_runs > 0 else 0.0

            # Update execution times with weighted average
            if avg_time > 0:
                new_avg_time = ((existing_avg_time * existing_runs) + (avg_time * total_runs)) / new_total_runs
                new_max_time = max(existing_max_time, max_time)
            else:
                new_avg_time = existing_avg_time
                new_max_time = existing_max_time

            self.conn.execute("""
                UPDATE flaky_tests
                SET last_detected = ?,
                    total_runs = ?,
                    failure_count = ?,
                    flaky_rate = ?,
                    avg_execution_time = ?,
                    max_execution_time = ?,
                    classification = ?,
                    failure_history = ?,
                    quarantine_reason = COALESCE(?, quarantine_reason),
                    updated_at = ?
                WHERE id = ?
            """, (
                now, new_total_runs, new_failure_count,
                round(new_flaky_rate, 3), round(new_avg_time, 3), round(new_max_time, 3),
                classification, json.dumps(merged_history), quarantine_reason, now, test_id
            ))
            self.conn.commit()
            return test_id
        else:
            # Insert new record
            cursor = self.conn.execute("""
                INSERT INTO flaky_tests (
                    test_path, platform, first_detected, last_detected,
                    total_runs, failure_count, flaky_rate, avg_execution_time, max_execution_time,
                    classification, failure_history, quarantine_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_path, platform, now, now,
                total_runs, failure_count, round(flaky_rate, 3),
                round(avg_time, 3), round(max_time, 3),
                classification, json.dumps(failure_history), quarantine_reason
            ))
            self.conn.commit()
            return cursor.lastrowid

    def get_quarantined_tests(self, platform: Optional[str] = None) -> List[Dict]:
        """Get all quarantined tests, optionally filtered by platform.

        Args:
            platform: Optional platform filter (backend/frontend/mobile/desktop)

        Returns:
            List of flaky test records as dictionaries
        """
        query = "SELECT * FROM flaky_tests WHERE classification = 'flaky'"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY flaky_rate DESC"

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_test_reliability_score(self, test_path: str, platform: str) -> float:
        """Calculate reliability score for a test (0.0 to 1.0).

        Reliability = 1.0 - flaky_rate
        Returns 1.0 if test not found (no failures = perfect reliability)

        Args:
            test_path: Full test identifier
            platform: Platform name

        Returns:
            Reliability score (0.0 = completely unreliable, 1.0 = perfect)
        """
        cursor = self.conn.execute(
            "SELECT flaky_rate FROM flaky_tests WHERE test_path = ? AND platform = ?",
            (test_path, platform)
        )
        row = cursor.fetchone()

        if not row:
            return 1.0  # No failures recorded = perfect reliability

        flaky_rate = row[0]
        return max(0.0, round(1.0 - flaky_rate, 3))

    def get_test_history(
        self,
        test_path: str,
        platform: str
    ) -> Optional[Dict]:
        """Get full history for a specific test.

        Args:
            test_path: Full test identifier
            platform: Platform name

        Returns:
            Test record as dictionary, or None if not found
        """
        cursor = self.conn.execute(
            "SELECT * FROM flaky_tests WHERE test_path = ? AND platform = ?",
            (test_path, platform)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_dict(row)

    def get_flaky_tests_by_rate(
        self,
        min_flaky_rate: float = 0.0,
        max_flaky_rate: float = 1.0,
        platform: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get flaky tests within a flaky rate range.

        Args:
            min_flaky_rate: Minimum flaky rate (inclusive)
            max_flaky_rate: Maximum flaky rate (inclusive)
            platform: Optional platform filter
            limit: Maximum number of records to return

        Returns:
            List of flaky test records sorted by flaky rate (descending)
        """
        query = """
            SELECT * FROM flaky_tests
            WHERE flaky_rate >= ? AND flaky_rate <= ?
        """
        params = [min_flaky_rate, max_flaky_rate]

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY flaky_rate DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def mark_test_fixed(
        self,
        test_path: str,
        platform: str,
        fixed_note: Optional[str] = None
    ) -> bool:
        """Mark a flaky test as fixed (remove from quarantine).

        Args:
            test_path: Full test identifier
            platform: Platform name
            fixed_note: Optional note about how the test was fixed

        Returns:
            True if test was updated, False if not found
        """
        now = datetime.utcnow().isoformat()

        cursor = self.conn.execute(
            "UPDATE flaky_tests "
            "SET classification = 'stable', "
            "    updated_at = ?, "
            "    quarantine_reason = ? "
            "WHERE test_path = ? AND platform = ?",
            (now, fixed_note or "Marked as fixed", test_path, platform)
        )

        self.conn.commit()
        return cursor.rowcount > 0

    def update_execution_time(
        self,
        test_path: str,
        platform: str,
        execution_times: List[float]
    ) -> bool:
        """Update execution time metrics for a test.

        Args:
            test_path: Full test identifier
            platform: Platform name
            execution_times: List of execution times from recent runs

        Returns:
            True if test was updated, False if not found
        """
        if not execution_times:
            return False

        # Calculate execution time statistics
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)

        # Get existing data to calculate weighted average
        cursor = self.conn.execute(
            "SELECT id, total_runs, avg_execution_time, max_execution_time FROM flaky_tests "
            "WHERE test_path = ? AND platform = ?",
            (test_path, platform)
        )
        row = cursor.fetchone()

        if not row:
            return False

        test_id, existing_runs, existing_avg_time, existing_max_time = row

        # Calculate weighted average
        new_runs = existing_runs + len(execution_times)
        new_avg_time = ((existing_avg_time * existing_runs) + sum(execution_times)) / new_runs
        new_max_time = max(existing_max_time, max_time)

        now = datetime.utcnow().isoformat()

        cursor = self.conn.execute(
            "UPDATE flaky_tests "
            "SET avg_execution_time = ?, max_execution_time = ?, total_runs = ?, updated_at = ? "
            "WHERE id = ?",
            (round(new_avg_time, 3), round(new_max_time, 3), new_runs, now, test_id)
        )

        self.conn.commit()
        return cursor.rowcount > 0

    def get_slow_tests(
        self,
        min_time: float = 10.0,
        platform: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get slow tests exceeding execution time threshold.

        Args:
            min_time: Minimum execution time in seconds (default: 10s)
            platform: Optional platform filter
            limit: Maximum records to return

        Returns:
            List of slow test records sorted by max_execution_time (descending)
        """
        query = """
            SELECT * FROM flaky_tests
            WHERE max_execution_time >= ?
        """
        params = [min_time]

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY max_execution_time DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_statistics(self, platform: Optional[str] = None) -> Dict:
        """Get aggregate statistics about flaky tests.

        Args:
            platform: Optional platform filter

        Returns:
            Dictionary with statistics (total, flaky, broken, stable counts)
        """
        where_clause = f"WHERE platform = '{platform}'" if platform else ""
        params = []

        # Get counts by classification
        query = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN classification = 'flaky' THEN 1 ELSE 0 END) as flaky,
                SUM(CASE WHEN classification = 'broken' THEN 1 ELSE 0 END) as broken,
                SUM(CASE WHEN classification = 'stable' THEN 1 ELSE 0 END) as stable,
                AVG(flaky_rate) as avg_flaky_rate
            FROM flaky_tests
            {where_clause}
        """

        cursor = self.conn.execute(query, params)
        row = cursor.fetchone()

        return {
            "total": row[0] or 0,
            "flaky": row[1] or 0,
            "broken": row[2] or 0,
            "stable": row[3] or 0,
            "avg_flaky_rate": round(row[4] or 0.0, 3)
        }

    def _row_to_dict(self, row) -> Dict:
        """Convert database row to dictionary.

        Args:
            row: Database row tuple

        Returns:
            Dictionary mapping column names to values
        """
        columns = [
            'id', 'test_path', 'platform', 'first_detected', 'last_detected',
            'total_runs', 'failure_count', 'flaky_rate', 'avg_execution_time', 'max_execution_time',
            'classification', 'failure_history', 'quarantine_reason', 'issue_url',
            'created_at', 'updated_at'
        ]
        result = dict(zip(columns, row))

        # Parse JSON fields
        if result['failure_history']:
            try:
                result['failure_history'] = json.loads(result['failure_history'])
            except json.JSONDecodeError:
                result['failure_history'] = []

        return result

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def main():
    """CLI for flaky test tracker operations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Flaky Test Tracker - SQLite Quarantine Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record a flaky test
  python flaky_test_tracker.py --record \\
    --test-path tests/test_foo.py::test_bar \\
    --platform backend \\
    --total-runs 10 \\
    --failures 3 \\
    --classification flaky

  # Get quarantined tests
  python flaky_test_tracker.py --quarantined --platform backend

  # Get reliability score
  python flaky_test_tracker.py --reliability \\
    --test-path tests/test_foo.py::test_bar \\
    --platform backend

  # Get statistics
  python flaky_test_tracker.py --stats
        """
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default="tests/coverage_reports/metrics/flaky_tests.db",
        help="Path to SQLite database"
    )

    parser.add_argument(
        "--record",
        action="store_true",
        help="Record a flaky test"
    )

    parser.add_argument(
        "--test-path",
        type=str,
        help="Test identifier (e.g., tests/test_foo.py::test_bar)"
    )

    parser.add_argument(
        "--platform",
        type=str,
        choices=["backend", "frontend", "mobile", "desktop"],
        help="Platform name"
    )

    parser.add_argument(
        "--total-runs",
        type=int,
        help="Total number of test runs"
    )

    parser.add_argument(
        "--failures",
        type=int,
        help="Number of failures"
    )

    parser.add_argument(
        "--classification",
        type=str,
        choices=["stable", "flaky", "broken"],
        help="Test classification"
    )

    parser.add_argument(
        "--quarantine-reason",
        type=str,
        help="Reason for quarantine"
    )

    parser.add_argument(
        "--quarantined",
        action="store_true",
        help="Get quarantined tests"
    )

    parser.add_argument(
        "--reliability",
        action="store_true",
        help="Get reliability score for a test"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Get aggregate statistics"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    tracker = FlakyTestTracker(Path(args.db_path))

    try:
        if args.record:
            if not all([args.test_path, args.platform, args.total_runs is not None,
                       args.failures is not None, args.classification]):
                print("ERROR: --record requires --test-path, --platform, --total-runs, "
                      "--failures, --classification")
                return 2

            failure_history = [
                {"run": i, "failed": i < args.failures}
                for i in range(args.total_runs)
            ]

            test_id = tracker.record_flaky_test(
                args.test_path,
                args.platform,
                args.total_runs,
                args.failures,
                args.classification,
                failure_history,
                args.quarantine_reason
            )

            if args.json:
                print(json.dumps({"test_id": test_id}))
            else:
                print(f"Recorded test ID: {test_id}")

        elif args.quarantined:
            tests = tracker.get_quarantined_tests(args.platform)

            if args.json:
                print(json.dumps(tests, indent=2))
            else:
                print(f"Quarantined tests: {len(tests)}")
                for test in tests:
                    print(f"  - {test['test_path']} ({test['platform']}) "
                          f"flaky_rate={test['flaky_rate']}")

        elif args.reliability:
            if not all([args.test_path, args.platform]):
                print("ERROR: --reliability requires --test-path and --platform")
                return 2

            score = tracker.get_test_reliability_score(args.test_path, args.platform)

            if args.json:
                print(json.dumps({"reliability_score": score}))
            else:
                print(f"Reliability score: {score}")

        elif args.stats:
            stats = tracker.get_statistics(args.platform)

            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print(f"Total tests: {stats['total']}")
                print(f"Flaky: {stats['flaky']}")
                print(f"Broken: {stats['broken']}")
                print(f"Stable: {stats['stable']}")
                print(f"Avg flaky rate: {stats['avg_flaky_rate']}")

        else:
            parser.print_help()

    finally:
        tracker.close()


if __name__ == "__main__":
    main()
