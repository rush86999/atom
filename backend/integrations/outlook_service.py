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

# Bare KQL operator words coming from prose must not OR/AND the query:
# "invoice OR password" used to sanitize to itself, silently widening the
# mailbox search to either word. Quoting turns them into literal terms.
_KQL_OPERATOR_WORDS = frozenset({"AND", "OR", "NOT"})

# Hard timeout for every Graph HTTP call (a bare ClientSession rides
# aiohttp's 300s default — see _make_graph_request).
_GRAPH_HTTP_TIMEOUT_SECONDS = float(
    os.getenv("OUTLOOK_GRAPH_TIMEOUT_SECONDS", "30") or 30
)

# KQL-ladder circuit breaker: consecutive rejected forms after which the
# ladder gives up, and the status classes that abort IMMEDIATELY (an
# expired/insufficient token fails every rung identically — retrying the
# ladder against it burned up to ~60 Graph round-trips per search, live
# 2026-09-13 review).
_SEARCH_LADDER_MAX_FAILURES = 3
_AUTH_FAILURE_STATUSES = (401, 403)
# Graph pages followed per search_emails_paged call when the first page
# comes back short. Bounded so a pathological nextLink chain can't loop a
# mailbox scan forever; the continuation token keeps deeper pages reachable.
_SEARCH_MAX_PAGES = 3

# ``sender=`` is interpolated into a quoted KQL clause — only a plainly
# shaped address may enter it (quotes, colons and control characters in a
# caller-supplied "address" would escape the clause; public entry points
# reach this from HTTP routes and the universal integration service).
_SENDER_ADDRESS_RE = re.compile(r"^[\w.+-]+@[\w.-]+$")

# Quoted phrases vs bare spans: phrase punctuation ($ , . – %) survives in
# phrase position (live 2026-09-12: '"$5,350.00"' as $search matches the
# Seguin quote email) — the old whole-string substitution gutted phrases
# into '" 5 350 00"', which 400'd and killed the sanitized retry too.
_KQL_SEGMENT_RE = re.compile(r'"([^"]*)"|([^"]+)')


