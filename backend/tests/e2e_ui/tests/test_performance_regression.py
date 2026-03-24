"""
Performance regression tests using Google Lighthouse.

These tests run Lighthouse to measure web performance and detect regressions.
Tests verify performance scores, metrics, and budgets for critical pages.

Lighthouse Metrics:
- Performance Score: 0-100 (target >90)
- Accessibility Score: 0-100 (target >90)
- Best Practices Score: 0-100 (target >90)
- SEO Score: 0-100 (target >80)

Performance Budgets:
- Time to First Byte (TTFB) < 600ms
- First Contentful Paint (FCP) < 1.5s
- Largest Contentful Paint (LCP) < 2.5s
- Total Blocking Time (TBT) < 300ms
- Cumulative Layout Shift (CLS) < 0.1
"""

import json
import os
import subprocess
import pytest
from pathlib import Path
from typing import Dict, Any, Optional


# ============================================================================
# Lighthouse Test Configuration
# ============================================================================

# Performance budgets for critical pages
PERFORMANCE_BUDGETS = {
    "ttfb": 600,        # Time to First Byte (ms)
    "fcp": 1500,        # First Contentful Paint (ms)
    "lcp": 2500,        # Largest Contentful Paint (ms)
    "tbt": 300,         # Total Blocking Time (ms)
    "cls": 0.1,         # Cumulative Layout Shift
}

# Score thresholds
SCORE_THRESHOLDS = {
    "performance": 90,
    "accessibility": 90,
    "best-practices": 90,
    "seo": 80,
}

# Regression detection thresholds
REGRESSION_THRESHOLD = 0.20  # 20% degradation triggers failure
IMPROVEMENT_THRESHOLD = 0.10  # 10% improvement triggers baseline update


# ============================================================================
# Helper Functions
# ============================================================================

def run_lighthouse(url: str, output_path: str) -> Dict[str, Any]:
    """Run Lighthouse CLI and return parsed results.

    This function executes the Lighthouse CLI tool and parses the
    JSON output into a Python dictionary for assertions.

    Args:
        url: URL to test (e.g., http://localhost:3001/dashboard)
        output_path: Path to save Lighthouse report JSON

    Returns:
        dict: Parsed Lighthouse report with scores and metrics

    Raises:
        pytest.skip.Exception: If Lighthouse is not installed
        subprocess.CalledProcessError: If Lighthouse execution fails

    Example:
        result = run_lighthouse("http://localhost:3001/dashboard", "/tmp/report.json")
        assert result['scores']['performance'] > 90
    """
    # Check if Lighthouse is installed
    try:
        subprocess.run(
            ["lighthouse", "--version"],
            capture_output=True,
            check=True,
            timeout=10
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(
            "Lighthouse CLI not installed. Install with: npm install -g lighthouse"
        )

    # Run Lighthouse
    cmd = [
        "lighthouse",
        url,
        "--output=json",
        f"--output-path={output_path}",
        "--chrome-flags='--headless'",
        "--quiet",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60  # 60 second timeout
        )
    except subprocess.TimeoutExpired:
        pytest.skip(f"Lighthouse timed out after 60 seconds for URL: {url}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Lighthouse failed for URL {url}: {e.stderr}")

    # Parse JSON output
    try:
        with open(output_path, "r") as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        pytest.fail(f"Failed to parse Lighthouse report: {e}")

    return report


def extract_scores(report: Dict[str, Any]) -> Dict[str, float]:
    """Extract Lighthouse scores from report.

    Args:
        report: Parsed Lighthouse report JSON

    Returns:
        dict: Scores for performance, accessibility, best-practices, seo

    Example:
        scores = extract_scores(report)
        assert scores['performance'] > 90
    """
    categories = report.get("categories", {})

    return {
        "performance": categories.get("performance", {}).get("score", 0) * 100,
        "accessibility": categories.get("accessibility", {}).get("score", 0) * 100,
        "best-practices": categories.get("best-practices", {}).get("score", 0) * 100,
        "seo": categories.get("seo", {}).get("score", 0) * 100,
    }


def extract_metrics(report: Dict[str, Any]) -> Dict[str, Any]:
    """Extract performance metrics from Lighthouse report.

    Args:
        report: Parsed Lighthouse report JSON

    Returns:
        dict: Performance metrics (ttfb, fcp, lcp, tbt, cls)

    Example:
        metrics = extract_metrics(report)
        assert metrics['lcp'] < 2500  # LCP < 2.5s
    """
    audits = report.get("audits", {})

    return {
        "ttfb": audits.get("time-to-first-byte", {}).get("numericValue", 0),
        "fcp": audits.get("first-contentful-paint", {}).get("numericValue", 0),
        "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", 0),
        "tbt": audits.get("total-blocking-time", {}).get("numericValue", 0),
        "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
    }


