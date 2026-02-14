"""
Tests for Marketing API Routes

Tests marketing endpoints including:
- Dashboard summary retrieval
- Lead scoring
- Reputation analysis
- GMB post suggestions
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.marketing_routes import router
from core.base_routes import BaseAPIRouter
from sales.models import Lead


class TestMarketingRoutes:
    """Test suite for marketing routes"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_user(self):
        """Mock current user"""
        user = Mock()
        user.id = "test-user-id"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def mock_lead(self):
        """Mock lead object"""
        lead = Mock(spec=Lead)
        lead.id = "lead-123"
        lead.email = "lead@example.com"
        lead.first_name = "John"
        lead.last_name = "Doe"
        lead.source = "website"
        lead.ai_score = 85.0
        lead.ai_qualification_summary = "High intent lead"
        return lead

    @pytest.fixture
    def mock_marketing_service(self):
        """Mock marketing intelligence service"""
        service = MagicMock()
        service.get_channel_performance = Mock(return_value=[
            {
                "channel_name": "google_ads",
                "leads": 50,
                "spend": 500.0,
                "conversions": 10,
                "conversion_rate": 0.2
            },
            {
                "channel_name": "facebook",
                "leads": 30,
                "spend": 300.0,
                "conversions": 5,
                "conversion_rate": 0.167
            }
        ])
        return service

    @pytest.fixture
    def client(self):
        """Create test client"""
        from main import app as main_app
        return TestClient(main_app)

    def test_get_marketing_summary_success(self, client, mock_db, mock_user, mock_lead):
        """Test GET /api/marketing/dashboard/summary - successful retrieval"""
        # Mock dependencies
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_lead]
        mock_db.query.return_value = mock_query

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_channel_performance.return_value = [
                    {
                        "channel_name": "google_ads",
                        "leads": 50,
                        "spend": 500.0,
                        "conversions": 10,
                        "conversion_rate": 0.2
                    }
                ]
                mock_service_class.return_value = mock_service

                with patch("api.marketing_routes.os.getenv") as mock_getenv:
                    mock_getenv.side_effect = lambda x, y=None: {
                        "MOCK_MODE_ENABLED": "true",
                        "GOOGLE_BUSINESS_API_KEY": None,
                        "GMB_CREDENTIALS": None
                    }.get(x, y)

                    with patch("api.marketing_routes.reporter") as mock_reporter:
                        mock_reporter.generate_narrative_report = AsyncMock(return_value="Marketing performance is strong with Google Ads leading conversions.")

                        response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert "narrative_report" in data
        assert "performance_metrics" in data
        assert "high_intent_leads" in data
        assert "gmb_status" in data
        assert "pending_reviews" in data
        assert "data_source" in data
        assert data["data_source"] == "mock"

    def test_get_marketing_summary_no_channels(self, client, mock_db, mock_user):
        """Test GET /api/marketing/dashboard/summary - no channels configured"""
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_channel_performance.return_value = []
                mock_service_class.return_value = mock_service

                with patch("api.marketing_routes.os.getenv") as mock_getenv:
                    mock_getenv.side_effect = lambda x, y=None: {
                        "MOCK_MODE_ENABLED": "false",
                        "GOOGLE_BUSINESS_API_KEY": None,
                        "GMB_CREDENTIALS": None
                    }.get(x, y)

                    with patch("api.marketing_routes.reporter") as mock_reporter:
                        mock_reporter.generate_narrative_report = AsyncMock(return_value="No data available")

                        response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["performance_metrics"] == {"no_data": {"leads": 0, "cost": 0, "conversions": 0}}
        assert data["high_intent_leads"] == []
        assert data["gmb_status"] == "not_configured"
        assert data["pending_reviews"] == "integration_required"

    def test_get_marketing_summary_gmb_configured(self, client, mock_db, mock_user):
        """Test GET /api/marketing/dashboard/summary - GMB configured"""
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_channel_performance.return_value = []
                mock_service_class.return_value = mock_service

                with patch("api.marketing_routes.os.getenv") as mock_getenv:
                    mock_getenv.side_effect = lambda x, y=None: {
                        "MOCK_MODE_ENABLED": "false",
                        "GOOGLE_BUSINESS_API_KEY": "test-key",
                        "GMB_CREDENTIALS": None
                    }.get(x, y)

                    with patch("api.marketing_routes.reporter") as mock_reporter:
                        mock_reporter.generate_narrative_report = AsyncMock(return_value="Report")

                        response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["gmb_status"] == "active"

    def test_get_marketing_summary_service_error(self, client, mock_db, mock_user):
        """Test GET /api/marketing/dashboard/summary - service error"""
        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service_class.side_effect = Exception("Service unavailable")

                response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 500

    def test_score_lead_success(self, client, mock_db, mock_user, mock_lead):
        """Test POST /api/marketing/leads/{lead_id}/score - successful scoring"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_lead
        mock_db.query.return_value = mock_query

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.marketing_manager") as mock_manager:
                mock_manager.lead_scoring.calculate_score = AsyncMock(return_value={
                    "score": 85.0,
                    "rationale": "High intent lead from website source"
                })

                response = client.post(f"/api/marketing/leads/{mock_lead.id}/score")

        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 85.0
        assert "rationale" in data
        mock_db.commit.assert_called_once()

    def test_score_lead_not_found(self, client, mock_db, mock_user):
        """Test POST /api/marketing/leads/{lead_id}/score - lead not found"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            response = client.post("/api/marketing/leads/nonexistent/score")

        assert response.status_code == 404

    def test_score_lead_service_error(self, client, mock_db, mock_user, mock_lead):
        """Test POST /api/marketing/leads/{lead_id}/score - service error"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_lead
        mock_db.query.return_value = mock_query

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.marketing_manager") as mock_manager:
                mock_manager.lead_scoring.calculate_score = AsyncMock(
                    side_effect=Exception("Scoring service unavailable")
                )

                response = client.post(f"/api/marketing/leads/{mock_lead.id}/score")

        assert response.status_code in [500, 202]  # May error or return partial result

    def test_analyze_reputation_success(self, client):
        """Test GET /api/marketing/reputation/analyze - successful analysis"""
        with patch("api.marketing_routes.reputation_manager") as mock_manager:
            mock_manager.determine_feedback_strategy = AsyncMock(return_value={
                "strategy": "public",
                "reasoning": "Positive interaction, suitable for public response"
            })

            response = client.get("/api/marketing/reputation/analyze?interaction=Great+service!")

        assert response.status_code == 200
        data = response.json()
        assert "strategy" in data

    def test_analyze_reputation_negative_interaction(self, client):
        """Test GET /api/marketing/reputation/analyze - negative interaction"""
        with patch("api.marketing_routes.reputation_manager") as mock_manager:
            mock_manager.determine_feedback_strategy = AsyncMock(return_value={
                "strategy": "private",
                "reasoning": "Negative interaction, respond privately to resolve"
            })

            response = client.get("/api/marketing/reputation/analyze?interaction=Very+disappointed+with+service")

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "private"

    def test_analyze_reputation_service_error(self, client):
        """Test GET /api/marketing/reputation/analyze - service error"""
        with patch("api.marketing_routes.reputation_manager") as mock_manager:
            mock_manager.determine_feedback_strategy = AsyncMock(
                side_effect=Exception("Analysis service unavailable")
            )

            response = client.get("/api/marketing/reputation/analyze?interaction=Test+interaction")

        assert response.status_code == 500

    def test_suggest_gmb_post_success(self, client):
        """Test GET /api/marketing/gmb/weekly-post/suggest - successful suggestion"""
        with patch("api.marketing_routes.marketing_manager") as mock_manager:
            mock_manager.gmb.generate_weekly_update = AsyncMock(
                return_value="Exciting news! We're open for business with new services available. Visit us today!"
            )

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={"business_name": "Test Business", "location": "San Francisco, CA"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "suggested_post" in data
        assert len(data["suggested_post"]) > 0

    def test_suggest_gmb_post_with_events(self, client):
        """Test GET /api/marketing/gmb/weekly-post/suggest - with custom events"""
        with patch("api.marketing_routes.marketing_manager") as mock_manager:
            mock_manager.gmb.generate_weekly_update = AsyncMock(
                return_value="Join us for our grand opening event this weekend!"
            )

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={
                    "business_name": "Test Business",
                    "location": "New York, NY",
                    "events": ["Grand Opening", "Live Music"]
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "suggested_post" in data

    def test_suggest_gmb_post_default_events(self, client):
        """Test GET /api/marketing/gmb/weekly-post/suggest - default events"""
        with patch("api.marketing_routes.marketing_manager") as mock_manager:
            mock_manager.gmb.generate_weekly_update = AsyncMock(
                return_value="Test Business is open for business with new services available!"
            )

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={"business_name": "Test Business", "location": "Austin, TX"}
            )

        assert response.status_code == 200
        # Should use default events if none provided
        mock_manager.gmb.generate_weekly_update.assert_called_once()

    def test_suggest_gmb_post_service_error(self, client):
        """Test GET /api/marketing/gmb/weekly-post/suggest - service error"""
        with patch("api.marketing_routes.marketing_manager") as mock_manager:
            mock_manager.gmb.generate_weekly_update = AsyncMock(
                side_effect=Exception("GMB service unavailable")
            )

            response = client.get(
                "/api/marketing/gmb/weekly-post/suggest",
                params={"business_name": "Test Business", "location": "Seattle, WA"}
            )

        assert response.status_code == 500


class TestMarketingDataValidation:
    """Test data validation and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from main import app as main_app
        return TestClient(main_app)

    def test_marketing_summary_high_intent_leads_format(self, client):
        """Test that high intent leads are properly formatted"""
        mock_lead = Mock(spec=Lead)
        mock_lead.id = "lead-123"
        mock_lead.email = "test@example.com"
        mock_lead.first_name = "Jane"
        mock_lead.last_name = "Smith"
        mock_lead.ai_score = 92.0
        mock_lead.ai_qualification_summary = "Very high intent"

        mock_db = Mock(spec=Session)
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_lead]
        mock_db.query.return_value = mock_query

        mock_user = Mock()
        mock_user.id = "test-user"

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_channel_performance.return_value = []
                mock_service_class.return_value = mock_service

                with patch("api.marketing_routes.os.getenv") as mock_getenv:
                    mock_getenv.return_value = "true"

                    with patch("api.marketing_routes.reporter") as mock_reporter:
                        mock_reporter.generate_narrative_report = AsyncMock(return_value="Report")

                        response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        leads = data["high_intent_leads"]
        assert len(leads) == 1
        assert leads[0]["id"] == "lead-123"
        assert leads[0]["name"] == "Jane Smith"
        assert leads[0]["score"] == 92.0
        assert leads[0]["summary"] == "Very high intent"

    def test_marketing_summary_lead_without_first_name(self, client):
        """Test that leads without first_name fall back to email"""
        mock_lead = Mock(spec=Lead)
        mock_lead.id = "lead-456"
        mock_lead.email = "no-name@example.com"
        mock_lead.first_name = None
        mock_lead.last_name = None
        mock_lead.ai_score = 75.0
        mock_lead.ai_qualification_summary = "Medium intent"

        mock_db = Mock(spec=Session)
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_lead]
        mock_db.query.return_value = mock_query

        mock_user = Mock()
        mock_user.id = "test-user"

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_channel_performance.return_value = []
                mock_service_class.return_value = mock_service

                with patch("api.marketing_routes.os.getenv") as mock_getenv:
                    mock_getenv.return_value = "true"

                    with patch("api.marketing_routes.reporter") as mock_reporter:
                        mock_reporter.generate_narrative_report = AsyncMock(return_value="Report")

                        response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        leads = data["high_intent_leads"]
        assert leads[0]["name"] == "no-name@example.com"

    def test_channel_performance_metrics_format(self, client):
        """Test that channel performance is correctly formatted"""
        mock_db = Mock(spec=Session)
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        mock_user = Mock()
        mock_user.id = "test-user"

        with patch("api.marketing_routes.get_current_user", return_value=mock_user):
            with patch("api.marketing_routes.MarketingIntelligenceService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.get_channel_performance.return_value = [
                    {
                        "channel_name": "email",
                        "leads": 100,
                        "spend": 50.0,
                        "conversions": 25,
                        "conversion_rate": 0.25
                    }
                ]
                mock_service_class.return_value = mock_service

                with patch("api.marketing_routes.os.getenv") as mock_getenv:
                    mock_getenv.return_value = "true"

                    with patch("api.marketing_routes.reporter") as mock_reporter:
                        mock_reporter.generate_narrative_report = AsyncMock(return_value="Report")

                        response = client.get("/api/marketing/dashboard/summary")

        assert response.status_code == 200
        data = response.json()
        metrics = data["performance_metrics"]
        assert "email" in metrics
        assert metrics["email"]["leads"] == 100
        assert metrics["email"]["cost"] == 50.0
        assert metrics["email"]["conversions"] == 25
        assert metrics["email"]["conversion_rate"] == 0.25
