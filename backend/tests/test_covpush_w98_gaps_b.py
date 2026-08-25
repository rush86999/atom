# -*- coding: utf-8 -*-
"""Coverage wave 98 gaps-b — real coverage gaps found by measurement:

- integrations/airtable_service.py   (19% baseline)
- integrations/dropbox_service.py    (77% baseline)
- integrations/deepgram_service.py   (17% baseline)
- integrations/twilio_service.py     (27% baseline)

Plain pytest + unittest.mock. No network / no LLM / no real DB: httpx
boundaries mocked, dropbox SDK mocked, SessionLocal mocked.
"""
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ── Fake dropbox SDK (real package not installed in this venv) ──────────────
def _install_fake_dropbox():
    if "dropbox" in sys.modules:
        # Another test module (e.g. test_covpush_w93_dropbox.py) already
        # installed a fake SDK — reuse it.
        if hasattr(sys.modules["dropbox"], "files"):
            return
    dbx = types.ModuleType("dropbox")
    dbx.__fake__ = True
    dbx.__path__ = []  # mark as package so submodule imports work

    files = types.ModuleType("dropbox.files")

    class Metadata:
        def __init__(self, name="f.txt", path_display="/f.txt", **kw):
            self.id = "id-1"
            self.name = name
            self.path_display = path_display
            self.path_lower = path_display.lower()

    class FileMetadata(Metadata):
        pass

    class FolderMetadata(Metadata):
        pass

    class WriteMode:
        overwrite = "overwrite"

    class SearchOptions:
        def __init__(self, path="", max_results=50, file_extensions=None):
            self.path, self.max_results, self.file_extensions = path, max_results, file_extensions

    files.Metadata = Metadata
    files.FileMetadata = FileMetadata
    files.FolderMetadata = FolderMetadata
    files.WriteMode = WriteMode
    files.SearchOptions = SearchOptions

    sharing = types.ModuleType("dropbox.sharing")

    class SharedLinkSettings:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    sharing.SharedLinkSettings = SharedLinkSettings

    exceptions = types.ModuleType("dropbox.exceptions")

    class ApiError(Exception):
        pass

    class AuthError(Exception):
        pass

    exceptions.ApiError = ApiError
    exceptions.AuthError = AuthError

    dbx.files = files
    dbx.sharing = sharing
    dbx.exceptions = exceptions
    dbx.Dropbox = MagicMock()
    sys.modules["dropbox.exceptions"] = exceptions
    sys.modules["dropbox"] = dbx
    sys.modules["dropbox.files"] = files
    sys.modules["dropbox.sharing"] = sharing



def _hresp(status=200, json_data=None):
    return httpx.Response(status, json=json_data if json_data is not None else {},
                          request=httpx.Request("GET", "http://x"))


def _ok(json_data=None):
    return _hresp(200, json_data if json_data is not None else {})


def _err():
    return _hresp(500, {"error": "boom"})


# ============================================================================
# integrations/airtable_service.py
# ============================================================================
from integrations.airtable_service import AirtableService, airtable_service


def _airtable():
    svc = AirtableService(tenant_id="t1", config={"api_key": "key"})
    svc.http = MagicMock()
    return svc