def _quote_mixed_alnum(match: "re.Match") -> str:
    token = match.group(0)
    if token in _KQL_OPERATOR_WORDS:
        return f'"{token}"'
    if re.search(r"[A-Za-z]", token) and re.search(r"\d", token):
        return f'"{token}"'
    return token


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

    Double-quoted spans are treated as exact phrases and preserved verbatim
    (only embedded quotes/newlines stripped): '"$5,350.00"' used to become
    '" 5 350 00"' — an equally illegal query — so the 400-retry ladder in
    search_emails never had a working second rung (live 2026-09-12: the
    Seguin $5,350.00 vendor-cost email was unfetchable while sitting in
    both the mailbox and the ingested store). Bare uppercase operator words
    (AND/OR/NOT) from prose are quoted as literals — 'invoice OR password'
    must not silently OR the KQL.
    """
    if not query:
        return query

    out = []
    for match in _KQL_SEGMENT_RE.finditer(query):
        phrase, bare = match.group(1), match.group(2)
        if phrase is not None:
            inner = re.sub(r'[\r\n"]+', " ", phrase).strip()
            if inner:
                out.append(f'"{inner}"')
        else:
            cleaned = _KQL_ILLEGAL.sub(" ", bare).strip()
            if cleaned:
                out.append(re.sub(r"\S+", _quote_mixed_alnum, cleaned))
    return " ".join(out).strip()


def decompose_graph_kql(query: str) -> str:
    """Last-resort KQL form: bare word tokens, every non-word character
    (except the decimal point) removed rather than space-substituted; tokens
    containing digits are individually quoted.

    This is the ladder's final rung for queries whose punctuation Graph
    rejects even quoted — '"$ 5,350.00 – 10 % in stock"' as a phrase AND its
    sanitized form both 400 (live 2026-09-12); quoted single tokens are
    legal where the bare run is not: bare digit-leading terms 400 on this
    backend ("character '5' is not valid at position 0 in '5 350 00'", live
    2026-09-12). Never emits a multi-token phrase, so it cannot re-introduce
    phrase syntax errors. Bare operator words are quoted so prose like
    "invoice OR password" cannot silently widen the query. Empty string when
    nothing survives.
    """
    if not query:
        return ""
    tokens = re.sub(r"[^\w.]+", " ", query).split()
    return " ".join(
        f'"{t}"' if (re.search(r"\d", t) or t in _KQL_OPERATOR_WORDS) else t
        for t in tokens
    )


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

    def __init__(
        self,
        tenant_id: str = "default",
        config: Dict[str, Any] = None,
        token_row_id: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        *,
        connection_id: Optional[str] = None,
        db_bound: Optional[bool] = None,
        db_tenant_id: Optional[str] = None,
        db_workspace_id: Optional[str] = None,
        token_id: Optional[str] = None,
        integration_token_id: Optional[str] = None,
        bound_token_row_id: Optional[str] = None,
        exact_token_row_id: Optional[str] = None,
    ):
        """
        Initialize Outlook service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with credentials
            token_row_id: Opt-in exact ``integration_tokens.id`` to bind this
                connector to. When supplied, token lookup, scope checks and
                refresh all operate on that one active canonical ``outlook``
                row only.
            user_id: Exact current user for the opt-in bound connection.
            workspace_id: Exact current workspace for the opt-in bound
                connection.
            connection_id: Alias for ``token_row_id`` (the opaque connection
                id persisted by callers).
            db_bound: Explicitly enable the opt-in DB-bound connection. It is
                also enabled automatically when an exact row/connection id is
                given.
        """
        if config is None:
            config = {}
        config = dict(config)

        def _clean(value: Any) -> Optional[str]:
            text = str(value or "").strip()
            return text or None

        def _first(*values: Any) -> Optional[str]:
            for value in values:
                cleaned = _clean(value)
                if cleaned:
                    return cleaned
            return None

        # Accept the aliases from both explicit arguments and tenant config so
        # a factory/configuration caller can opt in without changing existing
        # generic call sites.
        resolved_token_row_id = _first(
            token_row_id,
            bound_token_row_id,
            exact_token_row_id,
            connection_id,
            token_id,
            integration_token_id,
            config.get("token_row_id"),
            config.get("connection_id"),
            config.get("token_id"),
            config.get("integration_token_id"),
        )
        resolved_user_id = _first(
            user_id,
            config.get("user_id"),
            config.get("current_user_id"),
        )
        resolved_workspace_id = _first(
            workspace_id,
            db_workspace_id,
            config.get("workspace_id"),
            config.get("db_workspace_id"),
        )
        resolved_db_tenant_id = _first(
            db_tenant_id,
            config.get("db_tenant_id"),
            config.get("database_tenant_id"),
        )
        if db_bound is None:
            db_bound = config.get("db_bound")
        if db_bound is None:
            db_bound = config.get("bound_connection")
        # An explicit row id is inherently an opt-in binding. Requiring both a
        # user and workspace is also treated as opt-in so the resolved identity
        # can be validated against the row; without either signal the historical
        # generic connector path is unchanged.
        bound_requested = bool(db_bound) or bool(resolved_token_row_id) or bool(
            resolved_user_id and resolved_workspace_id
        )

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
        # Set when the transport failed before any HTTP response arrived.
        # For a send this means the provider MAY have accepted the effect;
        # it is not proof of failure and must not trigger a blind resend.
        self.last_transport_error: Optional[str] = None
        # Status of the LAST _handle_response'd Graph call (None while no
        # call ran / the call failed before a response): lets retrying
        # callers (the search_emails KQL ladder) abort immediately on
        # auth-class failures instead of burning every rung.
        self.last_graph_status: Optional[int] = None
        # Typed failure from the last attachment read.  A missing grant or a
        # Graph error must not look like an email with zero attachments.
        self.last_error: Optional[Dict[str, Any]] = None
        # Opt-in DB-bound connection context. The default connector path
        # (OutlookService()/OutlookService(tenant, config)) leaves this off and
        # keeps its historical lookup/refresh behavior.
        self.db_bound: bool = bool(bound_requested)
        self._db_bound: bool = self.db_bound
        self.token_row_id: Optional[str] = resolved_token_row_id
        self.connection_id: Optional[str] = resolved_token_row_id
        self._token_row_id: Optional[str] = resolved_token_row_id
        self._bound_token_row_id: Optional[str] = resolved_token_row_id
        self.bound_user_id: Optional[str] = resolved_user_id
        self.bound_workspace_id: Optional[str] = resolved_workspace_id
        self.workspace_id: Optional[str] = resolved_workspace_id
        # ``self.tenant_id`` is the tenant half of the exact DB identity. A
        # separate db_tenant_id remains available for callers whose service
        # tenant and database tenant are intentionally named differently.
        self.db_tenant_id: Optional[str] = (
            resolved_db_tenant_id or _clean(tenant_id)
        )
        # Read-only diagnostics: never contains token material.
        self.last_token_error: Optional[str] = None
        # Invocation-scoped credential pin for the opt-in staged path. It is
        # deliberately memory-only: the validated token is reused by every
        # provider call in this invocation so a concurrent refresh of the
        # same row cannot rotate the credential between draft/create/send.
        # Generic/direct callers never set this and keep their historical
        # per-call lookup behavior.
        self._pinned_access_token: Optional[str] = None

    # ------------------------------------------------------------------
    # Opt-in DB-bound connection selection
    # ------------------------------------------------------------------

    @staticmethod
    def _binding_text(value: Any) -> str:
        return str(value or "").strip()

    def _bound_identity(
        self, user_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """The exact user/tenant/workspace this bound instance must address.

        Returns ``None`` (and records ``last_token_error``) when the identity
        is not fully specified or the caller-supplied user disagrees with the
        identity fixed at construction time.
        """
        self.last_token_error = None
        caller_user = self._binding_text(user_id)
        fixed_user = self._binding_text(self.bound_user_id)
        if fixed_user and caller_user and fixed_user != caller_user:
            self.last_token_error = "bound_user_mismatch"
            return None
        current_user = fixed_user or caller_user
        placeholders = {
            "current", "default_user", "default", "anonymous", "guest", "",
        }
        tenant_id = self._binding_text(self.db_tenant_id)
        workspace_id = self._binding_text(self.bound_workspace_id)
        if not current_user or current_user in placeholders:
            self.last_token_error = "bound_user_missing"
            return None
        if not tenant_id:
            self.last_token_error = "bound_tenant_missing"
            return None
        if not workspace_id:
            self.last_token_error = "bound_workspace_missing"
            return None
        return {
            "user_id": current_user,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        }

    def _load_bound_token_row(
        self, db: Any, user_id: Optional[str] = None
    ) -> Optional[Any]:
        """Load the one active canonical Outlook row this instance is bound to.

        The callback fans a grant out to a canonical ``outlook`` row plus a
        mirror ``microsoft`` row. This lookup deliberately addresses ONLY the
        canonical row — it never falls back to the mirror. With an exact row id
        the row is re-read by id and then every identity field (user, tenant,
        workspace, provider, active status) is revalidated. Without an id the
        exact identity must resolve to exactly one active canonical row; zero
        rows and ambiguous rows both refuse.
        """
        from core.models import IntegrationToken

        identity = self._bound_identity(user_id)
        if identity is None:
            return None

        try:
            query = db.query(IntegrationToken)
            if self.token_row_id:
                rows = query.filter(
                    IntegrationToken.id == self.token_row_id
                ).all()
            else:
                rows = query.filter(
                    IntegrationToken.user_id == identity["user_id"],
                    IntegrationToken.tenant_id == identity["tenant_id"],
                    IntegrationToken.workspace_id == identity["workspace_id"],
                    IntegrationToken.provider == "outlook",
                    IntegrationToken.status == "active",
                ).all()

            if not rows:
                self.last_token_error = "bound_token_missing"
                return None
            if len(rows) != 1:
                # PK lookup cannot be ambiguous; an identity lookup with
                # multiple active canonical rows must refuse rather than pick.
                self.last_token_error = "bound_token_ambiguous"
                return None

            record = rows[0]
            checks = (
                (self._binding_text(getattr(record, "user_id", None)),
                 identity["user_id"], "bound_token_user_mismatch"),
                (self._binding_text(getattr(record, "tenant_id", None)),
                 identity["tenant_id"], "bound_token_tenant_mismatch"),
                (self._binding_text(getattr(record, "workspace_id", None)),
                 identity["workspace_id"], "bound_token_workspace_mismatch"),
                (self._binding_text(getattr(record, "provider", None)).lower(),
                 "outlook", "bound_token_provider_mismatch"),
                (self._binding_text(getattr(record, "status", None)).lower(),
                 "active", "bound_token_inactive"),
            )
            for actual, expected, reason in checks:
                if actual != expected:
                    self.last_token_error = reason
                    return None
            if self.token_row_id and self._binding_text(
                getattr(record, "id", None)
            ) != self.token_row_id:
                self.last_token_error = "bound_token_row_mismatch"
                return None
            return record
        except Exception as e:
            logger.debug(f"Could not read bound Outlook token row: {e}")
            self.last_token_error = "bound_token_read_failed"
            return None

    @classmethod
    def resolve_connection_id(
        cls,
        *,
        user_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> Optional[str]:
        """Return the id of the single active canonical outlook token row.

        This is a read-only identity lookup for callers (the staged Canvas
        branch) that need the opaque connection id to persist. It never
        returns a ``microsoft`` mirror row and returns ``None`` for a missing
        or ambiguous identity instead of choosing one.
        """
        identity = {
            "user_id": cls._binding_text(user_id),
            "tenant_id": cls._binding_text(tenant_id),
            "workspace_id": cls._binding_text(workspace_id),
        }
        if not all(identity.values()):
            return None
        try:
            from core.database import get_db_session
            from core.models import IntegrationToken

            with get_db_session() as db:
                rows = db.query(IntegrationToken).filter(
                    IntegrationToken.user_id == identity["user_id"],
                    IntegrationToken.tenant_id == identity["tenant_id"],
                    IntegrationToken.workspace_id == identity["workspace_id"],
                    IntegrationToken.provider == "outlook",
                    IntegrationToken.status == "active",
                ).all()
                if len(rows) != 1:
                    return None
                return cls._binding_text(getattr(rows[0], "id", None)) or None
        except Exception as e:
            logger.debug(f"Could not resolve bound Outlook connection: {e}")
            return None

    @classmethod
    def for_connection(
        cls,
        connection_id: Optional[str] = None,
        *,
        token_row_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: str = "default",
        workspace_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "OutlookService":
        """Factory for the opt-in DB-bound connection.

        ``connection_id`` is the opaque ``integration_tokens.id`` persisted by
        the caller; the service revalidates that exact row on every use.
        """
        return cls(
            tenant_id=tenant_id,
            config=config,
            token_row_id=token_row_id or connection_id,
            user_id=user_id,
            workspace_id=workspace_id,
            db_bound=True,
            **kwargs,
        )

    from_token_row = for_connection
    from_connection = for_connection
    with_token_row = for_connection
    for_bound_token = for_connection
    bind_to_token = for_connection

    async def _get_connection_scope(self, user_id: str) -> Optional[str]:
        """The consent grant's scope string for this user's active Outlook
        token, or None when unknown (no row / no scope recorded)."""
        if self.db_bound:
            try:
                from core.database import get_db_session

                with get_db_session() as db:
                    record = self._load_bound_token_row(db, user_id)
                    if record is None:
                        return None
                    return (record.scope or "").strip() if record else None
            except Exception as e:
                logger.debug(
                    f"Could not read bound connection scope for {user_id}: {e}")
                return None
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
        """Get access token for user from database.

        The historical generic path is unchanged. In the opt-in DB-bound mode
        this reads ONLY the exact canonical ``outlook`` row selected/revalidated
        by ``_load_bound_token_row`` and never falls back to the mirror
        ``microsoft`` row or another user's token.
        """
        if self.db_bound:
            try:
                from core.database import get_db_session
                from core.privsec.token_encryption import decrypt_token

                with get_db_session() as db:
                    token_record = self._load_bound_token_row(db, user_id)
                    if token_record is None or not token_record.access_token:
                        return None
                    _expires = token_record.expires_at
                    if _expires and _expires.tzinfo is None:
                        _expires = _expires.replace(tzinfo=timezone.utc)
                    tokens = {
                        "access_token": decrypt_token(
                            token_record.access_token, allow_plaintext=True),
                        "refresh_token": (
                            decrypt_token(
                                token_record.refresh_token,
                                allow_plaintext=True)
                            if token_record.refresh_token else None),
                        "expires_at": (
                            _expires.timestamp() if _expires else None),
                    }
                    if self._is_token_expired(tokens):
                        return await self._refresh_access_token(
                            token_record.user_id or user_id, tokens)
                    return tokens["access_token"]
            except Exception as e:
                logger.error(
                    f"Error getting bound access token for user {user_id}: {e}")
                return None

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
        """Refresh access token using refresh token.

        The generic path keeps fanning the refreshed grant to the canonical
        ``outlook`` row and its ``microsoft`` mirror. The opt-in DB-bound path
        refreshes one exact row only.
        """
        if self.db_bound:
            return await self._refresh_bound_access_token(user_id, tokens)
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

    async def _refresh_bound_access_token(
        self, user_id: str, tokens: Dict[str, Any]
    ) -> Optional[str]:
        """Refresh only the exact active canonical row this instance is bound to.

        The row is read and revalidated before the provider call, and its
        exact credential version is preserved as a snapshot. After the
        provider call a single conditional UPDATE writes the new grant only
        if that same row is still active, still belongs to the bound
        user/tenant/workspace, and still carries the observed encrypted
        access token, refresh token and expiration. A concurrent OAuth
        reconnect therefore wins: the refresh returns ``None`` instead of
        overwriting the newer grant or handing back a token it did not store.
        No sibling ``microsoft`` row and no other user row is touched, and the
        caller-supplied ``tokens`` are never substituted for a refresh token
        that the exact row no longer has.
        """
        try:
            from core.database import get_db_session
            from core.privsec.token_encryption import decrypt_token

            with get_db_session() as db:
                record = self._load_bound_token_row(db, user_id)
                if record is None:
                    return None
                if not record.refresh_token:
                    self.last_token_error = "bound_refresh_token_missing"
                    return None
                refresh_token = decrypt_token(
                    record.refresh_token, allow_plaintext=True)
                if not refresh_token:
                    self.last_token_error = "bound_refresh_token_missing"
                    return None

                # Preserve the exact row/identity/credential version observed
                # before the provider call. Values are plain snapshots (the
                # encrypted fields are never decrypted for logging or reused
                # as a fallback).
                observed_id = getattr(record, "id", None)
                observed_user_id = self._binding_text(
                    getattr(record, "user_id", None))
                observed_tenant_id = self._binding_text(
                    getattr(record, "tenant_id", None))
                observed_workspace_id = self._binding_text(
                    getattr(record, "workspace_id", None))
                observed_access_token = record.access_token
                observed_refresh_token = record.refresh_token
                observed_expires_at = record.expires_at
                if observed_id is None:
                    self.last_token_error = "bound_token_missing"
                    return None

            if not self.client_id or not self.client_secret or not self.tenant_id_config:
                logger.error(
                    f"Cannot refresh bound token for user {user_id}: "
                    "client credentials not configured"
                )
                return None

            tenant = (
                self.tenant_id_config
                if self.tenant_id_config
                and self.tenant_id_config not in ("default", "none", "")
                else (os.getenv("MICROSOFT_TENANT_ID") or "common")
            )
            authority = os.getenv(
                "MICROSOFT_AUTHORITY_BASE", "https://login.microsoftonline.com"
            ).rstrip("/")
            url = f"{authority}/{tenant}/oauth2/v2.0/token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status != 200:
                        logger.error(
                            "Bound token refresh failed with status "
                            f"{response.status}")
                        return None
                    token_data = await response.json()

            new_access_token = token_data.get("access_token")
            if not new_access_token:
                logger.error("Bound token refresh response missing access_token")
                return None
            new_refresh_token = token_data.get("refresh_token") or refresh_token
            expires_in = token_data.get("expires_in")

            from core.models import IntegrationToken
            from core.privsec.token_encryption import encrypt_token

            values = {
                "access_token": encrypt_token(new_access_token),
                "refresh_token": encrypt_token(new_refresh_token),
            }
            if expires_in:
                values["expires_at"] = datetime.now(timezone.utc) + timedelta(
                    seconds=int(expires_in)
                )

            def _unchanged(column: Any, observed: Any) -> Any:
                # NULL is a real observed value here: a credential column that
                # was empty before the call must compare as IS NULL, not as
                # ``= NULL`` (which never matches).
                return column.is_(None) if observed is None else column == observed

            with get_db_session() as db:
                # One conditional UPDATE is the compare-and-swap: the WHERE
                # clause carries the exact row id, canonical identity and the
                # encrypted credential version observed before the HTTP call.
                # If an OAuth reconnect changed any of them while the refresh
                # was in flight, zero rows match and the newer grant survives.
                updated = db.query(IntegrationToken).filter(
                    IntegrationToken.id == observed_id,
                    IntegrationToken.provider == "outlook",
                    IntegrationToken.status == "active",
                    IntegrationToken.user_id == observed_user_id,
                    IntegrationToken.tenant_id == observed_tenant_id,
                    IntegrationToken.workspace_id == observed_workspace_id,
                    _unchanged(
                        IntegrationToken.access_token, observed_access_token),
                    _unchanged(
                        IntegrationToken.refresh_token, observed_refresh_token),
                    _unchanged(
                        IntegrationToken.expires_at, observed_expires_at),
                ).update(values, synchronize_session=False)
                if not updated:
                    self.last_token_error = "bound_token_refresh_conflict"
                    logger.info(
                        "Bound token refresh conflict for user %s; "
                        "credentials changed while refreshing", user_id)
                    return None
                db.commit()

            self.last_token_error = None
            logger.info(f"Refreshed bound access token for user {user_id}")
            return new_access_token
        except Exception as e:
            logger.error(f"Error refreshing bound token for user {user_id}: {e}")
            return None

    async def _make_graph_request(
        self,
        user_id: str,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        access_token: Optional[str] = None,
        full_url: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Microsoft Graph API

        ``full_url=True`` sends ``endpoint`` verbatim (Graph ``@odata.nextLink``
        continuation URLs — they already carry the $skiptoken and point at
        this same base_url; callers must validate the prefix, see
        ``_validated_next_link``).

        ``extra_headers`` adds per-request headers (e.g. ``Prefer``) without
        changing any existing call site. Authorization is never overridable
        through it, and the value is merged only for this one request.

        Every request carries an explicit ``aiohttp.ClientTimeout``: a bare
        ``ClientSession()`` rides aiohttp's 300s default, so one hung Graph
        call could hold a search ladder (and every budgeted lane above it)
        for five minutes (2026-09-13 review — a slow pull converted a fast
        empty search into a caller timeout long before its own budget).
        """
        token = access_token
        if not token:
            # Staged callers pin the token validated against Graph /me for
            # this invocation. Honor it before any per-call DB lookup so a
            # same-row rotation cannot swap credentials mid-effect.
            token = self._pinned_access_token
        if not token:
            token = await self._get_access_token(user_id)

        if not token:
            logger.error(f"No access token available for user {user_id}")
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(
                {
                    str(key): str(value)
                    for key, value in extra_headers.items()
                    if str(key).lower() != "authorization"
                }
            )

        url = endpoint if full_url else f"{self.base_url}{endpoint}"
        self.last_graph_status = None
        self.last_transport_error = None

        try:
            timeout = aiohttp.ClientTimeout(total=_GRAPH_HTTP_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
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
            # No HTTP response was observed. For a mutating send this is an
            # AMBIGUOUS outcome, not a confirmed failure.
            self.last_transport_error = str(e)[:300]
            return None

    async def _handle_response(self, response) -> Optional[Dict[str, Any]]:
        """Handle API response.

        The response's status class is exposed on ``self.last_graph_status``
        (reset per request) so callers that retry — the KQL ladder in
        ``search_emails`` — can distinguish an expired token (401/403: no
        rung can succeed, abort immediately) from a malformed query (400:
        next rung) instead of burning every rung against a dead token.
        """
        try:
            self.last_graph_status = response.status
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
        from core.email_send_policy import (
            disabled_result,
            live_email_send_disabled,
        )
        if live_email_send_disabled():
            self.last_send_error = disabled_result()
            return None
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
            if result is None and self.last_transport_error:
                self.last_send_error = {
                    "error": (
                        "The connection failed after the send was attempted; "
                        "the provider may have accepted it."),
                    "outcome_uncertain": True,
                    "transport_error": self.last_transport_error,
                }
            return result
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            self.last_send_error = {
                "error": (
                    "The send failed before a provider confirmation was "
                    "observed. Check the Sent folder before retrying."),
                "outcome_uncertain": True,
                "transport_error": str(e)[:300],
            }
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
            self.last_send_error = {
                "error": "Outlook send failed after attaching files.",
                "outcome_uncertain": bool(self.last_transport_error),
                "transport_error": self.last_transport_error,
            }
        return sent

    # Fields required to correlate a sent message without reading its body.
    _SENT_EVIDENCE_SELECT = (
        "id,isDraft,conversationId,internetMessageId,sentDateTime,"
        "receivedDateTime,parentFolderId"
    )
    # Ask Graph to treat the path ID as the immutable ID returned at draft
    # creation. Scoped to this request only.
    _IMMUTABLE_ID_PREFER = 'IdType="ImmutableId"'

    async def get_sent_message_evidence(
        self,
        user_id: str,
        immutable_message_id: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read back one already-known message as sent-message evidence.

        The input is the opaque immutable message ID the provider returned
        when the draft was created. This performs exactly ONE authenticated
        ``GET /me/mailFolders/sentitems/messages/{id}`` — the documented
        folder-scoped read — with ``Prefer: IdType="ImmutableId"`` and a
        ``$select`` limited to the correlation fields. The folder scope is
        required for evidence: mailbox-wide ``/me/messages/{id}`` also
        returns Inbox messages, so an Inbox non-draft was indistinguishable
        from a sent one (synthetic verification 2026-11-19). The ID is
        percent-encoded as a single path segment and compared
        case-sensitively with the provider's returned ``id`` — immutable IDs
        are opaque, so no normalization is allowed. The request uses the
        existing authenticated user lookup unless the staged caller pins an
        invocation-scoped token (``access_token``).

        A result is ``resolved`` only when the message exists as a dict, its
        ``id`` matches the requested ID exactly, ``isDraft`` is explicitly
        ``false``, and non-empty provider ``conversationId`` and
        ``internetMessageId`` values are present. Anything else (404/transport
        failure, malformed non-dict body, mismatched ID, draft, missing
        correlation fields) is ``unresolved``.

        Graph can lag when persisting a message into Sent Items, so an
        ``unresolved`` read is inconclusive, not proof that no send occurred.
        This method deliberately does not send, search by subject, or retry;
        a caller that wants a later readback issues a new call.
        """
        unresolved: Dict[str, Any] = {
            "status": "unresolved",
            "resolved": False,
            "message_id": (
                immutable_message_id
                if isinstance(immutable_message_id, str)
                else None
            ),
            "sent_items_may_be_delayed": True,
        }
        if not isinstance(immutable_message_id, str) or not immutable_message_id:
            unresolved["reason"] = "invalid_message_id"
            return unresolved

        # quote(safe="") keeps '/', '?', '#', '=' etc. inside one segment, so
        # the opaque ID cannot change the request path or query. The
        # sentitems folder scope is what makes a non-draft Inbox message
        # unresolvable: mailbox-wide /me/messages would return it.
        encoded_id = urllib.parse.quote(immutable_message_id, safe="")
        endpoint = (
            f"/me/mailFolders/sentitems/messages/{encoded_id}"
            f"?$select={self._SENT_EVIDENCE_SELECT}"
        )
        message = await self._make_graph_request(
            user_id,
            endpoint,
            extra_headers={"Prefer": self._IMMUTABLE_ID_PREFER},
            access_token=access_token,
        )

        if message is None:
            unresolved["reason"] = (
                "message_not_found"
                if self.last_graph_status == 404
                else "readback_failed"
            )
            unresolved["http_status"] = self.last_graph_status
            return unresolved

        # _handle_response returns the parsed JSON verbatim; a 200 carrying a
        # list/string is not a message. Refuse it rather than crashing on
        # .get() or treating it as evidence.
        if not isinstance(message, dict):
            unresolved["reason"] = "malformed_response"
            return unresolved

        if message.get("id") != immutable_message_id:
            unresolved["reason"] = "message_id_mismatch"
            return unresolved

        if message.get("isDraft") is not False:
            unresolved["reason"] = "message_is_draft"
            return unresolved

        conversation_id = message.get("conversationId")
        if not isinstance(conversation_id, str) or not conversation_id:
            unresolved["reason"] = "missing_conversation_id"
            return unresolved

        internet_message_id = message.get("internetMessageId")
        if not isinstance(internet_message_id, str) or not internet_message_id:
            unresolved["reason"] = "missing_internet_message_id"
            return unresolved

        return {
            "status": "resolved",
            "resolved": True,
            "message_id": message["id"],
            "conversation_id": conversation_id,
            "internet_message_id": internet_message_id,
            "sent_date_time": message.get("sentDateTime"),
            "received_date_time": message.get("receivedDateTime"),
            "is_draft": False,
            "parent_folder_id": message.get("parentFolderId"),
            "sent_items_may_be_delayed": False,
        }

    # Opt-in exact-reply evidence reads are body-free by construction: the
    # select asks only for correlation fields plus internetMessageHeaders,
    # where RFC 5322 In-Reply-To actually lives (Graph does not surface that
    # header as a first-class message property). The conversation filter is
    # inbox-scoped, so the candidate set is bounded to one thread.
    _EXACT_REPLY_EVIDENCE_SELECT = (
        "id,conversationId,isDraft,internetMessageId,internetMessageHeaders,"
        "from,receivedDateTime,sentDateTime,parentFolderId"
    )
    _EXACT_REPLY_PAGE_SIZE = 50
    # Enough to cover ordinary reminder threads; a remaining nextLink after
    # this many Graph pages is reported as incomplete, never as "no reply".
    _EXACT_REPLY_MAX_PAGES = 5

    # RFC 5322 msg-id: angle brackets around a local-part and domain. The
    # whole token is compared byte-for-byte with the sent message's
    # internetMessageId — no bracket stripping, case folding or substring
    # matching (a "fuzzy" reference must not count as direct proof).
    _MESSAGE_ID_TOKEN_RE = re.compile(r"<[^<>\s]+>")
    _MESSAGE_ID_RE = re.compile(r"^<[^<>\s]+@[^<>\s]+>$")
    _AUTOREPLY_HEADER_NAMES = frozenset({
        "x-autoreply",
        "x-autorespond",
        "x-autoresponder",
        "x-autoresponse",
        "x-auto-reply",
        "x-autogenerated",
        "x-ms-exchange-organization-autoreply",
    })
    _AUTOREPLY_PRECEDENCE = frozenset({
        "auto_reply",
        "auto-reply",
        "autoreply",
        "bulk",
        "junk",
    })

    @staticmethod
    def _normalize_recipient_address(value: Any) -> Optional[str]:
        """Normalize an expected recipient for comparison, or None.

        The address is only compared with a candidate's ``from`` address; it
        is never interpolated into a Graph query. Angle brackets, display
        names, whitespace and separators are rejected so a caller cannot
        smuggle an ambiguous "recipient" into the match."""
        if not isinstance(value, str):
            return None
        address = value.strip()
        if not address or len(address) > 320:
            return None
        if any(ch.isspace() or ch in "<>,;" for ch in address):
            return None
        local_part, separator, domain = address.rpartition("@")
        if not separator or not local_part or not domain or "@" in local_part:
            return None
        return address.casefold()

    @staticmethod
    def _index_internet_headers(value: Any) -> Optional[Dict[str, List[str]]]:
        """Case-insensitive header index from Graph's internetMessageHeaders.

        Returns None when the collection (or any entry in it) is unreadable,
        which callers treat as missing evidence rather than an absent header.
        An empty collection is also missing data: every real Internet message
        carries headers, so Graph dropping the requested collection must not
        read as "no In-Reply-To"."""
        if not isinstance(value, list) or not value:
            return None
        index: Dict[str, List[str]] = {}
        for entry in value:
            if not isinstance(entry, dict):
                return None
            name = entry.get("name")
            header_value = entry.get("value")
            if not isinstance(name, str) or not isinstance(header_value, str):
                return None
            key = name.strip().lower()
            if not key:
                return None
            index.setdefault(key, []).append(header_value)
        return index

    @classmethod
    def _headers_mark_automatic_response(
        cls, headers: Dict[str, List[str]]
    ) -> bool:
        """True when RFC 3834/autoreply markers say this is machine mail."""
        for value in headers.get("auto-submitted", []):
            # RFC 3834: "no" is the explicit non-automatic value; every
            # other registered token (auto-replied, auto-generated, ...)
            # marks an automatic response.
            if value.strip().lower() not in ("", "no"):
                return True
        for name in cls._AUTOREPLY_HEADER_NAMES:
            for value in headers.get(name, []):
                if value.strip().lower() not in ("", "no", "false", "0"):
                    return True
        for value in headers.get("precedence", []):
            if value.strip().lower() in cls._AUTOREPLY_PRECEDENCE:
                return True
        # Calendar/meeting traffic is machine-generated; a meeting response
        # must never stand in for a human reply from the approved recipient.
        for value in headers.get("content-class", []):
            if value.strip().lower().startswith("meeting"):
                return True
        return False

    @classmethod
    def _parse_in_reply_to(cls, values: List[str]) -> Optional[List[str]]:
        """Parse the full RFC 5322 msg-id tokens from In-Reply-To.

        Returns None for anything that cannot be read as an unambiguous
        header: multiple In-Reply-To fields (RFC 5322 permits at most one),
        no complete angle-bracketed id, an id without a domain, stray text
        outside CFWS/comments, or unbalanced brackets. Callers fail closed on
        None instead of guessing at a malformed reference."""
        if len(values) != 1:
            return None
        raw = values[0]
        tokens = cls._MESSAGE_ID_TOKEN_RE.findall(raw)
        if not tokens:
            return None
        if not all(cls._MESSAGE_ID_RE.match(token) for token in tokens):
            return None

        # Strip legal comments (including nested ones) and then require that
        # only whitespace/commas remain between msg-ids. This keeps
        # "In-Reply-To: see <id>" from being treated as an exact reference.
        remainder = cls._MESSAGE_ID_TOKEN_RE.sub("", raw)
        cleaned: List[str] = []
        depth = 0
        for char in remainder:
            if char == "(":
                depth += 1
                continue
            if char == ")":
                if depth == 0:
                    return None
                depth -= 1
                continue
            if depth:
                continue
            if char in "<>":
                return None
            cleaned.append(char)
        if depth:
            return None
        if any(char not in " \t\r\n," for char in cleaned):
            return None
        return tokens

    @classmethod
    def _classify_exact_reply_candidate(
        cls,
        candidate: Any,
        conversation_id: str,
        anchor_internet_message_id: str,
        expected_recipient: str,
    ) -> tuple:
        """Classify one inbox message for exact-reply evidence.

        Returns ``(outcome, reason, matched)`` where outcome is ``ignore``
        (not an answer), ``match`` (direct reply) or ``incomplete`` (the
        message could be an answer but cannot be read safely). Drafts,
        automatic responses, messages from other senders and non- replies
        are ignored only after their identity/conversation fields are known
        good; anything unreadable is conservative."""
        if not isinstance(candidate, dict):
            return "incomplete", "malformed_candidate", None

        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            return "incomplete", "malformed_candidate", None

        candidate_conversation = candidate.get("conversationId")
        if (
            not isinstance(candidate_conversation, str)
            or not candidate_conversation
        ):
            return "incomplete", "malformed_candidate", None
        if candidate_conversation != conversation_id:
            # The inbox query is conversation-scoped; a different value means
            # the page cannot be trusted as the candidate set.
            return "incomplete", "conversation_mismatch", None

        is_draft = candidate.get("isDraft")
        if not isinstance(is_draft, bool):
            return "incomplete", "malformed_candidate", None
        if is_draft:
            return "ignore", None, None

        sender = cls._address_of(candidate.get("from"))
        if not sender:
            return "incomplete", "malformed_candidate", None
        if sender.casefold() != expected_recipient:
            return "ignore", None, None

        headers = cls._index_internet_headers(
            candidate.get("internetMessageHeaders")
        )
        if headers is None:
            return "incomplete", "missing_internet_message_headers", None
        if cls._headers_mark_automatic_response(headers):
            return "ignore", None, None

        in_reply_to = headers.get("in-reply-to")
        if not in_reply_to:
            return "ignore", None, None
        references = cls._parse_in_reply_to(in_reply_to)
        if references is None:
            return "incomplete", "malformed_in_reply_to", None
        if anchor_internet_message_id not in references:
            return "ignore", None, None

        return "match", None, {
            "reply_message_id": candidate_id,
            "reply_sender": sender,
            "reply_conversation_id": candidate_conversation,
            "reply_received_date_time": candidate.get("receivedDateTime"),
            "reply_sent_date_time": candidate.get("sentDateTime"),
        }

    @staticmethod
    def _exact_reply_evidence_result(
        status: str,
        *,
        message_id: Optional[str],
        conversation_id: Optional[str],
        reason: Optional[str] = None,
        http_status: Optional[int] = None,
        anchor_reason: Optional[str] = None,
        reply: Optional[Dict[str, Any]] = None,
        pages_fetched: int = 0,
        candidates_examined: int = 0,
        match_count: int = 0,
        sent_items_may_be_delayed: bool = False,
    ) -> Dict[str, Any]:
        resolved = status == "resolved" and reply is not None
        result: Dict[str, Any] = {
            "status": "resolved" if resolved else "unresolved",
            "resolved": resolved,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "reply_message_id": (reply or {}).get("reply_message_id"),
            "reply_sender": (reply or {}).get("reply_sender"),
            "reply_received_date_time": (
                reply or {}
            ).get("reply_received_date_time"),
            "reply_sent_date_time": (reply or {}).get("reply_sent_date_time"),
            "in_reply_to_matched": resolved,
            "pages_fetched": pages_fetched,
            "candidates_examined": candidates_examined,
            "match_count": match_count,
        }
        if reason is not None:
            result["reason"] = reason
        if http_status is not None:
            result["http_status"] = http_status
        if anchor_reason is not None:
            result["anchor_reason"] = anchor_reason
        if sent_items_may_be_delayed:
            result["sent_items_may_be_delayed"] = True
        return result

    def _validated_exact_reply_next_link(
        self, raw: Optional[str]
    ) -> Optional[str]:
        """Trust a continuation URL only when it points at Graph.

        The shared validator pins the public Graph hosts; a service
        configured with ``MICROSOFT_GRAPH_BASE_URL`` (journey/e2e) is still
        Graph, so its own configured base is allowed too. Anything else is
        rejected rather than followed."""
        validated = self._validated_next_link(raw)
        if validated:
            return validated
        candidate = str(raw or "")
        base = str(self.base_url or "").rstrip("/")
        if (
            base
            and base != GRAPH_API_BASE
            and candidate.startswith(base + "/")
            and "\\.." not in candidate
            and "/.." not in candidate
        ):
            return candidate
        return None

    async def get_exact_reply_evidence(
        self,
        user_id: str,
        immutable_message_id: str,
        expected_recipient: str,
    ) -> Dict[str, Any]:
        """Opt-in proof that the approved recipient replied to one SENT item.

        This is a read-only evidence probe for a verified sent reminder. It
        takes the current authenticated user, the exact immutable ID of the
        message already proven sent, and the approved recipient the reminder
        went to. It performs no send, draft, delete, corpus write, or token
        override.

        The anchor is proven first through the existing Sent Items helper
        (``get_sent_message_evidence``), which yields the anchor's
        conversationId and full Internet Message-ID. Only then is the inbox
        read, one conversation at a time, with ``Prefer:
        IdType="ImmutableId"`` and ``internetMessageHeaders`` in ``$select``.
        A candidate is evidence only when all of the following hold:

        * its conversationId exactly equals the anchor's;
        * it is explicitly not a draft;
        * its ``from`` address case-insensitively equals the approved
          recipient;
        * it is not an automatic response (RFC 3834 ``Auto-Submitted`` and
          the usual autoreply/precedence markers are rejected);
        * its single RFC 5322 ``In-Reply-To`` field parses to full
          angle-bracketed Internet Message-IDs and one token is EXACTLY the
          anchor's ``internetMessageId``.

        Subject and body are never selected, read or compared; malformed
        headers, missing header data, or extra text in In-Reply-To never fall
        back to fuzzy matching. Pages are bounded and every ``@odata.nextLink``
        must pass the existing Graph-only nextLink validation. A remaining
        page, an unreadable page/candidate, or more than one distinct match is
        reported as unresolved (``reason`` says why), never guessed around.
        Raw headers and message bodies are not returned.

        ``resolved`` therefore means exactly one human, non-automatic inbox
        message from the approved recipient is a direct reply to the proven
        sent item. As with the anchor helper, a Sent Items read may lag
        provider persistence; callers retry by calling this again.
        """
        self.last_graph_status = None
        self.last_transport_error = None

        if not isinstance(immutable_message_id, str) or not immutable_message_id:
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=(
                    immutable_message_id
                    if isinstance(immutable_message_id, str)
                    else None
                ),
                conversation_id=None,
                reason="invalid_message_id",
            )

        normalized_recipient = self._normalize_recipient_address(
            expected_recipient
        )
        if normalized_recipient is None:
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=None,
                reason="invalid_expected_recipient",
            )

        try:
            anchor = await self.get_sent_message_evidence(
                user_id, immutable_message_id
            )
        except Exception as e:
            logger.error(
                "Exact-reply anchor read failed for %s: %s", user_id, e
            )
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=None,
                reason="anchor_read_failed",
                sent_items_may_be_delayed=True,
            )
        if (
            not isinstance(anchor, dict)
            or anchor.get("status") != "resolved"
            or anchor.get("resolved") is not True
        ):
            anchor_reason = (
                anchor.get("reason") if isinstance(anchor, dict) else None
            )
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=None,
                reason="anchor_unresolved",
                http_status=(
                    anchor.get("http_status")
                    if isinstance(anchor, dict)
                    else None
                ),
                anchor_reason=anchor_reason,
                sent_items_may_be_delayed=True,
            )

        conversation_id = anchor.get("conversation_id")
        anchor_internet_message_id = anchor.get("internet_message_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=None,
                reason="malformed_anchor",
                sent_items_may_be_delayed=True,
            )
        if anchor.get("is_draft") is not False:
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=conversation_id,
                reason="anchor_is_draft",
            )
        if (
            not isinstance(anchor_internet_message_id, str)
            or not self._MESSAGE_ID_RE.match(anchor_internet_message_id)
        ):
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=conversation_id,
                reason="malformed_anchor_message_id",
            )

        # The anchor read has done its job; clear its transport state so an
        # inbox failure below reports only the inbox attempt.
        self.last_graph_status = None
        self.last_transport_error = None

        # One quote-doubled OData literal; conversationId is provider data,
        # never caller prose, and the inbox folder scope is what keeps the
        # candidate set from spanning the mailbox.
        escaped_conversation = conversation_id.replace("'", "''")
        params = {
            "$filter": f"conversationId eq '{escaped_conversation}'",
            "$select": self._EXACT_REPLY_EVIDENCE_SELECT,
            "$top": self._EXACT_REPLY_PAGE_SIZE,
        }
        endpoint = (
            "/me/mailFolders/inbox/messages?"
            + urllib.parse.urlencode(params)
        )

        matches: List[Dict[str, Any]] = []
        match_ids = set()
        incomplete_reason: Optional[str] = None
        pages_fetched = 0
        candidates_examined = 0
        current = endpoint
        first_page = True

        while current:
            page = await self._make_graph_request(
                user_id,
                current,
                full_url=not first_page,
                extra_headers={"Prefer": self._IMMUTABLE_ID_PREFER},
            )
            first_page = False
            pages_fetched += 1

            if page is None:
                return self._exact_reply_evidence_result(
                    "unresolved",
                    message_id=immutable_message_id,
                    conversation_id=conversation_id,
                    reason="inbox_read_failed",
                    http_status=self.last_graph_status,
                    pages_fetched=pages_fetched,
                    candidates_examined=candidates_examined,
                )
            if not isinstance(page, dict):
                return self._exact_reply_evidence_result(
                    "unresolved",
                    message_id=immutable_message_id,
                    conversation_id=conversation_id,
                    reason="malformed_inbox_page",
                    pages_fetched=pages_fetched,
                    candidates_examined=candidates_examined,
                )
            value = page.get("value")
            if not isinstance(value, list):
                return self._exact_reply_evidence_result(
                    "unresolved",
                    message_id=immutable_message_id,
                    conversation_id=conversation_id,
                    reason="malformed_inbox_page",
                    pages_fetched=pages_fetched,
                    candidates_examined=candidates_examined,
                )

            for candidate in value:
                candidates_examined += 1
                outcome, candidate_reason, matched = (
                    self._classify_exact_reply_candidate(
                        candidate,
                        conversation_id,
                        anchor_internet_message_id,
                        normalized_recipient,
                    )
                )
                if outcome == "incomplete":
                    if incomplete_reason is None:
                        incomplete_reason = (
                            candidate_reason or "incomplete_candidate"
                        )
                elif outcome == "match" and matched is not None:
                    # Graph pagination can repeat a message; a repeat is the
                    # same answer, not a second reply.
                    if matched["reply_message_id"] not in match_ids:
                        match_ids.add(matched["reply_message_id"])
                        matches.append(matched)

            next_link = page.get("@odata.nextLink")
            if not next_link:
                break
            validated_next = self._validated_exact_reply_next_link(next_link)
            if not validated_next:
                return self._exact_reply_evidence_result(
                    "unresolved",
                    message_id=immutable_message_id,
                    conversation_id=conversation_id,
                    reason="untrusted_next_link",
                    pages_fetched=pages_fetched,
                    candidates_examined=candidates_examined,
                )
            if pages_fetched >= self._EXACT_REPLY_MAX_PAGES:
                return self._exact_reply_evidence_result(
                    "unresolved",
                    message_id=immutable_message_id,
                    conversation_id=conversation_id,
                    reason="page_limit_reached",
                    pages_fetched=pages_fetched,
                    candidates_examined=candidates_examined,
                    match_count=len(matches),
                )
            current = validated_next

        if len(matches) > 1:
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=conversation_id,
                reason="ambiguous_reply",
                pages_fetched=pages_fetched,
                candidates_examined=candidates_examined,
                match_count=len(matches),
            )
        if incomplete_reason is not None:
            # A relevant candidate existed but could not be read safely, so
            # "exactly one reply" cannot be asserted even if one match was
            # found (it might not be the only one).
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=conversation_id,
                reason=incomplete_reason,
                pages_fetched=pages_fetched,
                candidates_examined=candidates_examined,
                match_count=len(matches),
            )
        if not matches:
            return self._exact_reply_evidence_result(
                "unresolved",
                message_id=immutable_message_id,
                conversation_id=conversation_id,
                reason="no_matching_reply",
                pages_fetched=pages_fetched,
                candidates_examined=candidates_examined,
            )

        return self._exact_reply_evidence_result(
            "resolved",
            message_id=immutable_message_id,
            conversation_id=conversation_id,
            reply=matches[0],
            pages_fetched=pages_fetched,
            candidates_examined=candidates_examined,
            match_count=1,
        )

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

    @staticmethod
    def _build_draft_payload(
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Message body shared by the draft-creating primitives."""
        payload: Dict[str, Any] = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in to_recipients
            ],
            "ccRecipients": [
                {"emailAddress": {"address": email}} for email in (cc_recipients or [])
            ],
            "bccRecipients": [
                {"emailAddress": {"address": email}} for email in (bcc_recipients or [])
            ],
        }
        if conversation_id:
            payload["conversationId"] = conversation_id
        return payload

    async def create_draft_email(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        token: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create draft email"""
        try:
            email_data = self._build_draft_payload(
                to_recipients=to_recipients,
                subject=subject,
                body=body,
                cc_recipients=cc_recipients,
                bcc_recipients=bcc_recipients,
                conversation_id=conversation_id,
            )
            result = await self._make_graph_request(
                user_id, "/me/messages", "POST", email_data, access_token=token
            )
            return result
        except Exception as e:
            logger.error(f"Error creating draft email: {e}")
            return None

    @staticmethod
    def _draft_creation_result(
        status: str,
        *,
        draft_id: Optional[str] = None,
        reason: Optional[str] = None,
        http_status: Optional[int] = None,
    ) -> Dict[str, Any]:
        created = status == "created"
        unknown = status == "unknown"
        result: Dict[str, Any] = {
            "status": status,
            "outcome": "unknown_effect" if unknown else status,
            "created": True if created else (None if unknown else False),
            "draft_id": draft_id,
            "is_draft": True if created else None,
            "effect_uncertain": unknown,
        }
        if reason is not None:
            result["reason"] = reason
        if http_status is not None:
            result["http_status"] = http_status
        return result

    async def create_draft_with_immutable_id(
        self,
        user_id: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create exactly one Outlook draft and return its immutable ID.

        This is the connector primitive for approved, replay-aware callers
        that persist the immutable ID and later act on that same draft. It
        performs ONE authenticated ``POST /me/messages`` through the existing
        per-user credential lookup, with ``Prefer: IdType="ImmutableId"`` on
        that request only, so the returned ``id`` is the immutable provider ID
        (Microsoft Learn: outlook-immutable-id and user-post-messages). The
        staged caller supplies the invocation-scoped ``access_token`` it has
        already validated against Graph /me; every provider call in that
        invocation therefore uses one pinned credential. It never calls
        ``/send``, never retries, and never falls back to another endpoint or
        cleans up a draft.

        A ``created`` result requires all of: a dict provider response, a
        non-empty string ``id``, ``isDraft`` explicitly ``True``, and an HTTP
        create status (200/201). Anything else after a successful HTTP status
        — malformed JSON, a partial body, a missing/odd ID, or a body that
        does not confirm a draft — is ``unknown``: the provider accepted the
        request, so the draft MAY exist and the caller must not treat it as
        not-created. A transport failure or timeout is likewise ``unknown``.
        All 5xx responses and HTTP 408 are also ``unknown``: the request may
        have reached the mailbox even though no usable response came back.
        Only an explicit provider denial (a conclusive 4xx rejection) or an
        unavailable credential whose transport never began is ``not_created``.

        Draft content and IDs are never logged here.
        """
        email_data = self._build_draft_payload(
            to_recipients=to_recipients,
            subject=subject,
            body=body,
            cc_recipients=cc_recipients,
            bcc_recipients=bcc_recipients,
            conversation_id=conversation_id,
        )
        # The generic transport resets these only after it resolves a token;
        # a missing credential returns first and would leave the previous
        # call's state visible here. Reset before this call so its outcome is
        # judged solely on this attempt.
        self.last_graph_status = None
        self.last_transport_error = None

        result = await self._make_graph_request(
            user_id,
            "/me/messages",
            "POST",
            email_data,
            extra_headers={"Prefer": self._IMMUTABLE_ID_PREFER},
            access_token=access_token,
        )
        http_status = self.last_graph_status

        if result is None:
            if self.last_transport_error:
                return self._draft_creation_result(
                    "unknown",
                    reason="transport_error",
                    http_status=http_status,
                )
            if http_status is None:
                # No credential: the transport never began, so no draft
                # request could have reached the provider.
                return self._draft_creation_result(
                    "not_created",
                    reason="not_authenticated",
                )
            if isinstance(http_status, int) and 200 <= http_status < 300:
                # The response arrived but its success body was unreadable;
                # the provider may still have created the draft.
                return self._draft_creation_result(
                    "unknown",
                    reason="incomplete_response",
                    http_status=http_status,
                )
            # An explicit denial proves the provider refused the create. 5xx,
            # 408, redirects and unrecognized statuses are not proof either
            # way: the provider may have accepted work before failing.
            conclusive_denial_statuses = {
                400, 401, 403, 404, 405, 406, 409, 410, 411, 412, 413,
                414, 415, 416, 417, 418, 421, 422, 423, 424, 425, 426,
                428, 429, 431, 451,
            }
            if http_status in conclusive_denial_statuses:
                return self._draft_creation_result(
                    "not_created",
                    reason="provider_rejected",
                    http_status=http_status,
                )
            return self._draft_creation_result(
                "unknown",
                reason="inconclusive_status",
                http_status=http_status,
            )

        if not isinstance(result, dict):
            return self._draft_creation_result(
                "unknown",
                reason="malformed_response",
                http_status=http_status,
            )

        draft_id = result.get("id")
        if not isinstance(draft_id, str) or not draft_id:
            return self._draft_creation_result(
                "unknown",
                reason="missing_draft_id",
                http_status=http_status,
            )
        if result.get("isDraft") is not True:
            return self._draft_creation_result(
                "unknown",
                reason="missing_is_draft",
                http_status=http_status,
            )
        if http_status not in (200, 201):
            # Accepted/reset without the documented create status is not
            # conclusive enough to claim a draft was created.
            return self._draft_creation_result(
                "unknown",
                reason="inconclusive_status",
                http_status=http_status,
            )
        return self._draft_creation_result(
            "created",
            draft_id=draft_id,
            http_status=http_status,
        )

    @staticmethod
    def _draft_send_result(
        status: str,
        *,
        message_id: Optional[str] = None,
        reason: Optional[str] = None,
        http_status: Optional[int] = None,
        provider_accepted: Optional[bool] = None,
    ) -> Dict[str, Any]:
        unknown = status == "unknown"
        result: Dict[str, Any] = {
            "status": status,
            "outcome": "unknown_effect" if unknown else status,
            "provider_accepted": provider_accepted,
            "sent_items_verified": False,
            "effect_uncertain": unknown,
            "message_id": message_id,
        }
        if reason is not None:
            result["reason"] = reason
        if http_status is not None:
            result["http_status"] = http_status
        return result

    async def send_existing_immutable_draft(
        self,
        user_id: str,
        immutable_message_id: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send one already-persisted draft by its exact immutable ID.

        This is an internal connector primitive for a caller that has already
        persisted the provider draft identity and independently verified human
        approval. It performs exactly ONE authenticated
        ``POST /me/messages/{id}/send`` through the existing per-user
        credential lookup, with ``Prefer: IdType="ImmutableId"`` on that
        request only. The staged caller supplies the invocation-scoped
        ``access_token`` it has already validated against Graph /me, so the
        create and send legs cannot observe different credentials from the
        same row. The opaque ID is percent-encoded as one path segment and
        otherwise used verbatim. There is deliberately no way to choose a
        different mailbox: the caller-supplied token must already be the one
        validated for this operation's persisted mailbox binding.

        It never creates a draft, searches, retries, deletes/cleans up,
        changes message content, or falls back to another endpoint.

        HTTP 202 means only that the provider ACCEPTED the send request; this
        method does not read Sent Items, so its result is never proof of a
        verified send. An explicit conclusive 4xx denial (other than 404/408)
        is ``not_sent``. A timeout/transport failure, HTTP 5xx, HTTP 408,
        HTTP 404, or any other inconclusive response is ``unknown`` with
        ``effect_uncertain`` true: the provider may already have sent the
        draft, and a 404 in particular can follow an earlier send. Draft
        content and IDs are never logged here.
        """
        # Reset before validating the ID: a refusal or a missing credential
        # must not expose the previous call's Graph status/transport state.
        self.last_graph_status = None
        self.last_transport_error = None
        self.last_send_error = None

        if (
            not isinstance(immutable_message_id, str)
            or not immutable_message_id.strip()
        ):
            return self._draft_send_result(
                "not_sent",
                reason="invalid_message_id",
                provider_accepted=False,
            )

        message_id = immutable_message_id
        encoded_id = urllib.parse.quote(message_id, safe="")
        try:
            result = await self._make_graph_request(
                user_id,
                f"/me/messages/{encoded_id}/send",
                "POST",
                {},
                extra_headers={"Prefer": self._IMMUTABLE_ID_PREFER},
                access_token=access_token,
            )
        except Exception as e:
            # The existing transport normally converts this to None plus
            # last_transport_error; keep the primitive safe if it does not.
            self.last_transport_error = str(e)[:300]
            return self._draft_send_result(
                "unknown",
                message_id=message_id,
                reason="transport_error",
                http_status=self.last_graph_status,
            )

        http_status = self.last_graph_status
        if http_status == 202:
            return self._draft_send_result(
                "provider_accepted",
                message_id=message_id,
                http_status=http_status,
                provider_accepted=True,
            )

        # 404 can mean the draft was already sent successfully, so it is not
        # a safe "not sent" signal. 408 and every 5xx are equally ambiguous.
        if http_status == 404:
            return self._draft_send_result(
                "unknown",
                message_id=message_id,
                reason="draft_not_found_or_already_sent",
                http_status=http_status,
            )
        if http_status == 408:
            return self._draft_send_result(
                "unknown",
                message_id=message_id,
                reason="timeout",
                http_status=http_status,
            )
        if isinstance(http_status, int) and 500 <= http_status < 600:
            return self._draft_send_result(
                "unknown",
                message_id=message_id,
                reason="provider_error",
                http_status=http_status,
            )

        if result is None:
            if self.last_transport_error:
                return self._draft_send_result(
                    "unknown",
                    message_id=message_id,
                    reason="transport_error",
                    http_status=http_status,
                )
            if http_status is None:
                # No credential: the transport never began, so no send
                # request could have reached the provider.
                return self._draft_send_result(
                    "not_sent",
                    message_id=message_id,
                    reason="not_authenticated",
                    provider_accepted=False,
                )
            if isinstance(http_status, int) and 200 <= http_status < 300:
                # A response arrived but no usable body did; the provider may
                # still have accepted the send.
                return self._draft_send_result(
                    "unknown",
                    message_id=message_id,
                    reason="incomplete_response",
                    http_status=http_status,
                )
            conclusive_denial_statuses = {
                400, 401, 403, 405, 406, 409, 410, 411, 412, 413, 414, 415,
                416, 417, 418, 421, 422, 423, 424, 425, 426, 428, 429, 431,
                451,
            }
            if http_status in conclusive_denial_statuses:
                return self._draft_send_result(
                    "not_sent",
                    message_id=message_id,
                    reason="provider_rejected",
                    http_status=http_status,
                    provider_accepted=False,
                )
            return self._draft_send_result(
                "unknown",
                message_id=message_id,
                reason="inconclusive_status",
                http_status=http_status,
            )

        # A non-202 success body is not the documented send response, so it
        # proves neither acceptance nor a verified Sent Items entry.
        return self._draft_send_result(
            "unknown",
            message_id=message_id,
            reason="inconclusive_status",
            http_status=http_status,
        )

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

    def _attachment_failure(self, operation: str, message: str) -> Dict[str, Any]:
        status = self.last_graph_status
        if status == 401:
            kind = "auth_expired"
        elif status == 403:
            kind = "unauthorized"
        else:
            kind = "provider_error"
        self.last_error = {
            "status": "error",
            "success": False,
            "provider": "outlook",
            "operation": operation,
            "error_kind": kind,
            "error": message,
            "retryable": False,
            "requires_reconnect": kind in ("auth_expired", "auth_unavailable"),
        }
        return self.last_error

    async def get_attachment_content(
        self, user_id: str, message_id: str, attachment_id: str, token: Optional[str] = None
    ) -> Optional[bytes]:
        """Fetch attachment content for an email"""
        self.last_error = None
        try:
            endpoint = f"/me/messages/{message_id}/attachments/{attachment_id}"
            result = await self._make_graph_request(user_id, endpoint, access_token=token)

            if result and "contentBytes" in result:
                import base64

                return base64.b64decode(result["contentBytes"])

            logger.error(
                f"Failed to fetch content for attachment {attachment_id} in message {message_id}"
            )
            self._attachment_failure(
                "get_attachment_content",
                f"attachment {attachment_id} returned no content")
            return None
        except Exception as e:
            logger.error(f"Error getting attachment content: {e}")
            self._attachment_failure("get_attachment_content", str(e)[:300])
            return None

    async def get_attachment_metadata(
        self, user_id: str, message_id: str, token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Attachment metadata normalized to the same schema as
        GmailService.get_attachment_metadata (id/name/size/contentType) —
        core.ingestion_pipeline's attachment branch dispatches on these names."""
        self.last_error = None
        try:
            endpoint = (
                f"/me/messages/{message_id}/attachments"
                "?$select=id,name,size,contentType,isInline"
            )
            result = await self._make_graph_request(user_id, endpoint, access_token=token)
            if not result:
                self._attachment_failure(
                    "get_attachment_metadata",
                    "the message attachment list could not be read")
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
            self._attachment_failure("get_attachment_metadata", str(e)[:300])
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

    @staticmethod
    def _graph_message_dicts(result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map one Graph /me/messages page to OutlookEmail dicts."""
        emails = []
        for email_data in (result or {}).get("value", []):
            emails.append(asdict(OutlookEmail(
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
            )))
        return emails

    # Continuation tokens must point at the Graph messages endpoint family —
    # a caller-supplied token is agent/HTTP-facing input, so an arbitrary URL
    # would be an SSRF vector, not just a malformed cursor.
    _NEXT_LINK_PREFIXES = (
        "https://graph.microsoft.com/v1.0/",
        "https://graph.microsoft.com/beta/",
    )

    @classmethod
    def _validated_next_link(cls, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        candidate = str(raw)
        if not candidate.startswith(cls._NEXT_LINK_PREFIXES):
            return None
        if "\\.." in candidate or "/.." in candidate:
            return None
        return candidate

    async def search_emails_paged(
        self, user_id: str, query: str, max_results: int = 50, token: Optional[str] = None,
        quote: bool = True, sender: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """search_emails with pagination visibility (MCP opaque-cursor shape).

        Two silent-truncation fixes over the historical single-page search
        (2026-09-16, the 100K-record mailbox class):

        - ``@odata.nextLink`` is FOLLOWED (up to ``_SEARCH_MAX_PAGES`` Graph
          calls) while fewer than ``max_results`` emails have been collected,
          so a ``$top=50`` request actually returns up to 50 messages instead
          of the first relevance page Graph chose to send.
        - the response reports ``has_more``/``next_page_token`` so the agent
          can request the continuation instead of reading a truncated page
          as the complete answer. ``next_page_token`` is the Graph nextLink
          URL (endpoint + $search + $skiptoken — no credentials in it);
          passing it back as ``page_token`` resumes exactly there.

        Returns ``{"emails": [...], "has_more": bool, "next_page_token":
        str|None, "pages_fetched": int}``; ``emails`` shape is identical to
        search_emails.
        """
        try:
            if page_token:
                next_link = self._validated_next_link(page_token)
                if not next_link:
                    return {"emails": [], "has_more": False, "next_page_token": None,
                            "pages_fetched": 0, "error": "invalid page_token"}
                emails: List[Dict[str, Any]] = []
                pages = 0
                current: Optional[str] = next_link
                while current and len(emails) < max_results and pages < _SEARCH_MAX_PAGES:
                    page = await self._make_graph_request(
                        user_id, current, access_token=token, full_url=True)
                    emails.extend(self._graph_message_dicts(page))
                    pages += 1
                    current = self._validated_next_link(
                        (page or {}).get("@odata.nextLink"))
                return {
                    "emails": emails[:max_results],
                    "has_more": bool(current) and len(emails) >= max_results,
                    "next_page_token": current,
                    "pages_fetched": pages,
                }

            if sender and not _SENDER_ADDRESS_RE.match(str(sender).strip()):
                logger.warning(
                    "search_emails: ignoring malformed sender filter %r",
                    str(sender)[:80],
                )
                sender = None
            attempts: List[str] = []
            if sender:
                # from:-scoping must be QUOTED on this Graph backend: the
                # bare clause 400s ("character ':' is not valid at position
                # 4", live 2026-09-12) while '"from:user@host"' matches the
                # sender reliably — Graph phrase-matches the rendered From
                # header. Quoted bare address is the final fallback.
                rest = sanitize_graph_kql(query) if query else ""
                scoped = f'"from:{sender}"'
                attempts.append(f"{scoped} {rest}".strip() if rest else scoped)
                attempts.append(scoped)
                attempts.append(f'"{sender}"')
            else:
                # Embedded quotes must not be double-wrapped — the outer
                # pair creates nested phrase syntax that always 400s.
                attempts.append(f'"{query}"' if quote and '"' not in query else query)
                sanitized = sanitize_graph_kql(query)
                if sanitized and sanitized != attempts[0]:
                    wrapped = f'"{sanitized}"' if quote and '"' not in sanitized else sanitized
                    if wrapped != attempts[0]:
                        attempts.append(wrapped)
                decomposed = decompose_graph_kql(query)
                if decomposed and decomposed not in attempts:
                    attempts.append(decomposed)

            result = None
            consecutive_failures = 0
            for attempt in attempts:
                # Graph rejects $orderby combined with $search on
                # /me/messages — results come back relevance-ranked, so
                # ordering is simply omitted.
                params = {
                    "$top": max_results,
                    "$search": attempt,
                }
                query_string = urllib.parse.urlencode(params)
                endpoint = f"/me/messages?{query_string}"
                result = await self._make_graph_request(user_id, endpoint, access_token=token)
                if result is not None:
                    break
                status = getattr(self, "last_graph_status", None)
                if status in _AUTH_FAILURE_STATUSES:
                    logger.warning(
                        "search_emails: Graph auth failure (%s) — aborting "
                        "the KQL ladder (no rung can fix credentials; "
                        "reconnect Outlook)",
                        status,
                    )
                    break
                consecutive_failures += 1
                if consecutive_failures >= _SEARCH_LADDER_MAX_FAILURES:
                    logger.warning(
                        "search_emails: %d consecutive KQL forms rejected — "
                        "aborting the ladder early",
                        consecutive_failures,
                    )
                    break
            if result is None and attempts:
                logger.warning(
                    "search_emails: every KQL form rejected by Graph for "
                    "query=%r (tried %r) — returning []",
                    query, attempts,
                )

            emails = self._graph_message_dicts(result)
            pages = 1
            next_link = self._validated_next_link((result or {}).get("@odata.nextLink"))
            # Short first page + a nextLink = Graph held results back; follow
            # it (bounded) until the caller's max_results is satisfied.
            while (next_link and len(emails) < max_results
                   and pages < _SEARCH_MAX_PAGES):
                page = await self._make_graph_request(
                    user_id, next_link, access_token=token, full_url=True)
                if page is None:
                    break
                emails.extend(self._graph_message_dicts(page))
                pages += 1
                next_link = self._validated_next_link(page.get("@odata.nextLink"))

            return {
                "emails": emails[:max_results],
                "has_more": bool(next_link) and len(emails) >= max_results,
                "next_page_token": next_link,
                "pages_fetched": pages,
            }
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return {"emails": [], "has_more": False, "next_page_token": None,
                    "pages_fetched": 0}

    async def search_emails(
        self, user_id: str, query: str, max_results: int = 50, token: Optional[str] = None,
        quote: bool = True, sender: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search emails across all folders (multi-page; list contract).

        See search_emails_paged for the KQL ladder, the ``from:`` scoping
        and the nextLink-following behavior — this wrapper keeps the
        historical plain-list return for existing callers.
        """
        paged = await self.search_emails_paged(
            user_id, query, max_results=max_results, token=token,
            quote=quote, sender=sender,
        )
        return paged.get("emails", [])

    async def list_recent_emails(
        self, user_id: str, max_results: int = 50, token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Newest-first mailbox listing with NO ``$search`` clause.

        The on-demand ingest fallback needs a target even when every search
        form misses — $search is the thing that fails (400s, relevance
        flooding), so this path avoids it entirely: plain
        ``$orderby=receivedDateTime desc`` paging over the whole mailbox
        (lowercase $orderby — OData is case-sensitive and Graph rejects
        ``$orderBy`` with an unrecognized-query-option 400, like every
        other call site here). Callers filter locally (figure tokens,
        sender). Same dict shape as search_emails; [] on failure.
        """
        try:
            params = {"$top": max_results, "$orderby": "receivedDateTime desc"}
            endpoint = f"/me/messages?{urllib.parse.urlencode(params)}"
            result = await self._make_graph_request(user_id, endpoint, access_token=token)
            emails = []
            for email_data in (result or {}).get("value", []):
                emails.append(asdict(OutlookEmail(
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
                )))
            return emails
        except Exception as e:
            logger.error(f"Error listing recent emails: {e}")
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

