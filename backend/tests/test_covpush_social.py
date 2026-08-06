"""
Coverage-push tests for core.agent_social_layer (AgentSocialLayer).

Covers methods not exercised by pre-existing tests plus regressions for
fixed bugs (author_type attributes, reputation, reactions, trending).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

import pytest

from core.agent_social_layer import AgentSocialLayer, agent_social_layer


def make_layer():
    return AgentSocialLayer()


def agent_db(agent, add=True):
    db = Mock()
    agent_query = Mock()
    agent_query.filter.return_value = agent_query
    agent_query.first.return_value = agent
    db.query.return_value = agent_query
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


class TestGetFeedCursor:
    def _posts_db(self, posts, limit=2):
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = posts
        q.count.return_value = len(posts)
        db.query.return_value = q
        return db

    def _post(self, post_id, created_at, author_type="agent", metadata=None):
        p = Mock()
        p.id = post_id
        p.author_type = author_type
        p.author_id = "a1"
        p.post_type = "status"
        p.content = "hello"
        p.post_metadata = metadata
        p.created_at = created_at
        return p

    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        feed = await layer.get_feed_cursor("a1", db=None)
        assert feed["posts"] == []
        assert feed["next_cursor"] is None
        assert feed["has_more"] is False

    @pytest.mark.asyncio
    async def test_with_cursor_compound(self):
        layer = make_layer()
        now = datetime.now(timezone.utc)
        db = self._posts_db([self._post("p2", now), self._post("p1", now)])
        feed = await layer.get_feed_cursor("a1", cursor=f"{now.isoformat()}:p9", limit=2, db=db)
        assert len(feed["posts"]) == 2

    @pytest.mark.asyncio
    async def test_legacy_cursor(self):
        layer = make_layer()
        now = datetime.now(timezone.utc)
        db = self._posts_db([self._post("p1", now)])
        feed = await layer.get_feed_cursor("a1", cursor=now.isoformat(), db=db)
        assert len(feed["posts"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_cursor(self):
        layer = make_layer()
        now = datetime.now(timezone.utc)
        db = self._posts_db([self._post("p1", now)])
        feed = await layer.get_feed_cursor("a1", cursor="not-a-cursor", db=db)
        assert len(feed["posts"]) == 1

    @pytest.mark.asyncio
    async def test_has_more_and_next_cursor(self):
        layer = make_layer()
        now = datetime.now(timezone.utc)
        posts = [self._post(f"p{i}", now - timedelta(minutes=i)) for i in range(3)]
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = posts
        db.query.return_value = q
        feed = await layer.get_feed_cursor("a1", limit=2, db=db)
        assert feed["has_more"] is True
        assert feed["next_cursor"] is not None
        assert len(feed["posts"]) == 2

    @pytest.mark.asyncio
    async def test_filters(self):
        layer = make_layer()
        now = datetime.now(timezone.utc)
        db = self._posts_db([self._post("p1", now, metadata={"is_public": True})])
        feed = await layer.get_feed_cursor(
            "a1", post_type="status", sender_filter="a1",
            channel_id="c1", is_public=True, db=db,
        )
        assert len(feed["posts"]) == 1


class TestChannels:
    @pytest.mark.asyncio
    async def test_create_channel_no_db(self):
        layer = make_layer()
        with pytest.raises(ValueError):
            await layer.create_channel("c1", "chan", "u1", db=None)

    @pytest.mark.asyncio
    async def test_create_channel_exists(self):
        layer = make_layer()
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.first.return_value = Mock(id="c1", name="chan")
        db.query.return_value = q
        result = await layer.create_channel("c1", "chan", "u1", db=db)
        assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_create_channel_new(self):
        layer = make_layer()
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.first.return_value = None
        db.query.return_value = q
        db.add = Mock()
        db.commit = Mock()
        created = Mock(id="c1", name="chan")
        db.refresh = Mock()
        result = await layer.create_channel("c1", "chan", "u1", display_name="Display", description="d", db=db)
        assert result["created"] is True
        db.add.assert_called()

    @pytest.mark.asyncio
    async def test_get_channels_no_db(self):
        layer = make_layer()
        assert await layer.get_channels(db=None) == []

    @pytest.mark.asyncio
    async def test_get_channels(self):
        layer = make_layer()
        db = Mock()
        ch = Mock(id="c1", name="chan", display_name="Display", description="d",
                  channel_type="general", is_public=True, created_by="u1",
                  created_at=datetime.now(timezone.utc))
        db.query.return_value.all.return_value = [ch]
        result = await layer.get_channels(db=db)
        assert result[0]["id"] == "c1"


class TestReplies:
    @pytest.mark.asyncio
    async def test_get_replies_no_db(self):
        layer = make_layer()
        assert await layer.get_replies("p1", db=None) == {"replies": [], "total": 0}

    @pytest.mark.asyncio
    async def test_get_replies(self):
        layer = make_layer()
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        r = Mock(id="r1", author_type="human", author_id="u1", post_type="status",
                 content="reply", post_metadata={"sender_name": "Alice"},
                 created_at=datetime.now(timezone.utc))
        q.all.return_value = [r]
        db.query.return_value = q
        result = await layer.get_replies("p1", db=db)
        assert result["total"] == 1
        assert result["replies"][0]["sender_id"] == "u1"


class TestCreatePostWithEpisode:
    @pytest.mark.asyncio
    async def test_with_explicit_episodes_and_segment(self):
        layer = make_layer()
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        with patch.object(layer, "create_post", new=AsyncMock(return_value={"id": "post-1", "mentioned_episode_ids": ["ep1"]})):
            result = await layer.create_post_with_episode(
                sender_type="agent", sender_id="a1", sender_name="Agent",
                post_type="status", content="hello", episode_ids=["ep1"], db=db,
            )
        assert result["id"] == "post-1"
        db.add.assert_called()

    @pytest.mark.asyncio
    async def test_auto_retrieve_episodes(self):
        layer = make_layer()
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        with patch.object(layer, "create_post", new=AsyncMock(return_value={"id": "post-2"})), \
             patch.object(layer, "_retrieve_relevant_episodes", new=AsyncMock(return_value=["ep9"])):
            result = await layer.create_post_with_episode(
                sender_type="agent", sender_id="a1", sender_name="Agent",
                post_type="status", content="hello", db=db,
            )
        assert result["id"] == "post-2"

    @pytest.mark.asyncio
    async def test_segment_failure_tolerated(self):
        layer = make_layer()
        db = Mock()
        db.add = Mock(side_effect=RuntimeError("segment down"))
        db.commit = Mock()
        db.refresh = Mock()
        with patch.object(layer, "create_post", new=AsyncMock(return_value={"id": "post-3"})):
            result = await layer.create_post_with_episode(
                sender_type="human", sender_id="u1", sender_name="U",
                post_type="insight", content="hello", episode_ids=["ep1"], db=db,
            )
        assert result["id"] == "post-3"

    @pytest.mark.asyncio
    async def test_retrieve_relevant_episodes_no_db(self):
        layer = make_layer()
        assert await layer._retrieve_relevant_episodes("a1", "content", db=None) == []

    @pytest.mark.asyncio
    async def test_retrieve_relevant_episodes_success(self):
        layer = make_layer()
        db = Mock()
        ep = Mock(id="ep1")
        service = Mock()
        service.retrieve_episodes = AsyncMock(return_value=[ep])
        with patch("core.episode_retrieval_service.EpisodeRetrievalService", return_value=service):
            result = await layer._retrieve_relevant_episodes("a1", "content", db=db)
        assert result == ["ep1"]

    @pytest.mark.asyncio
    async def test_retrieve_relevant_episodes_exception(self):
        layer = make_layer()
        db = Mock()
        with patch("core.episode_retrieval_service.EpisodeRetrievalService", side_effect=RuntimeError("boom")):
            assert await layer._retrieve_relevant_episodes("a1", "content", db=db) == []


class TestFeedWithEpisodeContext:
    @pytest.mark.asyncio
    async def test_with_context(self):
        layer = make_layer()
        db = Mock()
        with patch.object(layer, "get_feed", new=AsyncMock(return_value={
            "posts": [{"id": "p1", "mentioned_episode_ids": ["ep1"]}],
        })), patch.object(layer, "_get_episode_summaries", new=AsyncMock(return_value=[{"id": "ep1", "title": "T"}])):
            feed = await layer.get_feed_with_episode_context(db=db)
        assert feed["posts"][0]["episode_context"][0]["title"] == "T"

    @pytest.mark.asyncio
    async def test_context_failure(self):
        layer = make_layer()
        db = Mock()
        with patch.object(layer, "get_feed", new=AsyncMock(return_value={
            "posts": [{"id": "p1", "mentioned_episode_ids": ["ep1"]}],
        })), patch.object(layer, "_get_episode_summaries", new=AsyncMock(side_effect=RuntimeError("boom"))):
            feed = await layer.get_feed_with_episode_context(db=db)
        assert feed["posts"][0]["episode_context"] == []

    @pytest.mark.asyncio
    async def test_no_context_requested(self):
        layer = make_layer()
        with patch.object(layer, "get_feed", new=AsyncMock(return_value={"posts": []})):
            feed = await layer.get_feed_with_episode_context(include_episode_context=False, db=Mock())
        assert feed["posts"] == []

    @pytest.mark.asyncio
    async def test_get_episode_summaries_empty(self):
        layer = make_layer()
        assert await layer._get_episode_summaries([], db=Mock()) == []

    @pytest.mark.asyncio
    async def test_get_episode_summaries_success(self):
        layer = make_layer()
        db = Mock()
        ep = Mock(id="ep1", title="T", summary="summary here", created_at=datetime.now(timezone.utc), agent_id="a1")
        db.query.return_value.filter.return_value.all.return_value = [ep]
        result = await layer._get_episode_summaries(["ep1"], db=db)
        assert result[0]["title"] == "T"

    @pytest.mark.asyncio
    async def test_get_episode_summaries_exception(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer._get_episode_summaries(["ep1"], db=db) == []


class TestTrackPositiveInteraction:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        assert await layer.track_positive_interaction("p1", "👍", db=None) is None

    @pytest.mark.asyncio
    async def test_post_not_found(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert await layer.track_positive_interaction("p1", "👍", db=db) is None

    @pytest.mark.asyncio
    async def test_human_post_skipped(self):
        layer = make_layer()
        db = Mock()
        post = Mock(author_type="human", content="x")
        db.query.return_value.filter.return_value.first.return_value = post
        assert await layer.track_positive_interaction("p1", "👍", db=db) is None

    @pytest.mark.asyncio
    async def test_non_positive_interaction(self):
        layer = make_layer()
        db = Mock()
        post = Mock(author_type="agent", author_id="a1", content="x")
        db.query.return_value.filter.return_value.first.return_value = post
        assert await layer.track_positive_interaction("p1", "👎", db=db) is None

    @pytest.mark.asyncio
    async def test_positive_reaction(self):
        layer = make_layer()
        db = Mock()
        post = Mock(author_type="agent", author_id="a1", content="x")
        db.query.return_value.filter.return_value.first.return_value = post
        with patch.object(layer, "_update_agent_reputation", new=AsyncMock()) as rep:
            await layer.track_positive_interaction("p1", "❤️", user_id="u1", db=db)
        rep.assert_called_once_with("a1", "❤️", db=db)
        db.add.assert_called()

    @pytest.mark.asyncio
    async def test_import_error_tolerated(self):
        layer = make_layer()
        db = Mock()
        post = Mock(author_type="agent", author_id="a1", content="x")
        db.query.return_value.filter.return_value.first.return_value = post
        with patch("core.agent_graduation_service.AgentGraduationService", side_effect=ImportError("nope")), \
             patch.object(layer, "_update_agent_reputation", new=AsyncMock()):
            await layer.track_positive_interaction("p1", "thanks", db=db)

    def test_is_positive_interaction(self):
        layer = make_layer()
        assert layer._is_positive_interaction("👍") is True
        assert layer._is_positive_interaction("like") is True
        assert layer._is_positive_interaction("thanks!") is True
        assert layer._is_positive_interaction("awful") is False
        assert layer._is_positive_interaction("") is False

    @pytest.mark.asyncio
    async def test_update_agent_reputation_logs(self):
        layer = make_layer()
        await layer._update_agent_reputation("a1", "like", db=Mock())


class TestGetAgentReputation:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        result = await layer.get_agent_reputation("a1", db=None)
        assert result["reputation_score"] == 0

    @pytest.mark.asyncio
    async def test_success(self):
        layer = make_layer()
        db = Mock()
        post = Mock(author_type="agent", author_id="a1", content="x")
        post.reactions = [Mock(emoji="👍"), Mock(emoji="👍")]
        posts_query = Mock()
        posts_query.filter.return_value = posts_query
        posts_query.all.return_value = [post]
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.scalar.return_value = 3
        db.query.side_effect = [posts_query, count_query]
        with patch.object(layer, "_count_helpful_replies", new=AsyncMock(return_value=2)), \
             patch.object(layer, "_calculate_percentile_rank", new=AsyncMock(return_value=50.0)), \
             patch.object(layer, "_get_reputation_trend", new=AsyncMock(return_value=[{"date": "2026-01-01", "post_count": 1}])):
            result = await layer.get_agent_reputation("a1", db=db)
        assert result["total_reactions"] == 2
        assert result["total_replies"] == 3
        assert result["helpful_replies"] == 2
        assert result["reputation_score"] == 4 + 10 + 1

    @pytest.mark.asyncio
    async def test_exception_no_str_leak(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("secret-detail")
        result = await layer.get_agent_reputation("a1", db=db)
        assert result["error"]
        assert "secret-detail" not in result["error"]

    @pytest.mark.asyncio
    async def test_count_helpful_replies(self):
        layer = make_layer()
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.count.return_value = 2
        db.query.return_value = q
        assert await layer._count_helpful_replies("a1", db=db) == 2

    @pytest.mark.asyncio
    async def test_count_helpful_replies_exception(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer._count_helpful_replies("a1", db=db) == 0

    @pytest.mark.asyncio
    async def test_percentile_rank_no_db(self):
        layer = make_layer()
        assert await layer._calculate_percentile_rank("a1", 50, db=None) == 0.0

    @pytest.mark.asyncio
    async def test_percentile_rank_no_agents(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.all.return_value = []
        assert await layer._calculate_percentile_rank("a1", 50, db=db) == 0.0

    @pytest.mark.asyncio
    async def test_percentile_rank_score(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.all.return_value = [Mock(), Mock()]
        assert await layer._calculate_percentile_rank("a1", 80, db=db) == 80.0

    @pytest.mark.asyncio
    async def test_reputation_trend(self):
        layer = make_layer()
        db = Mock()
        posts = [Mock(created_at=datetime.now(timezone.utc)), Mock(created_at=datetime.now(timezone.utc) - timedelta(days=1))]
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = posts
        db.query.return_value = q
        trend = await layer._get_reputation_trend("a1", db=db)
        assert len(trend) == 2

    @pytest.mark.asyncio
    async def test_reputation_trend_exception(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer._get_reputation_trend("a1", db=db) == []


class TestPostGraduationMilestone:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        assert await layer.post_graduation_milestone("a1", "INTERN", "SUPERVISED", db=None) == {}

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await layer.post_graduation_milestone("a1", "INTERN", "SUPERVISED", db=db)

    @pytest.mark.asyncio
    async def test_success(self):
        layer = make_layer()
        db = Mock()
        agent = Mock(name="Agent One")
        db.query.return_value.filter.return_value.first.return_value = agent
        with patch.object(layer, "create_post", new=AsyncMock(return_value={"id": "post-1"})) as create:
            post = await layer.post_graduation_milestone("a1", "INTERN", "SUPERVISED", db=db)
        assert post["id"] == "post-1"
        assert "graduated" in create.call_args.kwargs["content"]


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_no_db_allowed(self):
        layer = make_layer()
        assert await layer.check_rate_limit("a1", db=None) == (True, None)

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        allowed, reason = await layer.check_rate_limit("a1", db=db)
        assert allowed is False
        assert "not found" in reason

    @pytest.mark.asyncio
    async def test_student_blocked(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(status="STUDENT")
        allowed, reason = await layer.check_rate_limit("a1", db=db)
        assert allowed is False
        assert "read-only" in reason

    @pytest.mark.asyncio
    async def test_intern_over_limit(self):
        layer = make_layer()
        db = Mock()
        agent_query = Mock()
        agent_query.filter.return_value = agent_query
        agent_query.first.return_value = Mock(status="INTERN")
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.count.return_value = 1
        db.query.side_effect = [agent_query, count_query]
        allowed, reason = await layer.check_rate_limit("a1", db=db)
        assert allowed is False
        assert "Rate limit" in reason

    @pytest.mark.asyncio
    async def test_supervised_allowed(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(status="SUPERVISED")
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.count.return_value = 5
        db.query.return_value = count_query
        assert await layer.check_rate_limit("a1", db=db) == (True, None)

    @pytest.mark.asyncio
    async def test_autonomous_unlimited(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(status="AUTONOMOUS")
        assert await layer.check_rate_limit("a1", db=db) == (True, None)

    @pytest.mark.asyncio
    async def test_exception_fail_open(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer.check_rate_limit("a1", db=db) == (True, None)

    @pytest.mark.asyncio
    async def test_hourly_limit_no_db(self):
        layer = make_layer()
        assert await layer._check_hourly_limit("a1", 1, db=None) == (True, None)

    @pytest.mark.asyncio
    async def test_hourly_limit_exception(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer._check_hourly_limit("a1", 1, db=db) == (True, None)

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_no_db(self):
        layer = make_layer()
        assert "error" in await layer.get_rate_limit_info("a1", db=None)

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_missing_agent(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert "error" in await layer.get_rate_limit_info("a1", db=db)

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_unlimited(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(status="AUTONOMOUS")
        info = await layer.get_rate_limit_info("a1", db=db)
        assert info["unlimited"] is True

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_intern(self):
        layer = make_layer()
        db = Mock()
        agent_query = Mock()
        agent_query.filter.return_value = agent_query
        agent_query.first.return_value = Mock(status="INTERN")
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.count.return_value = 1
        db.query.side_effect = [agent_query, count_query]
        info = await layer.get_rate_limit_info("a1", db=db)
        assert info["max_posts_per_hour"] == 1
        assert info["remaining_posts"] == 0

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_student(self):
        layer = make_layer()
        db = Mock()
        agent_query = Mock()
        agent_query.filter.return_value = agent_query
        agent_query.first.return_value = Mock(status="STUDENT")
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.count.return_value = 0
        db.query.side_effect = [agent_query, count_query]
        info = await layer.get_rate_limit_info("a1", db=db)
        assert info["max_posts_per_hour"] == 0

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_exception_no_str_leak(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("secret-detail")
        info = await layer.get_rate_limit_info("a1", db=db)
        assert "error" in info
        assert "secret-detail" not in info["error"]


class TestRegisterHooks:
    def test_register_hooks_success(self):
        with patch("core.operation_tracker_hooks.register_auto_post_hooks") as hook:
            from core.agent_social_layer import register_hooks_if_needed
            register_hooks_if_needed()
            hook.assert_called_once()

    def test_register_hooks_failure(self):
        with patch("core.operation_tracker_hooks.register_auto_post_hooks", side_effect=RuntimeError("boom")):
            from core.agent_social_layer import register_hooks_if_needed
            register_hooks_if_needed()


class TestAddReply:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        with pytest.raises(ValueError):
            await layer.add_reply("p1", "human", "u1", "Alice", "hello", db=None)

    @pytest.mark.asyncio
    async def test_post_not_found(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await layer.add_reply("p1", "human", "u1", "Alice", "hello", db=db)

    @pytest.mark.asyncio
    async def test_student_agent_cannot_reply(self):
        layer = make_layer()
        db = Mock()
        parent = Mock()
        agent = Mock(status="STUDENT")
        db.query.side_effect = [Mock(filter=Mock(return_value=Mock(first=Mock(return_value=parent)))),
                                Mock(filter=Mock(return_value=Mock(first=Mock(return_value=agent))))]
        with pytest.raises(PermissionError, match="STUDENT"):
            await layer.add_reply("p1", "agent", "a1", "Agent", "hello", db=db)

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        layer = make_layer()
        db = Mock()
        parent = Mock()
        db.query.side_effect = [Mock(filter=Mock(return_value=Mock(first=Mock(return_value=parent)))),
                                Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None))))]
        with pytest.raises(PermissionError, match="not found"):
            await layer.add_reply("p1", "agent", "a1", "Agent", "hello", db=db)

    @pytest.mark.asyncio
    async def test_success(self):
        layer = make_layer()
        db = Mock()
        parent = Mock()
        agent = Mock(status="INTERN", category="eng")
        db.query.side_effect = [Mock(filter=Mock(return_value=Mock(first=Mock(return_value=parent)))),
                                Mock(filter=Mock(return_value=Mock(first=Mock(return_value=agent))))]
        with patch.object(layer, "create_post", new=AsyncMock(return_value={"id": "r1"})) as create:
            result = await layer.add_reply("p1", "agent", "a1", "Agent", "hello", db=db)
        assert result["id"] == "r1"
        assert create.call_args.kwargs["reply_to_id"] == "p1"


class TestCreatePostErrors:
    @pytest.mark.asyncio
    async def test_agent_without_db_rejected(self):
        layer = make_layer()
        with pytest.raises(PermissionError, match="Database session required"):
            await layer.create_post(
                sender_type="agent", sender_id="a1", sender_name="A",
                post_type="status", content="x", db=None,
            )

    @pytest.mark.asyncio
    async def test_agent_not_found_rejected(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(PermissionError, match="not found"):
            await layer.create_post(
                sender_type="agent", sender_id="a1", sender_name="A",
                post_type="status", content="x", db=db,
            )


class TestGetFeedExtra:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        assert await layer.get_feed("a1", db=None) == {"posts": [], "total": 0}

    @pytest.mark.asyncio
    async def test_sender_filter(self):
        layer = make_layer()
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.count.return_value = 1
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        db.query.return_value = q
        feed = await layer.get_feed("a1", sender_filter="b1", db=db)
        assert feed["total"] == 1


class TestAddReactionExtra:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        with pytest.raises(ValueError, match="Database session required"):
            await layer.add_reaction("p1", "u1", "👍", db=None)

    @pytest.mark.asyncio
    async def test_post_not_found(self):
        layer = make_layer()
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await layer.add_reaction("p1", "u1", "👍", db=db)

    @pytest.mark.asyncio
    async def test_dict_reactions_accumulate(self):
        layer = make_layer()
        post = Mock()
        post.reactions = {"👍": 2, "❤️": 1}
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.first.return_value = post
        db.query.return_value = q
        reactions = await layer.add_reaction("p1", "u1", "👍", db=db)
        assert reactions == {"👍": 3, "❤️": 1}

    @pytest.mark.asyncio
    async def test_list_reactions_accumulate(self):
        layer = make_layer()
        post = Mock()
        post.reactions = [Mock(emoji="👍"), Mock(emoji="👍"), Mock(emoji="🎉")]
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.first.return_value = post
        db.query.return_value = q
        reactions = await layer.add_reaction("p1", "u1", "👍", db=db)
        assert reactions == {"👍": 3, "🎉": 1}


class TestTrendingExtra:
    @pytest.mark.asyncio
    async def test_no_db(self):
        layer = make_layer()
        assert await layer.get_trending_topics(db=None) == []

    @pytest.mark.asyncio
    async def test_metadata_mentions(self):
        layer = make_layer()
        db = Mock()
        post = Mock()
        post.post_metadata = {
            "mentioned_agent_ids": ["agent-1"],
            "mentioned_user_ids": ["user-1"],
            "mentioned_episode_ids": ["ep-1"],
            "mentioned_task_ids": ["task-1"],
        }
        q = Mock()
        q.filter.return_value = q
        q.all.return_value = [post]
        db.query.return_value = q
        trending = await layer.get_trending_topics(db=db)
        assert len(trending) == 4


class TestReputationExtra:
    @pytest.mark.asyncio
    async def test_dict_reactions(self):
        layer = make_layer()
        db = Mock()
        post = Mock(author_type="agent", author_id="a1", content="x")
        post.reactions = {"👍": 3}
        posts_query = Mock()
        posts_query.filter.return_value = posts_query
        posts_query.all.return_value = [post]
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.scalar.return_value = 0
        db.query.side_effect = [posts_query, count_query]
        with patch.object(layer, "_count_helpful_replies", new=AsyncMock(return_value=0)), \
             patch.object(layer, "_calculate_percentile_rank", new=AsyncMock(return_value=0.0)), \
             patch.object(layer, "_get_reputation_trend", new=AsyncMock(return_value=[])):
            result = await layer.get_agent_reputation("a1", db=db)
        assert result["total_reactions"] == 3

    @pytest.mark.asyncio
    async def test_count_helpful_replies_no_db(self):
        layer = make_layer()
        assert await layer._count_helpful_replies("a1", db=None) == 0

    @pytest.mark.asyncio
    async def test_percentile_exception(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer._calculate_percentile_rank("a1", 10, db=db) == 0.0

    @pytest.mark.asyncio
    async def test_trend_no_db(self):
        layer = make_layer()
        assert await layer._get_reputation_trend("a1", db=None) == []


class TestTrackPositiveException:
    @pytest.mark.asyncio
    async def test_exception_logged(self):
        layer = make_layer()
        db = Mock()
        db.query.side_effect = RuntimeError("boom")
        assert await layer.track_positive_interaction("p1", "👍", db=db) is None


class TestFeedCursorLegacy:
    @pytest.mark.asyncio
    async def test_legacy_cursor_no_colon(self):
        layer = make_layer()
        db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        db.query.return_value = q
        feed = await layer.get_feed_cursor("a1", cursor="2026-01-01T100000", db=db)
        assert feed["posts"] == []


class TestRateLimitSupervised:
    @pytest.mark.asyncio
    async def test_supervised_over_limit(self):
        layer = make_layer()
        db = Mock()
        agent_query = Mock()
        agent_query.filter.return_value = agent_query
        agent_query.first.return_value = Mock(status="SUPERVISED")
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.count.return_value = 12
        db.query.side_effect = [agent_query, count_query]
        allowed, reason = await layer.check_rate_limit("a1", db=db)
        assert allowed is False
        assert "12" in reason

    @pytest.mark.asyncio
    async def test_hourly_under_limit(self):
        layer = make_layer()
        db = Mock()
        count_query = Mock()
        count_query.filter.return_value = count_query
        count_query.count.return_value = 0
        db.query.return_value = count_query
        assert await layer._check_hourly_limit("a1", 1, db=db) == (True, None)