class TestAirtableService:
    def test_headers_and_close(self):
        svc = AirtableService(tenant_id="t1", config={})
        assert svc._get_headers()["Authorization"] == "Bearer None"
        assert svc._get_headers("tok")["Authorization"] == "Bearer tok"
        svc.client = MagicMock()
        svc.client.aclose = AsyncMock()
        import asyncio
        asyncio.get_event_loop().run_until_complete(svc.close())
        svc.client.aclose.assert_awaited_once()

    def test_get_bases(self):
        svc = _airtable()
        svc.http.get = AsyncMock(return_value=_ok({"bases": [{"id": "b"}]}))
        import asyncio
        assert asyncio.get_event_loop().run_until_complete(svc.get_bases()) == [{"id": "b"}]

    def test_get_bases_error(self):
        svc = _airtable()
        svc.http.get = AsyncMock(side_effect=RuntimeError("x"))
        import asyncio
        assert asyncio.get_event_loop().run_until_complete(svc.get_bases()) == []

    def test_get_tables(self):
        svc = _airtable()
        svc.http.get = AsyncMock(return_value=_ok({"tables": [{"id": "tbl"}]}))
        import asyncio
        assert asyncio.get_event_loop().run_until_complete(svc.get_tables("b")) == [{"id": "tbl"}]

    def test_get_tables_error(self):
        svc = _airtable()
        svc.http.get = AsyncMock(side_effect=RuntimeError("x"))
        import asyncio
        assert asyncio.get_event_loop().run_until_complete(svc.get_tables("b")) == []

    @pytest.mark.asyncio
    async def test_list_records(self):
        svc = _airtable()
        svc.http.get = AsyncMock(return_value=_ok({"records": [{"id": "r"}]}))
        res = await svc.list_records("b", "tbl", view="v", filter_formula="x")
        assert res == [{"id": "r"}]

    @pytest.mark.asyncio
    async def test_list_records_no_key(self):
        svc = _airtable()
        svc.api_key = None
        with pytest.raises(HTTPException) as ei:
            await svc.list_records("b", "tbl")
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_list_records_http_error(self):
        svc = _airtable()
        svc.http.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException) as ei:
            await svc.list_records("b", "tbl")
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_record(self):
        svc = _airtable()
        svc.http.get = AsyncMock(return_value=_ok({"id": "r"}))
        assert (await svc.get_record("b", "tbl", "r"))["id"] == "r"

    @pytest.mark.asyncio
    async def test_get_record_errors(self):
        svc = _airtable()
        svc.api_key = None
        with pytest.raises(HTTPException):
            await svc.get_record("b", "tbl", "r")
        svc.api_key = "key"
        svc.http.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.get_record("b", "tbl", "r")

    @pytest.mark.asyncio
    async def test_create_record(self):
        svc = _airtable()
        svc.http.post = AsyncMock(return_value=_ok({"id": "new"}))
        assert (await svc.create_record("b", "tbl", {"f": 1}))["id"] == "new"
        svc.api_key = None
        with pytest.raises(HTTPException):
            await svc.create_record("b", "tbl", {})
        svc.api_key = "key"
        svc.http.post = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.create_record("b", "tbl", {})

    @pytest.mark.asyncio
    async def test_update_record(self):
        svc = _airtable()
        svc.http.patch = AsyncMock(return_value=_ok({"id": "r"}))
        assert (await svc.update_record("b", "tbl", "r", {"f": 2}))["id"] == "r"
        svc.api_key = None
        with pytest.raises(HTTPException):
            await svc.update_record("b", "tbl", "r", {})
        svc.api_key = "key"
        svc.http.patch = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.update_record("b", "tbl", "r", {})

    @pytest.mark.asyncio
    async def test_delete_record(self):
        svc = _airtable()
        svc.http.delete = AsyncMock(return_value=_ok({"id": "r"}))
        assert (await svc.delete_record("b", "tbl", "r"))["id"] == "r"
        svc.api_key = None
        with pytest.raises(HTTPException):
            await svc.delete_record("b", "tbl", "r")
        svc.api_key = "key"
        svc.http.delete = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.delete_record("b", "tbl", "r")

    @pytest.mark.asyncio
    async def test_health_check_and_capabilities(self):
        svc = _airtable()
        hc = await svc.health_check()
        assert hc["ok"] is True
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is False
        assert len(caps["operations"]) == 7

    @pytest.mark.asyncio
    async def test_execute_operation_all(self):
        svc = _airtable()
        svc.get_bases = AsyncMock(return_value=[{"id": "b"}])
        svc.get_tables = AsyncMock(return_value=[{"id": "t"}])
        svc.list_records = AsyncMock(return_value=[{"id": "r"}])
        svc.get_record = AsyncMock(return_value={"id": "r"})
        svc.create_record = AsyncMock(return_value={"id": "r"})
        svc.update_record = AsyncMock(return_value={"id": "r"})
        svc.delete_record = AsyncMock(return_value={"id": "r"})

        assert (await svc.execute_operation("get_bases", {}))["result"] == [{"id": "b"}]
        assert (await svc.execute_operation("get_tables", {"base_id": "b"}))["result"] == [{"id": "t"}]
        assert (await svc.execute_operation(
            "list_records", {"base_id": "b", "table_name": "t", "view": "v", "filter_formula": "f"}))["result"] == [{"id": "r"}]
        assert (await svc.execute_operation(
            "get_record", {"base_id": "b", "table_name": "t", "record_id": "r"}))["success"] is True
        assert (await svc.execute_operation(
            "create_record", {"base_id": "b", "table_name": "t", "fields": {}}))["success"] is True
        assert (await svc.execute_operation(
            "update_record", {"base_id": "b", "table_name": "t", "record_id": "r", "fields": {}}))["success"] is True
        assert (await svc.execute_operation(
            "delete_record", {"base_id": "b", "table_name": "t", "record_id": "r"}))["success"] is True

    @pytest.mark.asyncio
    async def test_execute_operation_tenant_mismatch_and_unknown_and_error(self):
        svc = _airtable()
        r = await svc.execute_operation("get_bases", {}, context={"tenant_id": "other"})
        assert r["success"] is False and "mismatch" in r["error"]
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False and "Unknown operation" in r["error"]
        svc.get_bases = AsyncMock(side_effect=RuntimeError("boom"))
        r = await svc.execute_operation("get_bases", {})
        assert r["success"] is False and "failed" in r["error"]

    @pytest.mark.asyncio
    async def test_sync_to_postgres_cache(self):
        svc = _airtable()
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.IntegrationMetric", MagicMock()):
            r = await svc.sync_to_postgres_cache("ws1", "base1")
        assert r == {"success": True, "metrics_synced": 1}
        db.commit.assert_called_once()
        db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_to_postgres_cache_existing_and_error(self):
        svc = _airtable()
        existing = MagicMock()
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = existing
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.IntegrationMetric", MagicMock()):
            r = await svc.sync_to_postgres_cache("ws1")
            assert r["success"] is True
            db.commit.side_effect = RuntimeError("commit failed")
            r = await svc.sync_to_postgres_cache("ws1")
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_sync_outer_failure_and_full_sync(self):
        svc = _airtable()
        with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")):
            r = await svc.sync_to_postgres_cache("ws1")
        assert r["success"] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await svc.full_sync("ws1", "b")
        assert r["success"] is True and r["workspace_id"] == "ws1"

    def test_global_singleton(self):
        assert isinstance(airtable_service, AirtableService)


