"""
Feedback Export Service

Provides functionality to export feedback data in various formats (CSV, JSON).
Supports filtering by agent, date range, feedback type, and status.

Usage:
    from core.feedback_export_service import FeedbackExportService

    service = FeedbackExportService(db)

    # Export to CSV
    csv_data = service.export_to_csv(
        agent_id="agent-1",
        days=30,
        feedback_type="correction"
    )

    # Export to JSON
    json_data = service.export_to_json(
        agent_id="agent-1",
        days=30
    )
"""

import csv
from datetime import datetime, timedelta
from io import StringIO
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import AgentFeedback, AgentRegistry

logger = logging.getLogger(__name__)


class FeedbackExportService:
    """
    Service for exporting feedback data.

    Supports multiple export formats and filtering options.
    """

    def __init__(self, db: Session):
        """
        Initialize export service.

        Args:
            db: Database session
        """
        self.db = db

    def export_to_json(
        self,
        agent_id: Optional[str] = None,
        days: int = 30,
        feedback_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> str:
        """
        Export feedback data to JSON format.

        Args:
            agent_id: Optional filter by agent ID
            days: Number of days to look back
            feedback_type: Optional filter by feedback type
            status: Optional filter by status
            limit: Maximum number of records to export

        Returns:
            JSON string with feedback data
        """
        feedback_data = self._get_feedback_data(
            agent_id=agent_id,
            days=days,
            feedback_type=feedback_type,
            status=status,
            limit=limit
        )

        # Convert to export format
        export_data = {
            "export_date": datetime.now().isoformat(),
            "filters": {
                "agent_id": agent_id,
                "days": days,
                "feedback_type": feedback_type,
                "status": status
            },
            "total_records": len(feedback_data),
            "feedback": feedback_data
        }

        return json.dumps(export_data, indent=2, default=str)

    def export_to_csv(
        self,
        agent_id: Optional[str] = None,
        days: int = 30,
        feedback_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> str:
        """
        Export feedback data to CSV format.

        Args:
            agent_id: Optional filter by agent ID
            days: Number of days to look back
            feedback_type: Optional filter by feedback type
            status: Optional filter by status
            limit: Maximum number of records to export

        Returns:
            CSV string with feedback data
        """
        feedback_data = self._get_feedback_data(
            agent_id=agent_id,
            days=days,
            feedback_type=feedback_type,
            status=status,
            limit=limit
        )

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        # Header
        header = [
            "feedback_id",
            "agent_id",
            "agent_name",
            "agent_execution_id",
            "user_id",
            "feedback_type",
            "thumbs_up_down",
            "rating",
            "original_output",
            "user_correction",
            "status",
            "created_at",
            "adjudicated_at"
        ]
        writer.writerow(header)

        # Data rows
        for feedback in feedback_data:
            row = [
                feedback["id"],
                feedback["agent_id"],
                feedback.get("agent_name", ""),
                feedback.get("agent_execution_id", ""),
                feedback["user_id"],
                feedback.get("feedback_type", ""),
                feedback.get("thumbs_up_down", ""),
                feedback.get("rating", ""),
                feedback["original_output"][:200],  # Truncate long text
                feedback["user_correction"][:200],
                feedback["status"],
                feedback["created_at"],
                feedback.get("adjudicated_at", "")
            ]
            writer.writerow(row)

        return output.getvalue()

    def export_summary_to_json(
        self,
        agent_id: Optional[str] = None,
        days: int = 30
    ) -> str:
        """
        Export feedback summary statistics to JSON.

        Provides aggregated statistics rather than individual records.

        Args:
            agent_id: Optional filter by agent ID
            days: Number of days to analyze

        Returns:
            JSON string with summary statistics
        """
        from core.feedback_analytics import FeedbackAnalytics

        analytics = FeedbackAnalytics(self.db)

        if agent_id:
            # Per-agent summary
            summary = analytics.get_agent_feedback_summary(
                agent_id=agent_id,
                days=days
            )

            # Get agent name
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            export_data = {
                "export_date": datetime.now().isoformat(),
                "agent_id": agent_id,
                "agent_name": agent.name if agent else "",
                "period_days": days,
                "summary": summary
            }
        else:
            # Overall summary
            summary = analytics.get_feedback_statistics(days=days)

            export_data = {
                "export_date": datetime.now().isoformat(),
                "period_days": days,
                "summary": summary
            }

        return json.dumps(export_data, indent=2, default=str)

    def _get_feedback_data(
        self,
        agent_id: Optional[str] = None,
        days: int = 30,
        feedback_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Retrieve feedback data with optional filters.

        Args:
            agent_id: Optional filter by agent ID
            days: Number of days to look back
            feedback_type: Optional filter by feedback type
            status: Optional filter by status
            limit: Maximum number of records

        Returns:
            List of feedback dictionaries
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = self.db.query(AgentFeedback).filter(
            AgentFeedback.created_at >= cutoff_date
        )

        # Apply filters
        if agent_id:
            query = query.filter(AgentFeedback.agent_id == agent_id)

        if feedback_type:
            query = query.filter(AgentFeedback.feedback_type == feedback_type)

        if status:
            query = query.filter(AgentFeedback.status == status)

        # Get results
        feedback_items = query.order_by(
            AgentFeedback.created_at.desc()
        ).limit(limit).all()

        # Convert to dictionaries with agent names
        data = []
        for feedback in feedback_items:
            item = {
                "id": feedback.id,
                "agent_id": feedback.agent_id,
                "user_id": feedback.user_id,
                "input_context": feedback.input_context,
                "original_output": feedback.original_output,
                "user_correction": feedback.user_correction,
                "feedback_type": feedback.feedback_type,
                "thumbs_up_down": feedback.thumbs_up_down,
                "rating": feedback.rating,
                "status": feedback.status,
                "ai_reasoning": feedback.ai_reasoning,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
                "adjudicated_at": feedback.adjudicated_at.isoformat() if feedback.adjudicated_at else None,
                "agent_execution_id": feedback.agent_execution_id
            }

            # Add agent name
            if feedback.agent:
                item["agent_name"] = feedback.agent.name

            data.append(item)

        return data

    def get_export_filters(
        self,
        db: Session
    ) -> Dict[str, Any]:
        """
        Get available filter values for export UI.

        Returns unique values for filters like agent IDs,
        feedback types, and statuses.

        Args:
            db: Database session

        Returns:
            Dictionary with available filter values
        """
        # Get unique agent IDs with feedback
        agent_ids = db.query(AgentFeedback.agent_id).distinct().all()
        agents = []
        for (agent_id,) in agent_ids:
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()
            if agent:
                agents.append({
                    "id": agent.id,
                    "name": agent.name,
                    "category": agent.category
                })

        # Get unique feedback types
        feedback_types = db.query(AgentFeedback.feedback_type).filter(
            AgentFeedback.feedback_type.isnot(None)
        ).distinct().all()

        types_list = [ft[0] for ft in feedback_types]

        # Get unique statuses
        statuses = db.query(AgentFeedback.status).distinct().all()
        status_list = [s[0] for s in statuses]

        return {
            "agents": agents,
            "feedback_types": types_list,
            "statuses": status_list
        }
