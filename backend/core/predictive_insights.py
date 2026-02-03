"""
Predictive Insights Engine
Provides ML-style predictions for response times, optimal channels, and bottlenecks.
"""

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class UrgencyLevel(Enum):
    """Message urgency levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RecommendationConfidence(Enum):
    """Confidence level in recommendations"""
    HIGH = "high"       # Strong statistical evidence
    MEDIUM = "medium"   # Moderate evidence
    LOW = "low"         # Limited data


@dataclass
class ResponseTimePrediction:
    """Prediction for message response time"""
    user_id: str
    predicted_seconds: float
    confidence: RecommendationConfidence
    factors: Dict[str, Any] = field(default_factory=dict)
    time_window: Optional[Tuple[datetime, datetime]] = None


@dataclass
class ChannelRecommendation:
    """Recommendation for optimal communication channel"""
    user_id: str
    recommended_platform: str
    reason: str
    confidence: RecommendationConfidence
    expected_response_time: Optional[float] = None
    alternatives: List[str] = field(default_factory=list)


@dataclass
class BottleneckAlert:
    """Alert for communication bottleneck"""
    severity: UrgencyLevel
    thread_id: str
    platform: str
    description: str
    affected_users: List[str]
    wait_time_seconds: float
    suggested_action: str


@dataclass
class CommunicationPattern:
    """Pattern in user's communication behavior"""
    user_id: str
    most_active_hours: List[int]  # Hours of day (0-23)
    most_active_platform: str
    avg_response_time: float
    response_probability_by_hour: Dict[int, float]  # hour -> probability
    preferred_message_types: List[str]


