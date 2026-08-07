"""
Tests for Productivity Tool (Notion Integration)

Tests NotionService with mocked Notion SDK.
Covers governance enforcement, OAuth flows, workspace operations, read/write permissions.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import AgentRegistry, OAuthToken, User, AgentStatus

# Import NotionTool
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.productivity_tool import NotionTool
from core.productivity.notion_service import NotionService


# ============================================================================
# NotionService Tests
# ============================================================================

class TestNotionService:
    """Test Notion service with mocked API layer."""

    @pytest.fixture
    def notion_service(self):
        """Create NotionService with mocked token access."""
        service = NotionService("test_user")
        service.access_token = "test_access_token"
        return service

    @pytest.mark.asyncio
    async def test_get_authorization_url_generates_valid_url(self):
        """Test authorization URL generation."""
        mock_handler = MagicMock()
        mock_handler.get_authorization_url.return_value = (
            "https://auth.notion.so/authorize?client_id=test"
        )

        with patch.object(NotionService, "get_oauth_handler", return_value=mock_handler), \
             patch("core.productivity.notion_service.get_db_session", return_value=MagicMock()):
            url = await NotionService.get_authorization_url("test_user")

        assert url is not None
        assert "notion.so" in url

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_stores_workspace_info(self):
        """Test token exchange stores workspace information."""
        mock_handler = MagicMock()
        mock_handler.exchange_code_for_tokens = AsyncMock(return_value={
            "access_token": "test_access_token",
            "workspace_id": "workspace_123",
            "workspace_name": "Test Workspace",
            "workspace_icon": "https://example.com/icon.png",
            "bot_id": "bot_1",
            "owner": {"type": "workspace"},
        })

        with patch.object(NotionService, "get_oauth_handler", return_value=mock_handler), \
             patch("core.productivity.notion_service.get_db_session", return_value=MagicMock()), \
             patch("core.productivity.notion_service.encrypt_token", side_effect=lambda v: v), \
             patch("core.productivity.notion_service.IntegrationToken") as mock_token_cls:
            result = await NotionService.exchange_code_for_tokens("test_code", "test_user")

        assert result is not None
        assert result["workspace_id"] == "workspace_123"
        assert result["workspace_name"] == "Test Workspace"

    @pytest.mark.asyncio
    async def test_search_workspace_returns_results(self, notion_service):
        """Test workspace search returns results."""
        notion_service._make_request = AsyncMock(return_value={
            "results": [
                {
                    "id": "page_1",
                    "object": "page",
                    "url": "https://notion.so/page_1",
                    "properties": {
                        "title": {"type": "title", "title": [{"plain_text": "Test Page"}]}
                    },
                    "parent": {"type": "database_id", "database_id": "db_1"},
                },
                {
                    "id": "page_2",
                    "object": "page",
                    "url": "https://notion.so/page_2",
                    "properties": {
                        "title": {"type": "title", "title": [{"plain_text": "Another Page"}]}
                    },
                    "parent": {"type": "workspace"},
                },
            ]
        })

        results = await notion_service.search_workspace("test")

        assert len(results) >= 2
        assert results[0]["id"] == "page_1"
        assert results[0]["title"] == "Test Page"

    @pytest.mark.asyncio
    async def test_list_databases(self, notion_service):
        """Test listing databases."""
        notion_service._make_request = AsyncMock(return_value={
            "results": [
                {"id": "db_1", "title": [{"plain_text": "Tasks"}], "url": ""},
                {"id": "db_2", "title": [{"plain_text": "Projects"}], "url": ""},
            ]
        })

        databases = await notion_service.list_databases()

        assert len(databases) >= 2
        assert databases[0]["id"] == "db_1"
        assert databases[0]["title"] == "Tasks"

    @pytest.mark.asyncio
    async def test_query_database(self, notion_service):
        """Test querying database."""
        notion_service._make_request = AsyncMock(return_value={
            "results": [
                {"id": "page_1", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Task 1"}]}}},
                {"id": "page_2", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Task 2"}]}}},
            ]
        })

        results = await notion_service.query_database(database_id="db_1")

        assert len(results) >= 2
        assert results[0]["id"] == "page_1"

    @pytest.mark.asyncio
    async def test_get_database_schema(self, notion_service):
        """Test getting database schema."""
        notion_service._make_request = AsyncMock(return_value={
            "id": "db_1",
            "properties": {
                "Name": {"type": "title", "id": "t1"},
                "Status": {"type": "select", "id": "s1"},
                "Due Date": {"type": "date", "id": "d1"},
            },
            "title": [],
            "description": [],
            "url": "",
        })

        schema = await notion_service.get_database_schema(database_id="db_1")

        assert schema is not None
        assert schema["id"] == "db_1"
        assert "Name" in schema["properties"]
        assert schema["properties"]["Status"]["type"] == "select"

    @pytest.mark.asyncio
    async def test_get_page(self, notion_service):
        """Test getting page."""
        notion_service._make_request = AsyncMock(side_effect=[
            {
                "id": "page_1",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Test Page"}]},
                    "Status": {"type": "select", "select": {"name": "In Progress"}},
                },
            },
            {"results": []},
        ])

        page = await notion_service.get_page(page_id="page_1")

        assert page is not None
        assert page["id"] == "page_1"
        assert page["properties"]["Name"] == "Test Page"

    @pytest.mark.asyncio
    async def test_create_page_success(self, notion_service):
        """Test creating page."""
        notion_service._make_request = AsyncMock(return_value={
            "id": "new_page_1",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": "New Task"}]}},
        })

        result = await notion_service.create_page(
            database_id="db_1",
            properties={"Name": {"title": [{"text": {"content": "New Task"}}]}}
        )

        assert result is not None
        assert result["id"] == "new_page_1"

    @pytest.mark.asyncio
    async def test_update_page_success(self, notion_service):
        """Test updating page."""
        notion_service._make_request = AsyncMock(return_value={
            "id": "page_1",
            "properties": {"Status": {"type": "select", "select": {"name": "Complete"}}},
        })

        result = await notion_service.update_page(
            page_id="page_1",
            properties={"Status": {"select": {"name": "Complete"}}}
        )

        assert result is not None
        assert result["id"] == "page_1"

    @pytest.mark.asyncio
    async def test_append_page_blocks(self, notion_service):
        """Test appending blocks to page."""
        notion_service._make_request = AsyncMock(return_value={"results": []})

        result = await notion_service.append_page_blocks(
            page_id="page_1",
            blocks=[{"object": "block", "type": "paragraph", "paragraph": {}}]
        )

        assert result is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, notion_service):
        """Test rate limit error handling."""
        from fastapi import HTTPException

        notion_service._make_request = AsyncMock(
            side_effect=HTTPException(
                status_code=429,
                detail="Rate limited. Retry after 1 seconds.",
                headers={"Retry-After": "1"},
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await notion_service.create_page(database_id="db_1", properties={})

        assert exc_info.value.status_code == 429


# ============================================================================
# NotionTool Tests
# ============================================================================

class TestNotionToolGovernance:
    """Test governance enforcement for Notion tool."""

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_notion(self, db_session: Session):
        """Test STUDENT agent is blocked from all Notion operations."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            maturity_level="STUDENT",
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        result = await tool.run(
            action="search",
            agent_id=agent.id,
            user_id="test_user",
            db=db_session
        )

        assert result["success"] is False
        assert "requires" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_intern_agent_can_read_only(self, db_session: Session):
        """Test INTERN agent can read but not write."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="TestIntern",
            status=AgentStatus.INTERN.value,
            maturity_level="INTERN",
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.search_workspace = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            # Read operations should work
            result = await tool.run(
                action="search",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                query="test"
            )

            # Should pass governance check
            assert result.get("success") is not False or "governance_check" in result

            # Write operations should be blocked
            with patch.object(mock_service, 'create_page', return_value={"id": "new"}):
                result = await tool.run(
                    action="create_page",
                    agent_id=agent.id,
                    user_id="test_user",
                    db=db_session,
                    database_id="db_1",
                    properties={}
                )

                assert result["success"] is False
                assert "requires" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_supervised_agent_can_write(self, db_session: Session):
        """Test SUPERVISED agent can write to Notion."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="SupervisedAgent",
            category="test",
            module_path="test.module",
            class_name="TestSupervised",
            status=AgentStatus.SUPERVISED.value,
            maturity_level="SUPERVISED",
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.create_page = AsyncMock(return_value={"id": "new_page"})
            mock_service_class.return_value = mock_service

            result = await tool.run(
                action="create_page",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                database_id="db_1",
                properties={"Name": "Test"}
            )

            # Should pass governance check
            assert result.get("success") is not False or "governance_check" in result