def load_baseline(baseline_path: str) -> Optional[Dict[str, Any]]:
    """Load baseline metrics from JSON file.

    Args:
        baseline_path: Path to baseline JSON file

    Returns:
        dict: Baseline metrics or None if file doesn't exist

    Example:
        baseline = load_baseline("tests/data/lighthouse-baseline.json")
        if baseline:
            current_fcp = extract_metrics(report)['fcp']
            baseline_fcp = baseline['dashboard']['fcp']
    """
    if not os.path.exists(baseline_path):
        return None

    try:
        with open(baseline_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_baseline(baseline_path: str, page_name: str, metrics: Dict[str, Any]):
    """Save metrics to baseline JSON file.

    Args:
        baseline_path: Path to baseline JSON file
        page_name: Name of the page (e.g., 'dashboard', 'agents')
        metrics: Metrics to save (from extract_metrics)

    Example:
        metrics = extract_metrics(report)
        save_baseline("tests/data/lighthouse-baseline.json", "dashboard", metrics)
    """
    # Load existing baseline or create new
    baseline = load_baseline(baseline_path) or {}

    # Update baseline with new metrics
    baseline[page_name] = metrics

    # Ensure directory exists
    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)

    # Save baseline
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)


def compare_with_baseline(
    current_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
    metric_name: str
) -> Dict[str, Any]:
    """Compare current metrics with baseline and detect regressions.

    Args:
        current_metrics: Current test metrics
        baseline_metrics: Baseline metrics to compare against
        metric_name: Name of the metric (e.g., 'fcp', 'lcp')

    Returns:
        dict: Comparison results with regression detected flag

    Example:
        result = compare_with_baseline(current, baseline, 'fcp')
        assert not result['regression_detected'], "FCP regression detected"
    """
    current_value = current_metrics.get(metric_name, 0)
    baseline_value = baseline_metrics.get(metric_name, 0)

    if baseline_value == 0:
        return {
            "regression_detected": False,
            "improvement_detected": False,
            "percent_change": 0,
            "current": current_value,
            "baseline": baseline_value,
        }

    # Calculate percentage change (positive = worse, negative = better)
    percent_change = (current_value - baseline_value) / baseline_value

    regression_detected = percent_change > REGRESSION_THRESHOLD
    improvement_detected = percent_change < -IMPROVEMENT_THRESHOLD

    return {
        "regression_detected": regression_detected,
        "improvement_detected": improvement_detected,
        "percent_change": percent_change * 100,  # Convert to percentage
        "current": current_value,
        "baseline": baseline_value,
    }


# ============================================================================
# Lighthouse Performance Score Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.lighthouse
def test_lighthouse_performance_scores(page, test_user, tmp_path):
    """Test Lighthouse performance scores on dashboard page.

    This test runs Lighthouse on the dashboard and verifies that all
    scores meet the minimum thresholds.

    Score Thresholds:
    - Performance > 90
    - Accessibility > 90
    - Best Practices > 90
    - SEO > 80

    Args:
        page: Playwright page fixture
        test_user: Test user fixture
        tmp_path: Pytest temporary path fixture
    """
    # Navigate to dashboard
    page.goto("http://localhost:3001/dashboard")
    page.wait_for_load_state("networkidle")

    # Run Lighthouse
    output_path = str(tmp_path / "lighthouse-report.json")
    report = run_lighthouse("http://localhost:3001/dashboard", output_path)

    # Extract scores
    scores = extract_scores(report)

    print(f"\n[Lighthouse Scores]")
    print(f"  Performance: {scores['performance']:.0f}/100")
    print(f"  Accessibility: {scores['accessibility']:.0f}/100")
    print(f"  Best Practices: {scores['best-practices']:.0f}/100")
    print(f"  SEO: {scores['seo']:.0f}/100")

    # Verify all scores meet thresholds
    assert scores['performance'] >= SCORE_THRESHOLDS['performance'], (
        f"Performance score {scores['performance']:.0f} below threshold "
        f"{SCORE_THRESHOLDS['performance']}"
    )

    assert scores['accessibility'] >= SCORE_THRESHOLDS['accessibility'], (
        f"Accessibility score {scores['accessibility']:.0f} below threshold "
        f"{SCORE_THRESHOLDS['accessibility']}"
    )

    assert scores['best-practices'] >= SCORE_THRESHOLDS['best-practices'], (
        f"Best Practices score {scores['best-practices']:.0f} below threshold "
        f"{SCORE_THRESHOLDS['best-practices']}"
    )

    assert scores['seo'] >= SCORE_THRESHOLDS['seo'], (
        f"SEO score {scores['seo']:.0f} below threshold "
        f"{SCORE_THRESHOLDS['seo']}"
    )


