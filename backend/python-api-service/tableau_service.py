import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Tableau API configuration
TABLEAU_API_BASE = "https://api.tableau.com/api/3.20"
TABLEAU_AUTH_URL = "https://tableau.mathworks.com/api/2.0"

class TableauService:
    """Comprehensive Tableau API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.site_id = None
        self.user_content_url = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Tableau service with database pool"""
        try:
            from db_oauth_tableau import get_user_tableau_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_tableau_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self.site_id = tokens.get("site_id")
                self.user_content_url = tokens.get("user_content_url")
                self._initialized = True
                logger.info(f"Tableau service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Tableau tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Tableau service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Tableau service not initialized. Call initialize() first.")
    
    async def get_workbooks(self, page_size: int = 100, page_number: int = 1) -> Dict[str, Any]:
        """Get Tableau workbooks"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size,
                "pageNumber": page_number,
                "includeUsage": True,
                "includePermissions": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/workbooks",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                workbooks = []
                
                for workbook in data.get("workbooks", {}).get("workbook", []):
                    workbooks.append({
                        "id": workbook.get("id"),
                        "name": workbook.get("name"),
                        "description": workbook.get("description"),
                        "contentUrl": workbook.get("contentUrl"),
                        "showTabs": workbook.get("showTabs", False),
                        "size": workbook.get("size"),
                        "createdAt": workbook.get("createdAt"),
                        "updatedAt": workbook.get("updatedAt"),
                        "owner": workbook.get("owner", {}).get("displayName", "Unknown"),
                        "ownerId": workbook.get("owner", {}).get("id", ""),
                        "project": workbook.get("project", {}).get("name", "Unknown"),
                        "projectId": workbook.get("project", {}).get("id", ""),
                        "views": workbook.get("views", {}).get("view", []),
                        "permissions": workbook.get("permissions", {}).get("permission", []),
                        "usage": workbook.get("usage", {}),
                        "viewCount": len(workbook.get("views", {}).get("view", [])),
                        "hasPermissions": bool(workbook.get("permissions", {}).get("permission", [])),
                        "isEmbedded": workbook.get("embedded", False),
                        "sheetCount": self._calculate_sheet_count(workbook),
                        "tag": workbook.get("tag", "")
                    })
                
                # Cache workbooks
                await self.cache_workbooks(workbooks)
                
                return {
                    "success": True,
                    "data": workbooks,
                    "pagination": data.get("workbooks", {}).get("pagination", {}),
                    "total": len(workbooks)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau workbooks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_workbook_details(self, workbook_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific workbook"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "includeUsage": True,
                "includePermissions": True,
                "includeTags": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/workbooks/{workbook_id}",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                workbook = data.get("workbook", {})
                
                return {
                    "success": True,
                    "data": {
                        "id": workbook.get("id"),
                        "name": workbook.get("name"),
                        "description": workbook.get("description"),
                        "contentUrl": workbook.get("contentUrl"),
                        "showTabs": workbook.get("showTabs", False),
                        "size": workbook.get("size"),
                        "createdAt": workbook.get("createdAt"),
                        "updatedAt": workbook.get("updatedAt"),
                        "owner": workbook.get("owner", {}),
                        "project": workbook.get("project", {}),
                        "views": workbook.get("views", {}),
                        "permissions": workbook.get("permissions", {}),
                        "usage": workbook.get("usage", {}),
                        "tags": workbook.get("tags", {}),
                        "sheets": workbook.get("sheets", {}),
                        "dataSources": workbook.get("dataSources", {})
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get workbook details: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_workbook_views(self, workbook_id: str, page_size: int = 100) -> Dict[str, Any]:
        """Get all views in a workbook"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size,
                "includeUsage": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/workbooks/{workbook_id}/views",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                views = []
                
                for view in data.get("views", {}).get("view", []):
                    views.append({
                        "id": view.get("id"),
                        "name": view.get("name"),
                        "description": view.get("description"),
                        "contentUrl": view.get("contentUrl"),
                        "viewUrl": view.get("viewUrl"),
                        "createdAt": view.get("createdAt"),
                        "updatedAt": view.get("updatedAt"),
                        "owner": view.get("owner", {}).get("displayName", "Unknown"),
                        "ownerId": view.get("owner", {}).get("id", ""),
                        "workbookId": view.get("workbook", {}).get("id", ""),
                        "workbookName": view.get("workbook", {}).get("name", ""),
                        "sheetId": view.get("sheet", {}).get("id", ""),
                        "sheetName": view.get("sheet", {}).get("name", ""),
                        "usage": view.get("usage", {}),
                        "views": view.get("views", {}),
                        "isHidden": view.get("hidden", False),
                        "previewImage": view.get("previewImage", ""),
                        "tags": view.get("tags", {})
                    })
                
                return {
                    "success": True,
                    "data": views,
                    "total": len(views)
                }
                
        except Exception as e:
            logger.error(f"Failed to get workbook views: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_workbook_data(self, workbook_id: str, view_id: str = None) -> Dict[str, Any]:
        """Get data from a workbook/view"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Get workbook data using CSV API
            if view_id:
                data_url = f"{self.user_content_url}/views/{view_id}/data.csv"
            else:
                data_url = f"{self.user_content_url}/workbooks/{workbook_id}/views/all/data.csv"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    data_url,
                    headers=headers
                )
                response.raise_for_status()
                
                # Parse CSV data
                csv_data = response.text
                data_rows = []
                lines = csv_data.split('\n')
                
                if lines:
                    headers = [h.strip('"') for h in lines[0].split(',')]
                    for line in lines[1:]:
                        if line.strip():
                            values = [v.strip('"') for v in line.split(',')]
                            if len(values) == len(headers):
                                data_rows.append(dict(zip(headers, values)))
                
                return {
                    "success": True,
                    "data": {
                        "headers": headers,
                        "rows": data_rows,
                        "totalRows": len(data_rows),
                        "totalColumns": len(headers)
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get workbook data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_projects(self, page_size: int = 100) -> Dict[str, Any]:
        """Get Tableau projects"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size,
                "includeUsage": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/projects",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                projects = []
                
                for project in data.get("projects", {}).get("project", []):
                    projects.append({
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "description": project.get("description"),
                        "contentUrl": project.get("contentUrl"),
                        "createdAt": project.get("createdAt"),
                        "updatedAt": project.get("updatedAt"),
                        "owner": project.get("owner", {}).get("displayName", "Unknown"),
                        "ownerId": project.get("owner", {}).get("id", ""),
                        "parentProjectId": project.get("parentProjectId"),
                        "permissions": project.get("permissions", {}).get("permission", []),
                        "workbookCount": project.get("workbookCount", 0),
                        "usage": project.get("usage", {}),
                        "hasPermissions": bool(project.get("permissions", {}).get("permission", [])),
                        "isHidden": project.get("hidden", False)
                    })
                
                return {
                    "success": True,
                    "data": projects,
                    "total": len(projects)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau projects: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_data_sources(self, page_size: int = 100) -> Dict[str, Any]:
        """Get Tableau data sources"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size,
                "includeUsage": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/datasources",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                data_sources = []
                
                for ds in data.get("datasources", {}).get("datasource", []):
                    data_sources.append({
                        "id": ds.get("id"),
                        "name": ds.get("name"),
                        "description": ds.get("description"),
                        "contentUrl": ds.get("contentUrl"),
                        "type": ds.get("type"),
                        "createdAt": ds.get("createdAt"),
                        "updatedAt": ds.get("updatedAt"),
                        "owner": ds.get("owner", {}).get("displayName", "Unknown"),
                        "ownerId": ds.get("owner", {}).get("id", ""),
                        "project": ds.get("project", {}).get("name", "Unknown"),
                        "projectId": ds.get("project", {}).get("id", ""),
                        "connections": ds.get("connections", {}).get("connection", []),
                        "usage": ds.get("usage", {}),
                        "isActive": ds.get("isActive", False),
                        "isCertified": ds.get("isCertified", False),
                        "hasExtracts": bool(ds.get("connections", {}).get("connection", [])),
                        "connectionCount": len(ds.get("connections", {}).get("connection", []))
                    })
                
                return {
                    "success": True,
                    "data": data_sources,
                    "total": len(data_sources)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau data sources: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_users(self, page_size: int = 100) -> Dict[str, Any]:
        """Get Tableau users"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/users",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                users = []
                
                for user in data.get("users", {}).get("user", []):
                    users.append({
                        "id": user.get("id"),
                        "name": user.get("name"),
                        "email": user.get("email"),
                        "displayName": user.get("displayName", user.get("name")),
                        "role": user.get("role"),
                        "siteRole": user.get("siteRole"),
                        "authSetting": user.get("authSetting"),
                        "locale": user.get("locale"),
                        "timeZone": user.get("timeZone"),
                        "workbooks": user.get("workbooks", {}).get("workbook", []),
                        "workbookCount": len(user.get("workbooks", {}).get("workbook", [])),
                        "lastLogin": user.get("lastLogin"),
                        "externalAuthUserId": user.get("externalAuthUserId"),
                        "isActive": user.get("authSetting") != "local" or user.get("authSetting") != "saml",
                        "isAdmin": user.get("siteRole") in ["Creator", "SiteAdministratorCreator"],
                        "isExplorer": user.get("siteRole") in ["Explorer", "ExplorerCanPublish", "SiteAdministratorExplorer"]
                    })
                
                return {
                    "success": True,
                    "data": users,
                    "total": len(users)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Tableau users: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_workbooks(self, query: str, page_size: int = 50) -> Dict[str, Any]:
        """Search Tableau workbooks"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "pageSize": page_size,
                "filter": f"(name:eq:{query}),(description:eq:{query}),(tag:eq:{query})"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/workbooks",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                workbooks = []
                
                for workbook in data.get("workbooks", {}).get("workbook", []):
                    workbooks.append({
                        "id": workbook.get("id"),
                        "name": workbook.get("name"),
                        "description": workbook.get("description"),
                        "contentUrl": workbook.get("contentUrl"),
                        "owner": workbook.get("owner", {}).get("displayName", "Unknown"),
                        "project": workbook.get("project", {}).get("name", "Unknown"),
                        "tag": workbook.get("tag", ""),
                        "relevance": self._calculate_relevance(query, workbook)
                    })
                
                # Sort by relevance
                workbooks.sort(key=lambda x: x["relevance"], reverse=True)
                
                # Log search activity
                await self.log_activity("search_workbooks", {
                    "query": query,
                    "results_count": len(workbooks)
                })
                
                return {
                    "success": True,
                    "data": workbooks,
                    "total": len(workbooks)
                }
                
        except Exception as e:
            logger.error(f"Failed to search Tableau workbooks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_embed_code(self, workbook_id: str, view_id: str = None, 
                          width: int = 800, height: int = 600) -> Dict[str, Any]:
        """Get embed code for workbook/view"""
        try:
            await self._ensure_initialized()
            
            if view_id:
                embed_url = f"{self.user_content_url}/views/{view_id}"
            else:
                embed_url = f"{self.user_content_url}/views/{workbook_id}"
            
            embed_code = f'''
            <iframe 
                src="{embed_url}?:embed=yes"
                width="{width}" 
                height="{height}" 
                frameborder="0">
            </iframe>
            '''
            
            return {
                "success": True,
                "data": {
                    "embedCode": embed_code,
                    "embedUrl": embed_url,
                    "width": width,
                    "height": height
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get embed code: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_usage_metrics(self, workbook_id: str = None, days: int = 30) -> Dict[str, Any]:
        """Get usage metrics for workbooks"""
        try:
            await self._ensure_initialized()
            
            if workbook_id:
                # Get metrics for specific workbook
                workbook_details = await self.get_workbook_details(workbook_id)
                if not workbook_details["success"]:
                    return workbook_details
                
                workbook = workbook_details["data"]
                usage = workbook.get("usage", {})
                
                return {
                    "success": True,
                    "data": {
                        "workbookId": workbook_id,
                        "viewCount": usage.get("totalViewCount", 0),
                        "uniqueViewerCount": usage.get("uniqueViewers", 0),
                        "averageViewTime": usage.get("averageViewTime", 0),
                        "lastAccessed": usage.get("lastAccessedTime"),
                        "mostViewedSheet": usage.get("mostViewedSheet"),
                        "trendingViews": usage.get("trendingViews", [])
                    }
                }
            else:
                # Get metrics for all workbooks
                workbooks_result = await self.get_workbooks()
                if not workbooks_result["success"]:
                    return workbooks_result
                
                workbooks = workbooks_result["data"]
                total_views = 0
                total_unique_viewers = 0
                top_workbooks = []
                
                for workbook in workbooks:
                    usage = workbook.get("usage", {})
                    view_count = usage.get("totalViewCount", 0)
                    total_views += view_count
                    total_unique_viewers += usage.get("uniqueViewers", 0)
                    
                    top_workbooks.append({
                        "workbookId": workbook["id"],
                        "workbookName": workbook["name"],
                        "viewCount": view_count,
                        "owner": workbook["owner"]
                    })
                
                # Sort by view count
                top_workbooks.sort(key=lambda x: x["viewCount"], reverse=True)
                
                return {
                    "success": True,
                    "data": {
                        "totalViews": total_views,
                        "totalUniqueViewers": total_unique_viewers,
                        "topWorkbooks": top_workbooks[:10],
                        "workbookCount": len(workbooks),
                        "dateRange": f"Last {days} days"
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get usage metrics: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_project(self, name: str, description: str = None, 
                           parent_project_id: str = None) -> Dict[str, Any]:
        """Create a new Tableau project"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            project_data = {
                "project": {
                    "name": name,
                    "description": description or ""
                }
            }
            
            if parent_project_id:
                project_data["project"]["parentProjectId"] = parent_project_id
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/projects",
                    headers=headers,
                    json=project_data
                )
                response.raise_for_status()
                
                data = response.json()
                project = data.get("project", {})
                
                # Log activity
                await self.log_activity("create_project", {
                    "project_id": project.get("id"),
                    "name": name,
                    "description": description,
                    "parent_project_id": parent_project_id
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "description": project.get("description"),
                        "createdAt": project.get("createdAt")
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def refresh_extract(self, datasource_id: str) -> Dict[str, Any]:
        """Refresh a data source extract"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{TABLEAU_API_BASE}/sites/{self.site_id}/datasources/{datasource_id}/refresh",
                    headers=headers
                )
                response.raise_for_status()
                
                # Log activity
                await self.log_activity("refresh_extract", {
                    "datasource_id": datasource_id
                })
                
                return {
                    "success": True,
                    "message": "Extract refresh initiated successfully"
                }
                
        except Exception as e:
            logger.error(f"Failed to refresh extract: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_sheet_count(self, workbook: Dict[str, Any]) -> int:
        """Calculate the number of sheets in a workbook"""
        views = workbook.get("views", {}).get("view", [])
        unique_sheets = set()
        for view in views:
            sheet = view.get("sheet")
            if sheet:
                unique_sheets.add(sheet.get("id"))
        return len(unique_sheets)
    
    def _calculate_relevance(self, query: str, workbook: Dict[str, Any]) -> float:
        """Calculate relevance score for search results"""
        score = 0.0
        query_lower = query.lower()
        
        # Name match
        name = workbook.get("name", "").lower()
        if query_lower in name:
            score += 1.0 if name == query_lower else 0.5
        
        # Description match
        description = workbook.get("description", "").lower()
        if query_lower in description:
            score += 0.3
        
        # Tag match
        tags = workbook.get("tag", "").lower()
        if query_lower in tags:
            score += 0.2
        
        return score
    
    async def cache_workbooks(self, workbooks: List[Dict[str, Any]]) -> bool:
        """Cache Tableau workbook data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tableau_workbooks_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        workbook_id VARCHAR(255) NOT NULL,
                        workbook_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, workbook_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_user_id ON tableau_workbooks_cache(user_id);
                    CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_workbook_id ON tableau_workbooks_cache(workbook_id);
                """)
                
                # Update cache
                for workbook in workbooks:
                    await conn.execute("""
                        INSERT INTO tableau_workbooks_cache 
                        (user_id, workbook_id, workbook_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, workbook_id)
                        DO UPDATE SET 
                            workbook_data = EXCLUDED.workbook_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, self.user_id, workbook["id"], json.dumps(workbook))
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Tableau workbooks: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Tableau activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tableau_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_tableau_activity_user_id ON tableau_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_tableau_activity_action ON tableau_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO tableau_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Tableau activity: {e}")
            return False