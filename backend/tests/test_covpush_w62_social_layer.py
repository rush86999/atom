"""Coverage wave 62 — core/agent_social_layer.py (TDD, mocked db + redactor).

Wave 29 took this module to 91%; wave 62 closes the remaining branches and
locks in the full social contract: redaction audit paths (has_secrets
False), default-tenant fallback, feed/reply/cursor edge shapes, reaction
posts with None storage, trending topic fallbacks, episode-context toggles,
reputation helper exceptions, rate-limit fail-open paths, graduation
milestone error re-raise and hook registration. Includes a TDD fix proving
the ``add_reply`` STUDENT gate fires for lowercase statuses ("student" as
stored by AgentRegistry) — previously dead code that silently fell through
to create_post's misleading "cannot post" message.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent_social_layer import (
    AgentSocialLayer,
    agent_social_layer,
    register_hooks_if_needed,
)
from core.models import AuthorType


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


def patch_broadcast():
    return patch("core.agent_communication.agent_event_bus.broadcast_post",
                 new=AsyncMock())


class TestCreatePostEdges:
    async def test_redaction_no_secrets_skips_audit_log(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        layer = AgentSocialLayer()
        redactor = MagicMock()
        redactor.redact.return_value = SimpleNamespace(
            redacted_text="clean", has_secrets=False, redactions=[])
        with patch("core.agent_social_layer.get_pii_redactor", return_value=redactor), \
             patch.object(layer, "logger", MagicMock()) as log, \
             patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch_broadcast():
            post = await layer.create_post("human", "u1", "U", "status", "text", db=db)
        assert post["content"] == "clean"
        assert all("PII redacted" not in str(call) for call in log.info.call_args_list)

    async def test_human_post_without_db(self):
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.SocialPost", lambda **kw: make_post(**kw)), \
             patch_broadcast() as broadcast:
            post = await layer.create_post("human", "u1", "U", "status", "hi", db=None)
        assert post["sender_type"] == "human"
        broadcast.assert_called_once()

    async def test_agent_without_tenant_id_uses_default(self):
        db = make_db()
        agent = make_agent()
        del agent.tenant_id
        db.query.return_value.filter.return_value.first.return_value = agent
        captured = {}
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.SocialPost",
                   lambda **kw: captured.update(kw) or make_post(**kw)), \
             patch_broadcast():
            await layer.create_post("agent", "ag-1", "A", "status", "hi", db=db)
        assert captured["tenant_id"] == "default"

    async def test_post_data_uses_author_type_value(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent()
        layer = AgentSocialLayer()
        with patch("core.agent_social_layer.SocialPost",
                   lambda **kw: make_post(author_type=AuthorType.AGENT)), \
             patch_broadcast():
            post = await layer.create_post("agent", "ag-1", "A", "status", "hi", db=db)
        assert post["sender_type"] == "agent"
        assert post["created_at"] is not None


class TestGetFeedEdges:
    async def test_no_filters_and_null_metadata(self):
        db = make_db()
        post = make_post(post_metadata=None, author_type=AuthorType.AGENT,
                         post_type=AuthorType.HUMAN)
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [post]
        db.query.return_value.count.return_value = 1
        layer = AgentSocialLayer()
        feed = await layer.get_feed("u1", db=db)
        assert feed["total"] == 1
        entry = feed["posts"][0]
        assert entry["sender_name"] is None
        assert entry["is_public"] is True
        assert entry["mentioned_agent_ids"] == []
        assert entry["created_at"] is not None


class TestReactionEdges:
    async def test_reactions_none_starts_empty(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_post(reactions=None)
        layer = AgentSocialLayer()
        with patch("core.agent_communication.agent_event_bus.publish", new=AsyncMock()) as pub:
            reactions = await layer.add_reaction("p1", "u1", "🎉", db=db)
        assert reactions == {"🎉": 1}
        pub.assert_called_once_with({
            "type": "reaction_added", "post_id": "p1", "sender_id": "u1",
            "emoji": "🎉", "reactions": {"🎉": 1}}, ["post:p1", "global"])


class TestTrendingEdges:
    async def test_non_dict_metadata_and_missing_keys(self):
        db = make_db()
        db.query.return_value.filter.return_value.all.return_value = [
            make_post(post_metadata="not-a-dict"),
            make_post(post_metadata=None),
        ]
        layer = AgentSocialLayer()
        assert await layer.get_trending_topics(hours=1, db=db) == []

    async def test_mentions_from_post_attributes(self):
        db = make_db()
        db.query.return_value.filter.return_value.all.return_value = [
            make_post(post_metadata={}, mentioned_agent_ids=None),
            make_post(post_metadata={}, mentioned_agent_ids=None),
        ]
        # _mentions falls back to getattr(post, key) when metadata lacks the key
        layer = AgentSocialLayer()
        assert await layer.get_trending_topics(hours=24, db=db) == []


class TestReplyEdges:
    async def test_add_reply_agent_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_post()
        db.query.return_value.filter.return_value.first.side_effect = [make_post(), None]
        layer = AgentSocialLayer()
        with pytest.raises(PermissionError, match="not found"):
            await layer.add_reply("p1", "agent", "ghost", "A", "hi", db=db)

    async def test_student_reply_blocked_by_own_gate(self):
        # AgentRegistry.status stores lowercase AgentStatus values ("student").
        # add_reply's own gate must fire (its docstring: "STUDENT agents cannot
        # reply") instead of silently falling through to create_post.
        db = make_db()
        db.query.return_value.filter.return_value.first.side_effect = [
            make_post(),  # parent post
            make_agent(status="student"),
        ]
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post", new=AsyncMock()) as cp:
            with pytest.raises(PermissionError, match="cannot reply"):
                await layer.add_reply("p1", "agent", "ag-1", "A", "hi", db=db)
        cp.assert_not_called()


class TestCursorFeedEdges:
    async def test_all_filters_applied(self):
        db = make_db()
        posts = [make_post(id="p1")]
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = posts
        layer = AgentSocialLayer()
        feed = await layer.get_feed_cursor(
            "u1", post_type="status", sender_filter="ag-1",
            channel_id="ch-1", is_public=True, db=db)
        assert feed["has_more"] is False
        assert feed["next_cursor"] is None
        assert len(feed["posts"]) == 1

    async def test_post_with_enum_types(self):
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            make_post(author_type=AuthorType.HUMAN, post_type=AuthorType.AGENT,
                      post_metadata=None),
        ]
        layer = AgentSocialLayer()
        feed = await layer.get_feed_cursor("u1", limit=5, db=db)
        assert feed["posts"][0]["sender_type"] == "human"
        assert feed["posts"][0]["auto_generated"] is False


class TestChannelEdges:
    async def test_create_channel_private_with_defaults(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = MagicMock()
        db.commit = MagicMock()
        channel = SimpleNamespace(id="c1", name="support")
        layer = AgentSocialLayer()
        with patch("core.models.Channel", MagicMock(return_value=channel)) as ch_cls, \
             patch("core.agent_communication.agent_event_bus.publish", new=AsyncMock()):
            result = await layer.create_channel(
                "c1", "support", "u1", description="help", channel_type="support",
                is_public=False, db=db)
        assert result["created"] is True
        kwargs = ch_cls.call_args.kwargs
        assert kwargs["is_public"] is False
        assert kwargs["display_name"] == "support"  # falls back to name
        assert kwargs["description"] == "help"
        assert kwargs["channel_type"] == "support"

    async def test_get_channels_empty(self):
        db = make_db()
        db.query.return_value.all.return_value = []
        layer = AgentSocialLayer()
        assert await layer.get_channels(db=db) == []


class TestEpisodeEdges:
    async def test_create_post_with_episode_creates_segment(self):
        db = make_db()
        db.add = MagicMock()
        db.commit = MagicMock()
        segment = SimpleNamespace(id="seg-1")
        layer = AgentSocialLayer()
        with patch.object(layer, "create_post",
                          new=AsyncMock(return_value={"id": "p1"})), \
             patch("core.models.EpisodeSegment", MagicMock(return_value=segment)), \
             patch.object(layer, "logger", MagicMock()) as log:
            post = await layer.create_post_with_episode(
                "human", "u1", "U", "status", "hi", episode_ids=["ep-1"], db=db)
        assert post == {"id": "p1"}
        db.add.assert_called_once_with(segment)
        log.info.assert_called_once()

    async def test_feed_context_disabled(self):
        db = make_db()
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0
        layer = AgentSocialLayer()
        feed = await layer.get_feed_with_episode_context(
            include_episode_context=False, db=db)
        assert feed["posts"] == []

    async def test_feed_context_without_episode_mentions(self):
        db = make_db()
        post = make_post(post_metadata={"mentioned_agent_ids": ["ag-2"]})
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [post]
        db.query.return_value.count.return_value = 1
        layer = AgentSocialLayer()
        with patch.object(layer, "_get_episode_summaries", new=AsyncMock()) as summ:
            feed = await layer.get_feed_with_episode_context(db=db)
        assert "episode_context" not in feed["posts"][0]
        summ.assert_not_called()

    async def test_episode_summaries_empty_and_nulls(self):
        layer = AgentSocialLayer()
        assert await layer._get_episode_summaries([], db=make_db()) == []
        assert await layer._get_episode_summaries(["ep-1"], db=None) == []

        db = make_db()
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id="ep-1", title=None, summary=None,
                            created_at=None, agent_id="ag-1"),
        ]
        summaries = await layer._get_episode_summaries(["ep-1"], db=db)
        assert summaries[0]["summary"] is None
        assert summaries[0]["created_at"] is None


class TestPositiveInteractionEdges:
    async def test_author_type_str_enum_recognized_as_agent(self):
        # DB round-trips author_type as the AuthorType str-enum member; the
        # comparison `author_type != "agent"` must NOT skip agent posts.
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_post(
            author_type=AuthorType.AGENT)
        db.add = MagicMock()
        db.commit = MagicMock()
        layer = AgentSocialLayer()
        with patch.object(layer, "_update_agent_reputation", new=AsyncMock()) as rep, \
             patch("core.models.AgentFeedback", lambda **kw: make_post(**kw)):
            await layer.track_positive_interaction("p1", "❤️", user_id="u2", db=db)
        rep.assert_called_once()
        db.add.assert_called_once()


class TestReputationEdges:
    async def test_percentile_exception(self):
        db = make_db()
        db.query.return_value.all.side_effect = RuntimeError("boom")
        layer = AgentSocialLayer()
        assert await layer._calculate_percentile_rank("ag-1", 50, db=db) == 0.0

    async def test_trend_exception(self):
        db = make_db()
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("boom")
        layer = AgentSocialLayer()
        assert await layer._get_reputation_trend("ag-1", db=db) == []

    async def test_helpful_replies_exception(self):
        db = make_db()
        db.query.return_value.filter.return_value.count.side_effect = RuntimeError("boom")
        layer = AgentSocialLayer()
        assert await layer._count_helpful_replies("ag-1", db=db) == 0


class TestGraduationEdges:
    async def test_milestone_error_reraises(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
        layer = AgentSocialLayer()
        with pytest.raises(RuntimeError, match="db down"):
            await layer.post_graduation_milestone("ag-1", "intern", "supervised", db=db)


class TestRateLimitEdges:
    async def test_check_rate_limit_exception_fails_open(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
        layer = AgentSocialLayer()
        assert await layer.check_rate_limit("ag-1", db=db) == (True, None)

    async def test_hourly_limit_exception_fails_open(self):
        db = make_db()
        db.query.return_value.filter.return_value.count.side_effect = RuntimeError("db down")
        layer = AgentSocialLayer()
        assert await layer._check_hourly_limit("ag-1", max_posts=1, db=db) == (True, None)

    async def test_get_rate_limit_info_exception(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
        layer = AgentSocialLayer()
        info = await layer.get_rate_limit_info("ag-1", db=db)
        assert "error" in info

    async def test_get_rate_limit_info_student_zero(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="student")
        db.query.return_value.filter.return_value.count.return_value = 0
        layer = AgentSocialLayer()
        info = await layer.get_rate_limit_info("ag-1", db=db)
        assert info["max_posts_per_hour"] == 0
        assert info["remaining_posts"] == 0

    async def test_get_rate_limit_info_unknown_maturity_unlimited(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = make_agent(status="paused")
        layer = AgentSocialLayer()
        info = await layer.get_rate_limit_info("ag-1", db=db)
        assert info["unlimited"] is True

    async def test_hourly_limit_no_db_allowed(self):
        layer = AgentSocialLayer()
        assert await layer._check_hourly_limit("ag-1", max_posts=1, db=None) == (True, None)


class TestHookRegistration:
    def test_register_hooks_success(self):
        with patch("core.operation_tracker_hooks.register_auto_post_hooks") as reg, \
             patch("core.agent_social_layer.logger", MagicMock()) as log:
            register_hooks_if_needed()
        reg.assert_called_once()
        log.info.assert_called_once()

    def test_register_hooks_failure_tolerated(self):
        with patch("core.operation_tracker_hooks.register_auto_post_hooks",
                   side_effect=ImportError("circular")), \
             patch("core.agent_social_layer.logger", MagicMock()) as log:
            register_hooks_if_needed()
        log.warning.assert_called_once()

    def test_singleton_instance(self):
        assert isinstance(agent_social_layer, AgentSocialLayer)
