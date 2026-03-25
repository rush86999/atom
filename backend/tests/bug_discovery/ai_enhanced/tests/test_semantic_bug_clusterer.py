"""Unit tests for SemanticBugClusterer."""
import pytest
from datetime import datetime
from pathlib import Path
import sys
import tempfile

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.ai_enhanced.semantic_bug_clusterer import SemanticBugClusterer
from tests.bug_discovery.ai_enhanced.models.bug_cluster import BugCluster
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod


@pytest.fixture
def sample_bugs():
    """Create sample bugs for testing."""
    return [
        BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_auth_sql_injection",
            error_message="SQL injection in auth endpoint: ' OR 1=1 --",
            error_signature="sql_injection_auth",
            metadata={"platform": "web", "severity": "critical"}
        ),
        BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_agent_sql_injection",
            error_message="SQL injection in agent_id parameter: agent_id=' OR 1=1 --",
            error_signature="sql_injection_agent",
            metadata={"platform": "web", "severity": "critical"}
        ),
        BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="test_timeout",
            error_message="Request timeout after 30 seconds",
            error_signature="timeout",
            metadata={"platform": "mobile", "severity": "high"}
        ),
        BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="test_memory_leak",
            error_message="Memory leak detected in LLM streaming",
            error_signature="memory_leak",
            metadata={"platform": "web", "severity": "high"}
        )
    ]


