import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Google Slides API configuration
GOOGLE_SLIDES_API_BASE = "https://slides.googleapis.com/v1"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

class GoogleSlidesService:
    """Comprehensive Google Slides API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Google Slides service with database pool"""
        try:
            from db_oauth_google_drive import get_user_google_drive_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_google_drive_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self._initialized = True
                logger.info(f"Google Slides service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Google tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Slides service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Google Slides service not initialized. Call initialize() first.")
    
    async def get_presentations(self, query: str = None, page_size: int = 50) -> Dict[str, Any]:
        """Get Google Slides presentations"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Search for Google Slides files
            search_query = "mimeType='application/vnd.google-apps.presentation'"
            if query:
                search_query += f" and name contains '{query}'"
            
            params = {
                "q": search_query,
                "pageSize": page_size,
                "fields": "files(id,name,mimeType,createdTime,modifiedTime,webViewLink,webContentLink,parents,lastModifyingUser,thumbnailLink,owners,shared,size,version)",
                "orderBy": "modifiedTime desc"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_DRIVE_API_BASE}/files",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                presentations = []
                
                for file in data.get("files", []):
                    # Get presentation details
                    pres_details = await self.get_presentation_details(file["id"])
                    
                    presentations.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": "presentation",
                        "mimeType": file.get("mimeType"),
                        "created": file.get("createdTime"),
                        "modified": file.get("modifiedTime"),
                        "webViewLink": file.get("webViewLink"),
                        "webContentLink": file.get("webContentLink"),
                        "parents": file.get("parents", []),
                        "owner": file.get("owners", [{}])[0].get("displayName", "Unknown"),
                        "ownerEmail": file.get("owners", [{}])[0].get("emailAddress", ""),
                        "thumbnail": file.get("thumbnailLink"),
                        "shared": len(file.get("owners", [])) > 1,
                        "size": file.get("size", "0"),
                        "version": file.get("version"),
                        "presentationId": pres_details.get("presentationId", file.get("id")),
                        "pageSize": pres_details.get("pageSize", {}),
                        "masters": pres_details.get("masters", []),
                        "layouts": pres_details.get("layouts", []),
                        "slideCount": len(pres_details.get("slides", [])),
                        "slides": pres_details.get("slides", []),
                        "title": pres_details.get("title", file.get("name")),
                        "revisionId": pres_details.get("revisionId"),
                        "notesMaster": pres_details.get("notesMaster", {}),
                        "locale": pres_details.get("locale"),
                        "theme": pres_details.get("theme", {})
                    })
                
                # Cache presentations
                await self.cache_presentations(presentations)
                
                return {
                    "success": True,
                    "data": presentations,
                    "total": len(presentations)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Google Slides: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_presentation_details(self, presentation_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_SLIDES_API_BASE}/presentations/{presentation_id}",
                    headers=headers,
                    params={"fields": "presentationId,title,revisionId,pageSize,masters,layouts,slides(locale),notesMaster,locale,theme"}
                )
                response.raise_for_status()
                
                data = response.json()
                return data
                
        except Exception as e:
            logger.error(f"Failed to get presentation details: {e}")
            return {}
    
    async def create_presentation(self, title: str, theme: str = None, folder_id: str = None) -> Dict[str, Any]:
        """Create a new Google Slide presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create presentation metadata
            presentation_data = {
                "title": title
            }
            
            if theme:
                presentation_data["masters"] = [{"theme": theme}]
            
            async with httpx.AsyncClient() as client:
                # Create presentation
                response = await client.post(
                    f"{GOOGLE_SLIDES_API_BASE}/presentations",
                    headers=headers,
                    json=presentation_data
                )
                response.raise_for_status()
                
                pres_data = response.json()
                presentation_id = pres_data.get("presentationId")
                
                # Update folder if specified
                if folder_id:
                    await self.move_presentation(presentation_id, folder_id)
                
                # Log activity
                await self.log_activity("create_presentation", {
                    "presentation_id": presentation_id,
                    "title": title,
                    "theme": theme,
                    "folder_id": folder_id
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": presentation_id,
                        "title": title,
                        "presentationId": pres_data.get("presentationId"),
                        "webViewLink": f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create Google Slide presentation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_slides(self, presentation_id: str) -> Dict[str, Any]:
        """Get all slides in a presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_SLIDES_API_BASE}/presentations/{presentation_id}",
                    headers=headers,
                    params={"fields": "slides(objectId,pageElements,slideProperties,notesPage)"}
                )
                response.raise_for_status()
                
                data = response.json()
                slides = data.get("slides", [])
                
                # Process slides
                processed_slides = []
                for slide in slides:
                    processed_slides.append({
                        "objectId": slide.get("objectId"),
                        "pageElements": slide.get("pageElements", []),
                        "slideProperties": slide.get("slideProperties", {}),
                        "notesPage": slide.get("notesPage", {}),
                        "elementCount": len(slide.get("pageElements", []))
                    })
                
                return {
                    "success": True,
                    "data": {
                        "presentationId": presentation_id,
                        "slides": processed_slides,
                        "slideCount": len(processed_slides)
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get slides: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def add_slide(self, presentation_id: str, slide_index: int = None, layout_id: str = None) -> Dict[str, Any]:
        """Add a new slide to the presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create request for adding slide
            requests = []
            if slide_index is not None:
                if layout_id:
                    requests.append({
                        "createSlide": {
                            "objectId": f"slide_{datetime.now().timestamp()}",
                            "insertionIndex": slide_index,
                            "slideLayoutReference": {
                                "layoutId": layout_id
                            }
                        }
                    })
                else:
                    requests.append({
                        "createSlide": {
                            "objectId": f"slide_{datetime.now().timestamp()}",
                            "insertionIndex": slide_index
                        }
                    })
            else:
                requests.append({
                    "createSlide": {
                        "objectId": f"slide_{datetime.now().timestamp()}",
                        "slideLayoutReference": {
                            "layoutId": layout_id or "TITLE_AND_BODY"
                        }
                    }
                })
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SLIDES_API_BASE}/presentations/{presentation_id}:batchUpdate",
                    headers=headers,
                    json={"requests": requests}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("add_slide", {
                    "presentation_id": presentation_id,
                    "slide_index": slide_index,
                    "layout_id": layout_id
                })
                
                return {
                    "success": True,
                    "data": data.get("replies", [])
                }
                
        except Exception as e:
            logger.error(f"Failed to add slide: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_slide_content(self, presentation_id: str, slide_id: str, content: str) -> Dict[str, Any]:
        """Update slide content with text"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create request to update content
            requests = [
                {
                    "insertText": {
                        "objectId": slide_id,
                        "text": content,
                        "insertionIndex": 0
                    }
                }
            ]
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SLIDES_API_BASE}/presentations/{presentation_id}:batchUpdate",
                    headers=headers,
                    json={"requests": requests}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("update_slide_content", {
                    "presentation_id": presentation_id,
                    "slide_id": slide_id,
                    "content_length": len(content)
                })
                
                return {
                    "success": True,
                    "data": data.get("replies", [])
                }
                
        except Exception as e:
            logger.error(f"Failed to update slide content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_presentations(self, query: str, search_scope: str = "all") -> Dict[str, Any]:
        """Search Google Slides presentations"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build search query
            search_query = "mimeType='application/vnd.google-apps.presentation'"
            
            if search_scope == "title":
                search_query += f" and name contains '{query}'"
            elif search_scope == "content":
                # For content search, we need to use Drive API with fullText search
                search_query += f" and fullText contains '{query}'"
            else:
                search_query += f" and name contains '{query}' and fullText contains '{query}'"
            
            params = {
                "q": search_query,
                "pageSize": 50,
                "fields": "files(id,name,mimeType,createdTime,modifiedTime,webViewLink,parents,owners,lastModifyingUser,thumbnailLink,size,version)",
                "orderBy": "modifiedTime desc"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_DRIVE_API_BASE}/files",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                presentations = []
                
                for file in data.get("files", []):
                    presentations.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": "presentation",
                        "mimeType": file.get("mimeType"),
                        "created": file.get("createdTime"),
                        "modified": file.get("modifiedTime"),
                        "webViewLink": file.get("webViewLink"),
                        "owner": file.get("owners", [{}])[0].get("displayName", "Unknown"),
                        "thumbnail": file.get("thumbnailLink"),
                        "size": file.get("size", "0"),
                        "snippet": self.get_presentation_snippet(file.get("id"))
                    })
                
                # Log search activity
                await self.log_activity("search_presentations", {
                    "query": query,
                    "scope": search_scope,
                    "results_count": len(presentations)
                })
                
                return {
                    "success": True,
                    "data": presentations,
                    "total": len(presentations)
                }
                
        except Exception as e:
            logger.error(f"Failed to search Google Slides: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_presentation_permissions(self, presentation_id: str) -> Dict[str, Any]:
        """Get sharing permissions for a presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "fields": "permissions(id,type,emailAddress,domain,role,displayName,photoLink,deleted,expirationTime,teamDrivePermissionDetails)"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{presentation_id}/permissions",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                permissions = data.get("permissions", [])
                
                return {
                    "success": True,
                    "data": permissions
                }
                
        except Exception as e:
            logger.error(f"Failed to get presentation permissions: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def share_presentation(self, presentation_id: str, email_addresses: List[str], role: str = "reader") -> Dict[str, Any]:
        """Share a presentation with specified users"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            results = []
            
            for email in email_addresses:
                permission_data = {
                    "role": role,  # owner, organizer, fileOrganizer, writer, reader, commenter
                    "type": "user",
                    "emailAddress": email
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{GOOGLE_DRIVE_API_BASE}/files/{presentation_id}/permissions",
                        headers=headers,
                        json=permission_data
                    )
                    response.raise_for_status()
                    
                    results.append({
                        "email": email,
                        "role": role,
                        "success": True
                    })
            
            # Log sharing activity
            await self.log_activity("share_presentation", {
                "presentation_id": presentation_id,
                "email_addresses": email_addresses,
                "role": role
            })
            
            return {
                "success": True,
                "data": results
            }
            
        except Exception as e:
            logger.error(f"Failed to share presentation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_presentation(self, presentation_id: str) -> Dict[str, Any]:
        """Delete a Google Slide presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{presentation_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("delete_presentation", {
                    "presentation_id": presentation_id
                })
                
                return {
                    "success": True,
                    "message": "Presentation deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete presentation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_presentation_themes(self) -> Dict[str, Any]:
        """Get available presentation themes"""
        try:
            await self._ensure_initialized()
            
            # Predefined themes (Google Slides has limited theme API)
            themes = [
                {"id": "DEFAULT_THEME", "name": "Default Theme"},
                {"id": "TITLE_ONLY", "name": "Title Only"},
                {"id": "TITLE_AND_BODY", "name": "Title and Body"},
                {"id": "SECTION_TITLE", "name": "Section Title"},
                {"id": "MAIN_POINT", "name": "Main Point"},
                {"id": "BLANK", "name": "Blank"}
            ]
            
            return {
                "success": True,
                "data": themes
            }
            
        except Exception as e:
            logger.error(f"Failed to get presentation themes: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def duplicate_presentation(self, presentation_id: str, new_title: str, folder_id: str = None) -> Dict[str, Any]:
        """Duplicate an existing presentation"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create copy request
            file_metadata = {
                "name": new_title,
                "parents": [folder_id] if folder_id else []
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{presentation_id}/copy",
                    headers=headers,
                    json=file_metadata
                )
                response.raise_for_status()
                
                file_data = response.json()
                
                # Log activity
                await self.log_activity("duplicate_presentation", {
                    "source_id": presentation_id,
                    "new_id": file_data.get("id"),
                    "new_title": new_title,
                    "folder_id": folder_id
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": file_data.get("id"),
                        "name": new_title,
                        "webViewLink": file_data.get("webViewLink"),
                        "created": file_data.get("createdTime")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to duplicate presentation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def move_presentation(self, presentation_id: str, folder_id: str) -> Dict[str, Any]:
        """Move presentation to a different folder"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{presentation_id}",
                    headers=headers,
                    json={"parents": [folder_id]}
                )
                response.raise_for_status()
                
                return {
                    "success": True,
                    "message": "Presentation moved successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to move presentation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_presentation_snippet(self, presentation_id: str) -> str:
        """Get a snippet of presentation content for preview"""
        try:
            # Get first slide for preview
            slides_result = await self.get_slides(presentation_id)
            if slides_result["success"] and slides_result["data"]["slides"]:
                first_slide = slides_result["data"]["slides"][0]
                elements = first_slide.get("pageElements", [])
                
                # Extract text from elements
                text_content = []
                for element in elements:
                    if "text" in element.get("shape", {}):
                        text_content.append(element["shape"]["text"].get("content", ""))
                
                return "\n".join(text_content)[:200] + "..." if len("\n".join(text_content)) > 200 else "\n".join(text_content)
            return ""
        except Exception as e:
            logger.error(f"Failed to get presentation snippet: {e}")
            return ""
    
    async def cache_presentations(self, presentations: List[Dict[str, Any]]) -> bool:
        """Cache Google Slides data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_slides_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        presentation_id VARCHAR(255) NOT NULL,
                        presentation_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, presentation_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_slides_user_id ON google_slides_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_slides_presentation_id ON google_slides_cache(presentation_id);
                """)
                
                # Update cache
                for pres in presentations:
                    await conn.execute("""
                        INSERT INTO google_slides_cache 
                        (user_id, presentation_id, presentation_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, presentation_id)
                        DO UPDATE SET 
                            presentation_data = EXCLUDED.presentation_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, pres["id"], json.dumps(pres))
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Google Slides: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Google Slides activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_slides_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_slides_activity_user_id ON google_slides_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_slides_activity_action ON google_slides_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO google_slides_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Google Slides activity: {e}")
            return False