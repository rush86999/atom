# -*- coding: utf-8 -*-
"""Coverage wave 95 — integrations/teams_service (TeamsService).

Standalone, fully mocked (requests.Session), zero network, zero LLM spend.

Covers: __init__ (token from config + env fallback, no-token), test_connection
(200 success with mail/userPrincipalName fallback, non-200 error status,
exception path -> generic message — NO str(e) leak), get_teams / get_team /
get_channels / get_channel / create_channel / get_messages / send_message /
reply_to_message / get_meetings (team + user calendar) / create_meeting (with
and without attendees) / get_team_members / get_channel_members /
add_member_to_channel / remove_member_from_channel / get_online_meeting /
join_meeting / get_chat_messages / send_chat_message / get_user_presence (user
+ self) / set_user_presence: success + exception paths, health_check,
get_capabilities, execute_operation (get_teams / send_message / unknown ->
NotImplementedError per base-class contract).

Bug found (TDD RED -> GREEN): test_connection exception path leaked str(e) to
the caller.
"""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from integrations.teams_service import TeamsService


def _resp(status=200, payload=None, json_error=None):
    r = MagicMock()
    r.status_code = status
    if json_error is not None:
        r.json.side_effect = json_error
    else:
        r.json.return_value = payload if payload is not None else {}
    if status >= 400:
        r.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
    return r


class TestInit:
    def test_no_config_arg(self, monkeypatch):
        monkeypatch.delenv("TEAMS_ACCESS_TOKEN", raising=False)
        svc = TeamsService()  # config=None -> {}
        assert svc.access_token is None

    def test_token_from_config(self):
        svc = TeamsService(config={"access_token": "cfg-tok"})
        assert svc.access_token == "cfg-tok"
        assert svc.session.headers["Authorization"] == "Bearer cfg-tok"
        assert svc.session.headers["User-Agent"] == "ATOM-Platform/1.0"

    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("TEAMS_ACCESS_TOKEN", "env-tok")
        svc = TeamsService(config={})
        assert svc.access_token == "env-tok"
        assert svc.session.headers["Authorization"] == "Bearer env-tok"

    def test_config_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("TEAMS_ACCESS_TOKEN", "env-tok")
        svc = TeamsService(config={"access_token": "cfg-tok"})
        assert svc.access_token == "cfg-tok"

    def test_no_token(self, monkeypatch):
        monkeypatch.delenv("TEAMS_ACCESS_TOKEN", raising=False)
        svc = TeamsService(config={})
        assert svc.access_token is None
        assert "Authorization" not in svc.session.headers


