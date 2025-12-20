
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.unified_calendar_endpoints import MOCK_EVENTS
from core.unified_task_endpoints import MOCK_TASKS

logger = logging.getLogger(__name__)

class CrossSystemReasoningEngine:
    """Engine for performing cross-system semantic analysis and consistency enforcement"""
    
    def __init__(self):
        pass

    async def enforce_consistency(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Detect inconsistencies between CRM deal stages and Calendar events.
        Example: A deal is 'Closed' but there are still active 'Sales Call' meetings.
        """
        inconsistencies = []
        
        # 1. Fetch CRM data (In a real system, this would call hubspot_service/salesforce_service)
        # Mocking for demonstration: Assume a closed deal "Deal-123"
        closed_deals = ["Deal-123"]
        
        # 2. Scan Calendar for meetings linked to closed deals
        for event in MOCK_EVENTS:
            if event.metadata and event.metadata.get("deal_id") in closed_deals:
                # If meeting type implies active sales but deal is closed
                if "sales" in event.title.lower() or "demo" in event.title.lower():
                    inconsistencies.append({
                        "type": "CRM_CALENDAR_MISMATCH",
                        "severity": "medium",
                        "resource_id": event.id,
                        "title": event.title,
                        "description": f"The deal '{event.metadata.get('deal_id')}' is marked as CLOSED, but this sales/demo meeting is still scheduled.",
                        "suggested_action": "Cancel or re-categorize this meeting."
                    })
                    
        return inconsistencies

    async def deduplicate_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Semantic identification of duplicate tasks across platforms.
        """
        duplicates = []
        # Simple semantic check: overlap in titles and projects
        seen_titles = {} # Title -> TaskId
        
        for task in MOCK_TASKS:
            title_norm = task.title.lower().strip()
            if title_norm in seen_titles:
                original_id = seen_titles[title_norm]
                duplicates.append({
                    "type": "SEMANTIC_DUPLICATION",
                    "original_id": original_id,
                    "duplicate_id": task.id,
                    "title": task.title,
                    "platform": task.platform,
                    "description": f"Potential duplicate task found: '{task.title}' exists on both {task.platform} and local storage.",
                    "suggested_action": "Merge these tasks."
                })
            else:
                seen_titles[title_norm] = task.id
                
        return duplicates

    async def check_dependencies(self, workflow_id: str, results: Dict[str, Any]) -> bool:
        """
        Block execution if semantic prerequisites are unmet.
        """
        # Logic: If a task marked as 'dependency' is not 'completed', return False
        for task_id in results.get("dependencies", []):
            task = next((t for t in MOCK_TASKS if t.id == task_id), None)
            if task and task.status != "completed":
                logger.warning(f"Dependency check failed: Task {task_id} is {task.status}")
                return False
        return True

# Global instance
reasoning_engine = CrossSystemReasoningEngine()

def get_reasoning_engine():
    return reasoning_engine
