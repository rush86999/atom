import asyncio
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()


# Pydantic models
class AnalyticsTimeRange(BaseModel):
    start_date: str = Field(..., description="Start date in ISO format")
    end_date: str = Field(..., description="End date in ISO format")
    granularity: str = Field(
        "daily", description="Time granularity: hourly, daily, weekly"
    )


class ConversationMetrics(BaseModel):
    conversation_id: str = Field(..., description="Conversation identifier")
    user_id: str = Field(..., description="User identifier")
    message_count: int = Field(..., description="Number of messages")
    avg_response_time: float = Field(
        ..., description="Average response time in seconds"
    )
    sentiment_score: Optional[float] = Field(
        None, description="Sentiment score (-1 to 1)"
    )
    engagement_score: float = Field(..., description="User engagement score (0-100)")
    topics: List[str] = Field(
        default_factory=list, description="Detected conversation topics"
    )
    created_at: str = Field(..., description="Conversation start timestamp")


class UserAnalytics(BaseModel):
    user_id: str = Field(..., description="User identifier")
    total_messages: int = Field(..., description="Total messages sent")
    active_days: int = Field(..., description="Number of active days")
    avg_session_duration: float = Field(
        ..., description="Average session duration in minutes"
    )
    favorite_features: List[str] = Field(
        default_factory=list, description="Most used features"
    )
    satisfaction_score: Optional[float] = Field(
        None, description="User satisfaction score"
    )
    last_active: str = Field(..., description="Last activity timestamp")


class SystemPerformance(BaseModel):
    timestamp: str = Field(..., description="Timestamp")
    active_users: int = Field(..., description="Number of active users")
    message_throughput: float = Field(..., description="Messages per second")
    avg_response_time: float = Field(..., description="Average response time in ms")
    error_rate: float = Field(..., description="Error rate percentage")
    cpu_usage: float = Field(..., description="CPU usage percentage")
    memory_usage: float = Field(..., description="Memory usage percentage")


class AnalyticsDashboard(BaseModel):
    time_range: AnalyticsTimeRange = Field(..., description="Time range for analytics")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    user_analytics: List[UserAnalytics] = Field(..., description="User analytics data")
    conversation_metrics: List[ConversationMetrics] = Field(
        ..., description="Conversation metrics"
    )
    system_performance: List[SystemPerformance] = Field(
        ..., description="System performance data"
    )
    trends: Dict[str, Any] = Field(..., description="Trend analysis")
    recommendations: List[str] = Field(..., description="Actionable recommendations")


