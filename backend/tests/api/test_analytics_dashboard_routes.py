"""
Analytics Dashboard Routes Unit Tests

Tests for analytics dashboard APIs including:
- Analytics summary and overview
- Sentiment analysis
- Response time metrics
- Activity metrics
- Cross-platform analytics
- Cross-platform correlations
- Unified timeline
- Predictive insights (response time, channel recommendation)
- Bottleneck detection
- User patterns

Coverage: Analytics dashboard routes (507 lines)
Tests: 25-30 comprehensive tests
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from api.analytics_dashboard_routes import router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for analytics dashboard routes."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_message_analytics():
    """Create mock MessageAnalyticsEngine."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_correlation_engine():
    """Create mock CrossPlatformCorrelationEngine."""
    mock = MagicMock()
    mock.cross_platform_links = []
    mock.linked_conversations = []
    return mock


@pytest.fixture
def mock_insights_engine():
    """Create mock PredictiveInsightsEngine."""
    mock = MagicMock()

    # Mock response time prediction
    from core.predictive_insights import ResponseTimePrediction, ConfidenceLevel
    mock_prediction = MagicMock(spec=ResponseTimePrediction)
    mock_prediction.user_id = "user-123"
    mock_prediction.predicted_seconds = 3600  # 1 hour
    mock_prediction.confidence = ConfidenceLevel.HIGH
    mock_prediction.factors = ["time_of_day", "day_of_week"]

    # Mock channel recommendation
    from core.predictive_insights import ChannelRecommendation
    mock_recommendation = MagicMock(spec=ChannelRecommendation)
    mock_recommendation.user_id = "user-123"
    mock_recommendation.recommended_platform = "slack"
    mock_recommendation.reason = "User typically responds within minutes on Slack"
    mock_recommendation.confidence = ConfidenceLevel.HIGH
    mock_recommendation.expected_response_time = 300  # 5 minutes
    mock_recommendation.alternatives = ["teams", "email"]

    # Mock user pattern
    from core.predictive_insights import UserCommunicationPattern
    mock_pattern = MagicMock(spec=UserCommunicationPattern)
    mock_pattern.user_id = "user-123"
    mock_pattern.most_active_platform = "slack"
    mock_pattern.most_active_hours = [9, 10, 11, 14, 15, 16]
    mock_pattern.avg_response_time = 300
    mock_pattern.response_probability_by_hour = {i: 0.8 for i in range(9, 17)}
    mock_pattern.preferred_message_types = ["direct_message", "channel_mention"]

    mock.predict_response_time.return_value = mock_prediction
    mock.recommend_channel.return_value = mock_recommendation
    mock.get_user_pattern.return_value = mock_pattern

    # Mock insights summary
    mock.get_insights_summary.return_value = {
        "users_analyzed": 150,
        "bottlenecks_detected": 5,
        "avg_response_time_all_users": 450
    }

    return mock


# ============================================================================
# GET /analytics/summary - Analytics Summary Tests
# ============================================================================

def test_get_analytics_summary_default(client):
    """Test getting analytics summary with default time window."""
    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    data = response.json()
    assert "time_window" in data
    assert data["time_window"] == "24h"
    assert "message_stats" in data
    assert "response_times" in data
    assert "activity_peaks" in data
    assert "cross_platform" in data


def test_get_analytics_summary_with_platform(client):
    """Test getting analytics summary filtered by platform."""
    response = client.get("/api/analytics/summary?platform=slack")

    assert response.status_code == 200
    data = response.json()
    assert data["platform_filter"] == "slack"


@pytest.mark.parametrize("time_window", ["24h", "7d", "30d", "all"])
def test_get_analytics_summary_time_windows(client, time_window):
    """Test analytics summary with different time windows."""
    response = client.get(f"/analytics/summary?time_window={time_window}")

    assert response.status_code == 200
    assert response.json()["time_window"] == time_window


# ============================================================================
# GET /analytics/sentiment - Sentiment Analysis Tests
# ============================================================================

def test_get_sentiment_analysis_default(client):
    """Test getting sentiment analysis with defaults."""
    response = client.get("/api/analytics/sentiment")

    assert response.status_code == 200
    data = response.json()
    assert "sentiment_distribution" in data
    assert "positive" in data["sentiment_distribution"]
    assert "negative" in data["sentiment_distribution"]
    assert "neutral" in data["sentiment_distribution"]
    assert "sentiment_trend" in data


def test_get_sentiment_analysis_with_platform(client):
    """Test sentiment analysis filtered by platform."""
    response = client.get("/api/analytics/sentiment?platform=gmail")

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "gmail"


def test_get_sentiment_analysis_time_window(client):
    """Test sentiment analysis with time window."""
    response = client.get("/api/analytics/sentiment?time_window=7d")

    assert response.status_code == 200
    assert response.json()["time_window"] == "7d"