# ============================================================================
# integrations/deepgram_service.py
# ============================================================================
from integrations.deepgram_service import DeepgramService


def _deepgram():
    svc = DeepgramService(tenant_id="t1", config={"deepgram_api_key": "dk"})
    svc.client = MagicMock()
    return svc


class TestDeepgramService:
    @pytest.mark.asyncio
    async def test_close_and_headers_and_caps(self):
        svc = DeepgramService(tenant_id="t1", config={})
        svc.client = MagicMock()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()
        assert svc._get_headers()["Authorization"] == "Token None"
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is False
        assert len(caps["operations"]) == 3

    @pytest.mark.asyncio
    async def test_health_check(self):
        assert _deepgram().health_check()["healthy"] is True
        assert DeepgramService().health_check()["status"] == "unconfigured"

    @pytest.mark.asyncio
    async def test_execute_tenant_mismatch_and_no_key(self):
        svc = _deepgram()
        r = await svc.execute_operation("transcribe_audio", {}, context={"tenant_id": "other"})
        assert r["success"] is False and "validation failed" in r["error"]
        r = await DeepgramService().execute_operation("get_projects", {})
        assert r["success"] is False and "not configured" in r["error"]

    @pytest.mark.asyncio
    async def test_execute_transcribe_url_and_file(self):
        svc = _deepgram()
        svc.transcribe_url = AsyncMock(return_value={"text": "hi"})
        r = await svc.execute_operation("transcribe_audio", {"audio_url": "http://a"})
        assert r["success"] is True
        svc.transcribe_file = AsyncMock(return_value={"text": "yo"})
        r = await svc.execute_operation("transcribe_audio", {"audio_data": b"x", "model": "m"})
        assert r["success"] is True
        r = await svc.execute_operation("transcribe_audio", {})
        assert r["success"] is False and "Missing" in r["error"]

    @pytest.mark.asyncio
    async def test_execute_projects_usage_unsupported_error(self):
        svc = _deepgram()
        svc.get_projects = AsyncMock(return_value=[{"id": "p"}])
        svc.get_usage = AsyncMock(return_value={"hours": 1})
        assert (await svc.execute_operation("get_projects", {}))["success"] is True
        assert (await svc.execute_operation("get_usage", {"project_id": "p"}))["success"] is True
        r = await svc.execute_operation("get_usage", {})
        assert r["success"] is False and "project_id" in r["error"]
        svc.get_projects = AsyncMock(side_effect=RuntimeError("boom"))
        r = await svc.execute_operation("get_projects", {})
        assert r["success"] is False and "boom" in r["error"]
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False and "not supported" in r["error"]

    @pytest.mark.asyncio
    async def test_transcribe_url(self):
        svc = _deepgram()
        svc.client.post = AsyncMock(return_value=_ok({"text": "hello"}))
        res = await svc.transcribe_url("http://a", punctuate=False, diarize=True)
        assert res["text"] == "hello"
        svc.client.post = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.transcribe_url("http://a")

    @pytest.mark.asyncio
    async def test_transcribe_url_no_key(self):
        svc = DeepgramService(tenant_id="t", config={})
        svc.client = MagicMock()
        with pytest.raises(HTTPException):
            await svc.transcribe_url("http://a")

    @pytest.mark.asyncio
    async def test_transcribe_file(self):
        # BUG (now fixed in source): transcribe_file referenced undefined
        # `api_key` (should be self.api_key); now succeeds end-to-end.
        svc = _deepgram()
        svc.client.post = AsyncMock(return_value=_ok({"text": "f"}))
        result = await svc.transcribe_file(b"data")
        # transcribe_file returns the raw JSON body on success
        assert result == {"text": "f"}
        auth = svc.client.post.call_args[1]["headers"]["Authorization"]
        assert auth == "Token dk"

    @pytest.mark.asyncio
    async def test_transcribe_file_via_execute(self):
        svc = _deepgram()
        svc.client.post = AsyncMock(return_value=_ok({"text": "f"}))
        r = await svc.execute_operation("transcribe_audio", {"audio_data": b"d"})
        assert r["success"] is True  # api_key bug fixed; transcription works

    @pytest.mark.asyncio
    async def test_get_projects(self):
        svc = _deepgram()
        svc.client.get = AsyncMock(return_value=_ok({"projects": [{"id": "p"}]}))
        assert await svc.get_projects() == [{"id": "p"}]
        svc.client.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.get_projects()
        s2 = DeepgramService()
        s2.client = MagicMock()
        with pytest.raises(HTTPException):
            await s2.get_projects()

    @pytest.mark.asyncio
    async def test_get_usage(self):
        svc = _deepgram()
        svc.client.get = AsyncMock(return_value=_ok({"hours": 2}))
        assert (await svc.get_usage("p", "2026-01-01", "2026-02-01"))["hours"] == 2
        svc.client.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await svc.get_usage("p")
        s2 = DeepgramService()
        s2.client = MagicMock()
        with pytest.raises(HTTPException):
            await s2.get_usage("p")