class PredictiveInsightsEngine:
    """
    Engine for generating predictive insights from communication data.

    Features:
    - Response time prediction based on historical patterns
    - Optimal channel recommendations
    - Bottleneck detection and alerting
    - Communication pattern analysis
    """

    def __init__(self, min_data_points: int = 5):
        """
        Initialize the predictive insights engine.

        Args:
            min_data_points: Minimum messages required for predictions
        """
        self.min_data_points = min_data_points
        self.user_patterns: Dict[str, CommunicationPattern] = {}
        self.thread_activity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def analyze_historical_data(self, messages: List[Dict[str, Any]]) -> None:
        """
        Analyze historical messages to build predictive models.

        Args:
            messages: List of historical messages
        """
        # Group by user
        user_messages = defaultdict(list)
        for msg in messages:
            sender = msg.get("sender_name") or msg.get("sender") or "unknown"
            user_messages[sender].append(msg)

        # Analyze patterns for each user
        for user_id, user_msgs in user_messages.items():
            pattern = self._analyze_user_patterns(user_id, user_msgs)
            if pattern:
                self.user_patterns[user_id] = pattern

        # Track thread activity
        for msg in messages:
            thread_id = msg.get("thread_id") or msg.get("conversation_id") or "no_thread"
            self.thread_activity[thread_id].append(msg)

    def predict_response_time(
        self,
        recipient: str,
        platform: str,
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        time_of_day: Optional[datetime] = None
    ) -> ResponseTimePrediction:
        """
        Predict how long it will take for a user to respond.

        Args:
            recipient: User ID or name
            platform: Platform to send on
            urgency: Message urgency
            time_of_day: When message will be sent (default: now)

        Returns:
            ResponseTimePrediction with predicted time and confidence
        """
        if time_of_day is None:
            time_of_day = datetime.now(timezone.utc)

        # Get user pattern if available
        pattern = self.user_patterns.get(recipient)

        if not pattern:
            # No data - use platform defaults
            default_times = {
                "slack": 1800,      # 30 minutes
                "teams": 2400,      # 40 minutes
                "gmail": 86400,     # 1 day
                "outlook": 86400    # 1 day
            }
            base_time = default_times.get(platform, 3600)
            urgency_multiplier = {
                UrgencyLevel.LOW: 1.5,
                UrgencyLevel.MEDIUM: 1.0,
                UrgencyLevel.HIGH: 0.5,
                UrgencyLevel.URGENT: 0.25
            }

            return ResponseTimePrediction(
                user_id=recipient,
                predicted_seconds=base_time * urgency_multiplier.get(urgency, 1.0),
                confidence=RecommendationConfidence.LOW,
                factors={
                    "platform": platform,
                    "urgency": urgency.value,
                    "data_available": False
                }
            )

        # Use historical pattern
        hour = time_of_day.hour
        response_prob = pattern.response_probability_by_hour.get(hour, 0.5)

        # Calculate expected response time
        base_time = pattern.avg_response_time

        # Adjust by time of day (lower probability = longer time)
        if response_prob > 0.7:
            time_multiplier = 0.5
        elif response_prob > 0.4:
            time_multiplier = 1.0
        else:
            time_multiplier = 2.0

        # Adjust by platform match
        platform_multiplier = 1.0 if platform == pattern.most_active_platform else 1.5

        # Adjust by urgency
        urgency_multiplier = {
            UrgencyLevel.LOW: 1.2,
            UrgencyLevel.MEDIUM: 1.0,
            UrgencyLevel.HIGH: 0.7,
            UrgencyLevel.URGENT: 0.4
        }

        predicted = base_time * time_multiplier * platform_multiplier * urgency_multiplier.get(urgency, 1.0)

        # Determine confidence based on data amount
        data_points = len(self.thread_activity)  # Approximation
        if data_points >= 50:
            confidence = RecommendationConfidence.HIGH
        elif data_points >= self.min_data_points:
            confidence = RecommendationConfidence.MEDIUM
        else:
            confidence = RecommendationConfidence.LOW

        return ResponseTimePrediction(
            user_id=recipient,
            predicted_seconds=predicted,
            confidence=confidence,
            factors={
                "platform": platform,
                "urgency": urgency.value,
                "hour_of_day": hour,
                "response_probability": response_prob,
                "data_available": True,
                "platform_match": platform == pattern.most_active_platform
            }
        )

    def recommend_channel(
        self,
        recipient: str,
        message_type: str = "general",
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    ) -> ChannelRecommendation:
        """
        Recommend the best communication channel for a user.

        Args:
            recipient: User ID or name
            message_type: Type of message (general, urgent, file_share, etc.)
            urgency: Message urgency

        Returns:
            ChannelRecommendation with optimal platform
        """
        pattern = self.user_patterns.get(recipient)

        if not pattern:
            # No data - recommend Slack as default
            return ChannelRecommendation(
                user_id=recipient,
                recommended_platform="slack",
                reason="No historical data available - using default",
                confidence=RecommendationConfidence.LOW,
                alternatives=["teams", "gmail"]
            )

        # Recommend most active platform
        recommended = pattern.most_active_platform

        # Adjust for urgency
        if urgency == UrgencyLevel.URGENT:
            # For urgent messages, prefer real-time platforms
            if recommended in ["gmail", "outlook"]:
                recommended = "slack"
                reason = "Urgent message - switching to real-time platform"
            else:
                reason = f"Urgent message - using most active platform"
        elif message_type in pattern.preferred_message_types:
            reason = f"Platform matches user's preferred message types"
        else:
            reason = f"User's most active platform"

        # Calculate expected response time
        prediction = self.predict_response_time(recipient, recommended, urgency)

        # Determine alternatives
        alternatives = ["slack", "teams", "gmail", "outlook"]
        if recommended in alternatives:
            alternatives.remove(recommended)

        # Confidence based on data
        confidence = RecommendationConfidence.MEDIUM if pattern.avg_response_time > 0 else RecommendationConfidence.LOW

        return ChannelRecommendation(
            user_id=recipient,
            recommended_platform=recommended,
            reason=reason,
            confidence=confidence,
            expected_response_time=prediction.predicted_seconds,
            alternatives=alternatives[:3]
        )

    def detect_bottlenecks(
        self,
        threshold_hours: float = 24.0
    ) -> List[BottleneckAlert]:
        """
        Detect communication bottlenecks (threads awaiting response).

        Args:
            threshold_hours: Hours without response to consider a bottleneck

        Returns:
            List of BottleneckAlerts
        """
        alerts = []
        now = datetime.now(timezone.utc)
        threshold_seconds = threshold_hours * 3600

        # Check each thread
        for thread_id, messages in self.thread_activity.items():
            if not messages:
                continue

            # Sort by timestamp
            sorted_msgs = sorted(
                messages,
                key=lambda m: self._parse_timestamp(m.get("timestamp")) or datetime.min
            )

            # Get last message
            last_msg = sorted_msgs[-1]
            last_time = self._parse_timestamp(last_msg.get("timestamp"))

            if not last_time:
                continue

            wait_time = (now - last_time).total_seconds()

            if wait_time >= threshold_seconds:
                # Determine severity
                if wait_time >= 72 * 3600:  # 3 days
                    severity = UrgencyLevel.URGENT
                elif wait_time >= 48 * 3600:  # 2 days
                    severity = UrgencyLevel.HIGH
                else:
                    severity = UrgencyLevel.MEDIUM

                # Find affected users (participants in thread)
                participants = set()
                for msg in messages:
                    sender = msg.get("sender_name") or msg.get("sender")
                    if sender:
                        participants.add(sender)

                # Generate description
                platform = last_msg.get("platform", "unknown")
                sender = last_msg.get("sender_name") or last_msg.get("sender", "Unknown")

                alert = BottleneckAlert(
                    severity=severity,
                    thread_id=thread_id,
                    platform=platform,
                    description=f"Last message from {sender} {wait_time/3600:.1f} hours ago",
                    affected_users=list(participants),
                    wait_time_seconds=wait_time,
                    suggested_action=self._generate_bottleneck_action(severity, platform, sender)
                )

                alerts.append(alert)

        # Sort by severity and wait time
        severity_order = {UrgencyLevel.URGENT: 0, UrgencyLevel.HIGH: 1, UrgencyLevel.MEDIUM: 2}
        alerts.sort(key=lambda a: (severity_order.get(a.severity, 3), -a.wait_time_seconds))

        return alerts

    def get_user_pattern(self, user_id: str) -> Optional[CommunicationPattern]:
        """Get communication pattern for a specific user"""
        return self.user_patterns.get(user_id)

    def get_insights_summary(self) -> Dict[str, Any]:
        """Get summary of all predictive insights"""
        return {
            "users_analyzed": len(self.user_patterns),
            "threads_tracked": len(self.thread_activity),
            "bottlenecks_detected": len(self.detect_bottlenecks()),
            "active_patterns": sum(1 for p in self.user_patterns.values() if p.avg_response_time > 0),
            "avg_response_time_all_users": statistics.mean(
                [p.avg_response_time for p in self.user_patterns.values() if p.avg_response_time > 0]
            ) if self.user_patterns else 0
        }

    def _analyze_user_patterns(
        self,
        user_id: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[CommunicationPattern]:
        """Analyze patterns for a single user"""
        if len(messages) < self.min_data_points:
            return None

        # Extract timestamps
        timestamps = []
        platform_counts = defaultdict(int)
        hours = []

        for msg in messages:
            ts = self._parse_timestamp(msg.get("timestamp"))
            if ts:
                timestamps.append(ts)
                hours.append(ts.hour)

            platform = msg.get("platform", "unknown")
            platform_counts[platform] += 1

        if not timestamps:
            return None

        # Calculate response times
        response_times = self._calculate_response_times(messages)

        if not response_times:
            avg_response = 0
        else:
            avg_response = statistics.mean(response_times)

        # Most active platform
        most_active_platform = max(platform_counts.items(), key=lambda x: x[1])[0] if platform_counts else "unknown"

        # Response probability by hour
        hour_probabilities = self._calculate_hourly_probabilities(hours)

        # Most active hours (top 3)
        hour_counts = defaultdict(int)
        for h in hours:
            hour_counts[h] += 1

        most_active_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        most_active_hours = [h[0] for h in most_active_hours]

        # Preferred message types (based on keywords)
        preferred_types = self._extract_message_types(messages)

        return CommunicationPattern(
            user_id=user_id,
            most_active_hours=most_active_hours,
            most_active_platform=most_active_platform,
            avg_response_time=avg_response,
            response_probability_by_hour=hour_probabilities,
            preferred_message_types=preferred_types
        )

    def _calculate_response_times(self, messages: List[Dict[str, Any]]) -> List[float]:
        """Calculate response times for user's messages"""
        response_times = []

        # Group by thread
        thread_messages = defaultdict(list)
        for msg in messages:
            thread_id = msg.get("thread_id") or msg.get("conversation_id")
            if thread_id:
                thread_messages[thread_id].append(msg)

        # Calculate times for each thread
        for thread_msgs in thread_messages.values():
            if len(thread_msgs) < 2:
                continue

            # Sort by timestamp
            sorted_msgs = sorted(
                thread_msgs,
                key=lambda m: self._parse_timestamp(m.get("timestamp")) or datetime.min
            )

            # Calculate differences
            for i in range(1, len(sorted_msgs)):
                prev_time = self._parse_timestamp(sorted_msgs[i-1].get("timestamp"))
                curr_time = self._parse_timestamp(sorted_msgs[i].get("timestamp"))

                if prev_time and curr_time:
                    diff = (curr_time - prev_time).total_seconds()
                    if 30 <= diff <= 86400:  # Filter reasonable response times
                        response_times.append(diff)

        return response_times

    def _calculate_hourly_probabilities(self, hours: List[int]) -> Dict[int, float]:
        """Calculate probability of response by hour of day"""
        if not hours:
            return {}

        hour_counts = defaultdict(int)
        for h in hours:
            hour_counts[h] += 1

        total = len(hours)
        return {h: count/total for h, count in hour_counts.items()}

    def _extract_message_types(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract preferred message types from content"""
        type_keywords = {
            "urgent": ["urgent", "asap", "deadline", "emergency", "critical"],
            "file_share": ["attached", "document", "file", "attachment"],
            "meeting": ["meeting", "call", "discuss", "sync"],
            "question": ["?", "question", "help", "how to"],
            "task": ["task", "todo", "action item", "follow up"]
        }

        type_counts = defaultdict(int)

        for msg in messages:
            content = msg.get("content", "").lower()

            for msg_type, keywords in type_keywords.items():
                if any(kw in content for kw in keywords):
                    type_counts[msg_type] += 1

        # Return top types
        if type_counts:
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            return [t[0] for t in sorted_types[:3]]

        return ["general"]

    def _generate_bottleneck_action(
        self,
        severity: UrgencyLevel,
        platform: str,
        sender: str
    ) -> str:
        """Generate suggested action for bottleneck"""
        actions = {
            UrgencyLevel.URGENT: f"Escalate to alternative channel and notify {sender}",
            UrgencyLevel.HIGH: f"Send reminder to {sender} via different platform",
            UrgencyLevel.MEDIUM: f"Consider sending follow-up to {sender}"
        }

        return actions.get(severity, "Monitor thread for response")

    def _parse_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """Parse timestamp to datetime"""
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
predictive_insights_engine = PredictiveInsightsEngine()


def get_predictive_insights_engine() -> PredictiveInsightsEngine:
    """Get the singleton predictive insights engine"""
    return predictive_insights_engine
