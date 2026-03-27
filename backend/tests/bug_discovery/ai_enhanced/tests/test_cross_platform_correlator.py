"""Unit tests for CrossPlatformCorrelator."""
import pytest
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.ai_enhanced.cross_platform_correlator import CrossPlatformCorrelator
from tests.bug_discovery.ai_enhanced.models.cross_platform_correlation import CrossPlatformCorrelation, Platform
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod


@pytest.fixture
def sample_web_bugs():
    """Create sample web bugs for testing."""
    return [
        BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_web_login",
            error_message="HTTP 500: Internal Server Error at /backend/core/auth_service.py:456",
            error_signature="web_auth_error",
            metadata={"platform": "web", "api_endpoint": "/api/v1/auth/login"}
        ),
        BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_web_agent",
            error_message="Timeout waiting for agent response",
            error_signature="web_timeout",
            metadata={"platform": "web", "api_endpoint": "/api/v1/agents"}
        )
    ]


@pytest.fixture
def sample_mobile_bugs():
    """Create sample mobile bugs for testing."""
    return [
        BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_mobile_login",
            error_message="HTTP 500: Internal Server Error at mobile/src/api/auth.ts:78",
            error_signature="mobile_auth_error",
            metadata={"platform": "mobile", "api_endpoint": "/api/v1/auth/login"}
        ),
        BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_mobile_workflow",
            error_message="Network connection lost",
            error_signature="mobile_network",
            metadata={"platform": "mobile", "api_endpoint": "/api/v1/workflows"}
        )
    ]


@pytest.fixture
def sample_desktop_bugs():
    """Create sample desktop bugs for testing."""
    return []


