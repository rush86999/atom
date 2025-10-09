# Real Notion service implementation using notion-client
# This provides real implementations for Notion API functionality

import os
import logging
from typing import Dict, Any, Optional, List
from notion_client import Client
from mcp_base import MCPBase

logger = logging.getLogger(__name__)


class RealNotionService(MCPBase):
    def __init__(self, access_token: str):
        """Initialize real Notion client with OAuth access token"""
        self.client = Client(auth=access_token)
        self.is_mock = False

    def list_files(
        self,
        database_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get pages from a Notion database with optional search filtering"""
        try:
            # Query the Notion database
            response = self.client.databases.query(
                database_id=database_id,
                page_size=page_size,
                start_cursor=page_token if page_token else None,
            )

            pages = response.get("results", [])

            # Filter pages based on query if provided
            if query:
                filtered_pages = [
                    page for page in pages if self._page_matches_query(page, query)
                ]
            else:
                filtered_pages = pages

            # Convert pages to dictionary format
            files = []
            for page in filtered_pages:
                page_data = self._extract_page_data(page)
                if page_data:
                    files.append(page_data)

            # Handle pagination
            next_page_token = response.get("next_cursor")
            has_more = response.get("has_more", False)

            return {
                "status": "success",
                "data": {
                    "files": files,
                    "nextPageToken": next_page_token if has_more else None,
                    "total_count": len(files),
                    "has_more": has_more,
                },
            }

        except Exception as e:
            logger.error(f"Error listing Notion pages: {e}")
            return {"status": "error", "message": str(e)}

    def get_file_metadata(self, page_id: str, **kwargs) -> Dict[str, Any]:
        """Get detailed information about a specific Notion page"""
        try:
            # Get page details
            page = self.client.pages.retrieve(page_id=page_id)

            # Get page content (blocks)
            blocks = self.client.blocks.children.list(block_id=page_id)

            # Extract page data
            page_data = self._extract_page_data(page)
            if not page_data:
                return {"status": "error", "message": "Could not extract page data"}

            # Add blocks content
            page_data["blocks"] = self._extract_blocks_data(blocks.get("results", []))

            return {
                "status": "success",
                "data": page_data,
            }

        except Exception as e:
            logger.error(f"Error getting Notion page metadata: {e}")
            return {"status": "error", "message": str(e)}

    def download_file(self, page_id: str, **kwargs) -> Dict[str, Any]:
        """Download page content as markdown text"""
        try:
            # Get page details
            page = self.client.pages.retrieve(page_id=page_id)

            # Get page content (blocks)
            blocks = self.client.blocks.children.list(block_id=page_id)

            # Extract page data
            page_data = self._extract_page_data(page)
            if not page_data:
                return {"status": "error", "message": "Could not extract page data"}

            # Convert blocks to markdown
            markdown_content = self._blocks_to_markdown(blocks.get("results", []))

            return {
                "status": "success",
                "data": {
                    "page_id": page_id,
                    "title": page_data.get("name", "Untitled"),
                    "markdown_content": markdown_content,
                    "url": page_data.get("url", ""),
                    "last_edited": page_data.get("last_edited_time"),
                },
            }

        except Exception as e:
            logger.error(f"Error downloading Notion page: {e}")
            return {"status": "error", "message": str(e)}

    def search_pages(
        self,
        query: str,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Search across all Notion pages"""
        try:
            response = self.client.search(
                query=query,
                page_size=page_size,
                start_cursor=page_token if page_token else None,
            )

            pages = response.get("results", [])

            # Convert pages to dictionary format
            files = []
            for page in pages:
                page_data = self._extract_page_data(page)
                if page_data:
                    files.append(page_data)

            # Handle pagination
            next_page_token = response.get("next_cursor")
            has_more = response.get("has_more", False)

            return {
                "status": "success",
                "data": {
                    "files": files,
                    "nextPageToken": next_page_token if has_more else None,
                    "total_count": len(files),
                    "has_more": has_more,
                },
            }

        except Exception as e:
            logger.error(f"Error searching Notion pages: {e}")
            return {"status": "error", "message": str(e)}

    def get_service_status(self) -> Dict[str, Any]:
        """Get service status information"""
        try:
            # Test connectivity by searching for a simple query
            response = self.client.search(query="test", page_size=1)

            return {
                "status": "connected",
                "message": "Notion service connected successfully",
                "available": True,
                "mock_data": False,
                "user": "Notion User",  # Notion API doesn't provide user info in search
            }

        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"Notion service connection failed: {str(e)}",
                "available": False,
                "mock_data": False,
            }

    def _page_matches_query(self, page: Dict[str, Any], query: str) -> bool:
        """Check if a page matches the search query"""
        query_lower = query.lower()

        # Check page properties
        properties = page.get("properties", {})
        for prop_name, prop_value in properties.items():
            if self._property_contains_query(prop_value, query_lower):
                return True

        # Check page title (if available)
        title_property = self._get_page_title(page)
        if title_property and query_lower in title_property.lower():
            return True

        return False

    def _property_contains_query(self, prop_value: Dict[str, Any], query: str) -> bool:
        """Check if a property contains the query text"""
        if not prop_value:
            return False

        # Handle different property types
        prop_type = prop_value.get("type")
        if prop_type == "title":
            title_text = self._extract_rich_text(prop_value.get("title", []))
            return query in title_text.lower()
        elif prop_type == "rich_text":
            rich_text = self._extract_rich_text(prop_value.get("rich_text", []))
            return query in rich_text.lower()
        elif prop_type == "text":
            text_content = prop_value.get("text", "")
            return query in text_content.lower()
        elif prop_type == "select":
            select_value = prop_value.get("select", {})
            select_name = select_value.get("name", "")
            return query in select_name.lower()

        return False

    def _extract_page_data(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract relevant data from a Notion page"""
        try:
            page_id = page.get("id")
            if not page_id:
                return None

            # Get page title
            title = self._get_page_title(page)

            # Get page URL
            url = page.get("url", "")

            # Get last edited time
            last_edited_time = page.get("last_edited_time")

            # Get created time
            created_time = page.get("created_time")

            # Get properties
            properties = page.get("properties", {})

            return {
                "id": page_id,
                "name": title or "Untitled",
                "description": f"Notion page: {title or 'Untitled'}",
                "url": url,
                "last_edited_time": last_edited_time,
                "created_time": created_time,
                "properties": self._simplify_properties(properties),
                "object_type": page.get("object", "page"),
            }

        except Exception as e:
            logger.error(f"Error extracting page data: {e}")
            return None

    def _get_page_title(self, page: Dict[str, Any]) -> str:
        """Extract title from Notion page properties"""
        properties = page.get("properties", {})

        # Look for title property
        for prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_text = self._extract_rich_text(prop_value.get("title", []))
                return title_text

        # Fallback: check if there's a Name property
        name_prop = properties.get("Name") or properties.get("name")
        if name_prop and name_prop.get("type") == "title":
            name_text = self._extract_rich_text(name_prop.get("title", []))
            return name_text

        return "Untitled"

    def _extract_rich_text(self, rich_text_array: List[Dict[str, Any]]) -> str:
        """Extract plain text from rich text array"""
        text_parts = []
        for text_item in rich_text_array:
            if text_item.get("type") == "text":
                text_content = text_item.get("text", {})
                text_parts.append(text_content.get("content", ""))

        return "".join(text_parts)

    def _simplify_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Simplify Notion properties for API response"""
        simplified = {}

        for prop_name, prop_value in properties.items():
            prop_type = prop_value.get("type")

            if prop_type == "title":
                simplified[prop_name] = self._extract_rich_text(
                    prop_value.get("title", [])
                )
            elif prop_type == "rich_text":
                simplified[prop_name] = self._extract_rich_text(
                    prop_value.get("rich_text", [])
                )
            elif prop_type == "text":
                simplified[prop_name] = prop_value.get("text", "")
            elif prop_type == "select":
                select_value = prop_value.get("select", {})
                simplified[prop_name] = select_value.get("name", "")
            elif prop_type == "multi_select":
                multi_select = prop_value.get("multi_select", [])
                simplified[prop_name] = [item.get("name", "") for item in multi_select]
            elif prop_type == "date":
                date_value = prop_value.get("date", {})
                simplified[prop_name] = date_value
            elif prop_type == "checkbox":
                simplified[prop_name] = prop_value.get("checkbox", False)
            elif prop_type == "number":
                simplified[prop_name] = prop_value.get("number")
            else:
                simplified[prop_name] = f"{prop_type} property"

        return simplified

    def _extract_blocks_data(
        self, blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract data from Notion blocks"""
        blocks_data = []

        for block in blocks:
            block_type = block.get("type")
            block_id = block.get("id")

            if not block_type:
                continue

            block_data = {
                "id": block_id,
                "type": block_type,
                "has_children": block.get("has_children", False),
            }

            # Extract content based on block type
            type_data = block.get(block_type, {})
            if block_type == "paragraph":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
            elif block_type == "heading_1":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
                block_data["level"] = 1
            elif block_type == "heading_2":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
                block_data["level"] = 2
            elif block_type == "heading_3":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
                block_data["level"] = 3
            elif block_type == "bulleted_list_item":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
            elif block_type == "numbered_list_item":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
            elif block_type == "to_do":
                block_data["text"] = self._extract_rich_text(
                    type_data.get("rich_text", [])
                )
                block_data["checked"] = type_data.get("checked", False)
            elif block_type == "code":
                block_data["text"] = (
                    type_data.get("rich_text", [{}])[0]
                    .get("text", {})
                    .get("content", "")
                )
                block_data["language"] = type_data.get("language", "")

            blocks_data.append(block_data)

        return blocks_data

    def _blocks_to_markdown(self, blocks: List[Dict[str, Any]]) -> str:
        """Convert Notion blocks to markdown format"""
        markdown_lines = []

        for block in blocks:
            block_type = block.get("type")
            type_data = block.get(block_type, {})

            if block_type == "paragraph":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                if text.strip():
                    markdown_lines.append(text)
            elif block_type == "heading_1":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                markdown_lines.append(f"# {text}")
            elif block_type == "heading_2":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                markdown_lines.append(f"## {text}")
            elif block_type == "heading_3":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                markdown_lines.append(f"### {text}")
            elif block_type == "bulleted_list_item":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                markdown_lines.append(f"- {text}")
            elif block_type == "numbered_list_item":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                markdown_lines.append(f"1. {text}")
            elif block_type == "to_do":
                text = self._extract_rich_text(type_data.get("rich_text", []))
                checked = type_data.get("checked", False)
                checkbox = "[x]" if checked else "[ ]"
                markdown_lines.append(f"{checkbox} {text}")
            elif block_type == "code":
                text = (
                    type_data.get("rich_text", [{}])[0]
                    .get("text", {})
                    .get("content", "")
                )
                language = type_data.get("language", "")
                markdown_lines.append(f"```{language}\n{text}\n```")

            # Add empty line between blocks for readability
            markdown_lines.append("")

        return "\n".join(markdown_lines).strip()


# Function to get real Notion client
def get_real_notion_client(api_token: str) -> RealNotionService:
    """Get real Notion service client with provided API token"""
    return RealNotionService(api_token)