# ============================================================================
# GET /analytics/response-times - Response Time Metrics Tests
# ============================================================================

def test_get_response_time_metrics_default(client):
    """Test getting response time metrics."""
    response = client.get("/api/analytics/response-times")

    assert response.status_code == 200
    data = response.json()
    assert "avg_response_seconds" in data
    assert "median_response_seconds" in data
    assert "p95_response_seconds" in data
    assert "p99_response_seconds" in data
    assert data["time_window"] == "7d"


def test_get_response_time_metrics_with_platform(client):
    """Test response time metrics for specific platform."""
    response = client.get("/api/analytics/response-times?platform=teams")

    assert response.status_code == 200
    assert response.json()["platform"] == "teams"


def test_get_response_time_metrics_custom_window(client):
    """Test response time metrics with custom time window."""
    response = client.get("/api/analytics/response-times?time_window=30d")

    assert response.status_code == 200
    assert response.json()["time_window"] == "30d"


# ============================================================================
# GET /analytics/activity - Activity Metrics Tests
# ============================================================================

def test_get_activity_metrics_default(client):
    """Test getting activity metrics."""
    response = client.get("/api/analytics/activity")

    assert response.status_code == 200
    data = response.json()
    assert "messages_per_hour" in data
    assert "messages_per_day" in data
    assert "messages_per_channel" in data
    assert "peak_hours" in data
    assert "peak_days" in data
    assert data["period"] == "daily"


@pytest.mark.parametrize("period", ["hourly", "daily", "weekly"])
def test_get_activity_metrics_periods(client, period):
    """Test activity metrics with different periods."""
    response = client.get(f"/analytics/activity?period={period}")

    assert response.status_code == 200
    assert response.json()["period"] == period


def test_get_activity_metrics_with_platform(client):
    """Test activity metrics filtered by platform."""
    response = client.get("/api/analytics/activity?platform=slack&period=hourly")

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "slack"
    assert data["period"] == "hourly"


# ============================================================================
# GET /analytics/cross-platform - Cross-Platform Analytics Tests
# ============================================================================

def test_get_cross_platform_analytics_default(client):
    """Test getting cross-platform analytics."""
    response = client.get("/api/analytics/cross-platform")

    assert response.status_code == 200
    data = response.json()
    assert "platforms" in data
    assert "slack" in data["platforms"]
    assert "teams" in data["platforms"]
    assert "gmail" in data["platforms"]
    assert "most_active_platform" in data
    assert data["time_window"] == "7d"


def test_get_cross_platform_analytics_structure(client):
    """Test cross-platform analytics data structure."""
    response = client.get("/api/analytics/cross-platform")

    data = response.json()["platforms"]

    # Check slack platform structure
    slack_data = data["slack"]
    assert "message_count" in slack_data
    assert "sentiment" in slack_data
    assert "avg_response_time" in slack_data

    # Check sentiment structure
    assert "positive" in slack_data["sentiment"]
    assert "negative" in slack_data["sentiment"]
    assert "neutral" in slack_data["sentiment"]


# ============================================================================
# POST /analytics/correlations - Cross-Platform Correlations Tests
# ============================================================================

def test_analyze_cross_platform_correlations(client, mock_correlation_engine):
    """Test analyzing cross-platform correlations."""
    # Create mock linked conversation with simple dict
    mock_conv = MagicMock()
    mock_conv.conversation_id = "conv-123"
    mock_conv.platforms = {"slack", "email"}
    mock_conv.participants = {"user1", "user2"}
    mock_conv.message_count = 15
    mock_conv.correlation_strength.value = "strong"
    mock_conv.unified_messages = [
        {"platform": "slack", "content": "Message 1"},
        {"platform": "email", "content": "Message 2"}
    ]

    mock_correlation_engine.correlate_conversations.return_value = [mock_conv]
    mock_correlation_engine.cross_platform_links = []

    messages = [
        {"platform": "slack", "sender": "user1", "content": "Hello"},
        {"platform": "email", "sender": "user2", "content": "Hi there"}
    ]

    response = client.post("/api/analytics/correlations", json=messages)

    assert response.status_code == 200
    data = response.json()
    assert "linked_conversations" in data
    assert data["total_correlations"] == 1
    assert len(data["linked_conversations"]) == 1


def test_analyze_correlations_empty(client, mock_correlation_engine):
    """Test correlating with no messages."""
    mock_correlation_engine.correlate_conversations.return_value = []

    response = client.post("/api/analytics/correlations", json=[])

    assert response.status_code == 200
    data = response.json()
    assert data["total_correlations"] == 0


# ============================================================================
# GET /analytics/correlations/{conversation_id}/timeline - Unified Timeline Tests
# ============================================================================

