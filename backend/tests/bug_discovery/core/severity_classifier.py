"""
SeverityClassifier service for rule-based bug severity classification.

This module provides the SeverityClassifier that centralizes the
severity classification logic from BugFilingService._determine_severity()
and extends it to support all discovery methods with consistent rules.
"""

from typing import Dict, Any

# Add backend to path for imports
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, Severity, DiscoveryMethod


class SeverityClassifier:
    """
    Classify bug severity using rule-based heuristics.

    Extends BugFilingService._determine_severity() logic (Phase 236)
    to support all discovery methods with consistent severity rules.

    Severity levels:
    - CRITICAL: Security vulnerabilities, data corruption, crashes
    - HIGH: Resilience failures, memory leaks, network failures, security invariant violations
    - MEDIUM: WCAG violations, database invariant violations, property test failures
    - LOW: Broken links, visual issues, usability problems
    """

    # Severity keywords for error message analysis
    CRITICAL_KEYWORDS = [
        "sql injection", "xss", "csrf", "security", "vulnerability",
        "data corruption", "data loss", "crash", "overflow", "underflow",
        "authentication", "authorization", "bypass"
    ]

    HIGH_KEYWORDS = [
        "resilience failure", "memory leak", "connection", "timeout",
        "network", "database", "retry", "exhausted", "oom", "out of memory"
    ]

    MEDIUM_KEYWORDS = [
        "accessibility", "wcag", "aria", "invariant", "property",
        "assertion", "validation", "consistency"
    ]

    def classify(self, bug: BugReport) -> Severity:
        """
        Classify bug severity based on discovery method and impact.

        Args:
            bug: BugReport object

        Returns:
            Severity level (critical/high/medium/low)
        """
        # Check for critical keywords first (highest priority)
        if self._has_keywords(bug.error_message, self.CRITICAL_KEYWORDS):
            return Severity.CRITICAL

        # Classify by discovery method
        if bug.discovery_method == DiscoveryMethod.FUZZING:
            # Fuzzing crashes are critical (potential security vulnerabilities)
            return Severity.CRITICAL

        if bug.discovery_method == DiscoveryMethod.CHAOS:
            # Resilience failures are high (system instability)
            return Severity.HIGH

        if bug.discovery_method == DiscoveryMethod.PROPERTY:
            # Property test failures: Check if invariant is critical
            return self._classify_property_test(bug)

        if bug.discovery_method == DiscoveryMethod.BROWSER:
            # Browser bugs: Check bug type
            return self._classify_browser_bug(bug)

        # Default to low severity
        return Severity.LOW

    def _classify_property_test(self, bug: BugReport) -> Severity:
        """
        Classify property test failure severity.

        Args:
            bug: BugReport object

        Returns:
            Severity level
        """
        test_name_lower = bug.test_name.lower()

        # Security invariant violations are critical
        if "security" in test_name_lower or "auth" in test_name_lower:
            return Severity.CRITICAL

        # Database/transaction invariant violations are high (data corruption risk)
        if any(keyword in test_name_lower for keyword in ["database", "transaction", "persistence", "storage"]):
            return Severity.HIGH

        # Check for high keywords
        if self._has_keywords(bug.error_message, self.HIGH_KEYWORDS):
            return Severity.HIGH

        # Check for medium keywords
        if self._has_keywords(bug.error_message, self.MEDIUM_KEYWORDS):
            return Severity.MEDIUM

        # Other invariant violations are medium
        return Severity.MEDIUM

    def _classify_browser_bug(self, bug: BugReport) -> Severity:
        """
        Classify browser bug severity.

        Args:
            bug: BugReport object

        Returns:
            Severity level
        """
        bug_type = bug.metadata.get("bug_type", "").lower()

        # Console errors are high (JavaScript crashes)
        if "console_error" in bug_type or "error" in bug_type:
            return Severity.HIGH

        # Accessibility violations are medium (WCAG compliance)
        if "accessibility" in bug_type or "a11y" in bug_type:
            return Severity.MEDIUM

        # Broken links and visual issues are low
        return Severity.LOW

    def _has_keywords(self, text: str, keywords: list) -> bool:
        """
        Check if text contains any of the given keywords.

        Args:
            text: Text to search
            keywords: List of keywords to search for

        Returns:
            True if any keyword found (case-insensitive)
        """
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)

    def batch_classify(self, bugs: list) -> list:
        """
        Classify severity for a batch of bugs.

        Args:
            bugs: List of BugReport objects

        Returns:
            List of bugs with severity set
        """
        for bug in bugs:
            bug.severity = self.classify(bug)

        return bugs