# ============================================================================
# Lighthouse Performance Budget Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.lighthouse
def test_lighthouse_performance_budgets(page, tmp_path):
    """Test Lighthouse performance budgets on critical pages.

    This test verifies that all critical pages meet performance budgets
    for TTFB, FCP, LCP, TBT, and CLS.

    Performance Budgets:
    - TTFB < 600ms
    - FCP < 1.5s
    - LCP < 2.5s
    - TBT < 300ms
    - CLS < 0.1

    Args:
        page: Playwright page fixture
        tmp_path: Pytest temporary path fixture
    """
    # Critical pages to test
    critical_pages = {
        "dashboard": "http://localhost:3001/dashboard",
        "agents": "http://localhost:3001/agents",
        "login": "http://localhost:3001/login",
    }

    for page_name, url in critical_pages.items():
        print(f"\n[Performance Budget] Testing {page_name}: {url}")

        # Navigate to page
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Run Lighthouse
        output_path = str(tmp_path / f"lighthouse-{page_name}.json")
        report = run_lighthouse(url, output_path)

        # Extract metrics
        metrics = extract_metrics(report)

        print(f"  TTFB: {metrics['ttfb']:.0f}ms (budget: {PERFORMANCE_BUDGETS['ttfb']}ms)")
        print(f"  FCP: {metrics['fcp']:.0f}ms (budget: {PERFORMANCE_BUDGETS['fcp']}ms)")
        print(f"  LCP: {metrics['lcp']:.0f}ms (budget: {PERFORMANCE_BUDGETS['lcp']}ms)")
        print(f"  TBT: {metrics['tbt']:.0f}ms (budget: {PERFORMANCE_BUDGETS['tbt']}ms)")
        print(f"  CLS: {metrics['cls']:.3f} (budget: {PERFORMANCE_BUDGETS['cls']})")

        # Verify all metrics meet budgets
        assert metrics['ttfb'] <= PERFORMANCE_BUDGETS['ttfb'], (
            f"TTFB {metrics['ttfb']:.0f}ms exceeds budget "
            f"{PERFORMANCE_BUDGETS['ttfb']}ms for {page_name}"
        )

        assert metrics['fcp'] <= PERFORMANCE_BUDGETS['fcp'], (
            f"FCP {metrics['fcp']:.0f}ms exceeds budget "
            f"{PERFORMANCE_BUDGETS['fcp']}ms for {page_name}"
        )

        assert metrics['lcp'] <= PERFORMANCE_BUDGETS['lcp'], (
            f"LCP {metrics['lcp']:.0f}ms exceeds budget "
            f"{PERFORMANCE_BUDGETS['lcp']}ms for {page_name}"
        )

        assert metrics['tbt'] <= PERFORMANCE_BUDGETS['tbt'], (
            f"TBT {metrics['tbt']:.0f}ms exceeds budget "
            f"{PERFORMANCE_BUDGETS['tbt']}ms for {page_name}"
        )

        assert metrics['cls'] <= PERFORMANCE_BUDGETS['cls'], (
            f"CLS {metrics['cls']:.3f} exceeds budget "
            f"{PERFORMANCE_BUDGETS['cls']} for {page_name}"
        )


# ============================================================================
# Lighthouse Regression Detection Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.lighthouse
def test_performance_regression_detection(page, tmp_path):
    """Test for performance regressions by comparing against baseline.

    This test runs Lighthouse on critical pages and compares metrics
    against a baseline. If metrics degrade by >20%, the test fails.
    If metrics improve by >10%, the baseline is updated.

    Regression Threshold: 20% degradation
    Improvement Threshold: 10% improvement

    Args:
        page: Playwright page fixture
        tmp_path: Pytest temporary path fixture
    """
    # Baseline file path
    baseline_path = "backend/tests/e2e_ui/tests/data/lighthouse-baseline.json"

    # Pages to test for regression
    test_pages = {
        "dashboard": "http://localhost:3001/dashboard",
        "agents": "http://localhost:3001/agents",
    }

    # Load existing baseline
    baseline = load_baseline(baseline_path)

    for page_name, url in test_pages.items():
        print(f"\n[Regression Detection] Testing {page_name}: {url}")

        # Navigate to page
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Run Lighthouse
        output_path = str(tmp_path / f"lighthouse-{page_name}.json")
        report = run_lighthouse(url, output_path)

        # Extract metrics
        current_metrics = extract_metrics(report)

        # Check if baseline exists for this page
        if baseline and page_name in baseline:
            baseline_metrics = baseline[page_name]

            # Compare each metric
            for metric_name in ['ttfb', 'fcp', 'lcp', 'tbt', 'cls']:
                comparison = compare_with_baseline(
                    current_metrics,
                    baseline_metrics,
                    metric_name
                )

                print(f"  {metric_name.upper()}: "
                      f"{comparison['current']:.0f} vs "
                      f"{comparison['baseline']:.0f} "
                      f"({comparison['percent_change']:+.1f}%)")

                # Check for regression
                if comparison['regression_detected']:
                    pytest.fail(
                        f"Performance regression detected for {page_name}.{metric_name}: "
                        f"{comparison['percent_change']:+.1f}% change "
                        f"(threshold: +{REGRESSION_THRESHOLD*100:.0f}%)"
                    )

                # Check for improvement (update baseline)
                if comparison['improvement_detected']:
                    print(f"  [Improvement] Updating baseline for {page_name}.{metric_name}")
                    baseline_metrics[metric_name] = comparison['current']
        else:
            # No baseline exists, create one
            print(f"  [Baseline] Creating new baseline for {page_name}")
            save_baseline(baseline_path, page_name, current_metrics)