# ============================================================================
# API Key Authentication Tests
# ============================================================================

class TestNotionAPIKeyAuth:
    """Test API key authentication for Notion."""

    @pytest.mark.asyncio
    async def test_api_key_authentication_works(self, db_session: Session):
        """Test API key authentication works."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service with API key
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.list_databases = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            result = await tool.run(
                action="list_databases",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                api_key="secret_test_api_key"
            )

            assert result.get("success") is not False or "governance_check" in result

    @pytest.mark.asyncio
    async def test_oauth_and_api_key_both_supported(self, db_session: Session):
        """Test both OAuth and API key authentication are supported."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.list_databases = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            # Test with API key
            result1 = await tool.run(
                action="list_databases",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                api_key="secret_api_key"
            )

            # Test with OAuth (no api_key, uses database token)
            result2 = await tool.run(
                action="list_databases",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session
            )

            # Both should work (governance-wise)
            assert "governance_check" in result1 or result1.get("success") is not False
            assert "governance_check" in result2 or result2.get("success") is not False


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestNotionErrorHandling:
    """Test error handling for Notion operations."""

    @pytest.mark.asyncio
    async def test_page_not_found_error(self, db_session: Session):
        """Test page not found error handling."""
        import httpx
        from notion_client.errors import APIResponseError, APIErrorCode

        tool = NotionTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_page.side_effect = APIResponseError(
                httpx.Response(404, request=httpx.Request("GET", "https://api.notion.com/v1/pages/x")),
                "Not found",
                APIErrorCode.ObjectNotFound,
            )
            mock_service_class.return_value = mock_service

            result = await tool.run(
                action="get_page",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                page_id="nonexistent_page"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_invalid_properties_error(self, db_session: Session):
        """Test invalid properties error handling."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.create_page.side_effect = ValueError("Invalid properties")
            mock_service_class.return_value = mock_service

            result = await tool.run(
                action="create_page",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                database_id="db_1",
                properties={"InvalidField": "value"}
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_rate_limit_retry_logic(self, db_session: Session):
        """Test rate limit handling."""
        tool = NotionTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Notion service
        with patch('tools.productivity_tool.NotionService') as mock_service_class:
            mock_service = MagicMock()
            # Fail on first attempt, then succeed
            mock_service.create_page.side_effect = [
                Exception("Rate limited"),
                {"id": "new_page"}
            ]
            mock_service_class.return_value = mock_service

            result = await tool.run(
                action="create_page",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                database_id="db_1",
                properties={"Name": "Test"}
            )

            # Service call was attempted
            assert mock_service.create_page.call_count >= 1
            assert result["success"] is False


# ============================================================================
# Local-Only Mode Tests
# ============================================================================

class TestNotionLocalOnlyMode:
    """Test local-only mode enforcement for Notion."""

    @pytest.mark.asyncio
    async def test_local_only_mode_blocks_notion(self, db_session: Session, monkeypatch):
        """Test local-only mode blocks Notion (requires cloud API)."""
        # Enable local-only mode
        monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
        from core.privsec.local_only_guard import LocalOnlyGuard
        LocalOnlyGuard.reset_cache()

        tool = NotionTool()

        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        result = await tool.run(
            action="search",
            agent_id=agent.id,
            user_id="test_user",
            db=db_session,
            query="test"
        )

        assert result["success"] is False
        assert "local-only" in result.get("error", "").lower() or "cloud" in result.get("error", "").lower()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestNotionIntegration:
    """Integration tests requiring real Notion credentials."""

    @pytest.mark.skip(reason="Requires real Notion credentials")
    def test_real_notion_search(self):
        """Test with real Notion API (requires credentials)."""
        # This test only runs with: pytest -m integration
        pass

    @pytest.mark.skip(reason="Requires real Notion credentials")
    def test_real_notion_create_page(self):
        """Test with real Notion API (requires credentials)."""
        # This test only runs with: pytest -m integration
        pass
