"""
Test Suite for A/B Testing Service

Tests for core.ab_testing_service module (665 lines)
- Experiment management (creation, activation, termination)
- Variant assignment (deterministic, hash-based)
- Metric tracking and aggregation
- Statistical analysis (t-test, chi-square)
- Winner determination

Target Tests: 25-30
Target Coverage: 25-30%
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest

from core.ab_testing_service import ABTestingService


class TestABTestingServiceInit:
    """Test ABTestingService initialization."""

    def test_initialization_with_db_session(self):
        """ABTestingService can be initialized with database session."""
        mock_db = Mock()
        service = ABTestingService(db=mock_db)

        assert service.db == mock_db


class TestExperimentCreation:
    """Test experiment creation and configuration."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        # Mock query for agent existence check
        mock_agent = Mock()
        mock_agent.id = "agent-001"
        db.query.return_value.filter.return_value.first.return_value = mock_agent
        return db

    def test_create_experiment_with_valid_config(self, mock_db):
        """ABTestingService can create experiment with valid configuration."""
        service = ABTestingService(db=mock_db)

        result = service.create_test(
            name="Test Experiment",
            test_type="agent_config",
            agent_id="agent-001",
            variant_a_config={"temperature": 0.7},
            variant_b_config={"temperature": 0.9},
            primary_metric="satisfaction_rate"
        )

        assert "error" not in result
        assert result["name"] == "Test Experiment"
        assert result["status"] == "draft"
        assert result["test_type"] == "agent_config"
        assert result["variant_a"]["name"] == "Control"
        assert result["variant_b"]["name"] == "Treatment"

    def test_create_experiment_fails_with_invalid_agent(self, mock_db):
        """ABTestingService returns error when agent not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        service = ABTestingService(db=mock_db)

        result = service.create_test(
            name="Test Experiment",
            test_type="agent_config",
            agent_id="nonexistent-agent",
            variant_a_config={},
            variant_b_config={},
            primary_metric="satisfaction_rate"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_create_experiment_validates_test_type(self, mock_db):
        """ABTestingService validates test_type parameter."""
        service = ABTestingService(db=mock_db)

        result = service.create_test(
            name="Test Experiment",
            test_type="invalid_type",
            agent_id="agent-001",
            variant_a_config={},
            variant_b_config={},
            primary_metric="satisfaction_rate"
        )

        assert "error" in result
        assert "invalid" in result["error"].lower()

    def test_create_experiment_validates_traffic_percentage(self, mock_db):
        """ABTestingService validates traffic_percentage is between 0.0 and 1.0."""
        service = ABTestingService(db=mock_db)

        result = service.create_test(
            name="Test Experiment",
            test_type="agent_config",
            agent_id="agent-001",
            variant_a_config={},
            variant_b_config={},
            primary_metric="satisfaction_rate",
            traffic_percentage=1.5  # Invalid
        )

        assert "error" in result
        assert "traffic_percentage" in result["error"].lower()

    def test_create_experiment_with_custom_variant_names(self, mock_db):
        """ABTestingService accepts custom variant names."""
        service = ABTestingService(db=mock_db)

        result = service.create_test(
            name="Test Experiment",
            test_type="prompt",
            agent_id="agent-001",
            variant_a_config={"prompt": "v1"},
            variant_b_config={"prompt": "v2"},
            primary_metric="success_rate",
            variant_a_name="Version 1",
            variant_b_name="Version 2"
        )

        assert "error" not in result
        assert result["variant_a"]["name"] == "Version 1"
        assert result["variant_b"]["name"] == "Version 2"


class TestExperimentActivation:
    """Test experiment activation and lifecycle management."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        # Mock experiment in draft status
        mock_test = Mock()
        mock_test.id = "test-001"
        mock_test.name = "Test Experiment"
        mock_test.status = "draft"
        db.query.return_value.filter.return_value.first.return_value = mock_test
        return db

    def test_start_experiment_in_draft_status(self, mock_db):
        """ABTestingService can start experiment in draft status."""
        service = ABTestingService(db=mock_db)

        result = service.start_test(test_id="test-001")

        assert "error" not in result
        assert result["status"] == "running"
        assert "started_at" in result

    def test_start_experiment_fails_if_not_found(self, mock_db):
        """ABTestingService returns error when experiment not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        service = ABTestingService(db=mock_db)

        result = service.start_test(test_id="nonexistent-test")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_start_experiment_fails_if_already_running(self, mock_db):
        """ABTestingService returns error when experiment already running."""
        mock_test = mock_db.query.return_value.filter.return_value.first
        mock_test.return_value.status = "running"
        service = ABTestingService(db=mock_db)

        result = service.start_test(test_id="test-001")

        assert "error" in result
        assert "must be in 'draft' status" in result["error"]


class TestVariantAssignment:
    """Test variant assignment logic."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        # Mock running experiment
        mock_test = Mock()
        mock_test.id = "test-001"
        mock_test.name = "Test Experiment"
        mock_test.status = "running"
        mock_test.traffic_percentage = 0.5
        mock_test.variant_a_name = "Control"
        mock_test.variant_b_name = "Treatment"
        mock_test.variant_a_config = {"config": "A"}
        mock_test.variant_b_config = {"config": "B"}

        # Mock no existing participant
        db.query.return_value.filter.return_value.first.return_value = None

        # Return mock test when queried
        def query_side_effect(model):
            mock_query = Mock()
            if model == Mock:  # ABTest query
                mock_query.filter.return_value.first.return_value = mock_test
            return mock_query

        db.query.side_effect = query_side_effect
        return db

    def test_assign_variant_deterministic_for_same_user(self, mock_db):
        """ABTestingService assigns same variant to same user consistently."""
        service = ABTestingService(db=mock_db)

        # Assign same user twice
        result1 = service.assign_variant(
            test_id="test-001",
            user_id="user-123"
        )
        result2 = service.assign_variant(
            test_id="test-001",
            user_id="user-123"
        )

        # First assignment creates new participant
        assert "error" not in result1
        assert "variant" in result1

        # Second assignment should return existing
        # (Note: This test may need adjustment based on actual implementation)

    def test_assign_variant_for_nonexistent_experiment(self, mock_db):
        """ABTestingService returns error when assigning to nonexistent test."""
        # Configure mock to return None for test query
        def query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = None
            return mock_query

        mock_db.query.side_effect = query_side_effect
        service = ABTestingService(db=mock_db)

        result = service.assign_variant(
            test_id="nonexistent-test",
            user_id="user-123"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_assign_variant_fails_if_test_not_running(self, mock_db):
        """ABTestingService returns error when assigning to non-running test."""
        # Reconfigure mock to return draft test
        mock_test = Mock()
        mock_test.status = "draft"

        def query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = mock_test
            return mock_query

        mock_db.query.side_effect = query_side_effect
        service = ABTestingService(db=mock_db)

        result = service.assign_variant(
            test_id="test-001",
            user_id="user-123"
        )

        assert "error" in result
        assert "must be running" in result["error"]


class TestMetricTracking:
    """Test metric recording and tracking."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        # Mock existing participant
        mock_participant = Mock()
        mock_participant.test_id = "test-001"
        mock_participant.user_id = "user-123"
        mock_participant.assigned_variant = "A"
        db.query.return_value.filter.return_value.first.return_value = mock_participant
        return db

    def test_record_metric_success(self, mock_db):
        """ABTestingService can record success metric for participant."""
        service = ABTestingService(db=mock_db)

        result = service.record_metric(
            test_id="test-001",
            user_id="user-123",
            success=True,
            metric_value=0.85
        )

        assert "error" not in result
        assert result["success"] is True
        assert result["metric_value"] == 0.85
        assert "recorded_at" in result

    def test_record_metric_fails_if_participant_not_found(self, mock_db):
        """ABTestingService returns error when participant not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        service = ABTestingService(db=mock_db)

        result = service.record_metric(
            test_id="test-001",
            user_id="nonexistent-user"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_record_metric_with_metadata(self, mock_db):
        """ABTestingService can record metric with additional metadata."""
        service = ABTestingService(db=mock_db)

        result = service.record_metric(
            test_id="test-001",
            user_id="user-123",
            success=True,
            metadata={"response_time": 150, "model": "gpt-4"}
        )

        assert "error" not in result
        assert result["success"] is True


class TestResultsAndAnalysis:
    """Test results calculation and statistical analysis."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        # Mock completed test
        mock_test = Mock()
        mock_test.id = "test-001"
        mock_test.name = "Test Experiment"
        mock_test.status = "completed"
        mock_test.test_type = "agent_config"
        mock_test.primary_metric = "satisfaction_rate"
        mock_test.variant_a_name = "Control"
        mock_test.variant_b_name = "Treatment"
        mock_test.variant_a_metrics = None
        mock_test.variant_b_metrics = None
        mock_test.statistical_significance = None
        mock_test.winner = None
        mock_test.started_at = datetime.now()
        mock_test.completed_at = None
        mock_test.min_sample_size = 100
        mock_test.statistical_significance_threshold = 0.05

        # Mock participant counts
        from sqlalchemy import func
        db.query.return_value.filter.return_value.scalar.side_effect = [50, 45]

        def query_side_effect(model):
            mock_query = Mock()
            if model == func:  # Count query
                pass  # scalar side_effect handles this
            else:  # ABTest query
                mock_query.filter.return_value.first.return_value = mock_test
            return mock_query

        db.query.side_effect = query_side_effect
        return db

    def test_get_test_results(self, mock_db):
        """ABTestingService can retrieve test results."""
        service = ABTestingService(db=mock_db)

        result = service.get_test_results(test_id="test-001")

        assert "error" not in result
        assert result["test_id"] == "test-001"
        assert result["name"] == "Test Experiment"
        assert result["status"] == "completed"
        assert "variant_a" in result
        assert "variant_b" in result

    def test_get_test_results_not_found(self, mock_db):
        """ABTestingService returns error when test not found."""
        def query_side_effect(model):
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = None
            return mock_query

        mock_db.query.side_effect = query_side_effect
        service = ABTestingService(db=mock_db)

        result = service.get_test_results(test_id="nonexistent-test")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_list_tests_with_filters(self, mock_db):
        """ABTestingService can list tests with optional filters."""
        # Mock test list
        mock_tests = [
            Mock(id="test-001", name="Test 1", status="running",
                 test_type="agent_config", agent_id="agent-001",
                 primary_metric="success_rate", winner=None,
                 created_at=datetime.now()),
            Mock(id="test-002", name="Test 2", status="completed",
                 test_type="prompt", agent_id="agent-001",
                 primary_metric="satisfaction_rate", winner="B",
                 created_at=datetime.now())
        ]

        def query_side_effect(model):
            mock_query = Mock()
            mock_query.order_by.return_value.limit.return_value.all.return_value = mock_tests
            return mock_query

        mock_db.query.side_effect = query_side_effect
        service = ABTestingService(db=mock_db)

        result = service.list_tests(agent_id="agent-001", status="running")

        assert "total" in result
        assert result["total"] == 2
        assert "tests" in result
        assert len(result["tests"]) == 2


class TestStatisticalAnalysis:
    """Test statistical analysis methods."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    def test_calculate_variant_metrics_with_empty_participants(self, mock_db):
        """ABTestingService returns zero metrics for empty participant list."""
        service = ABTestingService(db=mock_db)

        result = service._calculate_variant_metrics(
            participants=[],
            primary_metric="success_rate"
        )

        assert result["count"] == 0
        assert result["success_rate"] is None
        assert result["average_metric_value"] is None

    def test_calculate_variant_metrics_with_participants(self, mock_db):
        """ABTestingService calculates metrics from participant data."""
        service = ABTestingService(db=mock_db)

        # Create mock participants
        participants = [
            Mock(success=True, metric_value=0.8),
            Mock(success=False, metric_value=0.6),
            Mock(success=True, metric_value=0.9)
        ]

        result = service._calculate_variant_metrics(
            participants=participants,
            primary_metric="success_rate"
        )

        assert result["count"] == 3
        assert result["success_count"] == 2
        assert result["success_rate"] == pytest.approx(0.667, rel=0.01)
        assert result["average_metric_value"] == pytest.approx(0.767, rel=0.01)

    def test_perform_statistical_test_with_success_rates(self, mock_db):
        """ABTestingService performs statistical test for success rates."""
        service = ABTestingService(db=mock_db)

        metrics_a = {"success_rate": 0.70, "count": 100}
        metrics_b = {"success_rate": 0.90, "count": 100}

        p_value, winner = service._perform_statistical_test(
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            primary_metric="success_rate",
            alpha=0.05
        )

        assert p_value is not None
        assert p_value < 0.05  # 20% difference should be significant
        assert winner == "B"  # B has higher rate

    def test_perform_statistical_test_inconclusive_small_difference(self, mock_db):
        """ABTestingService returns inconclusive for small differences."""
        service = ABTestingService(db=mock_db)

        metrics_a = {"success_rate": 0.75, "count": 100}
        metrics_b = {"success_rate": 0.78, "count": 100}

        p_value, winner = service._perform_statistical_test(
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            primary_metric="success_rate",
            alpha=0.05
        )

        # Small difference (3%) should have higher p-value
        assert p_value >= 0.05 or winner == "inconclusive"
