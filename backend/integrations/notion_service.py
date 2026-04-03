"""
Notion Service for ATOM Platform
Provides comprehensive Notion integration functionality
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta
import requests
from urllib.parse import urljoin

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class NotionService(IntegrationService):
    """Notion API integration service"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Notion service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with access_token
        """
        super().__init__(tenant_id, config)
        self.access_token = config.get("access_token")
        self.base_url = "https://api.notion.com/v1"
        self.api_version = "2022-06-28"
        self.session = requests.Session()

        if self.access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}',
                'Notion-Version': self.api_version,
                'Content-Type': 'application/json',
                'User-Agent': 'ATOM-Platform/1.0'
            })
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return Notion integration capabilities"""
        return {
            "operations": [
                {"id": "read", "description": "Read pages and databases"},
                {"id": "create", "description": "Create pages and databases"},
                {"id": "update", "description": "Update existing pages"},
                {"id": "delete", "description": "Delete blocks and pages"},
                {"id": "search", "description": "Search workspace content"},
            ],
            "required_params": ["access_token"],
            "optional_params": [],
            "rate_limits": {"requests_per_second": 3},
            "supports_webhooks": False,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Notion service"""
        try:
            # Basic health check - verify service can be initialized
            return {
                "healthy": True,
                "message": "Notion service is healthy",
                "service": "notion",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "service": "notion",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Notion operation with tenant context.

        Args:
            operation: Operation name (e.g., "search", "get_page", "create_page")
            parameters: Operation parameters
            context: Tenant context dict with tenant_id, agent_id, workspace_id

        Returns:
            Dict with success status and result
        """
        # Validate tenant context
        if context and 'tenant_id' in context:
            tenant_id = context.get('tenant_id')
            if tenant_id != self.tenant_id:
                return {
                    "success": False,
                    "error": f"Tenant mismatch: expected {self.tenant_id}, got {tenant_id}",
                }

        try:
            if operation == "search":
                result = self.search(**parameters)
                return {"success": True, "result": result}
            elif operation == "get_page":
                result = self.get_page(**parameters)
                return {"success": True, "result": result}
            elif operation == "create_page":
                result = self.create_page(**parameters)
                return {"success": True, "result": result}
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                }
        except Exception as e:
            logger.error(f"Notion operation {operation} failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation": operation,
            }

    def test_connection(self) -> Dict[str, Any]:
        """Test Notion API connection"""
        try:
            response = self.session.post(f"{self.base_url}/search", json={})
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "message": "Notion connection successful",
                    "authenticated": True,
                    "results_found": len(data.get('results', []))
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Authentication failed: {response.status_code} - {response.text}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"Notion connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def search(self, query: str = "", filter: Dict[str, Any] = None, page_size: int = 50) -> Dict[str, Any]:
        """Search pages and databases"""
        try:
            data = {
                "page_size": page_size
            }
            
            if query:
                data["query"] = query
            
            if filter:
                data["filter"] = filter
            
            response = self.session.post(f"{self.base_url}/search", json=data)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to search: {e}")
            return {"results": [], "has_more": False}
    
    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific page"""
        try:
            response = self.session.get(f"{self.base_url}/pages/{page_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get page {page_id}: {e}")
            return None
    
    def create_page(self, parent: Dict[str, str], properties: Dict[str, Any], 
                   children: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Create a new page"""
        try:
            data = {
                "parent": parent,
                "properties": properties
            }
            
            if children:
                data["children"] = children
            
            response = self.session.post(f"{self.base_url}/pages", json=data)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            return None
    
    def update_page(self, page_id: str, properties: Dict[str, Any],
                  archived: bool = False) -> Optional[Dict[str, Any]]:
        """Update a page"""
        try:
            data = {
                "properties": properties,
                "archived": archived
            }
            
            response = self.session.patch(f"{self.base_url}/pages/{page_id}", json=data)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to update page {page_id}: {e}")
            return None
    
    def get_database(self, database_id: str) -> Optional[Dict[str, Any]]:
        """Get database information"""
        try:
            response = self.session.get(f"{self.base_url}/databases/{database_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get database {database_id}: {e}")
            return None
    
    def query_database(self, database_id: str, filter: Dict[str, Any] = None,
                     sorts: List[Dict[str, Any]] = None, start_cursor: str = None,
                     page_size: int = 100) -> Dict[str, Any]:
        """Query a database"""
        try:
            data = {
                "page_size": page_size
            }
            
            if filter:
                data["filter"] = filter
            if sorts:
                data["sorts"] = sorts
            if start_cursor:
                data["start_cursor"] = start_cursor
            
            response = self.session.post(f"{self.base_url}/databases/{database_id}/query", json=data)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to query database {database_id}: {e}")
            return {"results": [], "has_more": False}
    
    def create_database(self, parent: Dict[str, str], title: str,
                       properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new database"""
        try:
            data = {
                "parent": parent,
                "title": [{"type": "text", "text": {"content": title}}],
                "properties": properties
            }
            
            response = self.session.post(f"{self.base_url}/databases", json=data)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return None
    
    def get_block_children(self, block_id: str, page_size: int = 100) -> Dict[str, Any]:
        """Get block children"""
        try:
            response = self.session.get(
                f"{self.base_url}/blocks/{block_id}/children",
                params={"page_size": page_size}
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get block children for {block_id}: {e}")
            return {"results": [], "has_more": False}
    
    def append_block_children(self, block_id: str, children: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Append block children"""
        try:
            data = {"children": children}
            response = self.session.patch(
                f"{self.base_url}/blocks/{block_id}/children",
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to append block children for {block_id}: {e}")
            return None
    
    def delete_block(self, block_id: str) -> bool:
        """Delete a block (set archived=True)"""
        try:
            data = {"archived": True}
            response = self.session.patch(
                f"{self.base_url}/blocks/{block_id}",
                json=data
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete block {block_id}: {e}")
            return False
    
    def create_text_block(self, text: str, annotations: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a text block"""
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": text},
                    "annotations": annotations or {}
                }]
            }
        }
    
    def create_heading_block(self, text: str, level: int = 1) -> Dict[str, Any]:
        """Create a heading block"""
        heading_type = f"heading_{level}"
        return {
            "object": "block",
            "type": heading_type,
            heading_type: {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": text}
                }]
            }
        }
    
    def create_todo_block(self, text: str, checked: bool = False) -> Dict[str, Any]:
        """Create a to-do block"""
        return {
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": text}
                }],
                "checked": checked
            }
        }
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information"""
        try:
            response = self.session.get(f"{self.base_url}/users/{user_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    def get_me(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        return self.get_user("me")
    
    def format_text_rich_text(self, text: str, bold: bool = False, italic: bool = False,
                            strikethrough: bool = False, underline: bool = False,
                            color: str = "default") -> Dict[str, Any]:
        """Format text with rich text properties"""
        return {
            "type": "text",
            "text": {"content": text},
            "annotations": {
                "bold": bold,
                "italic": italic,
                "strikethrough": strikethrough,
                "underline": underline,
                "color": color
            }
        }
    
    def create_page_in_database(self, database_id: str, properties: Dict[str, Any],
                            title_property: str = "Name", title_value: str = "New Page",
                            content_blocks: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Create a page in a database with title and content"""
        try:
            # Ensure title property exists
            if title_property not in properties:
                properties[title_property] = {
                    "title": [{"type": "text", "text": {"content": title_value}}]
                }
            
            parent = {"type": "database_id", "database_id": database_id}
            return self.create_page(parent, properties, content_blocks)
            
        except Exception as e:
            logger.error(f"Failed to create page in database {database_id}: {e}")
            return None
    
    def search_pages_in_workspace(self, query: str = "") -> List[Dict[str, Any]]:
        """Search for pages in workspace"""
        try:
            filter_obj = {"property": "object", "value": "page"}
            search_result = self.search(query=query, filter=filter_obj)
            return search_result.get("results", [])
            
        except Exception as e:
            logger.error(f"Failed to search pages: {e}")
            return []
    
    def search_databases_in_workspace(self, query: str = "") -> List[Dict[str, Any]]:
        """Search for databases in workspace"""
        try:
            filter_obj = {"property": "object", "value": "database"}
            search_result = self.search(query=query, filter=filter_obj)
            return search_result.get("results", [])
            
        except Exception as e:
            logger.error(f"Failed to search databases: {e}")
            return []

    async def sync_to_postgres_cache(self) -> Dict[str, Any]:
        """Sync Notion analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Search to get counts of pages and databases
            pages = self.search_pages_in_workspace()
            databases = self.search_databases_in_workspace()
            
            page_count = len(pages)
            db_count = len(databases)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("notion_page_count", page_count, "count"),
                    ("notion_database_count", db_count, "count"),
                ]
                
                # Use "me" or workspace identifier if available
                # Notion token is often per-workspace
                workspace_id = "default"
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="notion",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="notion",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Notion metrics to PostgreSQL cache")
            except Exception as e:
                logger.error(f"Error saving Notion metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Notion PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Notion"""
        # Pipeline 1: Atom Memory
        # Triggered via notion_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache()
        
        return {
            "success": True,
            "workspace_id": "default",
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# NOTE: Legacy singleton instance removed - use IntegrationRegistry instead
# from core.integration_registry import IntegrationRegistry
# registry = IntegrationRegistry(db)
# notion_service = await registry.get_service_instance("notion", tenant_id)
