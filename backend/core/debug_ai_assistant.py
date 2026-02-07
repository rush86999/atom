"""
AI Debug Assistant for Atom Platform

Natural language interface for querying debug data:
- Natural language query processing
- Intent detection and understanding
- Evidence retrieval and synthesis
- Answer generation with confidence scoring
- Context-aware response generation

Example:
    assistant = DebugAIAssistant(db_session, query_api, monitor)

    # Natural language query
    result = await assistant.ask(
        question="Why is agent-123 failing?",
        context={"user_id": "user-123"}
    )
    # Returns: {
    #   "answer": "Agent-123 has a 75% failure probability due to...",
    #   "evidence": [...],
    #   "confidence": 0.82,
    #   "related_insights": [...]
    # }
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugMetric,
    DebugInsightSeverity,
)
from core.debug_query import DebugQuery
from core.debug_monitor import DebugMonitor
from core.debug_insights.consistency import ConsistencyInsightGenerator
from core.debug_insights.performance import PerformanceInsightGenerator
from core.structured_logger import StructuredLogger


class DebugAIAssistant:
    """
    AI-powered debug assistant for natural language queries.

    Processes natural language questions and provides comprehensive
    debugging answers with evidence and confidence scoring.
    """

    def __init__(
        self,
        db_session: Session,
        enable_prediction: bool = True,
        enable_self_healing: bool = False,
    ):
        """
        Initialize AI debug assistant.

        Args:
            db_session: SQLAlchemy database session
            enable_prediction: Enable failure prediction features
            enable_self_healing: Enable self-healing suggestions
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session
        self.enable_prediction = enable_prediction
        self.enable_self_healing = enable_self_healing

        # Initialize dependencies
        self.query_api = DebugQuery(db_session)
        self.monitor = DebugMonitor(db_session)

        # Initialize advanced insight generators
        self.consistency_gen = ConsistencyInsightGenerator(db_session)
        self.performance_gen = PerformanceInsightGenerator(db_session)

        # Intent patterns
        self.intent_patterns = {
            # Component health queries
            r"health|status|how (is|are).*(?:agent|workflow|browser|system)",
            "component_health",

            # Failure queries
            r"why .*(?:fail|failing|error|not working|broken)",
            "failure_analysis",

            # Performance queries
            r"slow|performance|latency|response time|bottleneck",
            "performance_analysis",

            # Consistency queries
            r"consistency|data.*sync|replication|propagation",
            "consistency_check",

            # Error queries
            r"error.*pattern|recurring.*error|frequent.*error",
            "error_patterns",

            # General explanation
            r"what.*happened|explain|debug",
            "general_explanation",
        }

    async def ask(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process natural language question and provide answer.

        Args:
            question: Natural language question
            context: Additional context (user_id, component_id, etc.)

        Returns:
            Answer with evidence and confidence
        """
        try:
            question_lower = question.lower()

            # Detect intent
            intent = self._detect_intent(question)

            # Route to appropriate handler
            if intent == "component_health":
                return await self._handle_component_health_question(question, context)
            elif intent == "failure_analysis":
                return await self._handle_failure_question(question, context)
            elif intent == "performance_analysis":
                return await self._handle_performance_question(question, context)
            elif intent == "consistency_check":
                return await self._handle_consistency_question(question, context)
            elif intent == "error_patterns":
                return await self._handle_error_patterns_question(question, context)
            else:
                return await self._handle_general_question(question, context)

        except Exception as e:
            self.logger.error(
                "Failed to process question",
                question=question,
                error=str(e),
            )
            return {
                "answer": f"I encountered an error processing your question: {str(e)}",
                "confidence": 0.0,
                "evidence": [],
                "related_insights": [],
            }

    async def _detect_intent(self, question: str) -> str:
        """Detect user intent from question."""
        question_lower = question.lower()

        for pattern, intent in self.intent_patterns.items():
            if re.search(pattern, question_lower):
                return intent

        return "general_explanation"

    async def _handle_component_health_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle questions about component health."""
        try:
            # Extract component info from question
            component_match = re.search(
                r"(agent|workflow|browser|system)[-_]?\w+",
                question.lower()
            )

            if component_match:
                component_str = component_match.group(0)
                parts = component_str.split("-")
                component_type = parts[0]
                component_id = "-".join(parts[1:]) if len(parts) > 1 else None
            else:
                # Check context for component info
                component_type = context.get("component_type") if context else None
                component_id = context.get("component_id") if context else None

            if not component_type:
                return {
                    "answer": "Which component would you like to check? (e.g., 'agent-123', 'workflow-456')",
                    "confidence": 0.5,
                    "evidence": [],
                    "related_insights": [],
                    "clarification_needed": "component_id",
                }

            # Get component health
            if component_id:
                health = await self.query_api.get_component_health(
                    component_type=component_type,
                    component_id=component_id,
                    time_range="1h",
                )

                if health.get("error_rate", 0) > 0.5:
                    # Get error explanation
                    recent_errors = (
                        self.db.query(DebugEvent)
                        .filter(
                            and_(
                                DebugEvent.component_type == component_type,
                                DebugEvent.component_id == component_id,
                                DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                                DebugEvent.timestamp >= datetime.utcnow() - timedelta(hours=1),
                            )
                        )
                        .order_by(DebugEvent.timestamp.desc())
                        .limit(5)
                        .all()
                    )

                    error_messages = [e.message for e in recent_errors if e.message]

                    return {
                        "answer": f"{component_type}/{component_id} is experiencing issues. "
                        f"Health score is {health['health_score']}/100 with {health['error_events']} errors "
                        f"({health['error_rate']*100:.1f}% error rate).",
                        "confidence": 0.90,
                        "evidence": {
                            "health_score": health["health_score"],
                            "error_rate": health["error_rate"],
                            "recent_errors": error_messages,
                        },
                        "related_insights": health.get("recent_insights", []),
                        "suggestions": [
                            "Review error logs",
                            "Check component status",
                            "Investigate recent changes",
                        ],
                    }

                # Component is healthy
                return {
                    "answer": f"{component_type}/{component_id} is healthy with a score of {health['health_score']}/100. "
                    f"No errors in the last hour.",
                    "confidence": 0.95,
                    "evidence": health,
                    "related_insights": health.get("recent_insights", []),
                    "suggestions": ["Continue monitoring", "No action needed"],
                }

            # General system health
            system_health = await self.monitor.get_system_health("last_1h")

            return {
                "answer": f"System health score is {system_health['overall_health_score']}/100. "
                f"Status: {system_health['status']}. "
                f"Active operations: {system_health['active_operations']}. "
                f"Total events: {system_health['total_events']}.",
                "confidence": 0.85,
                "evidence": {
                    "system_health_score": system_health["overall_health_score"],
                    "error_rate": system_health["error_rate"],
                    "active_operations": system_health["active_operations"],
                },
                "related_insights": [],
                "suggestions": self._get_system_recommendations(system_health),
            }

        except Exception as e:
            self.logger.error("Failed to handle health question", error=str(e))
            return self._error_response(str(e))

    async def _handle_failure_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle questions about failures."""
        try:
            # Extract component info
            component_match = re.search(
                r"(agent|workflow|browser|system)[-_]?\w+",
                question.lower()
            )

            if not component_match:
                return {
                    "answer": "Which component is failing? Please specify the component ID.",
                    "confidence": 0.5,
                    "evidence": [],
                    "related_insights": [],
                    "clarification_needed": "component_id",
                }

            component_str = component_match.group(0)
            parts = component_str.split("-")
            component_type = parts[0]
            component_id = "-".join(parts[1:]) if len(parts) > 1 else None

            # Get component risk assessment
            if self.enable_prediction:
                # This would use FailurePredictor
                pass

            # Get recent errors
            time_filter = datetime.utcnow() - timedelta(hours=1)

            errors = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .order_by(DebugEvent.timestamp.desc())
                .limit(10)
                .all()
            )

            if not errors:
                return {
                    "answer": f"No recent errors found for {component_type}/{component_id} in the last hour.",
                    "confidence": 0.8,
                    "evidence": {"component_type": component_type, "component_id": component_id},
                    "related_insights": [],
                    "suggestions": ["Check if component is running", "Verify time range"],
                }

            # Analyze error patterns
            error_messages = [e.message for e in errors if e.message]
            common_errors = Counter(error_messages)

            # Get related insights
            related_insights = (
                self.db.query(DebugInsight)
                .filter(
                    and_(
                        DebugInsight.insight_type == "error",
                        DebugInsight.generated_at >= time_filter,
                        DebugInsight.resolved == False,
                    )
                )
                .order_by(DebugInsight.generated_at.desc())
                .limit(5)
                .all()
            )

            return {
                "answer": f"{component_type}/{component_id} has experienced {len(errors)} error(s) in the last hour. "
                f"Most common: {common_errors.most_common(1)[0]} ({common_errors.most_common(1)[1]} occurrences).",
                "confidence": 0.85,
                "evidence": {
                    "component_type": component_type,
                    "component_id": component_id,
                    "error_count": len(errors),
                    "common_errors": dict(common_errors.most_common(3)),
                },
                "related_insights": [
                    {
                        "id": insight.id,
                        "type": insight.insight_type,
                        "severity": insight.severity,
                        "summary": insight.summary,
                    }
                    for insight in related_insights
                ],
                "suggestions": self._generate_failure_suggestions(errors, related_insights),
            }

        except Exception as e:
            self.logger.error("Failed to handle failure question", error=str(e))
            return self._error_response(str(e))

    async def _handle_performance_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle questions about performance."""
        try:
            # Extract component info
            component_match = re.search(
                r"(agent|workflow|browser|system)[-_]?\w+",
                question.lower()
            )

            if not component_match:
                return {
                    "answer": "Which component would you like to analyze?",
                    "confidence": 0.5,
                    "clarification_needed": "component_id",
                }

            component_str = component_match.group(0)
            parts = component_str.split("-")
            component_type = parts[0]
            component_id = "-".join(parts[1:]) if len(parts) > 1 else None

            # Get performance analysis
            insight = await self.performance_gen.analyze_component_latency(
                component_type=component_type,
                component_id=component_id,
                time_range="last_1h",
            )

            if insight:
                if insight.severity == DebugInsightSeverity.WARNING.value:
                    # Performance issue detected
                    return {
                        "answer": insight.summary,
                        "description": insight.description,
                        "confidence": insight.confidence_score,
                        "evidence": insight.evidence,
                        "related_insights": [insight],
                        "suggestions": insight.suggestions,
                    }
                else:
                    # Performance is good
                    return {
                        "answer": insight.summary,
                        "confidence": insight.confidence_score,
                        "evidence": insight.evidence,
                        "related_insights": [insight],
                        "suggestions": ["Continue monitoring", "No action needed"],
                    }
            else:
                # No specific performance data
                return {
                    "answer": f"No performance data available for {component_type}/{component_id} in the last hour.",
                    "confidence": 0.6,
                    "evidence": {"component_type": component_type, "component_id": component_id},
                    "related_insights": [],
                    "suggestions": ["Generate some load to collect performance metrics"],
                }

        except Exception as e:
            self.logger.error("Failed to handle performance question", error=str(e))
            return self._error_response(str(e))

    async def _handle_consistency_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle questions about data consistency."""
        try:
            # Extract operation ID or component info
            operation_match = re.search(r"op(?:eration)?[-_]?\w+", question.lower())
            component_match = re.search(
                r"(agent|workflow|browser|system)[-_]?\w+",
                question.lower()
            )

            if not operation_match and not component_match:
                return {
                    "answer": "Which operation or component would you like to check for consistency?",
                    "confidence": 0.5,
                    "clarification_needed": "operation_or_component",
                }

            if operation_match:
                operation_id = operation_match.group(0).replace("op", "").replace("_", "-")

                # Analyze data flow
                # Get all components involved in this operation
                time_filter = datetime.utcnow() - timedelta(hours=1)

                components = (
                    self.db.query(
                        DebugEvent.component_type,
                        DebugEvent.component_id,
                    )
                    .filter(
                        and_(
                            DebugEvent.correlation_id.like(f"%{operation_id}%"),
                            DebugEvent.timestamp >= time_filter,
                        )
                    )
                    .distinct()
                    .all()
                )

                if not components:
                    return {
                        "answer": f"No activity found for operation {operation_id} in the last hour.",
                        "confidence": 0.7,
                        "evidence": {"operation_id": operation_id},
                        "related_insights": [],
                        "suggestions": ["Verify operation ID", "Check time range"],
                    }

                component_ids = [f"{comp[0]}/{comp[1]}" for comp in components]

                # Analyze consistency
                insight = await self.consistency_gen.analyze_data_flow(
                    operation_id=operation_id,
                    component_ids=[comp[1] for comp in components],
                    component_type=components[0][0] if components else "agent",
                )

                return {
                    "answer": insight.summary if insight else "No consistency data available",
                    "description": insight.description if insight else None,
                    "confidence": insight.confidence_score if insight else 0.5,
                    "evidence": insight.evidence if insight else {},
                    "related_insights": [insight] if insight else [],
                    "suggestions": insight.suggestions if insight else [],
                }

        except Exception as e:
            self.logger.error("Failed to handle consistency question", error=str(e))
            return self._error_response(str(e))

    async def _handle_error_patterns_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle questions about error patterns."""
        try:
            # Get error pattern insights
            time_filter = datetime.utcnow() - timedelta(hours=24)

            insights = (
                self.db.query(DebugInsight)
                .filter(
                    and_(
                        DebugInsight.insight_type == "error",
                        DebugInsight.generated_at >= time_filter,
                    )
                )
                .order_by(DebugInsight.generated_at.desc())
                .limit(10)
                .all()
            )

            if not insights:
                return {
                    "answer": "No significant error patterns detected in the last 24 hours.",
                    "confidence": 0.75,
                    "evidence": {"time_range": "last_24h"},
                    "related_insights": [],
                    "suggestions": ["Review recent errors", "Check time range"],
                }

            # Aggregate insights
            pattern_summaries = []
            for insight in insights:
                pattern_summaries.append({
                    "pattern": insight.title,
                    "occurrences": insight.evidence.get("occurrence_count", 0) if insight.evidence else 0,
                    "severity": insight.severity,
                    "summary": insight.summary,
                })

            return {
                "answer": f"Found {len(insights)} error pattern(s) in the last 24 hours.",
                "confidence": 0.80,
                "evidence": {
                    "patterns": pattern_summaries,
                    "time_range": "last_24h",
                },
                "related_insights": insights,
                "suggestions": [
                    "Review high-severity patterns first",
                    "Consider investigating recurring patterns",
                    "Implement fixes for common errors",
                ],
            }

        except Exception as e:
            self.logger.error("Failed to handle error patterns question", error=str(e))
            return self._error_response(str(e))

    async def _handle_general_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle general debugging questions."""
        try:
            # Check for operation ID in question
            operation_match = re.search(r"(?:op(?:eration)?[-_]?\w+)", question.lower())

            if operation_match:
                operation_id = operation_match.group(0).replace("op", "").replace("_", "-")

                # Get operation progress
                progress = await self.query_api.get_operation_progress(operation_id)

                return {
                    "answer": f"Operation {operation_id} {progress['status']} "
                    f"with {progress['progress']*100:.0f}% progress.",
                    "description": f"Started at {progress.get('started_at')}, "
                    f"{'in_progress' if progress['status'] == 'in_progress' else 'completed'} "
                    f"with {progress.get('total_steps', 0)} total steps.",
                    "confidence": 0.85,
                    "evidence": progress,
                    "suggestions": progress.get("insights", []),
                }

            # General system overview
            system_health = await self.monitor.get_system_health("last_1h")

            return {
                "answer": f"System is {system_health['status']} with a health score of "
                f"{system_health['overall_health_score']}/100. "
                f"{'No critical issues' if system_health['error_rate'] < 0.1 else f'Error rate is {system_health['error_rate']*100:.1f}%'}",
                "confidence": 0.75,
                "evidence": system_health,
                "suggestions": self._get_system_recommendations(system_health),
            }

        except Exception as e:
            self.logger.error("Failed to handle general question", error=str(e))
            return self._error_response(str(e))

    def _generate_failure_suggestions(
        self,
        errors: List[DebugEvent],
        insights: List[DebugInsight],
    ) -> List[str]:
        """Generate suggestions based on errors and insights."""
        suggestions = []

        # Check insights for suggestions
        for insight in insights:
            if insight.suggestions:
                suggestions.extend(insight.suggestions)

        # Add generic suggestions if none specific
        if not suggestions:
            if errors:
                suggestions.append("Review error logs for details")
            suggestions.append("Check component configuration")
            suggestions.append("Verify external dependencies")

        # Deduplicate
        return list(set(suggestions))

    def _get_system_recommendations(
        self,
        health: Dict[str, Any],
    ) -> List[str]:
        """Generate system health recommendations."""
        recommendations = []

        if health["error_rate"] > 0.1:
            recommendations.append("Investigate high error rate")

        if health["overall_health_score"] < 70:
            recommendations.append("System health requires attention")

        if health["active_operations"] > 100:
            recommendations.append("Consider scaling up")

        if not recommendations:
            recommendations.append("System is operating normally")

        return recommendations

    def _error_response(self, error_message: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            "answer": f"I encountered an error: {error_message}",
            "confidence": 0.0,
            "evidence": {"error": error_message},
            "related_insights": [],
            "suggestions": ["Check error logs", "Try rephrasing question"],
        }
