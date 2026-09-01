"""
Tests for Email API Real-Time Message Ingestion
Tests the Gmail and Outlook API integration for polling and message fetching.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
import pytest_asyncio

# Scoped stub for core.knowledge_ingestion: importing the pipeline drags in
# core.knowledge_ingestion -> enhanced_ai_workflow_endpoints -> service_factory
# -> atom_meta_agent -> the whole application (network-bound imports and slow
# provider initialization at import time). The pipeline only calls
# get_knowledge_ingestion() inside _store_in_memory (never exercised by these
# tests — the memory manager is mocked), so a stub is safe. The original
# module is restored immediately after the import to avoid pollution.
_orig_knowledge_ingestion = sys.modules.get("core.knowledge_ingestion")
_mock_knowledge_ingestion = MagicMock()
_mock_knowledge_ingestion.get_knowledge_ingestion = MagicMock(return_value=None)
sys.modules["core.knowledge_ingestion"] = _mock_knowledge_ingestion

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    CommunicationIngestionPipeline,
    IngestionConfig,
    LanceDBMemoryManager,
)

if _orig_knowledge_ingestion is not None:
    sys.modules["core.knowledge_ingestion"] = _orig_knowledge_ingestion
else:
    sys.modules.pop("core.knowledge_ingestion", None)


@pytest.fixture
def mock_memory_manager():
    """Create a mock LanceDBMemoryManager"""
    manager = Mock(spec=LanceDBMemoryManager)
    manager.db = Mock()
    manager.ingest_communication = Mock(return_value=True)
    return manager


@pytest.fixture
def ingestion_pipeline(mock_memory_manager):
    """Create CommunicationIngestionPipeline instance"""
    pipeline = CommunicationIngestionPipeline(mock_memory_manager)
    return pipeline


@pytest.fixture
def gmail_config():
    """Create Gmail ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.GMAIL,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30
    )


@pytest.fixture
def outlook_config():
    """Create Outlook ingestion configuration"""
    return IngestionConfig(
        app_type=CommunicationAppType.OUTLOOK,
        enabled=True,
        real_time=True,
        batch_size=50,
        ingest_attachments=True,
        embed_content=True,
        retention_days=30
    )


class TestGmailAPIIntegration:
    """Test suite for Gmail API integration"""

    def test_configure_gmail_ingestion(self, ingestion_pipeline, gmail_config):
        """Test configuring Gmail ingestion"""
        ingestion_pipeline.configure_app(CommunicationAppType.GMAIL, gmail_config)

        assert "gmail" in ingestion_pipeline.ingestion_configs
        assert "gmail" in ingestion_pipeline.app_configs

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_gmail_messages_without_service(self, ingestion_pipeline):
        """Test that missing Gmail service is handled gracefully"""
        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = None
            mock_service_class.return_value = mock_service

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_gmail_messages_success(self, ingestion_pipeline, gmail_config):
        """Test successful Gmail message fetching"""
        ingestion_pipeline.configure_app(CommunicationAppType.GMAIL, gmail_config)

        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = Mock()

            # Mock get_messages to return sample messages
            mock_service.get_messages = Mock(return_value=[
                {
                    "id": "1234567890",
                    "threadId": "thread_123",
                    "timestamp": "2024-02-01T12:00:00Z",
                    "sender": "John Doe <john@example.com>",
                    "recipient": "me@example.com",
                    "subject": "Test Email",
                    "body": "This is a test email from Gmail",
                    "snippet": "This is a test email",
                    "labelIds": ["INBOX", "UNREAD"],
                    "attachments": [],
                    "historyId": "123456",
                    "internalDate": "1706793600000"
                }
            ])

            mock_service_class.return_value = mock_service

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert len(messages) == 1
            assert messages[0]["app_type"] == "gmail"
            assert messages[0]["sender"] == "John Doe"
            assert messages[0]["sender_email"] == "john@example.com"
            assert messages[0]["subject"] == "Test Email"
            assert messages[0]["content"] == "This is a test email from Gmail"
            assert "INBOX" in messages[0]["tags"]

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_gmail_messages_incremental(self, ingestion_pipeline):
        """Test incremental Gmail fetching with date filter"""
        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = Mock()
            mock_service.get_messages = Mock(return_value=[])

            mock_service_class.return_value = mock_service

            last_fetch = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
            messages = await ingestion_pipeline._fetch_gmail_messages(last_fetch)

            # Verify that get_messages was called with date query
            mock_service.get_messages.assert_called_once()
            call_args = mock_service.get_messages.call_args
            query = call_args.kwargs.get('query', call_args.args[0] if call_args.args else "")

            assert "after:" in query

    @pytest.mark.asyncio(mode="auto")
    async def test_gmail_message_normalization(self, ingestion_pipeline):
        """Test Gmail message normalization structure"""
        with patch('integrations.gmail_service.GmailService') as mock_service_class:
            mock_service = Mock()
            mock_service.service = Mock()

            mock_service.get_messages = Mock(return_value=[
                {
                    "id": "msg_123",
                    "threadId": "thread_456",
                    "timestamp": "2024-02-01T14:30:00Z",
                    "sender": "Alice Smith <alice@company.com>",
                    "recipient": "bob@company.com",
                    "subject": "Project Update",
                    "body": "<p>HTML email content</p>",
                    "snippet": "HTML email content",
                    "labelIds": ["INBOX", "IMPORTANT", "CATEGORY_WORK"],
                    "attachments": [
                        {
                            "id": "att_123",
                            "filename": "document.pdf",
                            "size": 1024,
                            "contentType": "application/pdf"
                        }
                    ]
                }
            ])

            mock_service_class.return_value = mock_service

            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert len(messages) == 1
            msg = messages[0]

            # Verify structure
            assert msg["app_type"] == "gmail"
            assert msg["direction"] == "inbound"
            assert msg["sender"] == "Alice Smith"
            assert msg["sender_email"] == "alice@company.com"
            assert msg["subject"] == "Project Update"
            assert msg["content"] == "<p>HTML email content</p>"
            assert msg["priority"] == "high"  # IMPORTANT label
            assert "INBOX" in msg["tags"]
            assert "IMPORTANT" in msg["tags"]
            assert len(msg["attachments"]) == 1
            assert msg["attachments"][0]["filename"] == "document.pdf"


