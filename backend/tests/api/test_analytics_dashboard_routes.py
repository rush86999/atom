"""
Analytics Dashboard Routes Test Suite

Test coverage for analytics_dashboard_routes.py endpoints:
- Summary analytics
- Sentiment analysis
- Response time metrics
- Activity metrics
- Cross-platform analytics
- Cross-platform correlations
- Unified timeline
- Predict response time
- Recommend channel
- Detect bottlenecks
- User patterns
- Analytics overview

Target: 75%+ line coverage on analytics_dashboard_routes.py
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient


# ============================================================================
# Test Analytics Summary (6 tests)
# ============================================================================

class TestAnalyticsSummary:
    """Test GET /api/analytics/summary endpoint"""

    def test_get_analytics_summary_success(self, analytics_routes_client):
        """Test successful analytics summary retrieval"""
        response = analytics_routes_client.get("/api/analytics/summary")

        assert response.status_code == 200
        data = response.json()
        assert "time_window" in data
        assert "message_stats" in data
        assert "response_times" in data
        assert "activity_peaks" in data
        assert "cross_platform" in data

    def test_get_analytics_summary_with_time_window(self, analytics_routes_client):
        """Test summary with different time windows"""
        for window in ["24h", "7d", "30d", "all"]:
            response = analytics_routes_client.get("/api/analytics/summary", params={"time_window": window})
            assert response.status_code == 200
            data = response.json()
            assert data["time_window"] == window

    def test_get_analytics_summary_with_platform(self, analytics_routes_client):
        """Test summary with platform filter"""
        response = analytics_routes_client.get("/api/analytics/summary", params={"platform": "slack"})
        assert response.status_code == 200
        data = response.json()
        assert "platform_filter" in data
        assert data["platform_filter"] == "slack"

    def test_get_analytics_summary_empty_data(self, mock_message_analytics, analytics_routes_client):
        """Test summary returns zero counts when no messages"""
        mock_message_analytics.get_summary = AsyncMock(return_value={
            "message_stats": {
                "total_messages": 0,
                "total_words": 0,
                "with_attachments": 0,
                "with_mentions": 0,
                "with_urls": 0,
                "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0}
            },
            "response_times": {
                "avg_response_seconds": 0,
                "median_response_seconds": 0,
                "p95_response_seconds": 0,
                "total_responses_analyzed": 0
            },
            "activity_peaks": {"peak_days": [], "messages_per_day": {}},
            "cross_platform": {"platforms": {}, "most_active_platform": None, "total_messages": 0}
        })

        response = analytics_routes_client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["message_stats"]["total_messages"] == 0

    def test_get_analytics_summary_error_handling(self, mock_message_analytics, analytics_routes_client):
        """Test summary handles service exceptions"""
        with patch('api.analytics_dashboard_routes.get_message_analytics_engine', side_effect=Exception("Database connection failed")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/summary")
            assert response.status_code == 500


# ============================================================================
# Test Sentiment Analysis (6 tests)
# ============================================================================

class TestSentimentAnalysis:
    """Test GET /api/analytics/sentiment endpoint"""

    def test_get_sentiment_analysis_success(self, analytics_routes_client):
        """Test successful sentiment analysis retrieval"""
        response = analytics_routes_client.get("/api/analytics/sentiment")

        assert response.status_code == 200
        data = response.json()
        assert "sentiment_distribution" in data
        assert "positive" in data["sentiment_distribution"]
        assert "negative" in data["sentiment_distribution"]
        assert "neutral" in data["sentiment_distribution"]

    def test_get_sentiment_analysis_with_platform(self, analytics_routes_client):
        """Test sentiment analysis with platform filter"""
        response = analytics_routes_client.get("/api/analytics/sentiment", params={"platform": "teams"})
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "teams"

    def test_get_sentiment_analysis_with_time_window(self, analytics_routes_client):
        """Test sentiment analysis with time window"""
        for window in ["24h", "7d", "30d", "all"]:
            response = analytics_routes_client.get("/api/analytics/sentiment", params={"time_window": window})
            assert response.status_code == 200
            data = response.json()
            assert data["time_window"] == window

    def test_get_sentiment_analysis_includes_trends(self, analytics_routes_client):
        """Test sentiment analysis returns trend array"""
        response = analytics_routes_client.get("/api/analytics/sentiment")
        assert response.status_code == 200
        data = response.json()
        assert "sentiment_trend" in data
        assert isinstance(data["sentiment_trend"], list)

    def test_get_sentiment_analysis_topic_breakdown(self, analytics_routes_client):
        """Test sentiment analysis includes topic breakdown"""
        response = analytics_routes_client.get("/api/analytics/sentiment")
        assert response.status_code == 200
        data = response.json()
        assert "most_positive_topics" in data
        assert "most_negative_topics" in data

    def test_get_sentiment_analysis_error_handling(self, analytics_routes_client):
        """Test sentiment analysis handles service errors"""
        with patch('api.analytics_dashboard_routes.get_message_analytics_engine', side_effect=Exception("Sentiment service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/sentiment")
            assert response.status_code == 500


# ============================================================================
# Test Response Time Metrics (6 tests)
# ============================================================================

class TestResponseTimeMetrics:
    """Test GET /api/analytics/response-times endpoint"""

    def test_get_response_time_metrics_success(self, analytics_routes_client):
        """Test successful response time metrics retrieval"""
        response = analytics_routes_client.get("/api/analytics/response-times")

        assert response.status_code == 200
        data = response.json()
        assert "avg_response_seconds" in data
        assert "median_response_seconds" in data
        assert "p95_response_seconds" in data
        assert "p99_response_seconds" in data

    def test_get_response_time_metrics_with_platform(self, analytics_routes_client):
        """Test response time metrics with platform filter"""
        response = analytics_routes_client.get("/api/analytics/response-times", params={"platform": "gmail"})
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "gmail"

    def test_get_response_time_metrics_percentiles(self, analytics_routes_client):
        """Test response time metrics returns percentiles"""
        response = analytics_routes_client.get("/api/analytics/response-times")
        assert response.status_code == 200
        data = response.json()
        assert data["avg_response_seconds"] >= 0
        assert data["median_response_seconds"] >= 0
        assert data["p95_response_seconds"] >= 0
        assert data["p99_response_seconds"] >= 0
        assert data["p99_response_seconds"] >= data["p95_response_seconds"]

    def test_get_response_time_metrics_distribution(self, analytics_routes_client):
        """Test response time metrics returns distribution array"""
        response = analytics_routes_client.get("/api/analytics/response-times")
        assert response.status_code == 200
        data = response.json()
        assert "response_time_distribution" in data
        assert isinstance(data["response_time_distribution"], list)

    def test_get_response_time_metrics_extremes(self, analytics_routes_client):
        """Test response time metrics returns slowest and fastest threads"""
        response = analytics_routes_client.get("/api/analytics/response-times")
        assert response.status_code == 200
        data = response.json()
        assert "slowest_threads" in data
        assert "fastest_threads" in data

    def test_get_response_time_metrics_error_handling(self, analytics_routes_client):
        """Test response time metrics handles service errors"""
        with patch('api.analytics_dashboard_routes.get_message_analytics_engine', side_effect=Exception("Metrics service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/response-times")
            assert response.status_code == 500


# ============================================================================
# Test Activity Metrics (5 tests)
# ============================================================================

class TestActivityMetrics:
    """Test GET /api/analytics/activity endpoint"""

    def test_get_activity_metrics_success(self, analytics_routes_client):
        """Test successful activity metrics retrieval"""
        response = analytics_routes_client.get("/api/analytics/activity")

        assert response.status_code == 200
        data = response.json()
        assert "messages_per_hour" in data
        assert "messages_per_day" in data
        assert "peak_hours" in data
        assert "peak_days" in data

    def test_get_activity_metrics_period(self, analytics_routes_client):
        """Test activity metrics with different periods"""
        for period in ["hourly", "daily", "weekly"]:
            response = analytics_routes_client.get("/api/analytics/activity", params={"period": period})
            assert response.status_code == 200
            data = response.json()
            assert data["period"] == period

    def test_get_activity_metrics_with_platform(self, analytics_routes_client):
        """Test activity metrics with platform filter"""
        response = analytics_routes_client.get("/api/analytics/activity", params={"platform": "slack"})
        assert response.status_code == 200
        data = response.json()
        assert data["platform"] == "slack"

    def test_get_activity_metrics_heatmap(self, analytics_routes_client):
        """Test activity metrics returns heatmap data"""
        response = analytics_routes_client.get("/api/analytics/activity")
        assert response.status_code == 200
        data = response.json()
        assert "activity_heatmap" in data
        assert isinstance(data["activity_heatmap"], list)

    def test_get_activity_metrics_peak_times(self, analytics_routes_client):
        """Test activity metrics returns peak hours and days"""
        response = analytics_routes_client.get("/api/analytics/activity")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["peak_hours"], list)
        assert isinstance(data["peak_days"], list)


# ============================================================================
# Test Cross-Platform Analytics (4 tests)
# ============================================================================

class TestCrossPlatformAnalytics:
    """Test GET /api/analytics/cross-platform endpoint"""

    def test_get_cross_platform_analytics_success(self, analytics_routes_client):
        """Test successful cross-platform analytics retrieval"""
        response = analytics_routes_client.get("/api/analytics/cross-platform")

        assert response.status_code == 200
        data = response.json()
        assert "platforms" in data
        assert "most_active_platform" in data
        assert "platform_comparison" in data

    def test_get_cross_platform_analytics_time_window(self, analytics_routes_client):
        """Test cross-platform analytics with time window"""
        response = analytics_routes_client.get("/api/analytics/cross-platform", params={"time_window": "7d"})
        assert response.status_code == 200
        data = response.json()
        assert data["time_window"] == "7d"

    def test_get_cross_platform_analytics_platforms(self, analytics_routes_client):
        """Test cross-platform analytics returns data for all platforms"""
        response = analytics_routes_client.get("/api/analytics/cross-platform")
        assert response.status_code == 200
        data = response.json()
        assert "slack" in data["platforms"]
        assert "teams" in data["platforms"]
        assert "gmail" in data["platforms"]

    def test_get_cross_platform_analytics_most_active(self, analytics_routes_client):
        """Test cross-platform analytics identifies most active platform"""
        response = analytics_routes_client.get("/api/analytics/cross-platform")
        assert response.status_code == 200
        data = response.json()
        assert data["most_active_platform"] in ["slack", "teams", "gmail"]


# ============================================================================
# Test Cross-Platform Correlations (5 tests)
# ============================================================================

class TestCrossPlatformCorrelations:
    """Test POST /api/analytics/correlations endpoint"""

    def test_analyze_correlations_success(self, analytics_routes_client):
        """Test successful correlation analysis"""
        messages = [
            {"id": "msg1", "platform": "slack", "content": "Test", "sender": "user1", "timestamp": "2026-03-12T10:00:00Z"},
            {"id": "msg2", "platform": "teams", "content": "Related", "sender": "user2", "timestamp": "2026-03-12T10:05:00Z"}
        ]

        response = analytics_routes_client.post("/api/analytics/correlations", json=messages)
        assert response.status_code == 200
        data = response.json()
        assert "linked_conversations" in data
        assert "total_correlations" in data
        assert "cross_platform_links" in data

    def test_analyze_correlations_empty(self, analytics_routes_client):
        """Test correlation analysis with empty message list"""
        response = analytics_routes_client.post("/api/analytics/correlations", json=[])
        assert response.status_code == 200
        data = response.json()
        assert "linked_conversations" in data

    def test_analyze_correlations_conversation_fields(self, analytics_routes_client):
        """Test correlation analysis returns all required fields"""
        messages = [{"id": "msg1", "platform": "slack", "content": "Test"}]

        response = analytics_routes_client.post("/api/analytics/correlations", json=messages)
        assert response.status_code == 200
        data = response.json()
        if len(data["linked_conversations"]) > 0:
            conv = data["linked_conversations"][0]
            assert "conversation_id" in conv
            assert "platforms" in conv
            assert "participants" in conv
            assert "message_count" in conv
            assert "correlation_strength" in conv

    def test_analyze_correlations_total_count(self, analytics_routes_client):
        """Test correlation analysis returns total count"""
        messages = [{"id": "msg1", "platform": "slack", "content": "Test"}]

        response = analytics_routes_client.post("/api/analytics/correlations", json=messages)
        assert response.status_code == 200
        data = response.json()
        assert "total_correlations" in data
        assert isinstance(data["total_correlations"], int)

    def test_analyze_correlations_error_handling(self, mock_correlation_engine, analytics_routes_client):
        """Test correlation analysis handles service exceptions"""
        mock_correlation_engine.correlate_conversations.side_effect = Exception("Correlation service unavailable")

        messages = [{"id": "msg1", "platform": "slack", "content": "Test"}]
        response = analytics_routes_client.post("/api/analytics/correlations", json=messages)
        assert response.status_code == 500


# ============================================================================
# Test Unified Timeline (5 tests)
# ============================================================================

class TestUnifiedTimeline:
    """Test GET /api/analytics/correlations/{conversation_id}/timeline endpoint"""

    def test_get_unified_timeline_success(self, analytics_routes_client):
        """Test successful unified timeline retrieval"""
        response = analytics_routes_client.get("/api/analytics/correlations/linked-conv-123/timeline")

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert "message_count" in data
        assert "messages" in data

    def test_get_unified_timeline_not_found(self, mock_correlation_engine, analytics_routes_client):
        """Test unified timeline returns 404 for non-existent conversation"""
        mock_correlation_engine.get_unified_timeline = AsyncMock(return_value=None)
        
        from fastapi import FastAPI
        from api.analytics_dashboard_routes import router
        from unittest.mock import patch
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('api.analytics_dashboard_routes.get_cross_platform_correlation_engine', return_value=mock_correlation_engine):
            client = TestClient(app)
            response = client.get("/api/analytics/correlations/nonexistent/timeline")
            assert response.status_code == 404

    def test_get_unified_timeline_message_fields(self, analytics_routes_client):
        """Test unified timeline returns messages with all fields"""
        response = analytics_routes_client.get("/api/analytics/correlations/linked-conv-123/timeline")
        assert response.status_code == 200
        data = response.json()
        if len(data["messages"]) > 0:
            msg = data["messages"][0]
            assert "id" in msg
            assert "platform" in msg
            assert "content" in msg
            assert "sender" in msg
            assert "timestamp" in msg

    def test_get_unified_timeline_platform_sources(self, analytics_routes_client):
        """Test unified timeline includes correlation source"""
        response = analytics_routes_client.get("/api/analytics/correlations/linked-conv-123/timeline")
        assert response.status_code == 200
        data = response.json()
        if len(data["messages"]) > 0:
            msg = data["messages"][0]
            assert "source" in msg

    def test_get_unified_timeline_error_handling(self, analytics_routes_client):
        """Test unified timeline handles service exceptions"""
        with patch('api.analytics_dashboard_routes.get_cross_platform_correlation_engine', side_effect=Exception("Timeline service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/correlations/linked-conv-123/timeline")
            assert response.status_code == 500


# ============================================================================
# Test Predict Response Time (6 tests)
# ============================================================================

class TestPredictResponseTime:
    """Test GET /api/analytics/predictions/response-time endpoint"""

    def test_predict_response_time_success(self, analytics_routes_client):
        """Test successful response time prediction"""
        response = analytics_routes_client.get("/api/analytics/predictions/response-time", params={
            "recipient": "user123",
            "platform": "slack",
            "urgency": "medium"
        })

        assert response.status_code == 200
        data = response.json()
        assert "predicted_response_seconds" in data
        assert "predicted_response_minutes" in data
        assert "confidence" in data
        assert "factors" in data

    def test_predict_response_time_urgency_levels(self, analytics_routes_client):
        """Test response time prediction with all urgency levels"""
        for urgency in ["low", "medium", "high", "urgent"]:
            response = analytics_routes_client.get("/api/analytics/predictions/response-time", params={
                "recipient": "user123",
                "platform": "slack",
                "urgency": urgency
            })
            assert response.status_code == 200

    def test_predict_response_time_factors(self, analytics_routes_client):
        """Test response time prediction includes factors"""
        response = analytics_routes_client.get("/api/analytics/predictions/response-time", params={
            "recipient": "user123",
            "platform": "slack",
            "urgency": "medium"
        })
        assert response.status_code == 200
        data = response.json()
        assert "factors" in data
        assert isinstance(data["factors"], list)

    def test_predict_response_time_invalid_urgency(self, analytics_routes_client):
        """Test response time prediction with invalid urgency"""
        response = analytics_routes_client.get("/api/analytics/predictions/response-time", params={
            "recipient": "user123",
            "platform": "slack",
            "urgency": "invalid"
        })
        assert response.status_code == 422  # Validation error

    def test_predict_response_time_confidence_levels(self, mock_insights_engine, analytics_routes_client):
        """Test response time prediction returns confidence levels"""
        from core.predictive_insights import RecommendationConfidence as Confidence

        mock_insights_engine.predict_response_time = AsyncMock()
        mock_prediction = Mock()
        mock_prediction.user_id = "user123"
        mock_prediction.predicted_seconds = 3600
        mock_prediction.confidence = Confidence.MEDIUM
        mock_prediction.factors = []
        mock_insights_engine.predict_response_time.return_value = mock_prediction
        
        from fastapi import FastAPI
        from api.analytics_dashboard_routes import router
        from unittest.mock import patch
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', return_value=mock_insights_engine):
            client = TestClient(app)
            response = client.get("/api/analytics/predictions/response-time", params={
                "recipient": "user123",
                "platform": "slack",
                "urgency": "medium"
            })
            assert response.status_code == 200

    def test_predict_response_time_error_handling(self, analytics_routes_client):
        """Test response time prediction handles service errors"""
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', side_effect=Exception("Prediction service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/predictions/response-time", params={
                "recipient": "user123",
                "platform": "slack",
                "urgency": "medium"
            })
            assert response.status_code == 500


# ============================================================================
# Test Recommend Channel (5 tests)
# ============================================================================

class TestRecommendChannel:
    """Test GET /api/analytics/recommendations/channel endpoint"""

    def test_recommend_channel_success(self, analytics_routes_client):
        """Test successful channel recommendation"""
        response = analytics_routes_client.get("/api/analytics/recommendations/channel", params={
            "recipient": "user123",
            "message_type": "general",
            "urgency": "medium"
        })

        assert response.status_code == 200
        data = response.json()
        assert "recommended_platform" in data
        assert "reason" in data
        assert "confidence" in data

    def test_recommend_channel_message_types(self, analytics_routes_client):
        """Test channel recommendation with different message types"""
        for msg_type in ["general", "urgent", "question", "update"]:
            response = analytics_routes_client.get("/api/analytics/recommendations/channel", params={
                "recipient": "user123",
                "message_type": msg_type,
                "urgency": "medium"
            })
            assert response.status_code == 200

    def test_recommend_channel_with_alternatives(self, analytics_routes_client):
        """Test channel recommendation includes alternative platforms"""
        response = analytics_routes_client.get("/api/analytics/recommendations/channel", params={
            "recipient": "user123",
            "message_type": "general",
            "urgency": "medium"
        })
        assert response.status_code == 200
        data = response.json()
        assert "alternatives" in data
        assert isinstance(data["alternatives"], list)

    def test_recommend_channel_invalid_urgency(self, analytics_routes_client):
        """Test channel recommendation with invalid urgency"""
        response = analytics_routes_client.get("/api/analytics/recommendations/channel", params={
            "recipient": "user123",
            "message_type": "general",
            "urgency": "invalid"
        })
        assert response.status_code == 422  # Validation error

    def test_recommend_channel_error_handling(self, analytics_routes_client):
        """Test channel recommendation handles service errors"""
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', side_effect=Exception("Recommendation service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/recommendations/channel", params={
                "recipient": "user123",
                "message_type": "general",
                "urgency": "medium"
            })
            assert response.status_code == 500


# ============================================================================
# Test Detect Bottlenecks (5 tests)
# ============================================================================

class TestDetectBottlenecks:
    """Test GET /api/analytics/bottlenecks endpoint"""

    def test_detect_bottlenecks_success(self, analytics_routes_client):
        """Test successful bottleneck detection"""
        response = analytics_routes_client.get("/api/analytics/bottlenecks")

        assert response.status_code == 200
        data = response.json()
        assert "total_bottlenecks" in data
        assert "threshold_hours" in data
        assert "bottlenecks" in data

    def test_detect_bottlenecks_threshold(self, analytics_routes_client):
        """Test bottleneck detection with custom threshold"""
        response = analytics_routes_client.get("/api/analytics/bottlenecks", params={"threshold_hours": 48.0})
        assert response.status_code == 200
        data = response.json()
        assert data["threshold_hours"] == 48.0

    def test_detect_bottlenecks_severity(self, analytics_routes_client):
        """Test bottleneck detection returns severity levels"""
        response = analytics_routes_client.get("/api/analytics/bottlenecks")
        assert response.status_code == 200
        data = response.json()
        if len(data["bottlenecks"]) > 0:
            bottleneck = data["bottlenecks"][0]
            assert "severity" in bottleneck
            assert bottleneck["severity"] in ["critical", "warning", "info"]

    def test_detect_bottlenecks_suggested_actions(self, analytics_routes_client):
        """Test bottleneck detection includes suggested actions"""
        response = analytics_routes_client.get("/api/analytics/bottlenecks")
        assert response.status_code == 200
        data = response.json()
        if len(data["bottlenecks"]) > 0:
            bottleneck = data["bottlenecks"][0]
            assert "suggested_action" in bottleneck

    def test_detect_bottlenecks_error_handling(self, analytics_routes_client):
        """Test bottleneck detection handles service errors"""
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', side_effect=Exception("Bottleneck detection service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/bottlenecks")
            assert response.status_code == 500


# ============================================================================
# Test User Patterns (4 tests)
# ============================================================================

class TestUserPatterns:
    """Test GET /api/analytics/patterns/{user_id} endpoint"""

    def test_get_user_patterns_success(self, analytics_routes_client):
        """Test successful user patterns retrieval"""
        response = analytics_routes_client.get("/api/analytics/patterns/user123")

        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "most_active_platform" in data
        assert "most_active_hours" in data
        assert "response_probability_by_hour" in data

    def test_get_user_patterns_not_found(self, mock_insights_engine, analytics_routes_client):
        """Test user patterns returns 404 for non-existent user"""
        mock_insights_engine.get_user_pattern = AsyncMock(return_value=None)
        
        from fastapi import FastAPI
        from api.analytics_dashboard_routes import router
        from unittest.mock import patch
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', return_value=mock_insights_engine):
            client = TestClient(app)
            response = client.get("/api/analytics/patterns/nonexistent")
            assert response.status_code == 404

    def test_get_user_patterns_response_probability(self, analytics_routes_client):
        """Test user patterns includes response probability by hour"""
        response = analytics_routes_client.get("/api/analytics/patterns/user123")
        assert response.status_code == 200
        data = response.json()
        assert "response_probability_by_hour" in data
        assert isinstance(data["response_probability_by_hour"], dict)

    def test_get_user_patterns_error_handling(self, analytics_routes_client):
        """Test user patterns handles service errors"""
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', side_effect=Exception("User patterns service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/patterns/user123")
            assert response.status_code == 500


# ============================================================================
# Test Analytics Overview (4 tests)
# ============================================================================

class TestAnalyticsOverview:
    """Test GET /api/analytics/overview endpoint"""

    def test_get_analytics_overview_success(self, analytics_routes_client):
        """Test successful analytics overview retrieval"""
        response = analytics_routes_client.get("/api/analytics/overview")

        assert response.status_code == 200
        data = response.json()
        assert "message_analytics" in data
        assert "predictive_insights" in data
        assert "cross_platform" in data
        assert "health_status" in data

    def test_get_analytics_overview_timestamp(self, analytics_routes_client):
        """Test analytics overview includes UTC timestamp"""
        response = analytics_routes_client.get("/api/analytics/overview")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format check
        assert "Z" in data["timestamp"] or "+" in data["timestamp"]  # UTC check

    def test_get_analytics_overview_health_status(self, analytics_routes_client):
        """Test analytics overview returns health status"""
        response = analytics_routes_client.get("/api/analytics/overview")
        assert response.status_code == 200
        data = response.json()
        assert "health_status" in data
        assert data["health_status"] in ["healthy", "degraded", "unhealthy"]

    def test_get_analytics_overview_error_handling(self, analytics_routes_client):
        """Test analytics overview handles service errors"""
        with patch('api.analytics_dashboard_routes.get_predictive_insights_engine', side_effect=Exception("Overview service unavailable")):
            from fastapi import FastAPI
            from api.analytics_dashboard_routes import router
            
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)
            
            response = client.get("/api/analytics/overview")
            assert response.status_code == 500
