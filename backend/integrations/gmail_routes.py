from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.models import User

logger = logging.getLogger(__name__)

# Create router
# Auth Type: OAuth2
router = APIRouter(prefix="/api/gmail", tags=["gmail"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Gmail OAuth URL"""
    return {
        "url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=INSERT_CLIENT_ID&response_type=code&scope=https://www.googleapis.com/auth/gmail.readonly",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Gmail OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Gmail authentication successful (mock)",
        "timestamp": datetime.now().isoformat()
    }

class GmailSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"
    max_results: int = Field(default=10, ge=1, le=100)

class GmailSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    total_results: int
    timestamp: str

@router.get("/status")
async def gmail_status(user_id: str = "test_user"):
    """Get Gmail integration status"""
    return {
        "ok": True,
        "service": "gmail",
        "user_id": user_id,
        "status": "connected",
        "message": "Gmail integration is available",
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/health")
async def gmail_health():
    """Health check for Gmail service"""
    return {
        "status": "healthy",
        "service": "gmail",
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/search")
async def gmail_search(request: GmailSearchRequest):
    """Search Gmail messages"""
    logger.info(f"Searching Gmail for: {request.query}")

    mock_results = [
        {
            "id": f"msg_{i}",
            "subject": f"Email about {request.query} - Message {i}",
            "sender": f"sender{i}@example.com",
            "snippet": f"This email discusses {request.query}...",
            "date": f"2025-11-{9 - i}T10:00:00Z",
        }
        for i in range(1, request.max_results + 1)
    ]

    return GmailSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        total_results=len(mock_results),
        timestamp=datetime.now().isoformat(),
    )


async def create_gmail_draft(
    user_id: str, thread_id: Optional[str] = None, body: str = ""
) -> str:
    """Create a Gmail draft for a user (mock)."""
    return f"draft_{user_id}_{datetime.now().timestamp()}"


async def send_gmail_message(
    user_id: str, thread_id: Optional[str] = None, body: str = ""
) -> Dict[str, Any]:
    """Send a Gmail message for a user (mock)."""
    return {
        "ok": True,
        "user_id": user_id,
        "thread_id": thread_id,
        "message_id": f"msg_{user_id}_{datetime.now().timestamp()}",
    }


# ---------------------------------------------------------------------------
# Real Gmail / Calendar data for the integration page
# ---------------------------------------------------------------------------
# The Overview/Inbox/Calendar tabs derive their numbers from GET /emails and
# GET /events, which no backend route served (the Next.js proxy 404'd and the
# page silently showed 0). These hit the Gmail + Calendar APIs with the
# user-scoped unified Google token (same IntegrationToken family the Drive
# service resolves).


async def _resolve_google_token(user_id: str) -> Optional[str]:
    """User-scoped Google access token via the unified IntegrationToken store."""
    try:
        from integrations.google_drive_service import GoogleDriveService

        return await GoogleDriveService().get_access_token(user_id)
    except Exception as e:
        logger.warning(f"Gmail token resolution failed: {e}")
        return None


async def _google_get(
    client, token: str, url: str, params: Optional[Dict[str, Any]] = None
):
    """Authenticated Google API GET over a caller-owned client; (status, json-or-None)."""
    resp = await client.get(
        url, headers={"Authorization": f"Bearer {token}"}, params=params
    )
    if resp.status_code >= 400:
        try:
            err = (
                resp.json().get("error", {}).get("message")
                or resp.json().get("message")
            )
        except Exception:
            err = resp.text[:200]
        logger.warning(f"Gmail/Calendar API {resp.status_code}: {err}")
        return resp.status_code, None
    return resp.status_code, resp.json()


def _fmt_msg_time(ms: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return ""


_INVISIBLE_CHARS = "\u034f\u200b\u200c\u200d\u2060\ufeff\u00ad\u2007"


def _clean_text(value: Any) -> str:
    """Strip the junk Gmail snippets carry: invisible anti-spam characters
    (e.g. U+034F / zero-width spaces), HTML entities, and run-on whitespace."""
    import html as _html
    import re as _re

    s = str(value or "")
    s = s.translate({ord(c): None for c in _INVISIBLE_CHARS})
    s = _html.unescape(s)
    return _re.sub(r"\s+", " ", s).strip()


def _email_from_payload(full: Dict[str, Any]) -> Dict[str, Any]:
    """Gmail message resource -> the panel's email row shape."""
    headers = {}
    for h in (full.get("payload", {}).get("headers") or []):
        headers[h.get("name", "").lower()] = h.get("value", "")
    labels = full.get("labelIds") or []
    return {
        "id": full.get("id"),
        "from": _clean_text(headers.get("from", "")),
        "subject": _clean_text(headers.get("subject", "(no subject)")),
        "preview": _clean_text(full.get("snippet", "")),
        "time": _fmt_msg_time(full.get("internalDate")),
        "unread": "UNREAD" in labels,
        "important": "IMPORTANT" in labels,
        "starred": "STARRED" in labels,
    }


@router.get("/emails")
async def list_emails(
    q: str = Query(default="in:inbox", description="Gmail search query"),
    max_results: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """List real Gmail messages (defaults to the inbox)."""
    import asyncio
    import httpx

    token = await _resolve_google_token(str(current_user.id))
    if not token:
        return {"emails": [], "total": 0, "error": "not_connected"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        st, data = await _google_get(
            client,
            token,
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            {"maxResults": min(max_results, 100), "q": q},
        )
        if not data:
            return {"emails": [], "total": 0, "error": f"gmail_api_error:{st}"}

        ids = [m["id"] for m in data.get("messages", [])[:max_results]]
        # Fetch message metadata concurrently — sequential per-message calls
        # made the endpoint take tens of seconds for a full inbox.
        results = await asyncio.gather(
            *[
                _google_get(
                    client,
                    token,
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}",
                    {"format": "metadata", "metadataHeaders": ["From", "Subject"]},
                )
                for mid in ids
            ]
        )
    emails = [
        _email_from_payload(full) for st_, full in results if st_ and full
    ]
    return {"emails": emails, "total": len(emails)}


@router.get("/events")
async def list_events(
    max_results: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """List upcoming primary-calendar events."""
    import httpx

    token = await _resolve_google_token(str(current_user.id))
    if not token:
        return {"events": [], "total": 0, "error": "not_connected"}

    from datetime import timedelta, timezone

    now = datetime.now(timezone.utc)
    _url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    async with httpx.AsyncClient(timeout=30.0) as client:
        # FUTURE events only — the panel's upcoming stats/list. Past events
        # must never land in here (previously timeMin/max were swapped and the
        # upcoming bucket silently returned the previous 30 days).
        st_up, upcoming_data = await _google_get(
            client,
            token,
            _url,
            {
                "maxResults": min(max_results, 100),
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": now.isoformat(),
            },
        )
        # RECENT completed events only: last 30 days (bounded, so a huge
        # history cannot crowd the list with ancient items).
        st_past, past_data = await _google_get(
            client,
            token,
            _url,
            {
                "maxResults": min(max_results, 100),
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMax": now.isoformat(),
                "timeMin": (now - timedelta(days=30)).isoformat(),
            },
        )
    if upcoming_data is None and past_data is None:
        status = st_up or st_past
        return {"events": [], "total": 0, "error": f"calendar_api_error:{status}"}

    def _to_event(it: Dict[str, Any], completed: bool) -> Dict[str, Any]:
        start = it.get("start") or {}
        dt = start.get("dateTime") or start.get("date") or ""
        date_part = dt[:10]
        time_part = dt[11:16] if len(dt) > 10 else "All day"
        return {
            "id": it.get("id"),
            "title": it.get("summary") or "(no title)",
            "location": it.get("location") or "",
            "time": time_part,
            "date": date_part,
            "completed": completed,
        }

    # Upcoming first (ascending), then finished events newest-first.
    events = [_to_event(it, False) for it in (upcoming_data or {}).get("items", [])[:max_results]]
    past_items = (past_data or {}).get("items", [])[:max_results]
    events += [_to_event(it, True) for it in reversed(past_items)]
    return {"events": events, "total": len(events)}
