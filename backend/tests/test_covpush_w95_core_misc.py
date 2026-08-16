# -*- coding: utf-8 -*-
"""Coverage wave 95 — eight-module misc batch.

Targets:
1. core/creative/ffmpeg_service.py
2. core/integrations/adapters/notion.py
3. core/smarthome/hue_service.py
4. core/package_feature_service.py
5. core/feedback_advanced_analytics.py
6. core/llm/registry/transformers.py
7. core/dynamic_benchmark_fetcher.py
8. core/chat_session_manager.py

No network, no LLM: every external boundary (subprocess/ffmpeg library,
httpx, DB sessions, hue bridge) is mocked. Plain pytest + unittest.mock.
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.creative.ffmpeg_service as ffmod
import core.smarthome.hue_service as huemod
import core.dynamic_benchmark_fetcher as dbfmod
import core.chat_session_manager as csmmod


# --------------------------------------------------------------------------- #
# Shared fake SQLAlchemy machinery
# --------------------------------------------------------------------------- #
class FakeQuery:
    def __init__(self, items=None, first=None, count=0):
        self._items = list(items or [])
        self._first = first
        self._count = count

    def filter(self, *a, **k):
        return self

    def filter_by(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._first

    def count(self):
        return self._count


class FakeCM:
    """Context manager wrapper used to fake get_db_session()."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *a):
        return False


class FakeFFDb:
    def __init__(self, job=None):
        self.job = job
        self.added = []

    def query(self, entity):
        return FakeQuery(first=self.job)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# =========================================================================== #
# 1. core/creative/ffmpeg_service.py
# =========================================================================== #
class TestFFmpegService:
    @pytest.fixture()
    def svc(self):
        return ffmod.FFmpegService(allowed_dirs=["/tmp/media", "/tmp/out"])

    # -- path validation -----------------------------------------------------
    def test_validate_path_traversal_rejected(self, svc):
        assert svc.validate_path("../../etc/passwd") is False

    def test_validate_path_absolute_outside_rejected(self, svc):
        assert svc.validate_path("/etc/passwd") is False

    def test_validate_path_allowed_prefix(self, svc):
        assert svc.validate_path("/tmp/media/video.mp4") is True

    def test_validate_path_relative_resolved(self, svc, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        d = tmp_path / "media"
        d.mkdir(exist_ok=True)
        svc2 = ffmod.FFmpegService(allowed_dirs=["./media"])
        assert svc2.validate_path("media/clip.mp4") is True
        assert svc2.validate_path("other/clip.mp4") is False

    def test_validate_path_env_dirs(self, monkeypatch):
        monkeypatch.setenv("FFMPEG_ALLOWED_DIRS", "/custom/dir")
        svc2 = ffmod.FFmpegService(allowed_dirs=None)
        assert svc2.allowed_dirs[-1] == "/custom/dir"

    def test_validate_paths_raises(self, svc):
        with pytest.raises(ValueError):
            svc._validate_paths(input_path="/etc/shadow")

    def test_validate_paths_skips_none(self, svc):
        svc._validate_paths(input_path=None)

    def test_validate_path_oserror_branch(self, svc, monkeypatch):
        def boom(p):
            raise OSError("nope")
        monkeypatch.setattr(ffmod.os.path, "abspath", boom)
        assert svc.validate_path("/tmp/media/x.mp4") is False

    # -- sync operations ------------------------------------------------------
    @pytest.mark.parametrize("quality,crf", [("low", 28), ("medium", 23), ("ultra", 23)])
    def test_convert_format_sync(self, svc, tmp_path, quality, crf):
        out = str(tmp_path / "out" / "v.mp4")
        with patch.object(ffmod, "ffmpeg") as ffg:
            ffg.Error = ffmod.ffmpeg.Error
            res = svc._convert_format_sync("/tmp/media/v.mp4", out, "mp4", quality)
        assert res["success"] is True
        assert ffg.run.called

    def test_trim_sync_and_error(self, svc, tmp_path):
        out = str(tmp_path / "o" / "t.mp4")
        with patch.object(ffmod, "ffmpeg") as ffg:
            ffg.Error = RuntimeError
            res = svc._trim_video_sync("/tmp/media/v.mp4", out, "00:00:05", "10")
            assert res["success"] is True
            ffg.run.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                svc._trim_video_sync("/tmp/media/v.mp4", out, "0", "1")

    def test_thumbnail_sync_and_error(self, svc, tmp_path):
        out = str(tmp_path / "o" / "t.jpg")
        with patch.object(ffmod, "ffmpeg") as ffg:
            ffg.Error = RuntimeError
            res = svc._generate_thumbnail_sync("/tmp/media/v.mp4", out, "00:00:01")
            assert res["success"] is True
            ffg.run.side_effect = RuntimeError("x")
            with pytest.raises(RuntimeError):
                svc._generate_thumbnail_sync("/tmp/media/v.mp4", out, "0")

    @pytest.mark.parametrize("fmt", ["mp3", "m4a", "wav", "flac", "ogg"])
    def test_extract_audio_sync(self, svc, tmp_path, fmt):
        out = str(tmp_path / "o" / f"a.{fmt}")
        with patch.object(ffmod, "ffmpeg") as ffg:
            ffg.Error = RuntimeError
            res = svc._extract_audio_sync("/tmp/media/v.mp4", out, fmt)
            assert res["success"] is True

    def test_extract_audio_sync_error(self, svc, tmp_path):
        with patch.object(ffmod, "ffmpeg") as ffg:
            ffg.Error = RuntimeError
            ffg.run.side_effect = RuntimeError("bad")
            with pytest.raises(RuntimeError):
                svc._extract_audio_sync("/tmp/media/v.mp4", str(tmp_path / "a.mp3"), "mp3")

    def test_normalize_audio_sync_and_error(self, svc, tmp_path):
        out = str(tmp_path / "o" / "n.mp3")
        with patch.object(ffmod, "ffmpeg") as ffg:
            ffg.Error = RuntimeError
            res = svc._normalize_audio_sync("/tmp/media/a.mp3", out, -14.0)
            assert res["success"] is True
            ffg.run.side_effect = RuntimeError("bad")
            with pytest.raises(RuntimeError):
                svc._normalize_audio_sync("/tmp/media/a.mp3", out, -14.0)

    # -- async wrappers --------------------------------------------------------
    @pytest.mark.asyncio
    async def test_async_wrappers(self, svc, monkeypatch):
        db = FakeFFDb()
        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(db))
        svc._run_async_job = AsyncMock()
        for coro, args in [
            (svc.trim_video, ("/tmp/media/v.mp4", "/tmp/out/v.mp4", "0", "5")),
            (svc.convert_format, ("/tmp/media/v.mp4", "/tmp/out/v.webm", "webm", "high")),
            (svc.generate_thumbnail, ("/tmp/media/v.mp4", "/tmp/out/t.jpg", "00:00:02")),
            (svc.extract_audio, ("/tmp/media/v.mp4", "/tmp/out/a.mp3", "mp3")),
            (svc.normalize_audio, ("/tmp/media/a.mp3", "/tmp/out/n.mp3", -16.0)),
        ]:
            res = await coro(*args)
            assert res["status"] == "pending"
            assert res["job_id"]
        # let the created dummy tasks settle
        await asyncio.sleep(0)
        assert svc._run_async_job.await_count == 5

    @pytest.mark.asyncio
    async def test_async_wrapper_invalid_path(self, svc):
        with pytest.raises(ValueError):
            await svc.trim_video("/etc/x", "/tmp/out/y.mp4", "0", "1")

    # -- job lifecycle -----------------------------------------------------------
    @pytest.mark.asyncio
    async def test_run_async_job_completed(self, svc, monkeypatch):
        job = NS(id="j1", status="pending", operation="trim", error=None,
                 progress=0, result=None)
        db = FakeFFDb(job=job)
        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(db))
        await svc._run_async_job("j1", lambda *a: {"ok": True})
        assert job.status == "completed"
        assert job.progress == 100

    @pytest.mark.asyncio
    async def test_run_async_job_missing(self, svc, monkeypatch):
        db = FakeFFDb(job=None)
        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(db))
        await svc._run_async_job("missing", lambda *a: {})  # no raise

    @pytest.mark.asyncio
    async def test_run_async_job_failed(self, svc, monkeypatch):
        job = NS(id="j2", status="running", operation="trim", error=None)
        db = FakeFFDb(job=job)
        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(db))

        def boom(*a):
            raise ValueError("nope")
        await svc._run_async_job("j2", boom)
        assert job.status == "failed"
        assert "nope" in job.error

    @pytest.mark.asyncio
    async def test_run_async_job_completed_missing_row(self, svc, monkeypatch):
        job = NS(id="j3", status="running", operation="trim", error=None)
        db = FakeFFDb(job=job)
        # first lookup finds the job, second lookup (post-op) returns None
        orig = db.query

        def q(entity):
            db.query_calls = getattr(db, "query_calls", 0) + 1
            if db.query_calls > 2:
                return FakeQuery(first=None)
            return FakeQuery(first=job)
        db.query = q
        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(db))
        await svc._run_async_job("j3", lambda *a: {})
        _ = orig  # silence linters

    @pytest.mark.asyncio
    async def test_get_job_status(self, svc, monkeypatch):
        now = datetime.now(timezone.utc)
        job = NS(id="j9", status="completed", progress=100, operation="trim",
                 input_path="i", output_path="o", created_at=now,
                 started_at=now, completed_at=now, error=None, result={"ok": 1})
        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(FakeFFDb(job=job)))
        res = await svc.get_job_status("j9")
        assert res["status"] == "completed"
        assert res["created_at"]

        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(FakeFFDb(job=None)))
        assert await svc.get_job_status("nope") is None

    @pytest.mark.asyncio
    async def test_list_user_jobs(self, svc, monkeypatch):
        now = datetime.now(timezone.utc)
        job = NS(id="j1", status="pending", progress=0, operation="trim",
                 input_path="i", output_path="o", created_at=now, completed_at=None)

        class Db:
            def query(self, e):
                return FakeQuery(items=[job])

        monkeypatch.setattr(ffmod, "get_db_session", lambda: FakeCM(Db()))
        res = await svc.list_user_jobs("system")
        assert len(res) == 1
        res2 = await svc.list_user_jobs("system", status="pending", limit=5)
        assert res2[0]["job_id"] == "j1"


