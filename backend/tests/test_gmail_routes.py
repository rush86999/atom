"""Unit tests for the Gmail integration-page endpoints in
integrations/gmail_routes.py — the pure text/time/bucketing heuristics and
the endpoint error contract (empty stays 200; upstream failures surface as
502/400, never as a success-shaped empty mailbox/calendar).

The Gmail/Calendar API is faked with httpx.MockTransport, so no network and
no credentials are touched.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import integrations.gmail_routes as gmail_routes
from integrations.gmail_routes import (
    _clean_text,
    _email_from_payload,
    _event_end_dt,
    _event_start_dt,
    _finished_events,
    _fmt_msg_time,
    _parse_dt,
    router as gmail_router,
)
from core.auth import get_current_user
from core.models import User

TESTAPP = FastAPI()
TESTAPP.include_router(gmail_router)

GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
CAL_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


# ---------------------------------------------------------------------------
# _clean_text — invisible anti-spam chars, HTML entities, whitespace runs
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_strips_invisible_chars(self):
        # U+034F (combining grapheme joiner), zero-widths, soft hyphen, BOM,
        # figure space — the junk Gmail snippets carry to defeat spam filters.
        junk = "Hi\u034f there\u200b\u200c\u200d, \u2060fri\u00adend\ufeff!\u2007"
        assert _clean_text(junk) == "Hi there, friend!"

    def test_unescapes_html_entities(self):
        assert _clean_text("Tom &amp; Jerry&#39;s &quot;deal&quot;&nbsp;ok") == (
            "Tom & Jerry's \"deal\" ok"
        )

    def test_collapses_whitespace_runs(self):
        assert _clean_text("a\n\n  b\t c  ") == "a b c"

    def test_plain_text_passthrough(self):
        assert _clean_text("Weekly sync notes") == "Weekly sync notes"

    def test_none_and_non_string(self):
        assert _clean_text(None) == ""
        assert _clean_text("") == ""
        assert _clean_text(42) == "42"


# ---------------------------------------------------------------------------
# _fmt_msg_time — epoch ms -> display string; garbage -> ""
# ---------------------------------------------------------------------------

class TestFmtMsgTime:
    def test_valid_epoch_ms(self):
        out = _fmt_msg_time(1757000000000)
        # Local-time formatting; assert the shape, not the wall clock.
        assert out and "," in out and ":" in out

    def test_garbage_returns_empty(self):
        assert _fmt_msg_time(None) == ""
        assert _fmt_msg_time("not-a-number") == ""
        assert _fmt_msg_time({}) == ""


# ---------------------------------------------------------------------------
# _email_from_payload — Gmail message resource -> panel row
# ---------------------------------------------------------------------------

class TestEmailFromPayload:
    def _msg(self, **over):
        msg = {
            "id": "abc123",
            "snippet": "Meeting\u034f notes &amp; actions",
            "internalDate": "1757000000000",
            "labelIds": ["INBOX", "UNREAD", "IMPORTANT", "STARRED"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice \u200b<alice@x.com>"},
                    {"name": "Subject", "value": "Q3\u034f plan"},
                ]
            },
        }
        msg.update(over)
        return msg

    def test_happy_path(self):
        row = _email_from_payload(self._msg())
        assert row["id"] == "abc123"
        assert row["from"] == "Alice <alice@x.com>"
        assert row["subject"] == "Q3 plan"
        assert row["preview"] == "Meeting notes & actions"
        assert row["unread"] is True
        assert row["important"] is True
        assert row["starred"] is True

    def test_missing_subject_falls_back(self):
        msg = self._msg()
        msg["payload"]["headers"] = [{"name": "From", "value": "bob@x.com"}]
        row = _email_from_payload(msg)
        assert row["subject"] == "(no subject)"

    def test_no_labels_means_all_flags_false(self):
        row = _email_from_payload(self._msg(labelIds=None))
        assert row["unread"] is False
        assert row["important"] is False
        assert row["starred"] is False


# ---------------------------------------------------------------------------
# _parse_dt / _event_start_dt / _event_end_dt — Google event time parsing
# ---------------------------------------------------------------------------

class TestParseDt:
    def test_rfc3339_with_offset_is_tz_aware(self):
        dt = _parse_dt("2026-09-04T10:00:00+05:30")
        assert dt is not None and dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 5.5 * 3600
        assert dt.astimezone(timezone.utc).strftime("%H:%M") == "04:30"

    def test_all_day_date_becomes_midnight_utc(self):
        dt = _parse_dt("2026-09-04")
        assert dt == datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)

    def test_naive_value_assumed_utc(self):
        dt = _parse_dt("2026-09-04T10:00:00")
        assert dt == datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)

    def test_empty_and_garbage(self):
        assert _parse_dt(None) is None
        assert _parse_dt("") is None
        assert _parse_dt("not-a-date") is None

    def test_end_prefers_datetime_then_date(self):
        assert _event_end_dt({"end": {"dateTime": "2026-09-04T11:00:00Z"}}) == (
            datetime(2026, 9, 4, 11, 0, tzinfo=timezone.utc)
        )
        # All-day events: exclusive next-day end date.
        assert _event_end_dt({"end": {"date": "2026-09-05"}}) == (
            datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
        )
        assert _event_end_dt({"end": None}) is None
        assert _event_end_dt({}) is None

    def test_start_falls_back_to_date(self):
        assert _event_start_dt({"start": {"date": "2026-09-04"}}) == (
            datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
        )


# ---------------------------------------------------------------------------
# _finished_events — completed-bucket membership (overlap rule)
# ---------------------------------------------------------------------------

class TestFinishedEvents:
    NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)

    def test_ended_before_now_is_finished(self):
        past = [{"end": {"dateTime": "2026-09-04T11:00:00Z"}}]
        assert _finished_events(past, self.NOW) == past

    def test_in_progress_meeting_is_not_finished(self):
        # Started 11:00, ends 13:00 — still running at 12:00; matches both
        # window queries but must stay out of the completed bucket.
        active = [{"end": {"dateTime": "2026-09-04T13:00:00Z"}}]
        assert _finished_events(active, self.NOW) == []

    def test_end_exactly_now_counts_as_finished(self):
        boundary = [{"end": {"dateTime": "2026-09-04T12:00:00Z"}}]
        assert _finished_events(boundary, self.NOW) == boundary

    def test_unparseable_end_is_excluded(self):
        assert _finished_events([{"end": {"dateTime": "garbage"}}], self.NOW) == []
        assert _finished_events([{}], self.NOW) == []

    def test_sort_by_parsed_instant_not_rfc3339_string(self):
        # 09:30-05:00 == 14:30Z is NEWER than 10:00+05:30 == 04:30Z, although
        # its raw string sorts lower — lexicographic ranking would drop it.
        older_instant = {
            "id": "b",
            "start": {"dateTime": "2026-09-04T10:00:00+05:30"},
            "end": {"dateTime": "2026-09-04T11:00:00+05:30"},
        }
        newer_instant = {
            "id": "a",
            "start": {"dateTime": "2026-09-04T09:30:00-05:00"},
            "end": {"dateTime": "2026-09-04T10:30:00-05:00"},
        }
        ranked = sorted(
            [older_instant, newer_instant],
            key=lambda it: _event_start_dt(it) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        assert [it["id"] for it in ranked] == ["a", "b"]


# ---------------------------------------------------------------------------
# Endpoint contract — fake Google API over httpx.MockTransport
# ---------------------------------------------------------------------------

def _install(monkeypatch, handler, token="tok"):
    """Route the endpoints at a faked Google API with a fake user identity."""
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(httpx, "AsyncClient", factory)

    async def fake_token(user_id):
        return token

    monkeypatch.setattr(gmail_routes, "_resolve_google_token", fake_token)
    TESTAPP.dependency_overrides[get_current_user] = lambda: User(id=1, email="t@x.com")
    return TestClient(TESTAPP)


class TestEmailsEndpoint:
    def test_no_token_is_400_not_empty_200(self, monkeypatch):
        async def no_token(user_id):
            return None

        monkeypatch.setattr(gmail_routes, "_resolve_google_token", no_token)
        TESTAPP.dependency_overrides[get_current_user] = lambda: User(id=1, email="t@x.com")
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/emails")
        assert r.status_code == 400
        assert "not connected" in r.json()["detail"]

    def test_genuinely_empty_inbox_stays_200(self, monkeypatch):
        # Google returns {} (no "messages" key) for an empty mailbox — this
        # must stay a 200 empty list, never become a 502.
        def handler(request: httpx.Request):
            assert request.url.host == "gmail.googleapis.com"
            return httpx.Response(200, json={})

        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/emails")
        assert r.status_code == 200
        assert r.json() == {"emails": [], "total": 0}

    def test_upstream_list_failure_is_502(self, monkeypatch):
        def handler(request: httpx.Request):
            return httpx.Response(403, json={"error": {"message": "API not enabled"}})

        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/emails")
        assert r.status_code == 502
        assert "403" in r.json()["detail"]

    def test_metadata_fetch_failure_is_502_never_partial(self, monkeypatch):
        # One message's metadata fetch fails — the endpoint must fail loudly
        # rather than silently return a smaller mailbox.
        def handler(request: httpx.Request):
            path = request.url.path
            if path.endswith("/messages"):
                return httpx.Response(200, json={"messages": [{"id": "m1"}, {"id": "m2"}]})
            if path.endswith("/messages/m1"):
                return httpx.Response(
                    200,
                    json={"id": "m1", "snippet": "s", "payload": {"headers": []}},
                )
            return httpx.Response(500, json={"error": {"message": "boom"}})

        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/emails")
        assert r.status_code == 502
        assert "1/2 failed" in r.json()["detail"]

    def test_rows_are_cleaned_and_capped(self, monkeypatch):
        def handler(request: httpx.Request):
            if request.url.path.endswith("/messages"):
                return httpx.Response(
                    200, json={"messages": [{"id": f"m{i}"} for i in range(3)]}
                )
            mid = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "id": mid,
                    "snippet": "body\u034f text &amp; more",
                    "internalDate": "1757000000000",
                    "labelIds": ["UNREAD"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "a@x.com"},
                            {"name": "Subject", "value": f"subj {mid}"},
                        ]
                    },
                },
            )

        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/emails?max_results=2")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["emails"][0]["subject"] == "subj m0"
        assert body["emails"][0]["preview"] == "body text & more"
        assert body["emails"][0]["unread"] is True


class TestEventsEndpoint:
    @staticmethod
    def _calendar_handler(pages, upcoming_items, fail_past=False):
        """pages: list of past-window item pages served in order."""
        calls = {"past": 0}

        def handler(request: httpx.Request):
            if request.url.host != "www.googleapis.com" or "calendar" not in request.url.path:
                return httpx.Response(404, json={})
            params = dict(request.url.params)
            if fail_past and "timeMax" in params:
                return httpx.Response(500, json={"error": {"message": "backend error"}})
            if "timeMax" in params:
                idx = calls["past"]
                calls["past"] += 1
                body = {"items": pages[idx] if idx < len(pages) else []}
                if idx + 1 < len(pages):
                    body["nextPageToken"] = f"p{idx + 1}"
                return httpx.Response(200, json=body)
            return httpx.Response(200, json={"items": upcoming_items})

        return handler

    def test_no_token_is_400(self, monkeypatch):
        async def no_token(user_id):
            return None

        monkeypatch.setattr(gmail_routes, "_resolve_google_token", no_token)
        TESTAPP.dependency_overrides[get_current_user] = lambda: User(id=1, email="t@x.com")
        with TestClient(TESTAPP) as c:
            r = c.get("/api/gmail/events")
        assert r.status_code == 400

    def test_past_leg_failure_is_502_even_when_upcoming_ok(self, monkeypatch):
        handler = self._calendar_handler([], [], fail_past=True)
        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/events")
        assert r.status_code == 502
        assert "Calendar" in r.json()["detail"]

    def test_upcoming_and_completed_assembly(self, monkeypatch):
        # Times are relative to the real clock (the endpoint anchors its
        # windows to datetime.now): one future meeting, one finished meeting,
        # one still in progress (must NOT be reported completed), one all-day
        # event from 2 days ago.
        now = datetime.now(timezone.utc)
        fmt = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        upcoming = [
            {"id": "f1", "summary": "Future sync", "location": "Zoom",
             "start": {"dateTime": fmt(now + timedelta(days=1))},
             "end": {"dateTime": fmt(now + timedelta(days=1, hours=1))}},
        ]
        past_page = [
            {"id": "d1", "summary": "Done retro",
             "start": {"dateTime": fmt(now - timedelta(days=1))},
             "end": {"dateTime": fmt(now - timedelta(days=1) + timedelta(hours=1))}},
            {"id": "live", "summary": "In progress now",
             "start": {"dateTime": fmt(now - timedelta(hours=1))},
             "end": {"dateTime": fmt(now + timedelta(hours=1))}},
            {"id": "ad", "summary": "All-day conf",
             "start": {"date": (now - timedelta(days=2)).date().isoformat()},
             "end": {"date": (now - timedelta(days=1)).date().isoformat()}},
        ]
        handler = self._calendar_handler([past_page], upcoming)
        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/events")
        assert r.status_code == 200
        events = r.json()["events"]
        by_id = {e["id"]: e for e in events}

        assert by_id["f1"]["completed"] is False
        assert by_id["f1"]["time"] == (now + timedelta(days=1)).strftime("%H:%M")
        assert by_id["d1"]["completed"] is True
        assert by_id["ad"]["completed"] is True
        assert by_id["ad"]["time"] == "All day"
        # In-progress meeting: excluded entirely (not upcoming, not completed).
        assert "live" not in by_id

    def test_completed_pagination_walks_all_pages(self, monkeypatch):
        # Oldest finished events on page 1, newest on page 2 — the endpoint
        # must follow nextPageToken and rank the NEWEST first.
        upcoming = []
        page1 = [
            {"id": "old", "summary": "Oldest",
             "start": {"dateTime": "2026-09-01T09:00:00Z"},
             "end": {"dateTime": "2026-09-01T10:00:00Z"}},
        ]
        page2 = [
            {"id": "new", "summary": "Newest",
             "start": {"dateTime": "2026-09-03T18:00:00Z"},
             "end": {"dateTime": "2026-09-03T19:00:00Z"}},
        ]
        seen_tokens = []
        calls = {"past": 0}

        def handler(request: httpx.Request):
            params = dict(request.url.params)
            if "timeMax" not in params:
                return httpx.Response(200, json={"items": upcoming})
            if "pageToken" in params:
                seen_tokens.append(params["pageToken"])
                return httpx.Response(200, json={"items": page2})
            calls["past"] += 1
            return httpx.Response(200, json={"items": page1, "nextPageToken": "next-1"})

        c = _install(monkeypatch, handler)
        with c:
            r = c.get("/api/gmail/events")
        assert r.status_code == 200
        assert seen_tokens == ["next-1"]
        events = r.json()["events"]
        assert [e["id"] for e in events if e["completed"]] == ["new", "old"]