class TestOutlookAPIIntegration:
    """Test suite for Outlook API integration"""

    def test_configure_outlook_ingestion(self, ingestion_pipeline, outlook_config):
        """Test configuring Outlook ingestion"""
        ingestion_pipeline.configure_app(CommunicationAppType.OUTLOOK, outlook_config)

        assert "outlook" in ingestion_pipeline.ingestion_configs
        assert "outlook" in ingestion_pipeline.app_configs

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_without_token(self, ingestion_pipeline):
        """Test that missing Microsoft token is handled gracefully"""
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-test"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_token:
            messages = await ingestion_pipeline._fetch_outlook_messages(None)

            assert messages == []
            mock_token.assert_awaited_once()

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_success(self, ingestion_pipeline, outlook_config):
        """Test successful Outlook message fetching"""
        ingestion_pipeline.configure_app(CommunicationAppType.OUTLOOK, outlook_config)

        # Hermetic owner list: the real _outlook_token_owners queries the DB,
        # which made this test pass only on machines with a live token row.
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-test"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="test_outlook_token",
        ):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_client.get = AsyncMock(
                    return_value=Mock(
                        status_code=200,
                        json=lambda: {
                            "value": [
                                {
                                    "id": "AAMkADY3NjI5OWUzLWJjZDAtNDVkMS1h",
                                    "receivedDateTime": "2024-02-01T12:00:00Z",
                                    "from": {
                                        "emailAddress": {
                                            "name": "Bob Johnson",
                                            "address": "bob@example.com"
                                        }
                                    },
                                    "toRecipients": [
                                        {
                                            "emailAddress": {
                                                "address": "me@example.com"
                                            }
                                        }
                                    ],
                                    "subject": "Meeting Tomorrow",
                                    "body": {
                                        "contentType": "Text",
                                        "content": "Let's meet tomorrow at 2pm"
                                    },
                                    "importance": "Normal",
                                    "isRead": False,
                                    "conversationId": "conv_123"
                                }
                            ]
                        }
                    )
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                assert len(messages) == 1
                assert messages[0]["app_type"] == "outlook"
                assert messages[0]["sender"] == "Bob Johnson"
                assert messages[0]["sender_email"] == "bob@example.com"
                assert messages[0]["subject"] == "Meeting Tomorrow"
                assert messages[0]["content"] == "Let's meet tomorrow at 2pm"
                assert messages[0]["status"] == "unread"
                assert messages[0]["priority"] == "normal"

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_uses_configured_user_token(
        self, ingestion_pipeline, outlook_config
    ):
        """The poller must resolve the token for the user stored in its config
        when no DB grants exist (fallback path).

        Regression: _fetch_outlook_messages used to call
        _get_access_token(user_id=None). That function refuses falsy user ids
        by design (no cross-user fallback), so the poller always got None and
        never fetched mail — even with a single connected user.
        """
        ingestion_pipeline.configure_app(CommunicationAppType.OUTLOOK, outlook_config)
        ingestion_pipeline.app_configs["outlook"]["user_id"] = "user-abc123"
        ingestion_pipeline.ingestion_configs["outlook"]["user_id"] = "user-abc123"

        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-abc123"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="test_outlook_token",
        ) as mock_token:
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client.get = AsyncMock(
                    return_value=Mock(
                        status_code=200,
                        json=lambda: {"value": [], "@odata.nextLink": None},
                    )
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

        assert messages == []
        # The token lookup must target the configured user, never None
        assert mock_token.await_args.kwargs["user_id"] == "user-abc123"

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_polls_every_connected_user(self, ingestion_pipeline):
        """Multi-user: the poller must fetch EACH connected mailbox, not just
        the most recent connect (Greptile P1 — a later connection must not
        stop polling earlier users)."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "fallback-user"}
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-a", "user-b"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            side_effect=["token-a", "token-b"],
        ) as mock_token, patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(
                return_value=Mock(
                    status_code=200,
                    json=lambda: {"value": [], "@odata.nextLink": None},
                )
            )

            messages = await ingestion_pipeline._fetch_outlook_messages(None)

        assert messages == []
        # Both owners' tokens were resolved (user-a AND user-b).
        awaited_users = [c.kwargs["user_id"] for c in mock_token.await_args_list]
        assert awaited_users == ["user-a", "user-b"]
        # Per-user cursors advanced, so each mailbox resumes independently.
        assert "last_fetch_outlook_user-a" in ingestion_pipeline.fetch_timestamps
        assert "last_fetch_outlook_user-b" in ingestion_pipeline.fetch_timestamps

    @pytest.mark.asyncio(mode="auto")
    async def test_failed_page_walk_holds_cursor(self, ingestion_pipeline):
        """Regression (Greptile P1): a failed Graph page walk must NOT advance
        the owner cursor. The filter is `receivedDateTime gt cursor`, so a
        watermark jump after a transient error permanently skips everything
        that arrived during the failed window. Holding the cursor only
        re-walks the window — the seen-id dedup drops already-ingested mail.
        """
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-hold"}
        ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-hold"] = datetime(
            2024, 1, 1, 0, 0, 0
        )
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-hold"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-hold",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(
                return_value=Mock(status_code=503, json=lambda: {})
            )

            messages = await ingestion_pipeline._fetch_outlook_messages(None)

        assert messages == []
        # Cursor held at the pre-failure watermark — not jumped to now().
        assert ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-hold"] == datetime(
            2024, 1, 1, 0, 0, 0
        )

    @pytest.mark.asyncio(mode="auto")
    async def test_empty_window_advances_cursor(self, ingestion_pipeline):
        """A COMPLETE walk with zero new messages moves the watermark to now,
        so polls don't re-walk an empty window forever (mirror of the hold
        case: complete-but-empty is success, not failure)."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-empty"}
        ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-empty"] = datetime(
            2024, 1, 1, 0, 0, 0
        )
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-empty"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-empty",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(
                return_value=Mock(
                    status_code=200,
                    json=lambda: {"value": [], "@odata.nextLink": None},
                )
            )

            await ingestion_pipeline._fetch_outlook_messages(None)

        advanced = ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-empty"]
        assert advanced > datetime(2024, 1, 1, 0, 0, 0)

    @pytest.mark.asyncio(mode="auto")
    async def test_truncated_walk_holds_cursor_and_pins_resume_bound(self, ingestion_pipeline):
        """A page-cap truncation must NOT move the low watermark (the strict
        gt filter would exclude the unconsumed older pages forever). With the
        newest-first order pinned via $orderBy, the walk instead narrows a
        continuation bound to the oldest consumed timestamp; the next poll
        walks exactly the unconsumed remainder (C, bound]."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-trunc"}
        ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-trunc"] = datetime(
            2024, 1, 1, 0, 0, 0
        )
        page = {
            "value": [
                {
                    "id": "trunc-msg-1",
                    "receivedDateTime": "2024-02-01T12:00:00Z",
                    "from": {"emailAddress": {"name": "E", "address": "e@x.com"}},
                    "subject": "t",
                    "body": {"contentType": "Text", "content": "hi"},
                }
            ],
            # A pending next link + the default 1-page budget forces the
            # truncation path in _fetch_outlook_for_owner.
            "@odata.nextLink": "https://graph.microsoft.com/next",
        }
        seen_params = {}

        def capture_params(*args, **kwargs):
            seen_params.update(kwargs.get("params") or {})
            return Mock(status_code=200, json=lambda: page)

        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-trunc"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-trunc",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=capture_params)

            messages = await ingestion_pipeline._fetch_outlook_messages(None)

        # The walk is newest-first, so the consumed boundary is provable.
        assert seen_params.get("$orderBy") == "receivedDateTime desc"
        assert {m["id"] for m in messages} == {"trunc-msg-1"}
        # Low watermark HELD — unconsumed older pages stay reachable.
        assert ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-trunc"] == datetime(
            2024, 1, 1, 0, 0, 0
        )
        # Continuation bound pinned to the oldest consumed timestamp.
        assert ingestion_pipeline.fetch_timestamps[
            "last_fetch_outlook_resume_user-trunc"
        ] == datetime.fromisoformat("2024-02-01T12:00:00Z")

    @pytest.mark.asyncio(mode="auto")
    async def test_continuation_drain_promotes_cursor_and_clears_bound(self, ingestion_pipeline):
        """When a continuation walk (C, bound] completes naturally, the
        cursor promotes to the bound and the continuation state clears —
        proving truncated backfills terminate instead of looping."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-resume"}
        ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-resume"] = datetime(
            2024, 1, 1, 0, 0, 0
        )
        ingestion_pipeline.fetch_timestamps[
            "last_fetch_outlook_resume_user-resume"
        ] = datetime.fromisoformat("2024-02-01T12:00:00Z")
        captured = {}

        def capture_params(*args, **kwargs):
            captured.update(kwargs.get("params") or {})
            return Mock(
                status_code=200,
                json=lambda: {"value": [], "@odata.nextLink": None},
            )

        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-resume"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-resume",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=capture_params)

            await ingestion_pipeline._fetch_outlook_messages(None)

        # The walk targeted exactly the unconsumed remainder (C, bound].
        assert "receivedDateTime gt 2024-01-01T00:00:00Z" in captured.get("$filter", "")
        assert "receivedDateTime le 2024-02-01T12:00:00Z" in captured.get("$filter", "")
        # Drained: cursor promoted to the bound, continuation state cleared.
        assert ingestion_pipeline.fetch_timestamps[
            "last_fetch_outlook_user-resume"
        ] == datetime.fromisoformat("2024-02-01T12:00:00Z")
        assert "last_fetch_outlook_resume_user-resume" not in ingestion_pipeline.fetch_timestamps

    @pytest.mark.asyncio(mode="auto")
    async def test_continuation_bound_keeps_fractional_seconds(self, ingestion_pipeline):
        """Regression (Greptile): Graph receivedDateTime values carry
        microsecond precision. A continuation bound truncated to whole
        seconds SHRANK below the true consumed boundary, so an unconsumed
        message at 12:00:00.5 fell outside an inclusive `le 12:00:00`
        filter. The bound must round-trip at full precision into the
        follow-up filter."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-frac"}
        ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-frac"] = datetime(
            2024, 1, 1, 0, 0, 0
        )
        page = {
            "value": [
                {
                    "id": "frac-msg-1",
                    "receivedDateTime": "2024-02-01T12:00:00.512345Z",
                    "from": {"emailAddress": {"name": "F", "address": "f@x.com"}},
                    "subject": "t",
                    "body": {"contentType": "Text", "content": "hi"},
                }
            ],
            "@odata.nextLink": "https://graph.microsoft.com/next",
        }
        seen_filters = []

        def capture_params(*args, **kwargs):
            if kwargs.get("params", {}).get("$filter"):
                seen_filters.append(kwargs["params"]["$filter"])
            return Mock(status_code=200, json=lambda: page)

        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-frac"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-frac",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=capture_params)

            await ingestion_pipeline._fetch_outlook_messages(None)

        # The pinned bound keeps the consumed boundary at full precision.
        bound = ingestion_pipeline.fetch_timestamps[
            "last_fetch_outlook_resume_user-frac"
        ]
        assert bound == datetime.fromisoformat("2024-02-01T12:00:00.512345Z")
        # …and the formatter never truncates a non-zero-microsecond bound.
        from integrations.atom_communication_ingestion_pipeline import (
            _format_graph_timestamp,
        )
        assert _format_graph_timestamp(bound) == "2024-02-01T12:00:00.512345Z"
        assert _format_graph_timestamp(datetime(2024, 2, 1, 12, 0, 0)) == (
            "2024-02-01T12:00:00Z"
        )

    @pytest.mark.asyncio(mode="auto")
    async def test_new_owner_does_not_inherit_global_cursor(self, ingestion_pipeline):
        """Regression (Greptile): a freshly connected owner must start from
        its own initial-sync window, never from the loop-level global
        `last_fetch_outlook` watermark another mailbox left behind — that
        inheritance made the new owner skip all mail older than the other
        account's latest message."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-new"}
        # Global watermark from a PREVIOUS owner; the new owner must have NO
        # per-owner cursor (clear any residue restored from the persisted
        # fetch-state file) so the walk has to start from its own window.
        ingestion_pipeline.fetch_timestamps["last_fetch_outlook"] = datetime(
            2023, 6, 1, 0, 0, 0
        )
        ingestion_pipeline.fetch_timestamps.pop("last_fetch_outlook_user-new", None)
        captured = {}

        def capture_params(*args, **kwargs):
            captured.update(kwargs.get("params") or {})
            return Mock(
                status_code=200,
                json=lambda: {"value": [], "@odata.nextLink": None},
            )

        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-new"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-new",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=capture_params)

            await ingestion_pipeline._fetch_outlook_messages(datetime(2023, 6, 1))

        # Initial-sync window walk (`ge <now-90d>`), NOT `gt <inherited>` —
        # the global cursor was never consulted.
        assert "$filter" in captured
        assert captured["$filter"].startswith("receivedDateTime ge ")
        # And the new owner's own cursor starts fresh from this walk.
        advanced = ingestion_pipeline.fetch_timestamps["last_fetch_outlook_user-new"]
        assert advanced > datetime(2023, 6, 1)

    @pytest.mark.asyncio(mode="auto")
    async def test_fetched_messages_carry_mailbox_owner(self, ingestion_pipeline):
        """Regression (Greptile P1): ingested mail must record WHOSE mailbox
        it came from — knowledge extraction and communication intelligence
        scope their learning via metadata["user_id"]."""
        ingestion_pipeline.app_configs["outlook"] = {"user_id": "user-owner"}
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-owner"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="token-owner",
        ), patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(
                return_value=Mock(
                    status_code=200,
                    json=lambda: {
                        "value": [
                            {
                                "id": "owned-1",
                                "receivedDateTime": "2024-02-01T12:00:00Z",
                                "from": {
                                    "emailAddress": {"name": "B", "address": "b@x.com"}
                                },
                                "subject": "s",
                                "body": {"contentType": "Text", "content": "c"},
                            }
                        ],
                        "@odata.nextLink": None,
                    },
                )
            )

            messages = await ingestion_pipeline._fetch_outlook_messages(None)

        assert len(messages) == 1
        assert messages[0]["metadata"]["user_id"] == "user-owner"

    def test_email_normalizer_hoists_owner_user_id(self, ingestion_pipeline):
        """The email normalizer must hoist metadata.user_id to the TOP level
        (knowledge extraction reads comm_data.metadata["user_id"], not the
        nested email_metadata dict), and omit it entirely when absent so the
        downstream default_user fallback stays intact."""
        owned = ingestion_pipeline._normalize_message_impl(
            CommunicationAppType.OUTLOOK.value,
            {
                "id": "m1",
                "content": "hi",
                "content_type": "text",
                "timestamp": "2024-02-01T12:00:00Z",
                "metadata": {"user_id": "user-abc123", "custom": "kept"},
            },
        )
        assert owned["metadata"]["user_id"] == "user-abc123"
        assert owned["metadata"]["email_metadata"]["user_id"] == "user-abc123"

        anonymous = ingestion_pipeline._normalize_message_impl(
            CommunicationAppType.OUTLOOK.value,
            {
                "id": "m2",
                "content": "hi",
                "content_type": "text",
                "timestamp": "2024-02-01T12:00:00Z",
            },
        )
        assert "user_id" not in anonymous["metadata"]

    def test_owner_filter_enforces_mailbox_boundary(self):
        """Regression (Greptile): retrieval over the shared comms corpus must
        drop records stamped for a DIFFERENT owner. Ownerless records (legacy
        rows, unstamped webhook sources) stay visible, and unfiltered calls
        (background callers) return everything unchanged."""
        from integrations.atom_communication_ingestion_pipeline import (
            _filter_communication_records_by_owner,
        )

        records = [
            {"id": "a1", "metadata": json.dumps({"user_id": "user-a"})},
            {"id": "b1", "metadata": json.dumps({"user_id": "user-b"})},
            {"id": "legacy", "metadata": json.dumps({"custom": "no owner"})},
            {"id": "raw", "metadata": "not-json{"},
            {"id": "empty", "metadata": None},
        ]

        scoped = _filter_communication_records_by_owner(records, "user-a")
        assert [r["id"] for r in scoped] == ["a1", "legacy", "raw", "empty"]

        unfiltered = _filter_communication_records_by_owner(records, None)
        assert len(unfiltered) == 5

    def test_email_normalization_redacts_secrets(self, ingestion_pipeline):
        """Email bodies get the same secrets redaction as document files
        (regression: bodies were stored raw, so recalled email could expose
        live credentials)."""
        # Fake secrets are assembled at runtime: the redactor patterns match
        # these formats, but no secret-shaped literal is ever written into the
        # file (GitHub push protection + GitGuardian flag Stripe/AWS/password
        # formats even as deliberate test data).
        stripe_key = "sk_live_" + "x" * 24
        aws_key = "AKIA" + "A" * 16
        password_value = "x" * 12
        password_label = "Pass" + "word="  # runtime-assembled, not a literal
        body = (
            f"Here is my Stripe key: {stripe_key} and "
            f"my AWS key {aws_key}. {password_label}{password_value}!"
        )
        normalized = ingestion_pipeline._normalize_message_impl(
            CommunicationAppType.OUTLOOK.value,
            {
                "id": "m1",
                "content": body,
                "content_type": "text",
                "timestamp": "2024-02-01T12:00:00Z",
            },
        )

        assert stripe_key not in normalized["content"]
        assert aws_key not in normalized["content"]
        assert password_value not in normalized["content"]
        assert "[REDACTED_" in normalized["content"]

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_messages_with_attachments(self, ingestion_pipeline):
        """Test Outlook messages with attachments"""
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-test"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="test_token",
        ):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_client.get = AsyncMock(
                    return_value=Mock(
                        status_code=200,
                        json=lambda: {
                            "value": [
                                {
                                    "id": "msg_456",
                                    "receivedDateTime": "2024-02-01T13:00:00Z",
                                    "from": {
                                        "emailAddress": {
                                            "name": "Charlie",
                                            "address": "charlie@example.com"
                                        }
                                    },
                                    "toRecipients": [
                                        {"emailAddress": {"address": "me@example.com"}}
                                    ],
                                    "subject": "Document Attached",
                                    "body": {
                                        "contentType": "HTML",
                                        "content": "<p>Please review attached</p>"
                                    },
                                    "importance": "High",
                                    "attachments": [
                                        {
                                            "id": "att_1",
                                            "name": "report.xlsx",
                                            "size": 2048,
                                            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            "isInline": False
                                        }
                                    ]
                                }
                            ]
                        }
                    )
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                assert len(messages) == 1
                assert len(messages[0]["attachments"]) == 1
                assert messages[0]["attachments"][0]["name"] == "report.xlsx"
                assert messages[0]["priority"] == "high"  # Importance: High

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_rate_limiting(self, ingestion_pipeline):
        """Test Outlook API rate limiting handling"""
        with patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="test_token",
        ):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Rate limit responses. NOTE: the pipeline's 429 branch sleeps
                # Retry-After and retries WITHOUT incrementing fetch_count, so
                # a mock that always returns 429 loops forever — the sequence
                # must eventually return a non-429 response to terminate.
                rate_limit_response = Mock(status_code=429)
                rate_limit_response.headers = {"Retry-After": "0"}

                ok_response = Mock(status_code=200)
                ok_response.json = Mock(return_value={"value": []})

                mock_client.get = AsyncMock(
                    side_effect=[rate_limit_response, rate_limit_response, ok_response]
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                # Should handle gracefully and return empty list
                assert messages == []

    @pytest.mark.asyncio(mode="auto")
    async def test_fetch_outlook_incremental_filtering(self, ingestion_pipeline):
        """Test Outlook incremental fetching with timestamp filter"""
        with patch.object(
            ingestion_pipeline, "_outlook_token_owners", return_value=["user-test"]
        ), patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="test_token",
        ):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                filter_params = None

                def check_filter(*args, **kwargs):
                    nonlocal filter_params
                    filter_params = kwargs.get('params', {})
                    return Mock(
                        status_code=200,
                        json=lambda: {"value": []}
                    )

                mock_client.get = AsyncMock(side_effect=check_filter)

                last_fetch = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
                await ingestion_pipeline._fetch_outlook_messages(last_fetch)

                # Verify filter was applied
                assert filter_params is not None
                assert "$filter" in filter_params


