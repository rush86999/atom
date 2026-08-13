"""Regression tests: ConnectionService.list_connections (R85 bug) + model accessors.

The MCP tool dispatch (integrations/mcp_service.py, 7 call sites) awaits
``conn_service.list_connections(user_id=...)`` and accesses
``conn.piece_name`` / ``conn.credentials`` / ``conn.metadata`` on the rows.
The method never existed on ConnectionService (only ``get_connections``
returning plain dicts), so every MCP tool touching connections (create_task,
send_message, get_inventory_levels, zoom, whatsapp_*, shipping) raised
``AttributeError: 'ConnectionService' object has no attribute 'list_connections'``
→ HTTP 500 on POST /api/projects/unified-tasks.
"""
import inspect
from unittest.mock import MagicMock, patch

import pytest

from core.connection_service import ConnectionService
from core.models import UserConnection


class TestListConnectionsMethod:
    def test_method_exists_and_async(self):
        assert hasattr(ConnectionService, "list_connections")
        assert inspect.iscoroutinefunction(ConnectionService().list_connections)

    @pytest.mark.asyncio
    async def test_returns_orm_rows(self):
        rows = [MagicMock(spec=UserConnection), MagicMock(spec=UserConnection)]
        with patch("core.connection_service.get_db_session") as mock_ctx:
            db = MagicMock()
            db.query.return_value.filter.return_value.all.return_value = rows
            mock_ctx.return_value.__enter__.return_value = db
            result = await ConnectionService().list_connections("u1")
            assert result == rows
            db.query.return_value.filter.assert_called_once()
            db.query.return_value.filter.return_value.filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_integration_id_filter(self):
        with patch("core.connection_service.get_db_session") as mock_ctx:
            db = MagicMock()
            db.query.return_value.filter.return_value.filter.return_value.all.return_value = ["row"]
            mock_ctx.return_value.__enter__.return_value = db
            result = await ConnectionService().list_connections("u1", integration_id="slack")
            assert result == ["row"]

    @pytest.mark.asyncio
    async def test_exception_returns_empty_list(self):
        with patch("core.connection_service.get_db_session") as mock_ctx:
            db = MagicMock()
            db.query.side_effect = RuntimeError("boom")
            mock_ctx.return_value.__enter__.return_value = db
            result = await ConnectionService().list_connections("u1")
            assert result == []


class TestUserConnectionAccessors:
    def test_piece_name_activepieces_form(self):
        c = UserConnection(
            user_id="u", integration_id="@activepieces/piece-slack",
            connection_name="n", credentials={},
        )
        assert c.piece_name == "slack"

    def test_piece_name_native_form(self):
        c = UserConnection(
            user_id="u", integration_id="shopify", connection_name="n", credentials={},
        )
        assert c.piece_name == "shopify"

    def test_piece_name_empty(self):
        c = UserConnection(user_id="u", integration_id="", connection_name="n", credentials={})
        assert c.piece_name == ""

    def test_metadata_from_credentials(self):
        c = UserConnection(
            user_id="u", integration_id="shopify", connection_name="n",
            credentials={"access_token": "t", "metadata": {"shop_url": "s.myshopify.com"}},
        )
        assert c.connection_metadata == {"shop_url": "s.myshopify.com"}

    def test_metadata_missing(self):
        c = UserConnection(
            user_id="u", integration_id="shopify", connection_name="n",
            credentials={"access_token": "t"},
        )
        assert c.connection_metadata == {}

    def test_metadata_non_dict_credentials(self):
        c = UserConnection(
            user_id="u", integration_id="shopify", connection_name="n", credentials="not-dict",
        )
        assert c.connection_metadata == {}
