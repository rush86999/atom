"""
Debug Query API for AI Agents

Python API for AI agents to query debug data and retrieve abstracted insights.
Provides high-level methods for common debugging queries.

Example:
    query = DebugQuery()

    # Component health
    health = await query.get_component_health("agent", "agent-123", time_range="1h")

    # Operation progress
    progress = await query.get_operation_progress("op-456")

    # Error explanation
    error = await query.explain_error("err-789")

    # Compare components
    comparison = await query.compare_components([
        {"type": "agent", "id": "agent-123"},
        {"type": "agent", "id": "agent-456"}
    ])

    # Natural language query
    result = await query.ask("Why is workflow-789 failing?")
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugMetric,
    DebugEventType,
    DebugInsightType,
    DebugInsightSeverity,
)
from core.debug_cache import get_debug_cache
from core.structured_logger import StructuredLogger


# Configuration
DEBUG_QUERY_CACHE_ENABLED = os.getenv("DEBUG_QUERY_CACHE_ENABLED", "true").lower() == "true"


class DebugQuery:
    """
    Debug query API for AI agents.

    Provides high-level methods for querying debug data and insights.
    """

    def __init__(self, db_session: Session):
        """
        Initialize debug query API.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session
        self.cache = get_debug_cache() if DEBUG_QUERY_CACHE_ENABLED else None

    # ========================================================================
    # Component Health
    # ========================================================================

    async def get_component_health(
        self,
        component_type: str,
        component_id: str,
        time_range: str = "1h",
    ) -> Dict[str, Any]:
        """
        Get component health status.

        Args:
            component_type: Component type (agent, browser, workflow, system)
            component_id: Component ID
            time_range: Time range for analysis (1h, 24h, 7d)

        Returns:
            Health status with score and insights
        """
        try:
            # Check cache
            cache_key = f"health:{component_type}:{component_id}:{time_range}"
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached:
                    return cached

            # Parse time range
            time_filter = self._parse_time_range(time_range)

            # Query events
            events_query = self.db.query(DebugEvent).filter(
                and_(
                    DebugEvent.component_type == component_type,
                    DebugEvent.component_id == component_id,
                    DebugEvent.timestamp >= time_filter,
                )
            )

            total_events = events_query.count()
            error_events = events_query.filter(
                DebugEvent.level.in_(["ERROR", "CRITICAL"])
            ).count()

            # Calculate health score
            if total_events == 0:
                health_score = 100  # No errors if no events
                status = "unknown"
            else:
                error_rate = error_events / total_events
                health_score = max(0, 100 - (error_rate * 100))

                if health_score >= 90:
                    status = "healthy"
                elif health_score >= 70:
                    status = "degraded"
                else:
                    status = "unhealthy"

            # Get related insights
            insights = (
                self.db.query(DebugInsight)
                .filter(
                    and_(
                        DebugInsight.scope.in_(["component", "distributed"]),
                        DebugInsight.generated_at >= time_filter,
                    )
                )
                .order_by(desc(DebugInsight.generated_at))
                .limit(10)
                .all()
            )

            result = {
                "component_type": component_type,
                "component_id": component_id,
                "status": status,
                "health_score": health_score,
                "total_events": total_events,
                "error_events": error_events,
                "error_rate": error_events / total_events if total_events > 0 else 0,
                "insights": [self._insight_to_dict(i) for i in insights],
                "time_range": time_range,
                "analyzed_at": datetime.utcnow().isoformat(),
            }

            # Cache result
            if self.cache:
                self.cache.set(cache_key, result)

            return result

        except Exception as e:
            self.logger.error(
                "Failed to get component health",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return {
                "component_type": component_type,
                "component_id": component_id,
                "status": "error",
                "health_score": 0,
                "error": str(e),
            }

    # ========================================================================
    # Operation Progress
    # ========================================================================

    async def get_operation_progress(self, operation_id: str) -> Dict[str, Any]:
        """
        Get operation progress tracking.

        Args:
            operation_id: Operation correlation ID

        Returns:
            Operation progress with insights
        """
        try:
            # Query events for operation
            events = (
                self.db.query(DebugEvent)
                .filter(DebugEvent.correlation_id == operation_id)
                .order_by(DebugEvent.timestamp)
                .all()
            )

            if not events:
                return {
                    "operation_id": operation_id,
                    "progress": 0,
                    "status": "not_found",
                    "insights": [],
                }

            # Analyze events to determine progress
            total_steps = sum(1 for e in events if "step" in e.data or "progress" in e.data)
            completed_steps = sum(
                1
                for e in events
                if e.data.get("status") == "completed" or e.data.get("progress") == 1.0
            )

            progress = completed_steps / total_steps if total_steps > 0 else 0

            # Determine status
            error_events = [e for e in events if e.level in ["ERROR", "CRITICAL"]]
            if error_events:
                status = "failed"
            elif progress >= 1.0:
                status = "completed"
            elif progress > 0:
                status = "in_progress"
            else:
                status = "started"

            # Generate insights
            insights_text = []
            if total_steps > 0:
                insights_text.append(f"Operation has {total_steps} steps")
            if progress > 0:
                insights_text.append(f"Progress: {progress * 100:.1f}%")
            if status == "in_progress":
                last_event = events[-1]
                if last_event.message:
                    insights_text.append(f"Last action: {last_event.message}")

            return {
                "operation_id": operation_id,
                "progress": progress,
                "status": status,
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "insights": insights_text,
                "error_count": len(error_events),
                "started_at": events[0].timestamp.isoformat() if events[0].timestamp else None,
                "updated_at": events[-1].timestamp.isoformat() if events[-1].timestamp else None,
            }

        except Exception as e:
            self.logger.error(
                "Failed to get operation progress",
                operation_id=operation_id,
                error=str(e),
            )
            return {
                "operation_id": operation_id,
                "progress": 0,
                "status": "error",
                "error": str(e),
            }

    # ========================================================================
    # Error Explanation
    # ========================================================================

    async def explain_error(self, error_id: str) -> Dict[str, Any]:
        """
        Explain error with root cause and suggestions.

        Args:
            error_id: Error event ID

        Returns:
            Error explanation with root cause and suggestions
        """
        try:
            # Get error event
            error_event = (
                self.db.query(DebugEvent).filter(DebugEvent.id == error_id).first()
            )

            if not error_event:
                return {
                    "error_id": error_id,
                    "found": False,
                    "error": "Error event not found",
                }

            # Find related insights
            insights = (
                self.db.query(DebugInsight)
                .filter(
                    and_(
                        DebugInsight.insight_type == DebugInsightType.ERROR.value,
                        DebugInsight.source_event_id == error_id,
                    )
                )
                .all()
            )

            # Build explanation
            explanation = {
                "error_id": error_id,
                "found": True,
                "message": error_event.message,
                "component": f"{error_event.component_type}/{error_event.component_id}",
                "timestamp": error_event.timestamp.isoformat() if error_event.timestamp else None,
                "level": error_event.level,
                "data": error_event.data,
            }

            if insights:
                # Use insight explanation
                top_insight = insights[0]
                explanation["root_cause"] = top_insight.description
                explanation["suggestions"] = top_insight.suggestions
                explanation["confidence"] = top_insight.confidence_score
            else:
                # Basic explanation
                explanation["root_cause"] = f"Error in {error_event.component_type}"
                explanation["suggestions"] = [
                    "Review error message",
                    "Check component logs",
                    "Verify component configuration",
                ]
                explanation["confidence"] = 0.5

            return explanation

        except Exception as e:
            self.logger.error(
                "Failed to explain error",
                error_id=error_id,
                error=str(e),
            )
            return {
                "error_id": error_id,
                "found": False,
                "error": str(e),
            }

    # ========================================================================
    # Component Comparison
    # ========================================================================

    async def compare_components(
        self,
        components: List[Dict[str, str]],
        time_range: str = "1h",
    ) -> Dict[str, Any]:
        """
        Compare multiple components.

        Args:
            components: List of component dicts with 'type' and 'id' keys
            time_range: Time range for comparison

        Returns:
            Comparison insights
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get health for each component
            component_data = []
            for comp in components:
                health = await self.get_component_health(
                    comp["type"], comp["id"], time_range
                )
                component_data.append(
                    {
                        "component": comp,
                        "health_score": health.get("health_score", 0),
                        "total_events": health.get("total_events", 0),
                        "error_events": health.get("error_events", 0),
                    }
                )

            # Compare metrics
            if len(component_data) < 2:
                return {
                    "components": component_data,
                    "insights": ["Need at least 2 components to compare"],
                }

            insights = []

            # Compare health scores
            health_scores = [c["health_score"] for c in component_data]
            max_health = max(health_scores)
            min_health = min(health_scores)

            if max_health - min_health > 20:
                best_idx = health_scores.index(max_health)
                worst_idx = health_scores.index(min_health)
                insights.append(
                    f"{component_data[best_idx]['component']['id']} is "
                    f"{max_health - min_health:.0f} points healthier than "
                    f"{component_data[worst_idx]['component']['id']}"
                )

            # Compare error rates
            error_rates = [
                c["error_events"] / max(c["total_events"], 1) for c in component_data
            ]
            max_error_rate = max(error_rates)
            min_error_rate = min(error_rates)

            if max_error_rate - min_error_rate > 0.1:
                insights.append(
                    f"Error rate varies from {min_error_rate * 100:.1f}% to "
                    f"{max_error_rate * 100:.1f}% across components"
                )

            return {
                "components": component_data,
                "insights": insights,
                "time_range": time_range,
            }

        except Exception as e:
            self.logger.error(
                "Failed to compare components",
                error=str(e),
            )
            return {
                "components": [],
                "insights": [f"Comparison failed: {str(e)}"],
            }

    # ========================================================================
    # Natural Language Query
    # ========================================================================

    async def ask(self, question: str) -> Dict[str, Any]:
        """
        Natural language query for debug information.

        Args:
            question: Natural language question

        Returns:
            Answer with evidence and confidence
        """
        try:
            question_lower = question.lower()

            # Parse intent
            if "why is" in question_lower and "failing" in question_lower:
                # Extract component ID
                words = question_lower.split()
                for word in words:
                    if word.startswith("workflow-") or word.startswith("agent-"):
                        return await self._explain_component_failure(word)

            elif "health" in question_lower:
                # Component health query
                words = question_lower.split()
                for word in words:
                    if word.startswith("agent-") or word.startswith("browser-"):
                        return await self.get_component_health(
                            "agent" if "agent-" in word else "browser",
                            word,
                            "1h",
                        )

            elif "error" in question_lower:
                # Error explanation query
                # This would require more sophisticated NLP
                return {
                    "answer": "Please provide the error ID",
                    "confidence": 0.5,
                    "evidence": [],
                }

            # Default response
            return {
                "answer": "I couldn't understand the question. Try asking about component health, operation progress, or errors.",
                "confidence": 0.3,
                "evidence": [],
                "related_insights": [],
            }

        except Exception as e:
            self.logger.error(
                "Failed to process natural language query",
                question=question,
                error=str(e),
            )
            return {
                "answer": f"Error processing question: {str(e)}",
                "confidence": 0.0,
                "evidence": [],
            }

    async def _explain_component_failure(self, component_id: str) -> Dict[str, Any]:
        """Explain why a component is failing."""
        try:
            # Find recent errors for component
            error_events = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.component_id == component_id,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                        DebugEvent.timestamp >= datetime.utcnow() - timedelta(hours=1),
                    )
                )
                .order_by(desc(DebugEvent.timestamp))
                .limit(10)
                .all()
            )

            if not error_events:
                return {
                    "answer": f"No recent errors found for {component_id}",
                    "confidence": 0.8,
                    "evidence": [],
                    "related_insights": [],
                }

            # Analyze error patterns
            error_messages = [e.message for e in error_events]
            common_errors = {}
            for msg in error_messages:
                common_errors[msg] = common_errors.get(msg, 0) + 1

            most_common_error = max(common_errors.items(), key=lambda x: x[1])

            return {
                "answer": f"{component_id} is failing due to: {most_common_error[0]}",
                "confidence": 0.85,
                "evidence": [
                    {
                        "error_count": most_common_error[1],
                        "error_message": most_common_error[0],
                        "recent_errors": len(error_events),
                    }
                ],
                "related_insights": [],
                "suggestions": [
                    "Review error logs",
                    "Check component configuration",
                    "Verify dependencies",
                ],
            }

        except Exception as e:
            return {
                "answer": f"Error analyzing component failure: {str(e)}",
                "confidence": 0.0,
                "evidence": [],
            }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _parse_time_range(self, time_range: str) -> datetime:
        """Parse time range string to datetime."""
        now = datetime.utcnow()

        if time_range.endswith("h"):
            hours = int(time_range[:-1])
            return now - timedelta(hours=hours)
        elif time_range.endswith("d"):
            days = int(time_range[:-1])
            return now - timedelta(days=days)
        elif time_range.endswith("m"):
            minutes = int(time_range[:-1])
            return now - timedelta(minutes=minutes)
        else:
            # Default to 1 hour
            return now - timedelta(hours=1)

    def _insight_to_dict(self, insight: DebugInsight) -> Dict[str, Any]:
        """Convert insight to dictionary."""
        return {
            "id": insight.id,
            "type": insight.insight_type,
            "severity": insight.severity,
            "title": insight.title,
            "summary": insight.summary,
            "confidence_score": insight.confidence_score,
            "generated_at": insight.generated_at.isoformat()
            if insight.generated_at
            else None,
        }
