"""Read-shape parameters for every integration: limits, cursors, projection.

Bug class this closes (2026-09 audit of the SaaS fetch layer): at 100K-record
scale the agent-facing read surface silently returned the FIRST provider page
and said nothing about it. Outlook did a single-page ``$top`` with no
``@odata.nextLink`` follow, HubSpot ignored its own limit/offset, Slack capped
``count``, and the UIS family (Linear/Zendesk/...) passed no paging params at
all. Worse, no tool schema carried a cursor parameter, so the agent literally
could not ask for page two — and, seeing `status: success`, answered from a
partial page as if it were the whole record set. That is a silent-correctness
bug, not an efficiency loss.

Three shapes every integration read needs, one implementation each:

- ``ReadQuery`` — normalize the read shape from free-form action params
  (``limit``/``page_size``/``max_results``/``top``/``count`` are the same
  knob under five provider spellings; ``page_token``/``cursor``/``offset``
  likewise) and clamp it to a budget;
- ``project_records`` — field projection applied at the response boundary so
  every integration returns only the columns the question is about (the
  dominant token waste on wide CRM objects);
- ``SERVICE_CAPABILITIES`` — per-integration declaration of whether the
  provider supports server-side search / projection / which pagination
  style, so the general layer can push work down where the API allows it
  instead of pulling-then-filtering everywhere.

Cursor contract follows the MCP pagination spec
(https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination):
cursors are OPAQUE strings owned by the provider, page size is
server-determined, a missing ``nextCursor`` means end-of-results, and clients
never parse or synthesize one. Providers that expose offset/limit instead
(Stripe's ``starting_after``, HubSpot's ``after``) get their opaque token from
us — an offset encoded as a string — so the agent-facing surface is uniform.

For the tool-catalog side of the same audit see
``integrations/tool_catalog.py``.

Pure functions plus one frozen dataclass — no I/O, no repo imports, so any
integration service can import it without cycles.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# --- limits ------------------------------------------------------------------

#: Page size applied when the caller names none. Deliberately small: the old
#: default of "whatever the provider's default page was" (10-100 records of
#: every field) is the token bill this module exists to cut.
DEFAULT_READ_LIMIT = 25

#: Hard ceiling for one page. Above this the read is a bulk export, not a
#: question, and belongs in the ingestion/dataset path instead.
MAX_READ_LIMIT = 200

# Aliases providers and callers use for "how many records".
_LIMIT_KEYS: Tuple[str, ...] = (
    "limit", "page_size", "pagesize", "max_results", "maxresults",
    "top", "count", "per_page", "perpage", "size", "first",
)
# Aliases for "where to resume". Opaque to us; handed straight to the provider.
_TOKEN_KEYS: Tuple[str, ...] = (
    "page_token", "pagetoken", "next_page_token", "nextpagetoken",
    "cursor", "next_cursor", "nextcursor", "after", "offset", "page",
    "skip", "starting_after", "start_cursor",
)
# Aliases for "which columns".
_FIELD_KEYS: Tuple[str, ...] = (
    "fields", "field", "properties", "property", "select", "columns",
    "projection", "attributes",
)
# Aliases for a server-side filter predicate (distinct from the free-text
# `query` the search intents carry).
_FILTER_KEYS: Tuple[str, ...] = (
    "filter", "where", "filter_by", "filters", "predicate",
)


def _first_present(params: Mapping[str, Any], keys: Sequence[str]) -> Tuple[Optional[str], Any]:
    """First key present with a non-empty value, plus the key it came from."""
    for key in keys:
        if key in params:
            value = params[key]
            if value is None or value == "" or value == [] or value == {}:
                continue
            return key, value
    return None, None


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return int(text)
    return None


def _as_fields(value: Any) -> Tuple[str, ...]:
    """Normalize a projection spec into a tuple of dotted paths.

    Accepts ``"id,name"``, ``["id", "name"]``, ``{"id": 1, "name": 0}`` (the
    Mongo/Salesforce REST shape) and ``{"id": true}`` — callers reach for all
    four.
    """
    if not value:
        return ()
    if isinstance(value, str):
        raw: Iterable[Any] = value.replace(";", ",").split(",")
    elif isinstance(value, Mapping):
        raw = [k for k, v in value.items() if v not in (0, False, None)]
    elif isinstance(value, (list, tuple, set)):
        raw = value
    else:
        return ()
    out: List[str] = []
    for item in raw:
        if item is None:
            continue
        name = str(item).strip()
        if not name:
            continue
        # Providers spell nested paths with '/' (Socrata) or '.' (Mongo).
        name = name.replace("/", ".")
        if name not in out:
            out.append(name)
    return tuple(out)


@dataclass(frozen=True)
class ReadQuery:
    """The normalized read shape of one integration action.

    ``limit`` is clamped to ``[1, MAX_READ_LIMIT]``. ``page_token`` stays
    opaque (never parsed here). ``fields`` is a tuple of dotted paths.
    ``filter_expr`` is a server-side predicate in whatever dialect the
    provider takes; ``query`` is the free-text search term.
    """

    limit: int = DEFAULT_READ_LIMIT
    page_token: Optional[str] = None
    fields: Tuple[str, ...] = ()
    filter_expr: Optional[str] = None
    query: Optional[str] = None
    #: True when the caller explicitly asked for a page size (so a handler
    #: can tell "give me the default" from "give me 5").
    explicit_limit: bool = False
    #: The provider-facing key the limit arrived under, kept for handlers
    #: that must forward the caller's own spelling (Jira's ``maxResults``).
    limit_key: Optional[str] = None
    token_key: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_params(cls, params: Optional[Mapping[str, Any]]) -> "ReadQuery":
        params = params or {}
        limit_key, limit_val = _first_present(params, _LIMIT_KEYS)
        token_key, token_val = _first_present(params, _TOKEN_KEYS)
        _, fields_val = _first_present(params, _FIELD_KEYS)
        _, filter_val = _first_present(params, _FILTER_KEYS)

        limit = _as_int(limit_val)
        explicit = limit is not None
        if limit is None:
            limit = DEFAULT_READ_LIMIT
        limit = max(1, min(limit, MAX_READ_LIMIT))

        token: Optional[str] = None
        if token_val is not None:
            token = str(token_val).strip() or None

        filter_expr: Optional[str] = None
        if filter_val is not None:
            filter_expr = (
                str(filter_val).strip()
                if not isinstance(filter_val, (dict, list))
                else filter_val  # type: ignore[assignment]
            )

        query = params.get("query")
        query = str(query).strip() if query not in (None, "") else None

        return cls(
            limit=limit,
            page_token=token,
            fields=_as_fields(fields_val),
            filter_expr=filter_expr,  # type: ignore[arg-type]
            query=query,
            explicit_limit=explicit,
            limit_key=limit_key,
            token_key=token_key,
        )

    @property
    def has_projection(self) -> bool:
        return bool(self.fields)

    def page_size_for(self, provider_max: Optional[int] = None) -> int:
        """The page size to request, capped by the provider's own maximum."""
        if provider_max is None:
            return self.limit
        return max(1, min(self.limit, provider_max))

    def cache_key(self) -> str:
        """Stable identity of this read (for the TTL response cache)."""
        material = "|".join([
            str(self.limit),
            self.page_token or "",
            ",".join(self.fields),
            str(self.filter_expr or ""),
            self.query or "",
        ])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


