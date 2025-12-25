#!/usr/bin/env python3
"""
Chat Session Manager for ATOM
Manages chat session metadata (simple JSON-based storage)
"""

import json
import os
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Sessions file path
SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chat_sessions.json")

class ChatSessionManager:
    """Manages chat session metadata"""
    
    def __init__(self, sessions_file: str = None, workspace_id: str = None):
        self.workspace_id = workspace_id or "default"
        
        if sessions_file:
            self.sessions_file = sessions_file
        else:
            # Derive filename from workspace_id
            base_dir = os.path.dirname(os.path.dirname(__file__))
            filename = f"chat_sessions_{self.workspace_id}.json"
            self.sessions_file = os.path.join(base_dir, filename)
            
        self._ensure_file()
    
    def _ensure_file(self):
        """Ensure sessions file exists"""
        if not os.path.exists(self.sessions_file):
            self._save_sessions([])
    
    def _load_sessions(self) -> List[Dict[str, Any]]:
        """Load all sessions from file"""
        try:
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
            return []
    
    def _save_sessions(self, sessions: List[Dict[str, Any]]):
        """Save all sessions to file"""
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
    
    def create_session(
        self,
        user_id: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Create a new chat session.
        
        Returns: session_id
        """
        sessions = self._load_sessions()
        
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "message_count": 0
        }
        
        sessions.append(session)
        self._save_sessions(sessions)
        
        logger.info(f"Created session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        sessions = self._load_sessions()
        return next((s for s in sessions if s['session_id'] == session_id), None)
    
    def update_session_activity(self, session_id: str):
        """Update session's last_active timestamp"""
        sessions = self._load_sessions()
        for session in sessions:
            if session['session_id'] == session_id:
                session['last_active'] = datetime.utcnow().isoformat()
                session['message_count'] = session.get('message_count', 0) + 1
                break
        self._save_sessions(sessions)
    
    def list_user_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List all sessions for a user (most recent first)"""
        sessions = self._load_sessions()
        user_sessions = [s for s in sessions if s['user_id'] == user_id]
        
        # Sort by last_active (most recent first)
        user_sessions.sort(key=lambda x: x['last_active'], reverse=True)
        
        return user_sessions[:limit]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        sessions = self._load_sessions()
        initial_count = len(sessions)
        sessions = [s for s in sessions if s['session_id'] != session_id]
        
        if len(sessions) < initial_count:
            self._save_sessions(sessions)
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

# Global instance
chat_session_manager = ChatSessionManager()

def get_chat_session_manager(workspace_id: str = None) -> ChatSessionManager:
    """Get workspace-aware chat session manager instance"""
    return ChatSessionManager(workspace_id=workspace_id)