@pytest.mark.asyncio
class TestSemanticBugClusterer:
    """Test SemanticBugClusterer functionality."""

    async def test_cluster_bugs_creates_clusters(self, sample_bugs):
        """Test that bugs are clustered by similarity."""
        clusterer = SemanticBugClusterer()

        # Skip if FastEmbed not installed (graceful degradation)
        try:
            import fastembed
        except ImportError:
            pytest.skip("FastEmbed not installed - semantic clustering requires embeddings")

        clusters = await clusterer.cluster_bugs(
            bugs=sample_bugs,
            similarity_threshold=0.3,  # Lower for testing
            min_cluster_size=2
        )

        # Should create at least one cluster
        assert len(clusters) >= 1

        cluster = clusters[0]
        assert isinstance(cluster, BugCluster)
        assert cluster.size >= 2
        assert cluster.theme  # Theme should be generated

    async def test_cluster_filters_by_similarity_threshold(self, sample_bugs):
        """Test that clusters respect similarity threshold."""
        # Skip if FastEmbed not installed (graceful degradation)
        try:
            import fastembed
        except ImportError:
            pytest.skip("FastEmbed not installed - semantic clustering requires embeddings")

        clusterer = SemanticBugClusterer()

        # High threshold -> fewer clusters
        high_clusters = await clusterer.cluster_bugs(
            bugs=sample_bugs,
            similarity_threshold=0.9,
            min_cluster_size=2
        )

        # Low threshold -> more clusters
        low_clusters = await clusterer.cluster_bugs(
            bugs=sample_bugs,
            similarity_threshold=0.3,
            min_cluster_size=2
        )

        assert len(high_clusters) <= len(low_clusters)

    async def test_cluster_respects_min_cluster_size(self, sample_bugs):
        """Test that clusters meet minimum size requirement."""
        # Skip if FastEmbed not installed (graceful degradation)
        try:
            import fastembed
        except ImportError:
            pytest.skip("FastEmbed not installed - semantic clustering requires embeddings")

        clusterer = SemanticBugClusterer()

        clusters = await clusterer.cluster_bugs(
            bugs=sample_bugs,
            similarity_threshold=0.3,
            min_cluster_size=3
        )

        # All clusters should have at least 3 bugs
        for cluster in clusters:
            assert cluster.size >= 3

    def test_clean_text_for_embedding(self):
        """Test text cleaning for embedding."""
        clusterer = SemanticBugClusterer()

        # Remove file paths
        text = clusterer._clean_text_for_embedding("Error at /backend/core/service.py:456")
        assert "/backend/core/service.py" not in text
        assert ":456" not in text

        # Remove timestamps
        text = clusterer._clean_text_for_embedding("Error at 2026-03-25T10:30:00Z")
        assert "2026-03-25" not in text

        # Remove memory addresses
        text = clusterer._clean_text_for_embedding("Error at 0x7f8b4c0d0")
        assert "0x7f8b4c0d0" not in text

    def test_generate_cluster_id(self):
        """Test cluster ID generation."""
        clusterer = SemanticBugClusterer()

        id1 = clusterer._generate_cluster_id()
        id2 = clusterer._generate_cluster_id()

        # IDs should be unique
        assert id1 != id2

        # IDs should start with "cluster_"
        assert id1.startswith("cluster_")
        assert id2.startswith("cluster_")

    def test_calculate_severity_distribution(self, sample_bugs):
        """Test severity distribution calculation."""
        clusterer = SemanticBugClusterer()

        bug_ids = [bug.test_name for bug in sample_bugs[:2]]
        distribution = clusterer._calculate_severity_distribution(bug_ids, sample_bugs)

        assert isinstance(distribution, dict)
        assert len(distribution) > 0  # Should have at least one severity level

    def test_calculate_platform_distribution(self, sample_bugs):
        """Test platform distribution calculation."""
        clusterer = SemanticBugClusterer()

        bug_ids = [bug.test_name for bug in sample_bugs[:2]]
        distribution = clusterer._calculate_platform_distribution(bug_ids, sample_bugs)

        assert isinstance(distribution, dict)
        assert "web" in distribution  # Most bugs are web platform

    @pytest.mark.asyncio
    async def test_save_clusters(self, tmp_path):
        """Test saving clusters to JSON files."""
        clusterer = SemanticBugClusterer()

        cluster = BugCluster(
            cluster_id="test_cluster",
            theme="Test Theme",
            size=2,
            similarity_scores=[0.8, 0.85],
            avg_similarity=0.825,
            bug_ids=["bug1", "bug2"],
            bug_reports=["Bug 1", "Bug 2"],
            representative_bug="bug1",
            discovery_methods=["property"],
            timestamp=datetime.utcnow()
        )

        saved_paths = await clusterer.save_clusters([cluster], output_dir=str(tmp_path))

        assert len(saved_paths) == 1
        assert Path(saved_paths[0]).exists()
        assert "cluster_test_cluster.json" in saved_paths[0]

    @pytest.mark.asyncio
    async def test_generate_cluster_report(self):
        """Test cluster report generation."""
        clusterer = SemanticBugClusterer()

        cluster = BugCluster(
            cluster_id="test_cluster",
            theme="SQL Injection Bugs",
            size=3,
            similarity_scores=[0.8, 0.85, 0.82],
            avg_similarity=0.82,
            bug_ids=["bug1", "bug2", "bug3"],
            bug_reports=["Bug 1", "Bug 2", "Bug 3"],
            representative_bug="bug1",
            discovery_methods=["property", "fuzzing"],
            timestamp=datetime.utcnow(),
            severity_distribution={"critical": 2, "high": 1},
            platform_distribution={"web": 3}
        )

        report = await clusterer.generate_cluster_report([cluster])

        assert "# Semantic Bug Clustering Report" in report
        assert "SQL Injection Bugs" in report
        assert "test_cluster" in report
        assert "'critical': 2" in report
        assert "'web': 3" in report

    async def test_generate_cluster_theme_llm(self, sample_bugs, monkeypatch):
        """Test cluster theme generation via LLM."""
        clusterer = SemanticBugClusterer()

        # Mock LLM response
        async def mock_generate(*args, **kwargs):
            return "SQL injection in parameters"

        monkeypatch.setattr(clusterer.llm_service, "generate_completion", mock_generate)

        bug_ids = [bug.test_name for bug in sample_bugs[:2]]
        theme = await clusterer._generate_cluster_theme(bug_ids, sample_bugs)

        assert theme == "SQL injection in parameters"

    async def test_generate_cluster_theme_fallback(self, sample_bugs, monkeypatch):
        """Test fallback theme generation when LLM fails."""
        clusterer = SemanticBugClusterer()

        # Mock LLM to fail
        async def failing_generate(*args, **kwargs):
            raise Exception("LLM failed")

        monkeypatch.setattr(clusterer.llm_service, "generate_completion", failing_generate)

        bug_ids = [bug.test_name for bug in sample_bugs[:2]]
        theme = await clusterer._generate_cluster_theme(bug_ids, sample_bugs)

        assert "Cluster of 2 similar bugs" in theme

    async def test_empty_bugs_list(self):
        """Test clustering with empty bug list."""
        clusterer = SemanticBugClusterer()

        clusters = await clusterer.cluster_bugs(
            bugs=[],
            similarity_threshold=0.75,
            min_cluster_size=2
        )

        assert len(clusters) == 0

    async def test_single_bug_no_clusters(self, sample_bugs):
        """Test that single bug doesn't create cluster."""
        clusterer = SemanticBugClusterer()

        clusters = await clusterer.cluster_bugs(
            bugs=[sample_bugs[0]],  # Single bug
            similarity_threshold=0.75,
            min_cluster_size=2
        )

        assert len(clusters) == 0  # Need at least 2 bugs

    def test_find_representative_bug(self):
        """Test finding representative bug from similarity scores."""
        clusterer = SemanticBugClusterer()

        bug_ids = ["bug1", "bug2", "bug3"]
        similarity_scores = [0.7, 0.9, 0.8]

        representative = clusterer._find_representative_bug(bug_ids, similarity_scores)

        assert representative == "bug2"  # Highest similarity

    async def test_cluster_statistics(self, sample_bugs):
        """Test that clusters include statistics."""
        # Skip if FastEmbed not installed (graceful degradation)
        try:
            import fastembed
        except ImportError:
            pytest.skip("FastEmbed not installed - semantic clustering requires embeddings")

        clusterer = SemanticBugClusterer()

        clusters = await clusterer.cluster_bugs(
            bugs=sample_bugs,
            similarity_threshold=0.3,
            min_cluster_size=2
        )

        for cluster in clusters:
            assert hasattr(cluster, "severity_distribution")
            assert hasattr(cluster, "platform_distribution")
            assert isinstance(cluster.severity_distribution, dict)
            assert isinstance(cluster.platform_distribution, dict)
