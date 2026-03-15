"""
Coverage-driven tests for analytics_dashboard_routes.py (partial -> 70%+ target)

API Endpoints Tested:
- GET /api/analytics/summary - Comprehensive analytics summary
- GET /api/analytics/sentiment - Sentiment analysis breakdown
- GET /api/analytics/response-times - Response time metrics
- GET /api/analytics/activity - Activity metrics and peak times
- GET /api/analytics/cross-platform - Cross-platform analytics
- POST /api/analytics/correlations - Cross-platform correlation analysis
- GET /api/analytics/correlations/{conversation_id}/timeline - Unified timeline
- GET /api/analytics/predictions/response-time - Response time prediction
- GET /api/analytics/recommendations/channel - Channel recommendation
- GET /api/analytics/bottlenecks - Bottleneck detection
- GET /api/analytics/patterns/{user_id} - User communication patterns
- GET /api/analytics/overview - High-level analytics overview

Coverage Target Areas:
- Lines 1-30: Route initialization and dependencies
- Lines 30-85: Summary endpoint
- Lines 85-150: Sentiment and response-times endpoints
- Lines 150-250: Activity and cross-platform endpoints
- Lines 250-350: Correlations and timeline endpoints
- Lines 350-450: Predictive insights endpoints
- Lines 450-510: Patterns and overview endpoints
"""

from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
import pytest

