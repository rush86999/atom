
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from core.database import SessionLocal
from core.identifier_search import filter_by_terms
from integrations.read_cache import (
    cache_lookup,
    cache_store,
    cached_read_async,
    invalidate_after_write,
    is_read_action,
)
from integrations.read_query import (
    DEFAULT_READ_LIMIT,
    MAX_READ_LIMIT,
    ReadQuery,
    capabilities_for,
    decode_offset_token,
    offset_token,
    page_meta,
    project_records,
    truncation_notice,
)
from integrations.salesforce_service import SalesforceService
from integrations.hubspot_service import get_hubspot_service
from integrations.shopify_service import ShopifyService
from core.circuit_breaker import circuit_breaker
# governance_middleware is optional — the module may not exist in all setups.
try:
    from middleware.governance_middleware import governance_middleware
except ImportError:
    governance_middleware = None
# budget_service was renamed/removed; guard the import so this module loads.
try:
    from core.budget_service import budget_service
except ImportError:
    budget_service = None
try:
    from core.cost_config import get_action_cost
except ImportError:
    def get_action_cost(*args, **kwargs):
        return 0.0

logger = logging.getLogger(__name__)


def _query_anchored_excerpt(text: str, query: str, excerpt_chars: int = 4000) -> str:
    """Excerpt of ``text`` centered on the best query-token match region.

    A workbook read must surface the REGION the question is about (the
    WG350DSAV row), not the file head — the head is usually sheet 1 /
    cover-page boilerplate, which is exactly what the old preview-only paths
    showed while the answer sat further in. Falls back to the head when no
    query token appears.

    RAREST-TOKEN ANCHOR first: the query token with the fewest occurrences
    in the text is the identifying one (the model number vs "price"/"list"
    boilerplate). Coverage scoring alone loses exactly here — a row region
    is a numeric dump, so header windows containing "consolidated price
    list" out-score it 3-to-1 and the excerpt lands thousands of rows away
    (live 2026-09-04: 'wg350dsav' at offset 2.4M of a 4.1M-char workbook
    never surfaced). When the rarest token is itself frequent (>50 hits,
    i.e. not identifying), fall back to distinct-token coverage scoring.

    SHEET ANCHOR before that: our Excel parsers emit per-sheet markers
    (``=== Sheet: NAME ===`` / ``--- Sheet: NAME ---``). When a query token
    names a SHEET, the excerpt comes from that sheet — the rarest-token
    path cannot express "the region this token NAMES" because the token's
    first occurrences are the workbook index at the file head and brand-name
    rows in unrelated sheets (live 2026-09-06: "check Consolidated Price
    List 2019 for the Linmac bandsaw price" anchored on the index's LINMAC
    line ~3k chars in; the WG350DSAV row sat at 58% of a 3.4M-char text —
    the agent saw sheet headers and reported the row unreadable). Within
    the sheet the anchor follows the query's OTHER tokens (the model code)
    rather than the sheet head: a price-book sheet runs tens of thousands
    of chars, and the wanted row can begin just past a head-sized window
    (live 2026-09-07: WG350DSAV row 17 began ~4.2k chars into LINMAC — one
    row past the head window, again "unreadable"). Hyphenated model tokens
    also try their compacted form ("wg-350dsav" → "wg350dsav" as the
    workbook spells it).
    """
    text = text or ""
    import re as _re

    tokens = [t for t in _re.split(r"[^a-z0-9]+", (query or "").lower()) if len(t) > 2]
    # Compacted variants: workbooks write codes without the separator the
    # user typed ("WG-350DSAV" lives in the sheet as "WG350DSAV").
    for _raw in list(tokens):
        _compact = _raw.replace("-", "").replace("_", "")
        if _compact != _raw and len(_compact) >= 6 and _compact not in tokens:
            tokens.append(_compact)
    lower = text.lower()
    uniq = set(tokens)
    if not uniq:
        return text[:excerpt_chars]
    counts = {t: lower.count(t) for t in uniq}

    # Sheet-name anchor: query token names a sheet in the parsed body.
    sheet_hits = list(_re.finditer(
        r"\n(?:===|---) Sheet: ([^\n=]+?)(?:===|---)\n", text))
    if sheet_hits:
        compact = {t.replace("-", "").replace("_", ""): t for t in uniq}
        for m in sheet_hits:
            sheet_name = _re.sub(r"[^a-z0-9]+", "", m.group(1).lower())
            matched_token = next(
                (tok for compacted, tok in compact.items()
                 if len(sheet_name) >= 3
                 and (compacted == sheet_name
                      # containment needs BOTH sides ≥5: "heck" ⊂ "check"
                      # must not route a "check the price" query to the
                      # HECK sheet (live 2026-09-07 query variant)
                      or (len(compacted) >= 5 and len(sheet_name) >= 5
                          and (compacted in sheet_name
                               or sheet_name in compacted)))),
                None,
            )
            if matched_token:
                # The row the question asks about may sit far past the sheet
                # head — the LINMAC price list's WG350DSAV row begins ~4.2k
                # chars into its sheet, just past a head window, so the
                # anchor-at-sheet-start read ended ONE ROW short and the
                # agent again reported the row unreadable (live 2026-09-07:
                # 'consolidated price list 2019 linmac bandsaw'). Two-stage
                # sheet→row anchor, the shape mature spreadsheet-retrieval
                # stacks converge on (select the named sheet, locate the
                # row, ship it with the sheet's header block so the column
                # values are attributable). Parsed rows ARE lines: candidate
                # lines hold the sheet-identifying token (matched_token);
                # among them pick most distinct query tokens, then rarest
                # token set, then digit-densest (data row beats brand-title
                # line), then earliest.
                sheet_start = min(len(text) - 1, m.start() + 1)
                # Same-named adjacent markers (real exports carry duplicate/
                # whitespace-variant sheet tabs) are ONE body: clipping at
                # the twin marker would strand the rows between/after it.
                next_m = next(
                    (s for s in sheet_hits if s.start() > m.start()
                     and _re.sub(r"[^a-z0-9]+", "", s.group(1).lower())
                     != sheet_name),
                    None,
                )
                sheet_end = next_m.start() if next_m else len(text)
                lines = []
                for line_m in _re.finditer(
                        r"[^\n]+\n?", text[m.end():sheet_end]):
                    line_raw = line_m.group(0)
                    if _re.match(r"\s*(?:===|---) Sheet:", line_raw):
                        continue  # structural marker, never an anchor
                    toks = frozenset(
                        t for t in uniq if t in line_raw.lower())
                    if toks:
                        lines.append((
                            line_m.start() + m.end(),
                            toks,
                            sum(c.isdigit() for c in line_raw),
                        ))
                best_line = None
                if lines:
                    # Primary key: the token that IDENTIFIED the sheet —
                    # "the region this token names". Global counts misfire
                    # as the primary key on small workbooks where header
                    # boilerplate ("price") is nominally rarer than the
                    # brand (live-shape repro: one-sheet book, price=1 <
                    # linmac=2 → anchored the header line, row lost).
                    keyed = [
                        (pos, toks, digits) for pos, toks, digits in lines
                        if matched_token in toks]
                    if keyed:
                        # Digit count breaks the brand-title-vs-data-row
                        # tie: "R1 | Linmac Machinery" and the WG350DSAV
                        # row both carry just "linmac" for a linmac-only
                        # query, but only one holds the price.
                        best_line, _, _ = max(
                            keyed,
                            key=lambda item: (
                                len(item[1]),
                                -sum(counts[t] for t in item[1]),
                                item[2],
                                -item[0],
                            ),
                        )
                    else:
                        # The identifier can live only on the sheet's title
                        # line (query "invoices sheet … brightwater" against
                        # an AR-aging export whose rows never say
                        # "invoices"): score every content line by token
                        # identity. Keying on a single "rarest" token does
                        # NOT work here — header words ("Salary") tie with
                        # names ("Okafor") at count 1 and the header wins
                        # the coin flip, anchoring the head; whole-line hits
                        # ("Jane Okafor" = 2) beat header words (= 1) for
                        # free.
                        best_line, _, _ = max(
                            lines,
                            key=lambda item: (
                                len(item[1]),
                                -sum(counts[t] for t in item[1]),
                                item[2],
                                -item[0],
                            ),
                        )
                # A query that NAMES a sheet wants that sheet's content, and
                # price-book sheets run 10k+ chars — the old 4k cap is what
                # cut R17 off. Head stays the fallback ("open the LINMAC
                # sheet" legitimately reads from the top).
                start = max(sheet_start, best_line - 200) \
                    if best_line is not None else sheet_start
                end = min(sheet_end, start + 12_000)
                excerpt_body = text[start:end]
                head_chars = 800  # title + column-header rows
                if start > sheet_start + head_chars:
                    # Header + row: ship the sheet's head block ahead of a
                    # deep-anchored window so the row's numbers have their
                    # column names attached.
                    excerpt_body = (
                        text[sheet_start:sheet_start + head_chars]
                        + "\n…\n" + excerpt_body)
                suffix = " …" if end < len(text) else ""
                return (
                    f"[excerpt from the '{m.group(1).strip()}' sheet] "
                    f"{excerpt_body}{suffix}"
                )

    # Rare-token/coverage anchors search the sheet BODIES, not the workbook
    # index head — a sheet NAME's first occurrences are index lines whose
    # windows carry headers but no rows.
    index_m = _re.search(r"^WORKBOOK INDEX:", text, flags=_re.MULTILINE)
    body_start = 0
    if index_m:
        body_m = _re.search(r"\n(?:===|---) Sheet: ", text[index_m.end():])
        if body_m:
            body_start = index_m.end() + body_m.start() + 1
    # Anchor only on tokens PRESENT in the text: an enriched context token
    # may name a different product entirely (count 0) — anchoring on it
    # would land on the head and be worse than coverage scoring.
    present = {t: c for t, c in counts.items() if c > 0}
    half = excerpt_chars // 2
    if present:
        anchor = min(present, key=lambda t: (present[t], -len(t)))
        if present[anchor] <= 50:
            idx = lower.find(anchor, body_start)
            if idx < 0:
                idx = lower.find(anchor)
            start = max(0, idx - half)
            end = min(len(text), idx + half)
            prefix = "… " if start > 0 else ""
            suffix = " …" if end < len(text) else ""
            return f"{prefix}{text[start:end]}{suffix}"
    best_pos, best_hits = 0, -1
    for tok in sorted(uniq, key=len, reverse=True):
        start = body_start
        finds = 0
        while finds < 2000:  # cap: boilerplate tokens can occur thousands of times
            idx = lower.find(tok, start)
            if idx < 0:
                break
            finds += 1
            # count how many DISTINCT tokens appear in this window
            window = lower[max(0, idx - excerpt_chars // 2): idx + excerpt_chars // 2]
            hits = sum(1 for t in uniq if t in window)
            if hits > best_hits:
                best_pos, best_hits = idx, hits
            start = idx + len(tok)
            if best_hits >= len(uniq):
                break
    if best_hits <= 0 or (index_m and best_hits < len(uniq)):
        # Workbook texts: every-token-co-occurrence or the index. "price",
        # "list" and year numbers occur in nearly every sheet of a price
        # book, so a partial-coverage window is boilerplate coincidence from
        # a random sheet — the index head is the useful fallback: the model
        # sees the sheet list and can re-read with a sheet or model token.
        return text[:excerpt_chars]
    start = max(0, best_pos - half)
    end = min(len(text), best_pos + half)
    prefix = "… " if start > 0 else ""
    suffix = " …" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"

# All native integrations supported by Atom
NATIVE_INTEGRATIONS = {
    # Sales & CRM
    "salesforce", "hubspot", "zoho_crm",
    # Communication
    "slack", "teams", "discord", "google_chat", "telegram", "whatsapp", "zoom", "zoho_mail",
    # Project Management
    "asana", "jira", "linear", "trello", "monday", "zoho_projects",
    # Storage & Knowledge
    "google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive",
    # Forms & Automation (webhook-push apps — no public read API; the agent
    # reads what has been ingested, see _execute_zoho)
    "zoho_forms", "zoho_flow",
    # Support
    "zendesk", "freshdesk", "intercom",
    # Development
    "github", "gitlab", "figma",
    # Finance
    "stripe", "quickbooks", "xero", "zoho_books", "zoho_inventory",
    # Marketing
    "mailchimp", "hubspot_marketing", "meta_ads", "google_ads", "linkedin_ads", "google_reviews",
    # Analytics
    "tableau", "google_analytics",
    # E-commerce
    "shopify",
    # Email & Communication
    "aws_ses",
}

# Services with a LIVE search implementation in UniversalIntegrationService.search()
# (the family branches below). Single source of truth for:
#   - chat_tool_planner.execute_tool_plan: plain "search" intents for these
#     services route through search() instead of execute(), whose family
#     handlers only implement named actions;
#   - the planner catalog annotation ("live search supported" vs
#     "no live search — use memory").
# Keep in sync with the search() routing — asserted by
# tests/test_planner_live_search_routing.py.
SEARCHABLE_SERVICES = frozenset({
    # CRM
    "salesforce", "hubspot", "pipedrive", "zoho_crm",
    # Communication
    "slack", "teams", "discord", "google_chat", "telegram", "whatsapp",
    "gmail", "outlook", "zoho_mail",
    # Calendar
    "google_calendar", "outlook_calendar",
    # Project management
    "linear", "monday", "zoho_projects", "asana", "jira", "trello",
    # Storage
    "google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive",
    # Forms & automation (search the INGESTED records — no live read API)
    "zoho_forms", "zoho_flow",
    # Support
    "zendesk", "freshdesk", "intercom",
    # Development
    "github", "gitlab",
    # Marketing / analytics
    "mailchimp", "tableau", "google_analytics",
    # Finance (recent lists, client-side query filter)
    "stripe", "quickbooks", "xero", "zoho_books",
    # Dedicated item search (DC-correct service method)
    "zoho_inventory",
})

# Execute-path search routing (service → _search_* helper). The search()
# entry and the execute() families grew separate search implementations;
# the family chains implemented search for only SOME services, so planner
# "search" intents silently dead-ended for the rest (live 2026-09-03 class:
# box, linear, jira, asana, trello, gmail). _dispatch_execution routes
# search actions for these services through the same _search_* helpers the
# search() entry uses — one search implementation per service. Kept in sync
# with the families by tests/test_integration_dispatch_parity.py.
_SEARCH_ROUTES = {
    # Communication
    "slack": "_search_communication",
    "teams": "_search_communication",
    "discord": "_search_communication",
    "google_chat": "_search_communication",
    "telegram": "_search_communication",
    "whatsapp": "_search_communication",
    "gmail": "_search_communication",
    "outlook": "_search_communication",
    "zoho_mail": "_search_communication",
    # Project management
    "linear": "_search_project_management",
    "monday": "_search_project_management",
    "zoho_projects": "_search_project_management",
    "asana": "_search_project_management",
    "jira": "_search_project_management",
    "trello": "_search_project_management",
    # Storage
    "google_drive": "_search_storage",
    "dropbox": "_search_storage",
    "onedrive": "_search_storage",
    "box": "_search_storage",
    "notion": "_search_storage",
    "zoho_workdrive": "_search_storage",
    # CRM
    "salesforce": "_search_crm",
    "hubspot": "_search_crm",
    "zoho_crm": "_search_crm",
    "pipedrive": "_search_crm",
    # Support
    "zendesk": "_search_support",
    "freshdesk": "_search_support",
    "intercom": "_search_support",
    # Development
    "github": "_search_dev",
    "gitlab": "_search_dev",
    # Finance (client-side filter over recent lists)
    "stripe": "_search_finance",
    "quickbooks": "_search_finance",
    "xero": "_search_finance",
    "zoho_books": "_search_finance",
}

async def _download_storage_file_bytes(service: str, storage_service: Any, token: Optional[str],
                                       user_id: Optional[str], file_id: str) -> Optional[bytes]:
    """Provider-neutral download for the background dataset re-verify (mirrors
    the per-service branches in _read_storage_file)."""
    if service == "zoho_workdrive":
        return await storage_service.download_file(user_id or token, file_id)
    if service in ("google_drive", "onedrive", "box"):
        return await storage_service.download_file_bytes(token, file_id)
    if service == "dropbox":
        return await storage_service.download_file(file_id, token)
    return None


def _storage_hit_value(hit: Dict[str, Any], *keys: str) -> Any:
    if not isinstance(hit, dict):
        return None
    for key in keys:
        value = hit.get(key)
        if value not in (None, ""):
            return value
    for container_key in ("attributes", "metadata", "data"):
        container = hit.get(container_key)
        if isinstance(container, dict):
            for key in keys:
                value = container.get(key)
                if value not in (None, ""):
                    return value
    return None


def _storage_hit_id(hit: Dict[str, Any]) -> Optional[str]:
    value = _storage_hit_value(
        hit, "id", "file_id", "fileId", "resource_id", "external_id"
    )
    return str(value) if value not in (None, "") else None


def _storage_hit_name(hit: Dict[str, Any]) -> Optional[str]:
    value = _storage_hit_value(hit, "name", "display_name", "title", "file_name")
    return str(value) if value not in (None, "") else None


def _storage_requested_name(query: str) -> Optional[str]:
    try:
        from core.agent_file_context import detect_file_task_mentions

        mentions = detect_file_task_mentions(query or "")
        if mentions:
            return mentions[0]
    except Exception:
        pass
    return None


def _resolve_storage_hits(
    hits: List[Dict[str, Any]], query: str, service: str, user_id: Optional[str]
) -> Dict[str, Any]:
    requested = _storage_requested_name(query)
    result: Dict[str, Any] = {
        "requested_name": requested,
        "identity_verified": False,
        "ambiguous": False,
        "file_id": None,
        "file_name": None,
        "provider": service,
        "resource_id": None,
        "source_metadata": None,
        "candidates": [],
    }
    if not hits:
        result["reason"] = "no_hits"
        return result

    exact: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    for hit in hits:
        name = _storage_hit_name(hit)
        resource_id = _storage_hit_id(hit)
        if not name or not resource_id:
            continue
        item = {
            "id": resource_id,
            "name": name,
            "type": str(_storage_hit_value(hit, "type", "kind") or "file"),
            "team_id": _storage_hit_value(hit, "team_id", "teamId"),
            "folder_id": _storage_hit_value(
                hit, "folder_id", "parent_id", "parentId"
            ),
            "modified_at": _storage_hit_value(
                hit, "modified_at", "modified_time", "modifiedAt", "version"
            ),
            "size": _storage_hit_value(hit, "size", "size_in_bytes"),
            "extension": _storage_hit_value(hit, "extension", "extn"),
            "raw": hit,
        }
        candidates.append(item)
        if requested:
            try:
                from core.agent_file_context import score_file_match

                tier = score_file_match(requested, name)
            except Exception:
                tier = None
            if tier in ("exact", "normalized"):
                exact.append(item)
        elif service == "zoho_workdrive":
            exact.append(item)

    unique_exact = {item["id"]: item for item in exact}
    if len(unique_exact) > 1:
        result["ambiguous"] = True
        result["candidates"] = [
            {"id": item["id"], "name": item["name"]}
            for item in unique_exact.values()
        ]
        result["reason"] = "duplicate_exact_name"
        return result

    chosen = next(iter(unique_exact.values()), None)
    if chosen is None and requested and len(candidates) == 1:
        chosen = candidates[0]
        result["reason"] = "single_candidate_not_verified"
    if chosen is None:
        result["candidates"] = [
            {"id": item["id"], "name": item["name"]} for item in candidates[:5]
        ]
        result["reason"] = "no_exact_name"
        return result

    metadata = {
        "team_id": chosen.get("team_id"),
        "folder_id": chosen.get("folder_id"),
        "modified_at": chosen.get("modified_at"),
        "size": chosen.get("size"),
        "extension": chosen.get("extension"),
        "user_id": str(user_id) if user_id else None,
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}
    complete = bool(
        chosen.get("id")
        and chosen.get("name")
        and chosen.get("type") != "folder"
        and (metadata.get("modified_at") or metadata.get("version"))
        and (metadata.get("team_id") or metadata.get("folder_id"))
    )
    result.update({
        "file_id": chosen["id"],
        "resource_id": chosen["id"],
        "file_name": chosen["name"],
        "source_metadata": metadata,
        "identity_verified": bool(unique_exact and complete),
    })
    result["candidates"] = [
        {"id": item["id"], "name": item["name"]} for item in candidates[:5]
    ]
    return result


async def _refresh_storage_metadata(
    service: str, storage_service: Any, user_id: Optional[str], identity: Dict[str, Any]
) -> Dict[str, Any]:
    getter = getattr(storage_service, "get_file_metadata", None)
    if not callable(getter) or not identity.get("resource_id"):
        return identity
    try:
        raw = await getter(user_id, identity["resource_id"])
    except Exception as e:
        identity["metadata_error"] = str(e)[:160]
        return identity
    name = _storage_hit_name(raw or {})
    resource_id = _storage_hit_id(raw or {})
    if not resource_id or not name:
        identity["identity_verified"] = False
        identity["metadata_error"] = "metadata_incomplete"
    elif resource_id != identity.get("resource_id"):
        identity["identity_verified"] = False
        identity["metadata_error"] = "resource_id_mismatch"
    if name and not identity.get("file_name"):
        identity["file_name"] = name
    if isinstance(raw, dict):
        raw_meta = {
            "team_id": _storage_hit_value(raw, "team_id", "teamId"),
            "folder_id": _storage_hit_value(raw, "folder_id", "parent_id", "parentId"),
            "modified_at": _storage_hit_value(raw, "modified_at", "modified_time", "version"),
            "version": _storage_hit_value(raw, "version"),
            "size": _storage_hit_value(raw, "size", "size_in_bytes"),
            "extension": _storage_hit_value(raw, "extension", "extn"),
            "user_id": str(user_id) if user_id else None,
        }
        identity["source_metadata"] = {
            **(identity.get("source_metadata") or {}),
            **{key: value for key, value in raw_meta.items() if value is not None},
            "provider_metadata": raw,
        }
        if resource_id and name and not identity.get("metadata_error"):
            requested_name = identity.get("requested_name")
            requested_matches = True
            if requested_name:
                try:
                    from core.agent_file_context import score_file_match

                    requested_matches = score_file_match(
                        requested_name, name
                    ) in ("exact", "normalized")
                except Exception:
                    requested_matches = False
            identity["metadata_verified"] = bool(requested_matches)
            identity["identity_verified"] = bool(
                requested_matches
                and identity.get("reason") != "single_candidate_not_verified"
                and (
                    (identity["source_metadata"].get("modified_at")
                     or identity["source_metadata"].get("version"))
                    and (identity["source_metadata"].get("team_id")
                         or identity["source_metadata"].get("folder_id"))
                )
            )
    if name and identity.get("file_name"):
        try:
            from core.agent_file_context import score_file_match

            if score_file_match(identity["file_name"], name) not in (
                "exact", "normalized"
            ):
                identity["identity_verified"] = False
                identity["metadata_error"] = "name_mismatch"
        except Exception:
            pass
    if isinstance(raw, dict):
        identity["source_metadata"] = {
            **(identity.get("source_metadata") or {}),
            "provider_metadata": raw,
        }
        identity["metadata_verified"] = bool(resource_id and name)
    return identity


def _dataset_reverify_due(ds_result: Dict[str, Any]) -> bool:
    """Should a served-from-copy answer trigger a background re-verification?
    Only when the copy is older than the min-age — a copy materialized seconds
    ago is definitionally current, and skipping keeps the common case free."""
    try:
        min_age_s = float(os.getenv("ATOM_SHEET_DATASET_REVERIFY_MIN_AGE_S", "300"))
    except ValueError:
        min_age_s = 300.0
    ingested = ds_result.get("ingested_at")
    if not ingested:
        return True
    try:
        ingested_dt = datetime.fromisoformat(str(ingested).replace("Z", "+00:00"))
        if ingested_dt.tzinfo is None:
            ingested_dt = ingested_dt.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ingested_dt
        return age.total_seconds() >= min_age_s
    except (ValueError, TypeError):
        return True


def _schedule_dataset_reverify(service: str, storage_service: Any, token: Optional[str],
                               user_id: Optional[str], file_id: str, *, file_name: str,
                               workspace_id: Optional[str]) -> None:
    """Background: re-download the source, hash-check, re-materialize on
    change. Converts the answer-time staleness window into seconds — the user
    gets the instant copy answer AND the store self-corrects right after."""
    from core.sheet_dataset_service import ensure_sheet_dataset, spawn_background

    async def _task() -> None:
        content = await _download_storage_file_bytes(service, storage_service, token, user_id, file_id)
        if not content:
            return
        await ensure_sheet_dataset(
            content,
            file_name=file_name or f"{service}:{file_id}",
            source=service,
            user_id=user_id,
            workspace_id=workspace_id,
            external_id=str(file_id),
        )

    if not spawn_background(_task(), f"dataset re-verify {file_id}"):
        logger.debug(f"dataset re-verify not scheduled (no loop) for {file_id}")


class UniversalIntegrationService:
    """
    Unified interface for accessing third-party integrations.
    Provides consistent CRUD and Search capabilities for Agents via MCP.
    Supports all 44 native integrations + Activepieces catalog fallback.
    """
    
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        
    def _mask_response(self, service: str, response: Any) -> Any:
        """Apply the gatekeeper's per-provider response field masking so
        credentials (access_token, refresh_token, ...) never leak out of the
        integration layer. Best-effort: any gatekeeper failure returns the
        response unmasked rather than failing the action."""
        if governance_middleware is not None and hasattr(governance_middleware, "mask_response"):
            try:
                return governance_middleware.mask_response(service, response)
            except Exception:
                logger.warning(f"Response masking skipped for {service}", exc_info=True)
        return response

    @staticmethod
    def _filter_by_query(data: Any, query: str, limit: int = 8) -> List[Any]:
        """Client-side relevance filter for list endpoints that lack a
        server-side search param. ANY query term (>=3 chars; falls back to
        the whole query) matches, ranked by total matched-term weight — a
        record carrying the model code the question is about outranks ones
        that merely share a prose word — with recency (original) order
        preserved for ties. Previously this kept the FIRST limit matches in
        list order, which buried identifier matches under generic-term
        matches (live 2026-09-04: "bandsaw" matched 42 items while the
        stocked WG-350DSAV sat past the cut). Shared implementation:
        core.identifier_search.filter_by_terms."""
        from core.identifier_search import filter_by_terms
        return filter_by_terms(
            data if isinstance(data, (list, tuple)) else [data],
            query, text_of=str, limit=limit)

    # --- Read shape (pagination / projection) ---------------------------
    #
    # The audit's P1 finding: at 100K records the agent got the FIRST
    # provider page and a bare ``status: success``, so it answered from a
    # partial record set without knowing it. These two helpers are the
    # general fix — every service, every family, one implementation.
    # Cursor semantics per the MCP pagination spec: opaque token,
    # provider-owns-page-size, missing next cursor = end of results.

    @staticmethod
    def _records_container(data: Any):
        """(list_of_records, container_key) for the shapes integrations return."""
        if isinstance(data, list):
            return data, None
        if isinstance(data, dict):
            for key in ("records", "results", "value", "data", "items",
                        "issues", "entries", "messages", "tickets",
                        "conversations", "documents", "rows"):
                value = data.get(key)
                if isinstance(value, list):
                    return value, key
        return None, None

    def _apply_read_shape(
        self,
        service: str,
        action: str,
        read: ReadQuery,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Narrow + annotate a read result before it reaches the agent.

        Two transforms, both driven by the normalized :class:`ReadQuery`:

        1. **Projection** — when the caller named ``fields``, only those
           columns survive (works for every integration; the ones whose
           provider accepts a native projection also get it pushed down by
           :func:`provider_read_params`).
        2. **Pagination envelope** — a ``page`` block stating what was
           returned, whether more exists, and the opaque token to continue.
           Whenever ``has_more`` is not provably ``False`` the response also
           carries a PARTIAL PAGE notice, because silence is what let an
           agent present page one of a 100K-row object as the whole set.

        Never touches non-success envelopes, and never invents a cursor: a
        synthesized offset token is only offered for providers whose
        pagination IS an offset (declared in ``SERVICE_CAPABILITIES``).
        """
        # Normalize the two non-standard shapes the family helpers return
        # into the ONE shape search()/execute() promise:
        #   - a bare list (the search() branches assign the helper's list
        #     straight to `result`);
        #   - a bare provider envelope with no status key (Dropbox/Box style
        #     `{"results": [...]}`).
        # Without this, `search()` answered with a list for Linear, a raw
        # provider dict for Dropbox and `{"status","data"}` for Salesforce —
        # three shapes for one operation, and the page block reached only
        # the third. Error envelopes are left untouched so callers keep
        # seeing the key they check for.
        if isinstance(result, (list, tuple)):
            result = {"status": "success", "data": list(result)}
        elif isinstance(result, dict) and "status" not in result:
            if "error" in result:
                return result
            result = {"status": "success", "data": result}

        if not isinstance(result, dict) or result.get("status") != "success":
            return result
        if result.get("data") is None:
            return result

        # Copy before annotating: this object may be a cache entry, and
        # popping the private cursor off it would make the SECOND identical
        # read silently lose its continuation token.
        result = dict(result)

        caps = capabilities_for(service)
        data = result["data"]
        records, container_key = self._records_container(data)
        total = len(records) if records is not None else None

        # The provider cursor a handler recovered from its response envelope
        # (Graph @odata.nextLink, Slack next_cursor, HubSpot paging.next.after
        # ...). Private key so it is never mistaken for payload.
        provider_token = result.pop("_next_page_token", None)
        if not provider_token:
            provider_token = result.pop("next_page_token", None)
        if isinstance(provider_token, (dict, list)):
            provider_token = None

        # --- clamp to the requested page size ---
        truncated_by_slice = False
        if (read.explicit_limit and records is not None and total is not None
                and total > read.limit):
            records = records[:read.limit]
            truncated_by_slice = True
            total = len(records)
            if container_key is None:
                data = records
            else:
                data = dict(data)
                data[container_key] = records
            result["data"] = data

        # --- projection (after slicing so we never project dropped rows) ---
        if read.has_projection:
            result["data"] = project_records(result["data"], read.fields)
            result["projected"] = {"fields": list(read.fields),
                                   "side": "server" if caps.server_side_projection
                                   else "client"}

        if records is None:
            return result

        # --- next-page token ---
        next_token: Optional[str] = None
        if isinstance(provider_token, str) and provider_token.strip():
            next_token = provider_token.strip()
        elif truncated_by_slice:
            base = decode_offset_token(read.page_token)
            next_token = offset_token(base + read.limit)
        elif caps.pagination in ("offset", "page") and read.explicit_limit:
            base = decode_offset_token(read.page_token)
            next_token = offset_token(base + read.limit)

        # has_more is TRI-state on purpose:
        #   True  — we know more exist (we sliced, or the provider said so)
        #   False — the provider returned fewer than the page we asked for
        #   None  — no evidence either way; never claim completeness
        if next_token:
            has_more: Optional[bool] = True
        elif read.explicit_limit and total is not None and total < read.limit:
            has_more = False
        elif caps.pagination == "none":
            has_more = False
        else:
            has_more = None

        meta = page_meta(read, total or 0, next_token)
        meta["has_more"] = has_more
        meta["truncated"] = True if has_more is True else False
        if has_more is None:
            meta["note"] = (
                "one provider page; the provider reported no next-page "
                "cursor, so completeness is UNVERIFIED — narrow the query or "
                "request explicit fields before treating this as the full set"
            )
            result["page"] = meta
            return result

        result["page"] = meta
        notice = truncation_notice(meta)
        if notice:
            # Surfaced on `message` too: a model that reads only the summary
            # line still learns the answer is drawn from a partial set.
            result["message"] = notice
        return result

    async def execute(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an action against a specific integration service via IntegrationRegistry.
        """
        from core.database import SessionLocal
        from core.integration_registry import IntegrationRegistry

        context = context or {}
        user_id = context.get("user_id")
        workspace_id = context.get("workspace_id") or self.workspace_id
        tenant_id = context.get("tenant_id") or workspace_id
        agent_id = context.get("agent_id")

        # --- Tool-error signal capture ---
        # The evolution harness (ReflectionEngine → Memento/AlphaEvolver)
        # only learns from FAILED episodes, and episode outcome comes from
        # execution metadata. Swallowed tool errors (a 400 returned as [])
        # used to die here invisibly. Record every error/circuit-open/
        # attribution-hold onto the agent's running execution so episodes
        # stop recording silent failures as successes. Fire-and-forget,
        # never breaks the call.
        async def _record_tool_error(kind: str, detail: str) -> None:
            try:
                from core.auto_dev.tool_error_signals import (
                    record_tool_error,
                    should_trigger_live,
                    tool_error_signature,
                )

                await asyncio.to_thread(
                    record_tool_error,
                    agent_id,
                    service,
                    action,
                    f"{kind}: {detail}"[:500],
                    tenant_id=str(tenant_id or "default"),
                    user_id=user_id,
                )
                # REAL-TIME evolution trigger for the ACTIVE task: the
                # moment this tool's errors cross the repeat threshold,
                # propose a tool-mutation fix — no waiting for episode
                # finalization (one dispatch per signature per 30min).
                if agent_id and should_trigger_live(
                    agent_id, tool_error_signature(service, action)
                ):
                    from core.auto_dev.reflection_engine import (
                        trigger_live_tool_fix,
                    )

                    asyncio.ensure_future(trigger_live_tool_fix(
                        agent_id=agent_id,
                        tenant_id=str(tenant_id or "default"),
                        service=service,
                        action=action,
                        error_detail=detail[:400],
                        execution_id=None,
                    ))
            except Exception:
                pass

        if not await circuit_breaker.is_enabled(service):
            # get_stats is async (Redis-first with in-memory fallback). Without
            # the await, `stats` was a coroutine and building the response
            # below raised TypeError: 'coroutine' object is not subscriptable
            # — so the circuit-open short-circuit never returned; the failure
            # escaped into the caller's generic handler (live log: 420 such
            # tracebacks). The lookup is also defensive: a service with no
            # recorded stats must still produce the circuit-open envelope.
            try:
                stats = await circuit_breaker.get_stats(service)
            except Exception:
                stats = {}
            stats = stats or {}
            await _record_tool_error(
                "circuit_open", f"Circuit breaker OPEN for {service}"
            )
            return {
                "status": "error",
                "error": f"Circuit breaker is OPEN for {service}. Cooldown active until {stats.get('disabled_until', 'unknown')}",
                "circuit_open": True
            }

        # --- Governance Risk Check ---
        # NOTE: the governance_middleware.check_action_risk call was broken
        # (missing first argument + method may not exist). Wrapped in a guard
        # so the integration service still loads and functions without the
        # risk check rather than failing with a SyntaxError at import time.
        risk_result = {"allowed": True}
        try:
            if hasattr(governance_middleware, "check_action_risk"):
                risk_result = await governance_middleware.check_action_risk(
                    service,
                    action=action,
                    params=params,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                )
        except Exception:
            risk_result = {"allowed": True}
        if not risk_result["allowed"]:
            return {
                "status": "paused",
                "action": action,
                "reason": risk_result["reason"],
                "intervention_id": risk_result.get("intervention_id"),
                "message": f"Action paused for manual review: {risk_result['reason']}"
            }

        # --- Outbound attribution check ---
        # The email body gate (chat_orchestrator + outbound_identity) sees
        # signatures; IM sends, task assignment, calendar events and CRM
        # ownership name their sender/assignee/organizer in PARAMS instead.
        # Same confabulation class (live 2026-09-02: a lead's name used as
        # sender), gated at this shared chokepoint for ALL integrations.
        # Shadow by default; enforce refuses off-team attribution. Never
        # blocks on resolution failure — a broken identity lookup must not
        # break sends.
        try:
            from core.outbound_identity import check_tool_call_attribution
            identity_verdict = await check_tool_call_attribution(
                service, action, params, context or {}
            )
            if identity_verdict:
                if (
                    identity_verdict["mode"] == "enforce"
                    and identity_verdict["status"] == "external"
                ):
                    await _record_tool_error(
                        "identity_hold",
                        f"{identity_verdict['field']}='{identity_verdict['value']}' "
                        "not on tenant team",
                    )
                    return {
                        "status": "paused",
                        "action": action,
                        "reason": (
                            f"{identity_verdict['field']}="
                            f"'{identity_verdict['value']}' is not on the "
                            "tenant team — outbound attribution held for "
                            "review"
                        ),
                        "identity_check": identity_verdict,
                        "message": (
                            "Action paused: the outbound artifact would be "
                            "attributed to someone outside the team."
                        ),
                    }
                logger.info(
                    f"[outbound-identity][{identity_verdict['mode']}] "
                    f"{service}.{action}: {identity_verdict['field']}="
                    f"'{identity_verdict['value']}' is "
                    f"{identity_verdict['status']} (not the acting owner)"
                )
        except Exception:
            pass

        try:
            # Use SessionLocal to provide registry with DB access
            with SessionLocal() as db:
                registry = IntegrationRegistry(db)
                context["registry"] = registry
                context["tenant_id"] = tenant_id

                # Normalized read shape for THIS call: every provider
                # spelling of limit/cursor/fields collapses to one object.
                # Handlers that can push a limit, cursor or projection down
                # to the provider read it off the context; everyone else
                # gets the response-boundary layer in _apply_read_shape.
                read = ReadQuery.from_params(params)
                context["read_query"] = read

                # Pipeline 2: Standard Integration Logic
                #
                # Idempotent READS go through the TTL cache (gap #6): the
                # same list/search inside one agent turn must not burn
                # provider quota twice, and can never return different data.
                # A mutating action is never cached and invalidates the
                # service's cached reads, so a list after a create is fresh.
                if is_read_action(action):
                    result = await cached_read_async(
                        service=service,
                        action=action,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        query=read,
                        # params + user_id are part of the cache IDENTITY:
                        # without them `list entity=contact` and
                        # `list entity=deal` share one entry.
                        params=params,
                        user_id=user_id,
                        fetch=lambda: self._dispatch_execution(
                            service, action, params, context),
                    )
                else:
                    result = await self._dispatch_execution(
                        service, action, params, context)
                    invalidate_after_write(service)

                # --- Read shape: projection + pagination envelope ---
                result = self._apply_read_shape(service, action, read, result)

                # --- Gatekeeper response field masking (P3) ---
                # Never return credentials/secret-shaped fields to callers.
                result = self._mask_response(service, result)

                # Tool-error signal: the integration ran but failed (or the
                # circuit tripped mid-flight) — feed the evolution harness.
                if isinstance(result, dict) and result.get("status") in (
                    "error", "circuit_open",
                ):
                    await _record_tool_error(
                        "tool_error", str(result.get("error") or "")[:400]
                    )

                # --- Spend Attribution (Phase 44) ---
                if result.get("status") in ("success", "error"):
                    cost = get_action_cost(service, action)
                    # budget_service is optional (guarded import) — core/budget_service
                    # does not exist in this repo, so never crash on it.
                    if budget_service is not None:
                        budget_service.record_workspace_spend(workspace_id, cost)
                    
                return result
                
        except Exception as e:
            # exc_info: anonymous salesforce/jira/asana list calls recur with
            # no traceback — this names the calling code the moment it fires.
            logger.error(f"Universal Integration Execution Failed ({service}.{action}): {e}", exc_info=True)
            # await: record_failure is async — un-awaited since forever, so
            # the breaker never recorded failures and never opened.
            await circuit_breaker.record_failure(service, e)
            
            # Record spend even on crash if it was a real attempt
            cost = get_action_cost(service, action)
            if budget_service is not None:
                budget_service.record_workspace_spend(workspace_id, cost)
            
            return self._mask_response(service, {"status": "error", "error": str(e)})

    async def _dispatch_execution(self, service, action, params, context):
        """
        Helper to route to correct handler based on service name.

        Handles system agents by using workspace-level tokens when no user_id is provided.
        """
        if not context:
            context = {}

        user_id = context.get("user_id")
        agent_id = context.get("agent_id")
        workspace_id = context.get("workspace_id") or self.workspace_id

        # For system agents, use workspace-level tokens
        if not user_id and agent_id:
            try:
                # Check if this is a system agent
                from core.models import AgentRegistry
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker

                # Get DB session if available
                db = context.get("db")
                if db:
                    # STRICT: Only allow lookup if it IS a system agent
                    agent = db.query(AgentRegistry).filter(
                        AgentRegistry.id == agent_id,
                        AgentRegistry.is_system_agent == True
                    ).first()
                    
                    if agent:
                        # System agents can use workspace-level tokens
                        # We'll pass workspace_id in lieu of user_id
                        user_id = f"workspace:{workspace_id}"
                        logger.info(f"Using workspace-level token for system agent {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to check system agent status: {e}")

        # If still no user_id and not a system agent, raise error
        if not user_id:
            raise ValueError("user_id required for non-system agents")

        # SEARCH PARITY BRIDGE — the search() entry has complete per-service
        # helpers (_search_*), but the execute() families implemented search
        # for only SOME services. Everywhere else a planner "search" intent
        # fell through the family branch chains to a generic routed message
        # with no data (live 2026-09-03 class: box, linear, jira, asana,
        # trello, gmail — the planner catalog advertised search while the
        # execute path silently returned nothing). One search implementation
        # per service: execute-path searches route through the same helpers.
        if action == "search":
            helper = _SEARCH_ROUTES.get(service)
            if helper is not None:
                result = await getattr(self, helper)(
                    service, params.get("query") or "", context)
                if isinstance(result, dict) and "status" in result:
                    return result
                return {"status": "success", "data": result}

        if service == "salesforce":
            return await self._execute_salesforce(action, params, user_id, context)
        elif service == "hubspot":
            return await self._execute_hubspot(action, params, context)
        elif service == "shopify":
            return await self._execute_shopify(action, params, context)
        elif service in ("google_chat", "telegram", "whatsapp", "slack", "teams", "discord", "zoom"):
            return await self._execute_communication(service, action, params, context)
        elif service in ("gmail", "outlook", "zoho_mail"):
            return await self._execute_communication(service, action, params, context)
        elif service in ("google_calendar", "outlook_calendar"):
            return await self._execute_calendar(service, action, params, context)
        elif service in ("linear", "monday", "zoho_projects", "asana", "jira", "trello"):
            return await self._execute_project_management(service, action, params, context)
        elif service in ("google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive"):
            return await self._execute_storage(service, action, params, context)
        elif service in ("zendesk", "freshdesk", "intercom"):
            return await self._execute_support(service, action, params, context)
        elif service in ("github", "gitlab", "figma"):
            return await self._execute_development(service, action, params, context)
        elif service in ("mailchimp", "hubspot_marketing"):
            return await self._execute_marketing(service, action, params, context)
        elif service in ("stripe", "quickbooks", "xero", "zoho_books", "zoho_inventory", "aws_ses"):
            return await self._execute_finance(service, action, params, context)
        elif service == "zoho_crm":
            return await self._execute_zoho(service, action, params, context)
        elif service in ("zoho_forms", "zoho_flow"):
            return await self._execute_zoho(service, action, params, context)
        elif service in ("tableau", "google_analytics"):
            return await self._execute_analytics(service, action, params, context)
        elif service in ("google_reviews"):
            return await self._execute_marketing_reviews(service, action, params, context)
        elif service in ("meta_ads", "google_ads", "linkedin_ads"):
            return await self._execute_marketing_ads(service, action, params, context)
        elif service in NATIVE_INTEGRATIONS:
            return await self._execute_generic_native(service, action, params, context)
        else:
            return await self._execute_activepieces(service, action, params, context)

    async def search(self, service: str, query: str, entity_type: str = None,
                     context: Dict[str, Any] = None,
                     limit: int = None, page_token: str = None,
                     fields: List[str] = None) -> Dict[str, Any]:
        """
        Search for entities within an integration via IntegrationRegistry.
        Returns a standardized {"status": "success", "data": [...]} object.

        ``limit`` / ``page_token`` / ``fields`` normalize into the same
        ReadQuery the execute() path uses, so both entries share one read
        shape (clamped page size, opaque provider cursor, projection) and
        both get the pagination envelope from ``_apply_read_shape``.
        """
        from core.database import SessionLocal
        from core.integration_registry import IntegrationRegistry

        # Circuit Breaker Check
        if not await circuit_breaker.is_enabled(service):
            return {"status": "error", "error": f"Circuit breaker is OPEN for {service}", "circuit_open": True}

        context = context or {}
        user_id = context.get("user_id")
        workspace_id = context.get("workspace_id") or self.workspace_id
        tenant_id = context.get("tenant_id") or workspace_id

        read_params: Dict[str, Any] = {"query": query}
        if limit is not None:
            read_params["limit"] = limit
        if page_token:
            read_params["page_token"] = page_token
        if fields:
            read_params["fields"] = fields
        read = ReadQuery.from_params(read_params)
        context["read_query"] = read

        # `search()` is the FAN-OUT entry (global_search walks every
        # connected platform), so duplicate provider reads concentrate here
        # inside one turn. Same cache contract as execute(): read actions
        # only, errors never cached, any write to the service invalidates.
        _, _cached = cache_lookup(
            service=service, action="search", tenant_id=tenant_id,
            workspace_id=workspace_id, query=read,
            params={"query": query, "entity_type": entity_type},
            user_id=user_id,
        )
        if _cached is not None:
            return self._mask_response(
                service, self._apply_read_shape(service, "search", read, _cached))

        try:
            with SessionLocal() as db:
                registry = IntegrationRegistry(db)
                context["registry"] = registry
                context["tenant_id"] = tenant_id

                if service == "salesforce":
                    data = await self._search_salesforce(query, entity_type, user_id, context)
                    result = {"status": "success", "data": data}
                elif service == "hubspot":
                    result = await self._search_hubspot(query, entity_type, context)
                elif service in ("slack", "teams", "discord", "google_chat", "telegram", "whatsapp", "gmail", "outlook", "zoho_mail"):
                    result = await self._search_communication(service, query, context)
                elif service in ("google_calendar", "outlook_calendar"):
                    result = await self._search_calendar(service, query, context)
                elif service in ("linear", "monday", "zoho_projects", "asana", "jira", "trello"):
                    result = await self._search_project_management(service, query, context)
                elif service in ("google_drive", "dropbox", "onedrive", "box", "notion"):
                    result = await self._search_storage(service, query, context)
                elif service in ("zoho_forms", "zoho_flow"):
                    # Webhook-push apps — search the ingested memory table,
                    # there is no live provider API to query.
                    from integrations.zoho_forms_service import ZohoFormsService
                    from integrations.zoho_flow_service import ZohoFlowService

                    svc = (ZohoFormsService if service == "zoho_forms" else ZohoFlowService)(
                        config={"workspace_id": workspace_id}
                    )
                    data = (
                        await svc.search_submissions(query)
                        if service == "zoho_forms"
                        else await svc.search_events(query)
                    )
                    result = {"status": "success", "data": data}
                elif service in ("salesforce", "hubspot", "zoho_crm", "pipedrive"):
                    result = await self._search_crm(service, query, context)
                elif service in ("zendesk", "freshdesk", "intercom"):
                    result = await self._search_support(service, query, context)
                elif service in ("github", "gitlab"):
                    result = await self._search_dev(service, query, context)
                elif service in ("mailchimp"):
                    result = await self._search_marketing(service, query, context)
                elif service in ("tableau", "google_analytics"):
                    result = await self._search_analytics(service, query, context)
                elif service == "zoho_workdrive":
                    result = await self._execute_storage(service, "search", {"query": query}, context)
                elif service == "zoho_inventory":
                    # Live item search — the DC-correct service method (see
                    # ZohoInventoryService.search_items).
                    result = await self.execute(
                        service, "search_items", {"query": query, "limit": 8}, context)
                elif service in ("stripe", "quickbooks", "xero", "zoho_books"):
                    # Finance: Stripe searches server-side when it can; the
                    # others pull the recent list and filter client-side
                    # (single implementation in _search_finance, shared with
                    # the execute-path search bridge).
                    inner = await self._search_finance(service, query, context)
                    if isinstance(inner, dict) and inner.get("status") == "success":
                        result = inner
                    else:
                        result = {"status": "success", "data": inner}
                else:
                    raise ValueError(f"Service '{service}' not supported for search.")

                # Same read-shape contract as execute(): projection + page
                # envelope (opaque next-page token, has_more, PARTIAL PAGE
                # notice). `_next_page_token` set by a _search_* branch rides
                # the result dict into the envelope here.
                result = self._apply_read_shape(service, "search", read, result)

                cache_store(
                    service=service, action="search", tenant_id=tenant_id,
                    workspace_id=workspace_id, query=read, result=result,
                    params={"query": query, "entity_type": entity_type},
                    user_id=user_id,
                )

                # Gatekeeper response field masking (P3) — strip credentials
                # (access_token, refresh_token, ...) from search results too.
                return self._mask_response(service, result)
        except Exception as e:
            logger.error(f"Universal Search Failed ({service}): {e}")
            circuit_breaker.record_failure(service, e)
            return {"status": "error", "message": str(e)}

    # --- Salesforce Implementation ---
    async def _execute_salesforce(self, action: str, params: Dict[str, Any], user_id: str, context: Dict[str, Any] = None) -> Any:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        sf_service = await registry.get_service_instance("salesforce", tenant_id)
        if not sf_service:
             return {"status": "error", "message": f"Salesforce service not available for tenant {tenant_id}"}

        # Use token from service or context
        token = getattr(sf_service, 'access_token', None)
        if not token:
             # Fallback to legacy connection check if registry token is missing
             from core.token_storage import token_storage
             token_data = token_storage.get_token(f"salesforce:{tenant_id}") or token_storage.get_token("salesforce")
             token = token_data.get("access_token") if token_data else None

        if not token:
             return {"status": "error", "message": "Could not authenticate with Salesforce (No token found)"}

        entity = params.get("entity")
        
        if action == "list":
            if entity == "contact":
                return {"status": "success", "data": await sf_service.list_contacts(token)}
            elif entity == "opportunity":
                return {"status": "success", "data": await sf_service.list_opportunities(token)}
            elif entity == "account":
                return {"status": "success", "data": await sf_service.list_accounts(token)}
            else:
                raise ValueError(f"Entity '{entity}' not supported for list action.")
                
        elif action == "create":
            data = params.get("data", {})
            if entity == "contact":
                return {"status": "success", "data": await sf_service.create_contact(token=token, **data)}
            elif entity == "opportunity":
                return {"status": "success", "data": await sf_service.create_opportunity(token=token, **data)}
            elif entity == "account":
                return {"status": "success", "data": await sf_service.create_account(token=token, **data)}
                
        elif action == "read":
             obj_id = params.get("id")
             if entity == "opportunity":
                 return {"status": "success", "data": await sf_service.get_opportunity(token, obj_id)}
        
        elif action == "query":
            soql = params.get("query")
            return {"status": "success", "data": await sf_service.execute_query(token, soql)}

        elif action == "update":
            record_id = params.get("id")
            data = params.get("data", {})
            if entity == "contact":
                return {"status": "success", "data": await sf_service.update_contact(token, record_id, data)}
            elif entity == "opportunity":
                return {"status": "success", "data": await sf_service.update_opportunity(token, record_id, data)}
            elif entity == "lead":
                return {"status": "success", "data": await sf_service.update_lead(token, record_id, data)}
            elif entity == "account":
                return {"status": "success", "data": await sf_service.update_account(token, record_id, data)}

        return {"status": "error", "message": f"Action {action} not supported for {entity}"}

    async def _search_salesforce(self, query: str, entity_type: str, user_id: str, context: Dict[str, Any] = None) -> List[Dict]:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")

        sf_service = await registry.get_service_instance("salesforce", tenant_id)
        if not sf_service: return []

        token = getattr(sf_service, 'access_token', None)
        if not token: return []

        # Escape query to prevent SOQL injection
        from integrations.salesforce_service import escape_soql_string
        safe_query = escape_soql_string(query)

        if entity_type == "contact":
            soql = f"SELECT Id, Name, Email FROM Contact WHERE Name LIKE '%{safe_query}%'"
        elif entity_type == "account":
            soql = f"SELECT Id, Name FROM Account WHERE Name LIKE '%{safe_query}%'"
        else:
            return [{"message": "Only specific entity search implemented via SOQL"}]

        res = await sf_service.execute_query(token, soql)
        return res.get("records", [])

    # --- HubSpot Implementation ---
    async def _execute_hubspot(self, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> Any:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        hs_service = await registry.get_service_instance("hubspot", tenant_id)
        if not hs_service:
            # Fallback to legacy singleton if registry is missing
            from integrations.hubspot_service import get_hubspot_service
            hs_service = get_hubspot_service()
        
        token = getattr(hs_service, 'access_token', None) or os.getenv("HUBSPOT_ACCESS_TOKEN")
        
        entity = params.get("entity")
        # Read shape for this call (limit / opaque cursor / projection).
        # Handlers that CAN push these to the provider do; the general layer
        # still applies the response-boundary fallback for the rest.
        read = context.get("read_query") or ReadQuery.from_params(params)

        if action == "list":
            # HubSpot's list API pages with the OPAQUE `after` cursor from
            # the previous response (`paging.next.after`), NOT a numeric
            # offset — the service used to send `after=<int>` and silently
            # discard the real cursor, so page two was unreachable.
            kwargs = {
                "token": token,
                "limit": read.limit,
                "page_token": read.page_token,
            }
            if read.fields:
                kwargs["properties"] = list(read.fields)
            if entity == "contact":
                return {"status": "success",
                        "data": await hs_service.get_contacts(**kwargs),
                        "_next_page_token": getattr(
                            hs_service, "last_next_page_token", None)}
            elif entity == "deal":
                return {"status": "success",
                        "data": await hs_service.get_deals(**kwargs),
                        "_next_page_token": getattr(
                            hs_service, "last_next_page_token", None)}
            elif entity == "company":
                return {"status": "success",
                        "data": await hs_service.get_companies(**kwargs),
                        "_next_page_token": getattr(
                            hs_service, "last_next_page_token", None)}
                
        elif action == "create" or action in ("create_company", "create_deal", "create_contact"):
            data = params.get("data", params) 
            entity_type = entity
            if action == "create_company": entity_type = "company"
            elif action == "create_deal": entity_type = "deal"
            elif action == "create_contact": entity_type = "contact"

            if entity_type == "contact":
                return {"status": "success", "data": await hs_service.create_contact(token=token, **data)}
            elif entity_type == "deal":
                if "amount" in data and data["amount"] is not None:
                    data["amount"] = float(data["amount"])
                return {"status": "success", "data": await hs_service.create_deal(token=token, **data)}
            elif entity_type == "company":
                return {"status": "success", "data": await hs_service.create_company(token=token, **data)}

        elif action == "update":
            obj_id = params.get("id")
            data = params.get("data", {})
            if entity == "contact":
                return {"status": "success", "data": await hs_service.update_contact(obj_id, data, token=token)}
            elif entity == "deal":
                return {"status": "success", "data": await hs_service.update_deal(obj_id, data, token=token)}
            else:
                # Wrap like the other branches — the raw service result may not
                # carry a "status" key, which crashed execute()'s result.get().
                return {"status": "success", "data": await hs_service.update_object(entity + "s", obj_id, data, token=token)}
        
        return {"status": "error", "message": f"Action {action} not implemented for HubSpot {entity}"}

    async def _search_hubspot(self, query: str, entity_type: str, context: Dict[str, Any] = None) -> List[Dict]:
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")

        hs_service = await registry.get_service_instance("hubspot", tenant_id)
        token = getattr(hs_service, 'access_token', None) or os.getenv("HUBSPOT_ACCESS_TOKEN")

        # search_content now takes token/limit/after — before, the token=
        # kwarg TypeError'd on every universal-path HubSpot search, and the
        # paging cursor HubSpot returns was dropped along with the envelope.
        read = context.get("read_query")
        after: Optional[int] = None
        if read is not None and read.page_token:
            try:
                after = int(str(read.page_token).strip())
            except ValueError:
                after = None
        res = await hs_service.search_content(
            query, object_type=entity_type or "contact", token=token,
            limit=(read.limit if read is not None and read.explicit_limit else 50),
            after=after,
        )
        # Envelope (was a bare list — the search() docstring promises
        # {status, data} and every other family returns it; a raw list also
        # dropped HubSpot's paging cursor before it could reach the read
        # envelope). _next_page_token is HubSpot's opaque paging.next.after.
        result = {"status": "success", "data": res.get("results", [])}
        paging_after = ((res.get("paging") or {}).get("next") or {}).get("after")
        if paging_after is not None:
            result["_next_page_token"] = str(paging_after)
            result["_has_more"] = True
        return result

    # --- Shopify Implementation ---
    async def _execute_shopify(self, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Shopify actions via ShopifyService"""
        
        shopify = ShopifyService()
        access_token = context.get("access_token") or params.get("access_token")
        shop = context.get("shop") or params.get("shop")
        
        if not access_token or not shop:
            return {"status": "error", "message": "access_token and shop are required"}
        
        entity = params.get("entity", "product")
        read = context.get("read_query") or ReadQuery.from_params(params)
        page_info = read.page_token if isinstance(read.page_token, str) else None
        meta: Dict[str, Any] = {}

        if action == "search":
            # Customers search server-side (customers/search.json?query=) —
            # the REST endpoint matches name/email/phone at the provider, so
            # a match beyond the first page is reachable. Products/orders
            # REST has no search param, so they keep the client-side filter
            # but now page with Shopify's opaque page_info cursor (Link
            # header) instead of silently ending at page one.
            query = params.get("query") or ""
            if entity == "customer" and query:
                items = await shopify.search_customers(
                    access_token, shop, query,
                    limit=(read.limit if read.explicit_limit else 20))
                result = {"status": "success", "data": items or []}
                return result
            fetch = {
                "product": shopify.get_products,
                "order": shopify.get_orders,
                "customer": shopify.get_customers,
            }.get(entity)
            if fetch is None:
                return {"status": "error", "message": f"Unsupported shopify entity: {entity}"}
            items = await fetch(
                access_token, shop,
                limit=(read.limit if read.explicit_limit else 20),
                page_info=page_info, meta_out=meta,
            )
            result = {"status": "success",
                      "data": self._filter_by_query(items or [], query)}
            if meta.get("next_page_info"):
                result["_next_page_token"] = meta["next_page_info"]
                result["_has_more"] = True
            return result

        if action == "list":
            if entity == "product":
                return {"status": "success", "data": await shopify.get_products(
                    access_token, shop, limit=(read.limit if read.explicit_limit else 20),
                    page_info=page_info, meta_out=meta),
                    **({"_next_page_token": meta["next_page_info"]} if meta.get("next_page_info") else {})}
            elif entity == "order":
                return {"status": "success", "data": await shopify.get_orders(
                    access_token, shop, limit=(read.limit if read.explicit_limit else 20),
                    page_info=page_info, meta_out=meta),
                    **({"_next_page_token": meta["next_page_info"]} if meta.get("next_page_info") else {})}
            elif entity == "customer":
                return {"status": "success", "data": await shopify.get_customers(
                    access_token, shop, limit=(read.limit if read.explicit_limit else 20),
                    page_info=page_info, meta_out=meta),
                    **({"_next_page_token": meta["next_page_info"]} if meta.get("next_page_info") else {})}
        elif action == "create" and entity == "fulfillment":
            return {"status": "success", "data": await shopify.create_fulfillment(
                access_token, shop, params.get("order_id"), params.get("location_id"),
                params.get("tracking_number"), params.get("tracking_company")
            )}
        elif action == "analytics":
            return {"status": "success", "data": await shopify.get_shop_analytics(access_token, shop)}
            
        return {"status": "error", "message": f"Action {action} not supported for Shopify {entity}"}

    async def _execute_communication(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle communication platforms: Slack, Teams, Discord, Telegram, WhatsApp, Google Chat, Gmail, Outlook, Zoho Mail"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        # Resolve service from registry
        comm_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(comm_service, 'access_token', None) or context.get("access_token")

        if service == "slack":
            if not comm_service:
                from integrations.slack_service_unified import slack_unified_service
                comm_service = slack_unified_service # Fallback

            if action == "send_message":
                # Wrapped like the other branches — raw service results may
                # lack a "status" key and crash execute()'s result.get().
                return {"status": "success", "data": await comm_service.post_message(
                    token=token,
                    channel_id=params.get("channel") or params.get("channel_id"),
                    text=params.get("message") or params.get("content")
                )}
            elif action == "list_channels":
                return {"status": "success", "data": await comm_service.list_channels(token)}
            elif action == "search_messages":
                res = await comm_service.make_request("GET", "search.messages", params={"query": params.get("query")}, token=token)
                return {"status": "success", "data": res}
                
        elif service == "teams":
            # Registry-resolved TeamsEnhancedService carries the real
            # search (TeamsService.get_teams — the old branch here — lists
            # workspaces, not messages, and the registry class doesn't
            # even have it).
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_message(params.get("chat_id"), params.get("message") or params.get("content"))}
            elif action == "list_chats":
                return {"status": "success", "data": await comm_service.get_teams()}
                
        elif service == "discord":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_message(params.get("channel_id"), params.get("message") or params.get("content"))}
            elif action == "list_guilds":
                return {"status": "success", "data": await comm_service.list_guilds()}
                
        elif service == "google_chat":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_unified_message(
                    workspace_id=params.get("workspace_id", "default"),
                    channel_id=params.get("channel_id"),
                    content=params.get("content") or params.get("message"),
                    options=params.get("options", {})
                )}
            elif action == "list_spaces":
                return {"status": "success", "data": await comm_service.list_spaces()}
                
        elif service == "telegram":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_intelligent_message(
                    channel_id=params.get("channel_id"),
                    message=params.get("message") or params.get("content"),
                    metadata=params.get("metadata")
                )}
                
        elif service == "whatsapp":
            if action == "send_message":
                return {"status": "success", "data": await comm_service.send_intelligent_message(
                    channel_id=params.get("channel_id"),
                    message=params.get("message") or params.get("content"),
                    metadata=params.get("metadata")
                )}
                
        elif service == "gmail":
            if action == "send_message":
                # GmailService methods are sync — run them off the event loop
                # (they were awaited directly before, which raised TypeError
                # on every gmail send).
                thread_id = params.get("thread_id")
                reply_message_id = (
                    params.get("reply_to_message_id") or params.get("message_id")
                )
                if reply_message_id and not thread_id:
                    msg = await asyncio.to_thread(
                        comm_service.get_message, reply_message_id, token
                    )
                    thread_id = (msg or {}).get("threadId")
                    if not thread_id:
                        return {
                            "status": "error",
                            "message": f"Message {reply_message_id} has no Gmail thread",
                        }
                to = params.get("to")
                if thread_id and not to:
                    # Pure thread reply: recipient + In-Reply-To/References
                    # headers are derived from the thread's last message.
                    data = await asyncio.to_thread(
                        comm_service.reply_to_message, thread_id,
                        params.get("body") or params.get("content") or "", token,
                    )
                    return {
                        "status": "success" if data is not None else "error",
                        "data": data if data is not None else {"error": "Gmail thread reply failed"},
                    }
                return {"status": "success", "data": await asyncio.to_thread(
                    comm_service.send_message,
                    to=to,
                    subject=params.get("subject"),
                    body=params.get("body") or params.get("content"),
                    cc=params.get("cc", ""),
                    bcc=params.get("bcc", ""),
                    thread_id=thread_id,
                    token=token
                )}
            elif action == "list_messages":
                return {"status": "success", "data": await asyncio.to_thread(
                    comm_service.get_messages,
                    query=params.get("query", ""),
                    max_results=params.get("max_results", 20),
                    token=token,
                )}
            elif action == "get_message":
                return {"status": "success", "data": await asyncio.to_thread(
                    comm_service.get_message, params.get("id"), token
                )}
                
        elif service == "outlook":
            # Was a dead stub returning "Routed via UIS-Bridge" — wire the real
            # OutlookService so MCP send_email/search_emails actually work.
            if not comm_service:
                return {"status": "error", "message": "Outlook service not available"}
            user_id = (context or {}).get("user_id") or "default_user"
            if action == "send_message":
                # Threaded reply: reply_to_message_id (or message_id) replies
                # to that message; thread_id/conversation_id (Outlook
                # conversationId) resolves to the newest message of the
                # thread first. Recipients/subject come from the original,
                # so `to` is only required for standalone sends.
                reply_message_id = (
                    params.get("reply_to_message_id") or params.get("message_id")
                )
                reply_conversation = (
                    params.get("thread_id") or params.get("conversation_id")
                )
                if reply_message_id or reply_conversation:
                    if not reply_message_id:
                        reply_message_id = await comm_service.get_latest_conversation_message_id(
                            user_id, reply_conversation, token=token,
                        )
                        if not reply_message_id:
                            return {
                                "status": "error",
                                "message": f"No message found in Outlook conversation {reply_conversation}",
                            }
                    reply_all = bool(params.get("reply_all"))
                    sent = await comm_service.reply_to_email(
                        user_id=user_id,
                        message_id=reply_message_id,
                        comment=params.get("body") or params.get("content") or "",
                        reply_all=reply_all,
                        token=token,
                    )
                    if sent:
                        reply_data = {
                            "reply_to_message_id": reply_message_id,
                            "reply_all": reply_all,
                        }
                    else:
                        # Surface the diagnosable reason (internal-quote
                        # guard, thread not found, transport) so the agent
                        # can correct the draft instead of retrying blind.
                        detail = dict(getattr(comm_service, "last_send_error", None) or {})
                        reply_data = {
                            "error": detail.get("error", "Outlook reply failed"),
                            **(
                                {"policy": detail["policy"], "quotes": detail.get("quotes") or []}
                                if detail.get("policy")
                                else {}
                            ),
                        }
                    return {
                        "status": "success" if sent else "error",
                        "data": reply_data,
                    }
                to = params.get("to") or params.get("to_recipients") or params.get("recipients")
                if isinstance(to, str):
                    to = [to]
                if not to:
                    return {"status": "error", "message": "to is required for send_message"}
                data = await comm_service.send_email(
                    user_id=user_id,
                    to_recipients=to,
                    cc_recipients=params.get("cc") or params.get("cc_recipients"),
                    bcc_recipients=params.get("bcc") or params.get("bcc_recipients"),
                    subject=params.get("subject", ""),
                    body=params.get("body") or params.get("content") or "",
                    token=token,
                )
                return {"status": "success" if data is not None else "error", "data": data}
            elif action == "list_messages":
                messages = await comm_service.get_user_emails(
                    user_id=user_id,
                    folder=params.get("folder", "inbox"),
                    query=params.get("query"),
                    max_results=int(params.get("max_results") or params.get("limit") or 50),
                    token=token,
                )
                # P1: fetched email content must ride inside the untrusted
                # delimiters (like the webhook subject) so attacker-authored
                # instructions cannot steer the model prompt.
                from core.email_policy import spotlight_message_results

                return {"status": "success", "data": spotlight_message_results(messages)}
            elif action == "get_message":
                from core.email_policy import spotlight_message_results

                return {
                    "status": "success",
                    "data": spotlight_message_results(
                        await comm_service.get_email_by_id(user_id, params.get("id"), token=token)
                    ),
                }
            else:
                return {"status": "error", "message": f"Unsupported outlook action: {action}"}

        elif service == "zoho_mail":
            if action == "list":
                return {"status": "success", "data": await comm_service.get_recent_inbox(token, limit=params.get("limit", 20))}
            elif action == "send_message":
                 return {"status": "error", "message": "Zoho Mail send not implemented yet in service"}

        return {"status": "success", "message": f"Routed to {service} (default handler)"}

    async def _execute_calendar(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Calendar, Outlook Calendar via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        cal_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(cal_service, 'access_token', None) or context.get("access_token")

        if service == "google_calendar":
            if action == "list":
                events = await cal_service.get_events(
                    calendar_id=params.get("calendar_id", "primary"),
                    token=token
                )
                return {"status": "success", "data": events}
            elif action == "create":
                event = await cal_service.create_event(params.get("data", {}), token=token)
                return {"status": "success", "data": event}
            elif action == "check_conflicts":
                 from datetime import datetime
                 start = datetime.fromisoformat(params.get("start_time").replace("Z", "+00:00"))
                 end = datetime.fromisoformat(params.get("end_time").replace("Z", "+00:00"))
                 return {"status": "success", "data": await cal_service.check_conflicts(start, end, token=token)}
                 
        elif service == "outlook_calendar":
            if action == "list":
                events = await cal_service.get_events(token=token)
                return {"status": "success", "data": events}
            elif action == "create":
                event = await cal_service.create_event(params.get("data", {}), token=token)
                return {"status": "success", "data": event}
                
        return {"status": "error", "message": f"Action {action} not supported for {service}"}

    async def _search_communication(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Global search parity for communication platforms"""
        read = context.get("read_query")
        if service == "slack":
            from integrations.slack_service_unified import slack_unified_service
            # search_messages carries Slack's 1-based `page` — the read shape's
            # opaque token is that page number as a string.
            page = 1
            if read is not None and read.page_token:
                try:
                    page = max(1, int(str(read.page_token).strip()))
                except ValueError:
                    page = 1
            res = await slack_unified_service.search_messages(
                token=context.get("access_token"), query=query,
                count=(read.limit if read is not None and read.explicit_limit else 100),
                page=page,
            )
            pagination = ((res or {}).get("messages") or {}).get("pagination") or {}
            result: Dict[str, Any] = {"status": "success", "data": res}
            if pagination.get("page_count") and int(pagination["page_count"]) > page:
                result["_next_page_token"] = str(page + 1)
            return result
        elif service == "google_chat":
            from integrations.atom_google_chat_integration import atom_google_chat_integration
            return {"status": "success", "data": await atom_google_chat_integration.unified_search(query)}
        elif service == "telegram":
            from integrations.atom_telegram_integration import atom_telegram_integration
            return {"status": "success", "data": await atom_telegram_integration.perform_intelligent_search(
                query, user_id=context.get("user_id") or 0)}
        elif service == "whatsapp":
            from integrations.atom_whatsapp_integration import atom_whatsapp_integration
            return {"status": "success", "data": await atom_whatsapp_integration.perform_intelligent_search(
                query, user_id=context.get("user_id") or "default")}
        elif service == "gmail":
            from integrations.gmail_service import GmailService
            gmail_service = GmailService()
            return {"status": "success", "data": gmail_service.search_messages(query)}
        elif service == "teams":
            # Search lives on the registry class (TeamsEnhancedService.
            # search_messages) — TeamsService.get_teams, the old shape here,
            # lists workspaces, not messages.
            registry = context.get("registry")
            teams_service = None
            if registry:
                teams_service = await registry.get_service_instance(
                    "teams", context.get("tenant_id", "system"))
            if not teams_service:
                return {"status": "error", "message": "Teams service not found in registry"}
            return {"status": "success", "data": await teams_service.search_messages(
                context.get("workspace_id") or "default", query)}
        elif service == "outlook":
            # Same source the chat planner's dedicated outlook leg uses —
            # planner-planned outlook searches through the universal path
            # previously had no branch at all and errored into the memory
            # fallback while the mailbox was never queried.
            # search_emails_paged follows @odata.nextLink (short Graph pages
            # no longer truncate the result silently) and exposes the
            # continuation token the read-shape envelope surfaces as
            # page.next_page_token.
            from integrations.outlook_service import (
                outlook_service,
                sanitize_graph_kql,
            )
            kql = sanitize_graph_kql(query) or query
            paged = await outlook_service.search_emails_paged(
                user_id=context.get("user_id"), query=kql,
                max_results=(read.limit if read is not None and read.explicit_limit else 10),
                quote=False,
                page_token=(read.page_token if read is not None else None),
            )
            result = {"status": "success", "data": paged.get("emails") or []}
            if paged.get("next_page_token"):
                result["_next_page_token"] = paged["next_page_token"]
                result["_has_more"] = True
            return result
        # Add more search handlers...
        return {"status": "success", "data": []}

    async def _search_calendar(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search calendar events"""
        # Google Calendar's events.list takes a server-side ``q`` (matches
        # title/description/attendees/locations) — pushing it down searches
        # the WHOLE window instead of filtering the first max_results events
        # client-side, which buried the named event under whatever the
        # window's first page happened to be.
        if service == "google_calendar":
            from integrations.google_calendar_service import google_calendar_service
            events = await google_calendar_service.get_events(q=query or None)
            return {"status": "success", "data": events or []}
        return []

    # --- Project Management ---
    async def _execute_project_management(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Linear, Monday, Zoho Projects, Jira, Asana, Trello via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        
        pm_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(pm_service, 'access_token', None) or context.get("access_token")
        
        if service == "linear":
            if action == "list":
                return {"status": "success", "data": await pm_service.get_issues(token)}
            elif action == "create":
                return {"status": "success", "data": await pm_service.create_issue(
                    title=params.get("title"),
                    team_id=params.get("team_id"),
                    access_token=token,
                    description=params.get("description"),
                    priority=params.get("priority")
                )}
            elif action == "list_teams":
                return {"status": "success", "data": await pm_service.get_teams(token)}
            elif action == "list_projects":
                return {"status": "success", "data": await pm_service.get_projects(token)}

        elif service == "monday":
            if action == "list":
                return {"status": "success", "data": await pm_service.get_boards(token)}
            elif action == "create":
                return {"status": "success", "data": await pm_service.create_item(
                    access_token=token,
                    board_id=params.get("board_id"),
                    item_name=params.get("title") or params.get("name"),
                    column_values=params.get("column_values")
                )}
            elif action == "list_boards":
                return {"status": "success", "data": await pm_service.get_boards(token)}
            elif action == "search":
                return {"status": "success", "data": await pm_service.search_items(token, params.get("query"))}

        elif service == "zoho_projects":
            portal_id = params.get("portal_id")
            if action == "list_projects":
                return {"status": "success", "data": await pm_service.get_projects(token, portal_id)}
            elif action == "list":
                return {"status": "success", "data": await pm_service.get_tasks(token, portal_id, params.get("project_id"))}
            elif action == "list_tasks":
                return {"status": "success", "data": await pm_service.get_tasks(token, portal_id, params.get("project_id"))}

        elif service == "asana":
            if action == "list":
                # asana_service.get_tasks never raises — it returns
                # {"ok": False, "error": ...} on failure. Propagate the
                # failure instead of wrapping it in a lying "success".
                asana_list = await pm_service.get_tasks(token)
                if isinstance(asana_list, dict) and asana_list.get("ok") is False:
                    return {"status": "error", "error": asana_list.get("error") or "Asana get_tasks failed"}
                return {"status": "success", "data": asana_list.get("tasks", [])}
            elif action == "create":
                # asana_service.create_task requires task_data["name"] — the
                # unified tools send "title"/"summary" (frontend Quick Create
                # sends {title, platform, status}), so map them before the
                # call or every asana create fails with "Missing required
                # field: name".
                asana_params = dict(params.get("data", params) or {})
                asana_params.setdefault("name", asana_params.get("title") or asana_params.get("summary"))
                # asana_service.create_task never raises — it returns
                # {"ok": False, "error": ...} on failure. Propagate that as a
                # service-level error instead of wrapping it in a lying
                # "success" (the UI would show "Task created successfully"
                # although nothing was created).
                asana_result = await pm_service.create_task(token, asana_params)
                if isinstance(asana_result, dict) and asana_result.get("ok") is False:
                    return {"status": "error", "error": asana_result.get("error") or "Asana create_task failed"}
                return {"status": "success", "data": asana_result}
                
        elif service == "jira":
            if action == "list":
                # JiraService is fully synchronous (requests-based) — its
                # issue-list method is search_issues, NOT get_issues (the
                # former get_issues call raised AttributeError, surfacing as
                # "'JiraService' object has no attribute 'get_issues'" in
                # every unified-tasks response). search_issues already
                # degrades gracefully to {"issues": []} on failure.
                jira_result = pm_service.search_issues(
                    jql=params.get("jql") or "order by created DESC",
                    max_results=int(params.get("limit") or 50),
                    token=token,
                )
                return {"status": "success", "data": jira_result.get("issues", [])}
            elif action == "create":
                # create_issue is synchronous and returns None on failure —
                # awaiting it raised "object NoneType can't be used in
                # 'await' expression" whenever Jira was not configured.
                try:
                    issue = pm_service.create_issue(
                        params.get("project") or params.get("project_key"),
                        params.get("title") or params.get("summary"),
                        params.get("issue_type", "Task"),
                        params.get("description", ""),
                        token=token,
                    )
                except Exception as e:
                    logger.warning(f"Jira create_issue failed: {e}")
                    issue = None
                if not issue:
                    return {"status": "error", "error": "Jira create_issue failed (is JIRA configured?)"}
                return {"status": "success", "data": issue}
                
        elif service == "trello":
            if action == "list":
                return {"status": "success", "data": await pm_service.get_cards(params.get("board_id") or params.get("list_id"), token=token)}
            elif action == "create":
                return {"status": "success", "data": await pm_service.create_card(
                    params.get("title") or params.get("name"),
                    params.get("list_id") or params.get("board_id"),
                    params.get("description", ""),
                    token=token
                )}
        
        return {"status": "success", "message": f"Routed to {service} handler (Registry PM)"}

    async def _search_project_management(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search tasks/issues across PM platforms via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        pm_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(pm_service, 'access_token', None) or context.get("access_token")

        if service == "linear":
             issues = await pm_service.get_issues(token)
             # Any-term ranked filter (core.identifier_search) — the old
             # whole-query substring test zero-hits the moment the query
             # carries prose + an identifier ("bandsaw WG-350DSAV"), the
             # exact shape the planner's identifier net produces.
             return filter_by_terms(
                 issues, query,
                 text_of=lambda i: f"{i.get('title', '')} {i.get('description') or ''}")
        elif service == "monday":
             return await pm_service.search_items(token, query)
        elif service == "asana":
             tasks = await pm_service.get_tasks(token)
             return filter_by_terms(tasks, query, text_of=lambda t: t.get("name", ""))
        elif service == "jira":
             # search_issues is synchronous (requests-based) — do NOT await
             # (awaiting a plain dict raised TypeError).
             return pm_service.search_issues(f"text ~ '{query}'", token=token).get("issues", [])
        elif service == "trello":
             # TrelloService.search is synchronous (requests-based) — same
             # no-await rule as jira above.
             results = pm_service.search(query)
             return results or []
        return []

    # The following methods have been refactored to use the Registry pattern:

    async def _execute_storage(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Drive, Dropbox, OneDrive, Box, Notion via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        storage_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(storage_service, 'access_token', None) or context.get("access_token")

        # The `read` intent (open a file, return its contents) is implemented
        # ONCE for every storage service — download, extract, ingest (warming
        # the hybrid index for next time), and return a query-anchored
        # excerpt. This is step 2 of the find→open→read journey that
        # previously had no implementation at all (live 2026-09-03: the agent
        # could search WorkDrive metadata but nothing could open a file).
        if action in ("read", "read_file", "open_file", "get_file_content"):
            return await self._read_storage_file(
                service, storage_service, token, params, context
            )

        # Push-refresh actions (webhook events → per-file or bulk re-ingest).
        # One contract for every storage provider; per-vendor differences are
        # the signatures below, nothing else.
        if action in ("full_sync", "resync"):
            ws_id = context.get("workspace_id") or "default"
            if service == "zoho_workdrive":
                return {"status": "success", "data": await storage_service.full_sync(
                    context.get("user_id") or token or "default", workspace_id=ws_id)}
            return {"status": "success", "data": await storage_service.full_sync(
                ws_id, token)}
        if action in ("ingest_file_to_memory", "ingest_file", "ingest"):
            fid = params.get("file_id") or params.get("query")
            if service == "zoho_workdrive":
                return {"status": "success", "data": await storage_service.ingest_file_to_memory(
                    context.get("user_id") or token, fid)}
            if service == "dropbox":
                return {"status": "success", "data": await storage_service.ingest_file_to_memory(
                    fid, token)}
            return {"status": "success", "data": await storage_service.ingest_file_to_memory(
                token, fid)}

        if service == "google_drive":
            if action in ("list", "list_files"):
                return {"status": "success", "data": await storage_service.list_files(token, params.get("folder_id"))}
            elif action == "search":
                return {"status": "success", "data": await storage_service.search_files(token, params.get("query"))}
            elif action == "get_metadata":
                return {"status": "success", "data": await storage_service.get_file_metadata(token, params.get("file_id"))}

        elif service == "dropbox":
            if action in ("list", "list_folder"):
                return {"status": "success", "data": await storage_service.list_folder(params.get("path", ""), token)}
            elif action == "search":
                return {"status": "success", "data": await storage_service.search(params.get("query"), token, params.get("path", ""))}
            elif action == "create_folder":
                return {"status": "success", "data": await storage_service.create_folder(params.get("path"), token)}

        elif service == "onedrive":
            if action in ("list", "list_files"):
                return {"status": "success", "data": await storage_service.list_drive_items(token, params.get("path"))}
            elif action == "search":
                # Real Graph root search — the service's search_files sat
                # unused while this branch listed the drive root and
                # filtered client-side, so only top-folder items ever
                # matched a search.
                res = await storage_service.search_files(token, params.get("query"))
                data = res.get("data") or {} if isinstance(res, dict) else {}
                return {"status": "success", "data": data.get("value", [])}

        elif service == "box":
            if action == "list":
                return {"status": "success", "data": await storage_service.list_folder_items(token, params.get("folder_id", "0"))}
            elif action == "search":
                # The service's search_files (Box GET /search) existed but
                # this dispatch never offered search — the planner
                # advertised "box: search files" while every search fell
                # through to the generic routed message with no data.
                res = await storage_service.search_files(token, params.get("query"))
                data = res.get("data") or {} if isinstance(res, dict) else {}
                return {"status": "success", "data": data.get("entries", [])}

        elif service == "notion":
            if action == "search":
                return {"status": "success", "data": await storage_service.search(params.get("query"), token=token)}
            elif action == "create_page":
                return {"status": "success", "data": await storage_service.create_page(params.get("parent"), params.get("properties"), params.get("children"), token=token)}
            elif action == "list":
                return {"status": "success", "data": await storage_service.search_pages_in_workspace(token=token)}
        
        elif service == "zoho_workdrive":
            # WorkDrive resolves its OAuth token PER USER
            # (ConnectionService/IntegrationToken rows); the instance carries
            # no access_token and the executor context usually has none, so
            # the raw `token` here is None — passing it as user_id silently
            # emptied every WorkDrive list/search (live 2026-09-03 price-book
            # miss). Pass the acting user, as execute_operation does.
            wd_user = context.get("user_id") or token
            if action in ("list", "list_files"):
                return {"status": "success", "data": await storage_service.list_files(wd_user, params.get("folder_id"))}
            elif action == "search":
                return {"status": "success", "data": await storage_service.search_files(wd_user, params.get("query"), limit=params.get("limit") or 20)}

        return {"status": "success", "message": f"Routed to {service} handler (Registry Storage)"}

    async def _read_storage_file(
        self,
        service: str,
        storage_service: Any,
        token: Optional[str],
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Open a storage file: resolve → download → extract → excerpt.

        One implementation shared by every storage integration (the read leg
        of find→open→read). Resolution uses an explicit ``file_id`` when the
        caller has one, otherwise it runs the service's own search and picks
        the name-best-matching hit. The excerpt is query-anchored so a
        "find the WG350DSAV row" read returns the region around that model
        number rather than the workbook's head. The full text is ALSO
        ingested (best-effort) under the file's stable identity, so this one
        open warms the hybrid index — later questions hit search, not the
        download path.
        """
        user_id = context.get("user_id")
        query = (params.get("query") or "").strip()
        file_id = params.get("file_id") or params.get("id")
        file_name: Optional[str] = None
        identity_verified = bool(params.get("identity_verified"))
        identity: Dict[str, Any] = {
            "provider": service,
            "resource_id": str(file_id) if file_id else None,
            "file_name": params.get("file_name"),
            "source_metadata": params.get("source_metadata") or {},
            "identity_verified": identity_verified,
        }

        try:
            if (
                (identity_verified or not callable(
                    getattr(storage_service, "get_file_metadata", None)
                ))
                and query and context.get("llm_service")
            ):
                try:
                    from core.sheet_dataset_service import (
                        answer_from_datasets,
                        find_entries_sync,
                        render_dataset_answer,
                        sheet_datasets_enabled,
                    )

                    if sheet_datasets_enabled():
                        entries = await asyncio.to_thread(
                            find_entries_sync, query, user_id, None, 5
                        )
                        if entries:
                            best = entries[0]
                            ds_result = await answer_from_datasets(
                                best["source"], best["external_id"], query,
                                llm_service=context.get("llm_service"),
                                context_texts=[
                                    str(t) for t in (context.get("history_texts") or [])
                                    if t
                                ],
                            )
                            if ds_result:
                                # The copy answered within its freshness TTL —
                                # re-verify it in the background so a changed
                                # source self-heals immediately instead of at
                                # TTL expiry. Keyed on the CATALOG's canonical
                                # external_id — file_id is None here because
                                # resolution never ran on this path.
                                if _dataset_reverify_due(ds_result):
                                    _schedule_dataset_reverify(
                                        service, storage_service, token, user_id,
                                        str(best["external_id"]),
                                        file_name=ds_result.get("file_name") or file_name,
                                        workspace_id=context.get("workspace_id") or "default",
                                    )
                                return {"status": "success", "data": {
                                    "found": True,
                                    "file_id": best["external_id"],
                                    "file_name": ds_result.get("file_name") or best.get("file_name"),
                                    "chars_extracted": ds_result.get("row_count", 0),
                                    "excerpt": render_dataset_answer(ds_result),
                                    "dataset": {
                                        "name": ds_result.get("dataset_name"),
                                        "sheet": ds_result.get("entity_name"),
                                        "content_hash": ds_result.get("content_hash"),
                                        "rows": ds_result.get("row_count"),
                                    },
                                    "ingested_into_workspace": True,
                                    "note": (
                                        "Rows above were queried from the query-verified "
                                        "dataset copy of this file (R# = spreadsheet row "
                                        "numbers). Cite only these values for exact figures."
                                    ),
                                }}
                except Exception as ds_err:  # noqa: BLE001 — fast path is best-effort
                    logger.debug(f"catalog fast path skipped: {ds_err}")

            # --- resolve the file ---------------------------------------
            source_modified_hint = None  # connector mtime, set on search-resolved reads
            if not file_id:
                hits: List[Dict[str, Any]] = []
                if service == "zoho_workdrive":
                    raw = await storage_service.search_files(
                        user_id or token, query or " ", limit=20)
                    if isinstance(raw, list):
                        hits = raw
                    else:
                        hits = (raw or {}).get("data", {}).get("files", []) \
                            if isinstance(raw, dict) else []
                elif service == "google_drive":
                    raw = await storage_service.search_files(token, query)
                    hits = (raw or {}).get("data", {}).get("files", []) \
                        if isinstance(raw, dict) else []
                elif service == "onedrive":
                    raw = await storage_service.search_files(token, query)
                    hits = (raw or {}).get("data", {}).get("value", []) \
                        if isinstance(raw, dict) else []
                elif service == "box":
                    raw = await storage_service.search_files(token, query)
                    hits = (raw or {}).get("data", {}).get("entries", []) \
                        if isinstance(raw, dict) else []
                elif service == "dropbox":
                    hits = await storage_service.search(query or " ", token) or []
                if not hits:
                    return {"status": "success", "data": {
                        "found": False,
                        "served": False,
                        "identity_verified": False,
                        "message": f"No file in {service} matched '{query}'.",
                    }}
                if not callable(getattr(storage_service, "get_file_metadata", None)):
                    _legacy_id, _legacy_name = self._best_file_match(hits, query)
                    identity = {
                        "provider": service,
                        "resource_id": str(_legacy_id) if _legacy_id else None,
                        "file_name": _legacy_name,
                        "source_metadata": {},
                        "identity_verified": False,
                    }
                else:
                    identity = _resolve_storage_hits(
                        hits, query, service, user_id or token
                    )
                    identity = await _refresh_storage_metadata(
                        service, storage_service, user_id or token, identity
                    )
                if (
                    context.get("file_identity_confirmed")
                    and identity.get("reason") == "single_candidate_not_verified"
                    and not identity.get("metadata_error")
                    and identity.get("resource_id")
                    and identity.get("source_metadata", {}).get("modified_at")
                    and (
                        identity.get("source_metadata", {}).get("team_id")
                        or identity.get("source_metadata", {}).get("folder_id")
                    )
                ):
                    identity["identity_verified"] = True
                    identity["identity_confirmation"] = "unique_candidate"
                if identity.get("ambiguous"):
                    return {"status": "success", "data": {
                        "found": False,
                        "served": False,
                        "identity_verified": False,
                        "ambiguous": True,
                        "candidates": identity.get("candidates") or [],
                        "message": "More than one file matched the requested name.",
                    }}
                file_id = identity.get("file_id")
                file_name = identity.get("file_name")
                identity_verified = bool(identity.get("identity_verified"))
                if not file_id:
                    if not callable(getattr(storage_service, "get_file_metadata", None)):
                        file_id, file_name = self._best_file_match(hits, query)
                        identity = {
                            "provider": service,
                            "resource_id": str(file_id) if file_id else None,
                            "file_name": file_name,
                            "source_metadata": {},
                            "identity_verified": False,
                        }
                if not file_id:
                    return {"status": "success", "data": {
                        "found": False,
                        "served": False,
                        "identity_verified": False,
                        "candidates": identity.get("candidates") or [],
                        "message": "The requested file identity could not be resolved.",
                    }}
                source_modified_hint = (identity.get("source_metadata") or {}).get(
                    "modified_at"
                )
            else:
                identity = {
                    "provider": service,
                    "resource_id": str(file_id),
                    "file_name": params.get("file_name"),
                    "requested_name": _storage_requested_name(query),
                    "source_metadata": params.get("source_metadata") or {},
                    "identity_verified": bool(params.get("identity_verified")),
                }
                identity = await _refresh_storage_metadata(
                    service, storage_service, user_id or token, identity
                )
                identity_verified = bool(identity.get("identity_verified"))
                file_name = identity.get("file_name") or file_name
                source_modified_hint = (identity.get("source_metadata") or {}).get(
                    "modified_at"
                )

            if (
                not identity_verified
                and service == "zoho_workdrive"
                and callable(getattr(storage_service, "get_file_metadata", None))
            ):
                return {"status": "success", "data": {
                    "found": False,
                    "served": False,
                    "identity_verified": False,
                    "ambiguous": bool(identity.get("ambiguous")),
                    "candidates": identity.get("candidates") or [],
                    "resource_id": identity.get("resource_id"),
                    "file_name": identity.get("file_name"),
                    "message": "The file name resolved only to an unverified candidate.",
                }}

            # --- dataset fast path (BEFORE the download) -----------------
            # The chat harness runs ONE planned tool leg per turn and the
            # reply model is under a strict no-tool-calling contract — so
            # "the agent should query the dataset" can only happen HERE, in
            # the harness. If a hash-verified-fresh materialized copy of this
            # file exists, turn the question into SQL over it and return the
            # exact rows; every failure mode (no copy, stale copy, LLM
            # unavailable, bad SQL, zero rows) falls through to the ordinary
            # download→extract→excerpt path, so this can only SKIP a
            # 13MB-download/10s-parse round trip, never degrade an answer.
            if identity_verified and query and context.get("llm_service"):
                try:
                    from core.sheet_dataset_service import (
                        answer_from_datasets,
                        render_dataset_answer,
                        sheet_datasets_enabled,
                    )

                    if sheet_datasets_enabled():
                        ds_result = await answer_from_datasets(
                            service, str(file_id), query,
                            llm_service=context.get("llm_service"),
                            source_modified_hint=source_modified_hint,
                        )
                        if ds_result:
                            return {"status": "success", "data": {
                                "found": True,
                                "served": True,
                                "identity_verified": identity_verified,
                                "resource_id": str(file_id),
                                "provider": service,
                                "source_metadata": identity.get("source_metadata") or {},
                                "read_completed": True,
                                "coverage_complete": False,
                                "file_id": file_id,
                                "file_name": file_name or ds_result.get("file_name"),
                                "chars_extracted": ds_result.get("row_count", 0),
                                "excerpt": render_dataset_answer(ds_result),
                                "dataset": {
                                    "name": ds_result.get("dataset_name"),
                                    "sheet": ds_result.get("entity_name"),
                                    "content_hash": ds_result.get("content_hash"),
                                    "rows": ds_result.get("row_count"),
                                },
                                "ingested_into_workspace": True,
                                "note": (
                                    "Rows above were queried from the materialized copy of this "
                                    "file, freshness-verified against the source before answering "
                                    "(R# = spreadsheet row numbers). Cite only these values for "
                                    "exact figures."
                                ),
                            }}
                except Exception as ds_err:  # noqa: BLE001 — fast path is best-effort
                    logger.debug(f"dataset fast path skipped for {file_id}: {ds_err}")

            # --- download -------------------------------------------------
            content: Optional[bytes] = None
            if service == "zoho_workdrive":
                content = await storage_service.download_file(user_id or token, file_id)
            elif service == "google_drive":
                content = await storage_service.download_file_bytes(token, file_id)
            elif service == "onedrive":
                content = await storage_service.download_file_bytes(token, file_id)
            elif service == "box":
                content = await storage_service.download_file_bytes(token, file_id)
            elif service == "dropbox":
                content = await storage_service.download_file(file_id or query, token)
            if not content:
                return {"status": "success", "data": {
                    "found": False,
                    "served": False,
                    "identity_verified": identity_verified,
                    "resource_id": str(file_id),
                    "provider": service,
                    "file_id": file_id,
                    "file_name": file_name,
                    "message": f"Found the file in {service} but the download failed.",
                }}
            if not file_name:
                # Explicit file_id reads may carry no name (the planner's
                # read params hold only the id). Derive it: the ingested
                # copy's record first, then magic bytes — an empty name
                # yields an empty extension and the extractor refuses the
                # file ("Unsupported file type") even though the download
                # succeeded (live 2026-09-06: read-by-id on the price list).
                try:
                    from core.database import get_db_session
                    from core.models import IngestedDocument

                    with get_db_session() as _db:
                        _row = (
                            _db.query(IngestedDocument)
                            .filter(IngestedDocument.external_id == str(file_id))
                            .first()
                        )
                        if _row is not None:
                            file_name = _row.file_name
                except Exception as name_err:  # noqa: BLE001 — sniffing is the fallback
                    logger.debug(f"ingested-name lookup skipped for {file_id}: {name_err}")
            if not file_name:
                if content[:4] == b"%PDF":
                    file_name = f"{service}:{file_id}.pdf"
                elif content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                    file_name = f"{service}:{file_id}.xls"
                elif content[:4] == b"PK\x03\x04":
                    file_name = f"{service}:{file_id}.xlsx"
                else:
                    file_name = f"{service}:{file_id}"

            # --- extract --------------------------------------------------
            from core.auto_document_ingestion import (
                READ_EXTRACTION_MAX_CHARS,
                parse_document_cached,
            )

            file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

            # --- materialize the SQL-queryable dataset copy (fire-and-forget)
            # Deliberately INDEPENDENT of the ingest block below: it needs
            # only the downloaded bytes, and the ingest service can fail or
            # bail fast (live 2026-09-07: two reads, zero datasets — the hook
            # inside process_file_bytes never ran and its skip logged at
            # DEBUG, invisible). Background so the read's 45s tool budget is
            # never spent on the one-time parse+Parquet write; atomic writes
            # make a shutdown mid-task harmless, and the byte-hash key makes
            # concurrent duplicates collapse to one version.
            if file_ext in ("xlsx", "xls", "xlsm", "csv"):
                try:
                    from core.sheet_dataset_service import (
                        ensure_sheet_dataset_background,
                        sheet_datasets_enabled,
                    )

                    if sheet_datasets_enabled():
                        ensure_sheet_dataset_background(
                            content,
                            file_name=file_name,
                            source=service,
                            user_id=user_id,
                            workspace_id=context.get("workspace_id") or "default",
                            external_id=str(file_id),
                            source_modified_hint=source_modified_hint,
                        )
                except Exception as ds_err:  # noqa: BLE001 — never block the read
                    logger.warning(f"sheet datasets: scheduling failed for {file_name}: {ds_err}")

            # --- extract --------------------------------------------------
            from core.auto_document_ingestion import (
                READ_EXTRACTION_MAX_CHARS,
                parse_document_cached,
            )
            # Explicit open of a NAMED file: extract with a far larger
            # ceiling than the ingestion budget. The user asked for THIS
            # file's contents — a row in its last sheet must be reachable
            # (live 2026-09-03: the ingestion-budget cut landed before the
            # LINMAC sheet, so a read limited to that budget could not see
            # WG350DSAV row 17 either). Cached on the content hash: the
            # same file is re-opened on every follow-up question about it,
            # and a 13MB workbook costs ~10s per parse.
            text = await parse_document_cached(
                content, file_ext, file_name, max_chars=READ_EXTRACTION_MAX_CHARS
            )
            if not text or not text.strip():
                return {"status": "success", "data": {
                    "found": False,
                    "served": False,
                    "identity_verified": identity_verified,
                    "resource_id": str(file_id),
                    "provider": service,
                    "file_id": file_id,
                    "file_name": file_name,
                    "read_completed": False,
                    "message": f"Opened {file_name} but no text could be extracted from it.",
                }}

            workbook_read = None
            _context_texts = []
            if file_ext in ("xlsx", "xlsm"):
                try:
                    from core.workbook_read_artifact import inspect_workbook_bytes

                    for _entry in (context.get("history") or []):
                        if isinstance(_entry, dict):
                            _context_texts.append(str(_entry.get("message") or ""))
                            _response = _entry.get("response")
                            if isinstance(_response, dict):
                                _context_texts.append(str(_response.get("message") or ""))
                    _canvas_value = context.get("canvas")
                    if _canvas_value:
                        _context_texts.append(str(_canvas_value))
                    workbook_read = await asyncio.to_thread(
                        inspect_workbook_bytes,
                        content,
                        file_name,
                        query=query,
                        context_texts=_context_texts,
                        targets=context.get("requested_targets"),
                        provider=service,
                        resource_id=str(file_id),
                        source_metadata=identity.get("source_metadata") or {},
                    )
                except Exception as artifact_err:
                    logger.warning(
                        f"workbook read artifact unavailable for {file_name}: "
                        f"{artifact_err}"
                    )
                if not workbook_read or not workbook_read.get("all_sheets_searched"):
                    try:
                        from core.sheet_dataset_service import (
                            ensure_sheet_dataset,
                            entries_for_file_sync,
                            sheet_datasets_enabled,
                        )
                        from core.workbook_read_artifact import (
                            inspect_dataset_entries,
                        )

                        if sheet_datasets_enabled():
                            _dataset_result = await ensure_sheet_dataset(
                                content,
                                file_name=file_name,
                                source=service,
                                user_id=user_id,
                                workspace_id=context.get("workspace_id") or "default",
                                external_id=str(file_id),
                                source_modified_at=source_modified_hint,
                            )
                            if _dataset_result.get("status") in (
                                "materialized", "current"
                            ):
                                _entries = await asyncio.to_thread(
                                    entries_for_file_sync, service, str(file_id)
                                )
                                workbook_read = await asyncio.to_thread(
                                    inspect_dataset_entries,
                                    _entries,
                                    file_name,
                                    query=query,
                                    context_texts=_context_texts,
                                    targets=context.get("requested_targets"),
                                    provider=service,
                                    resource_id=str(file_id),
                                    source_metadata=identity.get("source_metadata") or {},
                                    sha256=hashlib.sha256(content).hexdigest(),
                                )
                    except Exception as dataset_artifact_err:
                        logger.warning(
                            f"dataset workbook artifact unavailable for "
                            f"{file_name}: {dataset_artifact_err}"
                        )

            # --- ingest (warming the hybrid index) — best-effort ----------
            ingested = False
            try:
                from core.auto_document_ingestion import AutoDocumentIngestionService

                ingest_result = await AutoDocumentIngestionService().process_file_bytes(
                    content,
                    file_name=file_name,
                    source=service,
                    user_id=user_id or "system",
                    external_id=file_id,
                    explicit=True,
                )
                ingested = ingest_result.get("status") == "ingested"
            except Exception as ingest_err:  # noqa: BLE001 — read still returns
                # The read's hybrid-index warming failed — visible at WARNING
                # (was DEBUG): silent skips left memory frozen for days.
                # The read itself still returns.
                logger.warning(f"read-path ingest skipped for {file_name}: {ingest_err}")

            excerpt = _query_anchored_excerpt(text, query)
            coverage_complete = file_ext not in ("xlsx", "xls", "xlsm", "csv", "tsv")
            if workbook_read:
                try:
                    from core.workbook_read_artifact import render_workbook_artifact

                    excerpt = (
                        f"{excerpt}\n\n"
                        f"{render_workbook_artifact(workbook_read)}"
                    )
                except Exception:
                    pass
                coverage = (workbook_read.get("coverage") or {})
                coverage_complete = bool(
                    workbook_read.get("all_sheets_searched")
                    and not workbook_read.get("truncated")
                    and coverage.get("complete")
                )
            # After this open the file has SQL-queryable datasets (if it is a
            # sheet) — the NEXT value question about it skips the download
            # entirely via the fast path above. Surface that in the note so
            # the provenance trail stays honest.
            dataset_note = ""
            try:
                from core.sheet_dataset_service import datasets_for_file

                _ds_entries = await datasets_for_file(service, str(file_id))
                if _ds_entries:
                    dataset_note = (
                        f" This file is also queryable as {_ds_entries[0]['dataset_name']}"
                        f" (+{max(0, len(_ds_entries) - 1)} more sheets): exact-value "
                        f"questions are answered from the copy directly."
                    )
            except Exception:  # noqa: BLE001 — metadata only
                dataset_note = ""
            return {"status": "success", "data": {
                "found": True,
                "served": True,
                "identity_verified": identity_verified,
                "resource_id": str(file_id),
                "provider": service,
                "source_metadata": identity.get("source_metadata") or {},
                "read_completed": True,
                "coverage_complete": coverage_complete,
                "workbook_read": workbook_read,
                "content_sha256": hashlib.sha256(content).hexdigest(),
                "file_id": file_id,
                "file_name": file_name,
                "chars_extracted": len(text),
                "excerpt": excerpt,
                "ingested_into_workspace": ingested,
                "note": (
                    "Contents above are EXCERPTS around the query. Cite only "
                    "values visible in them; the file is now ingested for "
                    "full-text search." + dataset_note
                ),
            }}
        except Exception as e:
            logger.error(f"read_storage_file failed ({service}, file={file_id}): {e}")
            return {"status": "error", "message": f"Could not open the file: {e}", "data": {
                "found": False,
                "served": False,
                "identity_verified": False,
                "read_completed": False,
                "coverage_complete": False,
            }}

    @staticmethod
    def _best_file_match(
        hits: List[Dict[str, Any]], query: str
    ) -> tuple:
        """Pick the hit whose NAME best matches the query tokens (falls back
        to the top hit). Returns (file_id, file_name)."""
        import re as _re

        def _norm(s: str) -> str:
            return _re.sub(r"[^a-z0-9]+", "", str(s or "").lower())

        q_tokens = [t for t in _re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2]
        best, best_score = None, -1
        for h in hits:
            name = str(
                h.get("name") or h.get("title")
                or (h.get("attributes") or {}).get("name", "")
            )
            nid = _norm(name)
            score = sum(1 for t in q_tokens if _norm(t) and _norm(t) in nid)
            if score > best_score:
                best, best_score = h, score
        h = best or hits[0]
        file_id = (
            h.get("id") or h.get("file_id") or h.get("fileId")
            or ((h.get("metadata") or {}).get("id") if isinstance(h.get("metadata"), dict) else None)
        )
        # Box wraps metadata; OneDrive nests under parent; keep a last-resort walk
        if file_id is None and isinstance(h, dict):
            for v in h.values():
                if isinstance(v, dict) and v.get("id"):
                    file_id = v["id"]
                    break
        file_name = str(
            h.get("name") or h.get("title")
            or (h.get("attributes") or {}).get("name", "")
        )
        return file_id, file_name

    async def _search_storage(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search files/pages across storage platforms via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        storage_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(storage_service, 'access_token', None) or context.get("access_token")

        if service == "google_drive":
            res = await storage_service.search_files(token, query)
            if res.get("status") == "success":
                return res.get("data", {}).get("files", [])
        elif service == "dropbox":
            return await storage_service.search(query, token)
        elif service == "notion":
            res = await storage_service.search(query, token=token)
            return res.get("results", [])
        elif service == "zoho_workdrive":
            # Same per-user token resolution as _execute_storage — the
            # storage branch previously fell through to `return []` here, so
            # agent-facing search_files fan-outs never saw WorkDrive results.
            return await storage_service.search_files(
                context.get("user_id") or token, query)
        elif service == "onedrive":
            res = await storage_service.search_files(token, query)
            return (res.get("data") or {}).get("value", []) if isinstance(res, dict) else []
        elif service == "box":
            # Was a silent fall-through `return []` — the MCP no-platform
            # search_files fan-out (which routes through _search_storage)
            # never saw Box results even though BoxService.search_files
            # existed.
            res = await storage_service.search_files(token, query)
            return (res.get("data") or {}).get("entries", []) if isinstance(res, dict) else []
        return []

    # --- Support Platforms ---
    async def _execute_support(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Zendesk, Freshdesk, Intercom via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        support_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(support_service, 'access_token', None) or context.get("access_token")

        if service == "zendesk":
            if action == "list":
                return {"status": "success", "data": await support_service.get_tickets(token=token)}
            elif action == "create":
                return {"status": "success", "data": await support_service.create_ticket(params.get("data", {}), token=token)}

        elif service == "freshdesk":
            if action in ("list", "get_tickets"):
                return {"status": "success", "data": await support_service.get_tickets(token=token)}
            elif action == "create":
                return {"status": "success", "data": await support_service.create_ticket(params.get("data", params), token=token)}
            elif action == "search":
                return {"status": "success", "data": await support_service.search_tickets(params.get("query"), token=token)}

        elif service == "intercom":
            if action in ("list", "get_conversations"):
                return {"status": "success", "data": await support_service.get_conversations(token)}
            elif action == "search_contacts":
                return {"status": "success", "data": await support_service.search_contacts(token, params.get("query"))}
        
        return {"status": "success", "message": f"Routed to {service} handler (Registry Support)"}

    # --- Development Platforms ---
    async def _execute_development(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub, GitLab, Figma via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        dev_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(dev_service, 'access_token', None) or context.get("access_token")

        if service == "github":
            if action in ("list", "list_repos"):
                return {"status": "success", "data": await dev_service.get_user_repositories(token=token)}
            elif action == "get_issues":
                return {"status": "success", "data": await dev_service.get_repository_issues(params.get("owner"), params.get("repo"), token=token)}
        elif service == "gitlab":
            if action in ("list", "list_projects"):
                return {"status": "success", "data": await dev_service.get_projects(token, limit=params.get("limit", 20))}
            elif action == "get_issues":
                return {"status": "success", "data": await dev_service.get_issues(token, project_id=params.get("project_id"))}
            elif action == "search":
                return {"status": "success", "data": await dev_service.search_projects(token, params.get("query"))}
        elif service == "figma":
            if action in ("list", "get_projects"):
                return {"status": "success", "data": await dev_service.get_team_projects(params.get("team_id"), token)}
            elif action == "get_file":
                return {"status": "success", "data": await dev_service.get_file(params.get("file_key"), token)}
            elif action == "get_comments":
                return {"status": "success", "data": await dev_service.get_comments(params.get("file_key"), token)}
        
        return {"status": "success", "message": f"Routed to {service} handler (Registry Dev)"}

    # --- Marketing Platforms ---
    async def _execute_marketing(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Mailchimp, HubSpot Marketing"""
        access_token = context.get("access_token")
        server_prefix = context.get("server_prefix", params.get("server_prefix"))

        if service == "mailchimp":
            from integrations.mailchimp_service import MailchimpService
            mailchimp_service = MailchimpService()
            if action in ("list", "get_campaigns"):
                return {"status": "success", "data": await mailchimp_service.get_campaigns(access_token, server_prefix, limit=params.get("limit", 20))}
            elif action == "get_audiences":
                return {"status": "success", "data": await mailchimp_service.get_audiences(access_token, server_prefix)}
        elif service == "hubspot_marketing":
            from integrations.hubspot_service import get_hubspot_service
            hs = get_hubspot_service()
            if action == "list_campaigns":
                return {"status": "success", "data": await hs.get_campaigns()}
        
        return {"status": "success", "message": f"Routed to {service} handler (marketing)"}

    async def _search_dev(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search repositories/code across Dev platforms"""
        access_token = context.get("access_token")
        if service == "github":
            from integrations.github_service import GitHubService
            github_service = GitHubService()
            # GitHub has a real search API (/search/repositories?q=) that
            # reaches every repo the token can see — listing the user's own
            # repos and filtering client-side can only ever match owned
            # repos (and only the first page of them). Server search first;
            # the client-side filter stays as the unauthenticated fallback.
            query = (query or "").strip()
            if query:
                try:
                    hits = github_service.search_repositories(query)
                    if hits:
                        return {"status": "success", "data": hits}
                except Exception as search_err:  # noqa: BLE001 — fall back below
                    logger.warning(f"github server search failed, falling back to repo list: {search_err}")
            repos = github_service.get_user_repositories()
            return {"status": "success",
                    "data": filter_by_terms(repos, query,
                                            text_of=lambda r: r.get("name", ""))}
        elif service == "gitlab":
            from integrations.gitlab_service import GitLabService
            gitlab_service = GitLabService()
            return {"status": "success", "data": await gitlab_service.search_projects(access_token, query)}
        return []

    async def _search_marketing(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search campaigns across Marketing platforms"""
        access_token = context.get("access_token")
        server_prefix = context.get("server_prefix")
        if service == "mailchimp":
            from integrations.mailchimp_service import MailchimpService
            mailchimp_service = MailchimpService()
            campaigns = await mailchimp_service.get_campaigns(access_token, server_prefix)
            return {"status": "success",
                    "data": filter_by_terms(
                        campaigns, query,
                        text_of=lambda c: " ".join([
                            (c.get("settings") or {}).get("subject_line") or "",
                            (c.get("settings") or {}).get("title") or "",
                        ]))}
        return []

    # --- Finance Platforms ---
    async def _search_finance(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search across finance platforms.

        Stripe has a real server-side Search API (charges/search) reaching
        the WHOLE account; the other finance providers expose list endpoints
        only, so those keep the pull-recent-list-and-filter shape (the read
        envelope's page block now marks those results as one unverified
        page). Shared by the search() entry and the execute-path search
        bridge."""
        fin_service = await context["registry"].get_service_instance(service, context.get("tenant_id", "system"))
        token = getattr(fin_service, "access_token", None) or context.get("access_token")
        if not fin_service:
            return {"status": "error", "message": f"{service} service unavailable"}
        read = context.get("read_query")
        if service == "stripe":
            query = (query or "").strip()
            if query and hasattr(fin_service, "search_charges"):
                # Server-side search over every charge — the client-side
                # filter below could only ever match the newest 25.
                try:
                    paged = await fin_service.search_charges(
                        query, limit=(read.limit if read is not None and read.explicit_limit else 25))
                    result: Dict[str, Any] = {"status": "success", "data": paged.get("data", [])}
                    if paged.get("next_page_token"):
                        result["_next_page_token"] = paged["next_page_token"]
                        result["_has_more"] = True
                    return result
                except Exception as search_err:  # noqa: BLE001 — fall back below
                    logger.warning(f"stripe server search failed, falling back to recent list: {search_err}")
            # StripeAdapter.get_charges — the branch used to call
            # list_payments, a method that exists on no stripe class
            # (AttributeError on the first live finance search).
            data = await fin_service.get_charges(limit=25)
        elif service == "quickbooks":
            data = await fin_service.get_invoices(token=token)
        else:
            data = await fin_service.get_invoices(token)
        return self._filter_by_query(data, query)

    async def _execute_finance(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe, QuickBooks, Xero, Zoho Books via Registry"""
        registry = context.get("registry")
        tenant_id = context.get("tenant_id", "system")
        fin_service = await registry.get_service_instance(service, tenant_id)
        token = getattr(fin_service, 'access_token', None) or context.get("access_token")

        if service == "stripe":
            if action == "list_payments":
                # StripeAdapter.get_charges — list_payments exists on no
                # stripe class (AttributeError class, caught by the parity
                # test).
                return {"status": "success", "data": await fin_service.get_charges(limit=params.get("limit", 10))}
            elif action == "get_balance":
                return {"status": "success", "data": await fin_service.get_balance(access_token=token)}
        elif service == "quickbooks":
            if action == "list_invoices":
                return {"status": "success", "data": await fin_service.get_invoices(token=token)}
            elif action == "create_customer":
                return {"status": "success", "data": await fin_service.create_customer(params.get("display_name"), params.get("email"), token=token)}
            elif action == "create_invoice":
                return {"status": "success", "data": await fin_service.create_invoice(params, token=token)}
        elif service == "xero":
            if action == "list_invoices":
                return {"status": "success", "data": await fin_service.get_invoices(token=token)}
        elif service == "zoho_books":
            if action == "list_invoices":
                return {"status": "success", "data": await fin_service.get_invoices(token)}
        elif service == "zoho_inventory":
            if action in ("search_items", "search"):
                # The live search leg the chat tool planner plans when a user
                # asks about stock ("is the wg-350dsav in stock?"). The service
                # resolves token/datacenter/org itself and returns slim item
                # dicts; an empty result flows to the planner's memory fallback.
                # user_id is required for the per-user token lookup — token
                # rows are user-keyed, so this previously died on
                # "no access token available" for every agent turn.
                return {"status": "success", "data": await fin_service.search_items(
                    params.get("query", ""), limit=params.get("limit", 8),
                    user_id=context.get("user_id"))}
            if action == "list_items":
                return {"status": "success", "data": await fin_service.get_items(token)}
        elif service == "aws_ses":
            if action == "send_email":
                return {"status": "success", "data": await fin_service.send_email(
                    params.get("from_email", "noreply@example.com"),
                    to=params.get("to", []),
                    subject=params.get("subject"),
                    html_body=params.get("html_body"),
                    text_body=params.get("text_body")
                )}
            elif action == "get_quota":
                return {"status": "success", "data": await fin_service.get_send_quota(tenant_id)}

        return {"status": "success", "message": f"Routed to {service} handler (Registry Finance)"}

    # --- Zoho Suite ---
    async def _execute_zoho(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Zoho CRM, Mail, Inventory"""
        access_token = context.get("access_token")
        if service == "zoho_crm":
            from integrations.zoho_crm_service import ZohoCRMService
            crm = ZohoCRMService()
            # ZohoCRMService credentials self-resolve (tenant token lookup);
            # the token= kwargs here TypeError'd on every call (live
            # 2026-09-03), so zoho_crm list/deals/create always failed.
            if action in ("list", "get_leads"):
                return {"status": "success", "data": await crm.get_leads()}
            elif action == "get_deals":
                return {"status": "success", "data": await crm.get_deals()}
            elif action == "create_lead":
                return {"status": "success", "data": await crm.create_lead(params.get("data", params))}
        elif service == "zoho_mail":
            from integrations.zoho_mail_service import ZohoMailService
            zoho_mail_service = ZohoMailService()
            if action == "list":
                return {"status": "success", "data": await zoho_mail_service.get_recent_inbox(access_token)}
        elif service == "zoho_inventory":
            from integrations.zoho_inventory_service import zoho_inventory_service
            if action == "list":
                return {"status": "success", "data": await zoho_inventory_service.get_items(access_token)}
        elif service == "zoho_projects":
            from integrations.zoho_projects_service import ZohoProjectsService
            zoho_projects_service = ZohoProjectsService()
            if action == "list":
                return {"status": "success", "data": await zoho_projects_service.get_projects(access_token, params.get("portal_id") or "")}
        elif service in ("zoho_forms", "zoho_flow"):
            # Webhook-push apps: no live API to call — the agent reads what
            # has been ingested into agent memory (see zoho_*_service).
            from integrations.zoho_forms_service import ZohoFormsService
            from integrations.zoho_flow_service import ZohoFlowService

            workspace_id = context.get("workspace_id") or self.workspace_id
            svc = (ZohoFormsService if service == "zoho_forms" else ZohoFlowService)(
                config={"workspace_id": workspace_id}
            )
            if action in ("list", "list_submissions", "list_events"):
                return {"status": "success", "data": await svc.list_submissions() if service == "zoho_forms" else await svc.list_events()}
            if action in ("search", "search_submissions", "search_events"):
                data = await svc.search_submissions(params.get("query", "")) if service == "zoho_forms" else await svc.search_events(params.get("query", ""))
                return {"status": "success", "data": data}

        return {"status": "success", "message": f"Routed to {service} handler (default zoho)"}

    async def _search_crm(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search across CRM platforms"""
        access_token = context.get("access_token")
        if service == "salesforce":
            # Delegate to the real implementation (the search() entry's
            # Salesforce search) — this branch used to be a literal `pass`
            # that returned [] while the catalog advertised the search.
            # SOQL entity defaults to contact (the common "find this
            # company/person" intent); the helper only implements
            # contact/account SOQL.
            return await self._search_salesforce(
                query, context.get("entity_type") or "contact",
                context.get("user_id"), context)
        elif service == "hubspot":
            return await self._search_hubspot(query, None, context)
        elif service == "zoho_crm":
            from integrations.zoho_crm_service import ZohoCRMService
            crm = ZohoCRMService()
            # List-and-filter: Zoho CRM has no simple text search endpoint at
            # this integration depth. Self-resolving credential path — the
            # token= kwarg predates it and TypeError'd on every call (live
            # 2026-09-03), so planner-planned zoho_crm searches always errored
            # into the memory fallback.
            leads = await crm.get_leads()
            return {"status": "success", "data": self._filter_by_query(leads, query)}
        return {"status": "success", "data": []}

    async def _search_support(self, service: str, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Search across Support platforms"""
        if service == "zendesk":
            from integrations.zendesk_service import ZendeskService
            zendesk_service = ZendeskService()
            return {"status": "success", "data": await zendesk_service.get_tickets()}
        elif service == "freshdesk":
            from integrations.freshdesk_service import FreshdeskService
            fd = FreshdeskService()
            return {"status": "success", "data": await fd.search_tickets(query)}
        elif service == "intercom":
            registry = context.get("registry")
            tenant_id = context.get("tenant_id", "system")
            if registry:
                service_inst = await registry.get_service_instance("intercom", tenant_id)
                if service_inst:
                    token = getattr(service_inst, 'access_token', None) or context.get("access_token")
                    return {"status": "success", "data": await service_inst.search_contacts(token, query)}
            return {"status": "error", "message": "Intercom service not found in registry"}
        return {"status": "success", "data": []}

    # --- Analytics Platforms ---
    async def _execute_analytics(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Tableau, Google Analytics"""
        access_token = context.get("access_token")
        if service == "tableau":
            from integrations.tableau_service import TableauService
            tableau = TableauService()
            try:
                if action in ("list", "get_workbooks"):
                    return {"status": "success", "data": await tableau.get_workbooks(access_token)}
            except Exception as e:
                return {"status": "error", "message": f"Tableau service failed: {str(e)}"}
        elif service == "google_analytics":
            # GA4 implementation link
            return {"status": "success", "message": f"Routed to {service} GA4 handler"}
        
        return {"status": "success", "message": f"Routed to {service} handler (analytics)"}

    async def _search_analytics(self, service: str, query: str, context: Dict[str, Any]) -> List[Dict]:
        """Search across Analytics platforms"""
        if service == "tableau":
            from integrations.tableau_service import TableauService
            tableau = TableauService()
            try:
                workbooks = await tableau.get_workbooks(context.get("access_token"))
                return {"status": "success", "data": [w for w in workbooks if query.lower() in w.get("name", "").lower()]}
            except Exception as e:
                return {"status": "error", "message": f"Tableau search failed: {str(e)}"}
        return {"status": "success", "data": []}

    # --- Generic Native Handler ---
    async def _execute_generic_native(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Refuse honestly for a native service with no implemented action.

        This used to return ``{"status": "success", "message": "Action X
        routed to Y (generic handler)"}`` with NO data. An agent that
        planned a real question onto that path saw a success envelope, had
        nothing to ground on, and answered from the model's priors — the
        fabrication class this repo has a test history for. An explicit
        error is strictly better: the agent learns the capability is
        missing and can say so, and the tool-error signal feeds the
        evolution harness instead of being lost.
        """
        logger.info(f"Generic native handler refused {service}.{action}")
        return {
            "status": "error",
            "error": "unsupported_action",
            "service": service,
            "action": action,
            "message": (
                f"'{action}' is not implemented for {service} in the native "
                f"integration layer — no data was fetched. Do not assume a "
                f"result. Use a supported action for {service} (list / search "
                f"/ get) or the dedicated tool for this platform."
            ),
            "supported_actions": ["list", "search", "get", "create", "update"],
        }

    # --- Activepieces Fallback ---
    async def _execute_activepieces(self, service: str, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Route to Activepieces catalog for non-native integrations"""
        try:
            from core.external_integration_service import external_integration_service
            logger.info(f"Routing {service}.{action} to Activepieces catalog")
            
            
            result = await external_integration_service.execute_integration_action(
                integration_id=service,
                action_id=action,
                params=params,
                credentials=context.get("credentials")
            )
            return {"status": "success", "data": result}
        except Exception as ex:
            logger.error(f"Activepieces fallback failed for {service}: {ex}")
            return {"status": "error", "message": f"Service '{service}' not supported. Activepieces fallback failed: {str(ex)}"}
    async def _execute_marketing_reviews(self, service, action, params, context):
        """
        Specialized handler for review platforms.
        """
        from core.marketing_skills_service import marketing_skills_service
        
        if action == "list_reviews":
            return {"status": "success", "data": await marketing_skills_service.manage_reviews(self.workspace_id, service)}
        elif action == "reply_to_review":
            # No review platform API call is implemented here. This used to
            # return "Successfully replied to review X" — a fabricated
            # confirmation for a message that was never sent, which the
            # agent then reported to the user as done.
            return {
                "status": "error",
                "error": "unsupported_action",
                "service": service,
                "action": action,
                "message": (
                    f"Posting a reply to a {service} review is not implemented "
                    f"— nothing was sent to the platform. Tell the user the "
                    f"reply could not be posted rather than confirming it."
                ),
            }
        return {"status": "error", "message": f"Unknown review action: {action}"}

    async def _execute_marketing_ads(self, service, action, params, context):
        """Honest refusal for the Ads platforms (Meta, Google, LinkedIn).

        The previous body returned ``{"data": {"count": 10, "insights":
        "Performance trending positive."}}`` for EVERY action — invented ad
        metrics that an agent presented as the user's campaign performance.
        No fabricated numbers, ever: an unimplemented read must look
        unimplemented.
        """
        logger.info(f"Ads action {action} requested on {service} (unimplemented)")
        return {
            "status": "error",
            "error": "unsupported_action",
            "service": service,
            "action": action,
            "message": (
                f"The {service} advertising API is not connected in this "
                f"build — no insights were retrieved. Do NOT report campaign "
                f"numbers; tell the user ads reporting is unavailable."
            ),
        }

# Singleton instance for platform-wide usage
universal_integration_service = UniversalIntegrationService()
