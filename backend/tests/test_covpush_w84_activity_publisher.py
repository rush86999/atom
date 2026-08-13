# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/activity_publisher (standalone, fake redis client;
zero network).

- ctor: disabled when redis missing or enabled=False; enabled with client.
- publish_activity: disabled → False; enabled → event JSON on per-agent and
  per-tenant channels, timestamp ISO, metadata default {}, publish raise →
  False.
- publish_skill_execution / publish_reasoning_activity /
  publish_episode_recording: payload shape + disabled passthrough.
- get_activity_publisher: redis enabled (client from_url, url passthrough),
  redis disabled in config, config access raise, redis import error.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.activity_publisher import ActivityPublisher, get_activity_publisher


class _FakeRedis:
    def __init__(self):
        self.published = []
        self.publish = MagicMock(side_effect=lambda ch, payload: self.published.append((ch, payload)))


class _FakeRedisModule:
    def __init__(self):
        self.from_url = MagicMock(return_value=_FakeRedis())


@pytest.fixture()
def redis():
    return _FakeRedis()


@pytest.fixture()
def publisher(redis):
    return ActivityPublisher(redis, enabled=True)


# ============================================================================
# ctor
# ============================================================================

class TestInit:
    def test_disabled_without_redis(self):
        assert ActivityPublisher().enabled is False

    def test_disabled_when_enabled_false(self, redis):
        assert ActivityPublisher(redis, enabled=False).enabled is False

    def test_enabled_with_client(self, redis):
        assert ActivityPublisher(redis, enabled=True).enabled is True


# ============================================================================
# publish_activity
# ============================================================================

class TestPublishActivity:
    def test_disabled_returns_false(self):
        publisher = ActivityPublisher()
        assert publisher.publish_activity("t1", "a1", "reasoning", "thinking") is False

    def test_publishes_to_both_channels(self, publisher, redis):
        result = publisher.publish_activity("t1", "a1", "reasoning", "thinking",
                                            session_key="main", metadata={"phase": "plan"})
        assert result is True
        assert [ch for ch, _ in redis.published] == ["activity:t1:a1", "activity:t1:all"]
        event = json.loads(redis.published[0][1])
        assert event["tenant_id"] == "t1"
        assert event["agent_id"] == "a1"
        assert event["session_key"] == "main"
        assert event["activity_type"] == "reasoning"
        assert event["state"] == "thinking"
        assert event["metadata"] == {"phase": "plan"}
        assert event["timestamp"].endswith("+00:00")

    def test_default_metadata_and_session(self, publisher, redis):
        publisher.publish_activity("t1", "a1", "skill-execution", "working")
        event = json.loads(redis.published[0][1])
        assert event["session_key"] == "main"
        assert event["metadata"] == {}

    def test_publish_error_returns_false(self):
        redis = _FakeRedis()
        redis.publish.side_effect = RuntimeError("redis down")
        publisher = ActivityPublisher(redis, enabled=True)
        assert publisher.publish_activity("t1", "a1", "x", "y") is False


# ============================================================================
# helpers
# ============================================================================

class TestHelpers:
    def test_publish_skill_execution(self, publisher, redis):
        assert publisher.publish_skill_execution("t1", "a1", "web_scrape", "running",
                                                 task_description="scrape x") is True
        event = json.loads(redis.published[0][1])
        assert event["activity_type"] == "skill-execution"
        assert event["metadata"] == {"skill_name": "web_scrape",
                                     "task_description": "scrape x"}

    def test_publish_reasoning_activity(self, publisher, redis):
        assert publisher.publish_reasoning_activity("t1", "a1", "analysis",
                                                    state="thinking") is True
        event = json.loads(redis.published[0][1])
        assert event["activity_type"] == "reasoning"
        assert event["metadata"] == {"phase": "analysis"}

    def test_publish_reasoning_default_state(self, publisher, redis):
        publisher.publish_reasoning_activity("t1", "a1", "analysis")
        event = json.loads(redis.published[0][1])
        assert event["state"] == "thinking"

    def test_publish_episode_recording(self, publisher, redis):
        assert publisher.publish_episode_recording("t1", "a1", "ep-1") is True
        event = json.loads(redis.published[0][1])
        assert event["activity_type"] == "episode-recording"
        assert event["state"] == "completed"
        assert event["metadata"] == {"episode_id": "ep-1"}

    def test_publish_episode_recording_custom_status(self, publisher, redis):
        publisher.publish_episode_recording("t1", "a1", "ep-1", status="failed")
        event = json.loads(redis.published[0][1])
        assert event["state"] == "failed"

    def test_helpers_disabled_mode(self):
        publisher = ActivityPublisher()
        assert publisher.publish_skill_execution("t1", "a1", "s", "running") is False
        assert publisher.publish_reasoning_activity("t1", "a1", "p") is False
        assert publisher.publish_episode_recording("t1", "a1", "e") is False


# ============================================================================
# get_activity_publisher factory
# ============================================================================

class TestGetActivityPublisher:
    def test_redis_enabled(self):
        redis = _FakeRedis()
        config = SimpleNamespace(redis=SimpleNamespace(enabled=True,
                                                       url="redis://localhost:6379/0"))
        with patch("core.config.get_config", return_value=config), \
                patch.dict("sys.modules", {"redis": _FakeRedisModule()}) as modules:
            redis_mod = modules["redis"]
            redis_mod.from_url.return_value = redis
            publisher = get_activity_publisher()
        assert publisher.enabled is True
        assert publisher.redis is redis
        redis_mod.from_url.assert_called_once_with("redis://localhost:6379/0")

    def test_redis_disabled_in_config(self):
        config = SimpleNamespace(redis=SimpleNamespace(enabled=False))
        with patch("core.config.get_config", return_value=config):
            publisher = get_activity_publisher()
        assert publisher.enabled is False

    def test_config_error_falls_back(self):
        with patch("core.config.get_config",
                   side_effect=RuntimeError("no config")):
            publisher = get_activity_publisher()
        assert publisher.enabled is False

    def test_redis_import_error_falls_back(self):
        config = SimpleNamespace(redis=SimpleNamespace(enabled=True,
                                                       url="redis://localhost:6379/0"))
        with patch("core.config.get_config", return_value=config), \
                patch.dict("sys.modules", {"redis": None}):
            publisher = get_activity_publisher()
        assert publisher.enabled is False

    def test_from_url_error_falls_back(self):
        config = SimpleNamespace(redis=SimpleNamespace(enabled=True,
                                                       url="redis://localhost:6379/0"))
        with patch("core.config.get_config", return_value=config), \
                patch.dict("sys.modules", {"redis": _FakeRedisModule()}) as modules:
            redis_mod = modules["redis"]
            redis_mod.from_url.side_effect = RuntimeError("bad url")
            publisher = get_activity_publisher()
        assert publisher.enabled is False