class TestConnection:
    def _svc(self):
        svc = TeamsService(config={"access_token": "t"})
        svc.session = MagicMock()
        return svc

    def test_success_with_mail(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"displayName": "Ada",
                                                   "mail": "ada@x.com"})
        out = svc.test_connection()
        assert out["status"] == "success"
        assert out["authenticated"] is True
        assert out["user"] == "Ada"
        assert out["email"] == "ada@x.com"
        assert svc.session.get.call_args.args[0].endswith("/me")

    def test_success_with_user_principal_fallback(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"displayName": "",
                                                   "userPrincipalName": "u@x.com"})
        out = svc.test_connection()
        assert out["email"] == "u@x.com"

    def test_success_missing_identifiers(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {})
        out = svc.test_connection()
        assert out["user"] == ""
        assert out["email"] == ""

    def test_non_200(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(401)
        out = svc.test_connection()
        assert out["status"] == "error"
        assert out["authenticated"] is False
        assert "401" in out["message"]

    def test_exception_generic_no_str_e(self):
        """RED: exception path returned str(e) verbatim; must be generic."""
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("secret-network-detail")
        out = svc.test_connection()
        assert out["status"] == "error"
        assert out["authenticated"] is False
        assert "secret-network-detail" not in out["message"]


class _ListBase:
    def _svc(self):
        svc = TeamsService(config={"access_token": "t"})
        svc.session = MagicMock()
        return svc


class TestReads(_ListBase):
    def test_get_teams(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "t1"}]})
        assert svc.get_teams() == [{"id": "t1"}]
        assert svc.session.get.call_args.args[0].endswith("/me/joinedTeams")

    def test_get_teams_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_teams() == []

    def test_get_team(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"id": "t1", "name": "Eng"})
        out = svc.get_team("t1")
        assert out["name"] == "Eng"
        assert svc.session.get.call_args.args[0].endswith("/teams/t1")

    def test_get_team_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_team("t1") is None

    def test_get_channels(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "c1"}]})
        assert svc.get_channels("t1") == [{"id": "c1"}]
        assert svc.session.get.call_args.args[0].endswith("/teams/t1/channels")

    def test_get_channels_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_channels("t1") == []

    def test_get_channel(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"id": "c1"})
        assert svc.get_channel("t1", "c1") == {"id": "c1"}

    def test_get_channel_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_channel("t1", "c1") is None

    def test_get_messages(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "m1"}]})
        assert svc.get_messages("t1", "c1", limit=10) == [{"id": "m1"}]
        assert svc.session.get.call_args.kwargs["params"] == {"$top": 10}

    def test_get_messages_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_messages("t1", "c1") == []

    def test_get_team_members(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "u1"}]})
        assert svc.get_team_members("t1") == [{"id": "u1"}]
        assert svc.session.get.call_args.args[0].endswith("/groups/t1/members")

    def test_get_team_members_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_team_members("t1") == []

    def test_get_channel_members(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "u1"}]})
        assert svc.get_channel_members("t1", "c1") == [{"id": "u1"}]

    def test_get_channel_members_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_channel_members("t1", "c1") == []

    def test_get_online_meeting(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"id": "om1"})
        assert svc.get_online_meeting("om1") == {"id": "om1"}

    def test_get_online_meeting_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_online_meeting("om1") is None

    def test_get_chat_messages(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "cm1"}]})
        assert svc.get_chat_messages("chat1") == [{"id": "cm1"}]
        assert svc.session.get.call_args.args[0].endswith("/chats/chat1/messages")

    def test_get_chat_messages_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_chat_messages("chat1") == []

    def test_get_user_presence_specific_user(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"availability": "Available"})
        out = svc.get_user_presence("u1")
        assert out["availability"] == "Available"
        assert svc.session.get.call_args.args[0].endswith("/users/u1/presence")

    def test_get_user_presence_self(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"availability": "Busy"})
        out = svc.get_user_presence()
        assert out["availability"] == "Busy"
        assert svc.session.get.call_args.args[0].endswith("/me/presence")

    def test_get_user_presence_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_user_presence() is None


class TestMeetings(_ListBase):
    def test_get_meetings_team_calendar(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "e1"}]})
        out = svc.get_meetings(team_id="t1")
        assert out == [{"id": "e1"}]
        assert svc.session.get.call_args.args[0].endswith("/teams/t1/events")

    def test_get_meetings_user_calendar(self):
        svc = self._svc()
        svc.session.get.return_value = _resp(200, {"value": []})
        assert svc.get_meetings() == []
        assert svc.session.get.call_args.args[0].endswith("/me/events")
        assert svc.session.get.call_args.kwargs["params"] == {"$top": 50}

    def test_get_meetings_exception(self):
        svc = self._svc()
        svc.session.get.side_effect = ConnectionError("net")
        assert svc.get_meetings() == []

    def test_create_meeting_with_attendees(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {"id": "e1"})
        out = svc.create_meeting("Sync", "2026-01-01T10:00:00", "2026-01-01T10:30:00",
                                 attendees=["a@x.com", "b@x.com"], body="hello")
        assert out == {"id": "e1"}
        payload = svc.session.post.call_args.kwargs["json"]
        assert payload["subject"] == "Sync"
        assert payload["start"]["dateTime"] == "2026-01-01T10:00:00"
        assert payload["end"]["timeZone"] == "UTC"
        assert payload["isOnlineMeeting"] is True
        assert len(payload["attendees"]) == 2
        assert payload["attendees"][0]["emailAddress"]["address"] == "a@x.com"
        assert payload["attendees"][0]["type"] == "required"
        assert payload["body"]["content"] == "hello"

    def test_create_meeting_without_attendees(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {})
        await_ = svc.create_meeting("Sync", "s", "e")
        assert await_ == {}
        payload = svc.session.post.call_args.kwargs["json"]
        assert "attendees" not in payload

    def test_create_meeting_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.create_meeting("Sync", "s", "e") is None


