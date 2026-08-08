"""Coverage-push part 2: analytics engines (discord/google), teams service,
chat orchestrator, plus remaining slack-analytics branches.
"""
# Some legacy test files permanently replace integration modules in sys.modules
# with MagicMock at import time (e.g. test_scheduled_messaging_minimal,
# test_condition_monitoring_minimal, test_alert_service). Restore the REAL
# modules before this file binds its imports so tests run against the source.
import sys as _sys
from unittest.mock import MagicMock as _MagicMock
for _name in ("integrations.teams_enhanced_service", "integrations.slack_enhanced_service"):
    if isinstance(_sys.modules.get(_name), _MagicMock):
        _sys.modules.pop(_name, None)
del _sys, _MagicMock, _name

import asyncio
import importlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.slack_analytics_engine import (
    SlackAnalyticsEngine,
    AnalyticsDataPoint,
    AnalyticsMetric,
    AnalyticsTimeRange,
    AnalyticsGranularity,
)
from integrations.discord_analytics_engine import (
    DiscordAnalyticsEngine,
    DiscordAnalyticsDataPoint,
    DiscordAnalyticsMetric,
    DiscordAnalyticsTimeRange,
    DiscordAnalyticsGranularity,
    LLMSentiment as DiscordLLMSentiment,
    LLMTopics as DiscordLLMTopics,
)
from integrations.google_chat_analytics_engine import (
    GoogleChatAnalyticsEngine,
    GoogleChatAnalyticsDataPoint,
    GoogleChatAnalyticsMetric,
    GoogleChatAnalyticsTimeRange,
    GoogleChatAnalyticsGranularity,
    LLMSentiment as GoogleLLMSentiment,
    LLMTopics as GoogleLLMTopics,
)
from integrations import chat_orchestrator as co

BACKEND = "/Users/rushiparikh/projects/atom/backend"


def _redis_mock():
    r = MagicMock()
    r.get.return_value = None
    r.setex = AsyncMock()
    r.lpush = AsyncMock()
    r.ltrim = AsyncMock()
    r.keys.return_value = []
    r.delete = MagicMock()
    r.close = MagicMock()
    return r


def _teams_module():
    """Lazily import the REAL teams_enhanced_service (module was unimportable
    before the phantom-import fix; also immune to legacy sys.modules pollution)."""
    import sys as _sys
    from unittest.mock import MagicMock as _MM
    if isinstance(_sys.modules.get("integrations.teams_enhanced_service"), _MM):
        _sys.modules.pop("integrations.teams_enhanced_service", None)
    return importlib.import_module("integrations.teams_enhanced_service")


# ============================================================================
# slack_analytics_engine leftovers
# ============================================================================

