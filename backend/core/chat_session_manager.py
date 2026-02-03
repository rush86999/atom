#!/usr/bin/env python3
"""
Chat Session Manager for ATOM
Manages chat session metadata (Hybrid: DB + JSON fallback)
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import desc
from sqlalchemy.orm import Session

# Conditional Import to avoid circular dependencies if simple script
try:
    from core.database import get_db_session
    from core.models import ChatMessage, ChatSession
    DB_AVAILABLE = True
except ImportError:
    SessionLocal = None
    ChatSession = None
    ChatMessage = None
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Sessions file path (Fallback)
SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chat_sessions.json")

class ChatSessionManager:
    """Manages chat session metadata with DB support"""
    
    def __init__(self, sessions_file: str = None, workspace_id: str = None):
        self.workspace_id = "default" # Single-tenant: always use default
        self.sessions_file = sessions_file or SESSIONS_FILE
        
        # Determine persistence mode
        self.persistence_mode = os.getenv("CHAT_PERSISTENCE_MODE", "HYBRID").upper()
        
        # Determine if we should use DB
        self.use_db = False
        
        if self.persistence_mode == "STRICT_DB":
            if not (DB_AVAILABLE and SessionLocal):
                raise RuntimeError("CHAT_PERSISTENCE_MODE is STRICT_DB but database dependencies are missing!")
            
            # Verify connection
            try:
                with get_db_session() as db:
                db.execute("SELECT 1")
                db.close()
                self.use_db = True
                logger.info("ChatSessionManager initialized in STRICT_DB mode.")
            except Exception as e:
                raise RuntimeError(f"CHAT_PERSISTENCE_MODE is STRICT_DB but database connection failed: {e}")
                
        elif DB_AVAILABLE and SessionLocal:
             # Check if we can actually connect (simple check)
             try:
                 # Optional: Add logic to force file mode via env var if needed
                 if os.getenv("ATOM_CHAT_STORAGE", "auto") != "file":
                     self.use_db = True
             except Exception:
                 logger.warning("DB available but configuration check failed. Defaulting to file.")
        
        # Initialize file fallback ONLY if not in strict mode
        if not self.use_db and self.persistence_mode != "STRICT_DB":
             self._ensure_file()
        elif not self.use_db and self.persistence_mode == "STRICT_DB":
             # Should be unreachable due to exception above, but safety check
             raise RuntimeError("Failed to initialize DB in STRICT_DB mode")

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
        """Load sessions from DB if available, else file"""
        if self.use_db:
             # Warning: This loads ALL sessions. Use carefully.
            with get_db_session() as db:
            try:
                sessions = db.query(ChatSession).all()
                return [{
                    "session_id": s.id,
                    "user_id": s.user_id,
                    "title": s.title, # Added title
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "last_active": s.updated_at.isoformat() if s.updated_at else None,
                    "history": [], # Heavy payload skipped
                    "metadata": s.metadata_json or {}
                } for s in sessions]
            except Exception as e:
                 logger.error(f"DB Load All Sessions failed: {e}")
            finally:
                db.close()
                
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
            with get_db_session() as db:
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
                if self.persistence_mode == "STRICT_DB":
                    logger.error(f"DB Create Session failed in STRICT_DB mode: {e}")
                    db.rollback()
                    raise RuntimeError(f"Database write failed in STRICT_DB mode: {e}")
                
                logger.error(f"DB Create Session failed: {e}. Falling back to file.")
                db.rollback()
                # Fallthrough to file
            finally:
                db.close()

        if self.persistence_mode == "STRICT_DB":
             raise RuntimeError("Critical Error: DB flow passed but no session returned")

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
            with get_db_session() as db:
            try:
                session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if session:
                    # Fetch chat history from ChatMessage table
                    messages = db.query(ChatMessage)\
                        .filter(ChatMessage.conversation_id == session_id)\
                        .order_by(desc(ChatMessage.created_at))\
                        .limit(100)\
                        .all()

                    history = [
                        {
                            "role": msg.role,
                            "content": msg.content,
                            "created_at": msg.created_at.isoformat() if msg.created_at else None
                        }
                        for msg in messages
                    ]

                    return {
                        "session_id": session.id,
                        "user_id": session.user_id,
                        "created_at": session.created_at.isoformat() if session.created_at else None,
                        "last_active": session.updated_at.isoformat() if session.updated_at else None,
                        "metadata": session.metadata_json or {},
                        "message_count": session.message_count,
                        "history": history
                    }
            except Exception as e:
                 if self.persistence_mode == "STRICT_DB":
                    logger.error(f"DB Get Session failed in STRICT_DB mode: {e}")
                    raise RuntimeError(f"Database read failed in STRICT_DB mode: {e}")
                 logger.warning(f"DB Get Session failed: {e}")
            finally:
                db.close()

        if self.persistence_mode == "STRICT_DB":
            return None # Do not fall back to file implementation

        # File fallback
        sessions = self._load_sessions_file()
        return next((s for s in sessions if s['session_id'] == session_id), None)
    
    def update_session_activity(self, session_id: str, history: List[Dict] = None, last_message: str = None):
        """Update session's last_active timestamp and history"""
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
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
                if self.persistence_mode == "STRICT_DB":
                    logger.error(f"DB Update Session failed in STRICT_DB mode: {e}")
                    raise RuntimeError(f"Database update failed in STRICT_DB mode: {e}")
                logger.error(f"DB Update Session failed: {e}")
            finally:
                db.close()
        
        if self.persistence_mode == "STRICT_DB":
            return # Do not fall back to file implementation

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
            with get_db_session() as db:
            try:
                # Query DB
                sessions = db.query(ChatSession)\
                             .filter(ChatSession.user_id == user_id)\
                             .order_by(desc(ChatSession.updated_at))\
                             .limit(limit)\
                             .all()
                
                # Convert DB sessions to dicts
                results = [{
                    "session_id": s.id,
                    "user_id": s.user_id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "last_active": s.updated_at.isoformat() if s.updated_at else None,
                    "metadata": s.metadata_json or {},
                    "message_count": s.message_count,
                    "history": [] # Lightweight list
                } for s in sessions]



                # STRICT_DB: Return only DB results
                if self.persistence_mode == "STRICT_DB":
                    return results

                # HYBRID MERGE: Also load from file and append any missing ones
                # This handles the case where we switched to DB mode but have old file sessions
                try:
                    file_sessions = self._load_sessions_file()
                    db_ids = {r["session_id"] for r in results}
                    
                    # Filter for this user and not in DB
                    legacy_sessions = [
                        s for s in file_sessions 
                        if s.get("user_id") == user_id and s.get("session_id") not in db_ids
                    ]
                    
                    # Sort legacy sessions
                    legacy_sessions.sort(key=lambda x: x.get('last_active', ''), reverse=True)
                    
                    # Append (respecting limit if needed, though we might go over)
                    results.extend(legacy_sessions)
                    
                    # Re-sort combined results
                    results.sort(key=lambda x: x.get('last_active', '') or '', reverse=True)
                    
                    return results[:limit]
                    
                except Exception as e:
                    logger.warning(f"Hybrid merge failed: {e}")
                    return results # Return at least DB results

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
            with get_db_session() as db:
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

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Rename a session"""
        
        # 1. Database Path
        if self.use_db:
            with get_db_session() as db:
            try:
                session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if session:
                    session.title = new_title
                    session.updated_at = datetime.utcnow()
                    db.commit()
                    # We continue to file sync for hybrid safety if desired,
                    # but usually for true hybrid we just rely on DB if active.
                    # For now, let's keep them in sync if file exists.
            except Exception as e:
                logger.error(f"DB Rename Session failed: {e}")
                return False
            finally:
                db.close()

        # 2. File Path (Always try to sync file for consistency in hybrid mode)
        sessions = self._load_sessions_file()
        updated = False
        for session in sessions:
            if session['session_id'] == session_id:
                session['title'] = new_title
                session['last_active'] = datetime.utcnow().isoformat()
                updated = True
                break
        
        if updated:
            self._save_sessions_file(sessions)
            
        return updated or self.use_db # Return true if either DB or File updated successfully


# Global instance
chat_session_manager = ChatSessionManager()

def get_chat_session_manager(workspace_id: str = None) -> ChatSessionManager:
    """Get workspace-aware chat session manager instance"""
    return ChatSessionManager(workspace_id=workspace_id)
