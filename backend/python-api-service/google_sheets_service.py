import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Google Sheets API configuration
GOOGLE_SHEETS_API_BASE = "https://sheets.googleapis.com/v4"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

class GoogleSheetsService:
    """Comprehensive Google Sheets API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Google Sheets service with database pool"""
        try:
            from db_oauth_google_drive import get_user_google_drive_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_google_drive_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self._initialized = True
                logger.info(f"Google Sheets service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Google tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Google Sheets service not initialized. Call initialize() first.")
    
    async def get_spreadsheets(self, query: str = None, page_size: int = 50) -> Dict[str, Any]:
        """Get Google Sheets spreadsheets"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Search for Google Sheets files
            search_query = "mimeType='application/vnd.google-apps.spreadsheet'"
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
                spreadsheets = []
                
                for file in data.get("files", []):
                    # Get spreadsheet details
                    sheet_details = await self.get_spreadsheet_details(file["id"])
                    
                    spreadsheets.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": "spreadsheet",
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
                        "sheets": sheet_details.get("sheets", []),
                        "spreadsheetId": sheet_details.get("spreadsheetId", file.get("id")),
                        "properties": sheet_details.get("properties", {}),
                        "sheetCount": len(sheet_details.get("sheets", [])),
                        "locale": sheet_details.get("properties", {}).get("locale"),
                        "timeZone": sheet_details.get("properties", {}).get("timeZone"),
                        "autoRecalc": sheet_details.get("properties", {}).get("autoRecalc"),
                        "defaultFormat": sheet_details.get("defaultFormat", {})
                    })
                
                # Cache spreadsheets
                await self.cache_spreadsheets(spreadsheets)
                
                return {
                    "success": True,
                    "data": spreadsheets,
                    "total": len(spreadsheets)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Google Sheets: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_spreadsheet_details(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific spreadsheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}",
                    headers=headers,
                    params={"fields": "spreadsheetId,title,sheets(properties,gridProperties,charts),properties,spreadsheetUrl"}
                }
                response.raise_for_status()
                
                data = response.json()
                return data
                
        except Exception as e:
            logger.error(f"Failed to get spreadsheet details: {e}")
            return {}
    
    async def create_spreadsheet(self, title: str, sheets_data: List[Dict[str, Any]] = None, folder_id: str = None) -> Dict[str, Any]:
        """Create a new Google Sheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Create file metadata
            file_metadata = {
                "name": title,
                "mimeType": "application/vnd.google-apps.spreadsheet"
            }
            
            if folder_id:
                file_metadata["parents"] = [folder_id]
            
            async with httpx.AsyncClient() as client:
                # Create spreadsheet
                response = await client.post(
                    f"{GOOGLE_DRIVE_API_BASE}/files",
                    headers=headers,
                    json=file_metadata
                )
                response.raise_for_status()
                
                file_data = response.json()
                spreadsheet_id = file_data.get("id")
                
                # Add sheets if provided
                if sheets_data:
                    await self.add_sheets(spreadsheet_id, sheets_data)
                
                # Log activity
                await self.log_activity("create_spreadsheet", {
                    "spreadsheet_id": spreadsheet_id,
                    "title": title,
                    "sheets_count": len(sheets_data) if sheets_data else 0,
                    "folder_id": folder_id
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": spreadsheet_id,
                        "name": title,
                        "webViewLink": file_data.get("webViewLink"),
                        "created": file_data.get("createdTime")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create Google Sheet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_sheet_data(self, spreadsheet_id: str, sheet_name: str = None, range: str = "A1:Z1000") -> Dict[str, Any]:
        """Get data from a specific sheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build range
            if sheet_name:
                full_range = f"'{sheet_name}'!{range}"
            else:
                full_range = range
            
            params = {
                "ranges": full_range,
                "fields": "spreadsheetId,sheets(data.rowData.values),sheets.data.rowData.values",
                "includeGridData": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}/values:batchGet",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract data from response
                values = []
                if data.get("valueRanges"):
                    values = data["valueRanges"][0].get("values", [])
                
                # Process data into structured format
                processed_data = []
                if values:
                    headers = values[0]
                    for i, row in enumerate(values[1:], 1):
                        if i < len(values):  # Safety check
                            row_data = {}
                            for j, cell in enumerate(row):
                                if j < len(headers):
                                    row_data[headers[j]] = cell
                            if row_data:  # Only add non-empty rows
                                processed_data.append(row_data)
                
                return {
                    "success": True,
                    "data": {
                        "spreadsheetId": spreadsheet_id,
                        "range": full_range,
                        "values": values,
                        "processedData": processed_data,
                        "rowCount": len(values),
                        "columnCount": len(values[0]) if values else 0,
                        "headers": values[0] if values else []
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get sheet data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_sheet_data(self, spreadsheet_id: str, sheet_name: str, data: List[List[Any]], range: str = None) -> Dict[str, Any]:
        """Update data in a specific sheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build range
            if not range:
                range = f"'{sheet_name}'!A1:Z1000"
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}/values/{range}",
                    headers=headers,
                    json={
                        "values": data,
                        "valueInputOption": "USER_ENTERED"
                    }
                )
                response.raise_for_status()
                
                result_data = response.json()
                
                # Log activity
                await self.log_activity("update_sheet_data", {
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": sheet_name,
                    "range": range,
                    "rows_updated": result_data.get("updatedRows", 0),
                    "columns_updated": result_data.get("updatedColumns", 0),
                    "cells_updated": result_data.get("updatedCells", 0)
                })
                
                return {
                    "success": True,
                    "data": result_data
                }
                
        except Exception as e:
            logger.error(f"Failed to update sheet data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def append_sheet_data(self, spreadsheet_id: str, sheet_name: str, data: List[List[Any]], range: str = None) -> Dict[str, Any]:
        """Append data to a specific sheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build range
            if not range:
                range = f"'{sheet_name}'!A:Z"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}/values/{range}:append",
                    headers=headers,
                    json={
                        "values": data,
                        "valueInputOption": "USER_ENTERED"
                    }
                )
                response.raise_for_status()
                
                result_data = response.json()
                
                # Log activity
                await self.log_activity("append_sheet_data", {
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": sheet_name,
                    "range": range,
                    "rows_appended": result_data.get("updates", {}).get("updatedRows", 0)
                })
                
                return {
                    "success": True,
                    "data": result_data
                }
                
        except Exception as e:
            logger.error(f"Failed to append sheet data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def clear_sheet_data(self, spreadsheet_id: str, sheet_name: str, range: str = None) -> Dict[str, Any]:
        """Clear data from a specific sheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build range
            if not range:
                range = f"'{sheet_name}'!A:Z"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}/values/{range}:clear",
                    headers=headers
                )
                response.raise_for_status()
                
                result_data = response.json()
                
                # Log activity
                await self.log_activity("clear_sheet_data", {
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": sheet_name,
                    "range": range
                })
                
                return {
                    "success": True,
                    "data": result_data
                }
                
        except Exception as e:
            logger.error(f"Failed to clear sheet data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def add_sheet(self, spreadsheet_id: str, sheet_properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new sheet to the spreadsheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}:batchUpdate",
                    headers=headers,
                    json={
                        "requests": [
                            {
                                "addSheet": {
                                    "properties": sheet_properties
                                }
                            }
                        ]
                    }
                )
                response.raise_for_status()
                
                result_data = response.json()
                
                # Log activity
                await self.log_activity("add_sheet", {
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_properties": sheet_properties
                })
                
                return {
                    "success": True,
                    "data": result_data.get("replies", [{}])[0]
                }
                
        except Exception as e:
            logger.error(f"Failed to add sheet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def add_sheets(self, spreadsheet_id: str, sheets_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add multiple sheets to the spreadsheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            requests = []
            for sheet_data in sheets_data:
                requests.append({
                    "addSheet": {
                        "properties": sheet_data
                    }
                })
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}:batchUpdate",
                    headers=headers,
                    json={"requests": requests}
                )
                response.raise_for_status()
                
                result_data = response.json()
                
                # Log activity
                await self.log_activity("add_sheets", {
                    "spreadsheet_id": spreadsheet_id,
                    "sheets_count": len(sheets_data)
                })
                
                return {
                    "success": True,
                    "data": result_data.get("replies", [])
                }
                
        except Exception as e:
            logger.error(f"Failed to add sheets: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_sheet(self, spreadsheet_id: str, sheet_id: int) -> Dict[str, Any]:
        """Delete a sheet from the spreadsheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GOOGLE_SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}:batchUpdate",
                    headers=headers,
                    json={
                        "requests": [
                            {
                                "deleteSheet": {
                                    "sheetId": sheet_id
                                }
                            }
                        ]
                    }
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("delete_sheet", {
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_id": sheet_id
                })
                
                return {
                    "success": True,
                    "message": "Sheet deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete sheet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_spreadsheets(self, query: str, search_scope: str = "all") -> Dict[str, Any]:
        """Search Google Sheets spreadsheets"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build search query
            search_query = "mimeType='application/vnd.google-apps.spreadsheet'"
            
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
                spreadsheets = []
                
                for file in data.get("files", []):
                    spreadsheets.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "type": "spreadsheet",
                        "mimeType": file.get("mimeType"),
                        "created": file.get("createdTime"),
                        "modified": file.get("modifiedTime"),
                        "webViewLink": file.get("webViewLink"),
                        "owner": file.get("owners", [{}])[0].get("displayName", "Unknown"),
                        "thumbnail": file.get("thumbnailLink"),
                        "size": file.get("size", "0"),
                        "snippet": self.get_spreadsheet_snippet(file.get("id"))
                    })
                
                # Log search activity
                await self.log_activity("search_spreadsheets", {
                    "query": query,
                    "scope": search_scope,
                    "results_count": len(spreadsheets)
                })
                
                return {
                    "success": True,
                    "data": spreadsheets,
                    "total": len(spreadsheets)
                }
                
        except Exception as e:
            logger.error(f"Failed to search Google Sheets: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_spreadsheet_permissions(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get sharing permissions for a spreadsheet"""
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
                    f"{GOOGLE_DRIVE_API_BASE}/files/{spreadsheet_id}/permissions",
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
            logger.error(f"Failed to get spreadsheet permissions: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def share_spreadsheet(self, spreadsheet_id: str, email_addresses: List[str], role: str = "reader") -> Dict[str, Any]:
        """Share a spreadsheet with specified users"""
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
                        f"{GOOGLE_DRIVE_API_BASE}/files/{spreadsheet_id}/permissions",
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
            await self.log_activity("share_spreadsheet", {
                "spreadsheet_id": spreadsheet_id,
                "email_addresses": email_addresses,
                "role": role
            })
            
            return {
                "success": True,
                "data": results
            }
            
        except Exception as e:
            logger.error(f"Failed to share spreadsheet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Delete a Google Sheet"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{spreadsheet_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("delete_spreadsheet", {
                    "spreadsheet_id": spreadsheet_id
                })
                
                return {
                    "success": True,
                    "message": "Spreadsheet deleted successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to delete spreadsheet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_spreadsheet_snippet(self, spreadsheet_id: str) -> str:
        """Get a snippet of spreadsheet data for preview"""
        try:
            # Get first sheet data preview
            data_result = await self.get_sheet_data(spreadsheet_id, range="A1:E10")
            if data_result["success"]:
                values = data_result["data"]["values"]
                if values:
                    # Return first few cells as snippet
                    snippet = ""
                    for row in values[:3]:  # First 3 rows
                        row_text = "\t".join([str(cell)[:20] for cell in row[:5]])  # First 5 columns
                        snippet += row_text + "\n"
                    return snippet.strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to get spreadsheet snippet: {e}")
            return ""
    
    async def cache_spreadsheets(self, spreadsheets: List[Dict[str, Any]]) -> bool:
        """Cache Google Sheets data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_sheets_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        spreadsheet_id VARCHAR(255) NOT NULL,
                        spreadsheet_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, spreadsheet_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_sheets_user_id ON google_sheets_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_sheets_spreadsheet_id ON google_sheets_cache(spreadsheet_id);
                """)
                
                # Update cache
                for sheet in spreadsheets:
                    await conn.execute("""
                        INSERT INTO google_sheets_cache 
                        (user_id, spreadsheet_id, spreadsheet_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, spreadsheet_id)
                        DO UPDATE SET 
                            spreadsheet_data = EXCLUDED.spreadsheet_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, sheet["id"], json.dumps(sheet))
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Google Sheets: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Google Sheets activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS google_sheets_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_google_sheets_activity_user_id ON google_sheets_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_google_sheets_activity_action ON google_sheets_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO google_sheets_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Google Sheets activity: {e}")
            return False