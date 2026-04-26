"""
Test suite for notion_service.py

Notion API integration service with OAuth authentication.
Target file: backend/core/productivity/notion_service.py (766 lines)
Target tests: 20-25 tests
Coverage target: 25-30%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, List

# Import target module classes
from core.productivity.notion_service import (
    NotionService,
    get_database,
    query_database,
    create_page,
    update_page,
)


class TestNotionServiceInit:
    """Test NotionService initialization."""

    def test_initialization_with_user_id(self):
        """NotionService initializes with user_id."""
        service = NotionService(user_id="user-001")
        assert service.user_id == "user-001"
        assert service.use_api_key is False
        assert service.access_token is None

    def test_initialization_with_api_key_mode(self):
        """NotionService can initialize in API key mode."""
        service = NotionService(user_id="user-001", use_api_key=True)
        assert service.use_api_key is True

    def test_api_base_url_constant(self):
        """NotionService has correct API base URL."""
        assert NotionService.API_BASE == "https://api.notion.com/v1"

    def test_notion_version_constant(self):
        """NotionService has correct API version."""
        assert NotionService.NOTION_VERSION == "2022-06-28"


class TestNotionServiceAuthentication:
    """Test NotionService authentication methods."""

    @pytest.mark.asyncio
    async def test_get_access_token_from_database(self):
        """NotionService retrieves OAuth token from database."""
        service = NotionService(user_id="user-001")

        with patch('core.productivity.notion_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_token = MagicMock()
            mock_token.access_token = "test-token"
            mock_token.expires_at = None
            mock_token.status = "active"

            mock_db.query.return_value.filter.return_value.first.return_value = mock_token
            mock_get_db.return_value.__enter__.return_value = mock_db

            token = await service._get_access_token()
            assert token == "test-token"

    @pytest.mark.asyncio
    async def test_get_access_token_from_env(self):
        """NotionService retrieves API key from environment in API key mode."""
        service = NotionService(user_id="user-001", use_api_key=True)

        with patch.dict('os.environ', {'NOTION_API_KEY': 'test-api-key'}):
            token = await service._get_access_token()
            assert token == "test-api-key"

    @pytest.mark.asyncio
    async def test_get_authorization_url(self):
        """NotionService generates OAuth authorization URL."""
        with patch('core.productivity.notion_service.get_db_session') as mock_get_db, \
             patch('core.productivity.notion_service.uuid.uuid4', return_value='test-state'):

            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            url = await NotionService.get_authorization_url("user-001")
            assert url is not None
            assert "state=test-state" in url or url.startswith("https://")


class TestNotionServiceWorkspace:
    """Test NotionService workspace methods."""

    @pytest.mark.asyncio
    async def test_search_workspace(self):
        """NotionService can search workspace for pages."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "results": [
                {
                    "id": "page-001",
                    "object": "page",
                    "properties": {
                        "title": [{
                            "type": "title",
                            "title": [{"plain_text": "Test Page"}]
                        }]
                    },
                    "parent": {"type": "workspace"},
                    "url": "https://notion.so/test"
                }
            ]
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            results = await service.search_workspace("test query")
            assert len(results) > 0
            assert results[0]["id"] == "page-001"
            assert results[0]["title"] == "Test Page"

    @pytest.mark.asyncio
    async def test_list_databases(self):
        """NotionService can list all databases in workspace."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "results": [
                {
                    "id": "db-001",
                    "title": [{"plain_text": "Test Database"}],
                    "description": [{"plain_text": "A test database"}],
                    "url": "https://notion.so/db-001"
                }
            ]
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            databases = await service.list_databases()
            assert len(databases) > 0
            assert databases[0]["id"] == "db-001"
            assert databases[0]["title"] == "Test Database"


class TestNotionServiceDatabase:
    """Test NotionService database methods."""

    @pytest.mark.asyncio
    async def test_query_database(self):
        """NotionService can query a database."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "results": [
                {
                    "id": "page-001",
                    "properties": {
                        "Name": {
                            "type": "title",
                            "title": [{"plain_text": "Item 1"}]
                        }
                    }
                }
            ],
            "has_more": False
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            pages = await service.query_database("db-001")
            assert len(pages) > 0

    @pytest.mark.asyncio
    async def test_get_database_schema(self):
        """NotionService can get database schema."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "id": "db-001",
            "title": [{"plain_text": "Test DB"}],
            "description": [{"plain_text": "Test description"}],
            "properties": {
                "Name": {
                    "type": "title",
                    "id": "title-prop"
                },
                "Status": {
                    "type": "select",
                    "id": "status-prop"
                }
            },
            "url": "https://notion.so/db-001"
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            schema = await service.get_database_schema("db-001")
            assert schema["id"] == "db-001"
            assert "properties" in schema
            assert "Name" in schema["properties"]


class TestNotionServicePage:
    """Test NotionService page methods."""

    @pytest.mark.asyncio
    async def test_get_page(self):
        """NotionService can get page content."""
        service = NotionService(user_id="user-001")

        mock_page_response = {
            "id": "page-001",
            "created_time": "2026-01-01T00:00:00.000Z",
            "last_edited_time": "2026-01-01T01:00:00.000Z",
            "archived": False,
            "url": "https://notion.so/page-001",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}]
                }
            }
        }

        mock_blocks_response = {
            "results": [
                {
                    "id": "block-001",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {
                        "rich_text": [{"plain_text": "Paragraph text"}]
                    }
                }
            ],
            "has_more": False
        }

        with patch.object(service, '_make_request', side_effect=[mock_page_response, mock_blocks_response]):
            page = await service.get_page("page-001")
            assert page["id"] == "page-001"
            assert "blocks" in page

    @pytest.mark.asyncio
    async def test_create_page(self):
        """NotionService can create a new page."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "id": "page-002",
            "created_time": "2026-01-01T00:00:00.000Z",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "New Page"}]
                }
            }
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            page = await service.create_page(
                "db-001",
                {"Name": {"title": [{"text": {"content": "New Page"}}]}}
            )
            assert page["id"] == "page-002"

    @pytest.mark.asyncio
    async def test_update_page(self):
        """NotionService can update page properties."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "id": "page-001",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Updated Title"}]
                }
            }
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            page = await service.update_page(
                "page-001",
                {"Name": {"title": [{"text": {"content": "Updated Title"}}]}}
            )
            assert page["id"] == "page-001"

    @pytest.mark.asyncio
    async def test_append_page_blocks(self):
        """NotionService can append blocks to a page."""
        service = NotionService(user_id="user-001")

        mock_response = {
            "results": [
                {
                    "id": "block-002",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "New paragraph"}]
                    }
                }
            ]
        }

        with patch.object(service, '_make_request', return_value=mock_response):
            result = await service.append_page_blocks(
                "page-001",
                [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "New paragraph"}}]
                        }
                    }
                ]
            )
            assert result["success"] is True


class TestNotionServiceHelperMethods:
    """Test NotionService helper methods."""

    def test_format_page_properties(self):
        """NotionService correctly formats page properties."""
        service = NotionService(user_id="user-001")

        page_data = {
            "id": "page-001",
            "created_time": "2026-01-01T00:00:00.000Z",
            "last_edited_time": "2026-01-01T01:00:00.000Z",
            "archived": False,
            "url": "https://notion.so/page-001",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}]
                },
                "Status": {
                    "type": "select",
                    "select": {"name": "In Progress"}
                },
                "Count": {
                    "type": "number",
                    "number": 42
                },
                "Tags": {
                    "type": "multi_select",
                    "multi_select": [
                        {"name": "tag1"},
                        {"name": "tag2"}
                    ]
                }
            }
        }

        formatted = service._format_page_properties(page_data)

        assert formatted["id"] == "page-001"
        assert formatted["properties"]["Name"] == "Test Page"
        assert formatted["properties"]["Status"] == "In Progress"
        assert formatted["properties"]["Count"] == 42
        assert "tag1" in formatted["properties"]["Tags"]

    def test_format_block_paragraph(self):
        """NotionService correctly formats paragraph blocks."""
        service = NotionService(user_id="user-001")

        block_data = {
            "id": "block-001",
            "type": "paragraph",
            "has_children": False,
            "paragraph": {
                "rich_text": [{"plain_text": "Test paragraph"}]
            }
        }

        formatted = service._format_block(block_data)

        assert formatted["id"] == "block-001"
        assert formatted["type"] == "paragraph"
        assert formatted["text"] == "Test paragraph"

    def test_format_block_heading(self):
        """NotionService correctly formats heading blocks."""
        service = NotionService(user_id="user-001")

        block_data = {
            "id": "block-002",
            "type": "heading_1",
            "has_children": False,
            "heading_1": {
                "rich_text": [{"plain_text": "Test Heading"}]
            }
        }

        formatted = service._format_block(block_data)

        assert formatted["type"] == "heading_1"
        assert formatted["text"] == "Test Heading"

    def test_extract_rich_text(self):
        """NotionService correctly extracts plain text from rich text."""
        service = NotionService(user_id="user-001")

        rich_text = [
            {"plain_text": "Hello "},
            {"plain_text": "World"}
        ]

        text = service._extract_rich_text(rich_text)

        assert text == "Hello World"


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_get_database_function(self):
        """get_database convenience function works."""
        with patch('core.productivity.notion_service.NotionService.get_database_schema') as mock_get:
            mock_get.return_value = {"id": "db-001"}
            result = await get_database("user-001", "db-001")
            assert result["id"] == "db-001"

    @pytest.mark.asyncio
    async def test_query_database_function(self):
        """query_database convenience function works."""
        with patch('core.productivity.notion_service.NotionService.query_database') as mock_query:
            mock_query.return_value = [{"id": "page-001"}]
            result = await query_database("user-001", "db-001")
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_create_page_function(self):
        """create_page convenience function works."""
        with patch('core.productivity.notion_service.NotionService.create_page') as mock_create:
            mock_create.return_value = {"id": "page-002"}
            result = await create_page("user-001", "db-001", {})
            assert result["id"] == "page-002"

    @pytest.mark.asyncio
    async def test_update_page_function(self):
        """update_page convenience function works."""
        with patch('core.productivity.notion_service.NotionService.update_page') as mock_update:
            mock_update.return_value = {"id": "page-001"}
            result = await update_page("user-001", "page-001", {})
            assert result["id"] == "page-001"


class TestNotionServiceErrorHandling:
    """Test NotionService error handling."""

    @pytest.mark.asyncio
    async def test_make_request_rate_limit(self):
        """NotionService handles rate limiting (429)."""
        service = NotionService(user_id="user-001", use_api_key=True)

        with patch.dict('os.environ', {'NOTION_API_KEY': 'test-key'}), \
             patch('httpx.AsyncClient.request') as mock_request:

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "5"}
            mock_request.return_value = mock_response

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await service._make_request("GET", "/search")

            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_make_request_unauthorized(self):
        """NotionService handles 401 unauthorized."""
        service = NotionService(user_id="user-001")

        with patch('core.productivity.notion_service.get_db_session') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value.__enter__.return_value = mock_db

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await service._get_access_token()

            assert exc_info.value.status_code == 401
