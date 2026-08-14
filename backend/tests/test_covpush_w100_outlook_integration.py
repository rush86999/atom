"""Coverage wave 100 — integrations/outlook_integration.py (TDD, 0% baseline).

Unit tests for the OutlookIntegration service class with the `requests`
library fully mocked — zero network, zero LLM spend. The module-level
singleton is replaced by a fresh instance per test so no state leaks.

Covers: set_access_token, get_headers (with/without token), get_user_info
(200 / non-200 / exception), list_items (200 / non-200 / exception),
create_item (200/201 / non-2xx / exception), all three endpoint builders,
and fetch_records (default 30-day window, explicit dates, OData filter
escaping, full normalization incl. sender/recipients/cc/body, missing
fields, malformed message -> skip, non-200 -> [], exception -> []).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from integrations.outlook_integration import OutlookIntegration


@pytest.fixture
def svc(monkeypatch):
    monkeypatch.delenv("OUTLOOK_CLIENT_ID", raising=False)
    monkeypatch.delenv("OUTLOOK_CLIENT_SECRET", raising=False)
    return OutlookIntegration()


class TestTokenAndHeaders:
    def test_init(self, svc):
        assert svc.client_id is None
        assert svc.client_secret is None
        assert svc.api_endpoint == "https://graph.microsoft.com"
        assert svc.access_token is None
        assert svc.integration_id == "outlook"

    def test_env_credentials(self, monkeypatch):
        monkeypatch.setenv("OUTLOOK_CLIENT_ID", "cid")
        monkeypatch.setenv("OUTLOOK_CLIENT_SECRET", "csec")
        inst = OutlookIntegration()
        assert inst.client_id == "cid"
        assert inst.client_secret == "csec"

    def test_set_access_token(self, svc):
        svc.set_access_token("tok-100")
        assert svc.access_token == "tok-100"

    def test_headers_no_token(self, svc):
        headers = svc.get_headers()
        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_headers_with_token(self, svc):
        svc.set_access_token("tok-100")
        headers = svc.get_headers()
        assert headers["Authorization"] == "Bearer tok-100"


class TestGetUserInfo:
    async def test_success(self, svc):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"id": "u1", "mail": "a@b.c"}
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp) as mock_get:
            result = await svc.get_user_info()
        assert result == {"id": "u1", "mail": "a@b.c"}
        mock_get.assert_called_once_with(
            "https://graph.microsoft.com/me", headers=svc.get_headers())

    async def test_non_200(self, svc):
        resp = MagicMock()
        resp.status_code = 401
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            assert await svc.get_user_info() is None

    async def test_exception(self, svc):
        with patch("integrations.outlook_integration.requests.get",
                   side_effect=RuntimeError("network")):
            assert await svc.get_user_info() is None


class TestListItems:
    async def test_success(self, svc):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"value": [{"id": "m1"}]}
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp) as mock_get:
            result = await svc.list_items()
        assert result == {"value": [{"id": "m1"}]}
        mock_get.assert_called_once_with(
            "https://graph.microsoft.com/me/messages",
            headers=svc.get_headers())

    async def test_non_200(self, svc):
        resp = MagicMock()
        resp.status_code = 500
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            assert await svc.list_items() == []

    async def test_exception(self, svc):
        with patch("integrations.outlook_integration.requests.get",
                   side_effect=RuntimeError("boom")):
            assert await svc.list_items() == []


class TestCreateItem:
    @pytest.mark.parametrize("status", [200, 201])
    async def test_success(self, svc, status):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = {"id": "sent1"}
        with patch("integrations.outlook_integration.requests.post",
                   return_value=resp) as mock_post:
            result = await svc.create_item({"subject": "hi"})
        assert result == {"id": "sent1"}
        mock_post.assert_called_once_with(
            "https://graph.microsoft.com/me/sendMail",
            json={"subject": "hi"}, headers=svc.get_headers())

    async def test_non_2xx(self, svc):
        resp = MagicMock()
        resp.status_code = 400
        with patch("integrations.outlook_integration.requests.post",
                   return_value=resp):
            assert await svc.create_item({}) is None

    async def test_exception(self, svc):
        with patch("integrations.outlook_integration.requests.post",
                   side_effect=RuntimeError("boom")):
            assert await svc.create_item({}) is None


class TestEndpoints:
    def test_user_endpoint(self, svc):
        assert svc._get_user_endpoint() == \
            "https://graph.microsoft.com/me"

    def test_list_endpoint(self, svc):
        assert svc._get_list_endpoint() == \
            "https://graph.microsoft.com/me/messages"

    def test_create_endpoint(self, svc):
        assert svc._get_create_endpoint() == \
            "https://graph.microsoft.com/me/sendMail"


class TestFetchRecords:
    def _graph_response(self, messages):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"value": messages}
        return resp

    async def test_default_date_window(self, svc):
        resp = self._graph_response([])
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp) as mock_get:
            assert await svc.fetch_records() == []
        url = mock_get.call_args.args[0]
        assert "$top=500" in url
        assert "$select=" in url
        assert "receivedDateTime ge" in url
        assert "receivedDateTime le" in url

    async def test_explicit_dates(self, svc):
        resp = self._graph_response([])
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp) as mock_get:
            await svc.fetch_records(start_date=start, end_date=end, limit=10)
        url = mock_get.call_args.args[0]
        assert "$top=10" in url
        assert "2026-01-01" in url
        assert "2026-01-31" in url

    async def test_filter_escaping(self, svc):
        resp = self._graph_response([])
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp) as mock_get:
            await svc.fetch_records(
                start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
        url = mock_get.call_args.args[0]
        assert "T00:00:00%2B00:00" in url or "T00%3A00%3A00" in url

    async def test_full_normalization(self, svc):
        msg = {
            "id": "m1",
            "subject": "Hello",
            "sender": {"emailAddress": {"address": "boss@x.com"}},
            "from": {"emailAddress": {"address": "boss@x.com"}},
            "toRecipients": [{"emailAddress": {"address": "a@x.com"}},
                             {"emailAddress": {"address": "b@x.com"}}],
            "ccRecipients": [{"emailAddress": {"address": "c@x.com"}}],
            "receivedDateTime": "2026-01-02T03:04:05Z",
            "body": {"content": "<p>hi</p>"},
        }
        resp = self._graph_response([msg])
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            records = await svc.fetch_records()
        assert len(records) == 1
        record = records[0]
        assert record["id"] == "m1"
        assert record["type"] == "email"
        assert record["subject"] == "Hello"
        assert record["from"] == "boss@x.com"
        assert record["to"] == ["a@x.com", "b@x.com"]
        assert record["cc"] == ["c@x.com"]
        assert record["date"] == "2026-01-02T03:04:05Z"
        assert record["body"] == "<p>hi</p>"
        assert record["integration"] == "outlook"
        assert "outlook.office.com" in record["url"]

    async def test_missing_fields(self, svc):
        resp = self._graph_response([{"id": "m2"}])
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            records = await svc.fetch_records()
        assert len(records) == 1
        record = records[0]
        assert record["from"] == ""
        assert record["to"] == []
        assert record["cc"] == []
        assert record["body"] == ""

    async def test_recipients_without_email_address(self, svc):
        msg = {"id": "m3", "toRecipients": [{"name": "NoMail"}],
               "ccRecipients": [{"name": "NoMail2"}]}
        resp = self._graph_response([msg])
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            records = await svc.fetch_records()
        assert records[0]["to"] == []
        assert records[0]["cc"] == []

    async def test_malformed_message_skipped(self, svc):
        bad = MagicMock()
        bad.get.side_effect = RuntimeError("malformed")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"value": [bad, {"id": "ok1"}]}
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            records = await svc.fetch_records()
        assert len(records) == 1
        assert records[0]["id"] == "ok1"

    async def test_non_200(self, svc):
        resp = MagicMock()
        resp.status_code = 403
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp):
            assert await svc.fetch_records() == []

    async def test_exception(self, svc):
        with patch("integrations.outlook_integration.requests.get",
                   side_effect=RuntimeError("boom")):
            assert await svc.fetch_records() == []

    async def test_fetch_uses_access_token_header(self, svc):
        resp = self._graph_response([])
        svc.set_access_token("tok-100")
        with patch("integrations.outlook_integration.requests.get",
                   return_value=resp) as mock_get:
            await svc.fetch_records()
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer tok-100"