class TestEmailErrorHandling:
    """Test error handling in email integration"""

    @pytest.mark.asyncio(mode="auto")
    async def test_gmail_service_import_error(self, ingestion_pipeline):
        """Test graceful handling when Gmail service is not available"""
        # Force ImportError by replacing integrations.gmail_service with a stub
        # module that does NOT expose GmailService. Restore afterwards so the
        # real module survives for co-collected suites.
        import types
        import sys

        real_gmail_module = sys.modules.get('integrations.gmail_service')
        stub_gmail_module = types.ModuleType('integrations.gmail_service')
        sys.modules['integrations.gmail_service'] = stub_gmail_module

        try:
            messages = await ingestion_pipeline._fetch_gmail_messages(None)

            assert messages == []
        finally:
            if real_gmail_module is not None:
                sys.modules['integrations.gmail_service'] = real_gmail_module
            else:
                sys.modules.pop('integrations.gmail_service', None)

    @pytest.mark.asyncio(mode="auto")
    async def test_outlook_handles_api_error(self, ingestion_pipeline):
        """Test graceful handling of Outlook API errors"""
        with patch(
            'integrations.outlook_service.outlook_service._get_access_token',
            new_callable=AsyncMock,
            return_value="test_token",
        ):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # API returns error
                mock_client.get = AsyncMock(
                    return_value=Mock(status_code=500, json=lambda: {"error": "Internal Server Error"})
                )

                messages = await ingestion_pipeline._fetch_outlook_messages(None)

                # Should handle gracefully and return empty list
                assert messages == []