def test_get_unified_timeline_success(client, mock_correlation_engine):
    """Test getting unified timeline for a conversation."""
    mock_correlation_engine.get_unified_timeline.return_value = [
        {
            "id": "msg-1",
            "platform": "slack",
            "content": "First message",
            "sender_name": "Alice",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_correlation_source": "slack"
        },
        {
            "id": "msg-2",
            "platform": "email",
            "content": "Follow-up",
            "sender": "Bob",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_correlation_source": "email"
        }
    ]

    response = client.get("/api/analytics/correlations/conv-123/timeline")

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "conv-123"
    assert data["message_count"] == 2
    assert len(data["messages"]) == 2


def test_get_unified_timeline_not_found(client, mock_correlation_engine):
    """Test getting timeline for non-existent conversation."""
    mock_correlation_engine.get_unified_timeline.return_value = None

    response = client.get("/api/analytics/correlations/nonexistent/timeline")

    assert response.status_code == 404


# ============================================================================
# GET /analytics/predictions/response-time - Response Time Prediction Tests
# ============================================================================

def test_predict_response_time_success(client, mock_insights_engine):
    """Test predicting response time successfully."""
    response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack&urgency=medium")

    assert response.status_code == 200
    data = response.json()
    assert data["recipient"] == "user-123"
    assert data["platform"] == "slack"
    assert data["urgency"] == "medium"
    assert "predicted_response_seconds" in data
    assert "predicted_response_minutes" in data
    assert "confidence" in data
    assert data["predicted_response_minutes"] == 60.0


@pytest.mark.parametrize("urgency", ["low", "medium", "high", "urgent"])
def test_predict_response_time_urgency_levels(client, mock_insights_engine, urgency):
    """Test response time prediction with different urgency levels."""
    response = client.get(f"/analytics/predictions/response-time?recipient=user-123&platform=slack&urgency={urgency}")

    assert response.status_code == 200
    assert response.json()["urgency"] == urgency


def test_predict_response_time_invalid_urgency(client):
    """Test response time prediction with invalid urgency."""
    response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack&urgency=invalid")

    # Should return 400 for invalid urgency
    assert response.status_code == 400


# ============================================================================
# GET /analytics/recommendations/channel - Channel Recommendation Tests
# ============================================================================

def test_recommend_channel_success(client, mock_insights_engine):
    """Test getting channel recommendation successfully."""
    response = client.get("/api/analytics/recommendations/channel?recipient=user-123&message_type=general&urgency=medium")

    assert response.status_code == 200
    data = response.json()
    assert data["recipient"] == "user-123"
    assert data["recommended_platform"] == "slack"
    assert "reason" in data
    assert "confidence" in data
    assert "expected_response_time_minutes" in data
    assert "alternatives" in data
    assert len(data["alternatives"]) == 2


def test_recommend_channel_different_message_types(client, mock_insights_engine):
    """Test channel recommendations for different message types."""
    message_types = ["general", "urgent", "informative", "question"]

    for msg_type in message_types:
        response = client.get(f"/analytics/recommendations/channel?recipient=user-123&message_type={msg_type}&urgency=medium")

        assert response.status_code == 200
        assert response.json()["recipient"] == "user-123"


def test_recommend_channel_invalid_urgency(client):
    """Test channel recommendation with invalid urgency."""
    response = client.get("/api/analytics/recommendations/channel?recipient=user-123&message_type=general&urgency=invalid")

    assert response.status_code == 400


# ============================================================================
# GET /analytics/bottlenecks - Bottleneck Detection Tests
# ============================================================================

def test_detect_bottlenecks_default(client, mock_insights_engine):
    """Test detecting communication bottlenecks with default threshold."""
    # Create simple mock bottleneck
    mock_bottleneck = MagicMock()
    mock_bottleneck.severity.value = "high"
    mock_bottleneck.thread_id = "thread-123"
    mock_bottleneck.platform = "email"
    mock_bottleneck.description = "No response for 48 hours"
    mock_bottleneck.affected_users = ["alice", "bob"]
    mock_bottleneck.wait_time_seconds = 48 * 3600
    mock_bottleneck.suggested_action = "Send follow-up reminder"

    mock_insights_engine.detect_bottlenecks.return_value = [mock_bottleneck]

    response = client.get("/api/analytics/bottlenecks")

    assert response.status_code == 200
    data = response.json()
    assert data["total_bottlenecks"] == 1
    assert data["threshold_hours"] == 24.0
    assert len(data["bottlenecks"]) == 1


def test_detect_bottlenecks_custom_threshold(client, mock_insights_engine):
    """Test detecting bottlenecks with custom threshold."""
    mock_insights_engine.detect_bottlenecks.return_value = []

    response = client.get("/api/analytics/bottlenecks?threshold_hours=12")

    assert response.status_code == 200
    assert response.json()["threshold_hours"] == 12