# --- pagination providers ----------------------------------------------------


def offset_token(offset: int) -> str:
    """Encode an offset as the opaque token the agent sees.

    Providers whose pagination is numeric (HubSpot's ``after``, Zendesk's
    ``page[after]`` cursor, Jira's ``startAt``, SQL-ish ``offset``) still get
    an opaque string token at the agent boundary, so a model can never
    mis-arithmetic its way to a wrong page and every integration's tool
    schema looks the same.
    """
    return f"o:{max(0, int(offset))}"


def decode_offset_token(token: Optional[str]) -> int:
    """Offset carried by a token, 0 for anything unparseable.

    Tolerant by design (MCP: "handle invalid cursors gracefully"): a
    hallucinated cursor restarts at the first page rather than erroring.
    """
    if not token:
        return 0
    text = str(token).strip()
    if text.startswith("o:"):
        text = text[2:]
    try:
        return max(0, int(text))
    except (TypeError, ValueError):
        return 0


def next_link_token(result: Any) -> Optional[str]:
    """Pull the next-page marker out of a raw provider envelope.

    Covers the shapes the catalog actually returns: Graph/OData
    ``@odata.nextLink``, Slack/Notion ``response_metadata.next_cursor``,
    Google ``nextPageToken``, HubSpot ``paging.next.after``, Stripe
    ``has_more`` + ``starting_after``. Returns ``None`` when the page is the
    last one — callers must treat that as end-of-results.
    """
    if not isinstance(result, Mapping):
        return None
    for key in ("@odata.nextLink", "nextLink", "next_link", "next"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("nextPageToken", "next_page_token", "nextCursor", "next_cursor"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    meta = result.get("response_metadata") or result.get("metadata")
    if isinstance(meta, Mapping):
        value = meta.get("next_cursor")
        if isinstance(value, str) and value.strip():
            return value.strip()
    paging = result.get("paging")
    if isinstance(paging, Mapping):
        nxt = paging.get("next")
        if isinstance(nxt, Mapping):
            value = nxt.get("after") or nxt.get("page")
            if value not in (None, ""):
                return str(value)
        if paging.get("next_page") not in (None, ""):
            return str(paging.get("next_page"))
    if result.get("has_more") is True:
        last = result.get("last_id") or (result.get("data") or [{}])[-1]
        if isinstance(last, Mapping) and last.get("id"):
            return str(last["id"])
    return None


# --- projection --------------------------------------------------------------

_MISSING = object()


def _dig(record: Mapping[str, Any], path: str) -> Any:
    """Value at a dotted path, case-insensitively on the first segment."""
    if path in record:
        return record[path]
    parts = path.split(".")
    current: Any = record
    for index, part in enumerate(parts):
        if not isinstance(current, Mapping):
            return _MISSING
        if part in current:
            current = current[part]
            continue
        if index == 0:
            match = next(
                (k for k in current if str(k).lower() == part.lower()), None
            )
            if match is not None:
                current = current[match]
                continue
        return _MISSING
    return current


def project_record(record: Any, fields: Sequence[str]) -> Any:
    """One record narrowed to ``fields`` (dotted paths rebuild their nesting).

    Non-mapping records pass through untouched — a projection request must
    never turn data into ``{}``. Absent fields are omitted rather than
    rendered as ``null`` (``null`` costs tokens and reads as a real value).
    """
    if not fields or not isinstance(record, Mapping):
        return record
    out: Dict[str, Any] = {}
    for path in fields:
        value = _dig(record, path)
        if value is _MISSING:
            continue
        if "." in path and path not in record:
            node = out
            parts = path.split(".")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
                if not isinstance(node, dict):  # pragma: no cover - defensive
                    break
            else:
                node[parts[-1]] = value
            continue
        out[path] = value
    return out


def project_records(data: Any, fields: Sequence[str]) -> Any:
    """Projection across the envelope shapes integrations return.

    Handles a bare list, a bare record, and the common wrappers
    (``{"data": [...]}``, ``{"results": [...]}``, ``{"records": [...]}``,
    ``{"value": [...]}``, ``{"issues": [...]}``, ``{"items": [...]}``).
    """
    if not fields:
        return data
    if isinstance(data, list):
        return [project_record(item, fields) for item in data]
    if not isinstance(data, Mapping):
        return data
    list_keys = [k for k, v in data.items() if isinstance(v, list)]
    if len(list_keys) == 1:
        # Exactly one list member — that is the record set, project it in
        # place so the surrounding metadata survives.
        key = list_keys[0]
        out = dict(data)
        out[key] = [project_record(item, fields) for item in data[key]]
        return out
    if list_keys:
        # Several lists (a Salesforce envelope can carry `records` plus
        # `errors`): project only the one that looks like records.
        for key in ("records", "results", "value", "data", "items", "issues"):
            if key in list_keys:
                out = dict(data)
                out[key] = [project_record(item, fields) for item in data[key]]
                return out
        return data
    # A single record returned bare (e.g. {"id": ..., "properties": {...}}).
    return project_record(data, fields)


# --- per-service capabilities ------------------------------------------------

# search:      "server"  provider has a real server-side search API
#              "client"  dispatch must pull then filter (core.identifier_search)
#              "memory"  no live read API; search the ingested mirror
#              "none"    no search surface at all
# projection:  "server"  provider accepts a fields/properties/select param
#              "client"  project the response after the fetch
# pagination:  "cursor" | "offset" | "page" | "next_link" | "none"
# kind:        free-text note naming the server-side filter parameter, if any.


@dataclass(frozen=True)
class ServiceCapabilities:
    search: str = "client"
    projection: str = "client"
    pagination: str = "cursor"
    #: Provider parameter that carries the free-text query server-side.
    search_param: Optional[str] = None
    #: Provider parameter that carries a field projection server-side.
    projection_param: Optional[str] = None
    #: Provider's own maximum page size, when it documents one.
    max_page_size: Optional[int] = None

    @property
    def server_side_search(self) -> bool:
        return self.search == "server"

    @property
    def server_side_projection(self) -> bool:
        return self.projection == "server"

    @property
    def paginated(self) -> bool:
        return self.pagination != "none"


#: Declared capabilities for every service the planner can advertise.
#: Adding a service to ``chat_tool_planner._SERVICE_DESCRIPTIONS`` without an
#: entry here is caught by tests/test_integration_read_capabilities.py.
SERVICE_CAPABILITIES: Dict[str, ServiceCapabilities] = {
    # --- CRM -------------------------------------------------------------
    "salesforce": ServiceCapabilities(
        search="server", projection="server", pagination="next_link",
        search_param="q", projection_param="fields", max_page_size=200,
    ),
    "hubspot": ServiceCapabilities(
        search="server", projection="server", pagination="cursor",
        search_param="query", projection_param="properties", max_page_size=100,
    ),
    "zoho_crm": ServiceCapabilities(
        search="server", projection="server", pagination="page",
        search_param="word", projection_param="fields", max_page_size=200,
    ),
    "pipedrive": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="term", max_page_size=100,
    ),
    # --- Communication ---------------------------------------------------
    "gmail": ServiceCapabilities(
        search="server", projection="server", pagination="cursor",
        search_param="q", projection_param="fields", max_page_size=500,
    ),
    "outlook": ServiceCapabilities(
        search="server", projection="server", pagination="next_link",
        search_param="$search", projection_param="$select", max_page_size=100,
    ),
    "outlook_calendar": ServiceCapabilities(
        search="server", projection="server", pagination="next_link",
        search_param="$search", projection_param="$select", max_page_size=100,
    ),
    "zoho_mail": ServiceCapabilities(
        search="server", projection="client", pagination="offset",
        search_param="searchKey", max_page_size=100,
    ),
    "slack": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="query", max_page_size=100,
    ),
    "teams": ServiceCapabilities(
        search="server", projection="client", pagination="next_link",
        search_param="$search", max_page_size=50,
    ),
    "google_chat": ServiceCapabilities(
        search="client", projection="client", pagination="page", max_page_size=100,
    ),
    "telegram": ServiceCapabilities(
        search="client", projection="client", pagination="offset", max_page_size=100,
    ),
    "whatsapp": ServiceCapabilities(
        search="client", projection="client", pagination="none",
    ),
    "discord": ServiceCapabilities(
        search="client", projection="client", pagination="cursor", max_page_size=100,
    ),
    "zoom": ServiceCapabilities(
        search="client", projection="client", pagination="page", max_page_size=300,
    ),
    # --- Calendar --------------------------------------------------------
    "google_calendar": ServiceCapabilities(
        search="client", projection="server", pagination="cursor",
        projection_param="fields", max_page_size=250,
    ),
    # --- Project management ----------------------------------------------
    "jira": ServiceCapabilities(
        search="server", projection="server", pagination="offset",
        search_param="jql", projection_param="fields", max_page_size=100,
    ),
    "linear": ServiceCapabilities(
        search="client", projection="client", pagination="cursor", max_page_size=250,
    ),
    "asana": ServiceCapabilities(
        search="client", projection="server", pagination="cursor",
        projection_param="opt_fields", max_page_size=100,
    ),
    "monday": ServiceCapabilities(
        search="client", projection="client", pagination="cursor", max_page_size=500,
    ),
    "trello": ServiceCapabilities(
        search="server", projection="server", pagination="none",
        search_param="query", projection_param="fields",
    ),
    "zoho_projects": ServiceCapabilities(
        search="client", projection="client", pagination="page", max_page_size=100,
    ),
    # --- Storage ---------------------------------------------------------
    "google_drive": ServiceCapabilities(
        search="server", projection="server", pagination="cursor",
        search_param="q", projection_param="fields", max_page_size=1000,
    ),
    "dropbox": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="query", max_page_size=1000,
    ),
    "onedrive": ServiceCapabilities(
        search="server", projection="server", pagination="next_link",
        search_param="$search", projection_param="$select", max_page_size=200,
    ),
    "box": ServiceCapabilities(
        search="server", projection="server", pagination="offset",
        search_param="query", projection_param="fields", max_page_size=200,
    ),
    "notion": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="query", max_page_size=100,
    ),
    "zoho_workdrive": ServiceCapabilities(
        search="server", projection="client", pagination="offset",
        search_param="search", max_page_size=100,
    ),
    # --- Support ---------------------------------------------------------
    "zendesk": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="query", max_page_size=100,
    ),
    "freshdesk": ServiceCapabilities(
        search="server", projection="client", pagination="page",
        search_param="query", max_page_size=100,
    ),
    "intercom": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="query", max_page_size=150,
    ),
    # --- Development -----------------------------------------------------
    "github": ServiceCapabilities(
        search="server", projection="client", pagination="page",
        search_param="q", max_page_size=100,
    ),
    "gitlab": ServiceCapabilities(
        search="server", projection="client", pagination="page",
        search_param="search", max_page_size=100,
    ),
    "figma": ServiceCapabilities(
        search="client", projection="client", pagination="cursor", max_page_size=100,
    ),
    # --- Finance ---------------------------------------------------------
    "stripe": ServiceCapabilities(
        search="server", projection="client", pagination="cursor",
        search_param="query", max_page_size=100,
    ),
    "quickbooks": ServiceCapabilities(
        search="server", projection="client", pagination="page",
        search_param="query", max_page_size=1000,
    ),
    "xero": ServiceCapabilities(
        search="server", projection="client", pagination="page",
        search_param="where", max_page_size=1000,
    ),
    "zoho_books": ServiceCapabilities(
        search="client", projection="client", pagination="page", max_page_size=200,
    ),
    "zoho_inventory": ServiceCapabilities(
        search="server", projection="client", pagination="page",
        search_param="search_text", max_page_size=200,
    ),
    "aws_ses": ServiceCapabilities(
        search="none", projection="client", pagination="none",
    ),
    # --- Marketing -------------------------------------------------------
    "mailchimp": ServiceCapabilities(
        search="server", projection="server", pagination="offset",
        search_param="query", projection_param="fields", max_page_size=1000,
    ),
    "hubspot_marketing": ServiceCapabilities(
        search="server", projection="server", pagination="cursor",
        search_param="query", projection_param="properties", max_page_size=100,
    ),
    "meta_ads": ServiceCapabilities(
        search="none", projection="server", pagination="cursor",
        projection_param="fields", max_page_size=100,
    ),
    "google_ads": ServiceCapabilities(
        search="server", projection="server", pagination="page",
        search_param="query", projection_param="fields", max_page_size=10000,
    ),
    "linkedin_ads": ServiceCapabilities(
        search="none", projection="client", pagination="page", max_page_size=100,
    ),
    "google_reviews": ServiceCapabilities(
        search="client", projection="client", pagination="page", max_page_size=50,
    ),
    # --- Analytics -------------------------------------------------------
    "tableau": ServiceCapabilities(
        search="client", projection="server", pagination="page",
        projection_param="fields", max_page_size=1000,
    ),
    "google_analytics": ServiceCapabilities(
        search="none", projection="server", pagination="offset",
        projection_param="metrics", max_page_size=100000,
    ),
    # --- E-commerce ------------------------------------------------------
    "shopify": ServiceCapabilities(
        search="server", projection="server", pagination="cursor",
        search_param="query", projection_param="fields", max_page_size=250,
    ),
    # --- Forms & automation (webhook-push; reads come from the mirror) ----
    "zoho_forms": ServiceCapabilities(
        search="memory", projection="client", pagination="offset", max_page_size=200,
    ),
    "zoho_flow": ServiceCapabilities(
        search="memory", projection="client", pagination="offset", max_page_size=200,
    ),
}


