"""
Phase 3 User Feedback Collection System
Collects and analyzes user feedback for AI-powered chat interface

Author: Atom Platform Engineering
Date: November 9, 2025
Version: 1.0.0
"""

import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    SUGGESTION = "suggestion"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"


class SentimentRating(int, Enum):
    VERY_NEGATIVE = 1
    NEGATIVE = 2
    NEUTRAL = 3
    POSITIVE = 4
    VERY_POSITIVE = 5


class UserFeedback(BaseModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: Optional[str] = None
    feedback_type: FeedbackType
    sentiment_rating: SentimentRating
    message: str
    conversation_context: Optional[List[Dict[str, str]]] = None
    ai_analysis_applied: bool = False
    ai_sentiment_score: Optional[float] = None
    ai_intents_detected: Optional[List[str]] = None
    ai_entities_extracted: Optional[List[Dict[str, str]]] = None
    response_helpfulness: Optional[int] = Field(None, ge=1, le=5)
    response_accuracy: Optional[int] = Field(None, ge=1, le=5)
    response_speed: Optional[int] = Field(None, ge=1, le=5)
    additional_comments: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackSummary(BaseModel):
    total_feedback: int
    feedback_by_type: Dict[FeedbackType, int]
    average_sentiment: float
    average_helpfulness: Optional[float]
    average_accuracy: Optional[float]
    average_speed: Optional[float]
    common_themes: List[str]
    top_suggestions: List[str]
    feedback_trend: str  # improving, stable, declining


class FeedbackAnalytics(BaseModel):
    period_start: str
    period_end: str
    total_users: int
    total_feedback: int
    feedback_distribution: Dict[FeedbackType, int]
    sentiment_distribution: Dict[str, int]
    response_metrics: Dict[str, float]
    feature_requests: List[str]
    bug_reports: List[str]
    user_satisfaction_score: float


class Phase3FeedbackCollector:
    def __init__(self):
        self.feedback_storage: List[UserFeedback] = []
        self.analytics_cache: Dict[str, FeedbackAnalytics] = {}

    def add_feedback(self, feedback: UserFeedback) -> str:
        """Add new feedback to storage"""
        self.feedback_storage.append(feedback)

        # Invalidate analytics cache
        self.analytics_cache.clear()

        return feedback.feedback_id

    def get_feedback_by_user(self, user_id: str) -> List[UserFeedback]:
        """Get all feedback from a specific user"""
        return [fb for fb in self.feedback_storage if fb.user_id == user_id]

    def get_feedback_by_type(self, feedback_type: FeedbackType) -> List[UserFeedback]:
        """Get all feedback of a specific type"""
        return [fb for fb in self.feedback_storage if fb.feedback_type == feedback_type]

    def get_recent_feedback(self, hours: int = 24) -> List[UserFeedback]:
        """Get feedback from the last specified hours"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        return [
            fb
            for fb in self.feedback_storage
            if datetime.fromisoformat(fb.timestamp).timestamp() > cutoff_time
        ]

    def calculate_summary(self) -> FeedbackSummary:
        """Calculate summary statistics for all feedback"""
        if not self.feedback_storage:
            return FeedbackSummary(
                total_feedback=0,
                feedback_by_type={},
                average_sentiment=3.0,
                average_helpfulness=None,
                average_accuracy=None,
                average_speed=None,
                common_themes=[],
                top_suggestions=[],
                feedback_trend="stable",
            )

        # Calculate basic statistics
        total_feedback = len(self.feedback_storage)

        feedback_by_type = {}
        for fb_type in FeedbackType:
            feedback_by_type[fb_type] = len(self.get_feedback_by_type(fb_type))

        # Calculate averages
        sentiment_sum = sum(fb.sentiment_rating.value for fb in self.feedback_storage)
        average_sentiment = sentiment_sum / total_feedback

        # Calculate response metrics if available
        helpfulness_scores = [
            fb.response_helpfulness
            for fb in self.feedback_storage
            if fb.response_helpfulness
        ]
        accuracy_scores = [
            fb.response_accuracy for fb in self.feedback_storage if fb.response_accuracy
        ]
        speed_scores = [
            fb.response_speed for fb in self.feedback_storage if fb.response_speed
        ]

        average_helpfulness = (
            sum(helpfulness_scores) / len(helpfulness_scores)
            if helpfulness_scores
            else None
        )
        average_accuracy = (
            sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else None
        )
        average_speed = sum(speed_scores) / len(speed_scores) if speed_scores else None

        # Extract common themes and suggestions
        common_themes = self._extract_common_themes()
        top_suggestions = self._extract_top_suggestions()

        # Determine trend (simplified)
        recent_feedback = self.get_recent_feedback(24)
        if len(recent_feedback) > 5:
            recent_sentiment = sum(
                fb.sentiment_rating.value for fb in recent_feedback
            ) / len(recent_feedback)
            feedback_trend = (
                "improving" if recent_sentiment > average_sentiment else "declining"
            )
        else:
            feedback_trend = "stable"

        return FeedbackSummary(
            total_feedback=total_feedback,
            feedback_by_type=feedback_by_type,
            average_sentiment=average_sentiment,
            average_helpfulness=average_helpfulness,
            average_accuracy=average_accuracy,
            average_speed=average_speed,
            common_themes=common_themes,
            top_suggestions=top_suggestions,
            feedback_trend=feedback_trend,
        )

    def _extract_common_themes(self) -> List[str]:
        """Extract common themes from feedback messages"""
        # Simple keyword-based theme extraction
        themes = {
            "response_quality": [
                "slow",
                "fast",
                "accurate",
                "wrong",
                "correct",
                "helpful",
                "unhelpful",
            ],
            "ai_features": [
                "sentiment",
                "analysis",
                "smart",
                "intelligent",
                "ai",
                "understanding",
            ],
            "usability": [
                "easy",
                "difficult",
                "simple",
                "complex",
                "intuitive",
                "confusing",
            ],
            "performance": ["slow", "fast", "responsive", "laggy", "quick"],
            "reliability": ["broken", "working", "reliable", "unreliable", "stable"],
        }

        theme_counts = {theme: 0 for theme in themes.keys()}

        for feedback in self.feedback_storage:
            message_lower = feedback.message.lower()
            for theme, keywords in themes.items():
                if any(keyword in message_lower for keyword in keywords):
                    theme_counts[theme] += 1

        # Return top 3 themes
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, count in sorted_themes[:3] if count > 0]

    def _extract_top_suggestions(self) -> List[str]:
        """Extract top suggestions from feedback"""
        suggestions = []
        for feedback in self.feedback_storage:
            if feedback.feedback_type == FeedbackType.SUGGESTION:
                suggestions.append(feedback.message)
            elif feedback.feedback_type == FeedbackType.FEATURE_REQUEST:
                suggestions.append(feedback.message)

        # Return top 5 suggestions (simplified)
        return suggestions[:5]

    def generate_analytics(self, days: int = 7) -> FeedbackAnalytics:
        """Generate detailed analytics for the specified period"""
        cache_key = f"analytics_{days}"
        if cache_key in self.analytics_cache:
            return self.analytics_cache[cache_key]

        cutoff_time = datetime.now() - timedelta(days=days)
        period_feedback = [
            fb
            for fb in self.feedback_storage
            if datetime.fromisoformat(fb.timestamp) > cutoff_time
        ]

        if not period_feedback:
            return FeedbackAnalytics(
                period_start=cutoff_time.isoformat(),
                period_end=datetime.now().isoformat(),
                total_users=0,
                total_feedback=0,
                feedback_distribution={},
                sentiment_distribution={},
                response_metrics={},
                feature_requests=[],
                bug_reports=[],
                user_satisfaction_score=0.0,
            )

        # Calculate basic metrics
        total_users = len(set(fb.user_id for fb in period_feedback))
        total_feedback = len(period_feedback)

        feedback_distribution = {}
        for fb_type in FeedbackType:
            count = len([fb for fb in period_feedback if fb.feedback_type == fb_type])
            feedback_distribution[fb_type] = count

        # Sentiment distribution
        sentiment_counts = {
            "very_negative": 0,
            "negative": 0,
            "neutral": 0,
            "positive": 0,
            "very_positive": 0,
        }

        for fb in period_feedback:
            if fb.sentiment_rating == SentimentRating.VERY_NEGATIVE:
                sentiment_counts["very_negative"] += 1
            elif fb.sentiment_rating == SentimentRating.NEGATIVE:
                sentiment_counts["negative"] += 1
            elif fb.sentiment_rating == SentimentRating.NEUTRAL:
                sentiment_counts["neutral"] += 1
            elif fb.sentiment_rating == SentimentRating.POSITIVE:
                sentiment_counts["positive"] += 1
            elif fb.sentiment_rating == SentimentRating.VERY_POSITIVE:
                sentiment_counts["very_positive"] += 1

        # Response metrics
        helpfulness_scores = [
            fb.response_helpfulness for fb in period_feedback if fb.response_helpfulness
        ]
        accuracy_scores = [
            fb.response_accuracy for fb in period_feedback if fb.response_accuracy
        ]
        speed_scores = [
            fb.response_speed for fb in period_feedback if fb.response_speed
        ]

        response_metrics = {
            "average_helpfulness": sum(helpfulness_scores) / len(helpfulness_scores)
            if helpfulness_scores
            else 0,
            "average_accuracy": sum(accuracy_scores) / len(accuracy_scores)
            if accuracy_scores
            else 0,
            "average_speed": sum(speed_scores) / len(speed_scores)
            if speed_scores
            else 0,
        }

        # Extract feature requests and bug reports
        feature_requests = [
            fb.message
            for fb in period_feedback
            if fb.feedback_type == FeedbackType.FEATURE_REQUEST
        ][:10]  # Top 10

        bug_reports = [
            fb.message
            for fb in period_feedback
            if fb.feedback_type == FeedbackType.BUG_REPORT
        ][:10]  # Top 10

        # Calculate user satisfaction score (simplified)
        positive_feedback = len(
            [fb for fb in period_feedback if fb.sentiment_rating.value >= 4]
        )
        user_satisfaction = (
            (positive_feedback / total_feedback) * 100 if total_feedback > 0 else 0
        )

        analytics = FeedbackAnalytics(
            period_start=cutoff_time.isoformat(),
            period_end=datetime.now().isoformat(),
            total_users=total_users,
            total_feedback=total_feedback,
            feedback_distribution=feedback_distribution,
            sentiment_distribution=sentiment_counts,
            response_metrics=response_metrics,
            feature_requests=feature_requests,
            bug_reports=bug_reports,
            user_satisfaction_score=user_satisfaction,
        )

        # Cache the results
        self.analytics_cache[cache_key] = analytics
        return analytics

    def export_feedback(self, format_type: str = "json") -> str:
        """Export feedback data in specified format"""
        if format_type == "json":
            return json.dumps([fb.dict() for fb in self.feedback_storage], indent=2)
        else:
            raise ValueError(f"Unsupported format: {format_type}")


# Initialize FastAPI app
app = FastAPI(
    title="Phase 3 Feedback Collection System",
    description="Collect and analyze user feedback for AI-powered chat interface",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize feedback collector
feedback_collector = Phase3FeedbackCollector()


# Background task for analytics processing
async def process_feedback_analytics():
    """Background task to process feedback analytics"""
    # This could be extended to send notifications, generate reports, etc.
    pass


# API Routes
@app.post("/api/v1/feedback/submit")
async def submit_feedback(
    feedback: UserFeedback, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """Submit user feedback"""
    try:
        feedback_id = feedback_collector.add_feedback(feedback)
        background_tasks.add_task(process_feedback_analytics)

        return {
            "status": "success",
            "feedback_id": feedback_id,
            "message": "Feedback submitted successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to submit feedback: {str(e)}"
        )


@app.get("/api/v1/feedback/summary")
async def get_feedback_summary() -> FeedbackSummary:
    """Get feedback summary"""
    return feedback_collector.calculate_summary()


@app.get("/api/v1/feedback/analytics")
async def get_feedback_analytics(days: int = 7) -> FeedbackAnalytics:
    """Get detailed feedback analytics"""
    if days not in [1, 7, 30]:
        raise HTTPException(status_code=400, detail="Days must be 1, 7, or 30")

    return feedback_collector.generate_analytics(days)


@app.get("/api/v1/feedback/user/{user_id}")
async def get_user_feedback(user_id: str) -> List[UserFeedback]:
    """Get all feedback from a specific user"""
    return feedback_collector.get_feedback_by_user(user_id)


@app.get("/api/v1/feedback/type/{feedback_type}")
async def get_feedback_by_type(feedback_type: FeedbackType) -> List[UserFeedback]:
    """Get feedback by type"""
    return feedback_collector.get_feedback_by_type(feedback_type)


@app.get("/api/v1/feedback/recent")
async def get_recent_feedback(hours: int = 24) -> List[UserFeedback]:
    """Get recent feedback"""
    if hours > 168:  # 1 week max
        raise HTTPException(status_code=400, detail="Hours cannot exceed 168 (1 week)")

    return feedback_collector.get_recent_feedback(hours)


@app.get("/api/v1/feedback/export")
async def export_feedback(format_type: str = "json") -> Dict[str, str]:
    """Export feedback data"""
    try:
        data = feedback_collector.export_feedback(format_type)
        return {"status": "success", "format": format_type, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    summary = feedback_collector.calculate_summary()

    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "feedback_stats": {
            "total_feedback": summary.total_feedback,
            "average_sentiment": summary.average_sentiment,
            "user_satisfaction": f"{summary.average_sentiment * 20:.1f}%",  # Convert to percentage
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "phase3_feedback_collection:app",
        host="0.0.0.0",
        port=5064,
        reload=True,
        log_level="info",
    )