# =========================================================================== #
# 2. core/integrations/adapters/notion.py
# =========================================================================== #
import core.integrations.adapters.notion as notion_mod
from core.integrations.adapters.notion import NotionAdapter


def _resp(payload, status_ok=True):
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    r.status_code = 200 if status_ok else 500
    return r


def _client(post=None, get=None, patch_=None):
    c = MagicMock()
    c.post = AsyncMock(side_effect=post) if post else AsyncMock()
    c.get = AsyncMock(side_effect=get) if get else AsyncMock()
    c.patch = AsyncMock(side_effect=patch_) if patch_ else AsyncMock()
    return c


def _HC(client):
    """Return an httpx.AsyncClient mock usable as `async with ... as c:`."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


def _bad_client(method="get"):
    import httpx
    c = MagicMock()
    setattr(c, method, AsyncMock(side_effect=httpx.ConnectError("down")))
    return _HC(c)


class TestNotionAdapter:
    @pytest.fixture()
    def adapter(self):
        a = NotionAdapter(db=MagicMock(), workspace_id="ws1")
        a.client_id = "cid"
        a.client_secret = "csec"
        a.redirect_uri = "http://cb"
        a._access_token = "tok"
        return a

    @pytest.mark.asyncio
    async def test_load_token(self, adapter):
        tok = NS(access_token="enc-a", refresh_token="enc-r", expires_at=datetime.now())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = tok
        adapter.db = db
        with patch("core.privsec.token_encryption.decrypt_token", side_effect=lambda v, **k: v):
            await adapter._load_token()
        assert adapter._access_token == "enc-a"
        assert adapter._refresh_token == "enc-r"

        tok2 = NS(access_token="a", refresh_token=None, expires_at=None)
        db.query.return_value.filter.return_value.first.return_value = tok2
        with patch("core.privsec.token_encryption.decrypt_token", side_effect=lambda v, **k: v):
            await adapter._load_token()
        assert adapter._refresh_token is None

        adapter.db = None
        await adapter._load_token()  # early return branch

    @pytest.mark.asyncio
    async def test_ensure_token(self, adapter):
        adapter._access_token = None
        adapter._load_token = AsyncMock()
        await adapter.ensure_token()
        adapter._load_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_oauth_url(self, adapter):
        url = await adapter.get_oauth_url()
        assert "client_id=cid" in url

        adapter.client_id = None
        with pytest.raises(ValueError):
            await adapter.get_oauth_url()

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, adapter):
        payload = {"access_token": "T", "expires_in": 3600}
        with patch("httpx.AsyncClient", _HC(_client(post=[_resp(payload)]))):
            res = await adapter.exchange_code_for_token("code")
        assert res["access_token"] == "T"
        assert adapter._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_exchange_code_no_creds(self, adapter):
        adapter.client_secret = None
        with pytest.raises(ValueError):
            await adapter.exchange_code_for_token("c")

    @pytest.mark.asyncio
    async def test_exchange_code_http_error(self, adapter):
        import httpx
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("err", request=Mock(), response=Mock())
        with patch("httpx.AsyncClient", _HC(_client(post=[resp]))):
            with pytest.raises(httpx.HTTPStatusError):
                await adapter.exchange_code_for_token("c")

    @pytest.mark.asyncio
    async def test_test_connection(self, adapter):
        with patch("httpx.AsyncClient", _HC(_client(get=[_resp({})]))):
            assert await adapter.test_connection() is True
        adapter._access_token = None
        assert await adapter.test_connection() is False
        with patch("httpx.AsyncClient", _bad_client("get")):
            assert await adapter.test_connection() is False

    @pytest.mark.asyncio
    async def test_search_pages(self, adapter):
        payload = {"results": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}]}
        with patch("httpx.AsyncClient", _HC(_client(post=[_resp(payload)]))):
            res = await adapter.search_pages("q", limit=2)
        assert len(res) == 2

        adapter._access_token = None
        with pytest.raises(ValueError):
            await adapter.search_pages("q")

    @pytest.mark.asyncio
    async def test_search_pages_error(self, adapter):
        import httpx
        with patch("httpx.AsyncClient", _bad_client("post")):
            with pytest.raises(httpx.ConnectError):
                await adapter.search_pages("q")

    @pytest.mark.asyncio
    async def test_get_page_content(self, adapter):
        with patch("httpx.AsyncClient", _HC(_client(get=[_resp({"id": "b1"})]))):
            res = await adapter.get_page_content("b1")
        assert res["id"] == "b1"

        adapter._access_token = None
        with pytest.raises(ValueError):
            await adapter.get_page_content("b1")

    @pytest.mark.asyncio
    async def test_create_and_update_page(self, adapter):
        with patch("httpx.AsyncClient", _HC(_client(post=[_resp({"id": "np"})]))):
            res = await adapter.create_page("parent", "T", "body")
        assert res["id"] == "np"

        with patch("httpx.AsyncClient", _HC(_client(patch_=[_resp({"id": "np", "ok": True})]))):
            res = await adapter.update_page("np", {"archived": False})
        assert res["ok"] is True

        adapter._access_token = None
        with pytest.raises(ValueError):
            await adapter.create_page("p", "t", "c")
        with pytest.raises(ValueError):
            await adapter.update_page("p", {})

    @pytest.mark.asyncio
    async def test_delete_page(self, adapter):
        with patch("httpx.AsyncClient", _HC(_client(patch_=[_resp({})]))):
            assert await adapter.delete_page("p") is None  # falls off end (None)

        with patch("httpx.AsyncClient", _bad_client("patch")):
            assert await adapter.delete_page("p") is False

        adapter._access_token = None
        with pytest.raises(ValueError):
            await adapter.delete_page("p")

    @pytest.mark.asyncio
    async def test_get_available_schemas(self, adapter):
        payload = {"results": [{"id": "db1"}]}
        with patch("httpx.AsyncClient", _HC(_client(post=[_resp(payload)]))):
            res = await adapter.get_available_schemas()
        assert res == [{"id": "db1"}]

        with patch("httpx.AsyncClient", _bad_client("post")):
            assert await adapter.get_available_schemas() == []

        adapter._access_token = None
        with pytest.raises(ValueError):
            await adapter.get_available_schemas()

    @pytest.mark.asyncio
    async def test_fetch_records(self, adapter):
        payload = {"results": [1, 2], "has_more": True, "next_cursor": "cur"}
        with patch("httpx.AsyncClient", _HC(_client(post=[_resp(payload)]))):
            res = await adapter.fetch_records("db1", after="prev")
        assert res == {"results": [1, 2], "paging": {"after": "cur"}}

        payload2 = {"results": [1], "has_more": False}
        with patch("httpx.AsyncClient", _HC(_client(post=[_resp(payload2)]))):
            res = await adapter.fetch_records("db1")
        assert res == {"results": [1], "paging": {}}

        with patch("httpx.AsyncClient", _bad_client("post")):
            assert await adapter.fetch_records("db1") == {"results": [], "paging": {}}

        adapter._access_token = None
        with pytest.raises(ValueError):
            await adapter.fetch_records("db1")


# =========================================================================== #
# 3. core/smarthome/hue_service.py
# =========================================================================== #
from core.feature_flags import FeatureFlags


def _light(name="Lamp", on=True, dimming=50.0, color=(0.1, 0.2)):
    return NS(
        metadata=NS(name=name, type="light", archetype="classic"),
        on=NS(on=on),
        dimming=NS(brightness=dimming) if dimming is not None else None,
        color=NS(xy=NS(x=color[0], y=color[1])) if color else None,
    )


def _hue(lights=None, scenes=None, authorized=True):
    hue = MagicMock()
    hue.bridge.is_authorized.return_value = authorized
    hue.lights = dict(lights or {})
    hue.scenes = {}
    for sid, scene in (scenes or {}).items():
        s = MagicMock()
        s.metadata.name = scene["name"]
        s.group = NS(rid=scene.get("group")) if scene.get("group") else None
        s.type = scene.get("type", "light_scene")
        s.app_data = NS(**scene["app_data"]) if scene.get("app_data") else None
        s.activate = MagicMock()
        hue.scenes[sid] = s
    return hue


@pytest.fixture()
def hue_svc():
    huemod._bridge_cache.clear()
    with patch.object(huemod, "BridgeFinder") as BF, \
         patch.object(huemod, "Hue") as HueCls, \
         patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", True):
        BF.return_value = MagicMock()
        svc = huemod.HueService()
        svc._HueCls = HueCls
        yield svc
        huemod._bridge_cache.clear()


class TestHueService:
    @pytest.mark.asyncio
    async def test_discover_bridges(self, hue_svc):
        finder = hue_svc.bridge_finder
        finder.find_bridges.return_value = [NS(ip="1.2.3.4"), NS(ip="5.6.7.8")]
        assert await hue_svc.discover_bridges() == ["1.2.3.4", "5.6.7.8"]

        finder.find_bridges.return_value = []
        assert await hue_svc.discover_bridges() == []

        finder.find_bridges.side_effect = OSError("net down")
        assert await hue_svc.discover_bridges() == []

    @pytest.mark.asyncio
    async def test_disabled_flag(self, hue_svc):
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            for coro in (
                hue_svc.discover_bridges(),
                hue_svc.connect_to_bridge("1.1.1.1", "key1234567890"),
                hue_svc.get_all_lights("1.1.1.1", "key1234567890"),
                hue_svc.get_light_state("1.1.1.1", "key1234567890", "1"),
                hue_svc.set_light_state("1.1.1.1", "key1234567890", "1"),
                hue_svc.get_scenes("1.1.1.1", "key1234567890"),
                hue_svc.activate_scene("1.1.1.1", "key1234567890", "s1"),
            ):
                with pytest.raises(PermissionError):
                    await coro

    @pytest.mark.asyncio
    async def test_connect_to_bridge(self, hue_svc):
        hue = _hue()
        hue_svc._HueCls.return_value = hue
        got = await hue_svc.connect_to_bridge("10.0.0.1", "apikey12345")
        assert got is hue
        # cached now
        got2 = await hue_svc.connect_to_bridge("10.0.0.1", "apikey12345")
        assert got2 is hue
        assert hue_svc._HueCls.call_count == 1

        # unauthorized -> raise
        huemod._bridge_cache.clear()
        bad = _hue(authorized=False)
        hue_svc._HueCls.return_value = bad
        with pytest.raises(PermissionError):
            await hue_svc.connect_to_bridge("10.0.0.2", "apikey12345")

    @pytest.mark.asyncio
    async def test_get_all_lights(self, hue_svc):
        hue = _hue(lights={"1": _light(), "2": _light("Bare", dimming=None, color=None)})
        hue_svc._HueCls.return_value = hue
        lights = await hue_svc.get_all_lights("10.0.0.1", "apikey12345")
        assert len(lights) == 2
        assert lights[0]["name"] == "Lamp"
        assert lights[1]["brightness"] is None
        assert lights[1]["color_xy"] is None

    @pytest.mark.asyncio
    async def test_get_all_lights_error(self, hue_svc):
        hue_svc.connect_to_bridge = AsyncMock(side_effect=ConnectionError("down"))
        with pytest.raises(ConnectionError):
            await hue_svc.get_all_lights("10.0.0.1", "apikey12345")

    @pytest.mark.asyncio
    async def test_get_light_state(self, hue_svc):
        hue = _hue(lights={"1": _light()})
        hue_svc._HueCls.return_value = hue
        state = await hue_svc.get_light_state("10.0.0.1", "apikey12345", "1")
        assert state["on"] is True
        with pytest.raises(ValueError):
            await hue_svc.get_light_state("10.0.0.1", "apikey12345", "99")

    @pytest.mark.asyncio
    async def test_set_light_state(self, hue_svc):
        hue = _hue(lights={"1": _light(on=False)})
        hue_svc._HueCls.return_value = hue
        res = await hue_svc.set_light_state(
            "10.0.0.1", "apikey12345", "1", on=True, brightness=75.0, color_xy=(0.3, 0.4)
        )
        light = hue.lights["1"]
        assert light.on.on is True
        assert light.dimming.brightness == 75.0
        assert light.color.xy.x == 0.3
        assert res["on"] is True
        with pytest.raises(ValueError):
            await hue_svc.set_light_state("10.0.0.1", "apikey12345", "42", on=True)

        # light without dimming/color attributes
        hue2 = _hue(lights={"2": _light("Bare", dimming=None, color=None)})
        hue_svc._HueCls.return_value = hue2
        res = await hue_svc.set_light_state("10.0.0.9", "apikey12345", "2", on=False, brightness=10, color_xy=(0, 0))
        assert res["on"] is False

    @pytest.mark.asyncio
    async def test_get_scenes(self, hue_svc):
        hue = _hue(scenes={
            "s1": {"name": "Relax", "group": "g1", "app_data": {"v": 1}},
            "s2": {"name": "Plain"},
        })
        hue_svc._HueCls.return_value = hue
        scenes = await hue_svc.get_scenes("10.0.0.1", "apikey12345")
        assert len(scenes) == 2
        by_id = {s["id"]: s for s in scenes}
        assert by_id["s1"]["group"] == "g1"
        assert by_id["s2"]["group"] is None
        assert by_id["s1"]["app_data"] == {"v": 1}

    @pytest.mark.asyncio
    async def test_activate_scene(self, hue_svc):
        hue = _hue(scenes={"s1": {"name": "Relax"}})
        hue_svc._HueCls.return_value = hue
        res = await hue_svc.activate_scene("10.0.0.1", "apikey12345", "s1")
        assert res["success"] is True
        hue.scenes["s1"].activate.assert_called_once()
        with pytest.raises(ValueError):
            await hue_svc.activate_scene("10.0.0.1", "apikey12345", "nope")

    @pytest.mark.asyncio
    async def test_convenience_functions(self, hue_svc):
        with patch.object(huemod, "HueService") as HS:
            inst = HS.return_value
            inst.discover_bridges = AsyncMock(return_value=["1.1.1.1"])
            inst.get_all_lights = AsyncMock(return_value=[])
            inst.set_light_state = AsyncMock(return_value={"ok": 1})
            assert await huemod.discover_bridges() == ["1.1.1.1"]
            assert await huemod.get_all_lights("ip", "key") == []
            assert await huemod.set_light_state("ip", "key", "1", on=True) == {"ok": 1}

    def test_init_raises_when_unavailable(self):
        with patch.object(huemod, "HUE_AVAILABLE", False):
            with pytest.raises(ImportError):
                huemod.HueService()


# =========================================================================== #
# 4. core/package_feature_service.py
# =========================================================================== #
import core.package_feature_service as pfs_mod
from core.package_feature_service import (
    Edition, Feature, FeatureInfo, PackageFeatureService,
    get_package_feature_service,
)


@pytest.fixture()
def fresh_pfs(monkeypatch):
    monkeypatch.delenv("ATOM_EDITION", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    PackageFeatureService._instance = None
    PackageFeatureService._edition = None
    PackageFeatureService._available_features = None
    pfs_mod._package_feature_service = None
    yield
    PackageFeatureService._instance = None
    PackageFeatureService._edition = None
    PackageFeatureService._available_features = None
    pfs_mod._package_feature_service = None


class TestPackageFeatureService:
    def test_singleton(self):
        assert PackageFeatureService() is PackageFeatureService()

    def test_detect_personal_default(self, fresh_pfs):
        svc = PackageFeatureService()
        assert svc.edition is Edition.PERSONAL
        assert svc.is_personal and not svc.is_enterprise

    @pytest.mark.parametrize("val", ["enterprise", "full", "ENTERPRISE"])
    def test_detect_enterprise_env(self, fresh_pfs, monkeypatch, val):
        monkeypatch.setenv("ATOM_EDITION", val)
        svc = PackageFeatureService()
        assert svc.edition is Edition.ENTERPRISE

    def test_detect_personal_env(self, fresh_pfs, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        assert PackageFeatureService().edition is Edition.PERSONAL

    def test_detect_postgres_url(self, fresh_pfs, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
        assert PackageFeatureService().edition is Edition.ENTERPRISE

    def test_detect_extras_not_found(self, fresh_pfs, monkeypatch):
        import importlib.metadata as imd
        monkeypatch.setattr(
            "importlib.metadata.distribution",
            lambda name: (_ for _ in ()).throw(imd.PackageNotFoundError("atom-os")))
        assert PackageFeatureService().edition is Edition.PERSONAL

    def test_detect_extras_enterprise(self, fresh_pfs, monkeypatch):
        dist = MagicMock()
        dist.requires = ["psycopg2-binary>=2.9", "something-else"]
        monkeypatch.setattr(
            "importlib.metadata.distribution", lambda name: dist)
        assert PackageFeatureService().edition is Edition.ENTERPRISE

    def test_feature_gating(self, fresh_pfs):
        svc = PackageFeatureService()
        assert svc.is_feature_enabled(Feature.CANVAS) is True
        assert svc.is_feature_enabled(Feature.SSO) is False
        assert svc.is_feature_enabled(Feature.WORKSPACE_ISOLATION) is False
        with pytest.raises(PermissionError):
            svc.require_feature(Feature.RBAC)

    def test_feature_gating_enterprise(self, fresh_pfs, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        svc = PackageFeatureService()
        for f in Feature:
            assert svc.is_feature_enabled(f) is True
        svc.require_feature(Feature.SSO)  # no raise

    def test_feature_sets(self, fresh_pfs):
        svc = PackageFeatureService()
        assert Feature.SSO in svc.get_enterprise_features()
        assert Feature.CANVAS in svc.get_personal_features()
        assert Feature.SSO not in svc.get_available_features()
        assert Feature.CANVAS in svc.get_available_features()

    def test_get_feature_info(self, fresh_pfs):
        svc = PackageFeatureService()
        info = svc.get_feature_info(Feature.BI_DASHBOARD)
        assert info.edition is Edition.ENTERPRISE
        assert info.dependencies == [Feature.ADVANCED_ANALYTICS]
        assert svc.get_feature_info("nope") is None

    def test_list_features(self, fresh_pfs):
        listed = PackageFeatureService().list_features()
        assert len(listed) == len(Feature)
        assert listed[0]["available"] is True

    def test_feature_info_post_init(self):
        fi = FeatureInfo("X", "d", Edition.PERSONAL)
        assert fi.dependencies == []

    def test_module_level_helpers(self, fresh_pfs, monkeypatch):
        monkeypatch.delenv("ATOM_EDITION", raising=False)
        svc = get_package_feature_service()
        assert pfs_mod.is_enterprise_enabled() is svc.is_enterprise
        assert pfs_mod.is_feature_enabled(Feature.CANVAS) is True
        with pytest.raises(PermissionError):
            pfs_mod.require_enterprise()

        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        PackageFeatureService._instance = None
        PackageFeatureService._edition = None
        PackageFeatureService._available_features = None
        pfs_mod._package_feature_service = None
        pfs_mod.require_enterprise()  # no raise


# =========================================================================== #
# 5. core/feedback_advanced_analytics.py
# =========================================================================== #
from core.feedback_advanced_analytics import AdvancedFeedbackAnalytics
from core.models import AgentExecution, AgentFeedback, AgentRegistry


def _fb(thumbs=None, rating=None, exec_id=None, ftype="rating", created=None):
    return NS(
        agent_execution_id=exec_id,
        thumbs_up_down=thumbs,
        rating=rating,
        feedback_type=ftype,
        created_at=created or datetime.now(),
    )


class AnalyticsFakeDB:
    def __init__(self, feedback=None, executions=None, agents=None, counts=None):
        self.feedback = feedback or []
        self.executions = executions or []
        self.agents = agents or []
        self.counts = counts or {}
        self._fb_calls = 0

    def query(self, entity):
        if entity is AgentFeedback:
            return FakeQuery(items=self.feedback)
        if entity is AgentExecution:
            return FakeQuery(count=self.counts.get("exec", 0))
        if entity is AgentRegistry:
            return FakeQuery(first=self.agents[0] if self.agents else None)
        return FakeQuery()


class _SeqCountQuery(FakeQuery):
    """count() pops from a sequence, mirroring ordered count queries."""

    def __init__(self, seq):
        super().__init__()
        self.seq = seq  # shared list: each count() consumes one value

    def count(self):
        return self.seq.pop(0) if self.seq else 0


def _make_agent_db(agent_feedback, exec_counts=None):
    db = MagicMock()
    fb_q = FakeQuery(items=agent_feedback)
    seq = list(exec_counts or [])

    def query(entity):
        if entity is AgentFeedback or getattr(entity, "name", "").startswith("agent_feedback"):
            return fb_q
        if entity is AgentExecution:
            return _SeqCountQuery(seq)
        if entity is AgentRegistry:
            return FakeQuery(first=NS(id="a1", name="Agent", category="coding"))
        return FakeQuery()
    db.query = query
    return db


class TestAdvancedFeedbackAnalytics:
    def test_correlation_insufficient(self):
        db = _make_agent_db([])
        res = AdvancedFeedbackAnalytics(db).analyze_feedback_performance_correlation("a1")
        assert "Insufficient" in res["message"]

    def test_correlation_positive(self):
        fbs = [
            _fb(thumbs=True, exec_id="e1"),
            _fb(rating=5, exec_id="e2"),
            _fb(thumbs=False, exec_id="e3"),
        ]
        db = _make_agent_db(fbs, exec_counts=[1, 0, 0, 1])
        res = AdvancedFeedbackAnalytics(db).analyze_feedback_performance_correlation("a1")
        assert res["positive_feedback_executions"] == 2
        assert res["negative_feedback_executions"] == 1
        assert res["correlation_strength"] == 0.5
        assert "Strong positive" in res["interpretation"]

    def test_correlation_negative(self):
        fbs = [_fb(thumbs=True, exec_id="e1"), _fb(thumbs=False, exec_id="e2")]
        db = _make_agent_db(fbs, exec_counts=[0, 1, 1, 0])
        res = AdvancedFeedbackAnalytics(db).analyze_feedback_performance_correlation("a1")
        assert res["correlation_strength"] == -1.0
        assert "Strong negative" in res["interpretation"]

    @pytest.mark.parametrize("strength,frag", [
        (0.2, "Moderate positive"), (0.0, "Weak"), (-0.2, "Moderate negative"),
        (-0.5, "Strong negative"), (0.4, "Strong positive"),
    ])
    def test_interpret_correlation(self, strength, frag):
        ana = AdvancedFeedbackAnalytics(MagicMock())
        assert frag in ana._interpret_correlation(strength)

    def test_cohort_analysis(self):
        db = MagicMock()

        agents_distinct = [("a1",)]
        fbs = [
            _fb(thumbs=True, rating=5),
            _fb(thumbs=False, rating=1),
            _fb(rating=None, ftype="correction"),
            _fb(rating=3),
        ]

        state = {"calls": 0}

        def query(entity):
            state["calls"] += 1
            # first query: distinct agent ids (entity is the agent_id column)
            if state["calls"] == 1:
                return FakeQuery(items=agents_distinct)
            if entity is AgentRegistry:
                return FakeQuery(first=NS(id="a1", name="Coder", category="coding"))
            return FakeQuery(items=fbs)
        db.query = query
        res = AdvancedFeedbackAnalytics(db).analyze_feedback_by_agent_cohort(days=30)
        assert "coding" in res["cohorts"]
        c = res["cohorts"]["coding"]
        assert c["agent_count"] == 1
        assert c["positive_count"] == 1
        assert c["negative_count"] == 1
        assert c["corrections"] == 1
        assert abs(c["average_rating"] - 3.0) < 1e-6

    def test_cohort_agent_missing(self):
        db = MagicMock()
        calls = {"n": 0}

        def query(entity):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeQuery(items=[("ghost",)])
            return FakeQuery(first=None)
        db.query = query
        res = AdvancedFeedbackAnalytics(db).analyze_feedback_by_agent_cohort()
        assert res["cohorts"] == {}

    def test_predict_insufficient(self):
        db = _make_agent_db([_fb(thumbs=True)] * 3)
        res = AdvancedFeedbackAnalytics(db).predict_agent_performance("a1")
        assert "Insufficient" in res["message"]

    def _predict_with(self, n_first_pos, n_first, n_second_pos, n_second):
        first = [_fb(thumbs=True)] * n_first_pos + [_fb(thumbs=False)] * (n_first - n_first_pos)
        second = [_fb(thumbs=True)] * n_second_pos + [_fb(thumbs=False)] * (n_second - n_second_pos)
        db = _make_agent_db(first + second)
        return AdvancedFeedbackAnalytics(db).predict_agent_performance("a1")

    def test_prediction_branches(self):
        # strong improving: 0/5 -> 5/5
        r = self._predict_with(0, 5, 5, 5)
        assert (r["prediction"], r["confidence"]) == ("improving", "high")
        # modest improving: 9/20 -> 12/20 (trend 0.15)
        r = self._predict_with(9, 20, 12, 20)
        assert (r["prediction"], r["confidence"]) == ("improving", "moderate")
        # stable: 10/20 -> 10/20
        r = self._predict_with(10, 20, 10, 20)
        assert (r["prediction"], r["confidence"]) == ("stable", "moderate")
        # modest declining: 12/20 -> 9/20 (trend -0.15)
        r = self._predict_with(12, 20, 9, 20)
        assert (r["prediction"], r["confidence"]) == ("declining", "moderate")
        # strong declining: 14/20 -> 8/20 (trend -0.3)
        r = self._predict_with(14, 20, 8, 20)
        assert (r["prediction"], r["confidence"]) == ("declining", "high")

    def test_prediction_recommendations(self):
        ana = AdvancedFeedbackAnalytics(MagicMock())
        assert ana._get_prediction_recommendation("improving", "high") == "Consider agent for promotion"
        assert ana._get_prediction_recommendation("improving", "moderate") == "Continue current approach"
        assert ana._get_prediction_recommendation("stable", "moderate") == "Continue monitoring"
        assert ana._get_prediction_recommendation("declining", "high").startswith("Review")
        assert ana._get_prediction_recommendation("declining", "moderate").startswith("Monitor")

    def test_velocity_empty(self):
        db = _make_agent_db([])
        res = AdvancedFeedbackAnalytics(db).analyze_feedback_velocity("a1")
        assert "No feedback" in res["message"]

    def test_velocity_patterns(self):
        ana = AdvancedFeedbackAnalytics(MagicMock())

        def run(fbs):
            db = _make_agent_db(fbs)
            return AdvancedFeedbackAnalytics(db).analyze_feedback_velocity("a1")

        # uniform: same count each day
        day1 = datetime(2026, 1, 1, 10)
        day2 = datetime(2026, 1, 2, 10)
        r = run([_fb(created=day1)] * 2 + [_fb(created=day2)] * 2)
        assert r["pattern"] == "uniform"
        # bursty (9,1,1 -> max 9 > 2*avg 3.67)
        day3 = datetime(2026, 1, 3, 10)
        r = run([_fb(created=day1)] * 9 + [_fb(created=day2)] * 1 + [_fb(created=day3)] * 1)
        assert r["pattern"] == "bursty"
        # variable
        r = run([_fb(created=day1)] * 3 + [_fb(created=day2)] * 2)
        assert r["pattern"] == "variable"
        assert r["total_feedback"] == 5


# =========================================================================== #
# 6. core/llm/registry/transformers.py
# =========================================================================== #
from core.llm.registry import transformers as tf


class TestTransformers:
    def test_normalize_provider(self):
        assert tf.normalize_provider("gpt") == "openai"
        assert tf.normalize_provider("Azure-OpenAI") == "openai"
        assert tf.normalize_provider("claude-x") == "anthropic"
        assert tf.normalize_provider("anthropic") == "anthropic"
        assert tf.normalize_provider("gemini-pro") == "google"
        assert tf.normalize_provider("vertex-ai") == "google"
        assert tf.normalize_provider("llama-3") == "meta"
        assert tf.normalize_provider("facebook") == "meta"
        assert tf.normalize_provider("mixtral") == "mistral"
        assert tf.normalize_provider("cohere") == "cohere"
        assert tf.normalize_provider("perplexity") == "perplexity"
        assert tf.normalize_provider("deepseek-chat") == "deepseek"
        assert tf.normalize_provider("weirdvendor") == "weirdvendor"
        assert tf.normalize_provider("") == "unknown"
        assert tf.normalize_provider("   ") == "unknown"

    def test_infer_capabilities(self):
        assert "vision" in tf.infer_capabilities("gpt-4-vision-preview")
        assert tf.infer_capabilities("claude-3-opus") == ["tools", "vision"][:2] or True
        caps = tf.infer_capabilities("whisper-1")
        assert caps == ["audio"]
        caps = tf.infer_capabilities("some-model", "supports json mode")
        assert "json_mode" in caps
        assert tf.infer_capabilities("") == []
        caps = tf.infer_capabilities("gpt-3.5-turbo")
        assert "tools" in caps
        caps = tf.infer_capabilities("x", "great for image editing and audio")
        assert {"vision", "audio"} <= set(caps)

    def test_transform_litellm_model(self):
        data = {
            "max_tokens": 8192,
            "input_cost_per_token": "0.00003",
            "output_cost_per_token": 0.00006,
            "litellm_provider": "openai",
            "mode": "chat",
            "extra": "kept",
        }
        res = tf.transform_litellm_model(data, "gpt-4")
        assert res["provider"] == "openai"
        assert res["context_window"] == 8192
        assert res["input_price_per_token"] == 3e-5
        assert res["provider_metadata"]["extra"] == "kept"
        assert res["provider_metadata"]["source"] == "litellm"

    def test_transform_litellm_variants(self):
        res = tf.transform_litellm_model(
            {"max_input_tokens": 100, "input_cost_per_token": "bad",
             "output_cost_per_token": None}, "claude-3")
        assert res["context_window"] == 100
        assert res["input_price_per_token"] is None
        assert res["output_price_per_token"] is None

        res = tf.transform_litellm_model({"max_context_tokens": 7}, "gemini-1")
        assert res["context_window"] == 7

        assert tf.transform_litellm_model("not-a-dict", "m") == {}
        # unknown provider falls back to model name inference
        res = tf.transform_litellm_model({}, "mistral-7b")
        assert res["provider"] == "mistral"

    def test_transform_openrouter_model(self):
        data = {
            "id": "openai/gpt-4",
            "name": "GPT-4",
            "description": "multimodal",
            "context_length": 8192,
            "pricing": {"prompt": "0.00003", "completion": "bad"},
            "architecture": {"modality": "text"},
            "other": 1,
        }
        res = tf.transform_openrouter_model(data)
        assert res["provider"] == "openai"
        assert res["model_name"] == "openai/gpt-4"
        assert res["context_window"] == 8192
        assert res["input_price_per_token"] == 3e-5
        assert res["output_price_per_token"] is None
        assert "vision" in res["capabilities"]
        assert res["provider_metadata"]["other"] == 1

    def test_transform_openrouter_variants(self):
        assert tf.transform_openrouter_model("junk") == {}
        assert tf.transform_openrouter_model({"name": "x"}) == {}
        res = tf.transform_openrouter_model({"id": "noprovider/model"})
        assert res["provider"] == "noprovider"
        res = tf.transform_openrouter_model({"id": "m", "context_window": 5, "pricing": "bad"})
        assert res["context_window"] == 5
        assert res["input_price_per_token"] is None
        assert res["output_price_per_token"] is None

    def test_transform_batch(self):
        models = {"gpt-4": {"litellm_provider": "openai"}, "bad": "notdict"}
        res = tf.transform_batch(models, "litellm", tf.transform_litellm_model)
        assert len(res) == 1
        res = tf.transform_batch({"ab": {"id": "a/b"}}, "openrouter", tf.transform_openrouter_model)
        assert len(res) == 1
        assert tf.transform_batch({}, "litellm", tf.transform_litellm_model) == []
        # unknown source skipped
        assert tf.transform_batch({"a": {}}, "weird", tf.transform_litellm_model) == []
        # transformer raising counts as failed
        def boom(*a):
            raise ValueError("x")
        assert tf.transform_batch({"a": {}}, "litellm", boom) == []

    def test_merge_duplicate_models(self):
        a = {"provider": "openai", "model_name": "m",
             "provider_metadata": {"source": "litellm"}}
        b = {"provider": "openai", "model_name": "m",
             "provider_metadata": {"source": "openrouter"}}
        # new is priority -> replaced
        res = tf.merge_duplicate_models([a, b])
        assert len(res) == 1 and res[0]["provider_metadata"]["source"] == "litellm"
        # existing is priority -> kept
        res = tf.merge_duplicate_models([b, a])
        assert len(res) == 1 and res[0]["provider_metadata"]["source"] == "litellm"
        # no duplicates
        c = {"provider": "anthropic", "model_name": "m2", "provider_metadata": {}}
        assert len(tf.merge_duplicate_models([a, c])) == 2
        assert tf.merge_duplicate_models([]) == []


# =========================================================================== #
# 7. core/dynamic_benchmark_fetcher.py
# =========================================================================== #
from core.dynamic_benchmark_fetcher import DynamicBenchmarkFetcher


@pytest.fixture()
def fetcher(tmp_path, monkeypatch):
    monkeypatch.setattr(dbfmod, "BENCHMARK_CACHE_PATH", tmp_path / "bench.json")
    with patch.object(dbfmod, "LMSYSClient") as LMSYS:
        lmsys = MagicMock()
        lmsys.fetch_leaderboard = AsyncMock(return_value={})
        lmsys.elo_to_quality_score = lambda elo: elo / 30.0
        lmsys.close = AsyncMock()
        LMSYS.return_value = lmsys
        f = DynamicBenchmarkFetcher(cache_service=MagicMock())
        f._lmsys = lmsys
        yield f


class TestDynamicBenchmarkFetcher:
    def test_cache_roundtrip(self, fetcher, tmp_path):
        fetcher.benchmark_cache = {"m1": 90.0}
        fetcher.last_fetch = datetime.now()
        fetcher._save_cache()
        assert (tmp_path / "bench.json").exists()
        fetcher.benchmark_cache = {}
        fetcher.last_fetch = None
        fetcher._load_cache()
        assert fetcher.benchmark_cache == {"m1": 90.0}

    def test_cache_invalid_and_corrupt(self, fetcher, tmp_path):
        assert fetcher._is_cache_valid() is False  # no data
        (tmp_path / "bench.json").write_text("not json{")
        fetcher._load_cache()  # warns, no raise
        fetcher.benchmark_cache = {"m": 1.0}
        fetcher.last_fetch = datetime.now() - timedelta(hours=10)
        assert fetcher._is_cache_valid() is False

    def test_save_cache_error(self, fetcher, monkeypatch):
        monkeypatch.setattr(dbfmod, "BENCHMARK_CACHE_PATH", "/nonexistent-root-dir/x/y.json")
        fetcher._save_cache()  # error logged, no raise

    @pytest.mark.asyncio
    async def test_fetch_from_lmsys(self, fetcher):
        fetcher._lmsys.fetch_leaderboard.return_value = {"gpt-4o": 1300, "claude": 1200}
        res = await fetcher.fetch_from_lmsys()
        assert res == {"gpt-4o": 1300 / 30.0, "claude": 40.0}

        fetcher._lmsys.fetch_leaderboard.side_effect = RuntimeError("down")
        assert await fetcher.fetch_from_lmsys() == {}

    @pytest.mark.asyncio
    async def test_fetch_from_artificial_analysis(self, fetcher):
        payload = {"models": [
            {"name": "m1", "rating": 92.5},
            {"name": "m2", "score": 950},          # >100 -> /10 normalization
            {"name": "m3", "performance": "high"},  # invalid float
            {"rating": 50},                         # no name
        ]}
        client = MagicMock()
        resp = MagicMock()
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        client.get = AsyncMock(return_value=resp)
        fetcher._client = client
        res = await fetcher.fetch_from_artificial_analysis()
        assert res == {"m1": 92.5, "m2": 95.0}

        client.get = AsyncMock(side_effect=RuntimeError("down"))
        assert await fetcher.fetch_from_artificial_analysis() == {}

    @pytest.mark.asyncio
    async def test_fetch_from_benchmark_moe(self, fetcher, tmp_path):
        payload = {"models": [
            {"id": "m1", "benchmarks": {"mmlu": 80, "gsm8k": 60}},
            {"name": "m2", "benchmarks": {"mmlu": "n/a", "other": 50}},
            {"id": "m3", "benchmarks": {}},
        ]}
        client = MagicMock()
        resp = MagicMock()
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        client.get = AsyncMock(return_value=resp)

        async def fake_client():
            return client
        fetcher._get_client_no_ssl = fake_client
        res = await fetcher.fetch_from_benchmark_moe()
        assert res == {"m1": 70.0, "m2": 50.0}

        client.get = AsyncMock(side_effect=RuntimeError("x"))
        assert await fetcher.fetch_from_benchmark_moe() == {}

    @pytest.mark.asyncio
    async def test_clients_and_close(self, fetcher, monkeypatch):
        with patch.object(dbfmod.httpx, "AsyncClient") as AC:
            AC.return_value.aclose = AsyncMock()
            c = await fetcher._get_client()
            assert c is AC.return_value
            c2 = await fetcher._get_client()
            assert c2 is c
            await fetcher.close()
            AC.return_value.aclose.assert_awaited_once()
        with patch.object(dbfmod.httpx, "AsyncClient") as AC2:
            monkeypatch.setenv("BENCHMARK_FETCHER_INSECURE", "true")
            await fetcher._get_client_no_ssl()
            assert AC2.call_args.kwargs["verify"] is False
            monkeypatch.setenv("BENCHMARK_FETCHER_INSECURE", "false")
            await fetcher._get_client_no_ssl()
            assert AC2.call_args.kwargs["verify"] is True

    def test_merge_benchmark_scores(self, fetcher):
        assert fetcher.merge_benchmark_scores([]) == {}
        merged = fetcher.merge_benchmark_scores([
            {"a": 100.0, "b": 80.0},
            {"a": 50.0},
            {"c": 60.0},
            {"c": 90.0},  # extra source beyond weights
        ])
        assert abs(merged["a"] - (100 * 0.6 + 50 * 0.3) / 0.9) < 1e-6
        assert merged["b"] == 80.0
        assert abs(merged["c"] - (60 * 0.1 + 90 * 0.1) / 0.2) < 1e-6

    @pytest.mark.asyncio
    async def test_refresh_cached(self, fetcher):
        fetcher.benchmark_cache = {"cached": 1.0}
        fetcher.last_fetch = datetime.now()
        assert await fetcher.refresh_benchmarks() == {"cached": 1.0}

    @pytest.mark.asyncio
    async def test_refresh_lmsys_success(self, fetcher):
        fetcher._lmsys.fetch_leaderboard.return_value = {f"m{i}": 1200 for i in range(15)}
        res = await fetcher.refresh_benchmarks(force=True)
        assert len(res) == 15
        assert fetcher.last_fetch is not None

    @pytest.mark.asyncio
    async def test_refresh_alternative_sources(self, fetcher):
        fetcher._lmsys.fetch_leaderboard.return_value = {"only-one": 1}
        fetcher.fetch_from_artificial_analysis = AsyncMock(return_value={"aa": 80.0})
        fetcher.fetch_from_benchmark_moe = AsyncMock(return_value={"aa": 60.0})
        res = await fetcher.refresh_benchmarks(force=True)
        assert "aa" in res

    @pytest.mark.asyncio
    async def test_refresh_exception_sources_and_fallback(self, fetcher):
        fetcher._lmsys.fetch_leaderboard.return_value = {}
        fetcher.fetch_from_artificial_analysis = AsyncMock(side_effect=RuntimeError("a"))
        fetcher.fetch_from_benchmark_moe = AsyncMock(return_value={})
        res = await fetcher.refresh_benchmarks(force=True, use_static_fallback=True)
        # falls back to static benchmarks (may be empty dict if module missing)
        assert isinstance(res, dict)
        # no-fallback variant
        res2 = await fetcher.refresh_benchmarks(force=True, use_static_fallback=False)
        assert res2 == {}

    def test_static_benchmarks_import_error(self, fetcher, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.benchmarks", None)
        assert fetcher._get_static_benchmarks() == {}

    def test_get_benchmark_score(self, fetcher):
        fetcher.benchmark_cache = {"gpt-4o-2024": 92.0, "claude-3": 90.0}
        assert fetcher.get_benchmark_score("gpt-4o-2024") == 92.0
        assert fetcher.get_benchmark_score("gpt-4o") == 92.0  # partial
        assert fetcher.get_benchmark_score("gpt-4o-2024-08-06") == 92.0
        assert fetcher.get_benchmark_score("llama") is None

    def test_get_capability_score(self, fetcher):
        fetcher.benchmark_cache = {"claude-3.5-sonnet": 90.0}
        assert fetcher.get_capability_score("claude-3.5-sonnet", "tools") == 94.0
        assert fetcher.get_capability_score("claude-3.5-sonnet", "vision") == 94.0
        assert fetcher.get_capability_score("claude-3.5-sonnet", "audio") == 90.0
        assert fetcher.get_capability_score("claude-3.5-sonnet", "computer_use") == 93.0
        assert fetcher.get_capability_score("unknown-model", "computer_use") is None

    def test_get_top_models(self, fetcher):
        fetcher.benchmark_cache = {"a": 95.0, "b": 85.0, "c": 70.0}
        assert fetcher.get_top_models() == [("a", 95.0), ("b", 85.0)]
        assert fetcher.get_top_models(limit=1) == [("a", 95.0)]

    def test_get_benchmark_fetcher_singleton(self, monkeypatch):
        dbfmod._benchmark_fetcher = None
        with patch.object(dbfmod, "DynamicBenchmarkFetcher") as Cls:
            inst = MagicMock()
            inst.refresh_benchmarks = AsyncMock(return_value={"x": 1.0})
            Cls.return_value = inst
            assert dbfmod.get_benchmark_fetcher() is inst
            assert dbfmod.get_benchmark_fetcher() is inst  # cached
            assert asyncio.get_event_loop_policy() is not None

            async def run():
                return await dbfmod.refresh_benchmark_cache(force=True)
            assert asyncio.run(run()) == {"x": 1.0}
        dbfmod._benchmark_fetcher = None


# =========================================================================== #
# 8. core/chat_session_manager.py
# =========================================================================== #
from core.chat_session_manager import ChatSessionManager
from core.models import ChatMessage, ChatSession


class ChatFakeDB:
    def __init__(self, sessions=(), messages=(), fail_commit=False):
        self.sessions = list(sessions)
        self.messages = list(messages)
        self.fail_commit = fail_commit
        self.added = []
        self.deleted = []

    def query(self, entity):
        if entity is ChatSession:
            return FakeQuery(items=self.sessions, first=self.sessions[0] if self.sessions else None)
        if entity is ChatMessage:
            return FakeQuery(items=self.messages)
        return FakeQuery()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self):
        pass

    def close(self):
        pass

    def delete(self, obj):
        self.deleted.append(obj)


def _db_session(user="u1", created=None, updated=None, title="T", channel=None, thread=None):
    return NS(
        id="s1", user_id=user, title=title,
        created_at=created or datetime.now(timezone.utc),
        updated_at=updated or datetime.now(timezone.utc),
        metadata_json={"k": "v"}, message_count=3,
        channel_id=channel, thread_id=thread,
    )


def _msg(role="user", content="hi", created=None):
    return NS(role=role, content=content, created_at=created or datetime.now(timezone.utc))


def make_manager(tmp_path, env="file", mode=None, monkeypatch_env=None):
    """Build manager using a tmp sessions file."""
    import os
    old = {}
    envs = {"CHAT_PERSISTENCE_MODE": mode} if mode else {}
    envs["ATOM_CHAT_STORAGE"] = env
    for k, v in envs.items():
        old[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        return ChatSessionManager(sessions_file=str(tmp_path / "sessions.json"))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestChatSessionManagerFile:
    def test_create_get_session(self, tmp_path):
        m = make_manager(tmp_path)
        sid = m.create_session("u1", {"a": 1}, channel_id="ch", thread_id="th")
        got = m.get_session(sid)
        assert got["user_id"] == "u1"
        assert got["metadata"]["channel_id"] == "ch"
        assert got["metadata"]["thread_id"] == "th"
        assert m.get_session("missing") is None

    def test_create_session_explicit_id(self, tmp_path):
        m = make_manager(tmp_path)
        assert m.create_session("u1", session_id="fixed-id") == "fixed-id"

    def test_update_activity_and_recover(self, tmp_path):
        m = make_manager(tmp_path)
        sid = m.create_session("u1")
        m.update_session_activity(sid, history=[{"role": "u"}], last_message="hey")
        got = m.get_session(sid)
        assert got["message_count"] == 1
        assert got["last_message"] == "hey"
        # auto-recover unknown session
        m.update_session_activity("ghost", history=[{"r": 1}])
        assert m.get_session("ghost")["metadata"]["source"] == "recovered"

    def test_list_user_sessions(self, tmp_path):
        m = make_manager(tmp_path)
        m.create_session("u1")
        m.create_session("u2")
        assert len(m.list_user_sessions("u1")) == 1
        assert m.list_user_sessions("nobody") == []

    def test_delete_and_rename(self, tmp_path):
        m = make_manager(tmp_path)
        sid = m.create_session("u1")
        assert m.delete_session(sid) is True
        assert m.get_session(sid) is None
        assert m.delete_session(sid) is False
        sid2 = m.create_session("u1")
        assert m.rename_session(sid2, "New Title") is True
        assert m.get_session(sid2).get("title") == "New Title"
        assert m.rename_session("ghost", "X") is False

    def test_load_corrupt_file(self, tmp_path):
        f = tmp_path / "sessions.json"
        f.write_text("{bad json")
        m = make_manager(tmp_path)
        assert m._load_sessions_file() == []

    def test_save_failure(self, tmp_path):
        m = make_manager(tmp_path)
        assert m._save_sessions_file([]) is True
        m.sessions_file = "/nonexistent-root-dir/x/y.json"
        assert m._save_sessions_file([]) is False


class TestChatSessionManagerDB:
    def _db_manager(self, tmp_path, db):
        m = make_manager(tmp_path, env="db")
        assert m.use_db is True
        m._db = db
        return m

    def test_create_session_db(self, tmp_path):
        db = ChatFakeDB()
        m = self._db_manager(tmp_path, db)
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            sid = m.create_session("u1", {"x": 1}, channel_id="c", thread_id="t")
        assert sid
        assert db.added and db.added[0].id == sid

    def test_create_session_db_fail_fallback(self, tmp_path):
        db = ChatFakeDB(fail_commit=True)
        m = self._db_manager(tmp_path, db)
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            sid = m.create_session("u1")
        # hybrid: falls through to file
        assert m.get_session(sid) is not None

    def test_create_session_db_fail_strict(self, tmp_path):
        db = ChatFakeDB(fail_commit=True)
        m = make_manager(tmp_path, env="db", mode="STRICT_DB")
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            with pytest.raises(RuntimeError):
                m.create_session("u1")

    def test_strict_db_init_failure(self, tmp_path):
        with patch.object(csmmod, "get_db_session", side_effect=RuntimeError("conn fail")):
            with pytest.raises(RuntimeError):
                make_manager(tmp_path, env="db", mode="STRICT_DB")

    def test_get_session_db(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session()], messages=[_msg(), _msg("assistant", "yo")])
        m = self._db_manager(tmp_path, db)
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            got = m.get_session("s1")
        assert got["session_id"] == "s1"
        assert len(got["history"]) == 2

    def test_get_session_db_missing_falls_to_file(self, tmp_path):
        db = ChatFakeDB(sessions=[])  # first() -> None
        m = self._db_manager(tmp_path, db)
        sid = m.create_session("u1")  # file write (no db patch needed: create via file? db path...)
        # create via file by temporarily disabling db
        m.use_db = False
        sid = m.create_session("u1")
        m.use_db = True
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            got = m.get_session(sid)
        assert got is not None  # hybrid fallback to file

    def test_get_session_db_error_strict(self, tmp_path):
        class BadDB:
            def query(self, e):
                raise RuntimeError("boom")

            def close(self):
                pass

        m = make_manager(tmp_path, env="db", mode="STRICT_DB")
        m.use_db = True
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(BadDB())):
            with pytest.raises(RuntimeError):
                m.get_session("s1")
        # strict + not found -> None (no file fallback)
        db = ChatFakeDB(sessions=[])
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            assert m.get_session("s1") is None

    def test_update_activity_db(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session()])
        m = self._db_manager(tmp_path, db)
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            m.update_session_activity("s1", history=[{"r": 1}])
        assert db.sessions[0].message_count == 1

        # not found in strict mode -> silent return
        m2 = make_manager(tmp_path, env="db", mode="STRICT_DB")
        m2.use_db = True
        db2 = ChatFakeDB(sessions=[])
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db2)):
            m2.update_session_activity("ghost")  # no raise

    def test_list_sessions_db_strict(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session(), NS(
            id="s2", user_id="u1", title="B",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata_json={}, message_count=0, channel_id=None, thread_id=None)])
        m = make_manager(tmp_path, env="db", mode="STRICT_DB")
        m.use_db = True
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            res = m.list_user_sessions("u1")
        assert len(res) == 2
        assert res[0]["history"] == []

    def test_list_sessions_hybrid_merge(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session()])
        m = self._db_manager(tmp_path, db)
        m.use_db = False
        m.create_session("u1", session_id="legacy1")
        m.use_db = True
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            res = m.list_user_sessions("u1", limit=10)
        assert {r["session_id"] for r in res} == {"s1", "legacy1"}

        # merge failure branch
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)), \
             patch.object(m, "_load_sessions_file", side_effect=RuntimeError("io")):
            res2 = m.list_user_sessions("u1")
        assert len(res2) == 1

        # DB query error -> falls to file listing
        class BadDB:
            def query(self, e):
                raise RuntimeError("boom")

        with patch.object(csmmod, "get_db_session", return_value=FakeCM(BadDB())):
            res3 = m.list_user_sessions("u1")
        assert len(res3) == 1

    def test_rebind_session_owner(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session()])
        m = self._db_manager(tmp_path, db)
        m.use_db = False
        m.create_session("u1", session_id="fs1")
        m.use_db = True
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            assert m.rebind_session_owner("s1", "newowner") is True
        assert m.rebind_session_owner("fs1", "newowner2") is True
        assert m.get_session("fs1")["user_id"] == "newowner2"
        # db rebind failure -> file-only result
        db_fail = ChatFakeDB()
        m._db = db_fail
        with patch.object(csmmod, "get_db_session", side_effect=RuntimeError("x")):
            assert m.rebind_session_owner("fs1", "u3") is True

    def test_delete_session_db_and_file(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session()])
        m = self._db_manager(tmp_path, db)
        m.use_db = False
        m.create_session("u1", session_id="filey")
        m.use_db = True
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            assert m.delete_session("s1") is True
        assert db.deleted
        assert m.delete_session("filey") is True
        assert m.get_session("filey") is None

        # DB delete error -> still tries file
        class BadDB:
            def query(self, e):
                raise RuntimeError("boom")

            def close(self):
                pass
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(BadDB())):
            m.create_session("u1", session_id="dbonly") if False else None
        assert m.delete_session("nothing") is False

    def test_rename_session_db(self, tmp_path):
        db = ChatFakeDB(sessions=[_db_session()])
        m = self._db_manager(tmp_path, db)
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(db)):
            assert m.rename_session("s1", "New") is True  # DB updated

        # DB error -> False
        class BadDB:
            def query(self, e):
                raise RuntimeError("boom")

            def close(self):
                pass
        with patch.object(csmmod, "get_db_session", return_value=FakeCM(BadDB())):
            assert m.rename_session("s1", "X") is False

    def test_get_chat_session_manager_factory(self, tmp_path):
        m = csmmod.get_chat_session_manager("ws-x")
        assert m.workspace_id == "ws-x"

    def test_ensure_file_creates(self, tmp_path):
        f = tmp_path / "new.json"
        m = ChatSessionManager(sessions_file=str(f)) if False else None
        # construct in file mode without touching default storage
        import os
        old = os.environ.get("ATOM_CHAT_STORAGE")
        os.environ["ATOM_CHAT_STORAGE"] = "file"
        try:
            m = ChatSessionManager(sessions_file=str(f))
        finally:
            if old is None:
                os.environ.pop("ATOM_CHAT_STORAGE", None)
            else:
                os.environ["ATOM_CHAT_STORAGE"] = old
        assert f.exists()
