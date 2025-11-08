import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Google Docs API configuration
GOOGLE_DOCS_API_BASE = "https://docs.googleapis.com/v1"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

class GoogleDocsService:
    """Comprehensive Google Docs API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Google Docs service with database pool"""
        try:
            from db_oauth_google_drive import get_user_google_drive_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_google_drive_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self._initialized = True
                logger.info(f"Google Docs service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Google tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Docs service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Google Docs service not initialized. Call initialize() first.")
    
    async def get_documents(self, query: str = None, page_size: int = 50) -> Dict[str, Any]:
        """Get Google Docs documents"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Search for Google Docs files
            search_query = "mimeType='application/vnd.google-apps.document'"
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
                documents = []
                
                for file in data.get("files", []):
                    # Get document details
                    doc_details = await self.get_document_details(file["id"])
                    
                    documents.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": "document",
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
                        "contentLength": doc_details.get("contentLength", 0),
                        "suggestionsViewId": doc_details.get("suggestionsViewId"),
                        "documentId": doc_details.get("documentId", file.get("id")),
                        "revisionId": doc_details.get("revisionId"),
                        "lastModifyingUser": doc_details.get("lastModifyingUser"),
                        "documentStyle": doc_details.get("documentStyle", {})
                    })
                
                # Cache documents
                await self.cache_documents(documents)
                
                return {
                    "success": True,
                    "data": documents,
                    "total": len(documents)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Google Docs: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_document_details(self, document_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific document"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_DOCS_API_BASE}/documents/{document_id}",
                    headers=headers,
                    params={"fields": "documentId,title,revisionId,contentLength,suggestionsViewId,documentStyle,documentStyle.namedStyles,lists,footnotes"}
                )
                response.raise_for_status()
                
                data = response.json()
                return data
                
        except Exception as e:
            logger.error(f"Failed to get document details: {e}")
            return {}
    
    async def create_document(self, title: str, content: str = None, folder_id: str = None) -> Dict[str, Any]:
        """Create a new Google Doc"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create file metadata
            file_metadata = {
                "name": title,
                "mimeType": "application/vnd.google-apps.document"
            }
            
            if folder_id:
                file_metadata["parents"] = [folder_id]
            
            async with httpx.AsyncClient() as client:
                # Create the document
                response = await client.post(
                    f"{GOOGLE_DRIVE_API_BASE}/files",
                    headers=headers,
                    json=file_metadata
                )
                response.raise_for_status()
                
                file_data = response.json()
                document_id = file_data.get("id")
                
                # Add content if provided
                if content:
                    await self.update_document_content(document_id, content)
                
                # Log activity
                await self.log_activity("create_document", {
                    "document_id": document_id,
                    "title": title,
                    "has_content": bool(content),
                    "folder_id": folder_id
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": document_id,
                        "name": title,
                        "webViewLink": file_data.get("webViewLink"),
                        "created": file_data.get("createdTime")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create Google Doc: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_document_content(self, document_id: str) -> Dict[str, Any]:
        """Get the content of a Google Doc"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_DOCS_API_BASE}/documents/{document_id}",
                    headers=headers,
                    params={"fields": "body(content(elements),body(sectionBreaks),body(paragraphs),body.lists)"}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract plain text content
                content = self.extract_text_from_document(data.get("body", {}))
                
                return {
                    "success": True,
                    "data": {
                        "documentId": data.get("documentId"),
                        "title": data.get("title"),
                        "content": content,
                        "rawData": data.get("body", {})
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_document_content(self, document_id: str, content: str) -> Dict[str, Any]:
        """Update the content of a Google Doc"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create requests to update content
            requests = []
            
            # Split content into chunks (max 1000 characters per text element)
            for i in range(0, len(content), 1000):
                chunk = content[i:i+1000]
                requests.append({
                    "insertText": {
                        "location": {
                            "index": i
                        },
                        "text": chunk
                    }
                })
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_DOCS_API_BASE}/documents/{document_id}:batchUpdate",
                    headers=headers,
                    json={
                        "requests": requests
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Log activity
                await self.log_activity("update_document", {
                    "document_id": document_id,
                    "content_length": len(content),
                    "requests_count": len(requests)
                })
                
                return {
                    "success": True,
                    "data": {
                        "documentId": document_id,
                        "replies": data.get("replies", [])
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to update document content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_documents(self, query: str, search_scope: str = "all") -> Dict[str, Any]:
        """Search Google Docs documents"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build search query
            search_query = "mimeType='application/vnd.google-apps.document'"
            
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
                documents = []
                
                for file in data.get("files", []):
                    documents.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": "document",
                        "mimeType": file.get("mimeType"),
                        "created": file.get("createdTime"),
                        "modified": file.get("modifiedTime"),
                        "webViewLink": file.get("webViewLink"),
                        "owner": file.get("owners", [{}])[0].get("displayName", "Unknown"),
                        "thumbnail": file.get("thumbnailLink"),
                        "size": file.get("size", "0"),
                        "snippet": self.get_document_snippet(file.get("id"))
                    })
                
                # Log search activity
                await self.log_activity("search_documents", {
                    "query": query,
                    "scope": search_scope,
                    "results_count": len(documents)
                })
                
                return {
                    "success": True,
                    "data": documents,
                    "total": len(documents)
                }
                
        except Exception as e:
            logger.error(f"Failed to search Google Docs: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_document_permissions(self, document_id: str) -> Dict[str, Any]:
        """Get sharing permissions for a document"""
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
                    f"{GOOGLE_DRIVE_API_BASE}/files/{document_id}/permissions",
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
            logger.error(f"Failed to get document permissions: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def share_document(self, document_id: str, email_addresses: List[str], role: str = "reader") -> Dict[str, Any]:
        """Share a document with specified users"""
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
                        f"{GOOGLE_DRIVE_API_BASE}/files/{document_id}/permissions",
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
            await self.log_activity("share_document", {
                "document_id": document_id,
                "email_addresses": email_addresses,
                "role": role
            })
            
            return {
                "success": True,
                "data": results
            }
            
        except Exception as e:
            logger.error(f"Failed to share document: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete a Google Doc"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{document_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("delete_document", {
                    "document_id": document_id
                })
                
                return {
                    "success": True,
                    "message": "Document deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_document_revision_history(self, document_id: str, page_size: int = 10) -> Dict[str, Any]:
        """Get revision history for a document"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size,
                "fields": "revisions(id,modifiedTime,lastModifyingUser,authorDisplayName,size,kind)"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{document_id}/revisions",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                revisions = data.get("revisions", [])
                
                return {
                    "success": True,
                    "data": revisions,
                    "total": len(revisions)
                }
                
        except Exception as e:
            logger.error(f"Failed to get revision history: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def extract_text_from_document(self, body: Dict[str, Any]) -> str:
        """Extract plain text from Google Docs structure"""
        try:
            content = body.get("content", [])
            text_parts = []
            
            for element in content:
                if "paragraph" in element:
                    paragraph = element["paragraph"]
                    for p_element in paragraph.get("elements", []):
                        if "textRun" in p_element:
                            text_parts.append(p_element["textRun"].get("content", ""))
                        elif "pageBreak" in p_element:
                            text_parts.append("\n--- Page Break ---\n")
                elif "table" in element:
                    # Handle tables
                    table = element["table"]
                    text_parts.append(self.extract_text_from_table(table))
                elif "sectionBreak" in element:
                    text_parts.append("\n--- Section Break ---\n")
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract text from document: {e}")
            return ""
    
    def extract_text_from_table(self, table: Dict[str, Any]) -> str:
        """Extract text from table structure"""
        try:
            rows = table.get("tableRows", [])
            table_text = []
            
            for row in rows:
                cells = row.get("tableCells", [])
                row_text = []
                
                for cell in cells:
                    cell_content = self.extract_text_from_document(cell.get("content", []))
                    row_text.append(cell_content.strip())
                
                table_text.append(" | ".join(row_text))
            
            return "\n".join(table_text)
            
        except Exception as e:
            logger.error(f"Failed to extract text from table: {e}")
            return ""
    
    async def get_document_snippet(self, document_id: str) -> str:
        """Get a snippet of document content for preview"""
        try:
            content_result = await self.get_document_content(document_id)
            if content_result["success"]:
                content = content_result["data"]["content"]
                return content[:200] + "..." if len(content) > 200 else content
            return ""
        except Exception as e:
            logger.error(f"Failed to get document snippet: {e}")
            return ""
    
    async def cache_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Cache Google Docs data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_docs_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        document_id VARCHAR(255) NOT NULL,
                        document_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, document_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_docs_user_id ON google_docs_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_docs_document_id ON google_docs_cache(document_id);
                """)
                
                # Update cache
                for doc in documents:
                    await conn.execute("""
                        INSERT INTO google_docs_cache 
                        (user_id, document_id, document_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, document_id)
                        DO UPDATE SET 
                            document_data = EXCLUDED.document_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, doc["id"], json.dumps(doc))
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Google Docs: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Google Docs activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_docs_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_docs_activity_user_id ON google_docs_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_docs_activity_action ON google_docs_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO google_docs_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Google Docs activity: {e}")
            return False