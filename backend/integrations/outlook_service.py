import os
import json
import base64
import logging
import re
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import urllib.parse
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

# Microsoft Graph API base. MICROSOFT_GRAPH_BASE_URL overrides it for
# self-contained journey/e2e environments (same pattern as ZOHO_ACCOUNTS_BASE
# / ZOHO_DEFAULT_API_DOMAIN); unset in production the real Graph is used.
GRAPH_API_BASE = os.getenv(
    "MICROSOFT_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0"
).rstrip("/")

# Characters Graph's $search KQL rejects in free-text terms with a 400
# ("Syntax error: character '@' is not valid at position 7 in
# 'jschulz@blumetric.ca'"; live-verified 2026-09-02: '.' is rejected too —
# 'jschulz blumetric.ca' → "character '.' is not valid at position 17").
# Email addresses — usually the rarest, most selective term a mailbox
# search has — always carry '@' and a dot. Kept: word characters,
# whitespace and apostrophes (O'Brien).
_KQL_ILLEGAL = re.compile(r"[^\w\s'\"]")


def sanitize_graph_kql(query: str) -> str:
    """Make a free-text query safe for Graph $search KQL.

    'jschulz@blumetric.ca' → 'jschulz blumetric ca' — each fragment is
    tokenized against the body ('Email : jschulz@blumetric.ca'), so the
    lead email still matches. Tokens mixing letters and digits (model
    numbers, SKUs: 'WG350DSAV') are wrapped in double quotes — Graph's KQL
    parser rejects them bare ("Syntax error: character '3' is not valid at
    position 2 in 'WG350DSAV'", live 2026-09-03) but accepts them as quoted
    phrases. A query that is already legal comes back unchanged, so callers
    can cheaply up-front-sanitize every term.
    """
    if not query:
        return query

    def _quote_mixed_alnum(match: "re.Match") -> str:
        token = match.group(0)
        inner = token.strip('"')
        if inner != token:
            return token  # already quoted — leave it alone
        if re.search(r"[A-Za-z]", inner) and re.search(r"\d", inner):
            return f'"{inner}"'
        return token

    cleaned = _KQL_ILLEGAL.sub(" ", query).strip()
    return re.sub(r"\S+", _quote_mixed_alnum, cleaned)


@dataclass
class OutlookUser:
    """Outlook user profile information"""

    id: str
    display_name: str
    mail: str
    user_principal_name: str
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    business_phones: Optional[List[str]] = None
    mobile_phone: Optional[str] = None


@dataclass
class OutlookEmail:
    """Outlook email message representation"""

    id: str
    subject: str
    body_preview: str
    body: Optional[Dict[str, Any]] = None
    sender: Optional[Dict[str, Any]] = None
    from_field: Optional[Dict[str, Any]] = None
    to_recipients: Optional[List[Dict[str, Any]]] = None
    cc_recipients: Optional[List[Dict[str, Any]]] = None
    bcc_recipients: Optional[List[Dict[str, Any]]] = None
    received_date_time: Optional[str] = None
    sent_date_time: Optional[str] = None
    has_attachments: bool = False
    importance: str = "normal"
    is_read: bool = False
    web_link: Optional[str] = None
    conversation_id: Optional[str] = None
    parent_folder_id: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


@dataclass
class OutlookCalendarEvent:
    """Outlook calendar event representation"""

    id: str
    subject: str
    body: Optional[Dict[str, Any]] = None
    start: Optional[Dict[str, Any]] = None
    end: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    attendees: Optional[List[Dict[str, Any]]] = None
    organizer: Optional[Dict[str, Any]] = None
    is_all_day: bool = False
    show_as: str = "busy"
    web_link: Optional[str] = None
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None


@dataclass
class OutlookContact:
    """Outlook contact representation"""

    id: str
    display_name: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    email_addresses: Optional[List[Dict[str, Any]]] = None
    business_phones: Optional[List[str]] = None
    mobile_phone: Optional[str] = None
    home_phones: Optional[List[str]] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None


@dataclass
class OutlookTask:
    """Outlook task representation"""

    id: str
    subject: str
    body: Optional[Dict[str, Any]] = None
    importance: str = "normal"
    status: str = "notStarted"
    created_date_time: Optional[str] = None
    last_modified_date_time: Optional[str] = None
    due_date_time: Optional[Dict[str, Any]] = None
    completed_date_time: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None


@dataclass
class OutlookAttachment:
    """Outlook attachment representation"""

    id: str
    name: str
    content_type: str
    size: int
    content_bytes: Optional[str] = None
    last_modified_date_time: Optional[str] = None