class TestCrossPlatformCorrelator:
    """Test CrossPlatformCorrelator functionality."""

    def test_correlate_cross_platform_bugs_same_endpoint(self, sample_web_bugs, sample_mobile_bugs):
        """Test correlation when same API endpoint fails on multiple platforms."""
        correlator = CrossPlatformCorrelator()

        correlated = correlator.correlate_cross_platform_bugs(
            web_bugs=sample_web_bugs,
            mobile_bugs=sample_mobile_bugs,
            desktop_bugs=[],
            similarity_threshold=0.5  # Lower threshold for testing
        )

        # Should correlate auth endpoint failures
        auth_correlations = [c for c in correlated if "/auth" in (c.api_endpoint or "")]
        assert len(auth_correlations) >= 1

        correlation = auth_correlations[0]
        assert Platform.WEB in correlation.platforms or Platform.MOBILE in correlation.platforms
        assert correlation.shared_root_cause  # Shared API endpoint
        assert "Fix shared API endpoint" in correlation.suggested_action

    def test_normalize_error_for_cross_platform(self):
        """Test error message normalization."""
        correlator = CrossPlatformCorrelator()

        # Remove file paths
        normalized = correlator._normalize_error_for_cross_platform(
            "Error at /backend/core/service.py:456",
            Platform.WEB
        )
        assert "/backend/core/service.py" not in normalized
        assert ":LINE" in normalized  # Line number placeholder

        # Normalize error codes
        normalized = correlator._normalize_error_for_cross_platform(
            "Internal Server Error",
            Platform.WEB
        )
        assert "HTTP 500" in normalized

    def test_calculate_cross_platform_similarity(self):
        """Test similarity score calculation."""
        correlator = CrossPlatformCorrelator()

        # Create bugs with same API endpoint
        bug1 = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test1",
            error_message="HTTP 500 error",
            error_signature="sig1",
            metadata={"api_endpoint": "/api/v1/test"}
        )
        bug2 = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test2",
            error_message="HTTP 500 failure",
            error_signature="sig2",
            metadata={"api_endpoint": "/api/v1/test"}
        )

        similarity = correlator._calculate_cross_platform_similarity([bug1, bug2])
        assert similarity > 0.5  # Should be similar (same endpoint, similar error)

    def test_suggest_action_shared_api(self):
        """Test suggested action for shared API bugs."""
        correlator = CrossPlatformCorrelator()

        bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test",
            error_message="Error",
            error_signature="sig",
            metadata={"api_endpoint": "/api/v1/agents"}
        )

        action = correlator._suggest_action(
            bugs=[bug],
            platforms=[Platform.WEB, Platform.MOBILE],
            api_endpoint="/api/v1/agents"
        )

        assert "Fix shared API endpoint" in action
        assert "/api/v1/agents" in action
        assert "web" in action.lower()
        assert "mobile" in action.lower()

    def test_suggest_action_timeout_pattern(self):
        """Test suggested action for timeout errors."""
        correlator = CrossPlatformCorrelator()

        bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test",
            error_message="Timeout waiting for response",
            error_signature="sig",
            metadata={"platform": "web"}
        )

        action = correlator._suggest_action(
            bugs=[bug],
            platforms=[Platform.WEB, Platform.MOBILE],
            api_endpoint=None
        )

        assert "timeout" in action.lower()

    def test_load_bugs_from_json(self, tmp_path):
        """Test loading bugs from JSON file."""
        correlator = CrossPlatformCorrelator()

        # Create JSON file with bug data
        bug_data = {
            "bugs": [
                {
                    "test_name": "test_login",
                    "error_message": "Auth failed",
                    "error_signature": "auth_fail",
                    "metadata": {"platform": "web"},
                    "timestamp": "2026-03-25T10:00:00Z"
                }
            ]
        }

        json_file = tmp_path / "bugs.json"
        json_file.write_text(json.dumps(bug_data))

        bugs = correlator.load_bugs_from_json(str(json_file), Platform.WEB)

        assert len(bugs) == 1
        assert bugs[0].test_name == "test_login"
        assert bugs[0].metadata["platform"] == "web"

    def test_extract_platforms(self):
        """Test platform extraction from bug metadata."""
        correlator = CrossPlatformCorrelator()

        bugs = [
            BugReport(
                discovery_method=DiscoveryMethod.BROWSER,
                test_name="test1",
                error_message="Error",
                error_signature="sig1",
                metadata={"platform": "web"}
            ),
            BugReport(
                discovery_method=DiscoveryMethod.BROWSER,
                test_name="test2",
                error_message="Error",
                error_signature="sig2",
                metadata={"platform": "mobile"}
            )
        ]

        platforms = correlator._extract_platforms(bugs)

        assert len(platforms) == 2
        assert Platform.WEB in platforms
        assert Platform.MOBILE in platforms

    def test_generate_correlation_report(self):
        """Test correlation report generation."""
        correlator = CrossPlatformCorrelator()

        correlations = [
            CrossPlatformCorrelation(
                correlation_id="test123",
                platforms=[Platform.WEB, Platform.MOBILE],
                similarity_score=0.85,
                error_signature="sig",
                api_endpoint="/api/v1/test",
                error_messages={"web": "Error 1", "mobile": "Error 2"},
                bug_reports=["test_web", "test_mobile"],
                suggested_action="Fix API",
                shared_root_cause=True,
                timestamp=datetime.utcnow().isoformat()
            )
        ]

        report = correlator.generate_correlation_report(correlations)

        assert "# Cross-Platform Bug Correlation Report" in report
        assert "sig" in report  # correlation_id is first 16 chars of signature
        assert "web, mobile" in report.lower()
        assert "0.85" in report
        assert "Fix API" in report

    def test_temporal_proximity_filtering(self, sample_web_bugs, sample_mobile_bugs):
        """Test that correlations respect temporal proximity."""
        # Add timestamps far apart
        old_time = datetime.utcnow() - timedelta(hours=48)
        recent_time = datetime.utcnow()

        sample_web_bugs[0].timestamp = old_time
        sample_mobile_bugs[0].timestamp = recent_time

        correlator = CrossPlatformCorrelator()

        correlated = correlator.correlate_cross_platform_bugs(
            web_bugs=sample_web_bugs,
            mobile_bugs=sample_mobile_bugs,
            desktop_bugs=[],
            similarity_threshold=0.5,
            max_hours_apart=1.0  # Only 1 hour apart
        )

        # Should not correlate bugs 48 hours apart
        far_apart_correlations = [c for c in correlated if c.temporal_proximity_hours and c.temporal_proximity_hours > 1.0]
        assert len(far_apart_correlations) == 0

    def test_no_correlation_single_platform(self, sample_web_bugs):
        """Test that single-platform bugs are not correlated."""
        correlator = CrossPlatformCorrelator()

        correlated = correlator.correlate_cross_platform_bugs(
            web_bugs=sample_web_bugs,
            mobile_bugs=[],  # No mobile bugs
            desktop_bugs=[],
            similarity_threshold=0.5
        )

        # Should return empty (no cross-platform bugs)
        assert len(correlated) == 0

    def test_similarity_score_components(self):
        """Test similarity score calculation components."""
        correlator = CrossPlatformCorrelator()

        # Same endpoint = high similarity
        bug1 = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test1",
            error_message="HTTP 500 Internal Server Error",
            error_signature="sig1",
            metadata={"api_endpoint": "/api/v1/test"}
        )
        bug2 = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test2",
            error_message="HTTP 500 Internal Server Error",
            error_signature="sig2",
            metadata={"api_endpoint": "/api/v1/test"}
        )

        similarity = correlator._calculate_cross_platform_similarity([bug1, bug2])

        # Should have high similarity due to:
        # - Same endpoint (0.6 weight)
        # - Similar error messages (0.4 weight)
        assert similarity > 0.7

    def test_cross_platform_signature_generation(self):
        """Test cross-platform signature generation is platform-agnostic."""
        correlator = CrossPlatformCorrelator()

        web_bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_web",
            error_message="Error at /backend/core/service.py:456",
            error_signature="sig1",
            metadata={"platform": "web", "api_endpoint": "/api/v1/test"}
        )

        mobile_bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_mobile",
            error_message="Error at mobile/src/service.ts:78",
            error_signature="sig2",
            metadata={"platform": "mobile", "api_endpoint": "/api/v1/test"}
        )

        all_bugs = {
            Platform.WEB: [web_bug],
            Platform.MOBILE: [mobile_bug],
            Platform.DESKTOP: []
        }

        signatures = correlator._generate_cross_platform_signatures(all_bugs)

        assert len(signatures) == 2

        # Signatures should be identical (same API endpoint + normalized error)
        # because file paths are stripped by normalization
        sig1, sig2 = signatures[0][1], signatures[1][1]
        assert sig1 == sig2  # Same signature after normalization

    def test_shared_root_cause_detection(self):
        """Test shared root cause detection for API endpoints."""
        correlator = CrossPlatformCorrelator()

        # API endpoint bug
        api_bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test",
            error_message="Error",
            error_signature="sig",
            metadata={"api_endpoint": "/api/v1/agents"}
        )

        action = correlator._suggest_action(
            bugs=[api_bug],
            platforms=[Platform.WEB, Platform.MOBILE],
            api_endpoint="/api/v1/agents"
        )

        assert "Fix shared API endpoint" in action

        # Non-API bug
        non_api_bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test",
            error_message="Timeout error",
            error_signature="sig",
            metadata={}
        )

        action = correlator._suggest_action(
            bugs=[non_api_bug],
            platforms=[Platform.WEB, Platform.MOBILE],
            api_endpoint=None
        )

        assert "Fix shared API endpoint" not in action
