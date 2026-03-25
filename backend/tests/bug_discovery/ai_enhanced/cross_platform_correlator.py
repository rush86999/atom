"""CrossPlatformCorrelator: Multi-platform bug correlation service."""
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport
from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator
from tests.bug_discovery.ai_enhanced.models.cross_platform_correlation import (
    CrossPlatformCorrelation, Platform
)


class CrossPlatformCorrelator:
    """
    Correlate bugs across web/mobile/desktop platforms.

    Detects when the same bug manifests on multiple platforms (e.g., auth
    fails on web + mobile → shared API bug) by analyzing error signatures,
    API endpoints, user flows, and temporal patterns.

    Example:
        correlator = CrossPlatformCorrelator()

        # Collect bugs from all platforms
        web_bugs = load_bugs_from_web_tests()
        mobile_bugs = load_bugs_from_mobile_tests()

        # Correlate across platforms
        correlated = correlator.correlate_cross_platform_bugs(
            web_bugs=web_bugs,
            mobile_bugs=mobile_bugs,
            desktop_bugs=[],
            similarity_threshold=0.8
        )

        for correlation in correlated:
            print(f"Same bug on {correlation['platforms']}: {correlation['error_signature']}")
            print(f"  Action: {correlation['suggested_action']}")
    """

    def __init__(self):
        """Initialize CrossPlatformCorrelator."""
        self.bug_deduplicator = BugDeduplicator()

    def correlate_cross_platform_bugs(
        self,
        web_bugs: List[BugReport],
        mobile_bugs: List[BugReport],
        desktop_bugs: List[BugReport] = None,
        similarity_threshold: float = 0.8,
        max_hours_apart: float = 24.0
    ) -> List[CrossPlatformCorrelation]:
        """
        Correlate bugs across platforms by error signature and context.

        Args:
            web_bugs: Bugs from web tests (e2e_ui/)
            mobile_bugs: Bugs from mobile tests (mobile_api/)
            desktop_bugs: Bugs from desktop tests (if available)
            similarity_threshold: Minimum similarity for correlation (0.0-1.0)
            max_hours_apart: Maximum time difference for temporal correlation

        Returns:
            List of CrossPlatformCorrelation objects
        """
        if desktop_bugs is None:
            desktop_bugs = []

        # Group all bugs by platform
        all_bugs = {
            Platform.WEB: web_bugs,
            Platform.MOBILE: mobile_bugs,
            Platform.DESKTOP: desktop_bugs
        }

        # Generate cross-platform error signatures
        cross_platform_signatures = self._generate_cross_platform_signatures(all_bugs)

        # Group bugs by cross-platform signature
        signature_groups = defaultdict(list)
        for bug, signature in cross_platform_signatures:
            signature_groups[signature].append(bug)

        # Filter to multi-platform groups
        correlated = []
        for signature, bugs in signature_groups.items():
            platforms = self._extract_platforms(bugs)

            if len(platforms) > 1:  # Multi-platform bug
                # Calculate similarity score
                similarity = self._calculate_cross_platform_similarity(bugs)

                if similarity >= similarity_threshold:
                    # Create correlation
                    correlation = self._create_correlation(
                        signature=signature,
                        bugs=bugs,
                        platforms=platforms,
                        similarity=similarity,
                        max_hours_apart=max_hours_apart
                    )
                    if correlation:
                        correlated.append(correlation)

        # Sort by number of platforms (descending)
        correlated.sort(key=lambda x: len(x.platforms), reverse=True)

        return correlated

    def _generate_cross_platform_signatures(
        self,
        all_bugs: Dict[Platform, List[BugReport]]
    ) -> List[Tuple[BugReport, str]]:
        """
        Generate cross-platform error signatures (platform-agnostic).

        Strips platform-specific details (file paths, line numbers) to focus
        on semantic error patterns.
        """
        signatures = []

        for platform, bugs in all_bugs.items():
            for bug in bugs:
                # Normalize error message for cross-platform comparison
                normalized_error = self._normalize_error_for_cross_platform(
                    bug.error_message,
                    platform
                )

                # Generate signature from normalized error + API endpoint
                api_endpoint = bug.metadata.get("api_endpoint", "unknown")
                signature_content = f"{normalized_error}|{api_endpoint}"
                signature = hashlib.sha256(signature_content.encode()).hexdigest()

                signatures.append((bug, signature))

        return signatures

    def _normalize_error_for_cross_platform(
        self,
        error_message: str,
        platform: Platform
    ) -> str:
        """
        Normalize error message by removing platform-specific details.

        Examples:
        - "/backend/core/agent_governance_service.py:456" → "agent_governance_service.py"
        - "HTTP 500: Internal Server Error" → "HTTP 500"
        - "File not found: /var/www/html/index.html" → "File not found"
        """
        normalized = error_message

        # Remove file paths completely (platform-specific)
        # Unix-style paths: /path/to/file.py
        normalized = re.sub(r'[a-zA-Z0-9_/\-\.]+\.[a-z]{2,4}:\d+', 'FILE:LINE', normalized)
        normalized = re.sub(r'[a-zA-Z0-9_/\-\.]+\.[a-z]{2,4}', 'FILE', normalized)
        # Windows-style paths
        normalized = re.sub(r'[a-zA-Z0-9_\\\-\.]+\.[a-z]{2,4}:\d+', 'FILE:LINE', normalized)
        normalized = re.sub(r'[a-zA-Z0-9_\\\-\.]+\.[a-z]{2,4}', 'FILE', normalized)

        # Remove remaining path-like patterns
        normalized = re.sub(r'/[a-zA-Z0-9_/\-\.]+/', '/', normalized)
        normalized = re.sub(r'\\+[a-zA-Z0-9_\\\-\.]+\\+', '\\\\', normalized)

        # Remove line numbers
        normalized = re.sub(r':\d+', ':LINE', normalized)

        # Normalize error codes
        replacements = {
            "Internal Server Error": "HTTP 500",
            "Not Found": "HTTP 404",
            "Unauthorized": "HTTP 401",
            "Forbidden": "HTTP 403",
            "Bad Request": "HTTP 400",
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        # Clean up multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized.strip()

    def _extract_platforms(self, bugs: List[BugReport]) -> List[Platform]:
        """Extract platform list from bug metadata."""
        platforms = set()
        for bug in bugs:
            platform_str = bug.metadata.get("platform", "unknown")
            try:
                platforms.add(Platform(platform_str))
            except ValueError:
                # Unknown platform, skip
                pass
        return list(platforms)

    def _calculate_cross_platform_similarity(self, bugs: List[BugReport]) -> float:
        """
        Calculate similarity score for cross-platform bug group.

        Args:
            bugs: List of bugs from different platforms

        Returns:
            Similarity score (0.0-1.0)
        """
        if len(bugs) < 2:
            return 0.0

        # Calculate similarity based on:
        # 1. Error message similarity (Jaccard similarity)
        # 2. API endpoint match (exact match required)
        # 3. Temporal proximity (bugs found within max_hours_apart)

        # Check API endpoint match
        endpoints = set(bug.metadata.get("api_endpoint", "") for bug in bugs)
        endpoint_match = 1.0 if len(endpoints) == 1 else 0.5

        # Calculate error message similarity
        error_messages = [bug.error_message.lower().split() for bug in bugs]
        word_sets = [set(msg) for msg in error_messages]

        # Jaccard similarity: |A ∩ B| / |A ∪ B|
        intersections = []
        unions = []

        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = word_sets[i] & word_sets[j]
                union = word_sets[i] | word_sets[j]
                intersections.append(len(intersection))
                unions.append(len(union) if len(union) > 0 else 1)

        avg_jaccard = sum(intersections) / max(sum(unions), 1)

        # Combine scores
        similarity = (endpoint_match * 0.6) + (avg_jaccard * 0.4)

        return round(similarity, 3)

    def _create_correlation(
        self,
        signature: str,
        bugs: List[BugReport],
        platforms: List[Platform],
        similarity: float,
        max_hours_apart: float
    ) -> Optional[CrossPlatformCorrelation]:
        """Create CrossPlatformCorrelation from bug group."""
        # Extract error messages by platform
        error_messages = {}
        bug_reports = []
        timestamps = []

        for bug in bugs:
            platform_str = bug.metadata.get("platform", "unknown")
            error_messages[platform_str] = bug.error_message
            bug_reports.append(bug.test_name)
            if hasattr(bug, 'timestamp') and bug.timestamp:
                timestamps.append(bug.timestamp)

        # Calculate temporal proximity
        temporal_proximity = None
        if len(timestamps) >= 2:
            # Assuming timestamp is ISO format string or datetime
            try:
                if isinstance(timestamps[0], str):
                    timestamps = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in timestamps]
                time_diff = max(timestamps) - min(timestamps)
                temporal_proximity_hours = time_diff.total_seconds() / 3600
                if temporal_proximity_hours > max_hours_apart:
                    return None  # Too far apart temporally
                temporal_proximity = temporal_proximity_hours
            except:
                pass

        # Determine API endpoint
        api_endpoint = bugs[0].metadata.get("api_endpoint") if bugs else None

        # Generate suggested action
        suggested_action = self._suggest_action(bugs, platforms, api_endpoint)

        # Check if shared root cause
        shared_root_cause = api_endpoint is not None and api_endpoint.startswith("/api/")

        return CrossPlatformCorrelation(
            correlation_id=signature[:16],  # First 16 chars of signature
            platforms=platforms,
            similarity_score=similarity,
            error_signature=signature,
            api_endpoint=api_endpoint,
            error_messages=error_messages,
            bug_reports=bug_reports,
            suggested_action=suggested_action,
            shared_root_cause=shared_root_cause,
            timestamp=datetime.utcnow().isoformat(),
            temporal_proximity_hours=temporal_proximity
        )

    def _suggest_action(
        self,
        bugs: List[BugReport],
        platforms: List[Platform],
        api_endpoint: Optional[str]
    ) -> str:
        """Suggest remediation action for cross-platform bug."""
        # Check if bug is in shared API (common cause)
        if api_endpoint and api_endpoint.startswith("/api/"):
            platforms_str = ", ".join([p.value for p in platforms])
            return f"Fix shared API endpoint {api_endpoint} (affects {platforms_str})"
        else:
            # Check for common error patterns
            error_messages = [bug.error_message.lower() for bug in bugs]
            if any("timeout" in msg for msg in error_messages):
                return "Investigate timeout handling across platforms"
            elif any("network" in msg or "connection" in msg for msg in error_messages):
                return "Investigate network error handling across platforms"
            elif any("authentication" in msg or "unauthorized" in msg for msg in error_messages):
                return "Review authentication flow across platforms"
            else:
                platforms_str = ", ".join([p.value for p in platforms])
                return f"Investigate shared backend logic (affects {platforms_str})"

    def load_bugs_from_json(
        self,
        json_path: str,
        platform: Platform
    ) -> List[BugReport]:
        """
        Load bugs from JSON file (e.g., test results).

        Args:
            json_path: Path to JSON file with bug reports
            platform: Platform source for bugs

        Returns:
            List of BugReport objects
        """
        bugs = []

        try:
            with open(json_path) as f:
                data = json.load(f)

            for bug_data in data.get("bugs", data.get("failures", [])):
                # Add platform to metadata
                metadata = bug_data.get("metadata", {})
                metadata["platform"] = platform.value

                bug = BugReport(
                    discovery_method=bug_data.get("discovery_method", "browser"),
                    test_name=bug_data.get("test_name", bug_data.get("name", "unknown")),
                    error_message=bug_data.get("error_message", bug_data.get("error", "")),
                    error_signature=bug_data.get("error_signature", ""),
                    metadata=metadata,
                    stack_trace=bug_data.get("stack_trace"),
                    timestamp=datetime.fromisoformat(bug_data["timestamp"]) if bug_data.get("timestamp") else None
                )
                bugs.append(bug)

        except Exception as e:
            print(f"[CrossPlatformCorrelator] Warning: Failed to load bugs from {json_path}: {e}")

        return bugs

    def generate_correlation_report(
        self,
        correlations: List[CrossPlatformCorrelation],
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate markdown report for cross-platform correlations.

        Args:
            correlations: List of cross-platform correlations
            output_path: Optional output file path

        Returns:
            Markdown report content
        """
        lines = [
            "# Cross-Platform Bug Correlation Report\n",
            f"**Generated**: {datetime.utcnow().isoformat()}",
            f"**Correlations Found**: {len(correlations)}\n",
            "## Summary\n",
            f"- Multi-platform bugs: {len(correlations)}",
            f"- Bugs with shared root cause: {sum(1 for c in correlations if c.shared_root_cause)}",
            f"- Average similarity: {sum(c.similarity_score for c in correlations) / max(len(correlations), 1):.2f}\n",
            "## Correlations\n"
        ]

        for i, correlation in enumerate(correlations, 1):
            lines.append(f"### {i}. {correlation.error_signature[:16]}...")
            # Handle both enum and string platforms (use_enum_values=True converts to strings)
            platform_strs = [p.value if hasattr(p, 'value') else p for p in correlation.platforms]
            lines.append(f"**Platforms**: {', '.join(platform_strs)}")
            lines.append(f"**Similarity**: {correlation.similarity_score:.2f}")
            lines.append(f"**API Endpoint**: {correlation.api_endpoint or 'N/A'}")
            lines.append(f"**Shared Root Cause**: {'Yes' if correlation.shared_root_cause else 'No'}")
            lines.append(f"**Suggested Action**: {correlation.suggested_action}")

            if correlation.error_messages:
                lines.append("**Error Messages**:")
                for platform, msg in correlation.error_messages.items():
                    msg_preview = msg[:100] + "..." if len(msg) > 100 else msg
                    lines.append(f"- {platform}: `{msg_preview}`")

            lines.append("")

        report = "\n".join(lines)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(report)

        return report
