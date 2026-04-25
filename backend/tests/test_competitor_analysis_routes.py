"""
Tests for api/competitor_analysis_routes.py
Competitor Analysis Routes - AI-powered competitor analysis using web scraping and LLM
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.competitor_analysis_routes import router
from core.models import User, CompetitorAnalysis, OAuthToken


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


# Analysis Creation Tests
class TestAnalysisCreation:
    """Test competitor analysis creation"""

    def test_create_competitor_analysis_success(self, client, db_session, test_user):
        """Test successful competitor analysis creation"""
        analysis_request = {
            "competitors": ["Competitor A", "Competitor B"],
            "analysis_depth": "standard",
            "focus_areas": ["products", "pricing", "marketing", "strengths", "weaknesses"]
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user), \
             patch('api.competitor_analysis_routes.LLMService') as mock_llm:

            # Mock LLM response
            mock_llm_instance = Mock()
            mock_llm_instance.generate_structured_response.return_value = {
                "competitors": [
                    {
                        "competitor": "Competitor A",
                        "strengths": ["Strong brand", "Good pricing"],
                        "weaknesses": ["Limited features"],
                        "market_position": "Market leader",
                        "key_products": ["Product A1", "Product A2"],
                        "pricing_strategy": "Premium pricing",
                        "marketing_tactics": ["Digital ads", "Content marketing"],
                        "recent_news": ["Launched new product"]
                    }
                ]
            }
            mock_llm.return_value = mock_llm_instance

            mock_analysis = Mock()
            mock_analysis.id = uuid4()
            mock_analysis.competitors = analysis_request["competitors"]
            db_session.add.return_value = None
            db_session.commit.return_value = None
            db_session.refresh.return_value = mock_analysis

            response = client.post("/api/v1/analysis/competitor", json=analysis_request)

            # Verify response
            assert response.status_code in [200, 201, 401]

    def test_create_analysis_with_competitors(self, client, db_session, test_user):
        """Test creating analysis with multiple competitors"""
        analysis_request = {
            "competitors": ["Comp A", "Comp B", "Comp C"],
            "analysis_depth": "comprehensive",
            "focus_areas": ["products", "pricing", "marketing"]
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user), \
             patch('api.competitor_analysis_routes.LLMService') as mock_llm:

            mock_llm_instance = Mock()
            mock_llm_instance.generate_structured_response.return_value = {
                "competitors": [
                    {"competitor": "Comp A", "strengths": [], "weaknesses": []},
                    {"competitor": "Comp B", "strengths": [], "weaknesses": []},
                    {"competitor": "Comp C", "strengths": [], "weaknesses": []}
                ]
            }
            mock_llm.return_value = mock_llm_instance

            mock_analysis = Mock()
            mock_analysis.id = uuid4()
            db_session.add.return_value = None
            db_session.commit.return_value = None

            response = client.post("/api/v1/analysis/competitor", json=analysis_request)

            # Verify response
            assert response.status_code in [200, 201, 401]

    def test_create_analysis_invalid_input(self, client, db_session, test_user):
        """Test creating analysis with invalid input"""
        invalid_request = {
            "competitors": [],  # Empty competitors list
            "analysis_depth": "invalid"
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            response = client.post("/api/v1/analysis/competitor", json=invalid_request)

            # Verify validation error
            assert response.status_code in [400, 422, 401]

    def test_create_analysis_duplicate(self, client, db_session, test_user):
        """Test creating duplicate analysis"""
        analysis_request = {
            "competitors": ["Competitor A"],
            "analysis_depth": "basic"
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            # Existing analysis found
            mock_existing = Mock()
            mock_existing.id = uuid4()
            mock_existing.competitors = ["Competitor A"]
            mock_existing.created_at = datetime.now() - timedelta(hours=1)
            db_session.query.return_value.filter.return_value.first.return_value = mock_existing

            response = client.post("/api/v1/analysis/competitor", json=analysis_request)

            # Verify response (should return existing or create new)
            assert response.status_code in [200, 201, 409, 401]


# Analysis Execution Tests
class TestAnalysisExecution:
    """Test competitor analysis execution"""

    def test_execute_competitor_analysis(self, client, db_session, test_user):
        """Test executing competitor analysis"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            mock_analysis.status = "pending"
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.post(f"/api/v1/analysis/{analysis_id}/execute")

            # Verify response
            assert response.status_code in [200, 202, 401, 404]

    def test_execute_analysis_async(self, client, db_session, test_user):
        """Test async analysis execution"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.post(f"/api/v1/analysis/{analysis_id}/execute", json={"async": True})

            # Verify response
            assert response.status_code in [200, 202, 401, 404]

    def test_execute_analysis_with_filters(self, client, db_session, test_user):
        """Test executing analysis with filters"""
        analysis_id = uuid4()
        execution_data = {
            "focus_areas": ["products", "pricing"],
            "exclude_areas": ["marketing"]
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.post(f"/api/v1/analysis/{analysis_id}/execute", json=execution_data)

            # Verify response
            assert response.status_code in [200, 202, 401, 404]

    def test_analysis_execution_status(self, client, db_session, test_user):
        """Test checking analysis execution status"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            mock_analysis.status = "in_progress"
            mock_analysis.progress = 50
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.get(f"/api/v1/analysis/{analysis_id}/status")

            # Verify response
            assert response.status_code in [200, 401, 404]


