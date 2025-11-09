#!/usr/bin/env python3
"""
Figma Enterprise Service
Enterprise-grade service for Figma integration
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from asyncpg import Pool

logger = logging.getLogger(__name__)

class FigmaEnterpriseService:
    """Enterprise Figma service with comprehensive features"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self.cache = {}
        self._initialized = False
        self.rate_limit = {
            "requests": 0,
            "window_start": datetime.now(timezone.utc),
            "limit": 120,  # Figma rate limit per hour
            "window_minutes": 60
        }
    
    async def initialize(self, db_pool: Pool):
        """Initialize service with database pool and tokens"""
        try:
            from db_oauth_figma import get_figma_tokens
            
            self.db_pool = db_pool
            tokens = await get_figma_tokens(db_pool, self.user_id)
            
            if tokens and not tokens.get("expired", True):
                self.access_token = tokens.get("access_token")
                self._initialized = True
                logger.info(f"Enterprise Figma service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No valid Figma tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize enterprise Figma service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Figma enterprise service not initialized. Call initialize() first.")
    
    async def _check_rate_limit(self) -> bool:
        """Check and enforce rate limiting"""
        now = datetime.now(timezone.utc)
        window_elapsed = (now - self.rate_limit["window_start"]).seconds
        
        # Reset window if elapsed
        if window_elapsed >= self.rate_limit["window_minutes"] * 60:
            self.rate_limit["requests"] = 0
            self.rate_limit["window_start"] = now
            return True
        
        # Check limit
        if self.rate_limit["requests"] >= self.rate_limit["limit"]:
            logger.warning("Figma API rate limit exceeded")
            return False
        
        self.rate_limit["requests"] += 1
        return True
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization"""
        return {
            "X-Figma-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def get_user_profile(self) -> Dict[str, Any]:
        """Get comprehensive user profile"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            # Check cache first
            cache_key = f"user_profile_{self.user_id}"
            if cache_key in self.cache:
                cache_time = self.cache[cache_key]["timestamp"]
                if datetime.now(timezone.utc) - cache_time < timedelta(minutes=5):
                    return self.cache[cache_key]["data"]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.figma.com/v1/me",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                user_info = {
                    "id": data.get("id"),
                    "email": data.get("email"),
                    "handle": data.get("handle"),
                    "img_url": data.get("img_url"),
                    "team_id": data.get("team_id"),
                    "is_active": True,
                    "last_login": datetime.now(timezone.utc).isoformat()
                }
                
                # Cache result
                self.cache[cache_key] = {
                    "data": {"success": True, "data": user_info},
                    "timestamp": datetime.now(timezone.utc)
                }
                
                return {"success": True, "data": user_info}
                
        except Exception as e:
            logger.error(f"Failed to get Figma user profile: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_projects(self) -> Dict[str, Any]:
        """List all Figma projects with details"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            cache_key = f"projects_{self.user_id}"
            if cache_key in self.cache:
                cache_time = self.cache[cache_key]["timestamp"]
                if datetime.now(timezone.utc) - cache_time < timedelta(minutes=10):
                    return self.cache[cache_key]["data"]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.figma.com/v1/me/projects",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                projects = []
                
                for project in data:
                    project_info = {
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "team_id": project.get("team_id"),
                        "organization_id": project.get("organization_id"),
                        "created_at": datetime.fromtimestamp(project.get("created_at", 0), timezone.utc).isoformat() if project.get("created_at") else None,
                        "updated_at": datetime.fromtimestamp(project.get("modified_at", 0), timezone.utc).isoformat() if project.get("modified_at") else None,
                        "thumbnail_url": project.get("thumbnail_url"),
                        "files_count": len(project.get("files", [])),
                        "is_personal": project.get("team_id") is None
                    }
                    projects.append(project_info)
                
                result = {
                    "success": True,
                    "data": projects,
                    "total": len(projects),
                    "metadata": {
                        "personal_projects": len([p for p in projects if p["is_personal"]]),
                        "team_projects": len([p for p in projects if not p["is_personal"]])
                    }
                }
                
                # Cache result
                self.cache[cache_key] = {
                    "data": result,
                    "timestamp": datetime.now(timezone.utc)
                }
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to list Figma projects: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_project_files(self, project_id: str) -> Dict[str, Any]:
        """Get all files in a project"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.figma.com/v1/projects/{project_id}/files",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                files = []
                
                for file in data:
                    file_info = {
                        "key": file.get("key"),
                        "name": file.get("name"),
                        "thumbnail_url": file.get("thumbnail_url"),
                        "last_modified": file.get("last_modified"),
                        "created_at": datetime.fromtimestamp(file.get("created_at", 0), timezone.utc).isoformat() if file.get("created_at") else None
                    }
                    files.append(file_info)
                
                return {
                    "success": True,
                    "data": files,
                    "total": len(files),
                    "project_id": project_id
                }
                
        except Exception as e:
            logger.error(f"Failed to get Figma project files: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_file_details(self, file_key: str, geometry: str = "paths") -> Dict[str, Any]:
        """Get detailed file information with components and styles"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            params = {"geometry": geometry}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.figma.com/v1/files/{file_key}",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                document = data.get("document", {})
                
                # Analyze components and styles
                components = []
                styles = []
                pages = []
                
                if document.get("children"):
                    for page in document["children"]:
                        page_info = {
                            "id": page.get("id"),
                            "name": page.get("name"),
                            "type": page.get("type"),
                            "frame_count": len([n for n in str(page).split() if "FRAME" in n])  # Simplified count
                        }
                        pages.append(page_info)
                
                file_details = {
                    "key": file_key,
                    "name": document.get("name"),
                    "version": data.get("version"),
                    "last_modified": data.get("lastModified"),
                    "thumbnail_url": data.get("thumbnailUrl"),
                    "pages": pages,
                    "pages_count": len(pages),
                    "components_count": len(components),
                    "styles_count": len(styles),
                    "file_size": len(str(data))  # Approximate size
                }
                
                return {
                    "success": True,
                    "data": file_details
                }
                
        except Exception as e:
            logger.error(f"Failed to get Figma file details: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_files(self, query: str, limit: int = 50) -> Dict[str, Any]:
        """Search for files by name or content"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            # Get all projects first
            projects_result = await self.list_projects()
            if not projects_result.get("success"):
                return projects_result
            
            all_files = []
            for project in projects_result["data"]:
                files_result = await self.get_project_files(project["id"])
                if files_result.get("success"):
                    for file in files_result["data"]:
                        file["project_name"] = project["name"]
                        file["project_id"] = project["id"]
                        all_files.append(file)
            
            # Search through files
            query_lower = query.lower()
            matched_files = []
            
            for file in all_files:
                if (query_lower in file["name"].lower() or 
                    query_lower in file.get("project_name", "").lower()):
                    matched_files.append(file)
            
            # Limit results
            matched_files = matched_files[:limit]
            
            return {
                "success": True,
                "data": matched_files,
                "total_found": len(matched_files),
                "query": query,
                "searched_files": len(all_files)
            }
            
        except Exception as e:
            logger.error(f"Failed to search Figma files: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_team_info(self, team_id: str) -> Dict[str, Any]:
        """Get team information"""
        try:
            await self._ensure_initialized()
            await self._check_rate_limit()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.figma.com/v1/teams/{team_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                team_info = {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "avatar_url": data.get("img_url"),
                    "member_count": len(data.get("members", [])),
                    "project_count": len(data.get("projects", []))
                }
                
                return {
                    "success": True,
                    "data": team_info
                }
                
        except Exception as e:
            logger.error(f"Failed to get Figma team info: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_usage_analytics(self) -> Dict[str, Any]:
        """Get usage analytics for the user"""
        try:
            await self._ensure_initialized()
            
            # Get all projects and files
            projects_result = await self.list_projects()
            if not projects_result.get("success"):
                return projects_result
            
            projects = projects_result["data"]
            total_files = 0
            total_projects = len(projects)
            total_storage = 0
            
            for project in projects:
                files_result = await self.get_project_files(project["id"])
                if files_result.get("success"):
                    total_files += len(files_result["data"])
                    total_storage += len(json.dumps(files_result["data"]))  # Approximate storage
            
            analytics = {
                "total_projects": total_projects,
                "total_files": total_files,
                "estimated_storage_mb": round(total_storage / (1024 * 1024), 2),
                "projects_by_type": {
                    "personal": len([p for p in projects if p["is_personal"]]),
                    "team": len([p for p in projects if not p["is_personal"]])
                },
                "api_usage": {
                    "requests_this_window": self.rate_limit["requests"],
                    "limit": self.rate_limit["limit"],
                    "window_minutes": self.rate_limit["window_minutes"],
                    "reset_time": (self.rate_limit["window_start"] + timedelta(minutes=self.rate_limit["window_minutes"])).isoformat()
                },
                "cached_items": len(self.cache)
            }
            
            return {
                "success": True,
                "data": analytics
            }
            
        except Exception as e:
            logger.error(f"Failed to get Figma usage analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def clear_cache(self):
        """Clear service cache"""
        self.cache.clear()
        logger.info("Cache cleared for Figma enterprise service")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        return {
            "service": "Figma Enterprise",
            "initialized": self._initialized,
            "user_id": self.user_id,
            "cache_size": len(self.cache),
            "rate_limit": self.rate_limit,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Factory function
def create_figma_enterprise_service(user_id: str) -> FigmaEnterpriseService:
    """Create enterprise Figma service instance"""
    return FigmaEnterpriseService(user_id)

# Export service class
__all__ = [
    'FigmaEnterpriseService',
    'create_figma_enterprise_service'
]
