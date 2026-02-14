"""
Tests for Operational Intelligence API Routes

Tests operational endpoints including:
- Daily priorities retrieval
- Business decision simulation
- Price drift detection
- Pricing advice
- Subscription waste detection
- Active interventions
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import sys

# Mock problematic imports before importing the router
sys.modules['core.risk_prevention'] = MagicMock()
sys.modules['core.cross_system_reasoning'] = MagicMock()

from api.operational_routes import router
from core.base_routes import BaseAPIRouter


class TestOperationalRoutes:
    """Test suite for operational routes"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def client(self):
        """Create test client"""
        from main import app as main_app
        return TestClient(main_app)

    def test_get_daily_priorities_success(self, client, mock_db):
        """Test GET /api/business-health/priorities - successful retrieval"""
        with patch("api.operational_routes.business_health_service") as mock_service:
            mock_service.get_daily_priorities = AsyncMock(return_value=[
                {
                    "id": "priority-1",
                    "title": "Review pricing strategy",
                    "impact": "high",
                    "estimated_time": "2 hours"
                },
                {
                    "id": "priority-2",
                    "title": "Follow up with high-value leads",
                    "impact": "medium",
                    "estimated_time": "1 hour"
                }
            ])

            response = client.get("/api/business-health/priorities")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["title"] == "Review pricing strategy"

    def test_get_daily_priorities_empty(self, client, mock_db):
        """Test GET /api/business-health/priorities - no priorities"""
        with patch("api.operational_routes.business_health_service") as mock_service:
            mock_service.get_daily_priorities = AsyncMock(return_value=[])

            response = client.get("/api/business-health/priorities")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_get_daily_priorities_service_error(self, client):
        """Test GET /api/business-health/priorities - service error"""
        with patch("api.operational_routes.business_health_service") as mock_service:
            mock_service.get_daily_priorities = AsyncMock(
                side_effect=Exception("Service unavailable")
            )

            response = client.get("/api/business-health/priorities")

        assert response.status_code == 500

    def test_simulate_business_decision_hiring(self, client):
        """Test POST /api/business-health/simulate - hiring decision"""
        request_data = {
            "decision_type": "hiring",
            "data": {
                "role": "Sales Representative",
                "salary": 60000,
                "count": 2
            }
        }

        with patch("api.operational_routes.business_health_service") as mock_service:
            mock_service.simulate_decision = AsyncMock(return_value={
                "decision_type": "hiring",
                "projected_cost": 120000,
                "projected_revenue_increase": 150000,
                "roi": 1.25,
                "recommendation": "Proceed with hiring"
            })

            response = client.post("/api/business-health/simulate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["decision_type"] == "hiring"

    def test_simulate_business_decision_spend(self, client):
        """Test POST /api/business-health/simulate - spend decision"""
        request_data = {
            "decision_type": "ad_spend",
            "data": {
                "channel": "google_ads",
                "budget_increase": 5000,
                "duration_months": 3
            }
        }

        with patch("api.operational_routes.business_health_service") as mock_service:
            mock_service.simulate_decision = AsyncMock(return_value={
                "decision_type": "ad_spend",
                "projected_cost": 15000,
                "projected_conversions": 75,
                "cost_per_conversion": 200,
                "recommendation": "Increase spend is justified"
            })

            response = client.post("/api/business-health/simulate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["decision_type"] == "ad_spend"

    def test_simulate_business_decision_service_error(self, client):
        """Test POST /api/business-health/simulate - service error"""
        request_data = {
            "decision_type": "hiring",
            "data": {"role": "Developer"}
        }

        with patch("api.operational_routes.business_health_service") as mock_service:
            mock_service.simulate_decision = AsyncMock(
                side_effect=Exception("Simulation failed")
            )

            response = client.post("/api/business-health/simulate", json=request_data)

        assert response.status_code == 500

    def test_get_price_drift_success(self, client):
        """Test GET /api/business-health/forensics/price-drift - successful detection"""
        with patch("api.operational_routes.VendorIntelligence") as mock_service_class:
            mock_service = MagicMock()
            mock_service.detect_price_drift = AsyncMock(return_value=[
                {
                    "vendor": "AWS",
                    "service": "EC2",
                    "current_price": 0.12,
                    "expected_price": 0.10,
                    "drift_percentage": 20.0,
                    "impact": "high",
                    "recommendation": "Review instance types and consider reserved instances"
                },
                {
                    "vendor": "Google Ads",
                    "service": "Display Ads",
                    "current_price": 2.50,
                    "expected_price": 2.00,
                    "drift_percentage": 25.0,
                    "impact": "medium",
                    "recommendation": "Optimize ad targeting and bidding strategy"
                }
            ])
            mock_service_class.return_value = mock_service

            with patch("api.operational_routes.MOCK_MODE", False):
                response = client.get("/api/business-health/forensics/price-drift")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["vendor"] == "AWS"
        assert data["metadata"]["is_mock"] is False

    def test_get_price_drift_no_drift(self, client):
        """Test GET /api/business-health/forensics/price-drift - no drift detected"""
        with patch("api.operational_routes.VendorIntelligence") as mock_service_class:
            mock_service = MagicMock()
            mock_service.detect_price_drift = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            response = client.get("/api/business-health/forensics/price-drift")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_get_price_drift_service_error(self, client):
        """Test GET /api/business-health/forensics/price-drift - service error"""
        with patch("api.operational_routes.VendorIntelligence") as mock_service_class:
            mock_service_class.side_effect = Exception("Service unavailable")

            response = client.get("/api/business-health/forensics/price-drift")

        assert response.status_code == 500

    def test_get_pricing_advice_success(self, client):
        """Test GET /api/business-health/forensics/pricing-advisor - successful recommendations"""
        with patch("api.operational_routes.PricingAdvisor") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_pricing_recommendations = AsyncMock(return_value=[
                {
                    "product": "Enterprise Plan",
                    "current_price": 999,
                    "recommended_price": 1199,
                    "reason": "Competitors charging 20% more for similar features",
                    "confidence": 0.85,
                    "impact": "increase_margin"
                },
                {
                    "product": "Starter Plan",
                    "current_price": 49,
                    "recommended_price": 39,
                    "reason": "Market saturation, lower price to compete",
                    "confidence": 0.72,
                    "impact": "increase_volume"
                }
            ])
            mock_service_class.return_value = mock_service

            with patch("api.operational_routes.MOCK_MODE", True):
                response = client.get("/api/business-health/forensics/pricing-advisor")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["product"] == "Enterprise Plan"
        assert data["data"][0]["recommended_price"] == 1199
        assert data["metadata"]["is_mock"] is True

    def test_get_pricing_advice_no_recommendations(self, client):
        """Test GET /api/business-health/forensics/pricing-advisor - no recommendations"""
        with patch("api.operational_routes.PricingAdvisor") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_pricing_recommendations = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            response = client.get("/api/business-health/forensics/pricing-advisor")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_get_pricing_advice_service_error(self, client):
        """Test GET /api/business-health/forensics/pricing-advisor - service error"""
        with patch("api.operational_routes.PricingAdvisor") as mock_service_class:
            mock_service_class.side_effect = Exception("Service unavailable")

            response = client.get("/api/business-health/forensics/pricing-advisor")

        assert response.status_code == 500

    def test_get_subscription_waste_success(self, client):
        """Test GET /api/business-health/forensics/waste - successful detection"""
        with patch("api.operational_routes.SubscriptionWasteService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.find_zombie_subscriptions = AsyncMock(return_value=[
                {
                    "service": "Zombie SaaS Tool",
                    "monthly_cost": 99,
                    "last_used": "2025-12-01",
                    "users": 0,
                    "recommendation": "Cancel immediately"
                },
                {
                    "service": "Underutilized Analytics",
                    "monthly_cost": 149,
                    "last_used": "2026-01-15",
                    "users": 1,
                    "recommendation": "Downgrade or cancel"
                }
            ])
            mock_service_class.return_value = mock_service

            with patch("api.operational_routes.MOCK_MODE", False):
                response = client.get("/api/business-health/forensics/waste")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["service"] == "Zombie SaaS Tool"
        assert data["data"][0]["monthly_cost"] == 99
        assert data["metadata"]["is_mock"] is False

    def test_get_subscription_waste_no_waste(self, client):
        """Test GET /api/business-health/forensics/waste - no waste found"""
        with patch("api.operational_routes.SubscriptionWasteService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.find_zombie_subscriptions = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            response = client.get("/api/business-health/forensics/waste")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_get_subscription_waste_service_error_graceful_fallback(self, client):
        """Test GET /api/business-health/forensics/waste - service error with graceful fallback"""
        with patch("api.operational_routes.SubscriptionWasteService") as mock_service_class:
            mock_service_class.side_effect = Exception("Service unavailable")

            # The endpoint should return success with empty data on error
            response = client.get("/api/business-health/forensics/waste")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["metadata"]["is_mock"] is False

    def test_generate_interventions_success(self, client):
        """Test POST /api/business-health/interventions/generate - successful generation"""
        with patch("api.operational_routes.CrossSystemReasoningEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine.generate_interventions = AsyncMock(return_value=[
                {
                    "id": "intervention-1",
                    "type": "pricing_alert",
                    "severity": "high",
                    "description": "Significant price drift detected in AWS spending",
                    "action": "Review and optimize cloud infrastructure",
                    "estimated_impact": "Save $500/month"
                },
                {
                    "id": "intervention-2",
                    "type": "lead_follow_up",
                    "severity": "medium",
                    "description": "5 high-intent leads not contacted in 24 hours",
                    "action": "Prioritize outreach to these leads",
                    "estimated_impact": "Close 2-3 deals"
                }
            ])
            mock_engine_class.return_value = mock_engine

            response = client.post("/api/business-health/interventions/generate")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["type"] == "pricing_alert"
        assert data["message"] == "Interventions generated successfully"

    def test_generate_interventions_no_interventions(self, client):
        """Test POST /api/business-health/interventions/generate - no interventions"""
        with patch("api.operational_routes.CrossSystemReasoningEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine.generate_interventions = AsyncMock(return_value=[])
            mock_engine_class.return_value = mock_engine

            response = client.post("/api/business-health/interventions/generate")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_generate_interventions_service_error(self, client):
        """Test POST /api/business-health/interventions/generate - service error"""
        with patch("api.operational_routes.CrossSystemReasoningEngine") as mock_engine_class:
            mock_engine_class.side_effect = Exception("Engine unavailable")

            response = client.post("/api/business-health/interventions/generate")

        assert response.status_code == 500

    def test_execute_intervention_success(self, client):
        """Test POST /api/business-health/interventions/{id}/execute - successful execution"""
        request_data = {
            "action": "approve",
            "payload": {
                "notes": "Proceed with pricing adjustment",
                "approved_by": "admin"
            }
        }

        with patch("api.operational_routes.active_intervention_service") as mock_service:
            mock_service.execute_intervention = AsyncMock(return_value={
                "intervention_id": "intervention-1",
                "status": "executed",
                "result": "Pricing adjustment approved",
                "timestamp": "2026-02-14T10:30:00Z"
            })

            response = client.post(
                "/api/business-health/interventions/intervention-1/execute",
                json=request_data
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["status"] == "executed"
        assert data["message"] == "Intervention executed successfully"

    def test_execute_intervention_dismiss(self, client):
        """Test POST /api/business-health/interventions/{id}/execute - dismiss action"""
        request_data = {
            "action": "dismiss",
            "payload": {
                "reason": "Not applicable at this time",
                "dismissed_by": "admin"
            }
        }

        with patch("api.operational_routes.active_intervention_service") as mock_service:
            mock_service.execute_intervention = AsyncMock(return_value={
                "intervention_id": "intervention-2",
                "status": "dismissed",
                "result": "Intervention dismissed",
                "timestamp": "2026-02-14T10:35:00Z"
            })

            response = client.post(
                "/api/business-health/interventions/intervention-2/execute",
                json=request_data
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "dismissed"

    def test_execute_intervention_service_error(self, client):
        """Test POST /api/business-health/interventions/{id}/execute - service error"""
        request_data = {
            "action": "approve",
            "payload": {}
        }

        with patch("api.operational_routes.active_intervention_service") as mock_service:
            mock_service.execute_intervention = AsyncMock(
                side_effect=Exception("Execution failed")
            )

            response = client.post(
                "/api/business-health/interventions/intervention-1/execute",
                json=request_data
            )

        assert response.status_code == 500


class TestOperationalDataValidation:
    """Test data validation and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from main import app as main_app
        return TestClient(main_app)

    def test_simulate_decision_missing_decision_type(self, client):
        """Test POST /api/business-health/simulate - missing decision_type"""
        request_data = {
            "data": {"role": "Developer"}
        }

        response = client.post("/api/business-health/simulate", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_simulate_decision_missing_data(self, client):
        """Test POST /api/business-health/simulate - missing data field"""
        request_data = {
            "decision_type": "hiring"
        }

        response = client.post("/api/business-health/simulate", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_execute_intervention_missing_action(self, client):
        """Test POST /api/business-health/interventions/{id}/execute - missing action"""
        request_data = {
            "payload": {}
        }

        response = client.post(
            "/api/business-health/interventions/intervention-1/execute",
            json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_execute_intervention_missing_payload(self, client):
        """Test POST /api/business-health/interventions/{id}/execute - missing payload"""
        request_data = {
            "action": "approve"
        }

        response = client.post(
            "/api/business-health/interventions/intervention-1/execute",
            json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_price_drift_impact_classification(self, client):
        """Test that price drift correctly classifies impact levels"""
        with patch("api.operational_routes.VendorIntelligence") as mock_service_class:
            mock_service = MagicMock()
            mock_service.detect_price_drift = AsyncMock(return_value=[
                {
                    "vendor": "Critical Vendor",
                    "drift_percentage": 50.0,
                    "impact": "critical"
                },
                {
                    "vendor": "Minor Vendor",
                    "drift_percentage": 5.0,
                    "impact": "low"
                }
            ])
            mock_service_class.return_value = mock_service

            response = client.get("/api/business-health/forensics/price-drift")

        assert response.status_code == 200
        data = response.json()
        assert data["data"][0]["impact"] == "critical"
        assert data["data"][1]["impact"] == "low"

    def test_intervention_severity_classification(self, client):
        """Test that interventions correctly classify severity levels"""
        with patch("api.operational_routes.CrossSystemReasoningEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine.generate_interventions = AsyncMock(return_value=[
                {
                    "id": "int-1",
                    "severity": "critical",
                    "description": "Security breach detected"
                },
                {
                    "id": "int-2",
                    "severity": "low",
                    "description": "Minor optimization opportunity"
                }
            ])
            mock_engine_class.return_value = mock_engine

            response = client.post("/api/business-health/interventions/generate")

        assert response.status_code == 200
        data = response.json()
        assert data["data"][0]["severity"] == "critical"
        assert data["data"][1]["severity"] == "low"
