"""
BugDeduplicator service for cross-method bug deduplication.

This module provides the BugDeduplicator that extends the
CrashDeduplicator pattern (Phase 239) to deduplicate bugs
across all discovery methods using error signature hashing.
"""

from typing import List, Dict, Set

# Add backend to path for imports
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport


class BugDeduplicator:
    """
    Deduplicate bugs across all discovery methods using error signature hashing.

    Extends CrashDeduplicator pattern (Phase 239) to support all bug types:
    - Fuzzing crashes (stack trace hashing)
    - Chaos resilience failures (metric signature hashing)
    - Property test failures (test name + error message hashing)
    - Browser bugs (bug type + URL + error hashing)

    Bugs are deduplicated by error_signature (SHA256 hash). When duplicates
    are found, metadata tracks which discovery methods found the same bug
    and the total duplicate count.
    """

    def deduplicate_bugs(self, bug_reports: List[BugReport]) -> List[BugReport]:
        """
        Deduplicate bugs by error signature across all discovery methods.

        Args:
            bug_reports: List of BugReport objects from all discovery methods

        Returns:
            List of unique BugReport objects (one per error signature)
        """
        unique_bugs: Dict[str, BugReport] = {}
        duplicate_counts: Dict[str, int] = {}
        discovery_methods: Dict[str, Set[str]] = {}

        for bug in bug_reports:
            signature = bug.error_signature

            # Track first occurrence
            if signature not in unique_bugs:
                unique_bugs[signature] = bug
                duplicate_counts[signature] = 1
                discovery_methods[signature] = {bug.discovery_method.value}
            else:
                # Increment duplicate count
                duplicate_counts[signature] += 1

                # Track which discovery methods found this bug
                discovery_methods[signature].add(bug.discovery_method.value)

                # Merge metadata if different discovery methods found same bug
                existing_bug = unique_bugs[signature]

                # Update discovery_methods in metadata
                methods_list = list(discovery_methods[signature])
                existing_bug.metadata["discovery_methods"] = methods_list

                # Update severity to max of duplicates (critical > high > medium > low)
                existing_bug.severity = self._max_severity(existing_bug.severity, bug.severity)

        # Update unique bugs with duplicate counts
        for bug in unique_bugs.values():
            bug.duplicate_count = duplicate_counts[bug.error_signature]

            # Add discovery methods count to metadata
            if "discovery_methods" in bug.metadata:
                bug.metadata["discovery_method_count"] = len(bug.metadata["discovery_methods"])

        return list(unique_bugs.values())

    def _max_severity(self, severity1: str, severity2: str) -> str:
        """
        Return the maximum severity between two values.

        Args:
            severity1: First severity value
            severity2: Second severity value

        Returns:
            Maximum severity (critical > high > medium > low)
        """
        severity_order = ["low", "medium", "high", "critical"]
        try:
            idx1 = severity_order.index(severity1)
            idx2 = severity_order.index(severity2)
            return severity_order[max(idx1, idx2)]
        except ValueError:
            return severity1  # Default to first if invalid

    def get_duplicate_groups(self, bug_reports: List[BugReport]) -> Dict[str, List[BugReport]]:
        """
        Group bugs by error signature to see duplicates.

        Args:
            bug_reports: List of BugReport objects

        Returns:
            Dict mapping error_signature to list of BugReport objects
        """
        groups: Dict[str, List[BugReport]] = {}

        for bug in bug_reports:
            signature = bug.error_signature
            if signature not in groups:
                groups[signature] = []
            groups[signature].append(bug)

        return groups

    def get_cross_method_bugs(self, bug_reports: List[BugReport]) -> List[BugReport]:
        """
        Get bugs found by multiple discovery methods.

        Args:
            bug_reports: List of BugReport objects (after deduplication)

        Returns:
            List of bugs with discovery_method_count > 1
        """
        cross_method_bugs = []

        for bug in bug_reports:
            method_count = bug.metadata.get("discovery_method_count", 1)
            if method_count > 1:
                cross_method_bugs.append(bug)

        return cross_method_bugs