def capabilities_for(service: str) -> ServiceCapabilities:
    """Declared capabilities for a service, with a conservative default.

    Unknown services (Activepieces catalog entries, tenant connectors) get
    the client-side posture: pull then filter, project locally. That is
    correct for any provider; it is just not the cheapest, and a service
    only earns the server-side posture by being declared above with evidence.
    """
    return SERVICE_CAPABILITIES.get(
        (service or "").strip().lower(), ServiceCapabilities()
    )


def declared_services() -> Tuple[str, ...]:
    return tuple(sorted(SERVICE_CAPABILITIES))


# --- response envelope -------------------------------------------------------


def page_meta(
    query: ReadQuery,
    returned: int,
    next_token: Optional[str],
    *,
    fetched: Optional[int] = None,
) -> Dict[str, Any]:
    """The ``page`` block attached to every paginated read response.

    This block is the fix for the silent-truncation bug: the agent is TOLD
    how many records it got, whether the provider has more, and the exact
    token to ask for the next page. ``truncated`` is the honest flag — it is
    true whenever a next page exists and the caller did not consume it.
    """
    meta: Dict[str, Any] = {
        "returned": returned,
        "limit": query.limit,
        "has_more": bool(next_token),
        "truncated": bool(next_token),
    }
    if fetched is not None:
        meta["fetched"] = fetched
    if query.page_token:
        meta["page_token"] = query.page_token
    if next_token:
        meta["next_page_token"] = next_token
    return meta


def truncation_notice(meta: Mapping[str, Any]) -> Optional[str]:
    """One-line, model-readable warning for a partial page.

    Returned alongside the data so a model that reads only ``message`` still
    learns the answer is drawn from a partial record set.
    """
    if not meta.get("truncated"):
        return None
    token = meta.get("next_page_token")
    return (
        f"PARTIAL PAGE: showing {meta.get('returned')} record(s) of a larger "
        f"result set — do NOT treat this as the complete set. Call again with "
        f"page_token={token!r} for the next page."
    )
