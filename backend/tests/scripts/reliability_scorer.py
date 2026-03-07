#!/usr/bin/env python3
"""
Reliability Scorer - Cross-Platform Test Reliability Calculation

Aggregates flaky test data from all platforms (pytest, Jest, jest-expo, cargo)
into a unified reliability score for CI/CD visibility and trend tracking.

Usage:
    python reliability_scorer.py \
        --backend-flaky results/backend/flaky_tests.json \
        --frontend-flaky results/frontend/flaky_tests.json \
        --mobile-flaky results/mobile/flaky_tests.json \
        --desktop-flaky results/desktop/flaky_tests.json \
        --output results/reliability_score.json

    # Or load from database
    python reliability_scorer.py \
        --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \
        --output results/reliability_score.json

Reliability Scoring Formula:
    - Individual test: reliability = 1.0 - flaky_rate
    - Platform score: average of all test reliabilities
    - Overall score: weighted average (backend 35%, frontend 40%, mobile 15%, desktop 10%)
    - Reference: Phase 146 weighted coverage distribution (based on business impact)
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def calculate_reliability_score(flaky_rate: float) -> float:
    """Calculate reliability score for a single test.

    Args:
        flaky_rate: Flaky rate (0.0 to 1.0, where 1.0 = always fails)

    Returns:
        Reliability score (0.0 to 1.0, where 1.0 = perfectly reliable)
    """
    # Handle edge cases
    if flaky_rate is None:
        return 1.0  # No data = assume reliable
    if flaky_rate < 0:
        flaky_rate = 0.0
    elif flaky_rate > 1.0:
        flaky_rate = 1.0

    # Reliability = 1.0 - flaky_rate
    reliability = 1.0 - flaky_rate
    return round(max(0.0, reliability), 3)


def calculate_platform_score(flaky_tests: List[Dict], platform: str) -> float:
    """Calculate reliability score for a platform.

    Args:
        flaky_tests: List of flaky test dicts with 'flaky_rate' field
        platform: Platform name (backend/frontend/mobile/desktop)

    Returns:
        Platform reliability score (0.0 to 1.0)
    """
    if not flaky_tests:
        return 1.0  # No flaky tests = perfect reliability

    # Calculate reliability for each test
    reliabilities = []
    for test in flaky_tests:
        flaky_rate = test.get('flaky_rate', 0.0)
        reliability = calculate_reliability_score(flaky_rate)
        reliabilities.append(reliability)

    # Return average reliability
    if not reliabilities:
        return 1.0

    avg_reliability = sum(reliabilities) / len(reliabilities)
    return round(avg_reliability, 3)


def aggregate_platform_scores(platform_flaky_data: Dict) -> Dict:
    """Aggregate platform scores into overall reliability score.

    Args:
        platform_flaky_data: Dict with platform keys and flaky test lists
            {
                "backend": [flaky test objects],
                "frontend": [flaky test objects],
                "mobile": [flaky test objects],
                "desktop": [flaky test objects]
            }

    Returns:
        Dict with overall_score, platform_scores, weights_used
    """
    # Phase 146 weights (based on business impact)
    weights = {
        "backend": 0.35,
        "frontend": 0.40,
        "mobile": 0.15,
        "desktop": 0.10
    }

    # Calculate each platform score
    platform_scores = {}
    for platform, flaky_tests in platform_flaky_data.items():
        score = calculate_platform_score(flaky_tests, platform)
        platform_scores[platform] = score

    # Calculate weighted average
    overall_score = sum(
        platform_scores[platform] * weights[platform]
        for platform in platform_scores
    )

    return {
        "overall_score": round(overall_score, 3),
        "platform_scores": platform_scores,
        "weights_used": weights
    }


def load_flaky_data(file_path: str, platform: str) -> List[Dict]:
    """Load flaky test data from JSON file.

    Args:
        file_path: Path to JSON file with flaky test data
        platform: Platform name to tag on each test

    Returns:
        List of flaky test dicts with platform field added
    """
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return []

    # Handle different JSON formats
    if isinstance(data, dict):
        # Format: {"flaky_tests": [...], "summary": {...}}
        flaky_tests = data.get('flaky_tests', [])
    elif isinstance(data, list):
        # Format:直接是数组
        flaky_tests = data
    else:
        flaky_tests = []

    # Add platform field to each test
    for test in flaky_tests:
        test['platform'] = platform

    return flaky_tests


def load_from_database(db_path: Path, platform: Optional[str] = None) -> List[Dict]:
    """Load flaky test data from SQLite database.

    Args:
        db_path: Path to flaky_tests.db
        platform: Optional platform filter (backend/frontend/mobile/desktop)

    Returns:
        List of flaky test dicts
    """
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM flaky_tests WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY flaky_rate DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        tests = []
        for row in rows:
            test = dict(row)
            # Parse JSON fields
            if test.get('failure_history'):
                try:
                    test['failure_history'] = json.loads(test['failure_history'])
                except json.JSONDecodeError:
                    test['failure_history'] = []
            tests.append(test)

        conn.close()
        return tests

    except (sqlite3.Error, json.JSONDecodeError):
        return []


def calculate_score_from_db(db_path: Path) -> Dict:
    """Calculate reliability score from database.

    Args:
        db_path: Path to flaky_tests.db

    Returns:
        Dict with reliability scores and metadata
    """
    # Load all platforms from database
    platform_data = {}
    for platform in ["backend", "frontend", "mobile", "desktop"]:
        platform_data[platform] = load_from_database(db_path, platform)

    # Calculate scores
    result = aggregate_platform_scores(platform_data)

    # Add metadata
    all_tests = []
    for platform_tests in platform_data.values():
        all_tests.extend(platform_tests)

    result['data_source'] = 'database'
    result['scan_date'] = datetime.now().isoformat()
    result['total_tests_quarantined'] = len(all_tests)
    result['platform_breakdown'] = {
        platform: len(tests)
        for platform, tests in platform_data.items()
    }

    return result


def compare_scores(current: Dict, previous_path: str) -> str:
    """Compare current score with previous score.

    Args:
        current: Current reliability score dict
        previous_path: Path to previous reliability score JSON

    Returns:
        Delta string (e.g., "+0.05" or "-0.03")
    """
    prev_path = Path(previous_path)
    if not prev_path.exists():
        return "N/A (no previous data)"

    try:
        previous = json.loads(prev_path.read_text())
        prev_score = previous.get('overall_score', 0.0)
        curr_score = current.get('overall_score', 0.0)
        delta = curr_score - prev_score

        if delta > 0:
            return f"+{delta:.3f}"
        elif delta < 0:
            return f"{delta:.3f}"
        else:
            return "0.000 (no change)"
    except (json.JSONDecodeError, IOError):
        return "N/A (error reading previous data)"


def get_least_reliable_tests(all_flaky_tests: List[Dict], limit: int = 10) -> List[Dict]:
    """Get least reliable tests sorted by flaky rate.

    Args:
        all_flaky_tests: List of all flaky test dicts
        limit: Maximum number of tests to return

    Returns:
        List of least reliable test dicts with reliability field added
    """
    # Sort by flaky rate (descending)
    sorted_tests = sorted(
        all_flaky_tests,
        key=lambda t: t.get('flaky_rate', 0.0),
        reverse=True
    )

    # Add reliability field and limit
    result = []
    for test in sorted_tests[:limit]:
        flaky_rate = test.get('flaky_rate', 0.0)
        reliability = calculate_reliability_score(flaky_rate)
        test['reliability'] = reliability
        result.append({
            'test_path': test.get('test_path', 'unknown'),
            'platform': test.get('platform', 'unknown'),
            'flaky_rate': flaky_rate,
            'reliability': reliability
        })

    return result


def generate_markdown_report(reliability_data: Dict) -> str:
    """Generate markdown report from reliability data.

    Args:
        reliability_data: Reliability score dict from aggregate_platform_scores

    Returns:
        Markdown formatted string
    """
    lines = [
        "# Test Reliability Report",
        f"Generated: {reliability_data.get('scan_date', datetime.now().isoformat())}",
        "",
        "## Overall Score",
        f"**{reliability_data.get('overall_score', 0.0):.3f}** / 1.0",
        ""
    ]

    # Add score change if available
    if 'score_change' in reliability_data:
        change = reliability_data['score_change']
        if change.startswith('+'):
            lines.append(f"*{change}* (improvement) 📈")
        elif change.startswith('-'):
            lines.append(f"*{change}* (regression) 📉")
        else:
            lines.append(f"*{change}*")
        lines.append("")

    # Platform breakdown
    lines.append("## Platform Scores")
    lines.append("| Platform | Score | Weight |")
    lines.append("|----------|-------|--------|")

    weights = reliability_data.get('weights_used', {})
    platform_scores = reliability_data.get('platform_scores', {})

    for platform in ['backend', 'frontend', 'mobile', 'desktop']:
        score = platform_scores.get(platform, 0.0)
        weight = weights.get(platform, 0.0)
        lines.append(f"| {platform.upper()} | {score:.3f} | {weight:.0%} |")

    lines.append("")

    # Platform breakdown counts
    if 'platform_breakdown' in reliability_data:
        lines.append("## Tests Quarantined")
        lines.append("| Platform | Count |")
        lines.append("|----------|-------|")

        breakdown = reliability_data['platform_breakdown']
        for platform in ['backend', 'frontend', 'mobile', 'desktop']:
            count = breakdown.get(platform, 0)
            lines.append(f"| {platform.upper()} | {count} |")

        lines.append("")

    # Least reliable tests
    if 'least_reliable_tests' in reliability_data:
        lines.append("## Least Reliable Tests (Top 10)")
        lines.append("| Test Path | Platform | Flaky Rate | Reliability |")
        lines.append("|-----------|----------|------------|-------------|")

        for test in reliability_data['least_reliable_tests'][:10]:
            test_path = test.get('test_path', 'unknown')
            platform = test.get('platform', 'unknown')
            flaky_rate = test.get('flaky_rate', 0.0)
            reliability = test.get('reliability', 0.0)
            lines.append(f"| {test_path} | {platform} | {flaky_rate:.3f} | {reliability:.3f} |")

        lines.append("")

    # Metadata
    if 'metadata' in reliability_data:
        lines.append("## Metadata")
        metadata = reliability_data['metadata']
        for key, value in metadata.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # Data source
    lines.append(f"*Data source: {reliability_data.get('data_source', 'unknown')}*")

    return "\n".join(lines)


def main():
    """Main entry point for reliability scorer."""
    parser = argparse.ArgumentParser(
        description="Calculate cross-platform test reliability scores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From JSON files
  python reliability_scorer.py \\
    --backend-flaky backend_flaky_tests.json \\
    --frontend-flaky frontend_flaky_tests.json \\
    --output reliability_score.json

  # From database
  python reliability_scorer.py \\
    --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \\
    --output reliability_score.json

  # With historical comparison
  python reliability_scorer.py \\
    --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \\
    --compare-with previous_reliability.json \\
    --output reliability_score.json
        """
    )

    # Input sources
    parser.add_argument(
        "--backend-flaky",
        help="Backend flaky tests JSON path"
    )
    parser.add_argument(
        "--frontend-flaky",
        help="Frontend flaky tests JSON path"
    )
    parser.add_argument(
        "--mobile-flaky",
        help="Mobile flaky tests JSON path"
    )
    parser.add_argument(
        "--desktop-flaky",
        help="Desktop flaky tests JSON path"
    )
    parser.add_argument(
        "--quarantine-db",
        type=str,
        help="Path to flaky_tests.db (alternative to JSON files)"
    )

    parser.add_argument(
        "--compare-with",
        help="Previous reliability score JSON for comparison"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path"
    )

    parser.add_argument(
        "--summary",
        help="Output markdown report file path"
    )

    args = parser.parse_args()

    # Determine if using database or JSON files
    using_database = args.quarantine_db is not None
    using_json_files = any([
        args.backend_flaky,
        args.frontend_flaky,
        args.mobile_flaky,
        args.desktop_flaky
    ])

    if using_database and using_json_files:
        print("ERROR: Cannot use --quarantine-db and --*-flaky flags together")
        sys.exit(2)

    # Load flaky test data
    if using_database:
        # Load from database
        result = calculate_score_from_db(Path(args.quarantine_db))
        all_tests = []
        for platform in ["backend", "frontend", "mobile", "desktop"]:
            all_tests.extend(load_from_database(Path(args.quarantine_db), platform))
    else:
        # Load from JSON files
        platform_data = {}
        all_tests = []

        if args.backend_flaky:
            backend_tests = load_flaky_data(args.backend_flaky, "backend")
            platform_data["backend"] = backend_tests
            all_tests.extend(backend_tests)

        if args.frontend_flaky:
            frontend_tests = load_flaky_data(args.frontend_flaky, "frontend")
            platform_data["frontend"] = frontend_tests
            all_tests.extend(frontend_tests)

        if args.mobile_flaky:
            mobile_tests = load_flaky_data(args.mobile_flaky, "mobile")
            platform_data["mobile"] = mobile_tests
            all_tests.extend(mobile_tests)

        if args.desktop_flaky:
            desktop_tests = load_flaky_data(args.desktop_flaky, "desktop")
            platform_data["desktop"] = desktop_tests
            all_tests.extend(desktop_tests)

        # Fill missing platforms with empty lists
        for platform in ["backend", "frontend", "mobile", "desktop"]:
            if platform not in platform_data:
                platform_data[platform] = []

        # Calculate scores
        result = aggregate_platform_scores(platform_data)

        # Add metadata
        result['data_source'] = 'json_files'
        result['scan_date'] = datetime.now().isoformat()
        result['total_tests_quarantined'] = len(all_tests)
        result['platform_breakdown'] = {
            platform: len(tests)
            for platform, tests in platform_data.items()
        }

    # Add least reliable tests
    if all_tests:
        result['least_reliable_tests'] = get_least_reliable_tests(all_tests, limit=10)

    # Add score change if comparison requested
    if args.compare_with:
        result['score_change'] = compare_scores(result, args.compare_with)

    # Add metadata
    result['metadata'] = {
        'detection_runs': 10,  # Default from flaky_test_detector.py
        'flaky_threshold': 0.3,
        'min_runs_for_classification': 3
    }

    # Write JSON output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2))

    # Write markdown summary if requested
    if args.summary:
        summary = generate_markdown_report(result)
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary)

    # Print summary to console
    overall_score = result.get('overall_score', 0.0)
    total_quarantined = result.get('total_tests_quarantined', 0)
    print(f"Reliability Score: {overall_score:.3f} / 1.0")
    print(f"Tests Quarantined: {total_quarantined}")

    if 'score_change' in result:
        print(f"Change: {result['score_change']}")

    # Exit with warning if reliability < 0.80
    if overall_score < 0.80:
        print("WARNING: Reliability score below 0.80 threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()
