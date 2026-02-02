"""
Message Analytics Engine
Provides analytics and insights from unified message data across platforms.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Message sentiment levels"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class MessageStats:
    """Statistics for a set of messages"""
    total_messages: int = 0
    total_words: int = 0
    total_characters: int = 0
    with_attachments: int = 0
    with_mentions: int = 0
    with_urls: int = 0
    sentiment_distribution: Dict[str, int] = field(default_factory=lambda: {
        "positive": 0,
        "negative": 0,
        "neutral": 0
    })


@dataclass
class ResponseTimeMetrics:
    """Response time metrics in seconds"""
    avg_response_time: float = 0.0
    median_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    total_responses: int = 0
    response_times: List[float] = field(default_factory=list)


@dataclass
class ThreadParticipation:
    """Thread participation metrics"""
    thread_id: str = ""
    total_messages: int = 0
    participants: Dict[str, int] = field(default_factory=dict)  # user_id -> message_count
    most_active_participant: Optional[str] = None
    average_messages_per_user: float = 0.0


@dataclass
class ActivityMetrics:
    """Activity metrics for time periods"""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    messages_per_hour: Dict[str, int] = field(default_factory=dict)  # hour -> count
    messages_per_day: Dict[str, int] = field(default_factory=dict)   # day -> count
    messages_per_channel: Dict[str, int] = field(default_factory=dict)  # channel_id -> count
    peak_hours: List[Tuple[str, int]] = field(default_factory=list)  # (hour, count)
    peak_days: List[Tuple[str, int]] = field(default_factory=list)   # (day, count)


class MessageAnalyticsEngine:
    """
    Engine for analyzing messages and extracting actionable insights.

    Features:
    - Sentiment analysis (keyword-based, no ML dependencies)
    - Response time calculation
    - Thread participation metrics
    - Peak activity detection
    - Cross-platform analytics
    """

    # Sentiment keywords (lightweight approach without heavy ML)
    POSITIVE_KEYWORDS = [
        "thank", "great", "awesome", "good", "love", "appreciate", "happy",
        "excited", "amazing", "excellent", "perfect", "wonderful", "fantastic",
        "brilliant", "helpful", "thanks", "thx", "👍", "🎉", "✨", "💯"
    ]

    NEGATIVE_KEYWORDS = [
        "bad", "terrible", "awful", "hate", "worst", "sucks", "issue",
        "problem", "error", "fail", "failed", "failure", "broken", "bug", "mistake", "sorry", "apologize",
        "frustrated", "confused", "annoyed", "upset", "angry", "disappointed",
        "nothing works", "doesn't work", "not working"
    ]

    def __init__(self):
        # Cache for analytics results
        self.analytics_cache: Dict[str, Any] = {}

        # Thread response tracking
        self.thread_last_message: Dict[str, datetime] = {}
        self.thread_response_times: Dict[str, List[float]] = {}

    def analyze_sentiment(self, text: str) -> SentimentLevel:
        """
        Analyze sentiment of message text using keyword matching.

        Args:
            text: Message text to analyze

        Returns:
            SentimentLevel (positive, negative, or neutral)
        """
        if not text:
            return SentimentLevel.NEUTRAL

        text_lower = text.lower()

        # Count positive and negative keywords
        positive_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text_lower)
        negative_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text_lower)

        # Determine sentiment
        if positive_count > negative_count:
            return SentimentLevel.POSITIVE
        elif negative_count > positive_count:
            return SentimentLevel.NEGATIVE
        else:
            return SentimentLevel.NEUTRAL

    def calculate_message_stats(self, messages: List[Dict[str, Any]]) -> MessageStats:
        """
        Calculate basic statistics for a set of messages.

        Args:
            messages: List of unified messages

        Returns:
            MessageStats with counts and distributions
        """
        stats = MessageStats()

        for msg in messages:
            stats.total_messages += 1

            # Word count
            content = msg.get("content", "")
            words = content.split()
            stats.total_words += len(words)
            stats.total_characters += len(content)

            # Attachments
            if msg.get("has_attachments"):
                stats.with_attachments += 1

            # Mentions
            mentions = msg.get("mentions", [])
            if mentions:
                stats.with_mentions += 1

            # URLs
            urls = msg.get("urls", [])
            if urls:
                stats.with_urls += 1

            # Sentiment
            sentiment = self.analyze_sentiment(content)
            stats.sentiment_distribution[sentiment.value] += 1

        return stats

    def calculate_response_times(
        self,
        messages: List[Dict[str, Any]]
    ) -> ResponseTimeMetrics:
        """
        Calculate response time metrics from threaded conversations.

        Args:
            messages: List of unified messages with thread info

        Returns:
            ResponseTimeMetrics with percentiles
        """
        response_times = []

        # Group messages by thread
        threads: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for msg in messages:
            thread_id = msg.get("thread_id") or msg.get("conversation_id")
            if thread_id:
                threads[thread_id].append(msg)

        # Calculate response times for each thread
        for thread_id, thread_messages in threads.items():
            # Sort by timestamp
            sorted_messages = sorted(
                thread_messages,
                key=lambda m: m.get("timestamp", datetime.min)
            )

            # Calculate time between consecutive messages
            for i in range(1, len(sorted_messages)):
                prev_time = sorted_messages[i - 1].get("timestamp")
                curr_time = sorted_messages[i].get("timestamp")

                if prev_time and curr_time:
                    # Calculate time difference in seconds
                    if isinstance(prev_time, str):
                        prev_time = datetime.fromisoformat(prev_time)
                    if isinstance(curr_time, str):
                        curr_time = datetime.fromisoformat(curr_time)

                    if isinstance(prev_time, datetime) and isinstance(curr_time, datetime):
                        diff = (curr_time - prev_time).total_seconds()
                        # Only count responses between 30 seconds and 24 hours
                        if 30 <= diff <= 86400:
                            response_times.append(diff)

        if not response_times:
            return ResponseTimeMetrics()

        # Calculate metrics
        response_times.sort()
        total = len(response_times)

        metrics = ResponseTimeMetrics(
            avg_response_time=sum(response_times) / total,
            median_response_time=response_times[total // 2],
            p95_response_time=response_times[int(total * 0.95)] if total >= 20 else response_times[-1],
            p99_response_time=response_times[int(total * 0.99)] if total >= 100 else response_times[-1],
            total_responses=total,
            response_times=response_times
        )

        return metrics

    def analyze_thread_participation(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, ThreadParticipation]:
        """
        Analyze participation in conversations.

        Args:
            messages: List of unified messages

        Returns:
            Dictionary mapping thread_id to ThreadParticipation
        """
        threads: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Group by thread
        for msg in messages:
            thread_id = msg.get("thread_id") or msg.get("conversation_id")
            if thread_id:
                threads[thread_id].append(msg)

        # Analyze each thread
        participation = {}

        for thread_id, thread_messages in threads.items():
            thread_stats = ThreadParticipation(thread_id=thread_id)

            # Count messages per user
            user_message_counts = Counter()
            for msg in thread_messages:
                sender = msg.get("sender_name", "unknown")
                user_message_counts[sender] += 1

            thread_stats.total_messages = len(thread_messages)
            thread_stats.participants = dict(user_message_counts)

            # Find most active participant
            if user_message_counts:
                most_active = max(user_message_counts.items(), key=lambda x: x[1])
                thread_stats.most_active_participant = most_active[0]
                thread_stats.average_messages_per_user = (
                    sum(user_message_counts.values()) / len(user_message_counts)
                )

            participation[thread_id] = thread_stats

        return participation

    def detect_peak_activity(
        self,
        messages: List[Dict[str, Any]],
        period: str = "daily"
    ) -> ActivityMetrics:
        """
        Detect peak activity times from messages.

        Args:
            messages: List of unified messages
            period: "hourly", "daily", or "weekly"

        Returns:
            ActivityMetrics with peak times
        """
        if not messages:
            return ActivityMetrics()

        # Build activity metrics
        metrics = ActivityMetrics()

        if period == "hourly":
            # Aggregate by hour across all days
            hourly_counts = defaultdict(int)
            for msg in messages:
                timestamp = msg.get("timestamp")
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp)
                    except (ValueError, TypeError):
                        continue
                elif not isinstance(timestamp, datetime):
                    continue

                hour = f"{timestamp.hour:02d}:00"
                hourly_counts[hour] += 1

            # Find peak hours
            peak_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            metrics.peak_hours = peak_hours
            metrics.messages_per_hour = dict(hourly_counts)

        elif period == "daily":
            daily_counts = defaultdict(int)
            channel_counts = defaultdict(int)

            for msg in messages:
                timestamp = msg.get("timestamp")
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp)
                    except (ValueError, TypeError):
                        continue
                elif not isinstance(timestamp, datetime):
                    continue

                day = timestamp.strftime("%Y-%m-%d")
                daily_counts[day] += 1

                channel = msg.get("channel_id", "unknown")
                channel_counts[channel] += 1

            # Find peak days
            peak_days = sorted(daily_counts.items(), key=lambda x: x[1], reverse=True)[:7]
            metrics.peak_days = peak_days
            metrics.messages_per_day = dict(daily_counts)
            metrics.messages_per_channel = dict(channel_counts)

        return metrics

    def get_cross_platform_analytics(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get cross-platform analytics comparing activity across platforms.

        Args:
            messages: List of unified messages

        Returns:
            Dictionary with cross-platform insights
        """
        platform_stats = defaultdict(lambda: {
            "message_count": 0,
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
            "avg_response_time": 0,
            "total_attachments": 0
        })

        # Group by platform
        for msg in messages:
            platform = msg.get("platform", "unknown")
            stats = platform_stats[platform]

            stats["message_count"] += 1

            # Sentiment
            sentiment = self.analyze_sentiment(msg.get("content", ""))
            stats["sentiment"][sentiment.value] += 1

            # Attachments
            if msg.get("has_attachments"):
                stats["total_attachments"] += 1

        # Calculate response times per platform
        for platform in platform_stats.keys():
            platform_messages = [m for m in messages if m.get("platform") == platform]
            response_metrics = self.calculate_response_times(platform_messages)
            if response_metrics.total_responses > 0:
                platform_stats[platform]["avg_response_time"] = response_metrics.avg_response_time

        return {
            "platforms": dict(platform_stats),
            "total_messages": len(messages),
            "most_active_platform": max(
                platform_stats.items(),
                key=lambda x: x[1]["message_count"]
            )[0] if platform_stats else None
        }

    def get_analytics_summary(
        self,
        messages: List[Dict[str, Any]],
        time_window: str = "24h"
    ) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary for a time window.

        Args:
            messages: List of unified messages
            time_window: "24h", "7d", "30d", or "all"

        Returns:
            Dictionary with analytics summary
        """
        # Filter by time window
        now = datetime.now(timezone.utc)
        if time_window == "24h":
            cutoff = now - timedelta(hours=24)
        elif time_window == "7d":
            cutoff = now - timedelta(days=7)
        elif time_window == "30d":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = None

        filtered_messages = messages
        if cutoff:
            filtered_messages = [
                m for m in messages
                if self._parse_timestamp(m.get("timestamp")) >= cutoff
            ]

        # Calculate various analytics
        stats = self.calculate_message_stats(filtered_messages)
        response_metrics = self.calculate_response_times(filtered_messages)
        participation = self.analyze_thread_participation(filtered_messages)
        activity = self.detect_peak_activity(filtered_messages, period="daily")
        cross_platform = self.get_cross_platform_analytics(filtered_messages)

        return {
            "time_window": time_window,
            "period": {
                "start": cutoff.isoformat() if cutoff else None,
                "end": now.isoformat()
            },
            "message_stats": {
                "total_messages": stats.total_messages,
                "total_words": stats.total_words,
                "avg_words_per_message": (
                    stats.total_words / stats.total_messages if stats.total_messages > 0 else 0
                ),
                "with_attachments": stats.with_attachments,
                "with_mentions": stats.with_mentions,
                "with_urls": stats.with_urls,
                "sentiment_distribution": stats.sentiment_distribution
            },
            "response_times": {
                "avg_response_seconds": response_metrics.avg_response_time,
                "median_response_seconds": response_metrics.median_response_time,
                "p95_response_seconds": response_metrics.p95_response_time,
                "p99_response_seconds": response_metrics.p99_response_time,
                "total_responses_analyzed": response_metrics.total_responses
            },
            "thread_participation": {
                "total_threads": len(participation),
                "avg_messages_per_thread": (
                    sum(p.total_messages for p in participation.values()) / len(participation)
                    if participation else 0
                ),
                "most_active_threads": sorted(
                    participation.items(),
                    key=lambda x: x[1].total_messages,
                    reverse=True
                )[:5]
            },
            "activity_peaks": {
                "peak_days": activity.peak_days[:7] if activity.peak_days else [],
                "messages_per_day": activity.messages_per_day
            },
            "cross_platform": cross_platform
        }

    def _parse_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """Helper to parse timestamp to datetime"""
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                return None

        return None


# Singleton instance
analytics_engine = MessageAnalyticsEngine()


def get_message_analytics_engine() -> MessageAnalyticsEngine:
    """Get the singleton message analytics engine"""
    return analytics_engine
