import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Google Keep API configuration (Note: Google Keep doesn't have official API, using unofficial or alternative approach)
# For this implementation, we'll use a simulated approach that could work with Google Apps Script
# Or consider using Google Keep's unofficial API endpoints

GOOGLE_KEEP_API_BASE = "https://www.googleapis.com/keep/v1"  # This is a conceptual base
# Note: In production, you might need to use Google Apps Script as a proxy
# For now, we'll create a service structure that could work with proper endpoints

class GoogleKeepService:
    """Comprehensive Google Keep API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Google Keep service with database pool"""
        try:
            from db_oauth_google_drive import get_user_google_drive_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_google_drive_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self._initialized = True
                logger.info(f"Google Keep service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Google tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Keep service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Google Keep service not initialized. Call initialize() first.")
    
    async def get_notes(self, query: str = None, page_size: int = 50, 
                       color_filter: str = None, label_filter: str = None) -> Dict[str, Any]:
        """Get Google Keep notes"""
        try:
            await self._ensure_initialized()
            
            # Since Google Keep doesn't have official API, we'll simulate with cached data
            # In production, this would need Google Apps Script or unofficial API
            
            # Get cached notes
            cached_notes = await self.get_cached_notes(query, color_filter, label_filter)
            
            # Simulate API response
            notes = cached_notes[:page_size]
            
            return {
                "success": True,
                "data": notes,
                "total": len(cached_notes)
            }
            
        except Exception as e:
            logger.error(f"Failed to get Google Keep notes: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_note(self, title: str = None, content: str = None, 
                        color: str = None, labels: List[str] = None, 
                        reminder: str = None, checklist_items: List[str] = None) -> Dict[str, Any]:
        """Create a new Google Keep note"""
        try:
            await self._ensure_initialized()
            
            # Create note object
            note_id = f"note_{datetime.now().timestamp()}"
            note_data = {
                "id": note_id,
                "title": title or "",
                "content": content or "",
                "color": color or "DEFAULT",
                "labels": labels or [],
                "reminder": reminder,
                "checklistItems": checklist_items or [],
                "created": datetime.now(timezone.utc).isoformat(),
                "modified": datetime.now(timezone.utc).isoformat(),
                "archived": False,
                "pinned": False,
                "trashed": False
            }
            
            # Save to cache
            await self.cache_note(note_data)
            
            # Log activity
            await self.log_activity("create_note", {
                "note_id": note_id,
                "title": title,
                "has_content": bool(content),
                "color": color,
                "labels_count": len(labels) if labels else 0,
                "has_reminder": bool(reminder),
                "checklist_items_count": len(checklist_items) if checklist_items else 0
            })
            
            return {
                "success": True,
                "data": note_data
            }
            
        except Exception as e:
            logger.error(f"Failed to create Google Keep note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_note(self, note_id: str, title: str = None, content: str = None, 
                        color: str = None, labels: List[str] = None, 
                        reminder: str = None, archived: bool = None, 
                        pinned: bool = None, checklist_items: List[str] = None) -> Dict[str, Any]:
        """Update an existing Google Keep note"""
        try:
            await self._ensure_initialized()
            
            # Get existing note
            existing_note = await self.get_cached_note(note_id)
            if not existing_note:
                return {
                    "success": False,
                    "error": "Note not found"
                }
            
            # Update note data
            updated_data = existing_note.copy()
            if title is not None:
                updated_data["title"] = title
            if content is not None:
                updated_data["content"] = content
            if color is not None:
                updated_data["color"] = color
            if labels is not None:
                updated_data["labels"] = labels
            if reminder is not None:
                updated_data["reminder"] = reminder
            if archived is not None:
                updated_data["archived"] = archived
            if pinned is not None:
                updated_data["pinned"] = pinned
            if checklist_items is not None:
                updated_data["checklistItems"] = checklist_items
            
            updated_data["modified"] = datetime.now(timezone.utc).isoformat()
            
            # Save to cache
            await self.cache_note(updated_data)
            
            # Log activity
            await self.log_activity("update_note", {
                "note_id": note_id,
                "updated_fields": list(filter(lambda x: x is not None, [
                    "title" if title is not None else None,
                    "content" if content is not None else None,
                    "color" if color is not None else None,
                    "labels" if labels is not None else None,
                    "reminder" if reminder is not None else None,
                    "archived" if archived is not None else None,
                    "pinned" if pinned is not None else None,
                    "checklistItems" if checklist_items is not None else None
                ]))
            })
            
            return {
                "success": True,
                "data": updated_data
            }
            
        except Exception as e:
            logger.error(f"Failed to update Google Keep note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_note(self, note_id: str) -> Dict[str, Any]:
        """Delete a Google Keep note"""
        try:
            await self._ensure_initialized()
            
            # Check if note exists
            existing_note = await self.get_cached_note(note_id)
            if not existing_note:
                return {
                    "success": False,
                    "error": "Note not found"
                }
            
            # Mark as trashed (Google Keep behavior)
            existing_note["trashed"] = True
            existing_note["modified"] = datetime.now(timezone.utc).isoformat()
            
            # Save to cache
            await self.cache_note(existing_note)
            
            # Log activity
            await self.log_activity("delete_note", {
                "note_id": note_id,
                "trashed": True
            })
            
            return {
                "success": True,
                "message": "Note deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete Google Keep note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_labels(self) -> Dict[str, Any]:
        """Get all labels from Google Keep"""
        try:
            await self._ensure_initialized()
            
            # Get cached labels
            cached_labels = await self.get_cached_labels()
            
            return {
                "success": True,
                "data": cached_labels,
                "total": len(cached_labels)
            }
            
        except Exception as e:
            logger.error(f"Failed to get Google Keep labels: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_label(self, name: str, color: str = None) -> Dict[str, Any]:
        """Create a new label in Google Keep"""
        try:
            await self._ensure_initialized()
            
            # Create label object
            label_id = f"label_{datetime.now().timestamp()}"
            label_data = {
                "id": label_id,
                "name": name,
                "color": color or "DEFAULT",
                "created": datetime.now(timezone.utc).isoformat(),
                "modified": datetime.now(timezone.utc).isoformat()
            }
            
            # Save to cache
            await self.cache_label(label_data)
            
            # Log activity
            await self.log_activity("create_label", {
                "label_id": label_id,
                "name": name,
                "color": color
            })
            
            return {
                "success": True,
                "data": label_data
            }
            
        except Exception as e:
            logger.error(f"Failed to create Google Keep label: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_notes(self, query: str, color_filter: str = None, 
                         label_filter: str = None, date_filter: str = None) -> Dict[str, Any]:
        """Search Google Keep notes"""
        try:
            await self._ensure_initialized()
            
            # Get all notes
            all_notes = await self.get_cached_notes()
            
            # Apply filters
            filtered_notes = []
            for note in all_notes:
                # Skip trashed notes
                if note.get("trashed", False):
                    continue
                
                # Text search
                if query:
                    search_text = f"{note.get('title', '')} {note.get('content', '')}".lower()
                    if query.lower() not in search_text:
                        continue
                
                # Color filter
                if color_filter and note.get("color", "DEFAULT") != color_filter:
                    continue
                
                # Label filter
                if label_filter and label_filter not in note.get("labels", []):
                    continue
                
                # Date filter (simple implementation)
                if date_filter:
                    # In production, implement proper date filtering
                    pass
                
                filtered_notes.append(note)
            
            # Sort by modified date
            filtered_notes.sort(key=lambda x: x.get("modified", ""), reverse=True)
            
            # Log search activity
            await self.log_activity("search_notes", {
                "query": query,
                "color_filter": color_filter,
                "label_filter": label_filter,
                "date_filter": date_filter,
                "results_count": len(filtered_notes)
            })
            
            return {
                "success": True,
                "data": filtered_notes,
                "total": len(filtered_notes)
            }
            
        except Exception as e:
            logger.error(f"Failed to search Google Keep notes: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def pin_note(self, note_id: str) -> Dict[str, Any]:
        """Pin a note to the top"""
        try:
            await self._ensure_initialized()
            
            return await self.update_note(note_id, pinned=True)
            
        except Exception as e:
            logger.error(f"Failed to pin Google Keep note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def unpin_note(self, note_id: str) -> Dict[str, Any]:
        """Unpin a note"""
        try:
            await self._ensure_initialized()
            
            return await self.update_note(note_id, pinned=False)
            
        except Exception as e:
            logger.error(f"Failed to unpin Google Keep note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def archive_note(self, note_id: str) -> Dict[str, Any]:
        """Archive a note"""
        try:
            await self._ensure_initialized()
            
            return await self.update_note(note_id, archived=True)
            
        except Exception as e:
            logger.error(f"Failed to archive Google Keep note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_note_content(self, note_id: str) -> Dict[str, Any]:
        """Get detailed content of a note"""
        try:
            await self._ensure_initialized()
            
            note = await self.get_cached_note(note_id)
            if not note:
                return {
                    "success": False,
                    "error": "Note not found"
                }
            
            # Process note content for display
            processed_content = {
                "title": note.get("title", ""),
                "content": note.get("content", ""),
                "checklistItems": note.get("checklistItems", []),
                "attachments": note.get("attachments", []),
                "reminders": note.get("reminders", [])
            }
            
            return {
                "success": True,
                "data": processed_content
            }
            
        except Exception as e:
            logger.error(f"Failed to get note content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_available_colors(self) -> Dict[str, Any]:
        """Get available note colors"""
        try:
            await self._ensure_initialized()
            
            colors = [
                {"name": "DEFAULT", "hex": "#FFFFFF"},
                {"name": "RED", "hex": "#F28B82"},
                {"name": "ORANGE", "hex": "#FABD02"},
                {"name": "YELLOW", "hex": "#FFF475"},
                {"name": "GREEN", "hex": "#CCFF90"},
                {"name": "TEAL", "hex": "#A7FFEB"},
                {"name": "BLUE", "hex": "#CBF0F8"},
                {"name": "PURPLE", "hex": "#D7AEFB"},
                {"name": "PINK", "hex": "#FFD2D2"},
                {"name": "BROWN", "hex": "#E6C9A8"},
                {"name": "GRAY", "hex": "#E8EAED"}
            ]
            
            return {
                "success": True,
                "data": colors
            }
            
        except Exception as e:
            logger.error(f"Failed to get available colors: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_pinned_notes(self) -> Dict[str, Any]:
        """Get all pinned notes"""
        try:
            await self._ensure_initialized()
            
            # Get all notes
            all_notes = await self.get_cached_notes()
            
            # Filter pinned notes
            pinned_notes = [
                note for note in all_notes 
                if note.get("pinned", False) and not note.get("trashed", False)
            ]
            
            # Sort by modified date
            pinned_notes.sort(key=lambda x: x.get("modified", ""), reverse=True)
            
            return {
                "success": True,
                "data": pinned_notes,
                "total": len(pinned_notes)
            }
            
        except Exception as e:
            logger.error(f"Failed to get pinned notes: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_archived_notes(self) -> Dict[str, Any]:
        """Get all archived notes"""
        try:
            await self._ensure_initialized()
            
            # Get all notes
            all_notes = await self.get_cached_notes()
            
            # Filter archived notes
            archived_notes = [
                note for note in all_notes 
                if note.get("archived", False) and not note.get("trashed", False)
            ]
            
            # Sort by modified date
            archived_notes.sort(key=lambda x: x.get("modified", ""), reverse=True)
            
            return {
                "success": True,
                "data": archived_notes,
                "total": len(archived_notes)
            }
            
        except Exception as e:
            logger.error(f"Failed to get archived notes: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Cache methods (simulating local database since no official API)
    async def get_cached_notes(self, query: str = None, color_filter: str = None, 
                            label_filter: str = None) -> List[Dict[str, Any]]:
        """Get cached notes"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_keep_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        note_id VARCHAR(255) NOT NULL,
                        note_data JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, note_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_keep_user_id ON google_keep_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_keep_note_id ON google_keep_cache(note_id);
                    CREATE INDEX IF NOT EXISTS idx_google_keep_updated_at ON google_keep_cache(updated_at);
                """)
                
                rows = await conn.fetch("""
                    SELECT note_id, note_data FROM google_keep_cache 
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                """, self.user_id)
                
                notes = []
                for row in rows:
                    note_data = json.loads(row["note_data"])
                    if not note_data.get("trashed", False):  # Don't return trashed notes
                        notes.append(note_data)
                
                return notes
                
        except Exception as e:
            logger.error(f"Failed to get cached notes: {e}")
            return []
    
    async def get_cached_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific cached note"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT note_data FROM google_keep_cache 
                    WHERE user_id = $1 AND note_id = $2
                """, self.user_id, note_id)
                
                if row:
                    return json.loads(row["note_data"])
                return None
                
        except Exception as e:
            logger.error(f"Failed to get cached note: {e}")
            return None
    
    async def cache_note(self, note_data: Dict[str, Any]) -> bool:
        """Cache a note"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO google_keep_cache 
                    (user_id, note_id, note_data, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, note_id)
                    DO UPDATE SET 
                        note_data = EXCLUDED.note_data,
                        updated_at = CURRENT_TIMESTAMP
                """, self.user_id, note_data["id"], json.dumps(note_data))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache note: {e}")
            return False
    
    async def get_cached_labels(self) -> List[Dict[str, Any]]:
        """Get cached labels"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create labels cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_keep_labels_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        label_id VARCHAR(255) NOT NULL,
                        label_data JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, label_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_keep_labels_user_id ON google_keep_labels_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_keep_labels_label_id ON google_keep_labels_cache(label_id);
                """)
                
                rows = await conn.fetch("""
                    SELECT label_data FROM google_keep_labels_cache 
                    WHERE user_id = $1
                    ORDER BY label_data->>'name'
                """, self.user_id)
                
                labels = []
                for row in rows:
                    labels.append(json.loads(row["label_data"]))
                
                return labels
                
        except Exception as e:
            logger.error(f"Failed to get cached labels: {e}")
            return []
    
    async def cache_label(self, label_data: Dict[str, Any]) -> bool:
        """Cache a label"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO google_keep_labels_cache 
                    (user_id, label_id, label_data, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, label_id)
                    DO UPDATE SET 
                        label_data = EXCLUDED.label_data,
                        updated_at = CURRENT_TIMESTAMP
                """, self.user_id, label_data["id"], json.dumps(label_data))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache label: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Google Keep activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_keep_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_keep_activity_user_id ON google_keep_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_keep_activity_action ON google_keep_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO google_keep_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Google Keep activity: {e}")
            return False