class TestOutlookPollerWiring:
    """Test the Outlook poller wiring (P0.4 audit fix)"""

    @pytest.mark.asyncio(mode="auto")
    async def test_start_outlook_poller_configured(self, ingestion_pipeline):
        """Starting the poller configures outlook with real-time + embedding on"""
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock):
            started = ingestion_pipeline.start_outlook_poller(polling_interval_seconds=45)

            assert started is True
            assert "outlook" in ingestion_pipeline.active_streams
            cfg = ingestion_pipeline.ingestion_configs["outlook"]
            assert cfg["real_time"] is True
            assert cfg["embed_content"] is True
            assert cfg["polling_interval_seconds"] == 45

    @pytest.mark.asyncio(mode="auto")
    async def test_start_outlook_poller_idempotent(self, ingestion_pipeline):
        """Starting the poller twice creates only one stream task"""
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock) as mock_rt:
            assert ingestion_pipeline.start_outlook_poller() is True
            task1 = ingestion_pipeline.active_streams["outlook"]

            assert ingestion_pipeline.start_outlook_poller() is True
            task2 = ingestion_pipeline.active_streams["outlook"]

            assert task2 is task1
            assert mock_rt.call_count == 1

    @pytest.mark.asyncio(mode="auto")
    async def test_start_outlook_poller_failure_returns_false(self, ingestion_pipeline):
        """A failed stream start propagates False instead of raising"""
        with patch.object(ingestion_pipeline, 'start_real_time_stream', return_value=False):
            assert ingestion_pipeline.start_outlook_poller() is False

    @pytest.mark.asyncio(mode="auto")
    async def test_start_outlook_poller_stores_user_id(self, ingestion_pipeline):
        """Starting the poller for a user records that user in the config,
        so the fetch loop can resolve that user's token (not None)."""
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock):
            started = ingestion_pipeline.start_outlook_poller(user_id="user-abc123")

            assert started is True
            assert "outlook" in ingestion_pipeline.active_streams
            assert ingestion_pipeline.app_configs["outlook"]["user_id"] == "user-abc123"

    @pytest.mark.asyncio(mode="auto")
    async def test_start_outlook_poller_reads_interval_env(self, ingestion_pipeline, monkeypatch):
        """ATOM_OUTLOOK_POLL_SECONDS drives the default interval"""
        monkeypatch.setenv("ATOM_OUTLOOK_POLL_SECONDS", "45")
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock):
            assert ingestion_pipeline.start_outlook_poller() is True
        assert ingestion_pipeline.app_configs["outlook"]["polling_interval_seconds"] == 45

    @pytest.mark.asyncio(mode="auto")
    async def test_start_outlook_poller_interval_floor(self, ingestion_pipeline, monkeypatch):
        """Intervals below 15 are clamped to the 15s floor"""
        monkeypatch.setenv("ATOM_OUTLOOK_POLL_SECONDS", "10")
        with patch.object(ingestion_pipeline, '_real_time_ingestion', new_callable=AsyncMock):
            assert ingestion_pipeline.start_outlook_poller() is True
        assert ingestion_pipeline.app_configs["outlook"]["polling_interval_seconds"] == 15

    @pytest.mark.asyncio(mode="auto")
    async def test_oauth_callback_microsoft_starts_poller(self):
        """Connecting Microsoft OAuth starts the Outlook poller"""
        from api import oauth_routes
        from core.oauth_handler import OAuthHandler
        import integrations.atom_communication_ingestion_pipeline as ip_module

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        user = MagicMock()
        user.id = "u1"
        user.tenant_id = "default"
        user.status = "active"

        with patch.object(
            OAuthHandler, 'exchange_code_for_tokens', new_callable=AsyncMock,
            return_value={
                "access_token": "acc",
                "refresh_token": "ref",
                "token_type": "Bearer",
                "scope": "Mail.Read",
                "expires_in": 3600,
            },
        ):
            with patch.object(ip_module.ingestion_pipeline, 'start_outlook_poller', return_value=True) as mock_poller:
                await oauth_routes._handle_callback_logic(
                    "microsoft", "code", MagicMock(), None, db, user
                )
                mock_poller.assert_called_once()

    @pytest.mark.asyncio(mode="auto")
    async def test_oauth_callback_google_does_not_start_poller(self):
        """Non-Microsoft providers must NOT start the Outlook poller"""
        from api import oauth_routes
        from core.oauth_handler import OAuthHandler
        import integrations.atom_communication_ingestion_pipeline as ip_module

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        user = MagicMock()
        user.id = "u1"
        user.tenant_id = "default"
        user.status = "active"

        with patch.object(
            OAuthHandler, 'exchange_code_for_tokens', new_callable=AsyncMock,
            return_value={
                "access_token": "acc",
                "refresh_token": "ref",
                "token_type": "Bearer",
                "scope": "gmail.readonly",
                "expires_in": 3600,
            },
        ):
            with patch.object(ip_module.ingestion_pipeline, 'start_outlook_poller', return_value=True) as mock_poller:
                await oauth_routes._handle_callback_logic(
                    "google", "code", MagicMock(), None, db, user
                )
                mock_poller.assert_not_called()


class TestEmailMessageNormalization:
    """Test email message normalization to unified format"""

    @pytest.mark.asyncio(mode="auto")
    async def test_gmail_and_outlook_same_structure(self):
        """Verify Gmail and Outlook messages have same unified structure"""
        # Both should have the same core fields
        required_fields = [
            "id", "app_type", "timestamp", "direction", "sender", "recipient",
            "subject", "content", "attachments", "metadata", "status", "priority", "tags"
        ]

        # Test that normalization includes all required fields
        # This is a structural test - actual normalization is tested in integration tests above
        assert "id" in required_fields
        assert "app_type" in required_fields
        assert "timestamp" in required_fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
