"""
Analytics Dashboard API Routes
Provides endpoints for message analytics, cross-platform correlation, and predictive insights.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from core.cross_platform_correlation import (
    CrossPlatformCorrelationEngine,
    get_cross_platform_correlation_engine,
)
from core.message_analytics_engine import MessageAnalyticsEngine, get_message_analytics_engine
from core.predictive_insights import (
    PredictiveInsightsEngine,
    UrgencyLevel,
    get_predictive_insights_engine,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
async def get_analytics_summary(
    time_window: str = Query("24h", description="Time window: 24h, 7d, 30d, all"),
    platform: Optional[str] = Query(None, description="Filter by platform")
) -> Dict[str, Any]:
    """
    Get comprehensive analytics summary.

    Args:
        time_window: Time period for analytics
        platform: Optional platform filter

    Returns:
        Analytics summary with message stats, response times, sentiment, etc.
    """
    try:
        analytics_engine = get_message_analytics_engine()

        # Get all messages (in production, would query from database)
        # For now, return summary structure
        summary = {
            "time_window": time_window,
            "message_stats": {
                "total_messages": 0,
                "total_words": 0,
                "with_attachments": 0,
                "with_mentions": 0,
                "with_urls": 0,
                "sentiment_distribution": {
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0
                }
            },
            "response_times": {
                "avg_response_seconds": 0,
                "median_response_seconds": 0,
                "p95_response_seconds": 0,
                "total_responses_analyzed": 0
            },
            "activity_peaks": {
                "peak_days": [],
                "messages_per_day": {}
            },
            "cross_platform": {
                "platforms": {},
                "most_active_platform": None,
                "total_messages": 0
            }
        }

        if platform:
            summary["platform_filter"] = platform

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating analytics: {str(e)}")


@router.get("/sentiment")
async def get_sentiment_analysis(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    time_window: str = Query("24h", description="Time window for analysis")
) -> Dict[str, Any]:
    """
    Get sentiment analysis breakdown.

    Args:
        platform: Optional platform filter
        time_window: Time period for analysis

    Returns:
        Sentiment distribution and trends
    """
    try:
        analytics_engine = get_message_analytics_engine()

        return {
            "platform": platform,
            "time_window": time_window,
            "sentiment_distribution": {
                "positive": 0,
                "negative": 0,
                "neutral": 0
            },
            "sentiment_trend": [],  # Time series of sentiment
            "most_positive_topics": [],
            "most_negative_topics": []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sentiment: {str(e)}")


@router.get("/response-times")
async def get_response_time_metrics(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    time_window: str = Query("7d", description="Time window for analysis")
) -> Dict[str, Any]:
    """
    Get response time metrics.

    Args:
        platform: Optional platform filter
        time_window: Time period for analysis

    Returns:
        Response time statistics (avg, median, P95, P99)
    """
    try:
        analytics_engine = get_message_analytics_engine()

        return {
            "platform": platform,
            "time_window": time_window,
            "avg_response_seconds": 0,
            "median_response_seconds": 0,
            "p95_response_seconds": 0,
            "p99_response_seconds": 0,
            "response_time_distribution": [],
            "slowest_threads": [],
            "fastest_threads": []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating response times: {str(e)}")


@router.get("/activity")
async def get_activity_metrics(
    period: str = Query("daily", description="Period: hourly, daily, weekly"),
    platform: Optional[str] = Query(None, description="Filter by platform")
) -> Dict[str, Any]:
    """
    Get activity metrics and peak times.

    Args:
        period: Time period granularity
        platform: Optional platform filter

    Returns:
        Activity metrics with peaks and patterns
    """
    try:
        analytics_engine = get_message_analytics_engine()

        return {
            "period": period,
            "platform": platform,
            "messages_per_hour": {},
            "messages_per_day": {},
            "messages_per_channel": {},
            "peak_hours": [],
            "peak_days": [],
            "activity_heatmap": []  # For visualization
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing activity: {str(e)}")


@router.get("/cross-platform")
async def get_cross_platform_analytics(
    time_window: str = Query("7d", description="Time window for analysis")
) -> Dict[str, Any]:
    """
    Get cross-platform analytics and comparisons.

    Args:
        time_window: Time period for analysis

    Returns:
        Platform comparison and insights
    """
    try:
        analytics_engine = get_message_analytics_engine()

        return {
            "time_window": time_window,
            "platforms": {
                "slack": {
                    "message_count": 0,
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "avg_response_time": 0
                },
                "teams": {
                    "message_count": 0,
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "avg_response_time": 0
                },
                "gmail": {
                    "message_count": 0,
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "avg_response_time": 0
                }
            },
            "most_active_platform": "slack",
            "platform_comparison": []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing cross-platform: {str(e)}")


@router.post("/correlations")
async def analyze_cross_platform_correlations(
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze and correlate conversations across platforms.

    Args:
        messages: List of unified messages to analyze

    Returns:
        Linked conversations and correlations
    """
    try:
        correlation_engine = get_cross_platform_correlation_engine()

        conversations = correlation_engine.correlate_conversations(messages)

        return {
            "linked_conversations": [
                {
                    "conversation_id": c.conversation_id,
                    "platforms": list(c.platforms),
                    "participants": list(c.participants),
                    "message_count": c.message_count,
                    "correlation_strength": c.correlation_strength.value,
                    "unified_message_count": len(c.unified_messages)
                }
                for c in conversations
            ],
            "total_correlations": len(conversations),
            "cross_platform_links": len(correlation_engine.cross_platform_links)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing correlations: {str(e)}")


@router.get("/correlations/{conversation_id}/timeline")
async def get_unified_timeline(
    conversation_id: str
) -> Dict[str, Any]:
    """
    Get unified timeline for a cross-platform conversation.

    Args:
        conversation_id: ID of the linked conversation

    Returns:
        Unified message timeline from all platforms
    """
    try:
        correlation_engine = get_cross_platform_correlation_engine()

        timeline = correlation_engine.get_unified_timeline(conversation_id)

        if timeline is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {
            "conversation_id": conversation_id,
            "message_count": len(timeline),
            "messages": [
                {
                    "id": m.get("id"),
                    "platform": m.get("platform"),
                    "content": m.get("content"),
                    "sender": m.get("sender_name") or m.get("sender"),
                    "timestamp": m.get("timestamp"),
                    "source": m.get("_correlation_source")
                }
                for m in timeline
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting timeline: {str(e)}")


@router.get("/predictions/response-time")
async def predict_response_time(
    recipient: str = Query(..., description="User ID or name"),
    platform: str = Query(..., description="Platform to send on"),
    urgency: str = Query("medium", description="Urgency: low, medium, high, urgent")
) -> Dict[str, Any]:
    """
    Predict response time for a user.

    Args:
        recipient: User to predict for
        platform: Platform to send on
        urgency: Message urgency

    Returns:
        Predicted response time with confidence
    """
    try:
        insights_engine = get_predictive_insights_engine()

        urgency_level = UrgencyLevel(urgency)
        prediction = insights_engine.predict_response_time(
            recipient=recipient,
            platform=platform,
            urgency=urgency_level
        )

        return {
            "recipient": prediction.user_id,
            "platform": platform,
            "urgency": urgency,
            "predicted_response_seconds": prediction.predicted_seconds,
            "predicted_response_minutes": prediction.predicted_seconds / 60,
            "confidence": prediction.confidence.value,
            "factors": prediction.factors
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid urgency level: {urgency}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error predicting response time: {str(e)}")


@router.get("/recommendations/channel")
async def recommend_channel(
    recipient: str = Query(..., description="User ID or name"),
    message_type: str = Query("general", description="Type of message"),
    urgency: str = Query("medium", description="Urgency: low, medium, high, urgent")
) -> Dict[str, Any]:
    """
    Get optimal channel recommendation for a user.

    Args:
        recipient: User to recommend for
        message_type: Type of message
        urgency: Message urgency

    Returns:
        Channel recommendation with alternatives
    """
    try:
        insights_engine = get_predictive_insights_engine()

        urgency_level = UrgencyLevel(urgency)
        recommendation = insights_engine.recommend_channel(
            recipient=recipient,
            message_type=message_type,
            urgency=urgency_level
        )

        return {
            "recipient": recommendation.user_id,
            "recommended_platform": recommendation.recommended_platform,
            "reason": recommendation.reason,
            "confidence": recommendation.confidence.value,
            "expected_response_time_minutes": recommendation.expected_response_time / 60 if recommendation.expected_response_time else None,
            "alternatives": recommendation.alternatives
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid urgency level: {urgency}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recommendation: {str(e)}")


@router.get("/bottlenecks")
async def detect_bottlenecks(
    threshold_hours: float = Query(24.0, description="Hours without response to flag")
) -> Dict[str, Any]:
    """
    Detect communication bottlenecks.

    Args:
        threshold_hours: Hours to wait before flagging

    Returns:
        List of bottleneck alerts
    """
    try:
        insights_engine = get_predictive_insights_engine()

        bottlenecks = insights_engine.detect_bottlenecks(threshold_hours=threshold_hours)

        return {
            "total_bottlenecks": len(bottlenecks),
            "threshold_hours": threshold_hours,
            "bottlenecks": [
                {
                    "severity": b.severity.value,
                    "thread_id": b.thread_id,
                    "platform": b.platform,
                    "description": b.description,
                    "affected_users": b.affected_users,
                    "wait_time_hours": b.wait_time_seconds / 3600,
                    "suggested_action": b.suggested_action
                }
                for b in bottlenecks
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting bottlenecks: {str(e)}")


@router.get("/patterns/{user_id}")
async def get_user_patterns(
    user_id: str
) -> Dict[str, Any]:
    """
    Get communication patterns for a specific user.

    Args:
        user_id: User to analyze

    Returns:
        User's communication patterns and preferences
    """
    try:
        insights_engine = get_predictive_insights_engine()

        pattern = insights_engine.get_user_pattern(user_id)

        if pattern is None:
            raise HTTPException(status_code=404, detail="User patterns not found")

        return {
            "user_id": pattern.user_id,
            "most_active_platform": pattern.most_active_platform,
            "most_active_hours": pattern.most_active_hours,
            "avg_response_time_minutes": pattern.avg_response_time / 60 if pattern.avg_response_time else None,
            "response_probability_by_hour": pattern.response_probability_by_hour,
            "preferred_message_types": pattern.preferred_message_types
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting patterns: {str(e)}")


@router.get("/overview")
async def get_analytics_overview() -> Dict[str, Any]:
    """
    Get high-level analytics overview for dashboard.

    Returns:
        Key metrics and insights for the dashboard
    """
    try:
        message_engine = get_message_analytics_engine()
        insights_engine = get_predictive_insights_engine()
        correlation_engine = get_cross_platform_correlation_engine()

        insights_summary = insights_engine.get_insights_summary()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_analytics": {
                "total_messages": 0,  # Would come from database
                "active_threads": 0,
                "platforms_active": ["slack", "teams", "gmail"]
            },
            "predictive_insights": {
                "users_analyzed": insights_summary.get("users_analyzed", 0),
                "bottlenecks_detected": insights_summary.get("bottlenecks_detected", 0),
                "avg_response_time_minutes": insights_summary.get("avg_response_time_all_users", 0) / 60
            },
            "cross_platform": {
                "linked_conversations": len(correlation_engine.linked_conversations),
                "cross_platform_links": len(correlation_engine.cross_platform_links)
            },
            "health_status": "healthy"  # Could derive from actual metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating overview: {str(e)}")
