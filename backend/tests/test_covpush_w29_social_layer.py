"""Coverage wave 29 — core/agent_social_layer.py (TDD, mocked db + redactor).

Drives the social feed: post creation (maturity governance, type mapping,
PII redaction, mentions), feed queries (filters, cursor pagination),
reactions, trending, replies, channels, episode-linked posts + episode
context, positive-interaction tracking, reputation (score/percentile/
trend), graduation milestones and rate limits — zero LLM, zero spend.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent_social_layer import AgentSocialLayer


def make_post(**kw):
    defaults = dict(
        id="post-1", author_type="agent", author_id="ag-1", post_type="status",
        content="hello world", post_metadata={}, reactions=[],
        created_at=datetime.now(timezone.utc))
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_agent(status="intern", **kw):
    defaults = dict(id="ag-1", name="Agent One", category="engineering",
                    status=status, tenant_id="t-1", user_id="u-1",
                    confidence_score=0.8)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_db(**overrides):
    db = MagicMock()
    for k, v in overrides.items():
        setattr(db, k, v)
    return db


class TestCreatePost:
    async def test_agent_student_blocked(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="student")
        layer = AgentSocialLayer()
        with pytest.raises(PermissionError, match="STUDENT"):
            await layer.create_post("agent", "ag-1", "A", "status", "hi", db=db)

    async def test_agent_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        layer = AgentSocialLayer()
        with pytest.raises(PermissionError, match="not found"):
            await layer.create_post("agent", "ghost", "A", "status", "hi", db=db)

    async def test_no_db_for_agent(self):
        layer = AgentSocialLayer()
        with pytest.raises(PermissionError, match="Database session"):
            await layer.create_post("agent", "ag-1", "A", "status", "hi", db=None)

    async def test_invalid_post_type(self):
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="Invalid post_type"):
            await layer.create_post("human", "u1", "U", "bogus_type", "hi", db=make_db())

    async def test_type_mapping(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch("core.agent_communication.agent_event_bus.broadcast_post",
                   new=AsyncMock()) as broadcast:
            post = await layer.create_post(
                "agent", "ag-1", "A", "command", "do the thing", db=db)
        assert post["post_type"] == "command"  # requested type preserved
        broadcast.assert_called_once()

    async def test_pii_redaction_with_secrets(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        layer = AgentSocialLayer()
        redactor = MagicMock()
        redactor.redact.return_value = SimpleNamespace(
            redacted_text="REDACTED", has_secrets=True,
            redactions=[{"type": "EMAIL"}])
        with patch("core.agent_social_layer.get_pii_redactor", return_value=redactor), \
             patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch("core.agent_communication.agent_event_bus.broadcast_post",
                   new=AsyncMock()):
            post = await layer.create_post(
                "human", "u1", "U", "status", "email a@b.c here", db=db)
        assert post["content"] == "REDACTED"

    async def test_pii_redaction_failure_tolerated(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.get_pii_redactor",
                   side_effect=RuntimeError("redactor down")), \
             patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch("core.agent_communication.agent_event_bus.broadcast_post",
                   new=AsyncMock()):
            post = await layer.create_post(
                "human", "u1", "U", "status", "original text", db=db)
        assert post["content"] == "original text"

    async def test_skip_redaction(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.get_pii_redactor") as redactor, \
             patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch("core.agent_communication.agent_event_bus.broadcast_post",
                   new=AsyncMock()):
            await layer.create_post(
                "human", "u1", "U", "status", "keep secret@x", db=db,
                skip_pii_redaction=True)
        redactor.assert_not_called()

    async def test_mentions_and_metadata(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch("core.agent_communication.agent_event_bus.broadcast_post",
                   new=AsyncMock()):
            post = await layer.create_post(
                "human", "u1", "U", "status", "hi @agent",
                mentioned_agent_ids=["ag-2"], mentioned_user_ids=["u2"],
                mentioned_episode_ids=["ep-1"], mentioned_task_ids=["t1"],
                channel_id="ch-1", channel_name="general",
                reply_to_id="post-0", auto_generated=True, db=db)
        assert post["mentioned_agent_ids"] == ["ag-2"]
        assert post["channel_id"] == "ch-1"
        assert post["auto_generated"] is True

    async def test_agent_tenant_id_used(self):
        db = make_db()
        agent = make_agent(tenant_id="tenant-9")
        db.query.return_value.filter.return_value.first.return_value = agent
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        layer = AgentSocialLayer()
        captured = {}
        with patch("core.agent_social_layer.SocialPost",
                   lambda **kw: captured.update(kw) or make_post(**kw)), \
             patch("core.agent_communication.agent_event_bus.broadcast_post",
                   new=AsyncMock()):
            await layer.create_post(
                "agent", "ag-1", "A", "status", "hi", db=db)
        assert captured["tenant_id"] == "tenant-9"


class TestGetFeed:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        feed = await layer.get_feed("u1", db=None)
        assert feed == {"posts": [], "total": 0}

    async def test_with_filters(self):
        db = make_db()
        post = make_post(post_metadata={"sender_name": "A", "is_public": True})
        f4 = db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value
        f4.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [post]
        f4.count.return_value = 1
        layer = AgentSocialLayer()
        feed = await layer.get_feed(
            "u1", post_type="status", sender_filter="ag-1",
            channel_id="ch-1", is_public=True, db=db)
        assert feed["total"] == 1
        assert feed["posts"][0]["sender_name"] == "A"
        assert feed["posts"][0]["post_type"] == "status"


class TestReactions:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="Database session required"):
            await layer.add_reaction("p1", "u1", "👍", db=None)

    async def test_post_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="not found"):
            await layer.add_reaction("p1", "u1", "👍", db=db)

    async def test_reaction_dict_post(self):
        db = make_db()
        post = make_post(reactions={"👍": 2})
        db.query.return_value.filter.return_value.first.return_value = post
        layer = AgentSocialLayer()
        with patch("core.agent_communication.agent_event_bus.publish", new=AsyncMock()) as pub:
            reactions = await layer.add_reaction("p1", "u1", "👍", db=db)
        assert reactions == {"👍": 3}
        pub.assert_called_once()

    async def test_reaction_list_post(self):
        db = make_db()
        post = make_post(reactions=[
            SimpleNamespace(emoji="❤️"),
            SimpleNamespace(emoji="❤️"),
            SimpleNamespace(emoji=None),
        ])
        db.query.return_value.filter.return_value.first.return_value = post
        layer = AgentSocialLayer()
        with patch("core.agent_communication.agent_event_bus.publish", new=AsyncMock()):
            reactions = await layer.add_reaction("p1", "u1", "👍", db=db)
        assert reactions == {"❤️": 2, "👍": 1}


class TestTrending:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        assert await layer.get_trending_topics(db=None) == []

    async def test_mentions_counted(self):
        db = make_db()
        db.query.return_value.filter.return_value.all.return_value = [
            make_post(post_metadata={"mentioned_agent_ids": ["ag-2", "ag-2"],
                                     "mentioned_user_ids": ["u2"],
                                     "mentioned_episode_ids": ["ep-1"],
                                     "mentioned_task_ids": ["t1"]}),
            make_post(post_metadata={"mentioned_agent_ids": ["ag-2"]}),
        ]
        layer = AgentSocialLayer()
        topics = await layer.get_trending_topics(hours=24, db=db)
        by_topic = {t["topic"]: t["mentions"] for t in topics}
        assert by_topic["agent:ag-2"] == 3
        assert by_topic["user:u2"] == 1
        assert by_topic["episode:ep-1"] == 1
        assert by_topic["task:t1"] == 1
        assert len(topics) <= 10


class TestReplies:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        assert await layer.get_replies("p1", db=None) == {"replies": [], "total": 0}

    async def test_get_replies(self):
        db = make_db()
        reply = make_post(id="r1", post_metadata={"sender_name": "B"})
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [reply]
        layer = AgentSocialLayer()
        result = await layer.get_replies("p1", db=db)
        assert result["total"] == 1
        assert result["replies"][0]["sender_name"] == "B"

    async def test_add_reply_no_db(self):
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="Database session required"):
            await layer.add_reply("p1", "human", "u1", "U", "hi", db=None)

    async def test_add_reply_parent_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="not found"):
            await layer.add_reply("p1", "human", "u1", "U", "hi", db=db)

    async def test_add_reply_student_blocked(self):
        db = make_db()
        parent = make_post()
        db.query.return_value.filter.return_value.first.side_effect = [parent, make_agent(status="STUDENT")]
        layer = AgentSocialLayer()
        with pytest.raises(PermissionError, match="STUDENT"):
            await layer.add_reply("p1", "agent", "ag-1", "A", "hi", db=db)

    async def test_add_reply_success(self):
        db = make_db()
        parent = make_post()
        db.query.return_value.filter.return_value.first.return_value = parent
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post", new=AsyncMock(return_value={"id": "r1"})) as cp:
            reply = await layer.add_reply("p1", "human", "u1", "U", "hi", db=db)
        assert reply == {"id": "r1"}
        assert cp.call_args.kwargs["reply_to_id"] == "p1"


class TestChannels:
    async def test_create_channel_no_db(self):
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="Database session required"):
            await layer.create_channel("c1", "name", "u1", db=None)

    async def test_create_channel_existing(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="c1", name="existing")
        layer = AgentSocialLayer()
        result = await layer.create_channel("c1", "name", "u1", db=db)
        assert result["exists"] is True

    async def test_create_channel_new(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = MagicMock()
        db.commit = MagicMock()
        channel = SimpleNamespace(id="c1", name="general")
        channel_cls = MagicMock(return_value=channel)
        layer = AgentSocialLayer()
        with patch("core.models.Channel", channel_cls), \
             patch("core.agent_communication.agent_event_bus.publish", new=AsyncMock()):
            result = await layer.create_channel("c1", "general", "u1",
                                                display_name="General", db=db)
        assert result["created"] is True

    async def test_get_channels_no_db(self):
        layer = AgentSocialLayer()
        assert await layer.get_channels(db=None) == []

    async def test_get_channels(self):
        db = make_db()
        db.query.return_value.all.return_value = [
            SimpleNamespace(id="c1", name="general", display_name="General",
                            description="d", channel_type="general",
                            is_public=True, created_by="u1",
                            created_at=datetime.now(timezone.utc))]
        layer = AgentSocialLayer()
        channels = await layer.get_channels(db=db)
        assert channels[0]["id"] == "c1"


class TestCursorFeed:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        assert await layer.get_feed_cursor("u1", db=None) == {
            "posts": [], "next_cursor": None, "has_more": False}

    async def test_cursor_and_has_more(self):
        db = make_db()
        posts = [make_post(id=f"p{i}") for i in range(3)]
        query = db.query.return_value.filter.return_value
        query.order_by.return_value.limit.return_value.all.return_value = posts  # limit+1 = 4 → 3 posts, has_more False... use 4 posts
        layer = AgentSocialLayer()
        # 4 posts returned for limit=3 → has_more True, next_cursor from last
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = posts + [make_post(id="p3")]
        feed = await layer.get_feed_cursor("u1", cursor="2026-01-01T00:00:00:p1",
                                           limit=3, db=db)
        assert feed["has_more"] is True
        assert feed["next_cursor"] is not None
        assert len(feed["posts"]) == 3

    async def test_invalid_cursor_tolerated(self):
        db = make_db()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        layer = AgentSocialLayer()
        feed = await layer.get_feed_cursor("u1", cursor="not-a-date", db=db)
        assert feed["posts"] == []

    async def test_legacy_cursor(self):
        db = make_db()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        layer = AgentSocialLayer()
        feed = await layer.get_feed_cursor(
            "u1", cursor=datetime.now(timezone.utc).isoformat(), db=db)
        assert feed["posts"] == []


class TestEpisodeLinkedPosts:
    async def test_create_post_with_episode_no_db(self):
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post",
                          new=AsyncMock(return_value={"id": "p1"})) as cp:
            post = await layer.create_post_with_episode(
                "human", "u1", "U", "status", "hi", episode_ids=["ep-1"], db=None)
        assert post == {"id": "p1"}
        cp.assert_called_once()

    async def test_create_post_with_episode_retrieves(self):
        db = make_db()
        db.add = MagicMock()
        db.commit = MagicMock()
        retrieve_mock = AsyncMock(return_value=["ep-9"])
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post",
                          new=AsyncMock(return_value={"id": "p1"})), \
             patch.object(layer, "_retrieve_relevant_episodes", new=retrieve_mock), \
             patch("core.models.EpisodeSegment", lambda **kw: make_post(**kw)):
            await layer.create_post_with_episode(
                "agent", "ag-1", "A", "status", "hi", db=db)
        retrieve_mock.assert_called_once()

    async def test_create_post_with_episode_segment_failure_tolerated(self):
        db = make_db()
        db.add = MagicMock(side_effect=RuntimeError("db down"))
        db.commit = MagicMock()
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post",
                          new=AsyncMock(return_value={"id": "p1"})), \
             patch("core.models.EpisodeSegment", lambda **kw: make_post(**kw)):
            post = await layer.create_post_with_episode(
                "human", "u1", "U", "status", "hi", episode_ids=["ep-1"], db=db)
        assert post == {"id": "p1"}

    async def test_retrieve_relevant_episodes_no_db(self):
        layer = AgentSocialLayer()
        assert await layer._retrieve_relevant_episodes("ag-1", "content", db=None) == []

    async def test_retrieve_relevant_episodes_success(self):
        db = make_db()
        svc = MagicMock()
        svc.retrieve_episodes = AsyncMock(return_value=[
            SimpleNamespace(id="ep-1"), SimpleNamespace(id="ep-2")])
        with patch("core.episode_retrieval_service.EpisodeRetrievalService",
                   return_value=svc):
            layer = AgentSocialLayer()
            result = await layer._retrieve_relevant_episodes("ag-1", "content", db=db)
        assert result == ["ep-1", "ep-2"]

    async def test_retrieve_relevant_episodes_error(self):
        db = make_db()
        with patch("core.episode_retrieval_service.EpisodeRetrievalService",
                   side_effect=RuntimeError("retrieval down")):
            layer = AgentSocialLayer()
            assert await layer._retrieve_relevant_episodes("ag-1", "c", db=db) == []

    async def test_feed_with_episode_context(self):
        db = make_db()
        post = make_post(post_metadata={"mentioned_episode_ids": ["ep-1"]})
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [post]
        db.query.return_value.count.return_value = 1
        layer = AgentSocialLayer()
        with patch.object(layer, "_get_episode_summaries",
                          new=AsyncMock(return_value=[{"id": "ep-1", "title": "E"}])):
            feed = await layer.get_feed_with_episode_context(db=db)
        assert feed["posts"][0]["episode_context"] == [{"id": "ep-1", "title": "E"}]

    async def test_feed_with_episode_context_error(self):
        db = make_db()
        post = make_post(post_metadata={"mentioned_episode_ids": ["ep-1"]})
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [post]
        db.query.return_value.count.return_value = 1
        layer = AgentSocialLayer()
        with patch.object(layer, "_get_episode_summaries",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            feed = await layer.get_feed_with_episode_context(db=db)
        assert feed["posts"][0]["episode_context"] == []

    async def test_get_episode_summaries(self):
        db = make_db()
        ep = SimpleNamespace(id="ep-1", title="T", summary="S" * 50,
                             created_at=datetime.now(timezone.utc), agent_id="ag-1")
        db.query.return_value.filter.return_value.all.return_value = [ep]
        layer = AgentSocialLayer()
        summaries = await layer._get_episode_summaries(["ep-1"], db=db)
        assert summaries[0]["id"] == "ep-1"
        assert len(summaries[0]["summary"]) <= 200

    async def test_get_episode_summaries_error(self):
        db = make_db()
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("boom")
        layer = AgentSocialLayer()
        assert await layer._get_episode_summaries(["ep-1"], db=db) == []


class TestPositiveInteractions:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        await layer.track_positive_interaction("p1", "👍", db=None)  # no crash

    async def test_non_agent_post_skipped(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_post(author_type="human")
        layer = AgentSocialLayer()
        await layer.track_positive_interaction("p1", "👍", db=db)
        db.add.assert_not_called()

    async def test_negative_interaction_skipped(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_post()
        layer = AgentSocialLayer()
        with patch.object(layer, "_update_agent_reputation", new=AsyncMock()) as rep:
            await layer.track_positive_interaction("p1", "👎", db=db)
        rep.assert_not_called()

    async def test_positive_interaction_tracked(self):
        db = make_db()
        post = make_post()
        db.query.return_value.filter.return_value.first.return_value = post
        db.add = MagicMock()
        db.commit = MagicMock()
        layer = AgentSocialLayer()
        with patch.object(layer, "_update_agent_reputation", new=AsyncMock()) as rep, \
             patch("core.agent_graduation_service.AgentGraduationService") as grad_cls, \
             patch("core.models.AgentFeedback", lambda **kw: make_post(**kw)):
            grad_cls.return_value = MagicMock()
            await layer.track_positive_interaction("p1", "thanks!", user_id="u2", db=db)
        rep.assert_called_once()
        db.add.assert_called_once()

    async def test_graduation_service_import_error(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_post()
        db.add = MagicMock()
        db.commit = MagicMock()
        layer = AgentSocialLayer()
        with patch.object(layer, "_update_agent_reputation", new=AsyncMock()), \
             patch("core.agent_graduation_service.AgentGraduationService",
                   side_effect=ImportError("no grad")), \
             patch("core.models.AgentFeedback", lambda **kw: make_post(**kw)):
            await layer.track_positive_interaction("p1", "👍", db=db)  # no crash

    async def test_track_exception_tolerated(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
        layer = AgentSocialLayer()
        await layer.track_positive_interaction("p1", "👍", db=db)  # no crash

    def test_is_positive_interaction(self):
        layer = AgentSocialLayer()
        assert layer._is_positive_interaction("👍")
        assert layer._is_positive_interaction("love")
        assert layer._is_positive_interaction("thanks for the help")
        assert not layer._is_positive_interaction("👎")
        assert not layer._is_positive_interaction("meh")

    async def test_update_agent_reputation(self):
        layer = AgentSocialLayer()
        await layer._update_agent_reputation("ag-1", "👍", db=make_db())  # no crash


class TestReputation:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        result = await layer.get_agent_reputation("ag-1", db=None)
        assert result["reputation_score"] == 0

    async def test_full_reputation(self):
        db = make_db()
        posts = [
            make_post(id="p1", reactions=[SimpleNamespace()] * 3),
            make_post(id="p2", reactions={"👍": 2}),
            make_post(id="p3", reactions=[]),
        ]
        db.query.return_value.filter.return_value.all.return_value = posts
        db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = 2
        layer = AgentSocialLayer()
        with patch.object(layer, "_count_helpful_replies", new=AsyncMock(return_value=1)), \
             patch.object(layer, "_calculate_percentile_rank", new=AsyncMock(return_value=50.0)), \
             patch.object(layer, "_get_reputation_trend", new=AsyncMock(return_value=[])):
            result = await layer.get_agent_reputation("ag-1", db=db)
        assert result["total_reactions"] == 5
        assert result["helpful_replies"] == 1
        assert result["percentile_rank"] == 50.0
        assert result["reputation_score"] == min(100, 5 * 2 + 1 * 5 + 3 * 1)

    async def test_reputation_exception(self):
        db = make_db()
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("boom")
        layer = AgentSocialLayer()
        result = await layer.get_agent_reputation("ag-1", db=db)
        assert result["reputation_score"] == 0
        assert "error" in result

    async def test_count_helpful_replies(self):
        db = make_db()
        db.query.return_value.filter.return_value.count.return_value = 4
        layer = AgentSocialLayer()
        assert await layer._count_helpful_replies("ag-1", db=db) == 4

    async def test_percentile_rank(self):
        db = make_db()
        db.query.return_value.all.return_value = [make_agent(), make_agent(id="ag-2")]
        layer = AgentSocialLayer()
        assert await layer._calculate_percentile_rank("ag-1", 80, db=db) == 80.0
        db.query.return_value.all.return_value = []
        assert await layer._calculate_percentile_rank("ag-1", 80, db=db) == 0.0
        assert await layer._calculate_percentile_rank("ag-1", 80, db=None) == 0.0

    async def test_reputation_trend(self):
        db = make_db()
        posts = [
            make_post(created_at=datetime(2026, 8, 1, tzinfo=timezone.utc)),
            make_post(created_at=datetime(2026, 8, 1, 1, tzinfo=timezone.utc)),
            make_post(created_at=datetime(2026, 8, 2, tzinfo=timezone.utc)),
        ]
        db.query.return_value.filter.return_value.all.return_value = posts
        layer = AgentSocialLayer()
        trend = await layer._get_reputation_trend("ag-1", db=db)
        assert len(trend) == 2
        assert trend[0]["post_count"] == 2
        assert trend[1]["date"] == "2026-08-02"


class TestGraduationMilestone:
    async def test_no_db(self):
        layer = AgentSocialLayer()
        assert await layer.post_graduation_milestone("ag-1", "intern", "supervised", db=None) == {}

    async def test_agent_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        layer = AgentSocialLayer()
        with pytest.raises(ValueError, match="not found"):
            await layer.post_graduation_milestone("ghost", "intern", "supervised", db=db)

    async def test_success(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post",
                          new=AsyncMock(return_value={"id": "m1"})), \
             patch("core.agent_communication.agent_event_bus.publish", new=AsyncMock()) as pub:
            post = await layer.post_graduation_milestone(
                "ag-1", "intern", "supervised", db=db)
        assert post == {"id": "m1"}
        pub.assert_called_once()


class TestRateLimits:
    async def test_no_db_allowed(self):
        layer = AgentSocialLayer()
        assert await layer.check_rate_limit("ag-1", db=None) == (True, None)

    async def test_agent_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        layer = AgentSocialLayer()
        allowed, reason = await layer.check_rate_limit("ghost", db=db)
        assert allowed is False
        assert "not found" in reason

    async def test_student_read_only(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="STUDENT")
        layer = AgentSocialLayer()
        allowed, reason = await layer.check_rate_limit("ag-1", db=db)
        assert allowed is False
        assert "read-only" in reason

    async def test_intern_limit(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="INTERN")
        layer = AgentSocialLayer()
        with patch.object(layer, "_check_hourly_limit",
                          new=AsyncMock(return_value=(True, None))) as check:
            await layer.check_rate_limit("ag-1", db=db)
        check.assert_called_once_with("ag-1", max_posts=1, db=db)

    async def test_supervised_limit(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="SUPERVISED")
        layer = AgentSocialLayer()
        with patch.object(layer, "_check_hourly_limit",
                          new=AsyncMock(return_value=(False, "Rate limit exceeded"))) as check:
            allowed, reason = await layer.check_rate_limit("ag-1", db=db)
        assert allowed is False
        check.assert_called_once_with("ag-1", max_posts=12, db=db)

    async def test_autonomous_unlimited(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="AUTONOMOUS")
        layer = AgentSocialLayer()
        assert await layer.check_rate_limit("ag-1", db=db) == (True, None)

    async def test_check_hourly_limit(self):
        db = make_db()
        db.query.return_value.filter.return_value.count.return_value = 5
        layer = AgentSocialLayer()
        allowed, reason = await layer._check_hourly_limit("ag-1", max_posts=3, db=db)
        assert allowed is False
        assert "Rate limit exceeded" in reason
        db.query.return_value.filter.return_value.count.return_value = 2
        assert await layer._check_hourly_limit("ag-1", max_posts=3, db=db) == (True, None)

    async def test_get_rate_limit_info(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="INTERN")
        db.query.return_value.filter.return_value.count.return_value = 0
        layer = AgentSocialLayer()
        info = await layer.get_rate_limit_info("ag-1", db=db)
        assert info["max_posts_per_hour"] == 1
        assert info["remaining_posts"] == 1

    async def test_get_rate_limit_info_unlimited(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="AUTONOMOUS")
        layer = AgentSocialLayer()
        info = await layer.get_rate_limit_info("ag-1", db=db)
        assert info["unlimited"] is True

    async def test_get_rate_limit_info_no_db(self):
        layer = AgentSocialLayer()
        assert "error" in await layer.get_rate_limit_info("ag-1", db=None)

    async def test_get_rate_limit_info_agent_missing(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        layer = AgentSocialLayer()
        assert "error" in await layer.get_rate_limit_info("ag-1", db=db)
