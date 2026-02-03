"""
Tests for Analytics Dashboard API Routes
Tests all analytics, correlation, and prediction endpoints.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch
import pytest
from fastapi.testclient import TestClient

from api.analytics_dashboard_routes import router
from core.cross_platform_correlation import (
    CorrelationStrength,
    CrossPlatformCorrelationEngine,
    LinkedConversation,
)
from core.message_analytics_engine import MessageAnalyticsEngine, SentimentLevel
from core.predictive_insights import (
    PredictiveInsightsEngine,
    RecommendationConfidence,
    ResponseTimePrediction,
    UrgencyLevel,
)


@pytest.fixture
def client():
    """Create test client"""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_analytics_engine():
    """Mock message analytics engine"""
    engine = Mock(spec=MessageAnalyticsEngine)
    return engine


@pytest.fixture
def mock_correlation_engine():
    """Mock correlation engine"""
    engine = Mock(spec=CrossPlatformCorrelationEngine)
    return engine


@pytest.fixture
def mock_insights_engine():
    """Mock insights engine"""
    engine = Mock(spec=PredictiveInsightsEngine)
    return engine


class TestAnalyticsSummary:
    """Test analytics summary endpoint"""

    def test_get_analytics_summary(self, client):
        """Test getting analytics summary"""
        response = client.get("/api/analytics/summary?time_window=24h")

        assert response.status_code == 200
        data = response.json()

        assert "time_window" in data
        assert data["time_window"] == "24h"
        assert "message_stats" in data
        assert "response_times" in data
        assert "activity_peaks" in data
        assert "cross_platform" in data

    def test_get_analytics_summary_with_platform_filter(self, client):
        """Test analytics summary with platform filter"""
        response = client.get("/api/analytics/summary?time_window=7d&platform=slack")

        assert response.status_code == 200
        data = response.json()

        assert data["platform_filter"] == "slack"

    def test_get_analytics_summary_invalid_window(self, client):
        """Test with invalid time window (should still work)"""
        response = client.get("/api/analytics/summary?time_window=invalid")

        # Should still return 200 with default handling
        assert response.status_code == 200


class TestSentimentAnalysis:
    """Test sentiment analysis endpoint"""

    def test_get_sentiment_analysis(self, client):
        """Test getting sentiment analysis"""
        response = client.get("/api/analytics/sentiment?time_window=24h")

        assert response.status_code == 200
        data = response.json()

        assert "sentiment_distribution" in data
        assert "positive" in data["sentiment_distribution"]
        assert "negative" in data["sentiment_distribution"]
        assert "neutral" in data["sentiment_distribution"]

    def test_get_sentiment_with_platform(self, client):
        """Test sentiment analysis with platform filter"""
        response = client.get("/api/analytics/sentiment?platform=teams")

        assert response.status_code == 200
        data = response.json()

        assert data["platform"] == "teams"


class TestResponseTimeMetrics:
    """Test response time metrics endpoint"""

    def test_get_response_times(self, client):
        """Test getting response time metrics"""
        response = client.get("/api/analytics/response-times?time_window=7d")

        assert response.status_code == 200
        data = response.json()

        assert "avg_response_seconds" in data
        assert "median_response_seconds" in data
        assert "p95_response_seconds" in data
        assert "p99_response_seconds" in data

    def test_get_response_times_with_platform(self, client):
        """Test response times with platform filter"""
        response = client.get("/api/analytics/response-times?platform=gmail")

        assert response.status_code == 200
        data = response.json()

        assert data["platform"] == "gmail"


class TestActivityMetrics:
    """Test activity metrics endpoint"""

    def test_get_activity_metrics(self, client):
        """Test getting activity metrics"""
        response = client.get("/api/analytics/activity?period=daily")

        assert response.status_code == 200
        data = response.json()

        assert "period" in data
        assert data["period"] == "daily"
        assert "messages_per_day" in data
        assert "peak_days" in data

    def test_get_activity_metrics_hourly(self, client):
        """Test hourly activity metrics"""
        response = client.get("/api/analytics/activity?period=hourly")

        assert response.status_code == 200
        data = response.json()

        assert data["period"] == "hourly"
        assert "messages_per_hour" in data
        assert "peak_hours" in data


class TestCrossPlatformAnalytics:
    """Test cross-platform analytics endpoint"""

    def test_get_cross_platform_analytics(self, client):
        """Test getting cross-platform analytics"""
        response = client.get("/api/analytics/cross-platform?time_window=7d")

        assert response.status_code == 200
        data = response.json()

        assert "platforms" in data
        assert "slack" in data["platforms"]
        assert "teams" in data["platforms"]
        assert "gmail" in data["platforms"]
        assert "most_active_platform" in data

    def test_cross_platform_platform_stats(self, client):
        """Test individual platform stats"""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        data = response.json()

        slack_stats = data["platforms"]["slack"]
        assert "message_count" in slack_stats
        assert "sentiment" in slack_stats
        assert "avg_response_time" in slack_stats


class TestCorrelations:
    """Test cross-platform correlation endpoints"""

    def test_analyze_correlations(self, client):
        """Test analyzing correlations"""
        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Test message",
                "sender_name": "Alice",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "thread_id": "thread1"
            },
            {
                "id": "msg2",
                "platform": "teams",
                "content": "Related message",
                "sender_name": "Alice",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "thread_id": "thread2"
            }
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200
        data = response.json()

        assert "linked_conversations" in data
        assert "total_correlations" in data
        assert isinstance(data["linked_conversations"], list)

    def test_analyze_correlations_empty(self, client):
        """Test correlation analysis with empty message list"""
        response = client.post("/api/analytics/correlations", json=[])

        assert response.status_code == 200
        data = response.json()

        assert data["total_correlations"] == 0
        assert data["linked_conversations"] == []

    def test_get_unified_timeline(self, client):
        """Test getting unified timeline"""
        # First need to correlate to get a conversation ID
        messages = [
            {
                "id": "msg1",
                "platform": "slack",
                "content": "Message",
                "sender_name": "Alice",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "thread_id": "thread1"
            }
        ]

        correlation_response = client.post("/api/analytics/correlations", json=messages)
        assert correlation_response.status_code == 200

        # Try to get timeline (will likely return 404 with mock data)
        timeline_response = client.get("/api/analytics/correlations/nonexistent/timeline")

        # Should return 404 for non-existent conversation
        assert timeline_response.status_code in [404, 200]


class TestPredictions:
    """Test prediction endpoints"""

    def test_predict_response_time(self, client):
        """Test response time prediction"""
        response = client.get(
            "/api/analytics/predictions/response-time",
            params={
                "recipient": "Alice",
                "platform": "slack",
                "urgency": "medium"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "recipient" in data
        assert data["recipient"] == "Alice"
        assert "platform" in data
        assert "predicted_response_seconds" in data
        assert "predicted_response_minutes" in data
        assert "confidence" in data

    def test_predict_response_time_invalid_urgency(self, client):
        """Test prediction with invalid urgency"""
        response = client.get(
            "/api/analytics/predictions/response-time",
            params={
                "recipient": "Alice",
                "platform": "slack",
                "urgency": "invalid"
            }
        )

        assert response.status_code == 400

    def test_predict_with_urgency_levels(self, client):
        """Test different urgency levels"""
        for urgency in ["low", "medium", "high", "urgent"]:
            response = client.get(
                "/api/analytics/predictions/response-time",
                params={
                    "recipient": "Bob",
                    "platform": "teams",
                    "urgency": urgency
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["urgency"] == urgency


class TestRecommendations:
    """Test recommendation endpoints"""

    def test_recommend_channel(self, client):
        """Test channel recommendation"""
        response = client.get(
            "/api/analytics/recommendations/channel",
            params={
                "recipient": "Alice",
                "message_type": "general",
                "urgency": "medium"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "recipient" in data
        assert data["recipient"] == "Alice"
        assert "recommended_platform" in data
        assert "reason" in data
        assert "confidence" in data
        assert "alternatives" in data
        assert isinstance(data["alternatives"], list)

    def test_recommend_for_urgent_message(self, client):
        """Test recommendation for urgent message"""
        response = client.get(
            "/api/analytics/recommendations/channel",
            params={
                "recipient": "Bob",
                "urgency": "urgent"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Urgent recommendations should be provided
        assert data["recommended_platform"] is not None


class TestBottlenecks:
    """Test bottleneck detection endpoint"""

    def test_detect_bottlenecks(self, client):
        """Test bottleneck detection"""
        response = client.get("/api/analytics/bottlenecks?threshold_hours=24")

        assert response.status_code == 200
        data = response.json()

        assert "total_bottlenecks" in data
        assert "threshold_hours" in data
        assert data["threshold_hours"] == 24
        assert "bottlenecks" in data
        assert isinstance(data["bottlenecks"], list)

    def test_detect_bottlenecks_custom_threshold(self, client):
        """Test bottleneck detection with custom threshold"""
        response = client.get("/api/analytics/bottlenecks?threshold_hours=48")

        assert response.status_code == 200
        data = response.json()

        assert data["threshold_hours"] == 48

    def test_bottleneck_structure(self, client):
        """Test bottleneck data structure"""
        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        data = response.json()

        # Check structure (even if empty)
        assert isinstance(data["bottlenecks"], list)


class TestUserPatterns:
    """Test user patterns endpoint"""

    def test_get_user_patterns(self, client):
        """Test getting user patterns"""
        response = client.get("/api/analytics/patterns/Alice")

        # Will likely return 404 with mock data
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            assert "user_id" in data
            assert data["user_id"] == "Alice"
            assert "most_active_platform" in data
            assert "most_active_hours" in data
            assert "response_probability_by_hour" in data

    def test_get_user_patterns_not_found(self, client):
        """Test patterns for non-existent user"""
        response = client.get("/api/analytics/patterns/NonExistentUser")

        assert response.status_code == 404


class TestOverview:
    """Test overview endpoint"""

    def test_get_analytics_overview(self, client):
        """Test getting analytics overview"""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        data = response.json()

        assert "timestamp" in data
        assert "message_analytics" in data
        assert "predictive_insights" in data
        assert "cross_platform" in data
        assert "health_status" in data

    def test_overview_structure(self, client):
        """Test overview data structure"""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        data = response.json()

        # Check message analytics
        assert "total_messages" in data["message_analytics"]
        assert "active_threads" in data["message_analytics"]

        # Check predictive insights
        assert "users_analyzed" in data["predictive_insights"]
        assert "bottlenecks_detected" in data["predictive_insights"]

        # Check cross-platform
        assert "linked_conversations" in data["cross_platform"]


class TestErrorHandling:
    """Test error handling"""

    def test_invalid_query_params(self, client):
        """Test with invalid query parameters"""
        response = client.get("/api/analytics/summary?time_window=invalid")

        # Should handle gracefully
        assert response.status_code == 200

    def test_missing_required_params(self, client):
        """Test missing required parameters"""
        response = client.get("/api/analytics/predictions/response-time")

        # Should return 422 for missing required params
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
