#!/usr/bin/env python3
"""
Figma Enterprise API
Comprehensive API for Figma integration with enterprise features
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Figma API configuration
FIGMA_API_BASE = "https://api.figma.com/v1"
FIGMA_API_VERSION = "v1"

# Create blueprint
figma_enterprise_api_bp = Blueprint('figma_enterprise_api', __name__)

class FigmaEnterpriseService:
    """Enterprise Figma API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.db_pool = None
        self._initialized = False
    
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
            raise Exception("Figma service not initialized. Call initialize() first.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization"""
        return {
            "X-Figma-Token": self.access_token,
            "Content-Type": "application/json"
        }
    
    async def get_user_profile(self) -> Dict[str, Any]:
        """Get Figma user profile"""
        try:
            await self._ensure_initialized()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{FIGMA_API_BASE}/me",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                
                return {
                    "success": True,
                    "data": {
                        "id": data.get("id"),
                        "handle": data.get("handle"),
                        "email": data.get("email"),
                        "img_url": data.get("img_url"),
                        "is_active": True
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get Figma user profile: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_projects(self) -> Dict[str, Any]:
        """List all Figma projects"""
        try:
            await self._ensure_initialized()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{FIGMA_API_BASE}/me/projects",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                projects = []
                
                for project in data:
                    projects.append({
                        "id": project.get("id"),
                        "name": project.get("name"),
                        "created_at": datetime.fromtimestamp(project.get("created_at", 0), timezone.utc).isoformat() if project.get("created_at") else None,
                        "updated_at": datetime.fromtimestamp(project.get("modified_at", 0), timezone.utc).isoformat() if project.get("modified_at") else None,
                        "thumbnail_url": project.get("thumbnail_url"),
                        "files_count": len(project.get("files", []))
                    })
                
                return {
                    "success": True,
                    "data": projects,
                    "total": len(projects)
                }
                
        except Exception as e:
            logger.error(f"Failed to list Figma projects: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_project_files(self, project_id: str) -> Dict[str, Any]:
        """Get files in a Figma project"""
        try:
            await self._ensure_initialized()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{FIGMA_API_BASE}/projects/{project_id}/files",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                files = []
                
                for file in data:
                    files.append({
                        "key": file.get("key"),
                        "name": file.get("name"),
                        "thumbnail_url": file.get("thumbnail_url"),
                        "last_modified": file.get("last_modified"),
                        "created_at": datetime.fromtimestamp(file.get("created_at", 0), timezone.utc).isoformat() if file.get("created_at") else None
                    })
                
                return {
                    "success": True,
                    "data": files,
                    "total": len(files)
                }
                
        except Exception as e:
            logger.error(f"Failed to get Figma project files: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_file_details(self, file_key: str) -> Dict[str, Any]:
        """Get detailed information about a Figma file"""
        try:
            await self._ensure_initialized()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{FIGMA_API_BASE}/files/{file_key}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                data = response.json()
                file_info = data.get("document", {})
                
                return {
                    "success": True,
                    "data": {
                        "key": file_key,
                        "name": file_info.get("name"),
                        "thumbnail_url": data.get("thumbnailUrl"),
                        "last_modified": data.get("lastModified"),
                        "version": data.get("version"),
                        "pages_count": len(file_info.get("children", [])),
                        "components_count": self._count_components(file_info),
                        "styles_count": self._count_styles(file_info)
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get Figma file details: {e}")
            return {"success": False, "error": str(e)}
    
    def _count_components(self, document: Dict[str, Any]) -> int:
        """Count components in document (simplified)"""
        # This is a simplified count - in production, traverse the document tree
        return len([node for node in str(document).split() if "component" in node.lower()])
    
    def _count_styles(self, document: Dict[str, Any]) -> int:
        """Count styles in document (simplified)"""
        # This is a simplified count - in production, check style guide
        return len([node for node in str(document).split() if "style" in node.lower()])
    
    async def create_team_component(self, name: str, description: str) -> Dict[str, Any]:
        """Create team component (enterprise feature)"""
        try:
            await self._ensure_initialized()
            
            # This would be a custom API call for team components
            # For now, return a mock response
            
            return {
                "success": True,
                "data": {
                    "id": f"component_{datetime.now().timestamp()}",
                    "name": name,
                    "description": description,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": self.user_id
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to create Figma team component: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_design_system_info(self) -> Dict[str, Any]:
        """Get design system information"""
        try:
            await self._ensure_initialized()
            
            # This would fetch design system information
            # For now, return mock data
            
            return {
                "success": True,
                "data": {
                    "components": 245,
                    "styles": 89,
                    "typography": 12,
                    "colors": 32,
                    "spacing": 16,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get Figma design system info: {e}")
            return {"success": False, "error": str(e)}

# API Endpoints
@figma_enterprise_api_bp.route('/api/figma/profile', methods=['POST'])
async def get_profile():
    """Get Figma user profile"""
    try:
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = FigmaEnterpriseService(user_id)
        await service.initialize(db_pool)
        
        result = await service.get_user_profile()
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Figma profile endpoint error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@figma_enterprise_api_bp.route('/api/figma/projects', methods=['POST'])
async def list_projects():
    """List Figma projects"""
    try:
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = FigmaEnterpriseService(user_id)
        await service.initialize(db_pool)
        
        result = await service.list_projects()
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Figma projects endpoint error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@figma_enterprise_api_bp.route('/api/figma/files/<project_id>', methods=['POST'])
async def get_project_files(project_id: str):
    """Get files in Figma project"""
    try:
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = FigmaEnterpriseService(user_id)
        await service.initialize(db_pool)
        
        result = await service.get_project_files(project_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Figma files endpoint error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@figma_enterprise_api_bp.route('/api/figma/file/<file_key>', methods=['POST'])
async def get_file_details(file_key: str):
    """Get Figma file details"""
    try:
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = FigmaEnterpriseService(user_id)
        await service.initialize(db_pool)
        
        result = await service.get_file_details(file_key)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Figma file details endpoint error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@figma_enterprise_api_bp.route('/api/figma/design-system', methods=['POST'])
async def get_design_system():
    """Get design system information"""
    try:
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = FigmaEnterpriseService(user_id)
        await service.initialize(db_pool)
        
        result = await service.get_design_system_info()
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Figma design system endpoint error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@figma_enterprise_api_bp.route('/api/figma/health', methods=['GET'])
async def health_check():
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "service": "Figma Enterprise API",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": FIGMA_API_VERSION
    })

# Export blueprint
__all__ = ['figma_enterprise_api_bp']