class TestWrites(_ListBase):
    def test_create_channel(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {"id": "c1"})
        out = svc.create_channel("t1", "General", "desc", channel_type="private")
        assert out == {"id": "c1"}
        payload = svc.session.post.call_args.kwargs["json"]
        assert payload == {"displayName": "General", "description": "desc",
                           "membershipType": "private"}

    def test_create_channel_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.create_channel("t1", "General") is None

    def test_send_message(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {"id": "m1"})
        out = svc.send_message("t1", "c1", "<b>hi</b>")
        assert out == {"id": "m1"}
        payload = svc.session.post.call_args.kwargs["json"]
        assert payload["body"] == {"content": "<b>hi</b>", "contentType": "html"}

    def test_send_message_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.send_message("t1", "c1", "x") is None

    def test_reply_to_message(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {"id": "r1"})
        out = svc.reply_to_message("t1", "c1", "m1", "reply")
        assert out == {"id": "r1"}
        assert svc.session.post.call_args.args[0].endswith(
            "/teams/t1/channels/c1/messages/m1/replies")

    def test_reply_to_message_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.reply_to_message("t1", "c1", "m1", "x") is None

    def test_add_member_to_channel(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {})
        assert svc.add_member_to_channel("t1", "c1", "u1", role="owner") is True
        payload = svc.session.post.call_args.kwargs["json"]
        assert payload["@odata.id"].endswith("/users/u1")
        assert payload["roles"] == ["owner"]

    def test_add_member_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.add_member_to_channel("t1", "c1", "u1") is False

    def test_remove_member_from_channel(self):
        svc = self._svc()
        svc.session.delete.return_value = _resp(204)
        assert svc.remove_member_from_channel("t1", "c1", "mem1") is True

    def test_remove_member_exception(self):
        svc = self._svc()
        svc.session.delete.side_effect = ConnectionError("net")
        assert svc.remove_member_from_channel("t1", "c1", "mem1") is False

    def test_send_chat_message(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(201, {"id": "cm1"})
        out = svc.send_chat_message("chat1", "hello")
        assert out == {"id": "cm1"}
        payload = svc.session.post.call_args.kwargs["json"]
        assert payload["body"] == {"content": "hello", "contentType": "text"}

    def test_send_chat_message_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.send_chat_message("chat1", "x") is None

    def test_set_user_presence(self):
        svc = self._svc()
        svc.session.post.return_value = _resp(200, {})
        assert svc.set_user_presence("Available", "Available") is True
        payload = svc.session.post.call_args.kwargs["json"]
        assert payload == {"availability": "Available", "activity": "Available"}

    def test_set_user_presence_exception(self):
        svc = self._svc()
        svc.session.post.side_effect = ConnectionError("net")
        assert svc.set_user_presence("Busy", "InACall") is False


class TestJoinMeeting:
    def test_success(self):
        svc = TeamsService(config={"access_token": "t"})
        out = svc.join_meeting("https://teams.microsoft.com/l/meetup-join/x")
        assert out["status"] == "success"
        assert out["join_url"] == "https://teams.microsoft.com/l/meetup-join/x"


class TestHealthCheck:
    def test_healthy(self):
        svc = TeamsService(config={"access_token": "t"})
        svc.session = MagicMock()
        svc.session.get.return_value = _resp(200, {"displayName": "Ada"})
        out = svc.health_check()
        assert out["healthy"] is True
        assert "successful" in out["message"]
        assert "timestamp" in out

    def test_unhealthy(self):
        svc = TeamsService(config={"access_token": "t"})
        svc.session = MagicMock()
        svc.session.get.return_value = _resp(401)
        out = svc.health_check()
        assert out["healthy"] is False
        assert "401" in out["message"]


class TestCapabilities:
    def test_operations(self):
        caps = TeamsService(config={}).get_capabilities()
        ops = {o["id"] for o in caps["operations"]}
        assert ops == {"get_teams", "send_message"}
        assert caps["supports_webhooks"] is True


class TestExecuteOperation:
    async def test_get_teams_op(self):
        svc = TeamsService(config={"access_token": "t"})
        svc.session = MagicMock()
        svc.session.get.return_value = _resp(200, {"value": [{"id": "t1"}]})
        out = await svc.execute_operation("get_teams", {})
        assert out == {"success": True, "result": [{"id": "t1"}]}

    async def test_send_message_op(self):
        svc = TeamsService(config={"access_token": "t"})
        svc.session = MagicMock()
        svc.session.post.return_value = _resp(201, {"id": "m1"})
        out = await svc.execute_operation("send_message", {"team_id": "t1",
                                                           "channel_id": "c1",
                                                           "content": "hi"})
        assert out["success"] is True
        assert out["result"] == {"id": "m1"}

    async def test_unknown_operation(self):
        svc = TeamsService(config={})
        with pytest.raises(NotImplementedError):
            await svc.execute_operation("nope", {})