# Analytics service
class AnalyticsService:
    def __init__(self):
        self.conversation_data = {}
        self.user_data = {}
        self.system_metrics = []
        self.message_log = []

        # Initialize sample data for demonstration
        self._initialize_sample_data()

    def _initialize_sample_data(self):
        """Initialize sample analytics data for demonstration"""
        # Sample conversation data
        sample_conversations = [
            {
                "conversation_id": "conv_001",
                "user_id": "user_001",
                "message_count": 15,
                "avg_response_time": 2.5,
                "sentiment_score": 0.8,
                "engagement_score": 85.0,
                "topics": ["task_management", "scheduling", "productivity"],
                "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
            },
            {
                "conversation_id": "conv_002",
                "user_id": "user_002",
                "message_count": 8,
                "avg_response_time": 1.8,
                "sentiment_score": 0.6,
                "engagement_score": 72.0,
                "topics": ["file_sharing", "collaboration"],
                "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
            },
            {
                "conversation_id": "conv_003",
                "user_id": "user_001",
                "message_count": 22,
                "avg_response_time": 3.2,
                "sentiment_score": 0.9,
                "engagement_score": 92.0,
                "topics": ["workflow_automation", "integration"],
                "created_at": datetime.now().isoformat(),
            },
        ]

        for conv in sample_conversations:
            self.conversation_data[conv["conversation_id"]] = conv

        # Sample user data
        sample_users = [
            {
                "user_id": "user_001",
                "total_messages": 150,
                "active_days": 14,
                "avg_session_duration": 25.5,
                "favorite_features": ["chat", "file_upload", "voice_commands"],
                "satisfaction_score": 4.8,
                "last_active": datetime.now().isoformat(),
            },
            {
                "user_id": "user_002",
                "total_messages": 85,
                "active_days": 8,
                "avg_session_duration": 18.2,
                "favorite_features": ["chat", "analytics"],
                "satisfaction_score": 4.5,
                "last_active": (datetime.now() - timedelta(hours=2)).isoformat(),
            },
        ]

        for user in sample_users:
            self.user_data[user["user_id"]] = user

        # Sample system metrics
        for i in range(24):
            timestamp = (datetime.now() - timedelta(hours=i)).isoformat()
            self.system_metrics.append(
                {
                    "timestamp": timestamp,
                    "active_users": max(1, 50 - i * 2),
                    "message_throughput": max(0.5, 10.0 - i * 0.4),
                    "avg_response_time": 150 + i * 5,
                    "error_rate": max(0.1, 1.0 - i * 0.04),
                    "cpu_usage": 30 + i * 2,
                    "memory_usage": 45 + i * 1.5,
                }
            )

    async def record_message(self, message_data: Dict[str, Any]):
        """Record a new message for analytics"""
        try:
            message_log_entry = {
                "message_id": str(len(self.message_log) + 1),
                "user_id": message_data.get("user_id"),
                "conversation_id": message_data.get("conversation_id"),
                "message_type": message_data.get("message_type", "text"),
                "timestamp": datetime.now().isoformat(),
                "response_time": message_data.get("response_time"),
                "has_attachments": message_data.get("has_attachments", False),
                "workflow_triggered": message_data.get("workflow_triggered", False),
            }

            self.message_log.append(message_log_entry)

            # Update user analytics
            user_id = message_data.get("user_id")
            if user_id:
                if user_id not in self.user_data:
                    self.user_data[user_id] = {
                        "user_id": user_id,
                        "total_messages": 0,
                        "active_days": 1,
                        "avg_session_duration": 0,
                        "favorite_features": [],
                        "satisfaction_score": None,
                        "last_active": datetime.now().isoformat(),
                    }

                self.user_data[user_id]["total_messages"] += 1
                self.user_data[user_id]["last_active"] = datetime.now().isoformat()

            logger.info(f"Recorded message analytics for user {user_id}")

        except Exception as e:
            logger.error(f"Error recording message analytics: {e}")

    async def record_conversation_metrics(self, conversation_data: Dict[str, Any]):
        """Record conversation metrics"""
        try:
            conversation_id = conversation_data.get("conversation_id")
            if conversation_id:
                self.conversation_data[conversation_id] = conversation_data
                logger.info(f"Recorded conversation metrics for {conversation_id}")
        except Exception as e:
            logger.error(f"Error recording conversation metrics: {e}")

    async def record_system_metrics(self, metrics_data: Dict[str, Any]):
        """Record system performance metrics"""
        try:
            metrics_entry = {
                "timestamp": datetime.now().isoformat(),
                "active_users": metrics_data.get("active_users", 0),
                "message_throughput": metrics_data.get("message_throughput", 0.0),
                "avg_response_time": metrics_data.get("avg_response_time", 0.0),
                "error_rate": metrics_data.get("error_rate", 0.0),
                "cpu_usage": metrics_data.get("cpu_usage", 0.0),
                "memory_usage": metrics_data.get("memory_usage", 0.0),
            }

            self.system_metrics.append(metrics_entry)

            # Keep only last 1000 metrics entries
            if len(self.system_metrics) > 1000:
                self.system_metrics = self.system_metrics[-1000:]

        except Exception as e:
            logger.error(f"Error recording system metrics: {e}")

    async def get_dashboard_data(
        self, time_range: AnalyticsTimeRange
    ) -> AnalyticsDashboard:
        """Get comprehensive analytics dashboard data"""
        try:
            start_date = datetime.fromisoformat(
                time_range.start_date.replace("Z", "+00:00")
            )
            end_date = datetime.fromisoformat(
                time_range.end_date.replace("Z", "+00:00")
            )

            # Filter data by time range
            filtered_conversations = [
                conv
                for conv in self.conversation_data.values()
                if start_date
                <= datetime.fromisoformat(conv["created_at"].replace("Z", "+00:00"))
                <= end_date
            ]

            filtered_system_metrics = [
                metric
                for metric in self.system_metrics
                if start_date
                <= datetime.fromisoformat(metric["timestamp"].replace("Z", "+00:00"))
                <= end_date
            ]

            # Calculate summary statistics
            summary = await self._calculate_summary_statistics(
                filtered_conversations, filtered_system_metrics, time_range
            )

            # Get user analytics
            user_analytics = await self._get_user_analytics(time_range)

            # Get conversation metrics
            conversation_metrics = [
                ConversationMetrics(**conv) for conv in filtered_conversations
            ]

            # Get system performance data
            system_performance = [
                SystemPerformance(**metric) for metric in filtered_system_metrics
            ]

            # Calculate trends
            trends = await self._calculate_trends(time_range)

            # Generate recommendations
            recommendations = await self._generate_recommendations(summary, trends)

            return AnalyticsDashboard(
                time_range=time_range,
                summary=summary,
                user_analytics=user_analytics,
                conversation_metrics=conversation_metrics,
                system_performance=system_performance,
                trends=trends,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error(f"Error generating dashboard data: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to generate analytics dashboard"
            )

    async def _calculate_summary_statistics(
        self,
        conversations: List[Dict],
        system_metrics: List[Dict],
        time_range: AnalyticsTimeRange,
    ) -> Dict[str, Any]:
        """Calculate summary statistics for the dashboard"""
        total_messages = sum(conv["message_count"] for conv in conversations)
        total_conversations = len(conversations)
        active_users = len(set(conv["user_id"] for conv in conversations))

        if conversations:
            avg_response_time = sum(
                conv["avg_response_time"] for conv in conversations
            ) / len(conversations)
            avg_engagement = sum(
                conv["engagement_score"] for conv in conversations
            ) / len(conversations)
            avg_sentiment = sum(
                conv.get("sentiment_score", 0)
                for conv in conversations
                if conv.get("sentiment_score")
            ) / len([conv for conv in conversations if conv.get("sentiment_score")])
        else:
            avg_response_time = 0
            avg_engagement = 0
            avg_sentiment = 0

        if system_metrics:
            avg_throughput = sum(
                metric["message_throughput"] for metric in system_metrics
            ) / len(system_metrics)
            avg_error_rate = sum(
                metric["error_rate"] for metric in system_metrics
            ) / len(system_metrics)
        else:
            avg_throughput = 0
            avg_error_rate = 0

        return {
            "total_messages": total_messages,
            "total_conversations": total_conversations,
            "active_users": active_users,
            "avg_response_time_seconds": round(avg_response_time, 2),
            "avg_engagement_score": round(avg_engagement, 1),
            "avg_sentiment_score": round(avg_sentiment, 2),
            "avg_message_throughput": round(avg_throughput, 2),
            "avg_error_rate_percent": round(avg_error_rate, 2),
            "time_range_days": (
                datetime.fromisoformat(time_range.end_date.replace("Z", "+00:00"))
                - datetime.fromisoformat(time_range.start_date.replace("Z", "+00:00"))
            ).days,
        }

    async def _get_user_analytics(
        self, time_range: AnalyticsTimeRange
    ) -> List[UserAnalytics]:
        """Get user analytics data"""
        user_analytics = []

        for user_data in self.user_data.values():
            # Convert to UserAnalytics model
            user_analytics.append(UserAnalytics(**user_data))

        return user_analytics

    async def _calculate_trends(self, time_range: AnalyticsTimeRange) -> Dict[str, Any]:
        """Calculate trends for the analytics dashboard"""
        # For demonstration, return mock trends
        # In production, calculate actual trends from historical data

        return {
            "user_growth": {
                "trend": "up",
                "percentage": 15.2,
                "description": "User base growing steadily",
            },
            "engagement": {
                "trend": "up",
                "percentage": 8.7,
                "description": "User engagement increasing",
            },
            "response_time": {
                "trend": "down",
                "percentage": -12.3,
                "description": "Response times improving",
            },
            "error_rate": {
                "trend": "down",
                "percentage": -5.6,
                "description": "Error rates decreasing",
            },
        }

    async def _generate_recommendations(
        self, summary: Dict[str, Any], trends: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on analytics"""
        recommendations = []

        # Response time recommendations
        if summary["avg_response_time_seconds"] > 3.0:
            recommendations.append(
                "Consider optimizing response times for better user experience"
            )

        # Engagement recommendations
        if summary["avg_engagement_score"] < 70:
            recommendations.append("Explore features to increase user engagement")

        # Error rate recommendations
        if summary["avg_error_rate_percent"] > 2.0:
            recommendations.append("Investigate and reduce system error rates")

        # User growth recommendations
        if trends["user_growth"]["percentage"] < 5:
            recommendations.append(
                "Consider marketing initiatives to boost user acquisition"
            )

        # Add general recommendations
        recommendations.extend(
            [
                "Monitor system performance during peak usage hours",
                "Collect user feedback to identify improvement areas",
                "Consider A/B testing for new feature adoption",
            ]
        )

        return recommendations

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time system metrics"""
        try:
            if not self.system_metrics:
                return {}

            latest_metrics = self.system_metrics[-1]

            # Calculate real-time statistics
            active_conversations = len(
                [
                    conv
                    for conv in self.conversation_data.values()
                    if (
                        datetime.now()
                        - datetime.fromisoformat(
                            conv["created_at"].replace("Z", "+00:00")
                        )
                    ).total_seconds()
                    < 3600
                ]
            )

            recent_messages = len(
                [
                    msg
                    for msg in self.message_log
                    if (
                        datetime.now()
                        - datetime.fromisoformat(
                            msg["timestamp"].replace("Z", "+00:00")
                        )
                    ).total_seconds()
                    < 300
                ]
            )

            return {
                "active_users": latest_metrics["active_users"],
                "active_conversations": active_conversations,
                "messages_last_5min": recent_messages,
                "current_throughput": latest_metrics["message_throughput"],
                "avg_response_time": latest_metrics["avg_response_time"],
                "system_health": "healthy"
                if latest_metrics["error_rate"] < 2.0
                else "degraded",
            }

        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            return {}


# Initialize analytics service
analytics_service = AnalyticsService()


# API endpoints
@router.post("/api/v1/analytics/dashboard", response_model=AnalyticsDashboard)
async def get_analytics_dashboard(time_range: AnalyticsTimeRange):
    """Get comprehensive analytics dashboard"""
    return await analytics_service.get_dashboard_data(time_range)


@router.post("/api/v1/analytics/messages")
async def record_message_analytics(message_data: Dict[str, Any]):
    """Record message analytics"""
    await analytics_service.record_message(message_data)
    return {"status": "success", "message": "Message analytics recorded"}


@router.post("/api/v1/analytics/conversations")
async def record_conversation_metrics(conversation_data: Dict[str, Any]):
    """Record conversation metrics"""
    await analytics_service.record_conversation_metrics(conversation_data)
    return {"status": "success", "message": "Conversation metrics recorded"}


@router.post("/api/v1/analytics/system")
async def record_system_metrics(metrics_data: Dict[str, Any]):
    """Record system performance metrics"""
    await analytics_service.record_system_metrics(metrics_data)
