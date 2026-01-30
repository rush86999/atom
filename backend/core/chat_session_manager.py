#!/usr/bin/env python3
"""
Chat Session Manager for ATOM
Manages chat session metadata (Hybrid: DB + JSON fallback)
"""

import json
import os
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Conditional Import to avoid circular dependencies if simple script
try:
    from core.database import SessionLocal
    from core.models import ChatSession
    DB_AVAILABLE = True
except ImportError:
    SessionLocal = None
    ChatSession = None
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Sessions file path (Fallback)
SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chat_sessions.json")

class ChatSessionManager:
    """Manages chat session metadata with DB support"""
    
    def __init__(self, sessions_file: str = None, workspace_id: str = None):
        self.workspace_id = "default" # Single-tenant: always use default
        self.sessions_file = sessions_file or SESSIONS_FILE
        
        # Determine if we should use DB
        self.use_db = False
        if DB_AVAILABLE and SessionLocal:
             # Check if we can actually connect (simple check)
             try:
                 # Optional: Add logic to force file mode via env var if needed
                 if os.getenv("ATOM_CHAT_STORAGE", "auto") != "file":
                     self.use_db = True
             except Exception:
                 logger.warning("DB available but configuration check failed. Defaulting to file.")
        
        if not self.use_db:
             self._ensure_file()

    def _ensure_file(self):
        """Ensure sessions file exists"""
        if not os.path.exists(self.sessions_file):
            self._save_sessions_file([])
    
    def _load_sessions_file(self) -> List[Dict[str, Any]]:
        """Load all sessions from file"""
        try:
            if not os.path.exists(self.sessions_file):
                return []
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sessions file: {e}")
            return []
            
    def _load_sessions(self) -> List[Dict[str, Any]]:
        """Backward compatibility alias for _load_sessions_file"""
        return self._load_sessions_file()
    
    def _save_sessions_file(self, sessions: List[Dict[str, Any]]):
        """Save all sessions to file atomically"""
        try:
            # Atomic write pattern
            temp_file = self.sessions_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(sessions, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.sessions_file)
        except Exception as e:
            logger.error(f"Failed to save sessions file: {e}")

    def create_session(
        self,
        user_id: str,
        metadata: Dict[str, Any] = None,
        session_id: str = None
    ) -> str:
        """Create a new chat session."""
        if not session_id:
            session_id = str(uuid.uuid4())
            
        timestamp = datetime.utcnow().isoformat()
        
        # 1. Database Path
        if self.use_db:
            db = SessionLocal()
            try:
                new_session = ChatSession(
                    id=session_id,
                    user_id=user_id,
                    metadata_json=metadata or {},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    message_count=0
                )
                db.add(new_session)
                db.commit()
                logger.info(f"Created DB session: {session_id}")
                return session_id
            except Exception as e:
                logger.error(f"DB Create Session failed: {e}. Falling back to file.")
                db.rollback()
                # Fallthrough to file
            finally:
                db.close()

        # 2. File Path (Fallback or Primary)
        sessions = self._load_sessions_file()
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": timestamp,
            "last_active": timestamp,
            "metadata": metadata or {},
            "message_count": 0,
            "history": [] 
        }
        sessions.append(session)
        self._save_sessions_file(sessions)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        # 1. Database Path
        if self.use_db:
            db = SessionLocal()
            try:
                session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if session:
                    return {
                        "session_id": session.id,
                        "user_id": session.user_id,
                        "created_at": session.created_at.isoformat() if session.created_at else None,
                        "last_active": session.updated_at.isoformat() if session.updated_at else None,
                        "metadata": session.metadata_json or {},
                        "message_count": session.message_count,
                        "history": [] # TODO: Fetch history from ChatMessage table if needed here
                    }
            except Exception as e:
                 logger.warning(f"DB Get Session failed: {e}")
            finally:
                db.close()

        # 2. File Path
        sessions = self._load_sessions_file()
        return next((s for s in sessions if s['session_id'] == session_id), None)
    
    def update_session_activity(self, session_id: str, history: List[Dict] = None, last_message: str = None):
        """Update session's last_active timestamp and history"""
        # 1. Database Path
        if self.use_db:
            db = SessionLocal()
            try:
                session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if session:
                    session.updated_at = datetime.utcnow()
                    if history is not None:
                        session.message_count = len(history)
                        # Ideally, messages are stored in ChatMessage table separately.
                        # This manager focuses on the Session Metadata.
                    db.commit()
                    return # Success
            except Exception as e:
                logger.error(f"DB Update Session failed: {e}")
            finally:
                db.close()

        # 2. File Path
        sessions = self._load_sessions_file()
        updated = False
        for session in sessions:
            if session['session_id'] == session_id:
                session['last_active'] = datetime.utcnow().isoformat()
                if history is not None:
                    session['history'] = history
                    session['message_count'] = len(history)
                if last_message:
                    session['last_message'] = last_message
                updated = True
                break
        
        if not updated:
             # Auto-recover for file mode
             new_session = {
                "session_id": session_id,
                "user_id": "default",
                "created_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
                "metadata": {"source": "recovered"},
                "message_count": len(history) if history else 0,
                "history": history or []
            }
             sessions.append(new_session)
        
        self._save_sessions_file(sessions)
    
    def list_user_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List all sessions for a user (most recent first)"""
        # 1. Database Path
        if self.use_db:
            db = SessionLocal()
            try:
                # Query DB
                sessions = db.query(ChatSession)\
                             .filter(ChatSession.user_id == user_id)\
                             .order_by(desc(ChatSession.updated_at))\
                             .limit(limit)\
                             .all()
                
                return [{
                    "session_id": s.id,
                    "user_id": s.user_id,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "last_active": s.updated_at.isoformat() if s.updated_at else None,
                    "metadata": s.metadata_json or {},
                    "message_count": s.message_count,
                    "history": [] # Lightweight list
                } for s in sessions]
            except Exception as e:
                logger.error(f"DB List Sessions failed: {e}")
            finally:
                db.close()

        # 2. File Path
        sessions = self._load_sessions_file()
        user_sessions = [s for s in sessions if s.get('user_id') == user_id]
        user_sessions.sort(key=lambda x: x.get('last_active', ''), reverse=True)
        return user_sessions[:limit]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        deleted = False
        
        # 1. Database Path
        if self.use_db:
            db = SessionLocal()
            try:
                session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if session:
                    db.delete(session)
                    db.commit()
                    deleted = True
            except Exception as e:
                logger.error(f"DB Delete Session failed: {e}")
            finally:
                db.close()
                
        # 2. File Path (Always try to clean up file too, just in case)
        sessions = self._load_sessions_file()
        initial_count = len(sessions)
        sessions = [s for s in sessions if s['session_id'] != session_id]
        if len(sessions) < initial_count:
            self._save_sessions_file(sessions)
            deleted = True
            
        return deleted

# Global instance
chat_session_manager = ChatSessionManager()

def get_chat_session_manager(workspace_id: str = None) -> ChatSessionManager:
    """Get workspace-aware chat session manager instance"""
    return ChatSessionManager(workspace_id=workspace_id)
