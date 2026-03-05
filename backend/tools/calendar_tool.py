"""
Calendar Tool - Google Calendar Integration

Provides Google Calendar operations with governance integration.

Supports:
- Checking schedule conflicts
- Getting upcoming events
- Creating and updating calendar events
- Deleting events

Governance:
- Read actions (get_events, check_conflicts): INTERN+ maturity
- Write actions (create_event, update_event, delete_event): SUPERVISED+ maturity
- STUDENT agents blocked from all calendar operations
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from core.database import get_db_session
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry
from integrations.google_calendar_service import google_calendar_service
from core.structured_logger import get_logger

logger = get_logger(__name__)

# Initialize governance cache
_governance_cache = GovernanceCache()


class CalendarTool:
    """
    Calendar tool for AI agents.

    Provides access to Google Calendar for scheduling and event management:
    - Get upcoming events
    - Check for scheduling conflicts
    - Create new events and meetings
    - Update or reschedule existing events
    - Cancel/delete events

    **Governance**:
    - Read operations (get_events, check_conflicts): INTERN+ maturity
    - Write operations (create_event, update_event, delete_event): SUPERVISED+ maturity
    - STUDENT agents blocked from all operations

    Examples:
    - "What is my schedule for today?"
    - "Check if I am free tomorrow at 2 PM"
    - "Schedule a meeting with the design team on Friday at 10 AM"
    - "Reschedule my 1 PM meeting to 3 PM"
    """

    def __init__(self):
        """Initialize Calendar tool."""
        # Governance cache for permission checks
        self.governance_cache = GovernanceCache()
        
        # Verify the service is authenticating
        try:
            # We don't block initialization if auth fails, as token might be added later
            authenticated = google_calendar_service.authenticate()
            logger.info("CalendarTool initialized", tool_available=True, authenticated=authenticated)
        except Exception as e:
            logger.warning(f"CalendarTool initialized but auth failed: {e}")

    async def run(
        self,
        action: str,
        agent_id: Optional[str] = None,
        maturity_level: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute Calendar operation with governance enforcement.

        Args:
            action: Operation to perform (get_events, create_event, etc.)
            agent_id: Agent identifier for governance check
            user_id: User ID for token lookup
            **kwargs: Action-specific parameters

        Returns:
            Dict with operation results

        Raises:
            PermissionError: If maturity level too low
        """
        # Governance check - maturity requirements by action type
        read_actions = {
            "get_events",
            "check_conflicts"
        }

        write_actions = {
            "create_event",
            "update_event",
            "delete_event"
        }

        # Determine required maturity level
        if action in read_actions:
            required_maturity = "INTERN"
        elif action in write_actions:
            required_maturity = "SUPERVISED"
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": sorted(read_actions | write_actions)
            }

        # Check governance permission
        allowed, reason = await self._check_calendar_permission(
            agent_id=agent_id,
            user_id=user_id or "default",
            action=action,
            required_maturity=required_maturity
        )

        if not allowed:
            logger.warning(
                "Calendar permission denied",
                action=action,
                agent_id=agent_id,
                reason=reason
            )
            raise PermissionError(reason)

        # Execute action
        try:
            result = await self._execute_action(
                action=action,
                user_id=user_id or "default",
                **kwargs
            )

            logger.info(
                "Calendar action completed",
                action=action,
                agent_id=agent_id,
                success=result.get("success", False)
            )

            return result

        except PermissionError:
            raise
        except Exception as e:
            logger.error(
                "Calendar action failed",
                action=action,
                error=str(e),
                kwargs=kwargs
            )
            return {
                "success": False,
                "error": str(e),
                "action": action
            }

    async def _check_calendar_permission(
        self,
        agent_id: Optional[str],
        user_id: str,
        action: str,
        required_maturity: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if agent has permission for Calendar operation.
        """
        # If no agent_id, it's a human-triggered action (allow)
        if not agent_id:
            return True, None

        # Check governance cache
        cache_key = f"calendar_{action}"
        cached = _governance_cache.get(agent_id, cache_key)
        if cached:
            return cached.get("allowed", False), cached.get("reason")

        # Check agent maturity level from database
        try:
            with get_db_session() as db:
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()

                if not agent:
                    return False, f"Agent '{agent_id}' not found"

                # Check maturity level
                maturity = agent.maturity_level
                maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

                try:
                    current_level = maturity_order.index(maturity)
                    required_level = maturity_order.index(required_maturity)
                except ValueError:
                    return False, f"Invalid maturity level: {maturity}"

                allowed = current_level >= required_level
                reason = None

                if not allowed:
                    reason = (
                        f"Calendar {action} requires {required_maturity}+ maturity "
                        f"(agent is {maturity})"
                    )

                # Cache decision
                _governance_cache.set(agent_id, cache_key, {
                    "allowed": allowed,
                    "reason": reason,
                    "maturity": maturity
                })

                return allowed, reason

        except Exception as e:
            logger.error("Permission check failed", error=str(e))
            return False, f"Permission check failed: {str(e)}"

    async def _execute_action(
        self,
        action: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute specific Calendar action.
        """
        # Ensure authenticated
        if not google_calendar_service.authenticate():
            return {
                "success": False, 
                "error": "Google Calendar is not authenticated. Please connect your Google account in Settings."
            }

        # Execute action
        if action == "get_events":
            time_min_str = kwargs.get("time_min")
            time_max_str = kwargs.get("time_max")
            max_results = kwargs.get("max_results", 100)
            
            time_min = datetime.fromisoformat(time_min_str) if time_min_str else datetime.utcnow()
            time_max = datetime.fromisoformat(time_max_str) if time_max_str else (time_min + timedelta(days=7))

            events = await google_calendar_service.get_events(
                time_min=time_min,
                time_max=time_max,
                max_results=max_results
            )
            
            return {
                "success": True,
                "action": "get_events",
                "count": len(events),
                "events": events
            }

        elif action == "check_conflicts":
            start_time_str = kwargs.get("start_time")
            end_time_str = kwargs.get("end_time")
            
            if not start_time_str or not end_time_str:
                return {"success": False, "error": "start_time and end_time parameters required"}
                
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)

            result = await google_calendar_service.check_conflicts(
                start_time=start_time,
                end_time=end_time
            )
            result["action"] = "check_conflicts"
            return result

        elif action == "create_event":
            title = kwargs.get("title")
            start_time = kwargs.get("start_time")
            end_time = kwargs.get("end_time")
            
            if not title or not start_time or not end_time:
                return {"success": False, "error": "title, start_time, and end_time parameters required"}

            event_data = {
                "title": title,
                "description": kwargs.get("description", ""),
                "start_time": start_time,
                "end_time": end_time,
                "location": kwargs.get("location", ""),
                "attendees": kwargs.get("attendees", [])
            }

            event = await google_calendar_service.create_event(event_data)
            
            if event:
                return {
                    "success": True,
                    "action": "create_event",
                    "event": event
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create event"
                }

        elif action == "update_event":
            event_id = kwargs.get("event_id")
            updates = kwargs.get("updates")
            
            if not event_id or not updates:
                return {"success": False, "error": "event_id and updates object required"}

            event = await google_calendar_service.update_event(
                event_id=event_id,
                updates=updates
            )
            
            if event:
                return {
                    "success": True,
                    "action": "update_event",
                    "event": event
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to update event {event_id}"
                }

        elif action == "delete_event":
            event_id = kwargs.get("event_id")
            
            if not event_id:
                return {"success": False, "error": "event_id required"}

            success = await google_calendar_service.delete_event(event_id=event_id)
            
            return {
                "success": success,
                "action": "delete_event",
                "event_id": event_id
            }

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": ["get_events", "check_conflicts", "create_event", "update_event", "delete_event"]
            }


# Tool registration function

def register_calendar_tool(tool_registry=None):
    """
    Register CalendarTool with tool registry.
    """
    from tools.registry import ToolRegistry, get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    calendar_tool = CalendarTool()

    tool_registry.register(
        name="calendar_tool",
        function=calendar_tool.run,
        version="1.0.0",
        description="Google Calendar tool for AI agents. Provides event creation, conflict checking, and schedule retrieval.",
        category="productivity",
        complexity=3,
        maturity_required="INTERN",
        dependencies=["google-api-python-client", "google-auth-oauthlib"],
        tags=["calendar", "schedule", "meeting", "events", "time", "google"]
    )

    logger.info("CalendarTool registered with ToolRegistry")

    return calendar_tool
