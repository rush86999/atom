"""
Notion Service for ATOM Platform
Provides comprehensive Notion integration functionality
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
import requests

logger = logging.getLogger(__name__)

class NotionService:
    """Notion API integration service"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv('NOTION_ACCESS_TOKEN')
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

# Singleton instance for global access
notion_service = NotionService()

def get_notion_service() -> NotionService:
    """Get Notion service instance"""
    return notion_service