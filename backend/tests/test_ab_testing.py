"""
A/B Testing Service Tests

Comprehensive test suite for A/B testing functionality including:
- Test creation and management
- Variant assignment
- Metric tracking
- Statistical analysis
- API endpoints
"""

import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy.orm import Session

from core.ab_testing_service import ABTestingService
from core.models import ABTest, ABTestParticipant, AgentRegistry, User

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_agent(db):
    """Create a test agent."""
    agent_id = f"agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Test Agent",
        category="Sales",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status="INTERN",
        confidence_score=0.6
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    db.query(ABTestParticipant).filter(ABTestParticipant.test_id.in_(
        db.query(ABTest.id).filter(ABTest.agent_id == agent_id)
    )).delete(synchronize_session=False)
    db.query(ABTest).filter(ABTest.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user_id = f"user-{uuid.uuid4()}"
    user = User(
        id=user_id,
        email=f"test-{uuid.uuid4()}@example.com",
        first_name="Test",
        last_name="User"
    )
    db.add(user)
    db.commit()
    db.expunge(user)
    yield user
    db.query(ABTestParticipant).filter(ABTestParticipant.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def sample_test_config():
    """Sample A/B test configuration."""
    return {
        "name": "Prompt Optimization Test",
        "test_type": "prompt",
        "agent_id": None,  # Will be set by test
        "variant_a_config": {
            "system_prompt": "You are a helpful assistant.",
            "temperature": 0.7
        },
        "variant_b_config": {
            "system_prompt": "You are an expert assistant with detailed knowledge.",
            "temperature": 0.7
        },
        "primary_metric": "satisfaction_rate",
        "variant_a_name": "Simple Prompt",
        "variant_b_name": "Detailed Prompt",
        "traffic_percentage": 0.5,
        "min_sample_size": 100,
        "confidence_level": 0.95
    }


# ============================================================================
# Test Creation Tests
# ============================================================================

class TestABTestCreation:
    """Test A/B test creation and validation."""

    def test_create_test_success(self, db, test_agent, sample_test_config):
        """Test successful A/B test creation."""
        service = ABTestingService(db)

        config = sample_test_config.copy()
        config["agent_id"] = test_agent.id

        result = service.create_test(**config)

        assert "error" not in result
        assert "test_id" in result
        assert result["name"] == "Prompt Optimization Test"
        assert result["test_type"] == "prompt"
        assert result["agent_id"] == test_agent.id
        assert result["status"] == "draft"
        assert result["variant_a"]["name"] == "Simple Prompt"
        assert result["variant_b"]["name"] == "Detailed Prompt"
        assert result["primary_metric"] == "satisfaction_rate"

    def test_create_test_invalid_agent(self, db, sample_test_config):
        """Test test creation with non-existent agent."""
        service = ABTestingService(db)

        config = sample_test_config.copy()
        config["agent_id"] = "non-existent-agent"

        result = service.create_test(**config)

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_create_test_invalid_type(self, db, test_agent, sample_test_config):
        """Test test creation with invalid test type."""
        service = ABTestingService(db)

        config = sample_test_config.copy()
        config["agent_id"] = test_agent.id
        config["test_type"] = "invalid_type"

        result = service.create_test(**config)

        assert "error" in result
        assert "test_type" in result["error"].lower()

    def test_create_test_invalid_traffic_percentage(self, db, test_agent, sample_test_config):
        """Test test creation with invalid traffic percentage."""
        service = ABTestingService(db)

        config = sample_test_config.copy()
        config["agent_id"] = test_agent.id
        config["traffic_percentage"] = 1.5  # Invalid: > 1.0

        result = service.create_test(**config)

        assert "error" in result
        assert "traffic_percentage" in result["error"].lower()

    def test_create_test_all_test_types(self, db, test_agent):
        """Test creating all valid test types."""
        service = ABTestingService(db)

        test_types = ["agent_config", "prompt", "strategy", "tool"]

        for test_type in test_types:
            result = service.create_test(
                name=f"Test {test_type}",
                test_type=test_type,
                agent_id=test_agent.id,
                variant_a_config={"config": "A"},
                variant_b_config={"config": "B"},
                primary_metric="success_rate"
            )

            assert "error" not in result
            assert result["test_type"] == test_type


# ============================================================================
# Test Lifecycle Tests
# ============================================================================

class TestABTestLifecycle:
    """Test A/B test lifecycle: draft -> running -> completed."""

    def test_start_test(self, db, test_agent):
        """Test starting an A/B test."""
        service = ABTestingService(db)

        # Create test
        create_result = service.create_test(
            name="Lifecycle Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate"
        )

        test_id = create_result["test_id"]

        # Start test
        start_result = service.start_test(test_id)

        assert "error" not in start_result
        assert start_result["status"] == "running"
        assert start_result["started_at"] is not None

    def test_start_non_existent_test(self, db):
        """Test starting a non-existent test."""
        service = ABTestingService(db)

        result = service.start_test("non-existent-test-id")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_complete_test_with_no_participants(self, db, test_agent):
        """Test completing a test with no participants."""
        service = ABTestingService(db)

        # Create and start test
        create_result = service.create_test(
            name="Empty Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate",
            min_sample_size=10
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Complete test
        result = service.complete_test(test_id)

        assert "error" not in result
        assert result["status"] == "completed"
        assert result["completed_at"] is not None
        assert result["winner"] == "inconclusive"  # No participants
        assert result["min_sample_size_reached"] is False

    def test_complete_test_with_participants(self, db, test_agent, sample_test_config):
        """Test completing a test with participants."""
        service = ABTestingService(db)

        # Create test
        config = sample_test_config.copy()
        config["agent_id"] = test_agent.id
        config["min_sample_size"] = 10

        create_result = service.create_test(**config)
        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Add 40 participants to ensure both variants have at least 10
        for i in range(40):
            user_id = f"user-{i}"
            service.assign_variant(test_id, user_id)

            # Record metrics
            variant_result = service.assign_variant(test_id, user_id)
            variant = variant_result["variant"]
            success = (variant == "B")  # Variant B performs better
            service.record_metric(
                test_id,
                user_id,
                success=success,
                metric_value=1.0 if success else 0.5
            )

        # Complete test
        result = service.complete_test(test_id)

        assert "error" not in result
        assert result["status"] == "completed"
        assert result["min_sample_size_reached"] is True
        assert "variant_a_metrics" in result
        assert "variant_b_metrics" in result


# ============================================================================
# Variant Assignment Tests
# ============================================================================

class TestVariantAssignment:
    """Test variant assignment functionality."""

    def test_assign_variant_deterministic(self, db, test_agent):
        """Test that assignment is deterministic for same user."""
        service = ABTestingService(db)

        # Create test
        create_result = service.create_test(
            name="Assignment Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate"
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Assign same user twice - should get same variant
        user_id = "user-123"

        result1 = service.assign_variant(test_id, user_id)
        result2 = service.assign_variant(test_id, user_id)

        assert result1["variant"] == result2["variant"]
        assert result2["existing_assignment"] is True

    def test_assign_variant_distribution(self, db, test_agent):
        """Test that variants are distributed according to traffic percentage."""
        service = ABTestingService(db)

        # Create test with 50% split
        create_result = service.create_test(
            name="Distribution Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate",
            traffic_percentage=0.5
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Assign 100 users
        variants = []
        for i in range(100):
            user_id = f"user-{i}"
            result = service.assign_variant(test_id, user_id)
            variants.append(result["variant"])

        # Check distribution (should be roughly 50/50)
        variant_a_count = variants.count("A")
        variant_b_count = variants.count("B")

        assert variant_a_count > 30  # Allow some variance
        assert variant_b_count > 30
        assert variant_a_count + variant_b_count == 100

    def test_assign_variant_before_start(self, db, test_agent):
        """Test assignment fails when test is not running."""
        service = ABTestingService(db)

        # Create test but don't start
        create_result = service.create_test(
            name="Not Started Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate"
        )

        test_id = create_result["test_id"]

        # Try to assign before starting
        result = service.assign_variant(test_id, "user-123")

        assert "error" in result
        assert "running" in result["error"].lower()


# ============================================================================
# Metric Recording Tests
# ============================================================================

class TestMetricRecording:
    """Test metric recording functionality."""

    def test_record_metric_success(self, db, test_agent, test_user):
        """Test recording a successful metric."""
        service = ABTestingService(db)

        # Create and start test
        create_result = service.create_test(
            name="Metric Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate"
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Assign user
        service.assign_variant(test_id, test_user.id)

        # Record metric
        result = service.record_metric(
            test_id,
            test_user.id,
            success=True,
            metric_value=5.0
        )

        assert "error" not in result
        assert result["success"] is True
        assert result["metric_value"] == 5.0
        assert result["recorded_at"] is not None

    def test_record_metric_non_existent_participant(self, db, test_agent):
        """Test recording metric for non-existent participant."""
        service = ABTestingService(db)

        # Create and start test
        create_result = service.create_test(
            name="Metric Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate"
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Record metric without assigning
        result = service.record_metric(
            test_id,
            "non-existent-user",
            success=True,
            metric_value=5.0
        )

        assert "error" in result
        assert "not found" in result["error"].lower()


# ============================================================================
# Results and Analytics Tests
# ============================================================================

class TestResultsAnalytics:
    """Test results retrieval and statistical analysis."""

    def test_get_test_results_draft(self, db, test_agent):
        """Test getting results for draft test."""
        service = ABTestingService(db)

        # Create test
        create_result = service.create_test(
            name="Results Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate"
        )

        test_id = create_result["test_id"]

        # Get results
        result = service.get_test_results(test_id)

        assert "error" not in result
        assert result["status"] == "draft"
        assert result["variant_a"]["participant_count"] == 0
        assert result["variant_b"]["participant_count"] == 0

    def test_get_test_results_with_participants(self, db, test_agent):
        """Test getting results with participants."""
        service = ABTestingService(db)

        # Create test
        create_result = service.create_test(
            name="Results Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate",
            min_sample_size=10
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Add participants with metrics
        for i in range(20):
            user_id = f"user-{i}"
            variant_result = service.assign_variant(test_id, user_id)
            variant = variant_result["variant"]

            success = (variant == "B")  # Variant B performs better
            service.record_metric(
                test_id,
                user_id,
                success=success,
                metric_value=1.0 if success else 0.5
            )

        # Get results before completion
        result = service.get_test_results(test_id)

        assert "error" not in result
        assert result["status"] == "running"
        assert result["variant_a"]["participant_count"] > 0
        assert result["variant_b"]["participant_count"] > 0

    def test_list_tests_empty(self, db):
        """Test listing tests when no tests exist."""
        service = ABTestingService(db)

        result = service.list_tests()

        assert "total" in result
        assert "tests" in result
        assert result["total"] == 0
        assert len(result["tests"]) == 0

    def test_list_tests_with_filters(self, db, test_agent):
        """Test listing tests with filters."""
        service = ABTestingService(db)

        # Create multiple tests
        for i in range(3):
            service.create_test(
                name=f"Test {i}",
                test_type="prompt",
                agent_id=test_agent.id,
                variant_a_config={"prompt": "A"},
                variant_b_config={"prompt": "B"},
                primary_metric="satisfaction_rate"
            )

        # Start one test
        list_result = service.list_tests()
        test_id = list_result["tests"][0]["test_id"]
        service.start_test(test_id)

        # List all tests
        result = service.list_tests()
        assert result["total"] == 3

        # Filter by status
        result_running = service.list_tests(status="running")
        assert result_running["total"] == 1

        result_draft = service.list_tests(status="draft")
        assert result_draft["total"] == 2

        # Filter by agent
        result_agent = service.list_tests(agent_id=test_agent.id)
        assert result_agent["total"] == 3

    def test_statistical_significance(self, db, test_agent):
        """Test statistical significance calculation."""
        service = ABTestingService(db)

        # Create test with small sample size
        create_result = service.create_test(
            name="Significance Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"prompt": "A"},
            variant_b_config={"prompt": "B"},
            primary_metric="satisfaction_rate",
            min_sample_size=10
        )

        test_id = create_result["test_id"]
        service.start_test(test_id)

        # Add participants with clear winner
        for i in range(30):
            user_id = f"user-{i}"
            variant_result = service.assign_variant(test_id, user_id)
            variant = variant_result["variant"]

            # Variant B: 90% success, Variant A: 50% success
            if variant == "B":
                success = (i % 10 != 0)  # 90% success
            else:
                success = (i % 2 == 0)  # 50% success

            service.record_metric(test_id, user_id, success=success)

        # Complete and check results
        result = service.complete_test(test_id)

        assert "error" not in result
        assert result["min_sample_size_reached"] is True
        assert "variant_a_metrics" in result
        assert "variant_b_metrics" in result
        assert result["variant_a_metrics"]["success_rate"] < 0.6
        assert result["variant_b_metrics"]["success_rate"] > 0.8
        # Winner should be B (higher success rate)
        assert result["winner"] == "B"


# ============================================================================
# Integration Tests
# ============================================================================

class TestABTestingIntegration:
    """Integration tests for complete A/B testing workflows."""

    def test_full_ab_test_workflow(self, db, test_agent):
        """Test complete A/B test from creation to completion."""
        service = ABTestingService(db)

        # Step 1: Create test
        create_result = service.create_test(
            name="Full Workflow Test",
            test_type="prompt",
            agent_id=test_agent.id,
            variant_a_config={"system_prompt": "You are helpful."},
            variant_b_config={"system_prompt": "You are very helpful and detailed."},
            primary_metric="satisfaction_rate",
            min_sample_size=20,
            traffic_percentage=0.5
        )

        assert "error" not in create_result
        test_id = create_result["test_id"]

        # Step 2: Start test
        start_result = service.start_test(test_id)
        assert start_result["status"] == "running"

        # Step 3: Assign 50 users
        assignments = []
        for i in range(50):
            user_id = f"workflow-user-{i}"
            assign_result = service.assign_variant(test_id, user_id)
            assignments.append(assign_result["variant"])

        # Step 4: Record metrics
        for i, variant in enumerate(assignments):
            user_id = f"workflow-user-{i}"
            # Variant B performs better
            success = (variant == "B") if i % 2 == 0 else (variant == "A")
            service.record_metric(
                test_id,
                user_id,
                success=success,
                metric_value=5.0 if success else 3.0
            )

        # Step 5: Get interim results
        interim_results = service.get_test_results(test_id)
        assert interim_results["variant_a"]["participant_count"] > 0
        assert interim_results["variant_b"]["participant_count"] > 0

        # Step 6: Complete test
        final_results = service.complete_test(test_id)
        assert final_results["status"] == "completed"
        assert final_results["winner"] in ["A", "B", "inconclusive"]
        assert final_results["completed_at"] is not None

        # Step 7: Verify final results
        list_result = service.list_tests(status="completed")
        assert len([t for t in list_result["tests"] if t["test_id"] == test_id]) == 1

    def test_multiple_concurrent_tests(self, db, test_agent):
        """Test running multiple A/B tests concurrently."""
        service = ABTestingService(db)

        test_ids = []

        # Create 3 concurrent tests
        for i in range(3):
            create_result = service.create_test(
                name=f"Concurrent Test {i}",
                test_type="prompt",
                agent_id=test_agent.id,
                variant_a_config={"prompt": f"A{i}"},
                variant_b_config={"prompt": f"B{i}"},
                primary_metric="satisfaction_rate"
            )
            test_ids.append(create_result["test_id"])
            service.start_test(create_result["test_id"])

        # Assign users to each test
        for test_id in test_ids:
            for i in range(20):
                user_id = f"concurrent-user-{test_id}-{i}"
                service.assign_variant(test_id, user_id)

        # Verify all tests have participants
        for test_id in test_ids:
            results = service.get_test_results(test_id)
            assert results["variant_a"]["participant_count"] > 0
            assert results["variant_b"]["participant_count"] > 0