# ============================================================================
# integrations/twilio_service.py
# ============================================================================
from integrations.twilio_service import TwilioService


def _twilio():
    svc = TwilioService(tenant_id="t1", config={
        "account_sid": "AC1", "auth_token": "tok", "phone_number": "+15550001"})
    svc.http = MagicMock()
    return svc


class TestTwilioService:
    def test_headers(self):
        h = _twilio()._get_headers()
        assert h["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_close(self):
        svc = _twilio()
        svc.client = MagicMock()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_sms(self):
        svc = _twilio()
        svc.http.post = AsyncMock(return_value=_ok({"sid": "SM1"}))
        assert (await svc.send_sms("+15550002", "hi"))["sid"] == "SM1"

    @pytest.mark.asyncio
    async def test_send_sms_no_auth(self):
        svc = TwilioService(tenant_id="t", config={})
        svc.http = MagicMock()
        with pytest.raises(HTTPException) as ei:
            await svc.send_sms("+15550002", "hi")
        assert ei.value.status_code == 401

    @pytest.mark.asyncio
    async def test_send_sms_no_sender(self):
        svc = _twilio()
        svc.phone_number = None
        with pytest.raises(HTTPException) as ei:
            await svc.send_sms("+15550002", "hi")
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_send_sms_http_error(self):
        svc = _twilio()
        svc.http.post = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException) as ei:
            await svc.send_sms("+15550002", "hi")
        assert ei.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_messages(self):
        svc = _twilio()
        svc.http.get = AsyncMock(return_value=_ok({"messages": [{"sid": "SM"}]}))
        assert await svc.get_messages(to="+1", from_number="+2") == [{"sid": "SM"}]

    @pytest.mark.asyncio
    async def test_get_messages_errors(self):
        svc = TwilioService(tenant_id="t", config={})
        svc.http = MagicMock()
        with pytest.raises(HTTPException):
            await svc.get_messages()
        s2 = _twilio()
        s2.http.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await s2.get_messages()

    @pytest.mark.asyncio
    async def test_make_call(self):
        svc = _twilio()
        svc.http.post = AsyncMock(return_value=_ok({"sid": "CA1"}))
        assert (await svc.make_call("+15550002", "http://twiml"))["sid"] == "CA1"

    @pytest.mark.asyncio
    async def test_make_call_errors(self):
        svc = TwilioService(tenant_id="t", config={})
        svc.http = MagicMock()
        with pytest.raises(HTTPException):
            await svc.make_call("+1", "http://t")
        s2 = _twilio()
        s2.phone_number = None
        with pytest.raises(HTTPException):
            await s2.make_call("+1", "http://t")
        s3 = _twilio()
        s3.http.post = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await s3.make_call("+1", "http://t")

    @pytest.mark.asyncio
    async def test_get_calls(self):
        svc = _twilio()
        svc.http.get = AsyncMock(return_value=_ok({"calls": [{"sid": "CA"}]}))
        assert await svc.get_calls(to="+1", from_number="+2") == [{"sid": "CA"}]

    @pytest.mark.asyncio
    async def test_get_calls_errors(self):
        svc = TwilioService(tenant_id="t", config={})
        svc.http = MagicMock()
        with pytest.raises(HTTPException):
            await svc.get_calls()
        s2 = _twilio()
        s2.http.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await s2.get_calls()

    @pytest.mark.asyncio
    async def test_get_account_info(self):
        svc = _twilio()
        svc.http.get = AsyncMock(return_value=_ok({"friendly_name": "acct"}))
        assert (await svc.get_account_info())["friendly_name"] == "acct"

    @pytest.mark.asyncio
    async def test_get_account_info_errors(self):
        svc = TwilioService(tenant_id="t", config={})
        svc.http = MagicMock()
        with pytest.raises(HTTPException):
            await svc.get_account_info()
        s2 = _twilio()
        s2.http.get = AsyncMock(return_value=_err())
        with pytest.raises(HTTPException):
            await s2.get_account_info()

    @pytest.mark.asyncio
    async def test_health_check_and_capabilities(self):
        hc = await _twilio().health_check()
        assert hc["ok"] is True and hc["service"] == "twilio"
        caps = _twilio().get_capabilities()
        assert caps["supports_webhooks"] is True
        assert len(caps["operations"]) == 5

    @pytest.mark.asyncio
    async def test_execute_operation_all(self):
        svc = _twilio()
        svc.send_sms = AsyncMock(return_value={"sid": "SM"})
        svc.get_messages = AsyncMock(return_value=[{"sid": "SM"}])
        svc.make_call = AsyncMock(return_value={"sid": "CA"})
        svc.get_calls = AsyncMock(return_value=[{"sid": "CA"}])
        svc.get_account_info = AsyncMock(return_value={"f": "acct"})
        assert (await svc.execute_operation("send_sms", {"to": "+1", "body": "x"}))["success"] is True
        assert (await svc.execute_operation("get_messages", {"to": "+1", "page_size": 5}))["success"] is True
        assert (await svc.execute_operation("make_call", {"to": "+1", "twiml_url": "u"}))["success"] is True
        assert (await svc.execute_operation("get_calls", {"from_number": "+2"}))["success"] is True
        assert (await svc.execute_operation("get_account_info", {}))["success"] is True

    @pytest.mark.asyncio
    async def test_execute_operation_unknown_and_error(self):
        svc = _twilio()
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False and "Unknown" in r["error"]
        svc.send_sms = AsyncMock(side_effect=RuntimeError("boom"))
        r = await svc.execute_operation("send_sms", {"to": "+1", "body": "x"})
        assert r["success"] is False and "failed" in r["error"]


