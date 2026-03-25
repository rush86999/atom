"""
Unit tests for SeverityClassifier service.

Tests rule-based severity classification for all discovery methods.
"""

import pytest

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity
from tests.bug_discovery.core.severity_classifier import SeverityClassifier


class TestSeverityClassifier:
    """Test SeverityClassifier rule-based classification."""

    def test_classify_fuzzing_crash_critical(self):
        """Test fuzzing crashes are classified as CRITICAL."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="fuzzing_api_v1_agents",
            error_message="Stack overflow detected",
            error_signature="sig123"
        )

        severity = classifier.classify(bug)

        assert severity == Severity.CRITICAL

    def test_classify_chaos_failure_high(self):
        """Test chaos resilience failures are classified as HIGH."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="network_latency_3g",
            error_message="Resilience failure: system did not recover",
            error_signature="sig456"
        )

        severity = classifier.classify(bug)

        assert severity == Severity.HIGH

    def test_classify_property_security_invariant_critical(self):
        """Test property test security invariant violations are CRITICAL."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_security_invariant",
            error_message="SQL injection vulnerability detected",
            error_signature="sig789"
        )

        severity = classifier.classify(bug)

        assert severity == Severity.CRITICAL

    def test_classify_property_database_invariant_high(self):
        """Test property test database invariant violations are HIGH."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_database_consistency",
            error_message="Transaction isolation violated",
            error_signature="sig101"
        )

        severity = classifier.classify(bug)

        assert severity == Severity.HIGH

    def test_classify_property_standard_invariant_medium(self):
        """Test standard property test invariant violations are MEDIUM."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_cache_consistency",
            error_message="Cache consistency invariant violated",
            error_signature="sig202"
        )

        severity = classifier.classify(bug)

        assert severity == Severity.MEDIUM

    def test_classify_browser_console_error_high(self):
        """Test browser console errors are classified as HIGH."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="browser_console_error",
            error_message="Uncaught TypeError",
            error_signature="sig303",
            metadata={"bug_type": "console_error"}
        )

        severity = classifier.classify(bug)

        assert severity == Severity.HIGH

    def test_classify_browser_accessibility_medium(self):
        """Test browser accessibility violations are MEDIUM."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="browser_accessibility",
            error_message="Missing ARIA label",
            error_signature="sig404",
            metadata={"bug_type": "accessibility"}
        )

        severity = classifier.classify(bug)

        assert severity == Severity.MEDIUM

    def test_classify_browser_broken_link_low(self):
        """Test browser broken links are LOW."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="browser_broken_link",
            error_message="404 Not Found",
            error_signature="sig505",
            metadata={"bug_type": "broken_link"}
        )

        severity = classifier.classify(bug)

        assert severity == Severity.LOW

    def test_classify_critical_keywords(self):
        """Test CRITICAL keywords in error message."""
        classifier = SeverityClassifier()

        bug = BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test",
            error_message="SQL injection vulnerability detected",
            error_signature="sig606"
        )

        severity = classifier.classify(bug)

        assert severity == Severity.CRITICAL

    def test_batch_classify(self):
        """Test batch classification of multiple bugs."""
        classifier = SeverityClassifier()

        bugs = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test1",
                error_message="Crash",
                error_signature="sig1"
            ),
            BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name="test2",
                error_message="Resilience failure",
                error_signature="sig2"
            )
        ]

        classified_bugs = classifier.batch_classify(bugs)

        assert classified_bugs[0].severity == Severity.CRITICAL
        assert classified_bugs[1].severity == Severity.HIGH
