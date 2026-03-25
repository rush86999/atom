"""
Unit tests for BugDeduplicator service.

Tests cross-method bug deduplication using error signature hashing.
"""

import pytest

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity, generate_error_signature
from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator


class TestBugDeduplicator:
    """Test BugDeduplicator deduplication logic."""

    def test_deduplicate_bugs_no_duplicates(self):
        """Test deduplication with no duplicate bugs."""
        deduplicator = BugDeduplicator()

        bug1 = BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="test1",
            error_message="Error 1",
            error_signature=generate_error_signature("error1")
        )
        bug2 = BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="test2",
            error_message="Error 2",
            error_signature=generate_error_signature("error2")
        )

        unique_bugs = deduplicator.deduplicate_bugs([bug1, bug2])

        assert len(unique_bugs) == 2
        assert all(b.duplicate_count == 1 for b in unique_bugs)

    def test_deduplicate_bugs_with_duplicates(self):
        """Test deduplication merges duplicate bugs by error signature."""
        deduplicator = BugDeduplicator()

        signature = generate_error_signature("same_error")

        bug1 = BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="test1",
            error_message="Same error",
            error_signature=signature
        )
        bug2 = BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="test2",
            error_message="Same error",
            error_signature=signature
        )

        unique_bugs = deduplicator.deduplicate_bugs([bug1, bug2])

        assert len(unique_bugs) == 1
        assert unique_bugs[0].duplicate_count == 2
        assert unique_bugs[0].metadata["discovery_method_count"] == 2

    def test_deduplicate_bugs_severity_upgrade(self):
        """Test deduplication upgrades to max severity."""
        deduplicator = BugDeduplicator()

        signature = generate_error_signature("error")

        bug_low = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test",
            error_message="Error",
            error_signature=signature,
            severity=Severity.LOW
        )
        bug_critical = BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="test",
            error_message="Error",
            error_signature=signature,
            severity=Severity.CRITICAL
        )

        unique_bugs = deduplicator.deduplicate_bugs([bug_low, bug_critical])

        assert len(unique_bugs) == 1
        assert unique_bugs[0].severity == Severity.CRITICAL

    def test_get_duplicate_groups(self):
        """Test getting duplicate groups."""
        deduplicator = BugDeduplicator()

        signature1 = generate_error_signature("error1")
        signature2 = generate_error_signature("error2")

        bugs = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test1",
                error_message="Error 1",
                error_signature=signature1
            ),
            BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name="test1",
                error_message="Error 1",
                error_signature=signature1
            ),
            BugReport(
                discovery_method=DiscoveryMethod.PROPERTY,
                test_name="test2",
                error_message="Error 2",
                error_signature=signature2
            )
        ]

        groups = deduplicator.get_duplicate_groups(bugs)

        assert len(groups) == 2
        assert len(groups[signature1]) == 2
        assert len(groups[signature2]) == 1

    def test_get_cross_method_bugs(self):
        """Test getting bugs found by multiple discovery methods."""
        deduplicator = BugDeduplicator()

        signature = generate_error_signature("cross_method_bug")

        bugs = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test",
                error_message="Error",
                error_signature=signature
            ),
            BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name="test",
                error_message="Error",
                error_signature=signature
            )
        ]

        # Deduplicate first
        unique_bugs = deduplicator.deduplicate_bugs(bugs)

        # Get cross-method bugs
        cross_method = deduplicator.get_cross_method_bugs(unique_bugs)

        assert len(cross_method) == 1
        assert cross_method[0].metadata["discovery_method_count"] == 2

    def test_get_cross_method_bugs_single_method(self):
        """Test getting cross-method bugs when none exist."""
        deduplicator = BugDeduplicator()

        bugs = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test",
                error_message="Error",
                error_signature=generate_error_signature("unique")
            )
        ]

        cross_method = deduplicator.get_cross_method_bugs(bugs)

        assert len(cross_method) == 0