def test_detect_bottlenecks_structure(client, mock_insights_engine):
    """Test bottleneck data structure."""
    # Create simple mock bottleneck
    mock_bottleneck = MagicMock()
    mock_bottleneck.severity.value = "medium"
    mock_bottleneck.thread_id = "thread-456"
    mock_bottleneck.platform = "slack"
    mock_bottleneck.description = "Slow response"
    mock_bottleneck.affected_users = ["charlie"]
    mock_bottleneck.wait_time_seconds = 18 * 3600
    mock_bottleneck.suggested_action = "Escalate to manager"

    mock_insights_engine.detect_bottlenecks.return_value = [mock_bottleneck]

    response = client.get("/api/analytics/bottlenecks?threshold_hours=24")

    data = response.json()["bottlenecks"][0]
    assert data["severity"] == "medium"
    assert data["thread_id"] == "thread-456"
    assert data["platform"] == "slack"
    assert data["wait_time_hours"] == 18.0


# ============================================================================
# GET /analytics/patterns/{user_id} - User Patterns Tests
# ============================================================================

def test_get_user_patterns_success(client, mock_insights_engine):
    """Test getting user communication patterns."""
    response = client.get("/api/analytics/patterns/user-123")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-123"
    assert "most_active_platform" in data
    assert "most_active_hours" in data
    assert "avg_response_time_minutes" in data
    assert "response_probability_by_hour" in data
    assert "preferred_message_types" in data


def test_get_user_patterns_structure(client, mock_insights_engine):
    """Test user patterns data structure."""
    response = client.get("/api/analytics/patterns/user-123")

    data = response.json()
    assert data["most_active_platform"] == "slack"
    assert 9 in data["most_active_hours"]
    assert data["avg_response_time_minutes"] == 5.0  # 300 seconds / 60
    assert len(data["response_probability_by_hour"]) > 0
    assert len(data["preferred_message_types"]) > 0


def test_get_user_patterns_not_found(client, mock_insights_engine):
    """Test getting patterns for non-existent user."""
    mock_insights_engine.get_user_pattern.return_value = None

    response = client.get("/api/analytics/patterns/nonexistent")

    assert response.status_code == 404


# ============================================================================
# GET /analytics/overview - Analytics Overview Tests
# ============================================================================

def test_get_analytics_overview(client, mock_message_analytics, mock_insights_engine, mock_correlation_engine):
    """Test getting high-level analytics overview."""
    mock_correlation_engine.linked_conversations = []
    mock_correlation_engine.cross_platform_links = []

    response = client.get("/api/analytics/overview")

    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data
    assert "message_analytics" in data
    assert "predictive_insights" in data
    assert "cross_platform" in data
    assert "health_status" in data


def test_get_analytics_overview_structure(client, mock_message_analytics, mock_insights_engine, mock_correlation_engine):
    """Test analytics overview data structure."""
    mock_correlation_engine.linked_conversations = []
    mock_correlation_engine.cross_platform_links = []

    response = client.get("/api/analytics/overview")

    data = response.json()

    # Check message analytics
    assert "total_messages" in data["message_analytics"]
    assert "platforms_active" in data["message_analytics"]

    # Check predictive insights
    assert "users_analyzed" in data["predictive_insights"]
    assert "bottlenecks_detected" in data["predictive_insights"]

    # Check cross-platform
    assert "linked_conversations" in data["cross_platform"]
    assert "cross_platform_links" in data["cross_platform"]


def test_get_analytics_overview_with_data(client, mock_message_analytics, mock_insights_engine, mock_correlation_engine):
    """Test analytics overview with actual data."""
    # Create simple mock linked conversation
    mock_conv = MagicMock()
    mock_conv.conversation_id = "conv-1"

    mock_correlation_engine.linked_conversations = [mock_conv]
    mock_correlation_engine.cross_platform_links = [("slack", "email")]

    response = client.get("/api/analytics/overview")

    data = response.json()
    assert data["cross_platform"]["linked_conversations"] == 1
    assert data["cross_platform"]["cross_platform_links"] == 1


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_internal_error_handling(client):
    """Test that internal errors are handled gracefully."""
    with patch('api.analytics_dashboard_routes.get_message_analytics_engine') as mock_get:
        mock_get.side_effect = Exception("Engine failure")

        response = client.get("/api/analytics/summary")

        # Should return 500 with error message
        assert response.status_code == 500
        assert "error" in response.json()


def test_missing_query_parameter(client):
    """Test endpoints with missing required query parameters."""
    # Missing required parameter 'recipient'
    response = client.get("/api/analytics/predictions/response-time?platform=slack")

    assert response.status_code == 422  # Validation error
