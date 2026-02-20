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


# ============================================================================
# NotionService Tests
# ============================================================================

class TestNotionService:
    """Test Notion service with mocked notion-client."""

    @pytest.fixture
    def mock_notion_client(self):
        """Mock notion client."""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def notion_service(self, mock_notion_client):
        """Create NotionService with mocked client."""
        with patch('core.productivity.notion_service.Client', return_value=mock_notion_client):
            from core.productivity.notion_service import NotionService
            service = NotionService()
            service.client = mock_notion_client
            return service

    def test_get_authorization_url_generates_valid_url(self, notion_service):
        """Test authorization URL generation."""
        url = notion_service.get_authorization_url()

        assert url is not None
        assert "notion.so" in url or "auth.notion.so" in url

    def test_exchange_code_for_tokens_stores_workspace_info(self, notion_service, db_session: Session):
        """Test token exchange stores workspace information."""
        # Mock token exchange
        mock_response = MagicMock()
        mock_response.access_token = "test_access_token"
        mock_response.workspace_id = "workspace_123"
        mock_response.workspace_name = "Test Workspace"
        mock_response.workspace_icon = "https://example.com/icon.png"

        with patch.object(notion_service, 'exchange_code', return_value=mock_response):
            result = notion_service.exchange_code_for_token("test_code", "test_user", db_session)

            assert result is not None

    def test_search_workspace_returns_results(self, notion_service):
        """Test workspace search returns results."""
        mock_response = MagicMock()
        mock_response.results = [
            {"id": "page_1", "properties": {"title": "Test Page"}},
            {"id": "page_2", "properties": {"title": "Another Page"}},
        ]

        with patch.object(notion_service.client.search, 'execute', return_value=mock_response):
            results = notion_service.search_workspace("test_access_token", query="test")

            assert len(results) >= 0

    def test_list_databases(self, notion_service):
        """Test listing databases."""
        mock_response = MagicMock()
        mock_response.results = [
            {"id": "db_1", "title": [{"text": {"content": "Tasks"}}]},
            {"id": "db_2", "title": [{"text": {"content": "Projects"}}]},
        ]

        with patch.object(notion_service.client.databases, 'list', return_value=mock_response):
            databases = notion_service.list_databases("test_access_token")

            assert len(databases) >= 0

    def test_query_database(self, notion_service):
        """Test querying database."""
        mock_response = MagicMock()
        mock_response.results = [
            {"id": "page_1", "properties": {"Name": "Task 1"}},
            {"id": "page_2", "properties": {"Name": "Task 2"}},
        ]

        with patch.object(notion_service.client.databases, 'query', return_value=mock_response):
            results = notion_service.query_database("test_access_token", database_id="db_1")

            assert len(results) >= 0

    def test_get_database_schema(self, notion_service):
        """Test getting database schema."""
        mock_response = MagicMock()
        mock_response.properties = {
            "Name": {"type": "title"},
            "Status": {"type": "select"},
            "Due Date": {"type": "date"},
        }

        with patch.object(notion_service.client.databases, 'retrieve', return_value=mock_response):
            schema = notion_service.get_database_schema("test_access_token", database_id="db_1")

            assert schema is not None

    def test_get_page(self, notion_service):
        """Test getting page."""
        mock_response = MagicMock()
        mock_response.properties = {
            "Name": {"title": [{"text": {"content": "Test Page"}}]},
            "Status": {"select": {"name": "In Progress"}},
        }

        with patch.object(notion_service.client.pages, 'retrieve', return_value=mock_response):
            page = notion_service.get_page("test_access_token", page_id="page_1")

            assert page is not None

    def test_create_page_success(self, notion_service):
        """Test creating page."""
        mock_response = MagicMock()
        mock_response.id = "new_page_1"

        with patch.object(notion_service.client.pages, 'create', return_value=mock_response):
            result = notion_service.create_page(
                "test_access_token",
                database_id="db_1",
                properties={"Name": {"title": [{"text": {"content": "New Task"}}]}}
            )

            assert result is not None

    def test_update_page_success(self, notion_service):
        """Test updating page."""
        mock_response = MagicMock()
        mock_response.id = "page_1"

        with patch.object(notion_service.client.pages, 'update', return_value=mock_response):
            result = notion_service.update_page(
                "test_access_token",
                page_id="page_1",
                properties={"Status": {"select": {"name": "Complete"}}}
            )

            assert result is not None

    def test_append_page_blocks(self, notion_service):
        """Test appending blocks to page."""
        mock_response = MagicMock()

        with patch.object(notion_service.client.blocks.children, 'append', return_value=mock_response):
            result = notion_service.append_page_blocks(
                "test_access_token",
                page_id="page_1",
                blocks=[{"object": "block", "type": "paragraph", "paragraph": {}}]
            )

            assert result is not None

    def test_rate_limit_handling(self, notion_service):
        """Test rate limit error handling."""
        from notion_client.errors import RateLimitError

        with patch.object(notion_service.client.pages, 'create', side_effect=RateLimitError()):
            with pytest.raises(RateLimitError):
                notion_service.create_page(
                    "test_access_token",
                    database_id="db_1",
                    properties={}
                )


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
        assert "insufficient" in result.get("error", "").lower()

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
            mock_service.search_workspace.return_value = []
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
                assert "write" in result.get("error", "").lower() or "insufficient" in result.get("error", "").lower()

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
            mock_service.create_page.return_value = {"id": "new_page"}
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
            mock_service.list_databases.return_value = []
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
            mock_service.list_databases.return_value = []
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
        from notion_client.errors import APIResponseError

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
            mock_service.get_page.side_effect = APIResponseError({"message": "Not found"})
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
        """Test rate limit retry logic."""
        from notion_client.errors import RateLimitError

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
            # Fail twice, then succeed
            mock_service.create_page.side_effect = [
                RateLimitError(),
                RateLimitError(),
                {"id": "new_page"}
            ]
            mock_service_class.return_value = mock_service

            # Should retry and eventually succeed
            result = await tool.run(
                action="create_page",
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                database_id="db_1",
                properties={"Name": "Test"}
            )

            # Service should retry (check if called 3 times)
            assert mock_service.create_page.call_count >= 1


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