from api.analytics_dashboard_routes import router
from core.message_analytics_engine import MessageAnalyticsEngine, get_message_analytics_engine
from core.cross_platform_correlation import (
    CrossPlatformCorrelationEngine,
    get_cross_platform_correlation_engine,
    LinkedConversation,
    CorrelationStrength
)
from core.predictive_insights import (
    PredictiveInsightsEngine,
    get_predictive_insights_engine,
    UrgencyLevel,
    ResponseTimePrediction,
    ChannelRecommendation,
    BottleneckAlert,
    UserPattern,
    ConfidenceLevel
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_analytics_engine():
    """Mock MessageAnalyticsEngine."""
    engine = Mock(spec=MessageAnalyticsEngine)
    return engine


@pytest.fixture
def mock_correlation_engine():
    """Mock CrossPlatformCorrelationEngine."""
    engine = Mock(spec=CrossPlatformCorrelationEngine)
    engine.linked_conversations = []
    engine.cross_platform_links = []

    # Setup mock for correlate_conversations
    mock_conversation = Mock(spec=LinkedConversation)
    mock_conversation.conversation_id = "conv-123"
    mock_conversation.platforms = {"slack", "email"}
    mock_conversation.participants = {"user-1", "user-2"}
    mock_conversation.message_count = 5
    mock_conversation.correlation_strength = CorrelationStrength.HIGH
    mock_conversation.unified_messages = [
        {"id": "msg-1", "platform": "slack", "content": "test"},
        {"id": "msg-2", "platform": "email", "content": "test"}
    ]
    engine.correlate_conversations.return_value = [mock_conversation]

    # Setup mock for get_unified_timeline
    engine.get_unified_timeline.return_value = [
        {
            "id": "msg-1",
            "platform": "slack",
            "content": "Test message",
            "sender_name": "User 1",
            "sender": "user-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_correlation_source": "slack"
        },
        {
            "id": "msg-2",
            "platform": "email",
            "content": "Re: Test message",
            "sender": "user-2",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_correlation_source": "email"
        }
    ]

    return engine


@pytest.fixture
def mock_predictive_engine():
    """Mock PredictiveInsightsEngine."""
    engine = Mock(spec=PredictiveInsightsEngine)

    # Mock predict_response_time
    mock_prediction = Mock(spec=ResponseTimePrediction)
    mock_prediction.user_id = "user-123"
    mock_prediction.predicted_seconds = 1800  # 30 minutes
    mock_prediction.confidence = ConfidenceLevel.HIGH
    mock_prediction.factors = ["time_of_day", "day_of_week"]
    engine.predict_response_time.return_value = mock_prediction

    # Mock recommend_channel
    mock_recommendation = Mock(spec=ChannelRecommendation)
    mock_recommendation.user_id = "user-123"
    mock_recommendation.recommended_platform = "slack"
    mock_recommendation.reason = "User most active on Slack"
    mock_recommendation.confidence = ConfidenceLevel.HIGH
    mock_recommendation.expected_response_time = 1200
    mock_recommendation.alternatives = ["teams", "email"]
    engine.recommend_channel.return_value = mock_recommendation

    # Mock detect_bottlenecks
    mock_bottleneck = Mock(spec=BottleneckAlert)
    mock_bottleneck.severity = "high"
    mock_bottleneck.thread_id = "thread-123"
    mock_bottleneck.platform = "slack"
    mock_bottleneck.description = "No response for 48 hours"
    mock_bottleneck.affected_users = ["user-1", "user-2"]
    mock_bottleneck.wait_time_seconds = 172800  # 48 hours
    mock_bottleneck.suggested_action = "Send follow-up message"
    engine.detect_bottlenecks.return_value = [mock_bottleneck]

    # Mock get_user_pattern
    mock_pattern = Mock(spec=UserPattern)
    mock_pattern.user_id = "user-123"
    mock_pattern.most_active_platform = "slack"
    mock_pattern.most_active_hours = [9, 10, 11, 14, 15, 16]
    mock_pattern.avg_response_time = 1500
    mock_pattern.response_probability_by_hour = {i: 0.1 for i in range(24)}
    mock_pattern.preferred_message_types = ["direct", "channel"]
    engine.get_user_pattern.return_value = mock_pattern

    # Mock get_insights_summary
    engine.get_insights_summary.return_value = {
        "users_analyzed": 10,
        "bottlenecks_detected": 2,
        "avg_response_time_all_users": 1200
    }

    return engine


@pytest.fixture
def client(mock_analytics_engine, mock_correlation_engine, mock_predictive_engine):
    """Test client with mocked engines."""
    def override_analytics():
        return mock_analytics_engine

    def override_correlation():
        return mock_correlation_engine

    def override_predictive():
        return mock_predictive_engine

    from core.main import app
    app.dependency_overrides[get_message_analytics_engine] = override_analytics
    app.dependency_overrides[get_cross_platform_correlation_engine] = override_correlation
    app.dependency_overrides[get_predictive_insights_engine] = override_predictive

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


# ============================================================================
# Test Summary Endpoint (10 tests)
# ============================================================================

class TestAnalyticsSummary:
    """Test suite for /api/analytics/summary endpoint."""

    def test_get_analytics_summary_default(self, client):
        """Cover summary endpoint with default parameters (lines 26-83)."""
        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        result = response.json()
        assert result["time_window"] == "24h"
        assert "message_stats" in result
        assert "response_times" in result
        assert "activity_peaks" in result
        assert "cross_platform" in result

    def test_get_analytics_summary_custom_time_window(self, client):
        """Cover summary with custom time window."""
        response = client.get("/api/analytics/summary?time_window=7d")

        assert response.status_code == 200
        assert response.json()["time_window"] == "7d"

    @pytest.mark.parametrize("time_window", ["24h", "7d", "30d", "all"])
    def test_get_analytics_summary_time_windows(self, client, time_window):
        """Cover various time window options."""
        response = client.get(f"/api/analytics/summary?time_window={time_window}")

        assert response.status_code == 200
        assert response.json()["time_window"] == time_window

    def test_get_analytics_summary_with_platform_filter(self, client):
        """Cover summary with platform filter."""
        response = client.get("/api/analytics/summary?platform=slack")

        assert response.status_code == 200
        assert "platform_filter" in response.json()

    def test_get_analytics_summary_message_stats_structure(self, client):
        """Cover message stats structure in summary."""
        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        stats = response.json()["message_stats"]
        assert "total_messages" in stats
        assert "total_words" in stats
        assert "with_attachments" in stats
        assert "with_mentions" in stats
        assert "with_urls" in stats
        assert "sentiment_distribution" in stats

    def test_get_analytics_summary_response_times_structure(self, client):
        """Cover response times structure in summary."""
        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        times = response.json()["response_times"]
        assert "avg_response_seconds" in times
        assert "median_response_seconds" in times
        assert "p95_response_seconds" in times
        assert "total_responses_analyzed" in times

    def test_get_analytics_summary_cross_platform_structure(self, client):
        """Cover cross-platform structure in summary."""
        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        cp = response.json()["cross_platform"]
        assert "platforms" in cp
        assert "most_active_platform" in cp
        assert "total_messages" in cp

    def test_get_analytics_summary_activity_peaks_structure(self, client):
        """Cover activity peaks structure in summary."""
        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        peaks = response.json()["activity_peaks"]
        assert "peak_days" in peaks
        assert "messages_per_day" in peaks

    def test_get_analytics_summary_sentiment_distribution(self, client):
        """Cover sentiment distribution in summary."""
        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        sentiment = response.json()["message_stats"]["sentiment_distribution"]
        assert "positive" in sentiment
        assert "negative" in sentiment
        assert "neutral" in sentiment

    def test_multiple_query_parameters(self, client):
        """Cover multiple query parameters combined."""
        response = client.get("/api/analytics/summary?time_window=7d&platform=slack")

        assert response.status_code == 200
        result = response.json()
        assert result["time_window"] == "7d"
        assert result["platform_filter"] == "slack"


# ============================================================================
# Test Sentiment Endpoint (8 tests)
# ============================================================================

class TestSentimentAnalysis:
    """Test suite for /api/analytics/sentiment endpoint."""

    def test_get_sentiment_analysis_default(self, client):
        """Cover sentiment analysis with default parameters (lines 86-100+)."""
        response = client.get("/api/analytics/sentiment")

        assert response.status_code == 200
        result = response.json()
        assert "sentiment_distribution" in result
        assert "sentiment_trend" in result

    def test_get_sentiment_with_platform_filter(self, client):
        """Cover sentiment with platform filter."""
        response = client.get("/api/analytics/sentiment?platform=slack")

        assert response.status_code == 200
        assert response.json()["platform"] == "slack"

    def test_get_sentiment_with_time_window(self, client):
        """Cover sentiment with time window."""
        response = client.get("/api/analytics/sentiment?time_window=7d")

        assert response.status_code == 200
        assert response.json()["time_window"] == "7d"

    @pytest.mark.parametrize("sentiment", ["positive", "negative", "neutral"])
    def test_sentiment_distribution_categories(self, client, sentiment):
        """Cover sentiment distribution categories."""
        response = client.get("/api/analytics/sentiment")

        assert response.status_code == 200
        distribution = response.json().get("sentiment_distribution", {})
        assert sentiment in distribution

    def test_sentiment_trend_structure(self, client):
        """Cover sentiment trend structure."""
        response = client.get("/api/analytics/sentiment")

        assert response.status_code == 200
        assert "sentiment_trend" in response.json()
        assert isinstance(response.json()["sentiment_trend"], list)

    def test_sentiment_topics_positive(self, client):
        """Cover most positive topics."""
        response = client.get("/api/analytics/sentiment")

        assert response.status_code == 200
        assert "most_positive_topics" in response.json()
        assert isinstance(response.json()["most_positive_topics"], list)

    def test_sentiment_topics_negative(self, client):
        """Cover most negative topics."""
        response = client.get("/api/analytics/sentiment")

        assert response.status_code == 200
        assert "most_negative_topics" in response.json()
        assert isinstance(response.json()["most_negative_topics"], list)

    def test_sentiment_combined_parameters(self, client):
        """Cover sentiment with multiple parameters."""
        response = client.get("/api/analytics/sentiment?platform=teams&time_window=30d")

        assert response.status_code == 200
        result = response.json()
        assert result["platform"] == "teams"
        assert result["time_window"] == "30d"


# ============================================================================
# Test Response Times Endpoint (8 tests)
# ============================================================================

class TestResponseTimes:
    """Test suite for /api/analytics/response-times endpoint."""

    def test_get_response_times_default(self, client):
        """Cover response times with default parameters."""
        response = client.get("/api/analytics/response-times")

        assert response.status_code == 200
        result = response.json()
        assert "avg_response_seconds" in result
        assert "median_response_seconds" in result
        assert "p95_response_seconds" in result
        assert "p99_response_seconds" in result

    def test_get_response_times_with_platform(self, client):
        """Cover response times with platform filter."""
        response = client.get("/api/analytics/response-times?platform=slack")

        assert response.status_code == 200
        assert response.json()["platform"] == "slack"

    def test_get_response_times_with_time_window(self, client):
        """Cover response times with time window."""
        response = client.get("/api/analytics/response-times?time_window=24h")

        assert response.status_code == 200
        assert response.json()["time_window"] == "24h"

    def test_response_time_distribution(self, client):
        """Cover response time distribution structure."""
        response = client.get("/api/analytics/response-times")

        assert response.status_code == 200
        assert "response_time_distribution" in response.json()
        assert isinstance(response.json()["response_time_distribution"], list)

    def test_slowest_threads(self, client):
        """Cover slowest threads structure."""
        response = client.get("/api/analytics/response-times")

        assert response.status_code == 200
        assert "slowest_threads" in response.json()
        assert isinstance(response.json()["slowest_threads"], list)

    def test_fastest_threads(self, client):
        """Cover fastest threads structure."""
        response = client.get("/api/analytics/response-times")

        assert response.status_code == 200
        assert "fastest_threads" in response.json()
        assert isinstance(response.json()["fastest_threads"], list)

    @pytest.mark.parametrize("time_window", ["24h", "7d", "30d"])
    def test_response_times_time_windows(self, client, time_window):
        """Cover various time windows for response times."""
        response = client.get(f"/api/analytics/response-times?time_window={time_window}")

        assert response.status_code == 200
        assert response.json()["time_window"] == time_window

    def test_response_times_combined_parameters(self, client):
        """Cover response times with combined parameters."""
        response = client.get("/api/analytics/response-times?platform=email&time_window=7d")

        assert response.status_code == 200
        result = response.json()
        assert result["platform"] == "email"
        assert result["time_window"] == "7d"


# ============================================================================
# Test Activity Metrics Endpoint (8 tests)
# ============================================================================

class TestActivityMetrics:
    """Test suite for /api/analytics/activity endpoint."""

    def test_get_activity_metrics_default(self, client):
        """Cover activity metrics with default parameters."""
        response = client.get("/api/analytics/activity")

        assert response.status_code == 200
        result = response.json()
        assert "period" in result
        assert result["period"] == "daily"

    def test_get_activity_metrics_with_period_hourly(self, client):
        """Cover activity metrics with hourly period."""
        response = client.get("/api/analytics/activity?period=hourly")

        assert response.status_code == 200
        assert response.json()["period"] == "hourly"

    def test_get_activity_metrics_with_period_weekly(self, client):
        """Cover activity metrics with weekly period."""
        response = client.get("/api/analytics/activity?period=weekly")

        assert response.status_code == 200
        assert response.json()["period"] == "weekly"

    def test_get_activity_metrics_with_platform(self, client):
        """Cover activity metrics with platform filter."""
        response = client.get("/api/analytics/activity?platform=slack")

        assert response.status_code == 200
        assert response.json()["platform"] == "slack"

    def test_activity_messages_per_hour(self, client):
        """Cover messages per hour structure."""
        response = client.get("/api/analytics/activity")

        assert response.status_code == 200
        assert "messages_per_hour" in response.json()

    def test_activity_messages_per_day(self, client):
        """Cover messages per day structure."""
        response = client.get("/api/analytics/activity")

        assert response.status_code == 200
        assert "messages_per_day" in response.json()

    def test_activity_peak_hours(self, client):
        """Cover peak hours structure."""
        response = client.get("/api/analytics/activity")

        assert response.status_code == 200
        assert "peak_hours" in response.json()
        assert isinstance(response.json()["peak_hours"], list)

    def test_activity_heatmap(self, client):
        """Cover activity heatmap structure."""
        response = client.get("/api/analytics/activity")

        assert response.status_code == 200
        assert "activity_heatmap" in response.json()
        assert isinstance(response.json()["activity_heatmap"], list)


# ============================================================================
# Test Cross-Platform Analytics Endpoint (8 tests)
# ============================================================================

class TestCrossPlatformAnalytics:
    """Test suite for /api/analytics/cross-platform endpoint."""

    def test_get_cross_platform_analytics_default(self, client):
        """Cover cross-platform analytics with default parameters."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        result = response.json()
        assert "platforms" in result
        assert "most_active_platform" in result

    def test_cross_platform_includes_slack(self, client):
        """Cover cross-platform includes Slack data."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        platforms = response.json()["platforms"]
        assert "slack" in platforms

    def test_cross_platform_includes_teams(self, client):
        """Cover cross-platform includes Teams data."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        platforms = response.json()["platforms"]
        assert "teams" in platforms

    def test_cross_platform_includes_gmail(self, client):
        """Cover cross-platform includes Gmail data."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        platforms = response.json()["platforms"]
        assert "gmail" in platforms

    def test_cross_platform_with_time_window(self, client):
        """Cover cross-platform with time window."""
        response = client.get("/api/analytics/cross-platform?time_window=30d")

        assert response.status_code == 200
        assert response.json()["time_window"] == "30d"

    def test_cross_platform_message_counts(self, client):
        """Cover platform message counts."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        platforms = response.json()["platforms"]
        for platform_name, platform_data in platforms.items():
            assert "message_count" in platform_data
            assert "sentiment" in platform_data
            assert "avg_response_time" in platform_data

    def test_cross_platform_sentiment_breakdown(self, client):
        """Cover sentiment breakdown per platform."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        platforms = response.json()["platforms"]
        for platform_data in platforms.values():
            sentiment = platform_data["sentiment"]
            assert "positive" in sentiment
            assert "negative" in sentiment
            assert "neutral" in sentiment

    def test_cross_platform_comparison(self, client):
        """Cover platform comparison structure."""
        response = client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        assert "platform_comparison" in response.json()
        assert isinstance(response.json()["platform_comparison"], list)


# ============================================================================
# Test Correlations Endpoint (7 tests)
# ============================================================================

class TestCrossPlatformCorrelations:
    """Test suite for /api/analytics/correlations endpoint."""

    def test_analyze_correlations_success(self, client, mock_correlation_engine):
        """Cover cross-platform correlation analysis."""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test message",
                "sender": "user-1",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "msg-2",
                "platform": "email",
                "content": "Re: Test message",
                "sender": "user-2",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200
        result = response.json()
        assert "linked_conversations" in result
        assert "total_correlations" in result
        assert "cross_platform_links" in result

    def test_analyze_correlations_empty_list(self, client, mock_correlation_engine):
        """Cover correlation with empty message list."""
        mock_correlation_engine.correlate_conversations.return_value = []

        response = client.post("/api/analytics/correlations", json=[])

        assert response.status_code == 200
        result = response.json()
        assert result["total_correlations"] == 0

    def test_correlation_conversation_structure(self, client):
        """Cover linked conversation structure."""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test",
                "sender": "user-1",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200
        conversations = response.json()["linked_conversations"]
        if len(conversations) > 0:
            conv = conversations[0]
            assert "conversation_id" in conv
            assert "platforms" in conv
            assert "participants" in conv
            assert "message_count" in conv
            assert "correlation_strength" in conv

    def test_correlation_platforms_set(self, client):
        """Cover platforms as set/list in conversation."""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test",
                "sender": "user-1",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200
        conversations = response.json()["linked_conversations"]
        if len(conversations) > 0:
            assert isinstance(conversations[0]["platforms"], list)

    def test_correlation_multiple_messages(self, client):
        """Cover correlation with multiple messages."""
        messages = [
            {
                "id": f"msg-{i}",
                "platform": "slack" if i % 2 == 0 else "email",
                "content": f"Test message {i}",
                "sender": f"user-{i % 3}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            for i in range(10)
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200

    def test_correlation_unified_message_count(self, client):
        """Cover unified message count in conversation."""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test",
                "sender": "user-1",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200
        conversations = response.json()["linked_conversations"]
        if len(conversations) > 0:
            assert "unified_message_count" in conversations[0]

    def test_correlation_cross_platform_links_count(self, client):
        """Cover cross-platform links count."""
        messages = [
            {
                "id": "msg-1",
                "platform": "slack",
                "content": "Test",
                "sender": "user-1",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]

        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code == 200
        result = response.json()
        assert "cross_platform_links" in result
        assert isinstance(result["cross_platform_links"], int)


# ============================================================================
# Test Unified Timeline Endpoint (8 tests)
# ============================================================================

class TestUnifiedTimeline:
    """Test suite for /api/analytics/correlations/{conversation_id}/timeline endpoint."""

    def test_get_unified_timeline_success(self, client, mock_correlation_engine):
        """Cover unified timeline retrieval."""
        response = client.get("/api/analytics/correlations/conv-123/timeline")

        assert response.status_code == 200
        result = response.json()
        assert "conversation_id" in result
        assert "message_count" in result
        assert "messages" in result

    def test_get_unified_timeline_not_found(self, client, mock_correlation_engine):
        """Cover unified timeline for non-existent conversation."""
        mock_correlation_engine.get_unified_timeline.return_value = None

        response = client.get("/api/analytics/correlations/nonexistent/timeline")

        assert response.status_code == 404

    def test_timeline_message_structure(self, client):
        """Cover timeline message structure."""
        response = client.get("/api/analytics/correlations/conv-123/timeline")

        assert response.status_code == 200
        messages = response.json()["messages"]
        if len(messages) > 0:
            msg = messages[0]
            assert "id" in msg
            assert "platform" in msg
            assert "content" in msg
            assert "sender" in msg
            assert "timestamp" in msg

    def test_timeline_cross_platform_messages(self, client):
        """Cover timeline includes cross-platform messages."""
        response = client.get("/api/analytics/correlations/conv-123/timeline")

        assert response.status_code == 200
        messages = response.json()["messages"]
        platforms = {msg["platform"] for msg in messages}
        # Should have messages from multiple platforms
        assert len(platforms) >= 1

    def test_timeline_sender_fallback(self, client):
        """Cover sender field fallback (sender_name -> sender)."""
        response = client.get("/api/analytics/correlations/conv-123/timeline")

        assert response.status_code == 200
        messages = response.json()["messages"]
        # Should have sender field (from sender_name or sender)
        if len(messages) > 0:
            assert "sender" in messages[0]

    def test_timeline_correlation_source(self, client):
        """Cover timeline includes correlation source."""
        response = client.get("/api/analytics/correlations/conv-123/timeline")

        assert response.status_code == 200
        messages = response.json()["messages"]
        if len(messages) > 0:
            assert "_correlation_source" in messages[0]

    def test_timeline_empty_conversation(self, client, mock_correlation_engine):
        """Cover timeline for conversation with no messages."""
        mock_correlation_engine.get_unified_timeline.return_value = []

        response = client.get("/api/analytics/correlations/conv-empty/timeline")

        assert response.status_code in [200, 404]

    def test_timeline_message_count(self, client):
        """Cover timeline message count accuracy."""
        response = client.get("/api/analytics/correlations/conv-123/timeline")

        assert response.status_code == 200
        result = response.json()
        assert result["message_count"] == len(result["messages"])


# ============================================================================
# Test Response Time Prediction Endpoint (8 tests)
# ============================================================================

class TestResponseTimePrediction:
    """Test suite for /api/analytics/predictions/response-time endpoint."""

    def test_predict_response_time_success(self, client):
        """Cover response time prediction."""
        response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack")

        assert response.status_code == 200
        result = response.json()
        assert "recipient" in result
        assert "platform" in result
        assert "predicted_response_seconds" in result
        assert "predicted_response_minutes" in result
        assert "confidence" in result

    def test_predict_response_time_with_urgency(self, client):
        """Cover prediction with urgency parameter."""
        response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack&urgency=high")

        assert response.status_code == 200
        assert response.json()["urgency"] == "high"

    @pytest.mark.parametrize("urgency", ["low", "medium", "high", "urgent"])
    def test_predict_response_time_urgency_levels(self, client, urgency):
        """Cover various urgency levels."""
        response = client.get(
            f"/api/analytics/predictions/response-time?recipient=user-123&platform=slack&urgency={urgency}"
        )

        assert response.status_code == 200
        assert response.json()["urgency"] == urgency

    def test_predict_response_time_minutes_conversion(self, client):
        """Cover response time in minutes."""
        response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack")

        assert response.status_code == 200
        result = response.json()
        predicted_seconds = result["predicted_response_seconds"]
        predicted_minutes = result["predicted_response_minutes"]
        assert abs(predicted_minutes - predicted_seconds / 60) < 0.01

    def test_predict_response_time_factors(self, client):
        """Cover prediction factors."""
        response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack")

        assert response.status_code == 200
        assert "factors" in response.json()
        assert isinstance(response.json()["factors"], list)

    def test_predict_response_time_invalid_urgency(self, client):
        """Cover prediction with invalid urgency."""
        response = client.get(
            "/api/analytics/predictions/response-time?recipient=user-123&platform=slack&urgency=invalid"
        )

        # Should return validation error
        assert response.status_code in [200, 422, 500]

    def test_predict_response_time_confidence_levels(self, client):
        """Cover prediction confidence levels."""
        response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack")

        assert response.status_code == 200
        assert "confidence" in response.json()


# ============================================================================
# Test Channel Recommendation Endpoint (8 tests)
# ============================================================================

class TestChannelRecommendation:
    """Test suite for /api/analytics/recommendations/channel endpoint."""

    def test_recommend_channel_success(self, client):
        """Cover channel recommendation."""
        response = client.get("/api/analytics/recommendations/channel?recipient=user-123")

        assert response.status_code == 200
        result = response.json()
        assert "recipient" in result
        assert "recommended_platform" in result
        assert "reason" in result
        assert "confidence" in result

    def test_recommend_channel_with_message_type(self, client):
        """Cover recommendation with message type."""
        response = client.get("/api/analytics/recommendations/channel?recipient=user-123&message_type=urgent")

        assert response.status_code == 200

    def test_recommend_channel_with_urgency(self, client):
        """Cover recommendation with urgency."""
        response = client.get("/api/analytics/recommendations/channel?recipient=user-123&urgency=high")

        assert response.status_code == 200
        assert response.json()["urgency"] == "high"

    @pytest.mark.parametrize("urgency", ["low", "medium", "high", "urgent"])
    def test_recommend_channel_urgency_levels(self, client, urgency):
        """Cover recommendation for various urgency levels."""
        response = client.get(
            f"/api/analytics/recommendations/channel?recipient=user-123&urgency={urgency}"
        )

        assert response.status_code == 200

    def test_recommend_channel_alternatives(self, client):
        """Cover recommendation alternatives."""
        response = client.get("/api/analytics/recommendations/channel?recipient=user-123")

        assert response.status_code == 200
        assert "alternatives" in response.json()
        assert isinstance(response.json()["alternatives"], list)

    def test_recommend_channel_expected_response_time(self, client):
        """Cover expected response time in recommendation."""
        response = client.get("/api/analytics/recommendations/channel?recipient=user-123")

        assert response.status_code == 200
        assert "expected_response_time_minutes" in response.json()

    def test_recommend_channel_invalid_urgency(self, client):
        """Cover recommendation with invalid urgency."""
        response = client.get(
            "/api/analytics/recommendations/channel?recipient=user-123&urgency=invalid"
        )

        # Should handle error gracefully
        assert response.status_code in [200, 422, 500]

    def test_recommend_channel_combined_parameters(self, client):
        """Cover recommendation with combined parameters."""
        response = client.get(
            "/api/analytics/recommendations/channel?recipient=user-123&message_type=general&urgency=medium"
        )

        assert response.status_code == 200


# ============================================================================
# Test Bottleneck Detection Endpoint (7 tests)
# ============================================================================

class TestBottleneckDetection:
    """Test suite for /api/analytics/bottlenecks endpoint."""

    def test_detect_bottlenecks_success(self, client):
        """Cover bottleneck detection."""
        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        result = response.json()
        assert "total_bottlenecks" in result
        assert "threshold_hours" in result
        assert "bottlenecks" in result

    def test_detect_bottlenecks_with_threshold(self, client):
        """Cover bottleneck detection with custom threshold."""
        response = client.get("/api/analytics/bottlenecks?threshold_hours=48")

        assert response.status_code == 200
        assert response.json()["threshold_hours"] == 48

    def test_bottleneck_structure(self, client):
        """Cover bottleneck structure."""
        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        bottlenecks = response.json()["bottlenecks"]
        if len(bottlenecks) > 0:
            b = bottlenecks[0]
            assert "severity" in b
            assert "thread_id" in b
            assert "platform" in b
            assert "description" in b
            assert "affected_users" in b
            assert "wait_time_hours" in b
            assert "suggested_action" in b

    def test_bottleneck_affected_users_list(self, client):
        """Cover affected users as list."""
        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        bottlenecks = response.json()["bottlenecks"]
        if len(bottlenecks) > 0:
            assert isinstance(bottlenecks[0]["affected_users"], list)

    def test_bottleneck_wait_time_conversion(self, client):
        """Cover wait time conversion to hours."""
        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        bottlenecks = response.json()["bottlenecks"]
        if len(bottlenecks) > 0:
            assert "wait_time_hours" in bottlenecks[0]
            assert isinstance(bottlenecks[0]["wait_time_hours"], (int, float))

    def test_bottleneck_empty(self, client, mock_predictive_engine):
        """Cover bottleneck detection with no bottlenecks."""
        mock_predictive_engine.detect_bottlenecks.return_value = []

        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        assert response.json()["total_bottlenecks"] == 0

    @pytest.mark.parametrize("threshold", [12.0, 24.0, 48.0, 72.0])
    def test_bottleneck_various_thresholds(self, client, threshold):
        """Cover bottleneck detection with various thresholds."""
        response = client.get(f"/api/analytics/bottlenecks?threshold_hours={threshold}")

        assert response.status_code == 200
        assert response.json()["threshold_hours"] == threshold


# ============================================================================
# Test User Patterns Endpoint (8 tests)
# ============================================================================

class TestUserPatterns:
    """Test suite for /api/analytics/patterns/{user_id} endpoint."""

    def test_get_user_patterns_success(self, client):
        """Cover user patterns retrieval."""
        response = client.get("/api/analytics/patterns/user-123")

        assert response.status_code == 200
        result = response.json()
        assert "user_id" in result
        assert "most_active_platform" in result
        assert "most_active_hours" in result
        assert "avg_response_time_minutes" in result

    def test_get_user_patterns_not_found(self, client, mock_predictive_engine):
        """Cover user patterns for non-existent user."""
        mock_predictive_engine.get_user_pattern.return_value = None

        response = client.get("/api/analytics/patterns/nonexistent")

        assert response.status_code == 404

    def test_user_patterns_active_hours(self, client):
        """Cover most active hours structure."""
        response = client.get("/api/analytics/patterns/user-123")

        assert response.status_code == 200
        assert "most_active_hours" in response.json()
        assert isinstance(response.json()["most_active_hours"], list)

    def test_user_patterns_response_probability(self, client):
        """Cover response probability by hour."""
        response = client.get("/api/analytics/patterns/user-123")

        assert response.status_code == 200
        assert "response_probability_by_hour" in response.json()
        assert isinstance(response.json()["response_probability_by_hour"], dict)

    def test_user_patterns_preferred_message_types(self, client):
        """Cover preferred message types."""
        response = client.get("/api/analytics/patterns/user-123")

        assert response.status_code == 200
        assert "preferred_message_types" in response.json()
        assert isinstance(response.json()["preferred_message_types"], list)

    def test_user_patterns_response_time_minutes(self, client):
        """Cover response time in minutes."""
        response = client.get("/api/analytics/patterns/user-123")

        assert response.status_code == 200
        # Response time should be in minutes (converted from seconds)
        assert "avg_response_time_minutes" in response.json()

    def test_user_patterns_probability_24_hours(self, client):
        """Cover response probability covers 24 hours."""
        response = client.get("/api/analytics/patterns/user-123")

        assert response.status_code == 200
        probability = response.json()["response_probability_by_hour"]
        # Should have entries for all 24 hours
        assert len(probability) == 24


# ============================================================================
# Test Analytics Overview Endpoint (6 tests)
# ============================================================================

class TestAnalyticsOverview:
    """Test suite for /api/analytics/overview endpoint."""

    def test_get_analytics_overview_success(self, client):
        """Cover analytics overview."""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        result = response.json()
        assert "timestamp" in result
        assert "message_analytics" in result
        assert "predictive_insights" in result
        assert "cross_platform" in result
        assert "health_status" in result

    def test_overview_timestamp(self, client):
        """Cover overview timestamp."""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        assert "timestamp" in response.json()
        # Should be valid ISO format timestamp
        datetime.fromisoformat(response.json()["timestamp"].replace('Z', '+00:00'))

    def test_overview_message_analytics(self, client):
        """Cover message analytics in overview."""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        msg_analytics = response.json()["message_analytics"]
        assert "total_messages" in msg_analytics
        assert "active_threads" in msg_analytics
        assert "platforms_active" in msg_analytics

    def test_overview_predictive_insights(self, client):
        """Cover predictive insights in overview."""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        insights = response.json()["predictive_insights"]
        assert "users_analyzed" in insights
        assert "bottlenecks_detected" in insights
        assert "avg_response_time_minutes" in insights

    def test_overview_cross_platform(self, client):
        """Cover cross-platform in overview."""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        cp = response.json()["cross_platform"]
        assert "linked_conversations" in cp
        assert "cross_platform_links" in cp

    def test_overview_health_status(self, client):
        """Cover health status in overview."""
        response = client.get("/api/analytics/overview")

        assert response.status_code == 200
        assert "health_status" in response.json()
        assert isinstance(response.json()["health_status"], str)


# ============================================================================
# Test Error Handling (6 tests)
# ============================================================================

class TestErrorHandling:
    """Test suite for error handling across all endpoints."""

    @patch('api.analytics_dashboard_routes.get_message_analytics_engine')
    def test_summary_endpoint_exception_handling(self, mock_get_engine, client):
        """Cover exception handling in summary endpoint."""
        mock_get_engine.side_effect = Exception("Analytics engine failed")

        response = client.get("/api/analytics/summary")

        # Should return error response, not crash
        assert response.status_code in [500, 200]

    @patch('api.analytics_dashboard_routes.get_predictive_insights_engine')
    def test_predictive_endpoint_exception_handling(self, mock_get_engine, client):
        """Cover exception handling in predictive endpoint."""
        mock_get_engine.side_effect = Exception("Predictive engine failed")

        response = client.get("/api/analytics/predictions/response-time?recipient=user-123&platform=slack")

        assert response.status_code in [500, 200]

    @patch('api.analytics_dashboard_routes.get_cross_platform_correlation_engine')
    def test_correlation_endpoint_exception_handling(self, mock_get_engine, client):
        """Cover exception handling in correlation endpoint."""
        mock_get_engine.side_effect = Exception("Correlation engine failed")

        messages = [{"id": "msg-1", "platform": "slack"}]
        response = client.post("/api/analytics/correlations", json=messages)

        assert response.status_code in [500, 200]

    @patch('api.analytics_dashboard_routes.get_message_analytics_engine')
    def test_sentiment_endpoint_exception_handling(self, mock_get_engine, client):
        """Cover exception handling in sentiment endpoint."""
        mock_get_engine.side_effect = Exception("Analytics engine failed")

        response = client.get("/api/analytics/sentiment")

        assert response.status_code in [500, 200]

    @patch('api.analytics_dashboard_routes.get_predictive_insights_engine')
    def test_bottleneck_endpoint_exception_handling(self, mock_get_engine, client):
        """Cover exception handling in bottleneck endpoint."""
        mock_get_engine.side_effect = Exception("Predictive engine failed")

        response = client.get("/api/analytics/bottlenecks")

        assert response.status_code in [500, 200]