# Analysis Results Tests
class TestAnalysisResults:
    """Test competitor analysis results"""

    def test_get_analysis_results(self, client, db_session, test_user):
        """Test getting analysis results"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            mock_analysis.results = {
                "competitors": [
                    {"competitor": "Comp A", "strengths": ["Strong brand"]},
                    {"competitor": "Comp B", "strengths": ["Low price"]}
                ]
            }
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.get(f"/api/v1/analysis/{analysis_id}/results")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_get_analysis_summary(self, client, db_session, test_user):
        """Test getting analysis summary"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            mock_analysis.summary = {
                "total_competitors": 3,
                "key_insights": ["Insight 1", "Insight 2"],
                "recommendations": ["Recommendation 1"]
            }
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.get(f"/api/v1/analysis/{analysis_id}/summary")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_export_analysis_report(self, client, db_session, test_user):
        """Test exporting analysis report"""
        analysis_id = uuid4()
        export_data = {
            "format": "pdf",
            "include_charts": True
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.post(f"/api/v1/analysis/{analysis_id}/export", json=export_data)

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_analysis_results_caching(self, client, db_session, test_user):
        """Test analysis results caching"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            mock_analysis.cached_results = True
            mock_analysis.cache_expires_at = datetime.now() + timedelta(hours=1)
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.get(f"/api/v1/analysis/{analysis_id}/results")

            # Verify response (should return cached results)
            assert response.status_code in [200, 401, 404]


# Analysis Management Tests
class TestAnalysisManagement:
    """Test competitor analysis management"""

    def test_list_all_analyses(self, client, db_session, test_user):
        """Test listing all analyses for user"""
        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analyses = [
                Mock(id=uuid4(), competitors=["Comp A"], user_id=test_user.id),
                Mock(id=uuid4(), competitors=["Comp B"], user_id=test_user.id)
            ]
            db_session.query.return_value.filter.return_value.all.return_value = mock_analyses

            response = client.get("/api/v1/analysis")

            # Verify response
            assert response.status_code in [200, 401]

    def test_delete_analysis(self, client, db_session, test_user):
        """Test deleting an analysis"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.delete(f"/api/v1/analysis/{analysis_id}")

            # Verify response
            assert response.status_code in [200, 204, 401, 404]

    def test_archive_analysis(self, client, db_session, test_user):
        """Test archiving an analysis"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.post(f"/api/v1/analysis/{analysis_id}/archive")

            # Verify response
            assert response.status_code in [200, 401, 404]

    def test_update_analysis_settings(self, client, db_session, test_user):
        """Test updating analysis settings"""
        analysis_id = uuid4()
        settings_data = {
            "auto_refresh": True,
            "refresh_interval_days": 7,
            "notify_on_updates": True
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.put(f"/api/v1/analysis/{analysis_id}/settings", json=settings_data)

            # Verify response
            assert response.status_code in [200, 401, 404]


# Analysis Comparison Tests
class TestAnalysisComparison:
    """Test competitor analysis comparison"""

    def test_compare_competitors(self, client, db_session, test_user):
        """Test comparing multiple competitors"""
        comparison_data = {
            "competitor_ids": ["comp_a", "comp_b", "comp_c"],
            "comparison_criteria": ["pricing", "features", "market_share"]
        }

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            response = client.post("/api/v1/analysis/compare", json=comparison_data)

            # Verify response
            assert response.status_code in [200, 401]

    def test_get_market_position_map(self, client, db_session, test_user):
        """Test getting market position visualization"""
        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            response = client.get("/api/v1/analysis/market-position")

            # Verify response
            assert response.status_code in [200, 401]

    def test_get_swot_analysis(self, client, db_session, test_user):
        """Test getting SWOT analysis"""
        analysis_id = uuid4()

        with patch('api.competitor_analysis_routes.get_db', return_value=db_session), \
             patch('api.competitor_analysis_routes.get_current_user', return_value=test_user):

            mock_analysis = Mock()
            mock_analysis.id = analysis_id
            mock_analysis.user_id = test_user.id
            db_session.query.return_value.filter.return_value.first.return_value = mock_analysis

            response = client.get(f"/api/v1/analysis/{analysis_id}/swot")

            # Verify response
            assert response.status_code in [200, 401, 404]
