"""
Review Analytics Service

Tracks review accuracy, false positive/negative rates, and generates feedback for prompt improvement.
Provides analytics dashboard for monitoring review workflow quality.

Phase 323-04: Human-in-the-Loop Review System
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.models import DiscoveredEntity

logger = logging.getLogger(__name__)


class ReviewAnalyticsService:
    """
    Analytics and feedback service for entity review workflow.

    Features:
    - Track review accuracy (approved vs. rejected)
    - Calculate false positive/negative rates
    - Generate feedback for prompt improvement
    - Track review time per entity
    - Export analytics dashboard

    Metrics:
    - Approval rate: approved / (approved + rejected)
    - False positive rate: rejected / total_flagged
    - Review throughput: entities reviewed per hour
    - Type accuracy: correct_type / total_reviewed
    """

    def __init__(self, db: Session):
        """
        Initialize Review Analytics Service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_review_stats(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive review statistics.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back (default: 30)

        Returns:
            Statistics dict
        """
        # Calculate date threshold
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Base query
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.created_at >= threshold_date
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        # Count by status
        stats = {
            "total_reviewed": query.filter(
                DiscoveredEntity.status.in_(["linked", "rejected"])
            ).count(),
            "approved": query.filter(DiscoveredEntity.status == "linked").count(),
            "rejected": query.filter(DiscoveredEntity.status == "rejected").count(),
            "pending": query.filter(DiscoveredEntity.status == "pending").count(),
            "needs_review": query.filter(DiscoveredEntity.status == "needs_review").count(),
        }

        # Calculate approval rate
        total_decisions = stats["approved"] + stats["rejected"]
        if total_decisions > 0:
            stats["approval_rate"] = stats["approved"] / total_decisions
            stats["rejection_rate"] = stats["rejected"] / total_decisions
        else:
            stats["approval_rate"] = 0.0
            stats["rejection_rate"] = 0.0

        # Average confidence score
        avg_confidence = query.filter(
            DiscoveredEntity.status.in_(["linked", "rejected"])
        ).with_entities(
            func.avg(DiscoveredEntity.confidence_score)
        ).scalar()

        stats["avg_confidence_score"] = float(avg_confidence) if avg_confidence else 0.0

        # Review throughput (entities reviewed per day)
        stats["review_throughput_per_day"] = stats["total_reviewed"] / days if days > 0 else 0

        # Unique entity types
        unique_types = query.with_entities(
            DiscoveredEntity._discovered_type
        ).distinct().count()

        stats["unique_types"] = unique_types

        # Time period
        stats["period_days"] = days
        stats["period_start"] = threshold_date.isoformat()
        stats["period_end"] = datetime.now(timezone.utc).isoformat()

        return stats

    async def get_rejection_reasons(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, int]:
        """
        Get breakdown of rejection reasons.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back

        Returns:
            Dict mapping reason to count
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query rejected entities
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "rejected",
            DiscoveredEntity.created_at >= threshold_date
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        rejected_entities = query.all()

        # Count by rejection reason
        reason_counts = {}
        for entity in rejected_entities:
            reason = entity.extraction_metadata.get("rejection_reason", "unknown") if entity.extraction_metadata else "unknown"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        return reason_counts

    async def get_type_accuracy_stats(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get accuracy statistics by entity type.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back

        Returns:
            List of type accuracy stats
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query entities grouped by type
        query = self.db.query(
            DiscoveredEntity._discovered_type,
            func.count(DiscoveredEntity.id).label('total'),
            func.sum(func.case(
                (DiscoveredEntity.status == "linked", 1),
                else_=0
            )).label('approved'),
            func.sum(func.case(
                (DiscoveredEntity.status == "rejected", 1),
                else_=0
            )).label('rejected'),
            func.avg(DiscoveredEntity.confidence_score).label('avg_confidence')
        ).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.created_at >= threshold_date,
            DiscoveredEntity.status.in_(["linked", "rejected"])
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        query = query.group_by(DiscoveredEntity._discovered_type)

        results = query.all()

        # Build stats list
        type_stats = []
        for row in results:
            total = row.total or 0
            approved = row.approved or 0
            rejected = row.rejected or 0

            type_stats.append({
                "discovered_type": row._discovered_type,
                "total_reviewed": total,
                "approved": approved,
                "rejected": rejected,
                "approval_rate": approved / total if total > 0 else 0.0,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0.0
            })

        # Sort by total reviewed (descending)
        type_stats.sort(key=lambda x: x["total_reviewed"], reverse=True)

        return type_stats

    async def get_review_time_stats(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, float]:
        """
        Get review time statistics.

        Measures time from entity creation to review completion.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back

        Returns:
            Time statistics dict
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query reviewed entities
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status.in_(["linked", "rejected"]),
            DiscoveredEntity.created_at >= threshold_date
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        entities = query.all()

        if not entities:
            return {
                "avg_review_time_hours": 0.0,
                "min_review_time_hours": 0.0,
                "max_review_time_hours": 0.0,
                "median_review_time_hours": 0.0
            }

        # Calculate review times
        review_times = []
        for entity in entities:
            if entity.extraction_metadata and "reviewed_at" in entity.extraction_metadata:
                created_at = entity.created_at
                reviewed_at = datetime.fromisoformat(entity.extraction_metadata["reviewed_at"])
                review_time_hours = (reviewed_at - created_at).total_seconds() / 3600
                review_times.append(review_time_hours)

        if not review_times:
            return {
                "avg_review_time_hours": 0.0,
                "min_review_time_hours": 0.0,
                "max_review_time_hours": 0.0,
                "median_review_time_hours": 0.0
            }

        # Calculate statistics
        review_times.sort()
        n = len(review_times)

        return {
            "avg_review_time_hours": sum(review_times) / n,
            "min_review_time_hours": min(review_times),
            "max_review_time_hours": max(review_times),
            "median_review_time_hours": review_times[n // 2]
        }

    async def get_false_positive_rate(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate false positive rate.

        False Positive: Entity flagged for review but should have been auto-approved.

        Proxy Metric: Rejected entities that had high confidence (>0.8)

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back

        Returns:
            False positive rate stats
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query rejected entities with high confidence
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "rejected",
            DiscoveredEntity.confidence_score > 0.8,
            DiscoveredEntity.created_at >= threshold_date
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        high_confidence_rejections = query.count()

        # Total rejected
        total_rejected = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "rejected",
            DiscoveredEntity.created_at >= threshold_date
        )

        if workspace_id:
            total_rejected = total_rejected.filter(DiscoveredEntity.workspace_id == workspace_id)

        total_rejected = total_rejected.count()

        # Calculate false positive rate
        if total_rejected > 0:
            false_positive_rate = high_confidence_rejections / total_rejected
        else:
            false_positive_rate = 0.0

        return {
            "high_confidence_rejections": high_confidence_rejections,
            "total_rejections": total_rejected,
            "false_positive_rate": false_positive_rate,
            "interpretation": "Lower is better - high confidence entities should rarely be rejected"
        }

    async def generate_prompt_feedback(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Generate feedback for prompt improvement.

        Analyzes rejection reasons and patterns to suggest prompt improvements.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back

        Returns:
            List of feedback suggestions
        """
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Query rejected entities
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "rejected",
            DiscoveredEntity.created_at >= threshold_date
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        rejected_entities = query.all()

        # Analyze patterns
        feedback = []

        # Pattern 1: High rejection rate for specific type
        type_rejections = {}
        for entity in rejected_entities:
            entity_type = entity._discovered_type
            type_rejections[entity_type] = type_rejections.get(entity_type, 0) + 1

        for entity_type, count in type_rejections.items():
            if count >= 5:  # Threshold for actionable feedback
                feedback.append({
                    "type": "high_rejection_rate",
                    "entity_type": entity_type,
                    "rejection_count": count,
                    "suggestion": f"Review extraction prompt for '{entity_type}' entities. High rejection rate indicates unclear extraction instructions."
                })

        # Pattern 2: Specific rejection reason
        reason_counts = await self.get_rejection_reasons(tenant_id, workspace_id, days)

        for reason, count in reason_counts.items():
            if count >= 5 and reason != "unknown":
                feedback.append({
                    "type": "common_rejection_reason",
                    "reason": reason,
                    "count": count,
                    "suggestion": f"Add validation rules to prevent '{reason}' errors during extraction."
                })

        # Pattern 3: Low confidence entities
        low_confidence_count = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "rejected",
            DiscoveredEntity.confidence_score < 0.5,
            DiscoveredEntity.created_at >= threshold_date
        ).count()

        if low_confidence_count >= 10:
            feedback.append({
                "type": "low_confidence",
                "count": low_confidence_count,
                "suggestion": "Many entities have low confidence. Consider improving few-shot examples in extraction prompt."
            })

        return feedback

    async def export_analytics_dashboard(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Export complete analytics dashboard.

        Combines all analytics into single report.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            days: Number of days to look back

        Returns:
            Complete dashboard data
        """
        # Gather all analytics
        review_stats = await self.get_review_stats(tenant_id, workspace_id, days)
        rejection_reasons = await self.get_rejection_reasons(tenant_id, workspace_id, days)
        type_accuracy = await self.get_type_accuracy_stats(tenant_id, workspace_id, days)
        review_time = await self.get_review_time_stats(tenant_id, workspace_id, days)
        false_positive = await self.get_false_positive_rate(tenant_id, workspace_id, days)
        prompt_feedback = await self.generate_prompt_feedback(tenant_id, workspace_id, days)

        return {
            "summary": review_stats,
            "rejection_breakdown": rejection_reasons,
            "type_accuracy": type_accuracy,
            "review_time_stats": review_time,
            "false_positive_analysis": false_positive,
            "prompt_improvement_suggestions": prompt_feedback,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days
        }