class OutlookService(IntegrationService):
    """Comprehensive Outlook service for Microsoft Graph API integration"""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        """
        Initialize Outlook service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with credentials
        """
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = GRAPH_API_BASE
        self.client_id = config.get("client_id") or os.getenv("MICROSOFT_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID") or os.getenv("OUTLOOK_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("MICROSOFT_CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET") or os.getenv("OUTLOOK_CLIENT_SECRET")
        raw_tenant = config.get("tenant_id") or os.getenv("MICROSOFT_TENANT_ID") or os.getenv("AZURE_TENANT_ID") or os.getenv("OUTLOOK_TENANT_ID")
        self.tenant_id_config = raw_tenant if raw_tenant and raw_tenant not in ("default", "none", "") else "common"
        self.redirect_uri = config.get("redirect_uri") or os.getenv("OUTLOOK_REDIRECT_URI") or os.getenv("AZURE_REDIRECT_URI")
        # Populated when an operation fails for a diagnosable connection
        # reason (e.g. a consent grant that predates a newly-requested
        # scope). Callers surface it so users see "reconnect Outlook"
        # instead of a bare Graph 403.
        self.last_send_error: Optional[Dict[str, Any]] = None

    async def _get_connection_scope(self, user_id: str) -> Optional[str]:
        """The consent grant's scope string for this user's active Outlook
        token, or None when unknown (no row / no scope recorded)."""
        try:
            from core.database import get_db_session
            from core.models import IntegrationToken

            with get_db_session() as db:
                record = db.query(IntegrationToken).filter(
                    IntegrationToken.user_id == user_id,
                    IntegrationToken.provider.in_(["outlook", "microsoft"]),
                    IntegrationToken.status == "active",
                ).first()
                return (record.scope or "").strip() if record else None
        except Exception as e:
            logger.debug(f"Could not read connection scope for {user_id}: {e}")
            return None

    @staticmethod
    def _scope_grants(scope_string: str, permission: str) -> bool:
        """True when `permission` (e.g. 'Mail.Send') is in a Graph scope
        string. Entries are either bare ('mail.send') or fully qualified
        ('https://graph.microsoft.com/Mail.Send'); the check matches the
        permission name on the segment after the last '/'."""
        for entry in (scope_string or "").split():
            if entry.rsplit("/", 1)[-1].lower() == permission.lower():
                return True
        return False

    async def _get_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user from database"""
        try:
            from core.database import get_db_session
            from core.models import IntegrationToken
            from core.privsec.token_encryption import decrypt_token

            with get_db_session() as db:
                token_record = None
                placeholders = {"current", "default_user", "default", "anonymous", "guest", ""}
                if user_id and user_id not in placeholders:
                    token_record = db.query(IntegrationToken).filter(
                        IntegrationToken.user_id == user_id,
                        IntegrationToken.provider.in_(["outlook", "microsoft"]),
                        IntegrationToken.status == "active"
                    ).first()

                # No cross-user fallback: grabbing any active token would serve
                # one user's mailbox to every authenticated user. No row for
                # THIS user means not connected — callers return empty/401.

                if token_record and token_record.access_token:
                    # SQLite returns naive datetimes even for UTC-stored values;
                    # .timestamp() on a naive value interprets LOCAL time and
                    # shifted expiry by the UTC offset (4h ghost-validity on
                    # EDT hosts → 401 storms before refresh ever fired), so pin
                    # UTC before converting.
                    _expires = token_record.expires_at
                    if _expires and _expires.tzinfo is None:
                        _expires = _expires.replace(tzinfo=timezone.utc)
                    tokens = {
                        "access_token": decrypt_token(token_record.access_token, allow_plaintext=True),
                        "refresh_token": decrypt_token(token_record.refresh_token, allow_plaintext=True) if token_record.refresh_token else None,
                        "expires_at": _expires.timestamp() if _expires else None
                    }
                    if self._is_token_expired(tokens):
                        refreshed = await self._refresh_access_token(token_record.user_id or user_id, tokens)
                        return refreshed
                    return tokens["access_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting access token for user {user_id}: {e}")
            return None

    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if access token is expired"""
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return True

        try:
            if isinstance(expires_at, (int, float)):
                expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
            else:
                expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            # DB rows come back naive but are stored UTC — pin before compare
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) >= expires_dt
        except Exception:
            return True

    async def _refresh_access_token(
        self, user_id: str, tokens: Dict[str, Any]
    ) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                return None

            if not self.client_id or not self.client_secret or not self.tenant_id_config:
                logger.error(
                    f"Cannot refresh token for user {user_id}: client credentials not configured"
                )
                return None

            tenant = self.tenant_id_config if self.tenant_id_config and self.tenant_id_config not in ("default", "none", "") else (os.getenv("MICROSOFT_TENANT_ID") or "common")
            authority = os.getenv(
                "MICROSOFT_AUTHORITY_BASE", "https://login.microsoftonline.com"
            ).rstrip("/")
            url = (
                f"{authority}/{tenant}"
                "/oauth2/v2.0/token"
            )
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status != 200:
                        logger.error(f"Token refresh failed with status {response.status}")
                        return None
                    token_data = await response.json()

            new_access_token = token_data.get("access_token")
            if not new_access_token:
                logger.error("Token refresh response missing access_token")
                return None
            new_refresh_token = token_data.get("refresh_token") or refresh_token
            expires_in = token_data.get("expires_in")

            from core.database import get_db_session
            from core.models import IntegrationToken
            from core.privsec.token_encryption import encrypt_token

            with get_db_session() as db:
                # The OAuth callback fans the grant out to BOTH provider rows
                # ("outlook" + "microsoft"); refresh must update both too, or
                # the sibling "microsoft" row keeps serving an expired token.
                records = db.query(IntegrationToken).filter(
                    IntegrationToken.user_id == user_id,
                    IntegrationToken.provider.in_(["outlook", "microsoft"]),
                    IntegrationToken.status == "active",
                ).all()
                for record in records:
                    record.access_token = encrypt_token(new_access_token)
                    record.refresh_token = encrypt_token(new_refresh_token)
                    if expires_in:
                        record.expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=int(expires_in)
                        )
                if records:
                    db.commit()

            logger.info(f"Refreshed access token for user {user_id}")
            return new_access_token
        except Exception as e:
            logger.error(f"Error refreshing token for user {user_id}: {e}")
            return None

    async def _make_graph_request(
        self,
        user_id: str,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Microsoft Graph API"""
        token = access_token
        if not token:
            token = await self._get_access_token(user_id)
        
        if not token:
            logger.error(f"No access token available for user {user_id}")
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers) as response:
                        return await self._handle_response(response)
                elif method.upper() == "POST":
                    async with session.post(
                        url, headers=headers, json=data
                    ) as response:
                        return await self._handle_response(response)
                elif method.upper() == "PATCH":
                    async with session.patch(
                        url, headers=headers, json=data
                    ) as response:
                        return await self._handle_response(response)
                elif method.upper() == "DELETE":
                    async with session.delete(url, headers=headers) as response:
                        return await self._handle_response(response)
                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return None
        except Exception as e:
            logger.error(f"Graph API request failed: {e}")
            return None

    async def _handle_response(self, response) -> Optional[Dict[str, Any]]:
        """Handle API response"""
        try:
            if response.status in (200, 201, 202):
                # 202 Accepted is the documented success response for
                # POST /me/sendMail (no body is returned).
                return await response.json() if response.status != 202 else {"success": True}
            elif response.status == 204:
                return {"success": True}
            else:
                error_text = await response.text()
                logger.error(f"API request failed: {response.status} - {error_text}")
                return None
        except Exception as e:
            logger.error(f"Error handling response: {e}")
            return None

    # Email Operations
    async def get_user_emails(
        self,
        user_id: str,
        folder: str = "inbox",
        query: Optional[str] = None,
        max_results: int = 50,
        skip: int = 0,
        include_attachments: bool = False,
        token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user emails with filtering and pagination"""
        try:
            # Build query parameters
            params = {
                "$top": max_results,
                "$skip": skip,
                "$orderby": "receivedDateTime desc",
            }

            if query:
                # OData string literals escape a single quote by doubling it —
                # a raw query like "O'Brien bandsaw" would otherwise terminate
                # the literal early and 400 the whole filter.
                _safe = str(query).replace("'", "''")
                params["$filter"] = (
                    f"contains(subject, '{_safe}') or contains(body/content, '{_safe}')"
                )

            if include_attachments:
                params["$expand"] = "attachments"

            # Build endpoint
            if folder == "inbox":
                endpoint = "/me/mailFolders/inbox/messages"
            elif folder == "sent":
                endpoint = "/me/mailFolders/sentitems/messages"
            elif folder == "drafts":
                endpoint = "/me/mailFolders/drafts/messages"
            else:
                endpoint = "/me/messages"

            if params:
                query_string = urllib.parse.urlencode(params)
                endpoint = f"{endpoint}?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                emails = []
                for email_data in result["value"]:
                    email = OutlookEmail(
                        id=email_data.get("id"),
                        subject=email_data.get("subject", "No Subject"),
                        body_preview=email_data.get("bodyPreview", ""),
                        body=email_data.get("body"),
                        sender=email_data.get("sender"),
                        from_field=email_data.get("from"),
                        to_recipients=email_data.get("toRecipients", []),
                        cc_recipients=email_data.get("ccRecipients", []),
                        bcc_recipients=email_data.get("bccRecipients", []),
                        received_date_time=email_data.get("receivedDateTime"),
                        sent_date_time=email_data.get("sentDateTime"),
                        has_attachments=email_data.get("hasAttachments", False),
                        importance=email_data.get("importance", "normal"),
                        is_read=email_data.get("isRead", False),
                        web_link=email_data.get("webLink"),
                        conversation_id=email_data.get("conversationId"),
                        parent_folder_id=email_data.get("parentFolderId"),
                        attachments=email_data.get("attachments"),
                    )
                    emails.append(asdict(email))
                return emails

            return []
        except Exception as e:
            logger.error(f"Error getting user emails: {e}")
            return []

    _HTML_TAG_RE = re.compile(
        r"<\s*/?\s*(p|br|div|span|ul|ol|li|h[1-6]|hr|table|thead|tbody|tr|td|th|"
        r"a|b|i|strong|em|u|font)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _body_to_html(body: str) -> str:
        """Plain text → HTML for Graph's /me/sendMail.

        The payload is ALWAYS declared contentType "HTML", but every caller
        passes editor/textarea text — newlines collapse into one blob in
        Outlook (observed 2026-09-01: a multi-line draft arrived as a wall
        of text). Conversion is LINE-AWARE so a plain-text draft with a
        styled HTML signature appended (CanvasPanel applySignature) keeps
        both: lines containing HTML tags pass through verbatim, plain lines
        are escaped and joined with <br>.
        """
        import html as _html

        text = str(body or "")
        # Multi-line HTML (agent-drafted tables pretty-print one tag per
        # line) must be re-joined at tag boundaries BEFORE the line-aware
        # pass — <br> fragments between <table>/<tr>/<td> elements break the
        # table out of its own structure at render (same incident class as
        # the composer's toDisplayHtml, observed live 2026-09-03).
        text = re.sub(r">\s*\n\s*<", "><", text)
        lines = text.splitlines()
        if not any(OutlookService._HTML_TAG_RE.search(ln) for ln in lines):
            escaped = _html.escape(text)
            return "<br>".join(escaped.splitlines()) or escaped
        converted = [
            ln if OutlookService._HTML_TAG_RE.search(ln) else _html.escape(ln)
            for ln in lines
        ]
        return "<br>".join(converted)

    async def send_email(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        token: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send email via Outlook"""
        self.last_send_error = None
        try:
            # Consent check before the wire call: /me/sendMail needs the
            # Mail.Send delegated permission, which is SEPARATE from
            # Mail.ReadWrite. Tokens minted before Mail.Send was added to
            # the OAuth request (refreshes never expand scopes) got Graph
            # 403 ErrorAccessDenied with no hint why. Fail fast with the
            # reconnect instruction instead. Skipped when the caller passed
            # an explicit token (scope unknown) or the grant string is
            # absent (legacy rows — let Graph decide).
            if not token:
                scope_string = await self._get_connection_scope(user_id)
                if scope_string and not self._scope_grants(scope_string, "Mail.Send"):
                    logger.error(
                        f"Outlook send blocked for {user_id}: consent grant is missing "
                        f"Mail.Send (scope: {scope_string}) — reconnect Outlook to fix"
                    )
                    self.last_send_error = {
                        "error": (
                            "Your Outlook connection is missing the Mail.Send permission. "
                            "Reconnect Outlook in Settings → Integrations to grant it, "
                            "then send again."
                        ),
                        "needs_reconnect": True,
                        "missing_scope": "Mail.Send",
                    }
                    return None

            # Prepare recipients
            to_recipients_data = [
                {"emailAddress": {"address": email}} for email in to_recipients
            ]
            cc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (cc_recipients or [])
            ]
            bcc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
            ]

            valid_attachments = self._normalize_send_attachments(attachments)
            if valid_attachments is None:
                self.last_send_error = {
                    "error": "One or more attachments are missing file content.",
                }
                return None

            if valid_attachments:
                return await self._send_with_attachments(
                    user_id,
                    subject,
                    body,
                    to_recipients_data,
                    cc_recipients_data,
                    bcc_recipients_data,
                    valid_attachments,
                    access_token=token,
                )

            email_data = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML",
                             "content": self._body_to_html(body)},
                    "toRecipients": to_recipients_data,
                    "ccRecipients": cc_recipients_data,
                    "bccRecipients": bcc_recipients_data,
                },
                "saveToSentItems": True,
            }

            result = await self._make_graph_request(
                user_id, "/me/sendMail", "POST", email_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return None

    # /me/sendMail with inline attachments is rejected by Graph above ~3 MB
    # total; anything larger must go draft → createUploadSession → send.
    GRAPH_INLINE_ATTACHMENT_LIMIT = 3 * 1024 * 1024
    # Upload-session chunk sizes must be multiples of 320 KiB (Graph requirement).
    GRAPH_UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024

    @staticmethod
    def _normalize_send_attachments(
        attachments: Optional[List[Dict[str, Any]]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Validate attachment dicts, resolving bytes from `content_bytes` or `content_bytes_b64`.

        Returns None when an entry carries neither (caller signals failure),
        empty list when no attachments were requested.
        """
        if not attachments:
            return []
        resolved = []
        for att in attachments:
            data = att.get("content_bytes")
            if data is None and att.get("content_bytes_b64"):
                try:
                    data = base64.b64decode(att["content_bytes_b64"])
                except Exception:
                    data = None
            if not data or not att.get("filename"):
                return None
            resolved.append(
                {
                    "filename": att["filename"],
                    "content_type": att.get("content_type") or "application/octet-stream",
                    "content_bytes": bytes(data),
                }
            )
        return resolved

    async def _upload_large_attachment(
        self,
        user_id: str,
        draft_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        access_token: Optional[str],
    ) -> bool:
        """Attach one oversized file via a Graph upload session.

        The uploadUrl returned by createUploadSession is pre-authenticated
        (PUT goes to outlook.office.com without a Bearer header).
        """
        try:
            session = await self._make_graph_request(
                user_id,
                f"/me/messages/{draft_id}/attachments/createUploadSession",
                "POST",
                {
                    "AttachmentItem": {
                        "attachmentType": "file",
                        "name": filename,
                        "size": len(data),
                        "contentType": content_type,
                    }
                },
                access_token=access_token,
            )
            upload_url = (session or {}).get("uploadUrl")
            if not upload_url:
                logger.error(f"Graph createUploadSession returned no uploadUrl for {filename}")
                return False

            total = len(data)
            offset = 0
            async with aiohttp.ClientSession() as http:
                while offset < total:
                    chunk = data[offset : offset + self.GRAPH_UPLOAD_CHUNK_SIZE]
                    end = offset + len(chunk) - 1
                    headers = {
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {offset}-{end}/{total}",
                    }
                    async with http.put(upload_url, data=chunk, headers=headers) as resp:
                        if resp.status not in (200, 201):
                            body = await resp.text()
                            logger.error(
                                f"Graph upload chunk failed for {filename}: "
                                f"{resp.status} - {body[:300]}"
                            )
                            return False
                    offset += len(chunk)
            return True
        except Exception as e:
            logger.error(f"Error uploading attachment {filename}: {e}")
            return False

    async def _send_with_attachments(
        self,
        user_id: str,
        subject: str,
        body: str,
        to_recipients_data: List[Dict[str, Any]],
        cc_recipients_data: List[Dict[str, Any]],
        bcc_recipients_data: List[Dict[str, Any]],
        attachments: List[Dict[str, Any]],
        access_token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send via draft + attachments + send (handles >3 MB via upload sessions)."""
        draft = await self._make_graph_request(
            user_id,
            "/me/messages",
            "POST",
            {
                "subject": subject,
                "body": {"contentType": "HTML", "content": self._body_to_html(body)},
                "toRecipients": to_recipients_data,
                "ccRecipients": cc_recipients_data,
                "bccRecipients": bcc_recipients_data,
            },
            access_token=access_token,
        )
        draft_id = (draft or {}).get("id")
        if not draft_id:
            self.last_send_error = {"error": "Outlook draft creation failed (attachment send)."}
            return None

        for att in attachments:
            data = att["content_bytes"]
            if len(data) <= self.GRAPH_INLINE_ATTACHMENT_LIMIT:
                payload = {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att["filename"],
                    "contentType": att["content_type"],
                    "contentBytes": base64.b64encode(data).decode(),
                }
                attached = await self._make_graph_request(
                    user_id,
                    f"/me/messages/{draft_id}/attachments",
                    "POST",
                    payload,
                    access_token=access_token,
                )
            else:
                attached = await self._upload_large_attachment(
                    user_id,
                    draft_id,
                    att["filename"],
                    att["content_type"],
                    data,
                    access_token,
                )
            if not attached:
                self.last_send_error = {
                    "error": f"Outlook rejected attachment '{att['filename']}'.",
                    "failed_attachment": att["filename"],
                }
                await self._make_graph_request(
                    user_id, f"/me/messages/{draft_id}", "DELETE", access_token=access_token
                )
                return None

        sent = await self._make_graph_request(
            user_id, f"/me/messages/{draft_id}/send", "POST", {}, access_token=access_token
        )
        if not sent:
            self.last_send_error = {"error": "Outlook send failed after attaching files."}
        return sent

    async def get_latest_conversation_message_id(
        self,
        user_id: str,
        conversation_id: str,
        token: Optional[str] = None,
        prefer_external_sender: bool = True,
    ) -> Optional[str]:
        """Resolve an Outlook conversationId to the id of the message a
        reply should anchor to. Graph /reply needs a message id, but
        ingested/searched threads surface a conversationId — this is the
        bridge.

        The anchor prefers the newest message from OUTSIDE the user's own
        domain: customer threads routinely carry internal legs (colleague
        notes in the same conversation), and rooting the reply's
        In-Reply-To/References in an internal message is the classic
        mixed-thread mistake (observed live 2026-09-04 — a customer reply
        anchored on an internal colleague's note). Internal-only threads
        fall back to the newest message overall.

        The newest-message sort happens client-side: Graph rejects a
        conversationId $filter combined with $orderby (400 InefficientFilter,
        observed live 2026-09-04 — it failed for EVERY conversation, making
        every threaded reply send fail with "thread not found")."""
        try:
            params = {
                "$filter": f"conversationId eq '{conversation_id}'",
                "$top": 50,
                "$select": "id,conversationId,receivedDateTime,from",
            }
            endpoint = (
                "/me/messages?" + urllib.parse.urlencode(params)
            )
            result = await self._make_graph_request(
                user_id, endpoint, access_token=token
            )
            value = (result or {}).get("value") or []
            if not value:
                return None
            if prefer_external_sender:
                own_domain = None
                try:
                    profile = await self.get_user_profile(user_id, token=token)
                    for key in ("mail", "userPrincipalName"):
                        own_domain = self._email_domain(
                            str((profile or {}).get(key) or "")
                        )
                        if own_domain:
                            break
                except Exception:
                    own_domain = None
                if own_domain:
                    external = [
                        m for m in value
                        if self._sender_domain(m) not in (None, own_domain)
                    ]
                    if external:
                        value = external
            # receivedDateTime is ISO-8601 UTC, so lexicographic order is
            # chronological order.
            value.sort(
                key=lambda m: str(m.get("receivedDateTime") or ""), reverse=True
            )
            return value[0].get("id")
        except Exception as e:
            logger.error(f"Error resolving conversation {conversation_id}: {e}")
            return None

    @staticmethod
    def _email_domain(addr: str) -> Optional[str]:
        if not addr or "@" not in addr:
            return None
        return addr.strip().rpartition("@")[2].lower() or None

    @classmethod
    def _sender_domain(cls, message: Dict[str, Any]) -> Optional[str]:
        addr = str(
            (((message or {}).get("from") or {}).get("emailAddress") or {}).get("address") or ""
        )
        return cls._email_domain(addr)

    async def reply_to_email(
        self,
        user_id: str,
        message_id: str,
        comment: str,
        reply_all: bool = False,
        to_recipients: Optional[List[str]] = None,
        cc_recipients: Optional[List[str]] = None,
        subject: Optional[str] = None,
        token: Optional[str] = None,
        override_internal_quote: bool = False,
    ) -> bool:
        """Reply to an email via Outlook. ``reply_all`` targets /replyAll so
        the whole thread stays on the message instead of only the sender.
        ``to_recipients``/``cc_recipients``/``subject`` ride the reply's
        ``message`` override so a caller that shows editable fields (the
        composer) keeps the user's edits while the reply still lands in
        the original thread (Graph adds In-Reply-To/References itself).

        Mixed-thread leak guard: when the reply reaches an external
        recipient, a body quoting text that exists only on the thread's
        INTERNAL legs is refused (``policy: internal_thread_quote``) —
        colleague notes riding a customer conversation must not reach the
        customer. ``override_internal_quote=True`` sends anyway; callers
        surface it as an explicit human decision. Internal-audience
        replies are never gated."""
        self.last_send_error = None
        if not override_internal_quote:
            try:
                flagged, audience_external = await self._internal_thread_quotes(
                    user_id, message_id, comment,
                    to_recipients=to_recipients,
                    cc_recipients=cc_recipients,
                    token=token,
                )
            except Exception as e:
                logger.warning(f"internal-thread quote check skipped: {e}")
                flagged, audience_external = [], False
            if flagged:
                first = flagged[0]
                snippet = str(first.get("text", ""))[:120]
                tier = first.get("match", "verbatim")
                self.last_send_error = {
                    "error": (
                        "Reply quotes internal-only discussion from this "
                        f"thread ({len(flagged)} passage(s), e.g. \"{snippet}\" "
                        f"[{tier}]). Remove it, or resend with the internal-quote "
                        "override."
                    ),
                    "policy": "internal_thread_quote",
                    "quotes": flagged,
                }
                logger.error(
                    f"Outlook reply blocked for {user_id}: internal_thread_quote "
                    f"({len(flagged)} fragment(s))"
                )
                return False
        try:
            overrides: Dict[str, Any] = {}
            if to_recipients:
                overrides["toRecipients"] = [
                    {"emailAddress": {"address": email}} for email in to_recipients
                ]
            if cc_recipients:
                overrides["ccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in cc_recipients
                ]
            if subject:
                overrides["subject"] = subject

            # HTML replies: /reply's `comment` param is plain text — styled
            # bodies (signature HTML, tables, links) arrive as literal tags
            # in Outlook. Route tag-bearing comments through createReply →
            # PATCH the draft's HTML body → send; plain comments keep the
            # one-shot path. Falls back to the legacy path on any step
            # failure so styling never costs the send itself.
            if self._HTML_TAG_RE.search(str(comment or "")):
                sent = await self._send_html_reply(
                    user_id, message_id, comment, overrides,
                    reply_all=reply_all, access_token=token,
                )
                if sent is not None:
                    return sent
            reply_data: Dict[str, Any] = {
                "comment": comment
            }
            if overrides:
                reply_data["message"] = overrides
            action = "replyAll" if reply_all else "reply"
            result = await self._make_graph_request(
                user_id, f"/me/messages/{message_id}/{action}", "POST", reply_data, access_token=token
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error replying to email: {e}")
            return False

    async def _send_html_reply(
        self,
        user_id: str,
        message_id: str,
        comment: str,
        overrides: Dict[str, Any],
        reply_all: bool = False,
        access_token: Optional[str] = None,
    ) -> Optional[bool]:
        """createReply → PATCH the draft's HTML body (+ recipient/subject
        overrides) → send. Returns None to signal "fall back to the legacy
        comment path" when any step fails; True/False when the reply was
        (not) sent via this route."""
        try:
            action = "replyAll" if reply_all else "reply"
            draft = await self._make_graph_request(
                user_id, f"/me/messages/{message_id}/{action}", "POST",
                {}, access_token=access_token,
            )
            draft_id = (draft or {}).get("id")
            if not draft_id:
                return None
            patch: Dict[str, Any] = {
                "body": {"contentType": "HTML",
                         "content": self._body_to_html(comment)},
            }
            if overrides:
                patch.update(overrides)
            patched = await self._make_graph_request(
                user_id, f"/me/messages/{draft_id}", "PATCH",
                patch, access_token=access_token,
            )
            if patched is None:
                return None
            sent = await self._make_graph_request(
                user_id, f"/me/messages/{draft_id}/send", "POST",
                {}, access_token=access_token,
            )
            return sent is not None
        except Exception as e:
            logger.warning(f"HTML reply route failed for {user_id}: {e} — falling back")
            return None

    async def _thread_embed(self, texts: List[str]) -> List[List[float]]:
        """Embedder for the leak guard's semantic tier, cached process-wide —
        the fastembed model loads once, not per send."""
        svc = getattr(OutlookService, "_cached_embedding_service", None)
        if svc is None:
            from core.embedding_service import EmbeddingService

            svc = EmbeddingService()
            OutlookService._cached_embedding_service = svc
        return await svc.generate_embeddings_batch(texts)

    async def _internal_thread_quotes(
        self,
        user_id: str,
        message_id: str,
        comment: str,
        to_recipients: Optional[List[str]] = None,
        cc_recipients: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> tuple:
        """(internal-only fragments the reply body quotes, whether the
        effective audience reaches outside the user's own domain)."""
        from core.email_policy import find_internal_quotes

        anchor = await self._make_graph_request(
            user_id,
            f"/me/messages/{message_id}"
            "?$select=conversationId,from,toRecipients,ccRecipients",
            access_token=token,
        )
        if not anchor:
            return [], False
        conversation_id = anchor.get("conversationId")

        explicit = [
            str(addr or "").strip()
            for addr in list(to_recipients or []) + list(cc_recipients or [])
            if str(addr or "").strip()
        ]
        if explicit:
            audience = explicit
        else:
            # No recipient overrides: Graph replies go to the anchor
            # message's sender (reply) or its full recipient set (replyAll).
            audience = [self._address_of(anchor.get("from"))] + [
                self._address_of(r)
                for r in list(anchor.get("toRecipients") or [])
                + list(anchor.get("ccRecipients") or [])
            ]
        own_domain = None
        try:
            profile = await self.get_user_profile(user_id, token=token)
            for key in ("mail", "userPrincipalName"):
                own_domain = self._email_domain(str((profile or {}).get(key) or ""))
                if own_domain:
                    break
        except Exception:
            own_domain = None
        audience_external = any(
            self._email_domain(addr) not in (None, own_domain)
            for addr in audience
            if addr
        )
        if not audience_external or not conversation_id:
            return [], audience_external

        legs = await self.get_conversation_leg_texts(
            user_id, conversation_id, token=token
        )
        if not legs.get("internal"):
            return [], audience_external
        return (
            await find_internal_quotes(
                comment, legs.get("internal") or [], legs.get("external") or [],
                embed_fn=self._thread_embed,
            ),
            audience_external,
        )

    @staticmethod
    def _address_of(entry: Any) -> str:
        return str(
            ((entry or {}).get("emailAddress") or {}).get("address") or ""
        ).strip()

    async def get_conversation_leg_texts(
        self,
        user_id: str,
        conversation_id: str,
        token: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Bodies of a conversation split into customer-visible vs internal-
        only text. Pagination follows @odata.nextLink so long threads are
        fully covered (hard cap 200 messages — a guard, not an archive).

        External senders are customer-visible — and so is our OWN mail
        addressed to an external recipient (quoting your previous reply to
        the customer is normal, not a leak). Only own-domain messages with
        no external recipients are true internal notes."""
        own_domain = None
        try:
            profile = await self.get_user_profile(user_id, token=token)
            for key in ("mail", "userPrincipalName"):
                own_domain = self._email_domain(str((profile or {}).get(key) or ""))
                if own_domain:
                    break
        except Exception:
            own_domain = None
        if not own_domain:
            return {"internal": [], "external": []}
        params = {
            "$filter": f"conversationId eq '{conversation_id}'",
            "$top": 50,
            "$select": "from,toRecipients,ccRecipients,receivedDateTime,body",
        }
        url = "/me/messages?" + urllib.parse.urlencode(params)
        messages: List[Dict[str, Any]] = []
        for _page in range(4):
            result = await self._make_graph_request(user_id, url, access_token=token)
            messages.extend((result or {}).get("value") or [])
            next_link = str((result or {}).get("@odata.nextLink") or "")
            if not next_link:
                break
            # nextLink is absolute; the client wants base-relative endpoints.
            if next_link.startswith(self.base_url):
                url = next_link[len(self.base_url):]
            else:
                parts = urllib.parse.urlsplit(next_link)
                path = parts.path
                for prefix in ("/v1.0", "/beta"):
                    if path.startswith(prefix):
                        path = path[len(prefix):]
                        break
                url = path + ("?" + parts.query if parts.query else "")
        legs: Dict[str, List[str]] = {"internal": [], "external": []}
        for message in (result or {}).get("value") or []:
            body = str(((message.get("body") or {}).get("content")) or "")
            if not body:
                continue
            domain = self._sender_domain(message)
            if not domain:
                continue
            recipients = [
                self._address_of(r)
                for r in list(message.get("toRecipients") or [])
                + list(message.get("ccRecipients") or [])
            ]
            recipient_external = any(
                self._email_domain(addr) not in (None, own_domain)
                for addr in recipients
                if addr
            )
            if domain != own_domain or recipient_external:
                legs["external"].append(body)
            else:
                legs["internal"].append(body)
        return legs

    async def create_draft_email(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create draft email"""
        try:
            # Prepare recipients
            to_recipients_data = [
                {"emailAddress": {"address": email}} for email in to_recipients
            ]
            cc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (cc_recipients or [])
            ]
            bcc_recipients_data = [
                {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
            ]

            email_data = {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": to_recipients_data,
                "ccRecipients": cc_recipients_data,
                "bccRecipients": bcc_recipients_data,
            }

            result = await self._make_graph_request(
                user_id, "/me/messages", "POST", email_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating draft email: {e}")
            return None

    async def get_email_by_id(
        self, user_id: str, email_id: str, token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get specific email by ID"""
        try:
            result = await self._make_graph_request(user_id, f"/me/messages/{email_id}", access_token=token)
            if result:
                email = OutlookEmail(
                    id=result.get("id"),
                    subject=result.get("subject", "No Subject"),
                    body_preview=result.get("bodyPreview", ""),
                    body=result.get("body"),
                    sender=result.get("sender"),
                    from_field=result.get("from"),
                    to_recipients=result.get("toRecipients", []),
                    cc_recipients=result.get("ccRecipients", []),
                    bcc_recipients=result.get("bccRecipients", []),
                    received_date_time=result.get("receivedDateTime"),
                    sent_date_time=result.get("sentDateTime"),
                    has_attachments=result.get("hasAttachments", False),
                    importance=result.get("importance", "normal"),
                    is_read=result.get("isRead", False),
                    web_link=result.get("webLink"),
                    conversation_id=result.get("conversationId"),
                    parent_folder_id=result.get("parentFolderId"),
                )
                return asdict(email)
            return None
        except Exception as e:
            logger.error(f"Error getting email by ID: {e}")
            return None

    async def delete_email(self, user_id: str, email_id: str, token: Optional[str] = None) -> bool:
        """Delete email by ID"""
        try:
            result = await self._make_graph_request(
                user_id, f"/me/messages/{email_id}", "DELETE", access_token=token
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False

    async def get_attachment_content(
        self, user_id: str, message_id: str, attachment_id: str, token: Optional[str] = None
    ) -> Optional[bytes]:
        """Fetch attachment content for an email"""
        try:
            endpoint = f"/me/messages/{message_id}/attachments/{attachment_id}"
            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "contentBytes" in result:
                import base64

                return base64.b64decode(result["contentBytes"])

            logger.error(
                f"Failed to fetch content for attachment {attachment_id} in message {message_id}"
            )
            return None
        except Exception as e:
            logger.error(f"Error getting attachment content: {e}")
            return None

    async def get_attachment_metadata(
        self, user_id: str, message_id: str, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Attachment metadata normalized to the same schema as
        GmailService.get_attachment_metadata (id/name/size/contentType) —
        core.ingestion_pipeline's attachment branch dispatches on these names."""
        try:
            endpoint = (
                f"/me/messages/{message_id}/attachments"
                "?$select=id,name,size,contentType,isInline"
            )
            result = await self._make_graph_request(user_id, endpoint, access_token=token)
            if not result:
                return []
            return [
                {
                    "id": att.get("id"),
                    "name": att.get("name", "unknown"),
                    "size": att.get("size", 0),
                    "contentType": att.get("contentType", ""),
                    "isInline": att.get("isInline", False),
                }
                for att in result.get("value", [])
                if att.get("id")
            ]
        except Exception as e:
            logger.error(f"Error getting attachment metadata for message {message_id}: {e}")
            return []

    async def download_attachment(
        self, user_id: str, message_id: str, attachment_id: str, token: Optional[str] = None
    ) -> Optional[bytes]:
        """Download attachment content as bytes (normalized pipeline interface)."""
        return await self.get_attachment_content(
            user_id=user_id, message_id=message_id, attachment_id=attachment_id, token=token
        )

    # Calendar Operations
    async def get_calendar_events(
        self,
        user_id: str,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 50,
        token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get calendar events with time range filtering"""
        try:
            # Build query parameters
            params = {"$top": max_results, "$orderby": "start/dateTime"}

            if time_min and time_max:
                params["$filter"] = (
                    f"start/dateTime ge '{time_min}' and end/dateTime le '{time_max}'"
                )
            elif time_min:
                params["$filter"] = f"start/dateTime ge '{time_min}'"
            elif time_max:
                params["$filter"] = f"end/dateTime le '{time_max}'"

            if params:
                query_string = urllib.parse.urlencode(params)
                endpoint = f"/me/events?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                events = []
                for event_data in result["value"]:
                    event = OutlookCalendarEvent(
                        id=event_data.get("id"),
                        subject=event_data.get("subject", "No Subject"),
                        body=event_data.get("body"),
                        start=event_data.get("start"),
                        end=event_data.get("end"),
                        location=event_data.get("location"),
                        attendees=event_data.get("attendees", []),
                        organizer=event_data.get("organizer"),
                        is_all_day=event_data.get("isAllDay", False),
                        show_as=event_data.get("showAs", "busy"),
                        web_link=event_data.get("webLink"),
                        created_date_time=event_data.get("createdDateTime"),
                        last_modified_date_time=event_data.get("lastModifiedDateTime"),
                    )
                    events.append(asdict(event))
                return events

            return []
        except Exception as e:
            logger.error(f"Error getting calendar events: {e}")
            return []

    async def create_calendar_event(
        self,
        user_id: str,
        subject: str,
        body: Optional[str] = None,
        start: Optional[Dict[str, Any]] = None,
        end: Optional[Dict[str, Any]] = None,
        location: Optional[Dict[str, Any]] = None,
        attendees: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create calendar event"""
        try:
            event_data = {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body or ""},
                "start": start
                or {"dateTime": datetime.now(timezone.utc).isoformat(), "timeZone": "UTC"},
                "end": end
                or {
                    "dateTime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                    "timeZone": "UTC",
                },
            }

            if location:
                event_data["location"] = location

            if attendees:
                event_data["attendees"] = [
                    {"emailAddress": {"address": email}} for email in attendees
                ]

            result = await self._make_graph_request(
                user_id, "/me/events", "POST", event_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return None

    async def update_calendar_event(
        self,
        user_id: str,
        event_id: str,
        event_data: Dict[str, Any],
        token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update calendar event"""
        try:
            result = await self._make_graph_request(
                user_id, f"/me/events/{event_id}", "PATCH", event_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error updating calendar event: {e}")
            return None

    # Contact Operations
    async def get_user_contacts(
        self, user_id: str, query: Optional[str] = None, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user contacts with optional search"""
        try:
            # Build query parameters
            params = {"$top": max_results, "$orderby": "displayName"}

            if query:
                params["$filter"] = (
                    f"contains(displayName, '{query}') or contains(givenName, '{query}') or contains(surname, '{query}')"
                )

            if params:
                query_string = urllib.parse.urlencode(params)
                endpoint = f"/me/contacts?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                contacts = []
                for contact_data in result["value"]:
                    contact = OutlookContact(
                        id=contact_data.get("id"),
                        display_name=contact_data.get("displayName", "Unknown"),
                        given_name=contact_data.get("givenName"),
                        surname=contact_data.get("surname"),
                        email_addresses=contact_data.get("emailAddresses", []),
                        business_phones=contact_data.get("businessPhones", []),
                        mobile_phone=contact_data.get("mobilePhone"),
                        home_phones=contact_data.get("homePhones", []),
                        company_name=contact_data.get("companyName"),
                        job_title=contact_data.get("jobTitle"),
                        office_location=contact_data.get("officeLocation"),
                        created_date_time=contact_data.get("createdDateTime"),
                        last_modified_date_time=contact_data.get(
                            "lastModifiedDateTime"
                        ),
                    )
                    contacts.append(asdict(contact))
                return contacts

            return []
        except Exception as e:
            logger.error(f"Error getting user contacts: {e}")
            return []

    async def create_contact(
        self,
        user_id: str,
        display_name: str,
        given_name: Optional[str] = None,
        surname: Optional[str] = None,
        email_addresses: Optional[List[Dict[str, Any]]] = None,
        business_phones: Optional[List[str]] = None,
        company_name: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create contact"""
        try:
            contact_data = {"displayName": display_name}

            if given_name:
                contact_data["givenName"] = given_name
            if surname:
                contact_data["surname"] = surname
            if email_addresses:
                contact_data["emailAddresses"] = email_addresses
            if business_phones:
                contact_data["businessPhones"] = business_phones
            if company_name:
                contact_data["companyName"] = company_name

            result = await self._make_graph_request(
                user_id, "/me/contacts", "POST", contact_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating contact: {e}")
            return None

    # Task Operations
    async def get_user_tasks(
        self, user_id: str, status: Optional[str] = None, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user tasks with optional status filtering"""
        try:
            # Build query parameters
            params = {"$top": max_results, "$orderby": "createdDateTime desc"}

            if status:
                params["$filter"] = f"status eq '{status}'"

            if params:
                query_string = urllib.parse.urlencode(params)
                endpoint = f"/me/todo/lists/tasks/tasks?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                tasks = []
                for task_data in result["value"]:
                    task = OutlookTask(
                        id=task_data.get("id"),
                        subject=task_data.get("subject", "No Subject"),
                        body=task_data.get("body"),
                        importance=task_data.get("importance", "normal"),
                        status=task_data.get("status", "notStarted"),
                        created_date_time=task_data.get("createdDateTime"),
                        last_modified_date_time=task_data.get("lastModifiedDateTime"),
                        due_date_time=task_data.get("dueDateTime"),
                        completed_date_time=task_data.get("completedDateTime"),
                        categories=task_data.get("categories", []),
                    )
                    tasks.append(asdict(task))
                return tasks

            return []
        except Exception as e:
            logger.error(f"Error getting user tasks: {e}")
            return []

    async def create_task(
        self,
        user_id: str,
        subject: str,
        body: Optional[str] = None,
        importance: str = "normal",
        due_date_time: Optional[Dict[str, Any]] = None,
        categories: Optional[List[str]] = None,
        token: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create task"""
        try:
            task_data = {"subject": subject, "importance": importance}

            if body:
                task_data["body"] = {"contentType": "text", "content": body}

            if due_date_time:
                task_data["dueDateTime"] = due_date_time

            if categories:
                task_data["categories"] = categories

            result = await self._make_graph_request(
                user_id, "/me/todo/lists/tasks/tasks", "POST", task_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None

    # User Profile Operations
    async def get_user_profile(self, user_id: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get user profile information"""
        try:
            result = await self._make_graph_request(user_id, "/me", access_token=token)
            if result:
                user = OutlookUser(
                    id=result.get("id"),
                    display_name=result.get("displayName", "Unknown"),
                    mail=result.get("mail"),
                    user_principal_name=result.get("userPrincipalName"),
                    job_title=result.get("jobTitle"),
                    office_location=result.get("officeLocation"),
                    business_phones=result.get("businessPhones", []),
                    mobile_phone=result.get("mobilePhone"),
                )
                data = asdict(user)
                data["displayName"] = user.display_name
                data["userPrincipalName"] = user.user_principal_name
                data["jobTitle"] = user.job_title
                data["officeLocation"] = user.office_location
                data["businessPhones"] = user.business_phones or []
                data["mobilePhone"] = user.mobile_phone
                return data
            return None
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    async def get_unread_emails(
        self, user_id: str, max_results: int = 50, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get unread emails"""
        try:
            params = {
                "$top": max_results,
                "$filter": "isRead eq false",
                "$orderby": "receivedDateTime desc",
            }
            query_string = urllib.parse.urlencode(params)
            endpoint = f"/me/messages?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "value" in result:
                emails = []
                for email_data in result["value"]:
                    email = OutlookEmail(
                        id=email_data.get("id"),
                        subject=email_data.get("subject", "No Subject"),
                        body_preview=email_data.get("bodyPreview", ""),
                        body=email_data.get("body"),
                        sender=email_data.get("sender"),
                        from_field=email_data.get("from"),
                        to_recipients=email_data.get("toRecipients", []),
                        cc_recipients=email_data.get("ccRecipients", []),
                        bcc_recipients=email_data.get("bccRecipients", []),
                        received_date_time=email_data.get("receivedDateTime"),
                        sent_date_time=email_data.get("sentDateTime"),
                        has_attachments=email_data.get("hasAttachments", False),
                        importance=email_data.get("importance", "normal"),
                        is_read=email_data.get("isRead", False),
                        web_link=email_data.get("webLink"),
                        conversation_id=email_data.get("conversationId"),
                        parent_folder_id=email_data.get("parentFolderId"),
                    )
                    emails.append(asdict(email))
                return emails

            return []
        except Exception as e:
            logger.error(f"Error getting unread emails: {e}")
            return []

    async def search_emails(
        self, user_id: str, query: str, max_results: int = 50, token: Optional[str] = None,
        quote: bool = True
    ) -> List[Dict[str, Any]]:
        """Search emails across all folders.

        ``quote=True`` wraps the query as an exact phrase; ``quote=False``
        passes it through as raw KQL (space-separated terms) — what the chat
        path wants for "find this email … Name : Mark, Kellam", where the
        phrase form would never match the body's punctuation.

        When Graph rejects the query with a 400 (its KQL syntax errors on
        characters like ``@`` — live 2026-09-02: "jschulz@blumetric.ca" was
        the only term that could match the lead email, and the 400 silently
        emptied the search), the query is retried once in sanitized form.
        """
        try:
            # Graph rejects $orderby combined with $search on /me/messages —
            # results come back relevance-ranked, so ordering is simply omitted.
            params = {
                "$top": max_results,
                "$search": f'"{query}"' if quote else query,
            }
            query_string = urllib.parse.urlencode(params)
            endpoint = f"/me/messages?{query_string}"

            result = await self._make_graph_request(user_id, endpoint, access_token=token)
            if result is None:
                sanitized = sanitize_graph_kql(query)
                if sanitized and sanitized != query:
                    params["$search"] = f'"{sanitized}"' if quote else sanitized
                    endpoint = f"/me/messages?{urllib.parse.urlencode(params)}"
                    result = await self._make_graph_request(
                        user_id, endpoint, access_token=token
                    )

            if result and "value" in result:
                emails = []
                for email_data in result["value"]:
                    email = OutlookEmail(
                        id=email_data.get("id"),
                        subject=email_data.get("subject", "No Subject"),
                        body_preview=email_data.get("bodyPreview", ""),
                        body=email_data.get("body"),
                        sender=email_data.get("sender"),
                        from_field=email_data.get("from"),
                        to_recipients=email_data.get("toRecipients", []),
                        cc_recipients=email_data.get("ccRecipients", []),
                        bcc_recipients=email_data.get("bccRecipients", []),
                        received_date_time=email_data.get("receivedDateTime"),
                        sent_date_time=email_data.get("sentDateTime"),
                        has_attachments=email_data.get("hasAttachments", False),
                        importance=email_data.get("importance", "normal"),
                        is_read=email_data.get("isRead", False),
                        web_link=email_data.get("webLink"),
                        conversation_id=email_data.get("conversationId"),
                        parent_folder_id=email_data.get("parentFolderId"),
                    )
                    emails.append(asdict(email))
                return emails

            return []
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Outlook integration capabilities"""
        return {
            "operations": [
                {"id": "send_email", "description": "Send email via Outlook"},
                {"id": "read_emails", "description": "Read emails from folders"},
                {"id": "create_calendar_event", "description": "Create calendar events"},
                {"id": "read_calendar", "description": "Read calendar events"},
                {"id": "create_contact", "description": "Create contacts"},
                {"id": "read_contacts", "description": "Read contacts"},
            ],
            "required_params": ["access_token"],
            "optional_params": ["folder", "max_results"],
            "rate_limits": {"requests_per_minute": 10000},
            "supports_webhooks": True,
        }

    def health_check(self) -> Dict[str, Any]:
        """Check if Outlook service is healthy"""
        try:
            return {
                "healthy": bool(self.client_id),
                "message": "Outlook service is configured" if self.client_id else "Missing client_id",
                "last_check": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "last_check": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an Outlook operation with tenant context.

        CRITICAL: Validates tenant_id from context to prevent cross-tenant access.
        """
        # Validate tenant context
        if context and "tenant_id" in context:
            if context["tenant_id"] != self.tenant_id:
                raise ValueError(f"Tenant ID mismatch: expected {self.tenant_id}, got {context['tenant_id']}")

        try:
            if operation == "send_email":
                result = await self.send_email(
                    user_id=parameters.get("user_id", self.tenant_id),
                    to_recipients=parameters["to_recipients"],
                    subject=parameters["subject"],
                    body=parameters["body"],
                    token=parameters.get("token"),
                )
                return {"success": result is not None, "result": result}

            elif operation == "read_emails":
                emails = await self.get_user_emails(
                    user_id=parameters.get("user_id", self.tenant_id),
                    folder=parameters.get("folder", "inbox"),
                    max_results=parameters.get("max_results", 50),
                    token=parameters.get("token"),
                )
                return {"success": True, "result": emails}

            elif operation == "create_calendar_event":
                result = await self.create_calendar_event(
                    user_id=parameters.get("user_id", self.tenant_id),
                    subject=parameters["subject"],
                    start=parameters.get("start"),
                    end=parameters.get("end"),
                    token=parameters.get("token"),
                )
                return {"success": result is not None, "result": result}

            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "details": f"Supported operations: send_email, read_emails, create_calendar_event",
                }

        except Exception as e:
            logger.error(f"Error executing Outlook operation {operation}: {e}")
            return {"success": False, "error": "Outlook operation failed"}
    async def sync_to_postgres_cache(self, user_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Sync Outlook analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get counts for Inbox
            inbox_res = await self._make_graph_request(user_id, "/me/mailFolders/inbox", access_token=token)
            if not inbox_res:
                return {"success": False, "error": "Failed to fetch Inbox stats"}
                
            total_messages = inbox_res.get('totalItemCount', 0)
            unread_messages = inbox_res.get('unreadItemCount', 0)
            
            # Get calendar events count (recent)
            events = await self.get_calendar_events(user_id, max_results=100, token=token)
            event_count = len(events)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("outlook_total_messages", total_messages, "count"),
                    ("outlook_unread_count", unread_messages, "count"),
                    ("outlook_event_count", event_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="outlook",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="outlook",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Outlook metrics to PostgreSQL cache for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving Outlook metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": "Failed to save Outlook metrics"}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Outlook PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Outlook PostgreSQL cache sync failed"}

    async def full_sync(self, user_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Outlook"""
        # Pipeline 1: Atom Memory
        # Triggered via outlook_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id, token)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # --- NATIVE HUB SYNC METHODS (PHASE 37) ---

    async def fetch_recent_messages(self, user_id: str, max_results: int = 50, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recent Outlook emails and ingest them into the Communication Hub pipeline"""
        from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
        
        try:
            # We use the existing get_user_emails method
            messages_list = await self.get_user_emails(user_id, max_results=max_results, token=token, include_attachments=True)
            if not messages_list:
                return []
            
            pipeline = get_ingestion_pipeline()
            # Outlook messages retrieved via get_emails are already somewhat normalized
            # but we need to match the Dict[str, Any] format the pipeline normalization expects
            
            for msg in messages_list:
                # Ingest into pipeline
                # The pipeline normalization for outlook expects body, from, to, date, etc.
                # outlook_service.get_emails returns objects that asdict turns into appropriate structures
                await pipeline.ingest_message("outlook", msg)
            
            return messages_list
        except Exception as e:
            logger.error(f"Error in fetch_recent_messages: {e}")
            return []

    async def sync_calendar_events(self, user_id: str, days_ahead: int = 7, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Sync Outlook Calendar events and ingest them into the Calendar Hub pipeline"""
        from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
        
        try:
            events = await self.get_calendar_events(user_id, max_results=100, token=token)
            if not events:
                return []
            
            pipeline = get_ingestion_pipeline()
            
            for event in events:
                # Normalize for pipeline
                # Outlook events from get_calendar_events are dictionaries
                start = event.get("start", {}).get("dateTime", "")
                end = event.get("end", {}).get("dateTime", "")
                normalized_event = {
                    "id": event.get("id"),
                    "title": event.get("subject", "No Title"),
                    "content": event.get("bodyPreview") or event.get("subject", "No Title"),
                    "sender": event.get("organizer", {}).get("emailAddress", {}).get("address"),
                    "timestamp": start,
                    "metadata": {
                        "description": event.get("bodyPreview"),
                        "location": event.get("location", {}).get("displayName"),
                        "start_time": start,
                        "end_time": end,
                        "attendees": [
                            {"email": a["emailAddress"]["address"], "name": a["emailAddress"]["name"]}
                            for a in event.get("attendees", [])
                        ],
                        "organizer": event.get("organizer", {}).get("emailAddress", {}).get("address"),
                        "tenant_id": user_id
                    }
                }
                await pipeline.ingest_message("outlook_calendar", normalized_event)
                
            return events
        except Exception as e:
            logger.error(f"Error in sync_calendar_events: {e}")
            return []

# Create a default instance for hub_sync_service compatibility
outlook_service = OutlookService("default", {})

