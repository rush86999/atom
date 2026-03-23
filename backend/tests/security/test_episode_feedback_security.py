"""
Episode Feedback Security Tests

Tests cover:
- Authentication requirement for episode feedback endpoint
- Input validation bounds for feedback_score
- Protection against importance score manipulation
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories.user_factory import UserFactory
from tests.security.conftest import create_test_token


class TestEpisodeFeedbackAuthentication:
    """Test authentication requirements for episode feedback."""

    def test_feedback_endpoint_requires_authentication(self, client: TestClient):
        """Test that unauthenticated requests are rejected."""
        response = client.post(
            "/api/episodes/test-episode-id/feedback",
            json={"feedback_score": 0.5}
        )

        # Should be unauthorized
        assert response.status_code in [401, 403]

    def test_feedback_endpoint_rejects_invalid_token(self, client: TestClient):
        """Test that invalid tokens are rejected."""
        response = client.post(
            "/api/episodes/test-episode-id/feedback",
            json={"feedback_score": 0.5},
            headers={"Authorization": "Bearer invalid_token"}
        )

        # Should be unauthorized
        assert response.status_code in [401, 403]


class TestEpisodeFeedbackInputValidation:
    """Test input validation for feedback scores."""

    def test_feedback_score_must_be_within_bounds(self, client: TestClient, db_session: Session):
        """Test that feedback_score must be between -1.0 and 1.0."""
        user = UserFactory(
            email="test@example.com",
            role="member",
            _session=db_session
        )

        # Test upper bound violation
        response = client.post(
            "/api/episodes/test-episode-id/feedback",
            json={"feedback_score": 1.5},
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be rejected (422 validation error)
        assert response.status_code == 422

    def test_feedback_score_rejects_extreme_values(self, client: TestClient, db_session: Session):
        """Test that extreme values (like the PoC 99999999.0) are rejected."""
        user = UserFactory(
            email="test2@example.com",
            role="member",
            _session=db_session
        )

        # Test extreme value from the vulnerability PoC
        response = client.post(
            "/api/episodes/test-episode-id/feedback",
            json={"feedback_score": 99999999.0},
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be rejected (422 validation error)
        assert response.status_code == 422

    def test_feedback_score_rejects_negative_extreme(self, client: TestClient, db_session: Session):
        """Test that extreme negative values are rejected."""
        user = UserFactory(
            email="test3@example.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/episodes/test-episode-id/feedback",
            json={"feedback_score": -99999999.0},
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be rejected (422 validation error)
        assert response.status_code == 422

    def test_feedback_score_accepts_valid_values(self, client: TestClient, db_session: Session):
        """Test that valid feedback scores are accepted."""
        from core.models import Episode
        import uuid

        user = UserFactory(
            email="test4@example.com",
            role="member",
            _session=db_session
        )

        # Create a test episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            session_id="test-session",
            title="Test Episode",
            importance_score=0.5,
            status="completed"
        )
        db_session.add(episode)
        db_session.commit()

        # Test valid boundary values
        for score in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            response = client.post(
                f"/api/episodes/{episode.id}/feedback",
                json={"feedback_score": score},
                headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
            )

            # Should accept valid scores (even if episode doesn't exist, validation comes first)
            # Note: May return 404 if episode doesn't exist, but NOT 422 for validation
            assert response.status_code in [200, 404]
            assert response.status_code != 422, f"Valid score {score} was rejected with 422"

    def test_feedback_score_rejects_wrong_type(self, client: TestClient, db_session: Session):
        """Test that non-numeric feedback_score is rejected."""
        user = UserFactory(
            email="test5@example.com",
            role="member",
            _session=db_session
        )

        response = client.post(
            "/api/episodes/test-episode-id/feedback",
            json={"feedback_score": "not_a_number"},
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be rejected (422 validation error)
        assert response.status_code == 422


class TestImportanceScoreManipulation:
    """Test protection against importance score manipulation attacks."""

    def test_cannot_max_out_importance_with_extreme_feedback(self, client: TestClient, db_session: Session):
        """
        Test that the vulnerability PoC no longer works.

        Before fix: Sending feedback_score=99999999.0 would force importance to 1.0
        After fix: Should be rejected at input validation layer
        """
        from core.models import Episode
        import uuid

        user = UserFactory(
            email="attacker@example.com",
            role="member",
            _session=db_session
        )

        # Create a test episode with low importance
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            session_id="test-session",
            title="Target Episode",
            importance_score=0.1,  # Low importance
            status="completed"
        )
        db_session.add(episode)
        db_session.commit()

        initial_score = episode.importance_score

        # Attempt the exploit from the PoC
        response = client.post(
            f"/api/episodes/{episode.id}/feedback",
            json={"feedback_score": 99999999.0},
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should be rejected at validation layer (422)
        assert response.status_code == 422

        # Verify importance score was NOT changed
        db_session.refresh(episode)
        assert episode.importance_score == initial_score
        assert episode.importance_score < 1.0

    def test_importance_score_updated_within_bounds(self, client: TestClient, db_session: Session):
        """
        Test that valid feedback correctly updates importance score.

        This ensures the fix doesn't break legitimate functionality.
        """
        from core.models import Episode
        import uuid

        user = UserFactory(
            email="user@example.com",
            role="member",
            _session=db_session
        )

        # Create a test episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            session_id="test-session",
            title="Test Episode",
            importance_score=0.5,
            status="completed"
        )
        db_session.add(episode)
        db_session.commit()

        # Submit positive feedback
        response = client.post(
            f"/api/episodes/{episode.id}/feedback",
            json={"feedback_score": 1.0},  # Maximum valid positive
            headers={"Authorization": f"Bearer {create_test_token(user.id)}"}
        )

        # Should succeed (200) or fail gracefully (404 if episode was deleted)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            # Verify importance score was updated
            db_session.refresh(episode)
            # New score should be higher due to positive feedback
            # Formula: new_importance = old * 0.8 + (feedback + 1.0) / 2.0 * 0.2
            # 0.5 * 0.8 + (1.0 + 1.0) / 2.0 * 0.2 = 0.4 + 1.0 * 0.2 = 0.6
            assert episode.importance_score > 0.5
            assert episode.importance_score <= 1.0  # Should never exceed 1.0


class TestFeedbackServiceValidation:
    """Test defensive validation in EpisodeLifecycleService."""

    def test_update_importance_scores_rejects_invalid_feedback(self, db_session: Session):
        """Test that update_importance_scores rejects out-of-bounds feedback."""
        from core.episode_lifecycle_service import EpisodeLifecycleService
        from core.models import Episode
        import uuid

        # Create a test episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            session_id="test-session",
            title="Test Episode",
            importance_score=0.5,
            status="completed"
        )
        db_session.add(episode)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Test that extreme positive value is rejected
        with pytest.raises(ValueError, match="Invalid feedback_score"):
            await service.update_importance_scores(episode.id, 99999999.0)

        # Test that extreme negative value is rejected
        with pytest.raises(ValueError, match="Invalid feedback_score"):
            await service.update_importance_scores(episode.id, -99999999.0)

        # Test that slightly out of bounds value is rejected
        with pytest.raises(ValueError, match="Invalid feedback_score"):
            await service.update_importance_scores(episode.id, 1.1)

        with pytest.raises(ValueError, match="Invalid feedback_score"):
            await service.update_importance_scores(episode.id, -1.1)

    def test_update_importance_scores_accepts_valid_bounds(self, db_session: Session):
        """Test that valid boundary values are accepted."""
        from core.episode_lifecycle_service import EpisodeLifecycleService
        from core.models import Episode
        import uuid

        # Create a test episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            session_id="test-session",
            title="Test Episode",
            importance_score=0.5,
            status="completed"
        )
        db_session.add(episode)
        db_session.commit()

        service = EpisodeLifecycleService(db_session)

        # Test boundary values
        for score in [-1.0, 0.0, 1.0]:
            result = await service.update_importance_scores(episode.id, score)
            assert result is True

            # Refresh to see updated score
            db_session.refresh(episode)
            assert 0.0 <= episode.importance_score <= 1.0