# ============================================================================
# integrations/dropbox_service.py
# NOTE: dropbox SDK is not installed in this venv. The fake module and the
# service import are done lazily inside a fixture so that, when collected
# alongside other fake-dropbox test files, whichever fake was installed at
# collection time wins — keeping integrations.dropbox_service's module
# binding consistent.
# ============================================================================


def _dbx():
    """Lazily import DropboxService (fake SDK installed by the fixture)."""
    from integrations.dropbox_service import DropboxService
    return DropboxService


def _file_meta(**kw):
    m = MagicMock()
    m.id = "id:1"
    m.name = "a.txt"
    m.path_display = "/a.txt"
    m.path_lower = "/a.txt"
    for k, v in kw.items():
        setattr(m, k, v)
    return m


@pytest.fixture(autouse=True)
def _dropbox_env():
    """Install fake SDK (only if absent) and point
    integrations.dropbox_service at the current sys.modules fake."""
    if "dropbox" not in sys.modules or not hasattr(sys.modules["dropbox"], "files"):
        _install_fake_dropbox()
    import integrations.dropbox_service as svc_mod
    old = svc_mod.dropbox
    svc_mod.dropbox = sys.modules["dropbox"]
    yield
    svc_mod.dropbox = old


class TestDropboxServiceGaps:
    def test_capabilities(self):
        caps = _dbx()().get_capabilities()
        op_ids = [op["id"] for op in caps["operations"]]
        assert {"walk_files", "ingest_file_to_memory", "full_sync"} <= set(op_ids)

    def test_health_check(self):
        healthy = _dbx()(config={"access_token": "t"}).health_check()
        assert healthy["ok"] is True
        unconfigured = _dbx()(config={}).health_check()
        assert unconfigured["ok"] is False and unconfigured["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_execute_no_token(self):
        r = await _dbx()().execute_operation("list_files", {})
        assert r["success"] is False and "token" in r["error"]

    @pytest.mark.asyncio
    async def test_execute_list_files(self):
        svc = _dbx()(config={"access_token": "t"})
        import integrations.dropbox_service as svc_mod

        class _Folder:
            def __init__(self):
                self.id = "id:f"
                self.name = "d"
                self.path_display = "/d"
                self.path_lower = "/d"

        with patch.object(svc_mod.dropbox.files, "FolderMetadata", _Folder), \
             patch.object(svc_mod.dropbox, "Dropbox") as D:
            D.return_value.files_list_folder.return_value = SimpleNamespace(
                entries=[_file_meta(), _Folder()], cursor="c", has_more=True)
            r = await svc.execute_operation("list_files", {"path": "/"})
        assert r["success"] is True
        assert r["result"]["cursor"] == "c"
        assert r["result"]["entries"][1]["type"] == "folder"

    @pytest.mark.asyncio
    async def test_execute_search_files_and_space(self):
        svc = _dbx()(config={"access_token": "t"})
        meta = _file_meta()
        match = SimpleNamespace(metadata=SimpleNamespace(get_metadata=lambda: meta))
        with patch("integrations.dropbox_service.dropbox.Dropbox") as D:
            D.return_value.files_search_v2.return_value = SimpleNamespace(matches=[match], has_more=False)
            r = await svc.execute_operation("search_files", {"query": "a"})
        assert r["success"] is True and r["result"]["matches"][0]["name"] == "a.txt"
        with patch("integrations.dropbox_service.dropbox.Dropbox") as D:
            D.return_value.users_get_space_usage.return_value = SimpleNamespace(used=10, allocation="individual")
            r = await svc.execute_operation("get_space_usage", {})
        assert r["success"] is True and r["result"]["used"] == 10

    @pytest.mark.asyncio
    async def test_execute_unsupported_and_error(self):
        svc = _dbx()(config={"access_token": "t"})
        r = await svc.execute_operation("nope", {})
        assert r["success"] is False and "not supported" in r["error"]
        with patch("integrations.dropbox_service.dropbox.Dropbox", side_effect=RuntimeError("boom")):
            r = await svc.execute_operation("list_files", {})
        assert r["success"] is False

    def test_get_client_no_token(self):
        with pytest.raises(ValueError):
            _dbx()()._get_dropbox_client(None)

    @pytest.mark.asyncio
    async def test_search_metadata_none(self):
        svc = _dbx()(config={"access_token": "t"})
        match = SimpleNamespace(metadata=None)
        with patch("integrations.dropbox_service.dropbox.Dropbox") as D:
            D.return_value.files_search_v2.return_value = SimpleNamespace(matches=[match])
            r = await svc.search("q", access_token="t")
        assert r == []

    def test_global_singleton(self):
        from integrations.dropbox_service import DropboxService, dropbox_service
        assert isinstance(dropbox_service, DropboxService)
