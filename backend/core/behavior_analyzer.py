import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from core.workflow_analytics_engine import get_analytics_engine
import uuid

logger = logging.getLogger(__name__)

class BehaviorAnalyzer:
    def __init__(self):
        self.analytics = get_analytics_engine()
        # In-memory window of recent actions per user+workspace for pattern detection
        self.user_action_windows: Dict[str, List[Dict[str, Any]]] = {} # key: "ws_user"
        self.window_size = 10 

    def log_user_action(self, user_id: str, action_type: str, metadata: Optional[Dict] = None, workspace_id: Optional[str] = None):
        """Log a high-level user action for pattern analysis"""
        ws_id = workspace_id or "default"
        key = f"{ws_id}_{user_id}"
        
        action = {
            "action_id": str(uuid.uuid4()),
            "user_id": user_id,
            "workspace_id": ws_id,
            "action_type": action_type,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        
        if key not in self.user_action_windows:
            self.user_action_windows[key] = []
            
        self.user_action_windows[key].append(action)
        
        # Keep window clean
        if len(self.user_action_windows[key]) > self.window_size:
            self.user_action_windows[key].pop(0)

        # Also track in general analytics
        self.analytics.track_user_activity(user_id, action_type, metadata=metadata, workspace_id=ws_id)

    def detect_patterns(self, user_id: str, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Analyze the recent actions for a user to find repeated sequences.
        """
        ws_id = workspace_id or "default"
        key = f"{ws_id}_{user_id}"
        actions = self.user_action_windows.get(key, [])
        if len(actions) < 3:
            return []

        # Simple sequence extraction (n-grams of actions)
        # In a real system, we'd use a more sophisticated sequence miner across all historical data
        recent_sequence = [a['action_type'] for a in actions]
        
        # Look for common patterns (hardcoded for demonstration)
        patterns = []
        
        # Pattern 1: Meeting Follow-up
        if "meeting_ended" in recent_sequence and "task_created" in recent_sequence:
            patterns.append({
                "name": "Meeting Follow-up Automation",
                "confidence": 0.8,
                "description": "You often create tasks right after meetings. Would you like to automate this?",
                "suggested_trigger": "meeting_ended",
                "suggested_actions": ["extract_action_items", "create_asana_task"]
            })

        # Pattern 2: Document Ingestion
        if "document_uploaded" in recent_sequence and "knowledge_update" in recent_sequence:
             patterns.append({
                "name": "Automated Knowledge Extraction",
                "confidence": 0.9,
                "description": "You usually manually add knowledge from uploaded documents. We can do this automatically.",
                "suggested_trigger": "document_uploaded",
                "suggested_actions": ["extract_entities", "update_knowledge_graph"]
            })

        return patterns

# Global instance
_behavior_analyzer = None

def get_behavior_analyzer() -> BehaviorAnalyzer:
    global _behavior_analyzer
    if _behavior_analyzer is None:
        _behavior_analyzer = BehaviorAnalyzer()
    return _behavior_analyzer
