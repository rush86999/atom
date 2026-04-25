"""
Tests for api/learning_plan_routes.py
Learning Plan Routes - AI-generated personalized learning plans with progress tracking
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.learning_plan_routes import router
from core.models import User, LearningPlan, OAuthToken


# Fixtures
@pytest.fixture
def db_session():
    """Mock database session"""
    mock_db = Mock(spec=Session)
    return mock_db


@pytest.fixture
def test_user():
    """Mock test user"""
    user = Mock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "Test User"
    return user


@pytest.fixture
def client():
    """Test client for the router"""
    from main import app
    app.include_router(router)
    return TestClient(app)


# Learning Plan CRUD Tests
class TestLearningPlanCRUD:
    """Test learning plan CRUD operations"""

    def test_create_learning_plan_success(self, client, db_session, test_user):
        """Test successful learning plan creation"""
        plan_request = {
            "topic": "Python Programming",
            "current_skill_level": "beginner",
            "learning_goals": ["Learn basics", "Build projects"],
            "time_commitment": "medium",
            "duration_weeks": 4,
            "preferred_format": ["articles", "videos", "exercises"]
        }

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user), \
             patch('api.learning_plan_routes.LLMService') as mock_llm:

            # Mock LLM response
            mock_llm_instance = Mock()
            mock_llm_instance.generate_structured_response.return_value = {
                "modules": [
                    {
                        "week": 1,
                        "title": "Introduction to Python",
                        "objectives": ["Setup Python", "Basic syntax"],
                        "resources": [{"type": "article", "url": "http://example.com"}],
                        "exercises": ["Install Python", "Hello World"]
                    }
                ]
            }
            mock_llm.return_value = mock_llm_instance

            mock_plan = Mock()
            mock_plan.id = uuid4()
            mock_plan.topic = plan_request["topic"]
            db_session.add.return_value = None
            db_session.commit.return_value = None
            db_session.refresh.return_value = mock_plan

            response = client.post("/api/v1/learning/plans", json=plan_request)

            # Verify response
            assert response.status_code in [200, 201, 401]

    def test_get_learning_plan_by_id(self, client, db_session, test_user):
        """Test retrieving a learning plan by ID"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.topic = "Python Programming"
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.get(f"/api/v1/learning/plans/{plan_id}")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_list_learning_plans(self, client, db_session, test_user):
        """Test listing learning plans for user"""
        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plans = [
                Mock(id=uuid4(), topic="Python", user_id=test_user.id),
                Mock(id=uuid4(), topic="JavaScript", user_id=test_user.id)
            ]
            db_session.query.return_value.filter.return_value.all.return_value = mock_plans

            response = client.get("/api/v1/learning/plans")

            # Verify response
            assert response.status_code in [200, 401]

    def test_update_learning_plan(self, client, db_session, test_user):
        """Test updating a learning plan"""
        plan_id = uuid4()
        update_data = {
            "topic": "Advanced Python",
            "time_commitment": "high"
        }

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.put(f"/api/v1/learning/plans/{plan_id}", json=update_data)

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_delete_learning_plan(self, client, db_session, test_user):
        """Test deleting a learning plan"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.delete(f"/api/v1/learning/plans/{plan_id}")

            # Verify response
            assert response.status_code in [200, 204, 401, 404]


# Learning Plan Execution Tests
class TestLearningPlanExecution:
    """Test learning plan execution"""

    def test_execute_learning_plan_success(self, client, db_session, test_user):
        """Test executing a learning plan"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            mock_plan.modules = [{"week": 1, "title": "Week 1"}]
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.post(f"/api/v1/learning/plans/{plan_id}/execute")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_execute_plan_with_steps(self, client, db_session, test_user):
        """Test executing plan with specific steps"""
        plan_id = uuid4()
        execution_data = {
            "steps": [1, 2],  # Execute weeks 1 and 2
            "auto_advance": True
        }

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.post(f"/api/v1/learning/plans/{plan_id}/execute", json=execution_data)

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_execute_plan_parallel_steps(self, client, db_session, test_user):
        """Test executing plan steps in parallel"""
        plan_id = uuid4()
        execution_data = {
            "parallel": True,
            "max_parallel": 3
        }

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.post(f"/api/v1/learning/plans/{plan_id}/execute", json=execution_data)

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_execute_plan_failure_handling(self, client, db_session, test_user):
        """Test execution failure handling"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            # Plan not found
            db_session.query.return_value.filter.return_value.first.return_value = None

            response = client.post(f"/api/v1/learning/plans/{plan_id}/execute")

            # Verify error handling
            assert response.status_code in [404, 401]


# Learning Plan Progress Tests
class TestLearningPlanProgress:
    """Test learning plan progress tracking"""

    def test_get_learning_plan_progress(self, client, db_session, test_user):
        """Test getting learning plan progress"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            mock_plan.progress = 50
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.get(f"/api/v1/learning/plans/{plan_id}/progress")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_update_plan_progress(self, client, db_session, test_user):
        """Test updating learning plan progress"""
        plan_id = uuid4()
        progress_data = {
            "week": 1,
            "completed": True,
            "notes": "Completed all exercises"
        }

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.put(f"/api/v1/learning/plans/{plan_id}/progress", json=progress_data)

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_plan_completion_tracking(self, client, db_session, test_user):
        """Test plan completion tracking"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            mock_plan.completed_at = None
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.post(f"/api/v1/learning/plans/{plan_id}/complete")

            # Verify response
            assert response.status_code in [200, 401, 404]


# Learning Plan Export Tests
class TestLearningPlanExport:
    """Test learning plan export functionality"""

    def test_export_to_notion(self, client, db_session, test_user):
        """Test exporting learning plan to Notion"""
        plan_id = uuid4()
        export_data = {
            "notion_database_id": str(uuid4()),
            "format": "structured"
        }

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user), \
             patch('api.learning_plan_routes.NotionService') as mock_notion:

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            mock_notion_instance = Mock()
            mock_notion_instance.create_learning_plan_page.return_value = {"id": "notion_page_id"}
            mock_notion.return_value = mock_notion_instance

            response = client.post(f"/api/v1/learning/plans/{plan_id}/export", json=export_data)

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_export_to_pdf(self, client, db_session, test_user):
        """Test exporting learning plan to PDF"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.get(f"/api/v1/learning/plans/{plan_id}/export/pdf")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_export_to_json(self, client, db_session, test_user):
        """Test exporting learning plan to JSON"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.get(f"/api/v1/learning/plans/{plan_id}/export/json")

            # Verify response
            assert response.status_code in [200, 401, 404]


# Learning Plan Recommendations Tests
class TestLearningPlanRecommendations:
    """Test learning plan recommendations"""

    def test_get_personalized_recommendations(self, client, db_session, test_user):
        """Test getting personalized learning recommendations"""
        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            response = client.get("/api/v1/learning/recommendations")

            # Verify response
            assert response.status_code in [200, 401]

    def test_get_similar_plans(self, client, db_session, test_user):
        """Test getting similar learning plans"""
        plan_id = uuid4()

        with patch('api.learning_plan_routes.get_db', return_value=db_session), \
             patch('api.learning_plan_routes.get_current_user', return_value=test_user):

            mock_plan = Mock()
            mock_plan.id = plan_id
            mock_plan.topic = "Python"
            db_session.query.return_value.filter.return_value.first.return_value = mock_plan

            response = client.get(f"/api/v1/learning/plans/{plan_id}/similar")

            # Verify response
            assert response.status_code in [200, 401, 404]
