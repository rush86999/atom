"""
Notion API Integration Service

Provides OAuth authentication, workspace search, database querying,
and page creation/editing for Notion workspaces.

Notion API: https://developers.notion.com/reference
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import HTTPException
import httpx

from core.oauth_handler import OAuthHandler, NOTION_OAUTH_CONFIG
from core.database import get_db_session
from core.models import OAuthToken

logger = logging.getLogger(__name__)


class NotionService:
    """
    Notion API integration service with OAuth and API key authentication.

    Supports two authentication modes:
    1. OAuth 2.0 flow (recommended for multi-user setups)
    2. API key authentication (simpler for Personal Edition)

    Notion tokens don't expire (no refresh token needed).
    """

    # Notion API base URL
    API_BASE = "https://api.notion.com/v1"

    # Notion API version
    NOTION_VERSION = "2022-06-28"

    def __init__(self, user_id: str, use_api_key: bool = False):
        """
        Initialize Notion service for a user.

        Args:
            user_id: User ID for token lookup
            use_api_key: If True, use NOTION_API_KEY instead of OAuth
        """
        self.user_id = user_id
        self.use_api_key = use_api_key
        self.access_token: Optional[str] = None

        # Notion-specific headers
        self.headers = {
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def _get_access_token(self) -> str:
        """
        Get access token from database or environment variable.

        Returns:
            Access token string

        Raises:
            HTTPException: If token not found
        """
        if self.use_api_key:
            # Use API key from environment (Personal Edition mode)
            api_key = os.getenv("NOTION_API_KEY")
            if not api_key:
                raise HTTPException(
                    status_code=401,
                    detail="Notion API key not configured. Set NOTION_API_KEY environment variable."
                )
            return api_key

        # Get OAuth token from database
        with get_db_session() as db:
            token = db.query(OAuthToken).filter(
                OAuthToken.user_id == self.user_id,
                OAuthToken.provider == "notion",
                OAuthToken.status == "active"
            ).first()

            if not token:
                raise HTTPException(
                    status_code=401,
                    detail="Notion not connected. Please authorize via OAuth."
                )

            # Check if token expired (shouldn't happen for Notion, but safe check)
            if token.expires_at and token.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=401,
                    detail="Notion token expired. Please re-authorize."
                )

            return token.access_token

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated request to Notion API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., /search, /databases/{id}/query)
            data: Request body for POST/PATCH
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            HTTPException: On API errors
        """
        # Get access token
        if not self.access_token:
            self.access_token = await self._get_access_token()

        # Add authorization header
        headers = {
            **self.headers,
            "Authorization": f"Bearer {self.access_token}"
        }

        url = f"{self.API_BASE}{endpoint}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=30.0
                )

                # Handle rate limiting (Notion: 3 requests/second)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    logger.warning(f"Notion rate limited. Retry after {retry_after}s")
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limited. Retry after {retry_after} seconds.",
                        headers={"Retry-After": str(retry_after)}
                    )

                # Handle other errors
                if response.status_code >= 400:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("message", error_detail)
                    except Exception:
                        pass

                    logger.error(f"Notion API error {response.status_code}: {error_detail}")

                    if response.status_code == 401:
                        raise HTTPException(401, "Invalid Notion token. Please re-authorize.")
                    elif response.status_code == 404:
                        raise HTTPException(404, "Notion resource not found.")
                    elif response.status_code == 400:
                        raise HTTPException(400, f"Invalid request: {error_detail}")
                    else:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Notion API error: {error_detail}"
                        )

                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Notion API request failed: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to connect to Notion API: {str(e)}"
            )

    # ==================== OAuth Methods ====================

    @staticmethod
    def get_oauth_handler() -> OAuthHandler:
        """Get OAuth handler for Notion."""
        return OAuthHandler(NOTION_OAUTH_CONFIG)

    @staticmethod
    async def get_authorization_url(user_id: str, state: Optional[str] = None) -> str:
        """
        Generate Notion OAuth authorization URL.

        Args:
            user_id: User ID for state tracking
            state: CSRF protection token (optional)

        Returns:
            Authorization URL
        """
        handler = NotionService.get_oauth_handler()

        # Generate state if not provided
        if not state:
            import uuid
            state = str(uuid.uuid4())

        # Store state in database for callback verification
        from core.models import OAuthState
        with get_db_session() as db:
            oauth_state = OAuthState(
                user_id=user_id,
                provider="notion",
                state=state,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.add(oauth_state)
            db.commit()

        return handler.get_authorization_url(state=state)

    @staticmethod
    async def exchange_code_for_tokens(code: str, user_id: str) -> Dict:
        """
        Exchange authorization code for access token.

        Notion returns:
        - access_token (never expires)
        - workspace_id
        - workspace_name
        - workspace_icon
        - bot_id
        - owner (workspace/user)

        Args:
            code: Authorization code from callback
            user_id: User ID for token storage

        Returns:
            Token response with workspace info
        """
        handler = NotionService.get_oauth_handler()

        # Exchange code for tokens
        tokens = await handler.exchange_code_for_tokens(code)

        # Store token in database
        with get_db_session() as db:
            # Check if user already has Notion token
            existing = db.query(OAuthToken).filter(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == "notion"
            ).first()

            if existing:
                # Update existing token
                existing.access_token = tokens["access_token"]
                existing.scopes = tokens.get("workspace_id")  # Use workspace_id as scope identifier
                existing.expires_at = datetime(2099, 12, 31)  # Notion tokens don't expire
                existing.status = "active"

                # Update metadata
                metadata = existing.metadata or {}
                metadata.update({
                    "workspace_id": tokens.get("workspace_id"),
                    "workspace_name": tokens.get("workspace_name"),
                    "workspace_icon": tokens.get("workspace_icon"),
                    "bot_id": tokens.get("bot_id"),
                    "owner": tokens.get("owner")
                })
                existing.metadata = metadata
            else:
                # Create new token
                oauth_token = OAuthToken(
                    user_id=user_id,
                    provider="notion",
                    access_token=tokens["access_token"],
                    token_type="Bearer",
                    scopes=[tokens.get("workspace_id")],
                    expires_at=datetime(2099, 12, 31),  # Notion tokens don't expire
                    status="active",
                    metadata={
                        "workspace_id": tokens.get("workspace_id"),
                        "workspace_name": tokens.get("workspace_name"),
                        "workspace_icon": tokens.get("workspace_icon"),
                        "bot_id": tokens.get("bot_id"),
                        "owner": tokens.get("owner")
                    }
                )
                db.add(oauth_token)

            db.commit()

        return {
            "success": True,
            "workspace_id": tokens.get("workspace_id"),
            "workspace_name": tokens.get("workspace_name"),
            "workspace_icon": tokens.get("workspace_icon")
        }

    # ==================== Workspace Methods ====================

    async def search_workspace(self, query: str) -> List[Dict]:
        """
        Search Notion workspace for pages and databases.

        Args:
            query: Search query text

        Returns:
            List of search results with id, title, type, parent
        """
        data = {
            "query": query,
            "filter": {
                "property": "object",
                "value": "page"  # Can also search "database"
            }
        }

        response = await self._make_request("POST", "/search", data=data)

        results = []
        for item in response.get("results", []):
            result = {
                "id": item["id"],
                "type": item["object"],
                "url": item.get("url", ""),
            }

            # Extract title
            if item["object"] == "page":
                title_data = item.get("properties", {}).get("title", {})
                if title_data.get("type") == "title" and title_data.get("title"):
                    result["title"] = title_data["title"][0].get("plain_text", "Untitled")
                else:
                    result["title"] = "Untitled"

                # Get parent info
                parent = item.get("parent", {})
                if parent.get("type") == "database_id":
                    result["parent_id"] = parent["database_id"]
                elif parent.get("type") == "page_id":
                    result["parent_id"] = parent["page_id"]
                elif parent.get("type") == "workspace":
                    result["parent_id"] = "workspace"

            elif item["object"] == "database":
                title_data = item.get("title", [])
                result["title"] = title_data[0].get("plain_text", "Untitled") if title_data else "Untitled"
                result["parent_id"] = "workspace"

            results.append(result)

        return results

    async def list_databases(self) -> List[Dict]:
        """
        List all databases in workspace.

        Returns:
            List of databases with id, title, description
        """
        data = {
            "filter": {
                "property": "object",
                "value": "database"
            }
        }

        response = await self._make_request("POST", "/search", data=data)

        databases = []
        for item in response.get("results", []):
            title_data = item.get("title", [])
            title = title_data[0].get("plain_text", "Untitled") if title_data else "Untitled"

            description = item.get("description", [])

            databases.append({
                "id": item["id"],
                "title": title,
                "description": description[0].get("plain_text", "") if description else "",
                "url": item.get("url", "")
            })

        return databases

    # ==================== Database Methods ====================

    async def query_database(
        self,
        database_id: str,
        filter: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Query Notion database with optional filter.

        Args:
            database_id: Database ID
            filter: Notion filter object (optional)

        Returns:
            List of page results with properties
        """
        data = {}
        if filter:
            data["filter"] = filter

        response = await self._make_request(
            "POST",
            f"/databases/{database_id}/query",
            data=data
        )

        pages = []
        for page in response.get("results", []):
            pages.append(self._format_page_properties(page))

        # Handle pagination (Notion uses cursor-based pagination)
        while response.get("has_more"):
            data["start_cursor"] = response["next_cursor"]
            response = await self._make_request(
                "POST",
                f"/databases/{database_id}/query",
                data=data
            )

            for page in response.get("results", []):
                pages.append(self._format_page_properties(page))

        return pages

    async def get_database_schema(self, database_id: str) -> Dict:
        """
        Get database schema (properties, title).

        Args:
            database_id: Database ID

        Returns:
            Database schema with property types
        """
        response = await self._make_request("GET", f"/databases/{database_id}")

        # Format properties
        properties = {}
        for prop_name, prop_data in response.get("properties", {}).items():
            properties[prop_name] = {
                "type": prop_data["type"],
                "id": prop_data["id"]
            }

        # Extract title
        title_data = response.get("title", [])
        title = title_data[0].get("plain_text", "") if title_data else ""

        return {
            "id": response["id"],
            "title": title,
            "description": response.get("description", [{}])[0].get("plain_text", ""),
            "properties": properties,
            "url": response.get("url", "")
        }

    # ==================== Page Methods ====================

    async def get_page(self, page_id: str) -> Dict:
        """
        Get page content (properties and blocks).

        Args:
            page_id: Page ID

        Returns:
            Page data with properties and blocks
        """
        response = await self._make_request("GET", f"/pages/{page_id}")

        page = self._format_page_properties(response)

        # Get page blocks (content)
        blocks = await self.get_page_blocks(page_id)
        page["blocks"] = blocks

        return page

    async def get_page_blocks(self, block_id: str) -> List[Dict]:
        """
        Get blocks for a page or block.

        Args:
            block_id: Page or block ID

        Returns:
            List of blocks with content
        """
        response = await self._make_request("GET", f"/blocks/{block_id}/children")

        blocks = []
        for block in response.get("results", []):
            blocks.append(self._format_block(block))

        # Handle pagination
        while response.get("has_more"):
            response = await self._make_request(
                "GET",
                f"/blocks/{block_id}/children",
                params={"start_cursor": response["next_cursor"]}
            )

            for block in response.get("results", []):
                blocks.append(self._format_block(block))

        return blocks

    async def create_page(
        self,
        database_id: str,
        properties: Dict
    ) -> Dict:
        """
        Create new page in database.

        Args:
            database_id: Parent database ID
            properties: Page properties formatted per Notion API spec

        Returns:
            Created page data
        """
        data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }

        response = await self._make_request("POST", "/pages", data=data)
        return self._format_page_properties(response)

    async def update_page(
        self,
        page_id: str,
        properties: Dict
    ) -> Dict:
        """
        Update existing page properties.

        Args:
            page_id: Page ID
            properties: Properties to update (partial updates allowed)

        Returns:
            Updated page data
        """
        data = {"properties": properties}

        response = await self._make_request("PATCH", f"/pages/{page_id}", data=data)
        return self._format_page_properties(response)

    async def append_page_blocks(
        self,
        page_id: str,
        blocks: List[Dict]
    ) -> Dict:
        """
        Add content blocks to page.

        Supported block types:
        - paragraph
        - heading_1, heading_2, heading_3
        - bulleted_list_item
        - numbered_list_item
        - to_do
        - code
        - quote
        - divider
        - callout

        Args:
            page_id: Page ID
            blocks: List of block objects

        Returns:
            Appended blocks data
        """
        data = {"children": blocks}

        response = await self._make_request(
            "PATCH",
            f"/blocks/{page_id}/children",
            data=data
        )

        return {
            "success": True,
            "blocks": [
                self._format_block(block)
                for block in response.get("results", [])
            ]
        }

    # ==================== Helper Methods ====================

    def _format_page_properties(self, page: Dict) -> Dict:
        """Extract and format page properties from Notion API response."""
        formatted = {
            "id": page["id"],
            "created_time": page.get("created_time"),
            "last_edited_time": page.get("last_edited_time"),
            "archived": page.get("archived", False),
            "url": page.get("url", ""),
            "properties": {}
        }

        # Format properties
        for prop_name, prop_data in page.get("properties", {}).items():
            prop_type = prop_data["type"]
            prop_value = None

            if prop_type == "title":
                titles = prop_data.get("title", [])
                prop_value = titles[0].get("plain_text", "") if titles else ""
            elif prop_type == "rich_text":
                texts = prop_data.get("rich_text", [])
                prop_value = texts[0].get("plain_text", "") if texts else ""
            elif prop_type == "number":
                prop_value = prop_data.get("number")
            elif prop_type == "select":
                select_data = prop_data.get("select")
                prop_value = select_data.get("name") if select_data else None
            elif prop_type == "multi_select":
                multi_select = prop_data.get("multi_select", [])
                prop_value = [s.get("name") for s in multi_select]
            elif prop_type == "date":
                date_data = prop_data.get("date")
                prop_value = date_data.get("start") if date_data else None
            elif prop_type == "checkbox":
                prop_value = prop_data.get("checkbox")
            elif prop_type == "url":
                prop_value = prop_data.get("url")
            elif prop_type == "email":
                prop_value = prop_data.get("email")
            elif prop_type == "phone":
                prop_value = prop_data.get("phone")
            elif prop_type == "formula":
                formula_data = prop_data.get("formula")
                if formula_data and formula_data.get("type") == "string":
                    prop_value = formula_data.get("string")
                elif formula_data and formula_data.get("type") == "number":
                    prop_value = formula_data.get("number")
            elif prop_type == "relation":
                relations = prop_data.get("relation", [])
                prop_value = [r["id"] for r in relations]
            elif prop_type == "rollup":
                rollup_data = prop_data.get("rollup")
                if rollup_data and rollup_data.get("type") == "number":
                    prop_value = rollup_data.get("number")
            else:
                # Fallback for other types
                prop_value = str(prop_data)

            formatted["properties"][prop_name] = prop_value

        return formatted

    def _format_block(self, block: Dict) -> Dict:
        """Extract and format block content from Notion API response."""
        formatted = {
            "id": block["id"],
            "type": block["type"],
            "has_children": block.get("has_children", False)
        }

        block_type = block["type"]
        block_data = block.get(block_type, {})

        # Extract content based on block type
        if block_type == "paragraph":
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)

        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)

        elif block_type == "bulleted_list_item":
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)

        elif block_type == "numbered_list_item":
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)
            formatted["number"] = block_data.get("number")

        elif block_type == "to_do":
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)
            formatted["checked"] = block_data.get("checked", False)

        elif block_type == "code":
            rich_text = block_data.get("rich_text", [])
            formatted["code"] = self._extract_rich_text(rich_text)
            formatted["language"] = block_data.get("language", "plain text")

        elif block_type == "quote":
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)

        elif block_type == "callout":
            rich_text = block_data.get("rich_text", [])
            formatted["text"] = self._extract_rich_text(rich_text)
            formatted["icon"] = block_data.get("icon", {}).get("emoji", "")

        elif block_type == "divider":
            formatted["text"] = "---"

        else:
            formatted["text"] = f"[{block_type}]"

        return formatted

    def _extract_rich_text(self, rich_text: List[Dict]) -> str:
        """Extract plain text from Notion rich text array."""
        return "".join(
            text.get("plain_text", "")
            for text in rich_text
        )


# Convenience functions for database operations

async def get_database(user_id: str, database_id: str) -> Dict:
    """Get database schema."""
    service = NotionService(user_id)
    return await service.get_database_schema(database_id)


async def query_database(
    user_id: str,
    database_id: str,
    filter: Optional[Dict] = None
) -> List[Dict]:
    """Query database with optional filter."""
    service = NotionService(user_id)
    return await service.query_database(database_id, filter)


async def create_page(
    user_id: str,
    database_id: str,
    properties: Dict
) -> Dict:
    """Create page in database."""
    service = NotionService(user_id)
    return await service.create_page(database_id, properties)


async def update_page(
    user_id: str,
    page_id: str,
    properties: Dict
) -> Dict:
    """Update page properties."""
    service = NotionService(user_id)
    return await service.update_page(page_id, properties)
