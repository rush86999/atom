"""
Discord ingestion parity (P0.4 audit §7 follow-up): poller branch + multi-entity.

RED:
  - `_fetch_new_messages("discord")` falls into the else branch ("No polling
    implementation") — there is no `_fetch_discord_messages`.
  - `"discord" not in COMMUNICATION_INTEGRATIONS` → no multi-entity extraction
    for discord queue records (gmail/teams/slack all have it).

Contracts pinned here:
  - dispatch: `_fetch_new_messages("discord")` routes to the new fetcher.
  - fail-closed: no bot token anywhere -> [] without raising.
  - happy path: guilds -> text channels (type 0) -> channel messages are
    normalized to comm records ({id, content, author, channel_id, timestamp,
    direction="inbound", source_app="discord"}), filtered to messages newer
    than ``last_fetch`` when one is given.
  - multi-entity: discord ∈ MULTI_ENTITY_INTEGRATIONS.
  - normalize: `ingest_message`-style `_normalize_message("discord", …)`
    preserves content for a transformer-shaped record.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.integration_constants import (
    COMMUNICATION_INTEGRATIONS,
    MULTI_ENTITY_INTEGRATIONS,
)
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationIngestionPipeline,
)


def _pipeline():
    return CommunicationIngestionPipeline(MagicMock())


def _discord_msg(mid, mins_ago, content="standup notes from the channel"):
    ts = datetime.now(timezone.utc) - timedelta(minutes=mins_ago)
    return {
        "id": mid,
        "content": f"{content} #{mid}",
        "author": {"username": "devops"},
        "channel_id": "ch_1",
        "timestamp": ts.isoformat(),
    }


class TestDiscordPollerDispatch:
    @pytest.mark.asyncio
    async def test_fetch_new_messages_dispatches_to_discord_fetcher(self):
        pipe = _pipeline()
        fetched = [_discord_msg("m1", 5)]
        with patch.object(
            pipe, "_fetch_discord_messages", new=AsyncMock(return_value=fetched)
        ) as fetcher:
            result = await pipe._fetch_new_messages("discord")
        fetcher.assert_awaited_once()
        assert result == fetched

    @pytest.mark.asyncio
    async def test_fetch_discord_messages_fail_closed_without_token(self):
        pipe = _pipeline()
        with patch.dict("os.environ", {}, clear=False):
            import os

            env = dict(os.environ)
            env.pop("DISCORD_BOT_TOKEN", None)
            with patch.dict("os.environ", env, clear=True):
                with patch(
                    "integrations.discord_service.DiscordService.get_user_guilds",
                    new=AsyncMock(side_effect=AssertionError("must not be called")),
                ):
                    result = await pipe._fetch_discord_messages(None)
        assert result == []


class TestDiscordFetcherHappyPath:
    @pytest.mark.asyncio
    async def test_guilds_channels_messages_normalized(self):
        pipe = _pipeline()
        old_msg = _discord_msg("old", 600)
        new_msgs = [_discord_msg("n1", 5), _discord_msg("n2", 2)]

        svc = MagicMock()
        svc.bot_token = "tok"
        svc.get_user_guilds = AsyncMock(return_value=[{"id": "g1"}])
        svc.get_guild_channels = AsyncMock(
            return_value=[
                {"id": "ch_1", "type": 0, "name": "general"},
                {"id": "ch_voice", "type": 2, "name": "voice"},  # skipped
            ]
        )
        svc.get_channel_messages = AsyncMock(return_value=[old_msg] + new_msgs)

        last_fetch = datetime.now(timezone.utc) - timedelta(hours=1)
        with patch("integrations.discord_service.DiscordService", return_value=svc), \
             patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "tok"}):
            result = await pipe._fetch_discord_messages(last_fetch)

        ids = [m["id"] for m in result]
        assert ids == ["n1", "n2"]  # old message filtered by last_fetch
        for m in result:
            assert m["source_app"] == "discord"
            assert m["direction"] == "inbound"
            assert m["author"] == "devops"
            assert m["channel_id"] == "ch_1"

    @pytest.mark.asyncio
    async def test_api_errors_degrade_to_empty(self):
        pipe = _pipeline()
        svc = MagicMock()
        svc.bot_token = "tok"
        svc.get_user_guilds = AsyncMock(side_effect=RuntimeError("api down"))
        with patch("integrations.discord_service.DiscordService", return_value=svc), \
             patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "tok"}):
            result = await pipe._fetch_discord_messages(None)
        assert result == []


class TestDiscordMultiEntityParity:
    def test_discord_in_communication_integrations(self):
        assert "discord" in COMMUNICATION_INTEGRATIONS

    def test_discord_in_multi_entity_integrations(self):
        assert "discord" in MULTI_ENTITY_INTEGRATIONS


class TestDiscordNormalizeContent:
    def test_normalize_preserves_transformer_content(self):
        pipe = _pipeline()
        record = {
            "type": "discord_message",
            "id": "dc_1",
            "content": "deploy window shifted to friday evening",
            "author": "devops",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "message_created",
        }
        normalized = pipe._normalize_message("discord", record)
        assert normalized["content"] == "deploy window shifted to friday evening"