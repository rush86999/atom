"""TDD bug-hunt: NotionService OAuth storage (R80 follow-up).

``NotionService`` reads/writes ``OAuthToken`` with ``provider`` /
``access_token`` / ``status`` / ``workspace_id`` — columns that exist on
``IntegrationToken`` (the model every other integration uses) but NOT on
``OAuthToken`` (the OAuth-server model, which stores hashes + client_id).
Every Notion OAuth lookup raised AttributeError and every code exchange
raised TypeError — Notion OAuth was completely dead in production.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def service():
    from core.productivity.notion_service import NotionService

    return NotionService(user_id="user-001")


@pytest.mark.asyncio
async def test_get_access_token_reads_integration_token(service):
    """Must read IntegrationToken rows (provider/user/status), not OAuthToken."""
    token = MagicMock()
    token.access_token = "notion-token-123"
    token.expires_at = None

    with patch("core.productivity.notion_service.get_db_session") as mock_get_db:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = token
        mock_db.query.return_value = mock_query
        mock_get_db.return_value.__enter__.return_value = mock_db

        result = await service._get_access_token()

    assert result == "notion-token-123"
    from core.models import IntegrationToken

    model_arg = mock_db.query.call_args.args[0]
    assert model_arg is IntegrationToken


@pytest.mark.asyncio
async def test_get_access_token_missing_raises_401(service):
    with patch("core.productivity.notion_service.get_db_session") as mock_get_db:
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        mock_get_db.return_value.__enter__.return_value = mock_db

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await service._get_access_token()
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_exchange_code_stores_integration_token():
    """Code exchange must upsert an IntegrationToken row."""
    from core.productivity.notion_service import NotionService

    tokens = {
        "access_token": "ntn_abc123",
        "workspace_id": "ws-9",
        "workspace_name": "Team Space",
        "workspace_icon": "icon.png",
        "bot_id": "bot-1",
        "owner": {"type": "workspace", "workspace": True},
    }

    with patch(
        "core.productivity.notion_service.NotionService.get_oauth_handler"
    ) as mock_handler, patch(
        "core.productivity.notion_service.get_db_session"
    ) as mock_get_db, patch(
        "core.productivity.notion_service.encrypt_token", side_effect=lambda v: f"enc:{v}"
    ):
        mock_handler.return_value.exchange_code_for_tokens = AsyncMock(return_value=tokens)
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # no existing row -> create
        mock_db.query.return_value = mock_query
        mock_get_db.return_value.__enter__.return_value = mock_db

        result = await NotionService.exchange_code_for_tokens("the-code", "user-001")

    assert result["success"] is True
    assert result["workspace_id"] == "ws-9"

    from core.models import IntegrationToken

    added = mock_db.add.call_args.args[0]
    assert isinstance(added, IntegrationToken)
    assert added.provider == "notion"
    assert added.access_token == "enc:ntn_abc123"
    assert added.user_id == "user-001"
    assert added.workspace_id == "ws-9"
    assert added.status == "active"


@pytest.mark.asyncio
async def test_exchange_code_updates_existing_token():
    from core.productivity.notion_service import NotionService

    tokens = {"access_token": "ntn_new", "workspace_id": "ws-9"}

    with patch(
        "core.productivity.notion_service.NotionService.get_oauth_handler"
    ) as mock_handler, patch(
        "core.productivity.notion_service.get_db_session"
    ) as mock_get_db, patch(
        "core.productivity.notion_service.encrypt_token", side_effect=lambda v: f"enc:{v}"
    ):
        mock_handler.return_value.exchange_code_for_tokens = AsyncMock(return_value=tokens)
        existing = MagicMock()
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = existing
        mock_db.query.return_value = mock_query
        mock_get_db.return_value.__enter__.return_value = mock_db

        await NotionService.exchange_code_for_tokens("the-code", "user-001")

    mock_db.add.assert_not_called()
    assert existing.access_token == "enc:ntn_new"
    assert existing.status == "active"
    mock_db.commit.assert_called_once()
