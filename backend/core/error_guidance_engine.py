"""
Error Guidance Engine

Maps errors to actionable resolution suggestions and tracks which
resolutions work for learning and improvement.

Features:
- Error categorization (permission, network, auth, rate_limit, etc.)
- Resolution suggestions with success tracking
- Agent analysis in plain English
- Resolution learning from user feedback
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.models import CanvasAudit, OperationErrorResolution
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


# Feature flags
import os

ERROR_GUIDANCE_ENABLED = os.getenv("ERROR_GUIDANCE_ENABLED", "true").lower() == "true"


class ErrorGuidanceEngine:
    """
    Error resolution mapping and suggestion engine.

    Provides actionable guidance when operations fail with learning
    from past resolutions.
    """

    # Error type → resolution mappings
    ERROR_RESOLUTIONS = {
        "permission_denied": {
            "title": "Permission Required",
            "resolutions": [
                {
                    "title": "Let Agent Request Permission",
                    "description": "I'll ask for the required permissions",
                    "agent_can_fix": True,
                    "steps": [
                        "I'll present a permission request",
                        "You approve the request",
                        "I retry the operation"
                    ]
                },
                {
                    "title": "Grant Permission Manually",
                    "description": "I'll show you how to grant the permission",
                    "agent_can_fix": False,
                    "steps": [
                        "Go to Settings → Permissions",
                        "Find the required permission",
                        "Enable it for this agent"
                    ]
                }
            ]
        },
        "auth_expired": {
            "title": "Authentication Expired",
            "resolutions": [
                {
                    "title": "Let Agent Reconnect",
                    "description": "I'll guide you through re-authentication",
                    "agent_can_fix": True,
                    "steps": [
                        "I'll open the OAuth page",
                        "You click 'Allow'",
                        "We're reconnected"
                    ]
                },
                {
                    "title": "Reconnect Manually",
                    "description": "I'll show you the exact steps to fix this",
                    "agent_can_fix": False,
                    "steps": [
                        "Go to Settings → Integrations",
                        "Click on the integration",
                        "Click 'Reconnect'"
                    ]
                }
            ]
        },
        "network_error": {
            "title": "Network Connection Failed",
            "resolutions": [
                {
                    "title": "Let Agent Retry",
                    "description": "I'll retry the operation with exponential backoff",
                    "agent_can_fix": True,
                    "steps": [
                        "I'll wait a few seconds",
                        "Retry the operation",
                        "Up to 3 attempts"
                    ]
                },
                {
                    "title": "Check Connection",
                    "description": "Verify your internet connection",
                    "agent_can_fix": False,
                    "steps": [
                        "Check your internet connection",
                        "Verify the service is online",
                        "Try again manually"
                    ]
                }
            ]
        },
        "rate_limit": {
            "title": "Rate Limit Exceeded",
            "resolutions": [
                {
                    "title": "Let Agent Wait and Retry",
                    "description": "I'll wait for the rate limit to reset",
                    "agent_can_fix": True,
                    "steps": [
                        "I'll wait for the rate limit window",
                        "Retry the operation automatically",
                        "Usually takes 1-60 seconds"
                    ]
                },
                {
                    "title": "Upgrade Plan",
                    "description": "Higher rate limits with paid plans",
                    "agent_can_fix": False,
                    "steps": [
                        "Go to Settings → Billing",
                        "View available plans",
                        "Upgrade for higher limits"
                    ]
                }
            ]
        },
        "invalid_input": {
            "title": "Invalid Input Data",
            "resolutions": [
                {
                    "title": "Let Agent Fix",
                    "description": "I'll try to correct the input data",
                    "agent_can_fix": True,
                    "steps": [
                        "I'll analyze the error",
                        "Fix the input format",
                        "Retry the operation"
                    ]
                },
                {
                    "title": "Fix Manually",
                    "description": "I'll show you what needs to be fixed",
                    "agent_can_fix": False,
                    "steps": [
                        "Review the error message",
                        "Correct the input data",
                        "Retry the operation"
                    ]
                }
            ]
        },
        "resource_not_found": {
            "title": "Resource Not Found",
            "resolutions": [
                {
                    "title": "Let Agent Search",
                    "description": "I'll try to find the correct resource",
                    "agent_can_fix": True,
                    "steps": [
                        "I'll search for similar resources",
                        "Present options to you",
                        "Use the correct resource"
                    ]
                },
                {
                    "title": "Provide Correct ID",
                    "description": "I'll help you find the right resource ID",
                    "agent_can_fix": False,
                    "steps": [
                        "Check the resource ID",
                        "Verify it exists",
                        "Retry with correct ID"
                    ]
                }
            ]
        }
    }

    def __init__(self, db: Session):
        self.db = db

    def categorize_error(
        self,
        error_code: Optional[str],
        error_message: str
    ) -> str:
        """
        Categorize error by type.

        Args:
            error_code: Optional error code from API
            error_message: Error message text

        Returns:
            Error type category
        """
        error_message_lower = error_message.lower()

        # Check by error code first
        if error_code:
            # For 401, check if it's auth vs permission
            if "401" in error_code and ("expired" in error_message_lower or "token" in error_message_lower):
                return "auth_expired"
            if "401" in error_code or "403" in error_code:
                return "permission_denied"
            if "429" in error_code:
                return "rate_limit"
            if "404" in error_code:
                return "resource_not_found"
            if "400" in error_code:
                return "invalid_input"

        # Check by message content
        if "permission" in error_message_lower or "unauthorized" in error_message_lower:
            return "permission_denied"
        if "expired" in error_message_lower or "token" in error_message_lower:
            return "auth_expired"
        if "rate limit" in error_message_lower or "too many requests" in error_message_lower:
            return "rate_limit"
        if "network" in error_message_lower or "connect" in error_message_lower or "timeout" in error_message_lower:
            return "network_error"
        if "not found" in error_message_lower:
            return "resource_not_found"
        if "invalid" in error_message_lower or "malformed" in error_message_lower:
            return "invalid_input"

        # Default
        return "unknown"

    def get_suggested_resolution(
        self,
        error_type: str
    ) -> int:
        """
        Get suggested resolution index based on historical success.

        Args:
            error_type: Error type category

        Returns:
            Index of suggested resolution (0-based)
        """
        if error_type not in self.ERROR_RESOLUTIONS:
            return 0

        # Query past resolutions for this error type
        resolutions = self.db.query(OperationErrorResolution).filter(
            OperationErrorResolution.error_type == error_type,
            OperationErrorResolution.success == True
        ).all()

        if not resolutions:
            # Default to first option (usually agent can fix)
            return 0

        # Count success rates for each resolution
        resolution_counts = {}
        for r in resolutions:
            resolution_counts[r.resolution_attempted] = \
                resolution_counts.get(r.resolution_attempted, 0) + 1

        # Return most successful resolution
        if resolution_counts:
            return max(resolution_counts, key=resolution_counts.get)

        return 0

    async def present_error(
        self,
        user_id: str,
        operation_id: str,
        error: Dict[str, Any],
        agent_id: Optional[str] = None
    ):
        """
        Present error with resolutions to user.

        Args:
            user_id: User ID
            operation_id: Operation ID that failed
            error: Error dict with type, code, message
            agent_id: Optional agent ID
        """
        if not ERROR_GUIDANCE_ENABLED:
            return

        try:
            # Categorize error
            error_type = self.categorize_error(
                error.get("code"),
                error.get("message", "")
            )

            # Get resolution template
            template = self.ERROR_RESOLUTIONS.get(
                error_type,
                {
                    "title": "Operation Failed",
                    "resolutions": [
                        {
                            "title": "Let Agent Try to Fix",
                            "description": "I'll attempt to resolve this issue",
                            "agent_can_fix": True,
                            "steps": ["Analyze the error", "Attempt fix", "Retry operation"]
                        },
                        {
                            "title": "Fix Manually",
                            "description": "I'll provide guidance for manual resolution",
                            "agent_can_fix": False,
                            "steps": ["Review the error", "Follow the steps", "Retry"]
                        }
                    ]
                }
            )

            # Get suggested resolution
            suggested_index = self.get_suggested_resolution(error_type)

            # Create agent analysis
            agent_analysis = {
                "what_happened": self._explain_what_happened(error_type, error),
                "why_it_happened": self._explain_why(error_type, error),
                "impact": self._explain_impact(error_type)
            }

            # Broadcast error with guidance
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "operation:error",
                    "data": {
                        "operation_id": operation_id,
                        "error": {
                            "type": error_type,
                            "code": error.get("code"),
                            "message": error.get("message"),
                            "technical_details": error.get("technical_details", "")
                        },
                        "agent_analysis": agent_analysis,
                        "resolutions": template["resolutions"],
                        "suggested_resolution": suggested_index
                    }
                }
            )

            # Create audit
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                error_type=error_type,
                action="present_error"
            )

            logger.info(f"Presented error {error_type} for operation {operation_id}")

        except Exception as e:
            logger.error(f"Failed to present error: {e}")

    async def track_resolution(
        self,
        error_type: str,
        error_code: Optional[str],
        resolution_attempted: str,
        success: bool,
        user_feedback: Optional[str] = None,
        agent_suggested: bool = True
    ):
        """
        Track resolution outcome for learning.

        Args:
            error_type: Error type category
            error_code: Optional error code
            resolution_attempted: Which resolution was used
            success: Whether it worked
            user_feedback: Optional user feedback
            agent_suggested: Whether agent suggested this resolution
        """
        if not ERROR_GUIDANCE_ENABLED:
            return

        try:
            resolution = OperationErrorResolution(
                id=str(uuid.uuid4()),
                error_type=error_type,
                error_code=error_code,
                resolution_attempted=resolution_attempted,
                success=success,
                user_feedback=user_feedback,
                agent_suggested=agent_suggested
            )

            self.db.add(resolution)
            self.db.commit()

            logger.info(
                f"Tracked resolution '{resolution_attempted}' for "
                f"error {error_type}: {'SUCCESS' if success else 'FAILED'}"
            )

        except Exception as e:
            logger.error(f"Failed to track resolution: {e}")

    def get_historical_resolutions(
        self,
        error_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get historical resolutions for an error type.

        Args:
            error_type: Error type category
            limit: Maximum results to return

        Returns:
            List of historical resolution attempts with outcomes
        """
        try:
            resolutions = self.db.query(OperationErrorResolution).filter(
                OperationErrorResolution.error_type == error_type
            ).order_by(
                OperationErrorResolution.timestamp.desc()
            ).limit(limit).all()

            return [
                {
                    "resolution": r.resolution_attempted,
                    "success": r.success,
                    "agent_suggested": r.agent_suggested,
                    "user_feedback": r.user_feedback,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in resolutions
            ]
        except Exception as e:
            logger.error(f"Failed to get historical resolutions: {e}")
            return []

    def get_resolution_success_rate(
        self,
        error_type: str,
        resolution_name: str
    ) -> Dict[str, Any]:
        """
        Get success rate statistics for a specific resolution.

        Args:
            error_type: Error type category
            resolution_name: Resolution to analyze

        Returns:
            Success rate statistics
        """
        try:
            resolutions = self.db.query(OperationErrorResolution).filter(
                OperationErrorResolution.error_type == error_type,
                OperationErrorResolution.resolution_attempted == resolution_name
            ).all()

            if not resolutions:
                return {
                    "resolution": resolution_name,
                    "success_rate": 0.0,
                    "total_attempts": 0,
                    "successful_attempts": 0,
                    "failed_attempts": 0,
                }

            successful = sum(1 for r in resolutions if r.success)
            failed = len(resolutions) - successful
            success_rate = successful / len(resolutions) if resolutions else 0

            return {
                "resolution": resolution_name,
                "success_rate": round(success_rate * 100, 2),
                "total_attempts": len(resolutions),
                "successful_attempts": successful,
                "failed_attempts": failed,
            }
        except Exception as e:
            logger.error(f"Failed to get resolution success rate: {e}")
            return {
                "resolution": resolution_name,
                "success_rate": 0.0,
                "error": str(e),
            }

    def get_resolution_statistics(
        self,
        error_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive resolution statistics.

        Args:
            error_type: Optional error type to filter by

        Returns:
            Resolution statistics by type and resolution
        """
        try:
            query = self.db.query(OperationErrorResolution)
            if error_type:
                query = query.filter(OperationErrorResolution.error_type == error_type)

            resolutions = query.all()

            if not resolutions:
                return {
                    "total_resolutions": 0,
                    "by_error_type": {},
                    "overall_success_rate": 0.0,
                }

            # Group by error type and resolution
            stats = {}
            for r in resolutions:
                key = f"{r.error_type}:{r.resolution_attempted}"
                if key not in stats:
                    stats[key] = {
                        "error_type": r.error_type,
                        "resolution": r.resolution_attempted,
                        "total": 0,
                        "successful": 0,
                        "failed": 0,
                    }

                stats[key]["total"] += 1
                if r.success:
                    stats[key]["successful"] += 1
                else:
                    stats[key]["failed"] += 1

            # Calculate success rates
            for key in stats:
                stats[key]["success_rate"] = round(
                    (stats[key]["successful"] / stats[key]["total"] * 100)
                    if stats[key]["total"] > 0 else 0,
                    2
                )

            # Overall success rate
            overall_successful = sum(1 for r in resolutions if r.success)
            overall_success_rate = overall_successful / len(resolutions) if resolutions else 0

            # Group by error type
            by_error_type = {}
            for r in resolutions:
                if r.error_type not in by_error_type:
                    by_error_type[r.error_type] = {
                        "total": 0,
                        "successful": 0,
                        "resolutions": {},
                    }
                by_error_type[r.error_type]["total"] += 1
                if r.success:
                    by_error_type[r.error_type]["successful"] += 1

            return {
                "total_resolutions": len(resolutions),
                "by_error_type": by_error_type,
                "overall_success_rate": round(overall_success_rate * 100, 2),
                "detailed_stats": list(stats.values()),
            }
        except Exception as e:
            logger.error(f"Failed to get resolution statistics: {e}")
            return {
                "error": str(e),
                "total_resolutions": 0,
            }

    def suggest_fixes_from_history(
        self,
        error_type: str,
        error_message: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Suggest fixes based on historical successful resolutions.

        Args:
            error_type: Error type category
            error_message: Error message for context
            limit: Maximum suggestions to return

        Returns:
            List of suggested fixes with success rates
        """
        try:
            # Get successful resolutions for this error type
            successful_resolutions = self.db.query(OperationErrorResolution).filter(
                OperationErrorResolution.error_type == error_type,
                OperationErrorResolution.success == True
            ).all()

            if not successful_resolutions:
                # Return default resolutions from template
                if error_type in self.ERROR_RESOLUTIONS:
                    return [
                        {
                            "resolution": r["title"],
                            "description": r["description"],
                            "agent_can_fix": r["agent_can_fix"],
                            "success_rate": None,
                            "source": "template",
                        }
                        for r in self.ERROR_RESOLUTIONS[error_type]["resolutions"][:limit]
                    ]
                return []

            # Count success by resolution
            resolution_counts = {}
            for r in successful_resolutions:
                resolution_counts[r.resolution_attempted] = \
                    resolution_counts.get(r.resolution_attempted, 0) + 1

            # Get total attempts for each resolution to calculate success rate
            all_resolutions = self.db.query(OperationErrorResolution).filter(
                OperationErrorResolution.error_type == error_type
            ).all()

            resolution_totals = {}
            for r in all_resolutions:
                resolution_totals[r.resolution_attempted] = \
                    resolution_totals.get(r.resolution_attempted, 0) + 1

            # Calculate success rates and sort
            suggestions = []
            for resolution, success_count in resolution_counts.items():
                total_count = resolution_totals.get(resolution, 0)
                success_rate = success_count / total_count if total_count > 0 else 0

                # Get description from template if available
                description = "Historically successful resolution"
                agent_can_fix = True

                if error_type in self.ERROR_RESOLUTIONS:
                    for r in self.ERROR_RESOLUTIONS[error_type]["resolutions"]:
                        if r["title"] == resolution:
                            description = r["description"]
                            agent_can_fix = r["agent_can_fix"]
                            break

                suggestions.append({
                    "resolution": resolution,
                    "description": description,
                    "agent_can_fix": agent_can_fix,
                    "success_rate": round(success_rate * 100, 2),
                    "successful_attempts": success_count,
                    "total_attempts": total_count,
                    "source": "historical",
                })

            # Sort by success rate and count
            suggestions.sort(
                key=lambda x: (x["success_rate"], x["successful_attempts"]),
                reverse=True
            )

            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Failed to suggest fixes from history: {e}")
            return []

    async def get_error_fix_suggestions(
        self,
        error_code: Optional[str],
        error_message: str,
        include_historical: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive error fix suggestions from templates and history.

        Args:
            error_code: Optional error code
            error_message: Error message
            include_historical: Whether to include historical data

        Returns:
            Comprehensive fix suggestions
        """
        try:
            # Categorize error
            error_type = self.categorize_error(error_code, error_message)

            # Get template resolutions
            template = self.ERROR_RESOLUTIONS.get(
                error_type,
                {
                    "title": "Operation Failed",
                    "resolutions": [
                        {
                            "title": "Let Agent Try to Fix",
                            "description": "I'll attempt to resolve this issue",
                            "agent_can_fix": True,
                            "steps": ["Analyze the error", "Attempt fix", "Retry operation"]
                        }
                    ]
                }
            )

            # Get historical suggestions if enabled
            historical_suggestions = []
            if include_historical:
                historical_suggestions = self.suggest_fixes_from_history(
                    error_type, error_message
                )

            # Get resolution statistics
            stats = self.get_resolution_statistics(error_type)

            return {
                "error_type": error_type,
                "error_message": error_message,
                "template_resolutions": template["resolutions"],
                "historical_suggestions": historical_suggestions,
                "statistics": stats,
                "recommended_resolution": self.get_suggested_resolution(error_type),
            }
        except Exception as e:
            logger.error(f"Failed to get error fix suggestions: {e}")
            return {
                "error": str(e),
                "error_type": "unknown",
            }

    def _explain_what_happened(self, error_type: str, error: Dict[str, Any]) -> str:
        """Generate plain English explanation of what happened."""
        explanations = {
            "permission_denied": "The operation failed because the agent lacks required permissions",
            "auth_expired": "Your connection to the service has expired",
            "network_error": "Failed to connect to the service due to network issues",
            "rate_limit": "The service is limiting how many requests we can make",
            "invalid_input": "The data provided doesn't match what the service expects",
            "resource_not_found": "The requested resource doesn't exist or was deleted",
            "unknown": "An unexpected error occurred"
        }
        return explanations.get(error_type, explanations["unknown"])

    def _explain_why(self, error_type: str, error: Dict[str, Any]) -> str:
        """Explain why the error occurred."""
        explanations = {
            "permission_denied": "Permissions are required for security and to prevent unauthorized access",
            "auth_expired": "Authentication tokens expire periodically for security",
            "network_error": "Network issues can be caused by connection problems or service outages",
            "rate_limit": "Services limit requests to prevent abuse and ensure fair usage",
            "invalid_input": "Services require specific data formats and validation",
            "resource_not_found": "The resource may have been deleted, moved, or never existed",
            "unknown": "The exact cause is unclear"
        }
        return explanations.get(error_type, explanations["unknown"])

    def _explain_impact(self, error_type: str) -> str:
        """Explain the impact of the error."""
        impacts = {
            "permission_denied": "The operation cannot proceed until the required permission is granted",
            "auth_expired": "We need to reconnect before the operation can continue",
            "network_error": "The operation will fail until connectivity is restored",
            "rate_limit": "We need to wait before trying again",
            "invalid_input": "The input needs to be corrected before retrying",
            "resource_not_found": "We need to verify the correct resource identifier",
            "unknown": "The operation cannot be completed until the issue is resolved"
        }
        return impacts.get(error_type, impacts["unknown"])

    async def _create_audit(
        self,
        agent_id: Optional[str],
        user_id: str,
        error_type: str,
        action: str
    ):
        """Create canvas audit entry."""
        try:
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                agent_execution_id=None,
                user_id=user_id,
                canvas_id=None,
                session_id=None,
                component_type="operation_error_guide",
                component_name="error_guidance",
                action=action,
                audit_metadata={"error_type": error_type},
                governance_check_passed=True
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to create audit: {e}")


# Singleton instance helper
def get_error_guidance_engine(db: Session) -> ErrorGuidanceEngine:
    """Get or create error guidance engine instance."""
    return ErrorGuidanceEngine(db)