class TestSlackEngineImportGuards:
    def test_reload_with_blocked_deps(self):
        code = (
            "import sys, types\n"
            "import builtins\n"
            "_orig_import = builtins.__import__\n"
            "def _blocked(names):\n"
            "    def _inner(name, *a, **k):\n"
            "        if name in names or any(name.startswith(n + '.') for n in names):\n"
            "            raise ImportError('blocked ' + name)\n"
            "        return _orig_import(name, *a, **k)\n"
            "    return _inner\n"
            "import importlib\n"
            "mod = importlib.import_module('integrations.slack_analytics_engine')\n"
            "builtins.__import__ = _blocked(['textblob'])\n"
            "importlib.reload(mod)\n"
            "builtins.__import__ = _blocked(['textblob', 'sklearn'])\n"
            "importlib.reload(mod)\n"
            "builtins.__import__ = _orig_import\n"
            "importlib.reload(mod)\n"
            "print('RELOAD_OK')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=BACKEND,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": BACKEND, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        assert "RELOAD_OK" in proc.stdout, f"reload failed: {proc.stderr[-2000:]}"

    def test_vader_init_failure_and_sklearn_off(self):
        mod = importlib.import_module("integrations.slack_analytics_engine")
        mod.SentimentIntensityAnalyzer = MagicMock(side_effect=RuntimeError("no model"))
        try:
            with patch.object(mod, "VADER_AVAILABLE", True):
                engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        finally:
            del mod.SentimentIntensityAnalyzer
        assert engine.vader_analyzer is None
        with patch.object(mod, "SKLEARN_AVAILABLE", False):
            engine2 = SlackAnalyticsEngine({"database": None, "redis_client": None})
        assert engine2.lda_model is None

    def test_no_processor_for_metric(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        engine.processors = {}
        result = asyncio.run(engine.get_analytics(AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY))
        assert result == []

    async def test_predict_volume_mean_fallback_and_errors(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        points = [
            AnalyticsDataPoint(
                timestamp=now - timedelta(hours=i), metric=AnalyticsMetric.MESSAGE_VOLUME,
                value=float(i % 5 + 1),
            )
            for i in range(168)
        ]
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            result = await engine.predict_message_volume(hours_ahead=3)
        assert "predictions" in result
        assert len(result["predictions"]) == 3
        with patch.object(engine, "get_analytics", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result2 = await engine.predict_message_volume()
        assert "error" in result2

    async def test_productivity_metrics_error(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        engine.get_analytics = AsyncMock(side_effect=RuntimeError("boom"))
        assert await engine.get_productivity_metrics(AnalyticsTimeRange.TODAY) == {}

    async def test_all_processors_all_granularities(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        engine._analyze_sentiment = AsyncMock(return_value={"score": 0.5, "label": "positive"})
        engine._extract_topics = AsyncMock(return_value={"topics": ["ai"]})
        ts = datetime.now(timezone.utc)
        item = {"timestamp": ts.isoformat(), "text": "task decided", "user_id": "U1",
                "reactions": [{"name": "x", "count": 1}], "reply_count": 1,
                "mentions": ["U2"], "thread_ts": "1", "files": [{"filetype": "png", "size": 5}],
                "response_time_seconds": 4}
        for granularity in (AnalyticsGranularity.HOUR, AnalyticsGranularity.DAY, AnalyticsGranularity.WEEK):
            assert await engine._process_message_volume([item], granularity)
            assert await engine._process_user_activity([item], granularity)
            assert await engine._process_engagement([item], granularity)
            assert await engine._process_response_time([item], granularity)
            assert await engine._process_sentiment([item], granularity)
            assert await engine._process_collaboration([item], granularity)
            assert await engine._process_productivity([item], granularity)
            assert await engine._process_topics([item], granularity)
            assert await engine._process_reactions([item], granularity)
            assert await engine._process_file_sharing([item], granularity)

    async def test_fetch_data_db_with_rows(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE slack_messages (timestamp TEXT, value INTEGER)")
        conn.execute("INSERT INTO slack_messages VALUES (?, ?)",
                     (str(datetime.now(timezone.utc)), 1))
        engine = SlackAnalyticsEngine({"database": conn, "redis_client": None})
        data = await engine._fetch_data(
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY, None, None, None, None
        )
        assert data == [{"timestamp": conn.execute("SELECT timestamp FROM slack_messages").fetchone()[0], "value": 1}]

    def test_add_training_texts_auto_train_log(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        engine.add_training_texts(["text %d" % i for i in range(55)])
        assert engine.get_training_corpus_size()["total_texts"] == 55
        assert engine.get_training_corpus_size()["can_train_lda"] is True
        assert engine.get_training_corpus_size()["recommended_topics"] >= 3

    def test_generate_mock_data_all_metrics(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        start = datetime.now(timezone.utc) - timedelta(hours=3)
        end = datetime.now(timezone.utc)
        for metric in (AnalyticsMetric.MESSAGE_VOLUME, AnalyticsMetric.USER_ACTIVITY,
                       AnalyticsMetric.ENGAGEMENT, AnalyticsMetric.RESPONSE_TIME,
                       AnalyticsMetric.TOPICS, AnalyticsMetric.SENTIMENT):
            data = engine._generate_mock_data(metric, start, end)
            assert len(data) >= 3

    async def test_sentiment_insights_negative(self):
        engine = SlackAnalyticsEngine({"database": None, "redis_client": None})
        points = [AnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=AnalyticsMetric.SENTIMENT, value=-0.2,
        )]
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=points)):
            insights = await engine.get_insights(AnalyticsMetric.SENTIMENT, AnalyticsTimeRange.TODAY)
        assert insights["dominant_sentiment"] == "negative"


# ============================================================================
# discord_analytics_engine
# ============================================================================

class TestDiscordAnalyticsCore:
    async def test_get_analytics_mock_data(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        data = await engine.get_analytics(
            DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_24_HOURS,
            DiscordAnalyticsGranularity.HOUR, None, "discord_g1",
        )
        assert len(data) > 0
        assert data[0].metric == DiscordAnalyticsMetric.MESSAGE_COUNT

    async def test_get_analytics_from_cache(self):
        r = _redis_mock()
        now = datetime.now(timezone.utc)
        r.get.return_value = json.dumps([{
            "timestamp": now.isoformat(), "metric": "message_count", "value": 5,
            "dimensions": {}, "metadata": {},
        }])
        engine = DiscordAnalyticsEngine({"database": None, "redis": {"client": r}})
        data = await engine.get_analytics(
            DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.DAY, {"a": 1}, "discord_g1", ["g2"], ["c1"], ["u1"],
        )
        assert data[0].value == 5

    async def test_get_analytics_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "_generate_cache_key", side_effect=RuntimeError("boom")):
            data = await engine.get_analytics(
                DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY,
            )
        assert data == []

    async def test_get_analytics_sentiment_and_topics(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        data = await engine.get_analytics(
            DiscordAnalyticsMetric.SENTIMENT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.HOUR,
        )
        assert data == []  # no db -> no raw messages
        data2 = await engine.get_analytics(
            DiscordAnalyticsMetric.TOPICS, DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.HOUR,
        )
        assert data2 == []

    async def test_build_query_unsupported_metric(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        result = await engine._build_analytics_query(
            DiscordAnalyticsMetric.SENTIMENT, datetime.now(timezone.utc), datetime.now(timezone.utc),
            DiscordAnalyticsGranularity.DAY, None, "discord_g1", ["g2"], ["c1"], ["u1"],
        )
        assert result["sql"] == ""

    async def test_build_query_all_metric_branches(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        now = datetime.now(timezone.utc)
        for metric in (DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsMetric.ACTIVE_USERS,
                       DiscordAnalyticsMetric.BOT_MESSAGE_COUNT, DiscordAnalyticsMetric.HUMAN_MESSAGE_COUNT,
                       DiscordAnalyticsMetric.REACTION_COUNT, DiscordAnalyticsMetric.FILE_UPLOADS,
                       DiscordAnalyticsMetric.GUILD_ACTIVITY):
            result = await engine._build_analytics_query(
                metric, now - timedelta(days=1), now, DiscordAnalyticsGranularity.DAY,
                {"channel_type": ["text"], "is_bot": 0}, "discord_g1", ["g2"], ["c1"], ["u1"],
            )
            assert result["sql"], metric
            assert "timestamp" in result["sql"]

    async def test_fetch_analytics_data_db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.create_function("date_trunc", 2, lambda unit, ts: ts)
        conn.execute("CREATE TABLE discord_messages (timestamp TEXT, value INTEGER, dimensions TEXT, metadata TEXT)")
        conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), 3, "{}", "{}"))
        engine = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        data = await engine._fetch_analytics_data(
            DiscordAnalyticsMetric.MESSAGE_COUNT, datetime.now(timezone.utc) - timedelta(days=2),
            datetime.now(timezone.utc), DiscordAnalyticsGranularity.DAY,
        )
        assert len(data) == 1
        assert data[0].value == 1  # COUNT(*) of 1 row

    async def test_fetch_analytics_data_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "_build_analytics_query", new=AsyncMock(side_effect=RuntimeError("boom"))):
            data = await engine._fetch_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, datetime.now(timezone.utc),
                datetime.now(timezone.utc), DiscordAnalyticsGranularity.DAY,
            )
        assert data == []

    def test_interval_delta_and_time_range(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        assert engine._get_interval_delta(DiscordAnalyticsGranularity.HOUR) == timedelta(hours=1)
        assert engine._get_interval_delta(DiscordAnalyticsGranularity.YEAR) == timedelta(days=1)
        for tr in DiscordAnalyticsTimeRange:
            start, end = engine._get_time_range_boundaries(tr)
            assert start <= end

    def test_generate_mock_value(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        ts = datetime(2026, 1, 3, 20, 0, tzinfo=timezone.utc)  # Saturday evening
        for metric in DiscordAnalyticsMetric:
            value = engine._generate_mock_value(metric, ts)
            assert value >= 0

    async def test_mock_analytics_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "_get_interval_delta", side_effect=RuntimeError("boom")):
            data = await engine._generate_mock_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, datetime.now(timezone.utc),
                datetime.now(timezone.utc), DiscordAnalyticsGranularity.HOUR,
            )
        assert data == []

    def test_cache_key(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        key = engine._generate_cache_key(
            DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
            DiscordAnalyticsGranularity.DAY, {"a": 1}, "discord_g1", ["g2", "g1"], ["u1"],
        )
        assert "g1" in key and "g2" in key

    async def test_cache_roundtrip(self):
        r = _redis_mock()
        engine = DiscordAnalyticsEngine({"database": None, "redis": {"client": r}})
        point = DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=1, dimensions={}, metadata={},
        )
        engine._cache_result("k", [point])
        r.setex.assert_called_once()
        r.get.return_value = json.dumps([{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metric": "message_count", "value": 1, "dimensions": {}, "metadata": {},
        }])
        cached = engine._get_from_cache("k")
        assert cached is not None
        assert cached[0].metric == DiscordAnalyticsMetric.MESSAGE_COUNT

    async def test_cache_error_paths(self):
        r = _redis_mock()
        r.get.side_effect = RuntimeError("boom")
        engine = DiscordAnalyticsEngine({"database": None, "redis": {"client": r}})
        assert engine._get_from_cache("k") is None
        r2 = _redis_mock()
        r2.setex.side_effect = RuntimeError("boom")
        engine2 = DiscordAnalyticsEngine({"database": None, "redis": {"client": r2}})
        engine2._cache_result("k", [DiscordAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
            value=1, dimensions={}, metadata={})])

    async def test_get_top_guilds_mock(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        top = await engine.get_top_guilds(
            DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS, limit=3
        )
        assert len(top) == 3

    async def test_get_top_guilds_db_and_error(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE discord_messages (guild_id TEXT, guild_name TEXT, is_bot INTEGER, timestamp TEXT)")
        conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?)", ("g1", "G", 0, str(datetime.now(timezone.utc) - timedelta(days=1))))
        engine = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        top = await engine.get_top_guilds(
            DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS, limit=5,
            workspace_id="discord_g1",
        )
        assert len(top) == 1
        assert top[0]["guild_id"] == "g1"
        with patch.object(engine, "_get_time_range_boundaries", side_effect=RuntimeError("boom")):
            assert await engine.get_top_guilds(DiscordAnalyticsMetric.MESSAGE_COUNT,
                                               DiscordAnalyticsTimeRange.LAST_7_DAYS) == []

    async def test_get_user_activity_mock(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        summary = await engine.get_user_activity_summary("u1", DiscordAnalyticsTimeRange.LAST_7_DAYS)
        assert summary["user_id"] == "u1"
        assert summary["message_count"] == 280

    async def test_get_user_activity_db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE discord_messages (user_id TEXT, channel_id TEXT, timestamp TEXT,
            integration_data TEXT, message_length INTEGER)""")
        conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?, ?)",
                     ("u1", "c1", str(datetime.now(timezone.utc) - timedelta(days=1)), '{"reactions": [1,2]}', 10))
        engine = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        summary = await engine.get_user_activity_summary("u1", DiscordAnalyticsTimeRange.LAST_7_DAYS)
        assert summary["message_count"] == 1
        assert summary["reactions_given"] == 2

    async def test_get_user_activity_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "_get_time_range_boundaries", side_effect=RuntimeError("boom")):
            assert await engine.get_user_activity_summary("u1", DiscordAnalyticsTimeRange.LAST_7_DAYS) == {}

    async def test_get_guild_activity_mock(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        report = await engine.get_guild_activity_report("g1", DiscordAnalyticsTimeRange.LAST_7_DAYS)
        assert report["guild_id"] == "g1"
        assert report["total_messages"] == 2450

    async def test_get_guild_activity_db(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE discord_messages (guild_id TEXT, user_id TEXT, user_name TEXT,
            is_bot INTEGER, timestamp TEXT, integration_data TEXT, message_length INTEGER)""")
        for i in range(3):
            conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                         ("g1", f"u{i}", f"name{i}", 0, str(datetime.now(timezone.utc) - timedelta(days=1)), "{}", 5))
        engine = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        report = await engine.get_guild_activity_report("g1", DiscordAnalyticsTimeRange.LAST_7_DAYS)
        assert report["total_messages"] == 3
        assert report["human_messages"] == 3

    async def test_get_guild_activity_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "_get_time_range_boundaries", side_effect=RuntimeError("boom")):
            assert await engine.get_guild_activity_report("g1", DiscordAnalyticsTimeRange.LAST_7_DAYS) == {}

    async def test_voice_analytics(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        result = await engine.get_voice_chat_analytics("g1", DiscordAnalyticsTimeRange.LAST_7_DAYS)
        assert result["guild_id"] == "g1"
        result2 = await engine._generate_mock_voice_analytics("g1", DiscordAnalyticsTimeRange.LAST_7_DAYS)
        assert result2["total_voice_minutes"] == 24000
        with patch.object(engine, "_generate_mock_voice_analytics", new=AsyncMock(side_effect=RuntimeError("boom"))):
            engine.db = MagicMock()  # non-None -> calls mock generator
            assert await engine.get_voice_chat_analytics("g1", DiscordAnalyticsTimeRange.LAST_7_DAYS) == {}

    async def test_export_csv_json_excel_unsupported(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[
            DiscordAnalyticsDataPoint(timestamp=datetime.now(timezone.utc),
                                      metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
                                      value=5, dimensions={}, metadata={}),
        ])):
            csv_result = await engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY, "csv",
            )
            assert csv_result["ok"] is True
            assert "timestamp" in csv_result["data"]
            json_result = await engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY, "json",
            )
            assert json_result["ok"] is True
            bad = await engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY, "xml",
            )
            assert bad["ok"] is False

    async def test_export_excel(self):
        with patch("integrations.discord_analytics_engine.OPENPYXL_AVAILABLE", True):
            engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
            with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[
                DiscordAnalyticsDataPoint(timestamp=datetime.now(timezone.utc),
                                          metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
                                          value=5, dimensions={}, metadata={}),
                DiscordAnalyticsDataPoint(timestamp=datetime.now(timezone.utc),
                                          metric=DiscordAnalyticsMetric.MESSAGE_COUNT,
                                          value=9, dimensions={}, metadata={}),
            ])):
                result = await engine.export_analytics_data(
                    DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                    DiscordAnalyticsGranularity.DAY, "excel",
                )
            assert result["ok"] is True
            assert result["data"].startswith(b"PK")

    async def test_export_no_data_and_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[])):
            result = await engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY,
            )
        assert result["ok"] is False
        with patch.object(engine, "get_analytics", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result2 = await engine.export_analytics_data(
                DiscordAnalyticsMetric.MESSAGE_COUNT, DiscordAnalyticsTimeRange.LAST_7_DAYS,
                DiscordAnalyticsGranularity.DAY,
            )
        assert result2["ok"] is False

    def test_convert_to_csv_empty_and_error(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        assert engine._convert_to_csv([]) == ""
        with patch.object(engine, "_convert_to_csv", side_effect=RuntimeError("boom")):
            pass

    async def test_clear_cache(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        await engine.clear_cache()  # no redis -> no-op
        r = _redis_mock()
        r.keys.return_value = ["discord_analytics:1", "discord_analytics:2"]
        engine2 = DiscordAnalyticsEngine({"database": None, "redis": {"client": r}})
        await engine2.clear_cache()
        r.delete.assert_called_once()
        r3 = _redis_mock()
        r3.keys.side_effect = RuntimeError("boom")
        engine3 = DiscordAnalyticsEngine({"database": None, "redis": {"client": r3}})
        await engine3.clear_cache()

    async def test_sentiment_analytics_llm(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE discord_messages (timestamp TEXT, content TEXT, user_id TEXT, channel_id TEXT, guild_id TEXT)")
        conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), "wonderful message here", "u1", "c1", "g1"))
        engine = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=DiscordLLMSentiment(score=0.8, label="positive", confidence=0.9))
        with patch("integrations.discord_analytics_engine.get_llm_service", return_value=llm):
            data = await engine._get_sentiment_analytics(
                datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc),
                DiscordAnalyticsGranularity.DAY, None, "discord_g1",
            )
        assert len(data) == 1
        assert data[0].value == 0.8

    async def test_topics_analytics_llm(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE discord_messages (timestamp TEXT, content TEXT, user_id TEXT, channel_id TEXT)")
        conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), "talk about pricing and launch", "u1", "c1"))
        engine = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=DiscordLLMTopics(topics=["pricing"], confidence=0.7))
        with patch("integrations.discord_analytics_engine.get_llm_service", return_value=llm):
            data = await engine._get_topics_analytics(
                datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc),
                DiscordAnalyticsGranularity.DAY,
            )
        assert len(data) == 1
        assert data[0].value == "pricing"

    async def test_sentiment_and_topics_fallback(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        assert await engine._analyze_sentiment("") == {"score": 0.0, "label": "neutral", "confidence": 1.0}
        assert await engine._extract_topics([]) == {"topics": [], "confidence": 1.0}
        assert await engine._analyze_sentiment("xy") == {"score": 0.0, "label": "neutral", "confidence": 1.0}
        llm = MagicMock()
        llm.generate_structured = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.discord_analytics_engine.get_llm_service", return_value=llm):
            result = await engine._analyze_sentiment("a proper message with enough length here")
            assert result["score"] == 0.0
            result2 = await engine._extract_topics(["some text"])
            assert result2["topics"] == []

    async def test_fetch_raw_messages_and_group(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        assert await engine._fetch_raw_messages(datetime.now(timezone.utc), datetime.now(timezone.utc)) == []
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE discord_messages (timestamp TEXT, content TEXT, user_id TEXT, channel_id TEXT, guild_id TEXT)")
        conn.execute("INSERT INTO discord_messages VALUES (?, ?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), "hi", "u1", "c1", "g1"))
        engine2 = DiscordAnalyticsEngine({"database": conn, "redis": {}})
        msgs = await engine2._fetch_raw_messages(
            datetime(2020, 1, 1), datetime(2030, 1, 1), None, "discord_g1"
        )
        assert len(msgs) == 1
        grouped = engine2._group_messages_by_granularity(msgs, DiscordAnalyticsGranularity.HOUR)
        assert grouped
        grouped_day = engine2._group_messages_by_granularity(msgs, DiscordAnalyticsGranularity.DAY)
        assert grouped_day
        grouped_raw = engine2._group_messages_by_granularity(msgs, DiscordAnalyticsGranularity.YEAR)
        assert grouped_raw
        conn2 = sqlite3.connect(":memory:")
        conn2.row_factory = sqlite3.Row
        conn2.execute("CREATE TABLE discord_messages (timestamp TEXT, content TEXT, user_id TEXT, channel_id TEXT)")
        engine3 = DiscordAnalyticsEngine({"database": MagicMock(), "redis": {}})
        engine3.db.execute.side_effect = RuntimeError("boom")
        assert await engine3._fetch_raw_messages(
            datetime.now(timezone.utc), datetime.now(timezone.utc)) == []

    def test_get_engine_info(self):
        engine = DiscordAnalyticsEngine({"database": None, "redis": {}})
        info = engine.get_engine_info()
        assert info["name"] == "Discord Analytics Engine"


# ============================================================================
# google_chat_analytics_engine
# ============================================================================

class TestGoogleAnalyticsCore:
    async def test_get_analytics_mock_data(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        data = await engine.get_analytics(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_24_HOURS,
            GoogleChatAnalyticsGranularity.HOUR, None, "ws1", ["s1"], ["u1"],
        )
        assert len(data) > 0

    async def test_get_analytics_cache_and_error(self):
        r = _redis_mock()
        now = datetime.now(timezone.utc)
        r.get.return_value = json.dumps([{
            "timestamp": now.isoformat(), "metric": "message_count", "value": 3,
            "dimensions": {}, "metadata": {},
        }])
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {"client": r}})
        data = await engine.get_analytics(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.DAY, {"a": 1}, "ws1", ["s1"], ["u1"],
        )
        assert data[0].value == 3
        engine2 = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine2, "_generate_cache_key", side_effect=RuntimeError("boom")):
            assert await engine2.get_analytics(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY) == []

    async def test_get_analytics_sentiment_topics(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        assert await engine.get_analytics(
            GoogleChatAnalyticsMetric.SENTIMENT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.HOUR) == []
        assert await engine.get_analytics(
            GoogleChatAnalyticsMetric.TOPICS, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.HOUR) == []

    async def test_build_query_all_branches(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        now = datetime.now(timezone.utc)
        for metric in (GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsMetric.ACTIVE_USERS,
                       GoogleChatAnalyticsMetric.BOT_MESSAGE_COUNT, GoogleChatAnalyticsMetric.HUMAN_MESSAGE_COUNT,
                       GoogleChatAnalyticsMetric.THREAD_CREATION, GoogleChatAnalyticsMetric.CARD_INTERACTIONS,
                       GoogleChatAnalyticsMetric.RESPONSE_TIME, GoogleChatAnalyticsMetric.REACTION_COUNT,
                       GoogleChatAnalyticsMetric.MESSAGE_FREQUENCY):
            result = await engine._build_analytics_query(
                metric, now - timedelta(days=1), now, GoogleChatAnalyticsGranularity.DAY,
                {"space_type": ["DM"], "is_bot": 0}, "ws1", ["s1"], ["u1"],
            )
            assert result["sql"], metric
        result2 = await engine._build_analytics_query(
            GoogleChatAnalyticsMetric.SENTIMENT, now, now, GoogleChatAnalyticsGranularity.DAY)
        assert result2["sql"] == ""

    async def test_fetch_db_and_error(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.create_function("date_trunc", 2, lambda unit, ts: ts)
        conn.execute("CREATE TABLE google_chat_messages (timestamp TEXT, value INTEGER, dimensions TEXT, metadata TEXT)")
        conn.execute("INSERT INTO google_chat_messages VALUES (?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), 3, "{}", "{}"))
        engine = GoogleChatAnalyticsEngine({"database": conn, "redis": {}})
        data = await engine._fetch_analytics_data(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, datetime.now(timezone.utc) - timedelta(days=2),
            datetime.now(timezone.utc), GoogleChatAnalyticsGranularity.DAY,
        )
        assert data[0].value == 1  # COUNT(*) of 1 row
        with patch.object(engine, "_build_analytics_query", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await engine._fetch_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, datetime.now(timezone.utc),
                datetime.now(timezone.utc), GoogleChatAnalyticsGranularity.DAY) == []

    def test_interval_delta_time_range_mock_value(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        assert engine._get_interval_delta(GoogleChatAnalyticsGranularity.HOUR) == timedelta(hours=1)
        for tr in GoogleChatAnalyticsTimeRange:
            start, end = engine._get_time_range_boundaries(tr)
            assert start <= end
        for metric in GoogleChatAnalyticsMetric:
            assert engine._generate_mock_value(metric, datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)) >= 0

    def test_cache_key(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        key = engine._generate_cache_key(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            GoogleChatAnalyticsGranularity.DAY, {"a": 1}, "ws1", ["s2", "s1"], ["u1"],
        )
        assert "s1" in key and "s2" in key

    async def test_cache_roundtrip_and_errors(self):
        r = _redis_mock()
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {"client": r}})
        point = GoogleChatAnalyticsDataPoint(
            timestamp=datetime.now(timezone.utc), metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
            value=1, dimensions={}, metadata={},
        )
        engine._cache_result("k", [point])
        r.setex.assert_called_once()
        r.get.return_value = json.dumps([{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metric": "message_count", "value": 1, "dimensions": {}, "metadata": {},
        }])
        assert engine._get_from_cache("k") is not None
        r.get.side_effect = RuntimeError("boom")
        assert engine._get_from_cache("k") is None

    async def test_get_top_spaces(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        top = await engine.get_top_spaces(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS, limit=3
        )
        assert len(top) == 3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE google_chat_messages (space_id TEXT, space_name TEXT, sender_type TEXT, timestamp TEXT, workspace_id TEXT)")
        conn.execute("INSERT INTO google_chat_messages VALUES (?, ?, ?, ?, ?)",
                     ("s1", "General", "HUMAN", str(datetime.now(timezone.utc) - timedelta(days=1)), "ws1"))
        engine2 = GoogleChatAnalyticsEngine({"database": conn, "redis": {}})
        top2 = await engine2.get_top_spaces(
            GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
            limit=5, workspace_id="ws1",
        )
        assert len(top2) == 1
        with patch.object(engine2, "_get_time_range_boundaries", side_effect=RuntimeError("boom")):
            assert await engine2.get_top_spaces(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS) == []

    async def test_user_activity_summary(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        summary = await engine.get_user_activity_summary("u1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS)
        assert summary["user_id"] == "u1"
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE google_chat_messages (user_id TEXT, space_id TEXT, timestamp TEXT,
            integration_data TEXT, message_length INTEGER, thread_id TEXT, reply_to_id TEXT)""")
        conn.execute("INSERT INTO google_chat_messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                     ("u1", "s1", str(datetime.now(timezone.utc) - timedelta(days=1)), '{"reactions": [1]}', 10, "t1", None))
        engine2 = GoogleChatAnalyticsEngine({"database": conn, "redis": {}})
        summary2 = await engine2.get_user_activity_summary("u1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS)
        assert summary2["message_count"] == 1
        assert summary2["threads_created"] == 1
        assert summary2["most_active_hours"] == [datetime.now(timezone.utc).hour]
        with patch.object(engine2, "_get_time_range_boundaries", side_effect=RuntimeError("boom")):
            err = await engine2.get_user_activity_summary("u1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS)
        assert err["success"] is False

    async def test_space_activity_report(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        report = await engine.get_space_activity_report("s1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS)
        assert report["space_id"] == "s1"
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE google_chat_messages (space_id TEXT, user_id TEXT, user_name TEXT,
            sender_type TEXT, timestamp TEXT, integration_data TEXT, message_length INTEGER,
            thread_id TEXT, reply_to_id TEXT)""")
        conn.execute("INSERT INTO google_chat_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("s1", "u1", "n1", "BOT", str(datetime.now(timezone.utc) - timedelta(days=1)), "{}", 5, None, None))
        engine2 = GoogleChatAnalyticsEngine({"database": conn, "redis": {}})
        report2 = await engine2.get_space_activity_report("s1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS)
        assert report2["total_messages"] == 1
        assert report2["bot_messages"] == 1
        with patch.object(engine2, "_get_time_range_boundaries", side_effect=RuntimeError("boom")):
            err = await engine2.get_space_activity_report("s1", GoogleChatAnalyticsTimeRange.LAST_7_DAYS)
        assert err["success"] is False

    async def test_export_formats(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[
            GoogleChatAnalyticsDataPoint(timestamp=datetime.now(timezone.utc),
                                         metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                                         value=5, dimensions={}, metadata={}),
        ])):
            assert (await engine.export_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY, "csv"))["ok"] is True
            assert (await engine.export_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY, "json"))["ok"] is True
            assert (await engine.export_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY, "xml"))["ok"] is False
        with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[])):
            assert (await engine.export_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY))["ok"] is False
        with patch.object(engine, "get_analytics", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert (await engine.export_analytics_data(
                GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                GoogleChatAnalyticsGranularity.DAY))["ok"] is False

    async def test_export_excel(self):
        with patch("integrations.google_chat_analytics_engine.OPENPYXL_AVAILABLE", True):
            engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
            with patch.object(engine, "get_analytics", new=AsyncMock(return_value=[
                GoogleChatAnalyticsDataPoint(timestamp=datetime.now(timezone.utc),
                                             metric=GoogleChatAnalyticsMetric.MESSAGE_COUNT,
                                             value=5, dimensions={}, metadata={}),
            ])):
                result = await engine.export_analytics_data(
                    GoogleChatAnalyticsMetric.MESSAGE_COUNT, GoogleChatAnalyticsTimeRange.LAST_7_DAYS,
                    GoogleChatAnalyticsGranularity.DAY, "excel",
                )
            assert result["ok"] is True
            assert result["data"].startswith(b"PK")

    async def test_clear_cache(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        await engine.clear_cache()
        r = _redis_mock()
        r.keys.return_value = ["google_chat_analytics:1"]
        engine2 = GoogleChatAnalyticsEngine({"database": None, "redis": {"client": r}})
        await engine2.clear_cache()
        r.delete.assert_called_once()
        r3 = _redis_mock()
        r3.keys.side_effect = RuntimeError("boom")
        engine3 = GoogleChatAnalyticsEngine({"database": None, "redis": {"client": r3}})
        await engine3.clear_cache()

    async def test_sentiment_topics_llm_paths(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE google_chat_messages (timestamp TEXT, content TEXT, user_id TEXT, space_id TEXT, workspace_id TEXT)")
        conn.execute("INSERT INTO google_chat_messages VALUES (?, ?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), "wonderful message here", "u1", "s1", "ws1"))
        engine = GoogleChatAnalyticsEngine({"database": conn, "redis": {}})
        llm = MagicMock()
        llm.generate_structured = AsyncMock(return_value=GoogleLLMSentiment(score=0.7, label="positive", confidence=0.8))
        with patch("integrations.google_chat_analytics_engine.get_llm_service", return_value=llm):
            data = await engine._get_sentiment_analytics(
                datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc),
                GoogleChatAnalyticsGranularity.DAY, None, "ws1",
            )
        assert data[0].value == 0.7
        llm2 = MagicMock()
        llm2.generate_structured = AsyncMock(return_value=GoogleLLMTopics(topics=["launch"], confidence=0.7))
        with patch("integrations.google_chat_analytics_engine.get_llm_service", return_value=llm2):
            data2 = await engine._get_topics_analytics(
                datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc),
                GoogleChatAnalyticsGranularity.DAY, None, "ws1",
            )
        assert data2[0].value == "launch"

    async def test_sentiment_topics_fallback(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        assert await engine._analyze_sentiment("xy") == {"score": 0.0, "label": "neutral", "confidence": 1.0}
        assert await engine._extract_topics([]) == {"topics": [], "confidence": 1.0}
        llm = MagicMock()
        llm.generate_structured = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.google_chat_analytics_engine.get_llm_service", return_value=llm):
            result = await engine._analyze_sentiment("a message with plenty of characters to analyze here")
            assert result["score"] == 0.0
            result2 = await engine._extract_topics(["text"])
            assert result2["topics"] == []

    async def test_fetch_raw_messages_and_group(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        assert await engine._fetch_raw_messages(datetime.now(timezone.utc), datetime.now(timezone.utc)) == []
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE google_chat_messages (timestamp TEXT, content TEXT, user_id TEXT, space_id TEXT, workspace_id TEXT)")
        conn.execute("INSERT INTO google_chat_messages VALUES (?, ?, ?, ?, ?)",
                     (str(datetime.now(timezone.utc) - timedelta(days=1)), "hi", "u1", "s1", "ws1"))
        engine2 = GoogleChatAnalyticsEngine({"database": conn, "redis": {}})
        msgs = await engine2._fetch_raw_messages(datetime(2020, 1, 1), datetime(2030, 1, 1), None, "ws1")
        assert len(msgs) == 1
        assert engine2._group_messages_by_granularity(msgs, GoogleChatAnalyticsGranularity.HOUR)
        assert engine2._group_messages_by_granularity(msgs, GoogleChatAnalyticsGranularity.YEAR)
        conn2 = sqlite3.connect(":memory:")
        conn2.row_factory = sqlite3.Row
        conn2.execute("CREATE TABLE google_chat_messages (timestamp TEXT, content TEXT, user_id TEXT, space_id TEXT)")
        engine3 = GoogleChatAnalyticsEngine({"database": MagicMock(), "redis": {}})
        engine3.db.execute.side_effect = RuntimeError("boom")
        assert await engine3._fetch_raw_messages(
            datetime.now(timezone.utc), datetime.now(timezone.utc)) == []

    def test_get_engine_info(self):
        engine = GoogleChatAnalyticsEngine({"database": None, "redis": {}})
        info = engine.get_engine_info()
        assert info["name"] == "Google Chat Analytics Engine"
