"""Registered Brennan connected reads/drafts for the employee workflow.

This is the small handoff surface Agent 1 consumes through the existing
``action.registry`` assignment adapter.  It deliberately wraps the provider
services rather than inventing another client, cache or job engine.

Reads return a typed receipt with provider identity, resource identity,
retrieval time and coverage.  Failures are errors, never empty successes.
Writes are limited to the actions the business workflow needs and require an
explicit authority reference; every write performs an authoritative readback.
No action sends email.
"""
from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Optional

from core.action_registry import action_registry, register_action
from core.commercial_readback import (
    bind_remote_identity,
    verify_bill_readback,
    verify_estimate_readback,
)

logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 25 * 1024 * 1024

# Serialize same-target writes inside this process.  The assignment executor's
# effect arbiter is the cross-process/durable guarantee; this closes the local
# sweep-then-create race where two coroutines both see no duplicate and both
# post before either readback lands.
_effect_locks: Dict[str, asyncio.Lock] = {}


def _serialized_effect(key_fn: Callable[[Dict[str, Any], Dict[str, Any]], str]):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(args: Dict[str, Any], context: Dict[str, Any]):
            key = key_fn(args or {}, context or {})
            lock = _effect_locks.setdefault(key, asyncio.Lock())
            try:
                async with lock:
                    return await fn(args, context)
            finally:
                if not lock.locked() and _effect_locks.get(key) is lock:
                    _effect_locks.pop(key, None)

        return wrapper

    return decorator


def _bill_effect_key(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    proposal = args.get("proposal") or {}
    return ("zoho_books|bill|"
            f"{proposal.get('organization_id') or ''}|"
            f"{proposal.get('external_id') or ''}")


def _estimate_effect_key(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    data = args.get("estimate_data") or {}
    reference = data.get("reference_number") or args.get("operation_id") or ""
    return (f"zoho_books|estimate|{args.get('organization_id') or ''}|"
            f"{reference}")


def _draft_effect_key(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    return f"outlook|draft|{args.get('operation_id') or ''}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_ACTION_IDS: ContextVar[Dict[str, str]] = ContextVar(
    "brennan_action_ids", default={})


def _ids(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
    ids = {
        "tenant_id": str(context.get("tenant_id") or args.get("tenant_id")
                         or "default"),
        "workspace_id": str(context.get("workspace_id")
                            or args.get("workspace_id") or ""),
        "user_id": str(context.get("user_id") or args.get("user_id")
                       or context.get("employee_id") or ""),
    }
    _ACTION_IDS.set(ids)
    return ids


def _error(provider: str, operation: str, kind: str, message: str,
           *, reconnect: bool = False,
           action_result: Optional[str] = None) -> Dict[str, Any]:
    if action_result is None:
        action_result = (
            "unavailable"
            if kind in ("auth_expired", "auth_revoked", "auth_unavailable",
                        "provider_error", "parse_error", "rate_limited",
                        "transient")
            else "proven_not_applied"
        )
    return {
        "status": "error",
        "success": False,
        "action_result": action_result,
        "provider": provider,
        "operation": operation,
        "error_kind": kind,
        "error": message,
        "retryable": kind in ("rate_limited", "transient"),
        "requires_reconnect": reconnect,
    }


def action_executor_outcome(result: Dict[str, Any]) -> str:
    """Map a connected action result to the executor's outcome vocabulary.

    ``_action_registry_adapter`` must not wrap every return as ``applied``:
    a duplicate/validation result is ``proven_not_applied``, a changed
    readback is ``conflict`` and a lost confirmation is ``uncertain``.  Agent
    1 owns the adapter; this helper is the drop-in mapping for it.
    """
    payload = result or {}
    action_result = str(payload.get("action_result") or "")
    if action_result == "applied":
        return "applied"
    if action_result == "proven_not_applied":
        return "failed"
    if action_result in ("uncertain", "conflict", "unavailable"):
        return "uncertain"
    status = str(payload.get("status") or "").lower()
    if status in ("success", "applied", "completed"):
        return "applied"
    if status in ("conflict", "uncertain"):
        return "uncertain"
    if status in ("duplicate", "error", "failed", "unavailable"):
        return "failed" if status != "unavailable" else "uncertain"
    if payload.get("success") is False:
        return "failed"
    if payload.get("error") or payload.get("error_kind"):
        return "failed"
    # Legacy read actions return a bare value dict with no status.
    return "applied"


def _normalize_estimate_data(estimate_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize runtime quote rows into the provider estimate contract.

    `quote.calculate` exposes ``unit_price`` and a fraction ``discount_rate``;
    Zoho line items use ``rate`` and a percentage.  Normalization happens
    before the payload digest so the authorized payload and the readback
    comparison use the same canonical form.
    """
    normalized = dict(estimate_data or {})
    lines = []
    for raw in normalized.get("line_items") or normalized.get("lines") or []:
        if not isinstance(raw, dict):
            continue
        line = dict(raw)
        if line.get("rate") in (None, "") and line.get("unit_price") is not None:
            line["rate"] = str(line["unit_price"])
        if (line.get("item_id") in (None, "")
                and line.get("sku") not in (None, "")):
            line["item_id"] = str(line["sku"])
        if line.get("name") in (None, ""):
            line["name"] = str(line.get("description")
                               or line.get("item_id") or "Quote line")
        if (line.get("discount_percent") in (None, "")
                and line.get("discount_rate") not in (None, "")):
            try:
                line["discount_percent"] = str(
                    Decimal(str(line["discount_rate"])) * Decimal("100"))
            except (InvalidOperation, ValueError):
                pass
        # Keep only provider payload fields.  Evidence/source references and
        # calculated gross/net values stay in the calculation receipt; they
        # must not deepen the bound operation payload or become provider
        # input.
        allowed = {
            "item_id", "name", "description", "quantity", "rate",
            "discount_percent", "discount_amount", "discount_type",
            "unit", "account_id", "tax_id", "tax_name", "tax_percentage",
        }
        lines.append({key: value for key, value in line.items()
                      if key in allowed and value not in (None, "")})
    if lines:
        normalized["line_items"] = lines
    return normalized


def _payload_digest(payload: Dict[str, Any]) -> str:
    """Digest the exact effect payload with the shared approval hasher.

    The executor already signs effects with ``_approval_payload_hash``.  Using
    the same function means a caller can compare the plan's approval digest
    with the receipt the action returns instead of maintaining a second
    canonicalisation rule.
    """
    from core.task_lifecycle import _approval_payload_hash

    return _approval_payload_hash(payload)


def _normalize_outlook_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Material fields for a draft request/readback comparison."""

    def addresses(value: Any) -> List[str]:
        result: List[str] = []
        for item in value or []:
            if isinstance(item, str):
                address = item
            elif isinstance(item, dict):
                address = (
                    (item.get("emailAddress") or {}).get("address")
                    or item.get("address") or "")
            else:
                address = ""
            if str(address).strip():
                result.append(str(address).strip().lower())
        return result

    body = payload.get("body")
    if isinstance(body, dict):
        body = body.get("content")
    return {
        "subject": str(payload.get("subject") or ""),
        "body": str(body or "").replace("\r\n", "\n"),
        "to": addresses(
            payload.get("toRecipients") or payload.get("to_recipients")),
        "cc": addresses(
            payload.get("ccRecipients") or payload.get("cc_recipients")),
        "bcc": addresses(
            payload.get("bccRecipients") or payload.get("bcc_recipients")),
    }


def _draft_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    """The exact material draft payload whose digest is authorized."""
    return {
        "to": list(args.get("to") or []),
        "cc": list(args.get("cc") or []),
        "bcc": list(args.get("bcc") or []),
        "subject": str(args.get("subject") or ""),
        "body": str(args.get("body") or ""),
    }


def _outlook_missing_fields(readback: Dict[str, Any]) -> List[str]:
    """Fields whose absence makes a verified draft comparison impossible."""
    missing: List[str] = []
    if "subject" not in readback or readback.get("subject") is None:
        missing.append("subject")
    body = readback.get("body")
    if "body" not in readback or body is None:
        missing.append("body")
    elif isinstance(body, dict) and "content" not in body:
        missing.append("body")
    for field, aliases in (
        ("to", ("toRecipients", "to_recipients")),
        ("cc", ("ccRecipients", "cc_recipients")),
        ("bcc", ("bccRecipients", "bcc_recipients")),
    ):
        if not any(alias in readback for alias in aliases):
            missing.append(field)
    return missing


def _draft_read_receipt(
    readback: Dict[str, Any], *, requested_id: str, observed_id: str,
) -> Dict[str, Any]:
    """Build a read receipt without inventing the observed remote identity."""
    receipt = _receipt(
        "outlook", "get_email_by_id", resource_id=observed_id,
        coverage="single", kind="draft",
        fields=readback if isinstance(readback, dict) else [])
    receipt["requested_remote_id"] = requested_id
    receipt["observed_remote_id"] = observed_id
    return receipt


def is_connected_mutation(action: str) -> bool:
    """True for connected write classes that require a frozen request binding."""
    return str(action or "").endswith(
        ("books.create_bill", "books.create_estimate",
         "outlook.create_draft"))


def oracle_request_binding(
    action: str, arguments: Dict[str, Any],
) -> Dict[str, str]:
    """Expected request binding for a connected mutation.

    These values come from the authorized request, never from the returned
    action envelope.  The provider material digest is computed with the same
    canonical payload builders the action uses before dispatch.
    """
    name = str(action or "")
    args = arguments if isinstance(arguments, dict) else {}
    binding = {
        "provider": "",
        "operation_id": str(args.get("operation_id") or ""),
        "organization_id": "",
        "target": "",
        "payload_sha256": "",
    }
    try:
        if name.endswith("books.create_estimate"):
            data = _normalize_estimate_data(args.get("estimate_data") or {})
            binding.update({
                "provider": "zoho_books",
                "organization_id": str(args.get("organization_id") or ""),
                "target": str(data.get("reference_number") or ""),
                "payload_sha256": _payload_digest(data),
            })
        elif name.endswith("books.create_bill"):
            proposal = args.get("proposal") or {}
            payload = _bill_payload(proposal)
            binding.update({
                "provider": "zoho_books",
                "organization_id": str(
                    proposal.get("organization_id")
                    or args.get("organization_id") or ""),
                "target": str(
                    proposal.get("external_id")
                    or payload.get("reference_number") or ""),
                "payload_sha256": _payload_digest(payload),
            })
        elif name.endswith("outlook.create_draft"):
            payload = _draft_payload(args)
            binding.update({
                "provider": "outlook",
                "target": str(payload.get("subject") or ""),
                "payload_sha256": _payload_digest(payload),
            })
    except Exception:  # noqa: BLE001 - malformed arguments stay unbound
        return binding
    return binding


def _write_failure(
    provider: str,
    operation: str,
    exc: Exception,
    *,
    may_have_landed: bool,
    remote_id: str = "",
    payload_sha256: str = "",
    authority_reference: str = "",
    operation_id: str = "",
) -> Dict[str, Any]:
    """Classify a write failure by whether the provider could have applied it."""
    from integrations.provider_errors import ProviderRequestError

    if isinstance(exc, ProviderRequestError):
        safe_kinds = {
            "auth_expired", "auth_revoked", "auth_unavailable", "unauthorized",
            "invalid_request", "not_found", "rate_limited",
        }
        landed = bool(may_have_landed) and exc.kind not in safe_kinds
        result = exc.to_dict()
        result.update({
            "status": "uncertain" if landed else "error",
            "action_result": "uncertain" if landed else "proven_not_applied",
            "remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": {
                "operation_id": operation_id,
                "authority_reference": authority_reference,
                "payload_sha256": payload_sha256,
                "remote_id": remote_id,
            },
        })
        return result
    return {
        "status": "uncertain" if may_have_landed else "error",
        "success": False,
        "action_result": (
            "uncertain" if may_have_landed else "proven_not_applied"),
        "provider": provider,
        "operation": operation,
        "error_kind": "provider_error",
        "error": f"{type(exc).__name__}: {exc}"[:500],
        "retryable": False,
        "requires_reconnect": False,
        "remote_id": remote_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "operation_id": operation_id,
            "authority_reference": authority_reference,
            "payload_sha256": payload_sha256,
            "remote_id": remote_id,
        },
    }


def _validate_accounting_period(
    document_date: Any, *, period_start: Any = None,
    period_end: Any = None, closed_through: Any = None,
) -> Optional[Dict[str, Any]]:
    """Enforce caller-supplied accounting period bounds before posting."""
    from datetime import date

    try:
        doc = date.fromisoformat(str(document_date))
    except (TypeError, ValueError):
        return _error("zoho_books", "create_bill", "invalid_request",
                      "The proposal has no valid document date.",
                      action_result="proven_not_applied")
    for field, raw in (("period_start", period_start),
                       ("period_end", period_end),
                       ("closed_through", closed_through)):
        if raw in (None, ""):
            continue
        try:
            bound = date.fromisoformat(str(raw))
        except ValueError:
            return _error(
                "zoho_books", "create_bill", "invalid_request",
                f"{field} is not an ISO date: {raw!r}",
                action_result="proven_not_applied")
        if field == "period_start" and doc < bound:
            return _error(
                "zoho_books", "create_bill", "invalid_request",
                f"document date {doc} is before the authorized period "
                f"start {bound}", action_result="proven_not_applied")
        if field == "period_end" and doc > bound:
            return _error(
                "zoho_books", "create_bill", "invalid_request",
                f"document date {doc} is after the authorized period "
                f"end {bound}", action_result="proven_not_applied")
        if field == "closed_through" and doc <= bound:
            return _error(
                "zoho_books", "create_bill", "invalid_request",
                f"document date {doc} falls in a period closed through "
                f"{bound}", action_result="proven_not_applied")
    return None


async def _readback_with_retry(getter, verifier) -> tuple:
    """Read the same remote object at most twice; never repeat the create.

    A sparse first readback is a provider-consistency possibility, so one
    bounded retry is allowed.  A definite mismatch is returned immediately.
    """
    readback: Dict[str, Any] = {}
    report: Optional[Dict[str, Any]] = None
    last_error: Optional[Exception] = None
    attempts = 0
    for _ in range(2):
        attempts += 1
        try:
            readback = await getter()
        except Exception as exc:  # noqa: BLE001 - classified by the caller
            last_error = exc
            continue
        if not isinstance(readback, dict) or not readback:
            last_error = ValueError("provider returned an empty readback")
            continue
        report = verifier(readback)
        last_error = None
        if report.get("status") != "incomplete":
            return readback, report, None, attempts
    return readback, report, last_error, attempts


async def _chart_of_account_ids(
    service: Any, token: str, organization_id: str,
) -> set:
    """Read the complete CoA identity set; a partial read must not validate."""
    ids = set()
    page = 1
    while True:
        rows, info = await service.get_chart_of_accounts_page(
            token, organization_id, page=page, per_page=200)
        for row in rows:
            account_id = str(
                row.get("account_id") or row.get("id") or "").strip()
            if account_id:
                ids.add(account_id)
        if not info.get("has_more"):
            break
        page += 1
        if page > 50:
            raise ValueError("chart of accounts exceeds the bounded sweep")
    return ids


def _tabular_rows(content: bytes, file_name: Optional[str],
                  *, max_rows: int = 500) -> Optional[Dict[str, Any]]:
    """Parse CSV/XLSX bytes into typed rows without guessing the schema.

    Returns ``{"rows", "columns", "sheet", "truncated"}`` for a supported
    tabular file, ``{"error": ...}`` for a corrupt/encrypted/unsupported one,
    and ``None`` when the file is not tabular (a prose document stays prose).
    """
    import csv
    import io

    name = str(file_name or "").strip().lower()
    extension = name.rsplit(".", 1)[-1] if "." in name else ""
    try:
        if extension in ("csv", "tsv"):
            text = None
            for encoding in ("utf-8-sig", "utf-8", "cp1252"):
                try:
                    text = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                return {"error": "the delimited file is not decodable text"}
            delimiter = "\t" if extension == "tsv" else ","
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            all_rows = list(reader)
            if not all_rows:
                return {"rows": [], "columns": [], "sheet": None,
                        "truncated": False}
            columns = [str(value).strip() for value in all_rows[0]]
            rows = []
            for index, values in enumerate(all_rows[1:max_rows + 1], start=2):
                if not any(str(value).strip() for value in values):
                    continue
                row = {columns[pos]: (values[pos] if pos < len(values) else "")
                       for pos in range(len(columns)) if columns[pos]}
                row["__row"] = index
                rows.append(row)
            return {"rows": rows, "columns": columns, "sheet": None,
                    "truncated": len(all_rows) - 1 > max_rows}
        if extension in ("xlsx", "xlsm"):
            from openpyxl import load_workbook

            workbook = load_workbook(
                io.BytesIO(content), data_only=True, read_only=True)
            sheet = workbook.worksheets[0]
            values = list(sheet.iter_rows(values_only=True))
            if not values:
                return {"rows": [], "columns": [], "sheet": sheet.title,
                        "truncated": False}
            columns = [str(value).strip() if value is not None else ""
                       for value in values[0]]
            rows = []
            for index, values_row in enumerate(
                    values[1:max_rows + 1], start=2):
                if not any(value not in (None, "") for value in values_row):
                    continue
                row = {}
                for pos, column in enumerate(columns):
                    if not column:
                        continue
                    value = (values_row[pos]
                             if pos < len(values_row) else None)
                    if hasattr(value, "isoformat"):
                        value = value.isoformat()
                    row[column] = value
                row["__row"] = index
                rows.append(row)
            return {"rows": rows, "columns": columns, "sheet": sheet.title,
                    "truncated": len(values) - 1 > max_rows}
    except Exception as exc:  # noqa: BLE001 - corrupt/encrypted/unsupported
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
    return None


def _receipt(provider: str, operation: str, *, resource_id: str = "",
             version: str = "", coverage: Any = "", evidence=None,
             fields: Any = None, continuation=None,
             account_id: Optional[str] = None,
             access: str = "granted", kind: Optional[str] = None,
             customer_id: Optional[str] = None, rows=None,
             content: Optional[str] = None, citations=None,
             price_basis: Optional[str] = None,
             effective_date: Optional[str] = None) -> Dict[str, Any]:
    """Read receipt shared with Agent 1's evidence validator.

    ``fields`` accepts the legacy list of field names or a typed dict of
    values; Agent 1 reads a dict when it is present and otherwise falls back
    to top-level values.  ``access`` makes an authorized read explicit.
    """
    ids = _ACTION_IDS.get({})
    receipt: Dict[str, Any] = {
        "provider": provider,
        "operation": operation,
        "workspace_id": ids.get("workspace_id") or None,
        "tenant_id": ids.get("tenant_id") or None,
        "account": {"workspace_id": ids.get("workspace_id") or None,
                    "account_id": account_id},
        "account_id": account_id,
        "resource_id": resource_id,
        "version": version,
        "retrieved_at": _now(),
        "access": access,
        "coverage": coverage,
        "fields": fields if fields is not None else [],
        "evidence": evidence or [],
        "continuation": continuation,
    }
    if kind:
        receipt["kind"] = kind
    if customer_id:
        receipt["customer_id"] = customer_id
    if rows is not None:
        receipt["rows"] = rows
    if content is not None:
        receipt["content"] = content
    if citations:
        receipt["citations"] = list(citations)[:20]
    if price_basis:
        receipt["price_basis"] = price_basis
    if effective_date:
        receipt["effective_date"] = effective_date
    return receipt


async def _zoho_token(service: Any, ids: Dict[str, str]) -> Optional[str]:
    try:
        return await service._get_active_token(
            tenant_id=ids["tenant_id"], user_id=ids["user_id"] or None,
            workspace_id=ids["workspace_id"] or None)
    except TypeError:
        try:
            return await service._get_active_token(
                tenant_id=ids["tenant_id"], user_id=ids["user_id"] or None)
        except Exception:
            return None
    except Exception:
        return None


async def _workdrive_service(ids: Dict[str, str]):
    from integrations.zoho_workdrive_service import ZohoWorkDriveService

    return ZohoWorkDriveService(ids["tenant_id"], {})


async def _onedrive_service(ids: Dict[str, str]):
    from integrations.onedrive_service import OneDriveService

    return OneDriveService(ids["tenant_id"], {})


@register_action(
    "brennan.workdrive.list_page",
    description="List one bounded WorkDrive folder page. Returns provider IDs, version, coverage and cursor; unavailable is an error.",
    parameters_schema={
        "type": "object",
        "properties": {
            "folder_id": {"type": "string"},
            "workspace_id": {"type": "string"},
            "team_id": {"type": "string"},
            "cursor": {"type": "string"},
            "page_size": {"type": "integer"},
        },
    },
    effects=[{"effect": "read"}],
)
async def workdrive_list_page(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    service = await _workdrive_service(ids)
    result = await service.list_files_page(
        ids["user_id"], args.get("folder_id") or "root",
        team_id=args.get("team_id"), workspace_id=args.get("workspace_id")
        or ids["workspace_id"] or None,
        cursor=args.get("cursor"), page_size=int(args.get("page_size") or 100))
    if result.get("status") != "success":
        return result
    items = result.get("items") or []
    return {
        "status": "success",
        "provider": "zoho_workdrive",
        "items": items,
        "next_cursor": result.get("next_cursor"),
        "has_more": bool(result.get("has_more")),
        "read_receipt": _receipt(
            "zoho_workdrive", "list_files_page",
            resource_id=str(args.get("folder_id") or "root"),
            coverage=str(result.get("coverage") or "partial"),
            account_id=str(args.get("workspace_id") or ""),
            kind=args.get("evidence_kind"),
            customer_id=args.get("customer_id"),
            fields=["id", "name", "type", "version", "modified_at", "size"],
            continuation={"next_cursor": result.get("next_cursor"),
                          "has_more": bool(result.get("has_more"))},
        ),
    }


@register_action(
    "brennan.workdrive.read_file",
    description="Read WorkDrive file bytes and metadata as evidence. Content is bounded; returns SHA-256 and version.",
    parameters_schema={
        "type": "object",
        "properties": {"file_id": {"type": "string"},
                       "workspace_id": {"type": "string"},
                       "max_bytes": {"type": "integer"},
                       "evidence_kind": {"type": "string"},
                       "customer_id": {"type": "string"},
                       "price_basis": {"type": "string"},
                       "effective_date": {"type": "string"},
                       "typed_fields": {"type": "object"}},
        "required": ["file_id"],
    },
    effects=[{"effect": "read"}],
)
async def workdrive_read_file(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    file_id = str(args.get("file_id") or "")
    if not file_id:
        return _error("zoho_workdrive", "read_file", "invalid_request",
                      "file_id is required")
    service = await _workdrive_service(ids)
    meta = await service.get_file_metadata(
        ids["user_id"], file_id, workspace_id=args.get("workspace_id")
        or ids["workspace_id"] or None)
    content = await service.download_file(
        ids["user_id"], file_id, workspace_id=args.get("workspace_id")
        or ids["workspace_id"] or None)
    if content is None:
        return _error("zoho_workdrive", "read_file", "auth_unavailable"
                      if not await service.get_access_token(ids["user_id"])
                      else "provider_error",
                      "WorkDrive file could not be read; no content returned.",
                      reconnect=True)
    if len(content) > int(args.get("max_bytes") or _MAX_FILE_BYTES):
        return _error("zoho_workdrive", "read_file", "too_large",
                      "WorkDrive file exceeds the bounded read size.")
    file_name = (meta or {}).get("name")
    tabular = _tabular_rows(content, file_name)
    rows = (tabular or {}).get("rows")
    typed_fields = args.get("typed_fields") or {
        "name": file_name,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if tabular:
        typed_fields = {
            **typed_fields,
            "columns": tabular.get("columns") or [],
            "sheet": tabular.get("sheet"),
            "truncated": bool(tabular.get("truncated")),
        }
        if tabular.get("error"):
            typed_fields["parse_error"] = tabular["error"]
    citations = [
        {"provider": "zoho_workdrive", "file_id": file_id,
         "sheet": (tabular or {}).get("sheet"),
         "row": row.get("__row")}
        for row in (rows or [])[:20]
    ]
    return {
        "status": "success",
        "provider": "zoho_workdrive",
        "file": meta or {"id": file_id},
        "content_b64": base64.b64encode(content).decode("ascii"),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "rows": rows or [],
        "parse_error": (tabular or {}).get("error"),
        "read_receipt": _receipt(
            "zoho_workdrive", "download_file", resource_id=file_id,
            version=str((meta or {}).get("version") or ""),
            coverage="complete",
            account_id=str(args.get("workspace_id") or ""),
            kind=args.get("evidence_kind") or ("price_rows" if rows else None),
            customer_id=args.get("customer_id"),
            price_basis=args.get("price_basis"),
            effective_date=args.get("effective_date"),
            fields=typed_fields,
            rows=rows or [],
            citations=citations,
            evidence=[{"kind": "file", "id": file_id,
                       "sha256": hashlib.sha256(content).hexdigest()}],
        ),
    }


@register_action(
    "brennan.onedrive.list_page",
    description="List one bounded OneDrive/SharePoint page. Explicit drive/site identity is preserved.",
    parameters_schema={
        "type": "object",
        "properties": {"folder_id": {"type": "string"},
                       "drive_id": {"type": "string"},
                       "site_id": {"type": "string"},
                       "cursor": {"type": "string"},
                       "page_size": {"type": "integer"}},
    },
    effects=[{"effect": "read"}],
)
async def onedrive_list_page(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    service = await _onedrive_service(ids)
    token, resolution = await service.get_access_token_resolution(ids["user_id"])
    if not token:
        return _error("onedrive", "list_files_page", "auth_unavailable",
                      "No Microsoft Graph token for this user.",
                      reconnect=True)
    result = await service.list_files_page(
        token, args.get("folder_id"), cursor=args.get("cursor"),
        page_size=int(args.get("page_size") or 100),
        drive_id=args.get("drive_id"), site_id=args.get("site_id"))
    if result.get("status") != "success":
        return result
    return {
        "status": "success",
        "provider": "onedrive",
        "items": result.get("items") or [],
        "next_cursor": result.get("next_cursor"),
        "has_more": bool(result.get("has_more")),
        "read_receipt": _receipt(
            "onedrive", "list_files_page",
            resource_id=str(args.get("folder_id") or args.get("drive_id") or ""),
            coverage=str(result.get("coverage") or "partial"),
            account_id=str(args.get("drive_id") or args.get("site_id") or ""),
            kind=args.get("evidence_kind"),
            customer_id=args.get("customer_id"),
            fields=["id", "name", "type", "version", "modified_at", "size"],
            continuation={"next_cursor": result.get("next_cursor"),
                          "has_more": bool(result.get("has_more"))},
        ),
    }


@register_action(
    "brennan.onedrive.read_file",
    description="Download OneDrive/SharePoint file bytes as evidence; never JSON-decodes the content.",
    parameters_schema={
        "type": "object",
        "properties": {"file_id": {"type": "string"},
                       "max_bytes": {"type": "integer"},
                       "drive_id": {"type": "string"},
                       "site_id": {"type": "string"},
                       "evidence_kind": {"type": "string"},
                       "customer_id": {"type": "string"},
                       "price_basis": {"type": "string"},
                       "effective_date": {"type": "string"},
                       "typed_fields": {"type": "object"}},
        "required": ["file_id"],
    },
    effects=[{"effect": "read"}],
)
async def onedrive_read_file(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    file_id = str(args.get("file_id") or "")
    if not file_id:
        return _error("onedrive", "read_file", "invalid_request",
                      "file_id is required")
    service = await _onedrive_service(ids)
    token, resolution = await service.get_access_token_resolution(ids["user_id"])
    if not token:
        return _error("onedrive", "read_file", "auth_unavailable",
                      "No Microsoft Graph token for this user.",
                      reconnect=True)
    content = await service.download_file_bytes(token, file_id)
    if content is None:
        return _error("onedrive", "read_file", "provider_error",
                      "OneDrive file could not be read.")
    if len(content) > int(args.get("max_bytes") or _MAX_FILE_BYTES):
        return _error("onedrive", "read_file", "too_large",
                      "OneDrive file exceeds the bounded read size.")
    meta_result = await service.get_file_metadata(token, file_id)
    meta_data = (meta_result.get("data")
                 if isinstance(meta_result, dict)
                 and meta_result.get("status") == "success" else {}) or {}
    file_name = meta_data.get("name")
    tabular = _tabular_rows(content, file_name)
    rows = (tabular or {}).get("rows")
    typed_fields = args.get("typed_fields") or {
        "name": file_name,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if tabular:
        typed_fields = {
            **typed_fields,
            "columns": tabular.get("columns") or [],
            "sheet": tabular.get("sheet"),
            "truncated": bool(tabular.get("truncated")),
        }
        if tabular.get("error"):
            typed_fields["parse_error"] = tabular["error"]
    citations = [
        {"provider": "onedrive", "file_id": file_id,
         "sheet": (tabular or {}).get("sheet"),
         "row": row.get("__row")}
        for row in (rows or [])[:20]
    ]
    return {
        "status": "success",
        "provider": "onedrive",
        "file": {"id": file_id, "name": file_name},
        "content_b64": base64.b64encode(content).decode("ascii"),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "rows": rows or [],
        "parse_error": (tabular or {}).get("error"),
        "read_receipt": _receipt(
            "onedrive", "download_file_bytes", resource_id=file_id,
            version=str(meta_data.get("version") or ""),
            coverage="complete",
            account_id=str(args.get("drive_id") or args.get("site_id") or ""),
            kind=args.get("evidence_kind") or ("price_rows" if rows else None),
            customer_id=args.get("customer_id"),
            price_basis=args.get("price_basis"),
            effective_date=args.get("effective_date"),
            fields=typed_fields,
            rows=rows or [],
            citations=citations,
            evidence=[{"kind": "file", "id": file_id,
                       "sha256": hashlib.sha256(content).hexdigest()}],
        ),
    }


async def _crm_service(ids: Dict[str, str]):
    from integrations.zoho_crm_service import ZohoCRMService

    return ZohoCRMService(ids["tenant_id"], {})


@register_action(
    "brennan.crm.get_record",
    description="Read one CRM record by module and record id, with a typed read receipt.",
    parameters_schema={"type": "object",
                       "properties": {"module": {"type": "string"},
                                      "record_id": {"type": "string"}},
                       "required": ["module", "record_id"]},
    effects=[{"effect": "read"}],
)
async def crm_get_record(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    service = await _crm_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_crm", "get_record", "auth_unavailable",
                      "No Zoho CRM token for this user.", reconnect=True)
    data = await service.get_record(args["module"], args["record_id"],
                                    tenant_id=ids["tenant_id"])
    if isinstance(data, dict) and data.get("error"):
        return _error("zoho_crm", "get_record", "provider_error",
                      str(data["error"]))
    return {"status": "success", "provider": "zoho_crm", "data": data,
            "read_receipt": _receipt(
                "zoho_crm", "get_record", resource_id=args["record_id"],
                coverage="single",
                account_id=ids["workspace_id"] or "",
                kind=args.get("evidence_kind") or "crm_record",
                customer_id=args.get("customer_id")
                or (data.get("id") if isinstance(data, dict) else None),
                fields=data if isinstance(data, dict) else [])}


@register_action(
    "brennan.inventory.check_stock",
    description="Read observed stock for one item. Observation is not a reservation.",
    parameters_schema={"type": "object",
                       "properties": {"item_id": {"type": "string"},
                                      "organization_id": {"type": "string"}},
                       "required": ["item_id"]},
    effects=[{"effect": "read"}],
)
async def inventory_check_stock(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    from integrations.zoho_inventory_service import zoho_inventory_service
    token = await zoho_inventory_service._get_active_token(
        ids["tenant_id"], user_id=ids["user_id"] or None)
    stock = await zoho_inventory_service.check_stock(
        args["item_id"], token=token,
        organization_id=args.get("organization_id"),
        user_id=ids["user_id"] or None)
    if stock.get("error"):
        return _error("zoho_inventory", "check_stock", "provider_error",
                      str(stock["error"]))
    return {"status": "success", "provider": "zoho_inventory", "data": stock,
            "read_receipt": _receipt(
                "zoho_inventory", "check_stock",
                resource_id=args["item_id"], coverage="observed",
                account_id=args.get("organization_id") or "",
                kind="product",
                fields=stock if isinstance(stock, dict) else
                ["item_id", "stock_on_hand", "available_stock"])}


@register_action(
    "brennan.books.get_bill",
    description="Read one Zoho Books bill with organization binding and readback evidence.",
    parameters_schema={"type": "object",
                       "properties": {"organization_id": {"type": "string"},
                                      "bill_id": {"type": "string"}},
                       "required": ["organization_id", "bill_id"]},
    effects=[{"effect": "read"}],
)
async def books_get_bill(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    from integrations.zoho_books_service import ZohoBooksService
    service = ZohoBooksService(ids["tenant_id"], {})
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_books", "get_bill", "auth_unavailable",
                      "No Zoho Books token for this user.", reconnect=True)
    data = await service.get_bill(token, args["organization_id"],
                                  args["bill_id"])
    return {"status": "success", "provider": "zoho_books", "data": data,
            "read_receipt": _receipt(
                "zoho_books", "get_bill", resource_id=args["bill_id"],
                coverage="single",
                account_id=args["organization_id"],
                kind="bill",
                fields=data if isinstance(data, dict) else [])}


@register_action(
    "brennan.outlook.create_draft",
    description="Create an Outlook draft only. Never sends; sending requires separate authority.",
    parameters_schema={"type": "object",
                       "properties": {"to": {"type": "array"},
                                      "cc": {"type": "array"},
                                      "bcc": {"type": "array"},
                                      "subject": {"type": "string"},
                                      "body": {"type": "string"},
                                      "authority_reference": {"type": "string"},
                                      "operation_id": {"type": "string"},
                                      "payload_sha256": {"type": "string"}},
                       "required": ["to", "subject", "body", "operation_id"]},
    effects=[{"effect": "create"}],
)
@_serialized_effect(_draft_effect_key)
async def outlook_create_draft(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    operation_id = str(args.get("operation_id") or "")
    if not operation_id:
        return _error("outlook", "create_draft_email", "invalid_request",
                      "A durable operation_id is required.",
                      action_result="proven_not_applied")
    draft_payload = _draft_payload(args)
    payload_sha256 = _payload_digest(draft_payload)
    supplied_digest = str(args.get("payload_sha256") or "")
    base_receipt = {
        "operation_id": operation_id,
        "authority_reference": str(args.get("authority_reference") or ""),
        "payload_sha256": payload_sha256,
    }
    if supplied_digest and supplied_digest != payload_sha256:
        return {
            **_error("outlook", "create_draft_email", "payload_changed",
                     "The authorized payload digest does not match this draft.",
                     action_result="conflict"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }
    from integrations.outlook_service import OutlookService
    service = OutlookService(ids["tenant_id"], {})
    token = context.get("access_token") or args.get("access_token")
    if not token:
        try:
            token = await service._get_access_token(ids["user_id"])
        except Exception:
            token = None
    if not token:
        return {
            **_error("outlook", "create_draft_email", "auth_unavailable",
                     "No Outlook token for this user.",
                     reconnect=True, action_result="proven_not_applied"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }
    try:
        result = await service.create_draft_email(
            user_id=ids["user_id"],
            to_recipients=draft_payload["to"],
            subject=draft_payload["subject"], body=draft_payload["body"],
            cc_recipients=draft_payload["cc"],
            bcc_recipients=draft_payload["bcc"], token=token)
    except Exception as exc:  # noqa: BLE001 - draft may have landed
        return _write_failure(
            "outlook", "create_draft_email", exc, may_have_landed=True,
            payload_sha256=payload_sha256, operation_id=operation_id)
    if not result:
        return {
            **_error("outlook", "create_draft_email", "provider_error",
                     "Outlook did not create a draft.",
                     action_result="uncertain"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }
    remote_id = str((result or {}).get("id") or "")
    if not remote_id:
        return {
            **_error("outlook", "create_draft_email", "provider_error",
                     "Outlook returned no draft identity; reconciliation is "
                     "required.",
                     action_result="uncertain"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }
    created_receipt = {**base_receipt, "created_remote_id": remote_id}
    try:
        readback = await service.get_email_by_id(
            ids["user_id"], remote_id, token=token)
    except Exception as exc:  # noqa: BLE001 - the create may have landed
        return {
            **_error("outlook", "create_draft_email", "readback_unavailable",
                     f"Draft {remote_id} was created but could not be read "
                     f"back: {type(exc).__name__}.",
                     action_result="uncertain"),
            "remote_id": remote_id,
            "observed_remote_id": "",
            "requested_remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": created_receipt,
            "verification": {
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
        }
    if not isinstance(readback, dict) or not readback:
        return {
            **_error("outlook", "create_draft_email", "readback_unavailable",
                     f"Draft {remote_id} was created but not returned by "
                     "independent readback.",
                     action_result="uncertain"),
            "remote_id": remote_id,
            "observed_remote_id": "",
            "requested_remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": created_receipt,
            "verification": {
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
        }
    observed_id = str(readback.get("id") or "")
    missing_fields = _outlook_missing_fields(readback)
    if not observed_id:
        missing_fields.insert(0, "id")
    if missing_fields:
        return {
            **_error("outlook", "create_draft_email", "readback_incomplete",
                     "Draft readback lacks a complete remote identity or "
                     "material fields; reconcile the same draft without a "
                     "second create.",
                     action_result="uncertain"),
            "remote_id": remote_id,
            "observed_remote_id": observed_id,
            "requested_remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": created_receipt,
            "data": readback,
            "verification": {
                "status": "incomplete",
                "missing_fields": missing_fields,
                "mismatches": [],
            },
            "read_receipt": _draft_read_receipt(
                readback, requested_id=remote_id, observed_id=observed_id),
        }
    if observed_id != remote_id:
        return {
            **_error("outlook", "create_draft_email", "readback_object_mismatch",
                     "Draft readback returned a different remote object.",
                     action_result="conflict"),
            "remote_id": remote_id,
            "observed_remote_id": observed_id,
            "requested_remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": created_receipt,
            "data": readback,
            "verification": {
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": ["remote_id"],
            },
            "read_receipt": _draft_read_receipt(
                readback, requested_id=remote_id, observed_id=observed_id),
        }
    observed = _normalize_outlook_draft(readback)
    expected = _normalize_outlook_draft({
        "subject": draft_payload["subject"],
        "body": {"content": draft_payload["body"]},
        "toRecipients": [
            {"emailAddress": {"address": item}}
            for item in draft_payload["to"]
        ],
        "ccRecipients": [
            {"emailAddress": {"address": item}}
            for item in draft_payload["cc"]
        ],
        "bccRecipients": [
            {"emailAddress": {"address": item}}
            for item in draft_payload["bcc"]
        ],
    })
    mismatches = [
        key for key in ("subject", "body", "to", "cc", "bcc")
        if observed.get(key) != expected.get(key)
    ]
    if mismatches:
        return {
            **_error("outlook", "create_draft_email", "readback_mismatch",
                     "Draft readback does not match the authorized payload.",
                     action_result="conflict"),
            "remote_id": remote_id,
            "observed_remote_id": observed_id,
            "requested_remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": created_receipt,
            "data": readback,
            "verification": {
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": mismatches,
            },
            "read_receipt": _draft_read_receipt(
                readback, requested_id=remote_id, observed_id=observed_id),
        }
    return {"status": "success", "success": True,
            "action_result": "applied",
            "provider": "outlook", "operation": "create_draft_email",
            "remote_id": remote_id,
            "observed_remote_id": observed_id,
            "requested_remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "provider_receipt": created_receipt,
            "data": readback,
            "verification": {
                "status": "verified",
                "missing_fields": [],
                "mismatches": [],
            },
            "read_receipt": _draft_read_receipt(
                readback, requested_id=remote_id, observed_id=observed_id)}


# Importing this module is enough to register the actions.  Keep the
# provider imports lazy so importing core.action_registry stays light.
__all__ = [
    "workdrive_list_page", "workdrive_read_file", "onedrive_list_page",
    "onedrive_read_file", "crm_get_record", "inventory_check_stock",
    "books_get_bill", "outlook_create_draft",
]


async def _books_service(ids: Dict[str, str]):
    from integrations.zoho_books_service import ZohoBooksService

    return ZohoBooksService(ids["tenant_id"], {})


@register_action(
    "brennan.crm.search_records",
    description="Search one CRM module by query; returns exact record IDs and a bounded coverage receipt.",
    parameters_schema={"type": "object",
                       "properties": {"module": {"type": "string"},
                                      "query": {"type": "string"}},
                       "required": ["module", "query"]},
    effects=[{"effect": "read"}],
)
async def crm_search_records(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    service = await _crm_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_crm", "search_records", "auth_unavailable",
                      "No Zoho CRM token for this user.", reconnect=True)
    service.access_token = token
    data = await service.search_records(
        args["module"], args["query"], tenant_id=None)
    return {"status": "success", "provider": "zoho_crm",
            "items": data if isinstance(data, list) else [data],
            "read_receipt": _receipt(
                "zoho_crm", "search_records",
                resource_id=str(args["module"]), coverage="bounded",
                account_id=ids["workspace_id"] or "",
                kind=args.get("evidence_kind") or "crm_records",
                rows=data if isinstance(data, list) else [data],
                fields=["id", "name", "module", "Modified_Time"])}


@register_action(
    "brennan.inventory.get_item",
    description="Read one inventory item and its observed availability; never reserves stock.",
    parameters_schema={"type": "object",
                       "properties": {"item_id": {"type": "string"},
                                      "organization_id": {"type": "string"}},
                       "required": ["item_id"]},
    effects=[{"effect": "read"}],
)
async def inventory_get_item(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    from integrations.zoho_inventory_service import zoho_inventory_service
    token = await zoho_inventory_service._get_active_token(
        ids["tenant_id"], user_id=ids["user_id"] or None)
    if not token:
        return _error("zoho_inventory", "get_item", "auth_unavailable",
                      "No Zoho Inventory token for this user.", reconnect=True)
    items = await zoho_inventory_service.get_items(
        token, args.get("organization_id"), user_id=ids["user_id"] or None)
    if getattr(zoho_inventory_service, "last_error", None):
        return zoho_inventory_service.last_error
    item = next((row for row in items
                 if str(row.get("item_id") or row.get("id") or "")
                 == str(args["item_id"])), None)
    if item is None:
        return _error("zoho_inventory", "get_item", "not_found",
                      "The requested inventory item was not found.")
    return {"status": "success", "provider": "zoho_inventory", "data": item,
            "read_receipt": _receipt(
                "zoho_inventory", "get_item", resource_id=args["item_id"],
                coverage="single",
                account_id=args.get("organization_id") or "",
                kind="product",
                fields=item if isinstance(item, dict) else
                ["item_id", "sku", "name", "unit", "stock_on_hand",
                 "available_stock"])}


@register_action(
    "brennan.books.get_estimate",
    description="Read one Zoho Books estimate with organization binding and readback evidence.",
    parameters_schema={"type": "object",
                       "properties": {"organization_id": {"type": "string"},
                                      "estimate_id": {"type": "string"}},
                       "required": ["organization_id", "estimate_id"]},
    effects=[{"effect": "read"}],
)
async def books_get_estimate(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_books", "get_estimate", "auth_unavailable",
                      "No Zoho Books token for this user.", reconnect=True)
    data = await service.get_estimate(
        token, args["organization_id"], args["estimate_id"])
    return {"status": "success", "provider": "zoho_books", "data": data,
            "read_receipt": _receipt(
                "zoho_books", "get_estimate",
                resource_id=args["estimate_id"], coverage="single",
                account_id=args["organization_id"],
                kind="estimate",
                fields=data if isinstance(data, dict) else [])}


def _bill_payload(proposal: Dict[str, Any]) -> Dict[str, Any]:
    lines = []
    for line in proposal.get("lines") or []:
        amount = line.get("amount")
        lines.append({
            "name": str(line.get("description") or "Supplier line"),
            "description": str(line.get("description") or ""),
            "quantity": str(line.get("quantity") or "1"),
            "rate": str(line.get("unit_price") or amount),
            "account_id": line.get("account_id"),
        })
    payload = {
        "vendor_id": (proposal.get("vendor") or {}).get("id"),
        "bill_number": proposal.get("external_id"),
        "reference_number": proposal.get("external_id"),
        "date": proposal.get("document_date"),
        "currency_code": proposal.get("currency"),
        "line_items": lines,
        "notes": "Prepared by Atom bookkeeping proposal",
    }
    if proposal.get("due_date"):
        payload["due_date"] = proposal["due_date"]
    return payload


@register_action(
    "brennan.books.propose_bill",
    description="Validate extracted supplier facts and return a reviewed bill proposal; never posts.",
    parameters_schema={"type": "object",
                       "properties": {"proposal_input": {"type": "object"}},
                       "required": ["proposal_input"]},
    effects=[{"effect": "read"}],
)
async def books_propose_bill(args: Dict[str, Any], context: Dict[str, Any]):
    from accounting.bookkeeping_proposal import build_proposal
    try:
        result = build_proposal(**(args.get("proposal_input") or {}))
    except Exception as exc:  # ProposalError and malformed input
        return _error("zoho_books", "propose_bill", "invalid_request", str(exc))
    return {"status": "success", "provider": "zoho_books", "data": result,
            "read_receipt": _receipt(
                "zoho_books", "propose_bill",
                resource_id=str(result.get("external_id") or ""),
                coverage="document",
                account_id=str((args.get("proposal_input") or {}).get(
                    "organization_id") or ""),
                kind="bill_proposal",
                fields=result)}


@register_action(
    "brennan.books.create_bill",
    description="Post an authorized, reviewed bill proposal and read it back. Requires explicit authority and operation id.",
    parameters_schema={"type": "object",
                       "properties": {"proposal": {"type": "object"},
                                      "authority_reference": {"type": "string"},
                                      "operation_id": {"type": "string"},
                                      "payload_sha256": {"type": "string"},
                                      "proposal_version": {"type": "string"},
                                      "period_start": {"type": "string"},
                                      "period_end": {"type": "string"},
                                      "closed_through": {"type": "string"}},
                       "required": ["proposal", "authority_reference",
                                    "operation_id"]},
    effects=[{"effect": "create"}],
)
@_serialized_effect(_bill_effect_key)
async def books_create_bill(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    proposal = args.get("proposal") or {}
    authority = str(args.get("authority_reference") or "")
    operation_id = str(args.get("operation_id") or "")
    proposal_version = str(
        args.get("proposal_version") or proposal.get("version") or "1")
    if proposal.get("status") != "proposed":
        return _error("zoho_books", "create_bill", "invalid_request",
                      "Only a reviewed proposal in status 'proposed' can be posted.")
    if not authority:
        return _error("zoho_books", "create_bill", "unauthorized",
                      "An explicit authority reference is required.",
                      action_result="proven_not_applied")
    if not operation_id:
        return _error("zoho_books", "create_bill", "invalid_request",
                      "A durable operation_id is required.",
                      action_result="proven_not_applied")
    org = str(proposal.get("organization_id") or "")
    if not org:
        return _error("zoho_books", "create_bill", "invalid_request",
                      "organization_id is required.",
                      action_result="proven_not_applied")
    external_id = str(proposal.get("external_id") or "")
    if not external_id:
        return _error("zoho_books", "create_bill", "invalid_request",
                      "external_id is required for duplicate identity.",
                      action_result="proven_not_applied")
    if not proposal.get("lines"):
        return _error("zoho_books", "create_bill", "invalid_request",
                      "A bill requires at least one authorized line item.",
                      action_result="proven_not_applied")

    payload = _bill_payload(proposal)
    payload_sha256 = _payload_digest(payload)
    supplied_digest = str(args.get("payload_sha256") or "")
    base_receipt = {
        "operation_id": operation_id,
        "authority_reference": authority,
        "payload_sha256": payload_sha256,
        "proposal_version": proposal_version,
    }
    if supplied_digest and supplied_digest != payload_sha256:
        return {
            **_error(
                "zoho_books", "create_bill", "payload_changed",
                "The authorized payload digest does not match this proposal.",
                action_result="conflict"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }

    period_error = _validate_accounting_period(
        proposal.get("document_date"),
        period_start=args.get("period_start"),
        period_end=args.get("period_end"),
        closed_through=args.get("closed_through"))
    if period_error:
        period_error["payload_sha256"] = payload_sha256
        period_error["provider_receipt"] = base_receipt
        return period_error

    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return {
            **_error("zoho_books", "create_bill", "auth_unavailable",
                     "No Zoho Books token for this user.",
                     action_result="proven_not_applied"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }

    # Account references must exist in the organization's complete chart of
    # accounts.  Posting an unmapped line is refused, not guessed.
    try:
        account_ids = await _chart_of_account_ids(service, token, org)
    except Exception as exc:  # noqa: BLE001 - typed below
        result = _write_failure(
            "zoho_books", "get_chart_of_accounts", exc,
            may_have_landed=False, payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **base_receipt, **result.get("provider_receipt", {})}
        return result
    line_accounts = {
        str(line.get("account_id") or "").strip()
        for line in proposal.get("lines") or []
        if str(line.get("account_id") or "").strip()
    }
    unknown = sorted(line_accounts - account_ids)
    if unknown:
        return {
            **_error(
                "zoho_books", "create_bill", "invalid_request",
                "Unknown account reference(s): " + ", ".join(unknown),
                action_result="proven_not_applied"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
            "unknown_account_ids": unknown,
        }

    # Exact duplicate identity check over the complete bounded sweep.  An
    # unavailable page cannot be read as "no duplicate"; the action refuses
    # to dispatch rather than risk a second provider bill.
    existing = []
    page = 1
    try:
        while True:
            rows, page_info = await service.get_bills_page(
                token, org, page=page, per_page=200)
            existing.extend(rows)
            if not page_info.get("has_more"):
                break
            page += 1
            if page > 50:
                return {
                    **_error(
                        "zoho_books", "create_bill", "unavailable",
                        "The duplicate sweep exceeded its bounded page limit; "
                        "creation was not attempted.",
                        action_result="proven_not_applied"),
                    "payload_sha256": payload_sha256,
                    "provider_receipt": base_receipt,
                }
    except Exception as exc:  # noqa: BLE001 - typed failure below
        result = _write_failure(
            "zoho_books", "get_bills", exc, may_have_landed=False,
            payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **base_receipt, **result.get("provider_receipt", {})}
        return result
    duplicate = next((
        item for item in existing
        if external_id in {
            str(item.get("reference_number") or ""),
            str(item.get("bill_number") or ""),
        }), None)
    if duplicate:
        return {
            "status": "duplicate",
            "success": False,
            "action_result": "proven_not_applied",
            "provider": "zoho_books",
            "operation": "create_bill",
            "remote_id": str(duplicate.get("bill_id") or ""),
            "payload_sha256": payload_sha256,
            "existing": duplicate,
            "provider_receipt": base_receipt,
            "read_receipt": _receipt(
                "zoho_books", "get_bills",
                resource_id=str(duplicate.get("bill_id") or ""),
                coverage="complete", account_id=org, kind="bill",
                fields=duplicate),
        }

    try:
        created = await service.create_bill(token, org, payload)
    except Exception as exc:  # noqa: BLE001 - classify below
        result = _write_failure(
            "zoho_books", "create_bill", exc, may_have_landed=True,
            payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **base_receipt, **result.get("provider_receipt", {})}
        return result
    remote_id = str(created.get("bill_id") or created.get("id") or "")
    if not remote_id:
        # The provider accepted the POST but did not identify the object.  The
        # effect may exist, so this is uncertain, not failed.
        return {
            **_error(
                "zoho_books", "create_bill", "provider_error",
                "Zoho Books accepted the create but returned no bill id.",
                action_result="uncertain"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }
    readback, verification, readback_error, attempts = await _readback_with_retry(
        lambda: service.get_bill(token, org, remote_id),
        lambda data: bind_remote_identity(
            verify_bill_readback(
                proposal, payload, data, organization_id=org),
            remote_id))
    receipt = {**base_receipt, "readback_attempts": attempts,
               "observed_remote_id": remote_id}
    if readback_error is not None and not verification:
        result = _write_failure(
            "zoho_books", "get_bill", readback_error, may_have_landed=True,
            remote_id=remote_id, payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **receipt, **result.get("provider_receipt", {})}
        result["verification"] = {
            "status": "incomplete", "effect": "observed",
            "missing_fields": ["readback"], "mismatches": [],
            "attempts": attempts,
        }
        return result
    if verification["status"] == "mismatch":
        return {
            "status": "conflict",
            "success": False,
            "action_result": "conflict",
            "provider": "zoho_books",
            "operation": "create_bill",
            "remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "conflicts": verification["conflicts"],
            "verification": verification,
            "data": readback,
            "provider_receipt": receipt,
            "read_receipt": _receipt(
                "zoho_books", "get_bill", resource_id=remote_id,
                coverage="single", account_id=org, kind="bill",
                fields=readback if isinstance(readback, dict) else []),
        }
    if verification["status"] == "incomplete":
        return {
            **_error(
                "zoho_books", "create_bill", "provider_error",
                "The bill was created but the readback is incomplete; "
                "reconcile the same remote object without a second create.",
                action_result="uncertain"),
            "success": False,
            "remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "verification": verification,
            "data": readback,
            "provider_receipt": receipt,
        }
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": "zoho_books",
        "operation": "create_bill",
        "remote_id": remote_id,
        "payload_sha256": payload_sha256,
        "verification": verification,
        "provider_receipt": receipt,
        "data": readback,
        "read_receipt": _receipt(
            "zoho_books", "get_bill", resource_id=remote_id,
            coverage="single", account_id=org, kind="bill",
            fields=readback if isinstance(readback, dict) else []),
    }


@register_action(
    "brennan.books.create_estimate",
    description="Post an authorized quote estimate and read it back. Requires explicit authority and operation id.",
    parameters_schema={"type": "object",
                       "properties": {"organization_id": {"type": "string"},
                                      "estimate_data": {"type": "object"},
                                      "authority_reference": {"type": "string"},
                                      "operation_id": {"type": "string"},
                                      "payload_sha256": {"type": "string"},
                                      "artifact_version": {"type": "string"}},
                       "required": ["organization_id", "estimate_data",
                                    "authority_reference", "operation_id"]},
    effects=[{"effect": "create"}],
)
@_serialized_effect(_estimate_effect_key)
async def books_create_estimate(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    authority = str(args.get("authority_reference") or "")
    operation_id = str(args.get("operation_id") or "")
    artifact_version = str(
        args.get("artifact_version")
        or (args.get("estimate_data") or {}).get("version") or "1")
    if not authority:
        return _error("zoho_books", "create_estimate", "unauthorized",
                      "An explicit authority reference is required.",
                      action_result="proven_not_applied")
    if not operation_id:
        return _error("zoho_books", "create_estimate", "invalid_request",
                      "A durable operation_id is required.",
                      action_result="proven_not_applied")
    org = str(args.get("organization_id") or "")
    if not org:
        return _error("zoho_books", "create_estimate", "invalid_request",
                      "organization_id is required.",
                      action_result="proven_not_applied")
    estimate_data = _normalize_estimate_data(args.get("estimate_data") or {})
    if not isinstance(estimate_data, dict) or not estimate_data:
        return _error("zoho_books", "create_estimate", "invalid_request",
                      "estimate_data must be a non-empty object.",
                      action_result="proven_not_applied")
    reference = str(estimate_data.get("reference_number") or "").strip()
    if not reference:
        return _error(
            "zoho_books", "create_estimate", "invalid_request",
            "estimate_data.reference_number is required for duplicate identity.",
            action_result="proven_not_applied")
    required_material = {
        "customer_id": estimate_data.get("customer_id"),
        "currency_code": (estimate_data.get("currency_code")
                          or estimate_data.get("currency")),
        "date": estimate_data.get("date"),
        "total": (estimate_data.get("total")
                  or estimate_data.get("grand_total")),
        "line_items": (estimate_data.get("line_items")
                       or estimate_data.get("lines")),
    }
    missing = [field for field, value in required_material.items()
               if value in (None, "", [], {})]
    if missing:
        return _error(
            "zoho_books", "create_estimate", "invalid_request",
            "estimate_data is missing material field(s): "
            + ", ".join(missing),
            action_result="proven_not_applied")
    if (estimate_data.get("tax_total") in (None, "")
            and estimate_data.get("tax_treatment") in (None, "")
            and estimate_data.get("tax") in (None, "", {})):
        return _error(
            "zoho_books", "create_estimate", "invalid_request",
            "estimate_data must state tax_total or tax_treatment explicitly.",
            action_result="proven_not_applied")

    payload_sha256 = _payload_digest(estimate_data)
    supplied_digest = str(args.get("payload_sha256") or "")
    base_receipt = {
        "operation_id": operation_id,
        "authority_reference": authority,
        "payload_sha256": payload_sha256,
        "artifact_version": artifact_version,
    }
    if supplied_digest and supplied_digest != payload_sha256:
        return {
            **_error(
                "zoho_books", "create_estimate", "payload_changed",
                "The authorized payload digest does not match this estimate.",
                action_result="conflict"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }

    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return {
            **_error("zoho_books", "create_estimate", "auth_unavailable",
                     "No Zoho Books token for this user.",
                     action_result="proven_not_applied"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }

    existing = []
    page = 1
    try:
        while True:
            rows, info = await service.get_estimates_page(
                token, org, page=page, per_page=200)
            existing.extend(rows)
            if not info.get("has_more"):
                break
            page += 1
            if page > 50:
                return {
                    **_error(
                        "zoho_books", "create_estimate", "unavailable",
                        "The duplicate sweep exceeded its bounded page limit; "
                        "creation was not attempted.",
                        action_result="proven_not_applied"),
                    "payload_sha256": payload_sha256,
                    "provider_receipt": base_receipt,
                }
    except Exception as exc:  # noqa: BLE001 - typed failure below
        result = _write_failure(
            "zoho_books", "get_estimates", exc, may_have_landed=False,
            payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **base_receipt, **result.get("provider_receipt", {})}
        return result
    duplicate = next((
        item for item in existing
        if reference in {
            str(item.get("reference_number") or ""),
            str(item.get("estimate_number") or ""),
        }), None)
    if duplicate:
        return {
            "status": "duplicate",
            "success": True,
            "action_result": "proven_not_applied",
            "provider": "zoho_books",
            "operation": "create_estimate",
            "remote_id": str(duplicate.get("estimate_id") or ""),
            "payload_sha256": payload_sha256,
            "existing": duplicate,
            "provider_receipt": base_receipt,
            "read_receipt": _receipt(
                "zoho_books", "get_estimates",
                resource_id=str(duplicate.get("estimate_id") or ""),
                coverage="complete", account_id=org, kind="estimate",
                fields=duplicate),
        }

    try:
        created = await service.create_estimate(token, org, estimate_data)
    except Exception as exc:  # noqa: BLE001 - classify below
        result = _write_failure(
            "zoho_books", "create_estimate", exc, may_have_landed=True,
            payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **base_receipt, **result.get("provider_receipt", {})}
        return result
    remote_id = str(created.get("estimate_id") or created.get("id") or "")
    if not remote_id:
        return {
            **_error(
                "zoho_books", "create_estimate", "provider_error",
                "Zoho Books accepted the create but returned no estimate id.",
                action_result="uncertain"),
            "payload_sha256": payload_sha256,
            "provider_receipt": base_receipt,
        }
    readback, verification, readback_error, attempts = await _readback_with_retry(
        lambda: service.get_estimate(token, org, remote_id),
        lambda data: bind_remote_identity(
            verify_estimate_readback(
                estimate_data, data, organization_id=org),
            remote_id))
    receipt = {**base_receipt, "readback_attempts": attempts,
               "observed_remote_id": remote_id}
    if readback_error is not None and not verification:
        result = _write_failure(
            "zoho_books", "get_estimate", readback_error, may_have_landed=True,
            remote_id=remote_id, payload_sha256=payload_sha256,
            authority_reference=authority, operation_id=operation_id)
        result["provider_receipt"] = {
            **receipt, **result.get("provider_receipt", {})}
        result["verification"] = {
            "status": "incomplete", "effect": "observed",
            "missing_fields": ["readback"], "mismatches": [],
            "attempts": attempts,
        }
        return result
    if verification["status"] == "mismatch":
        return {
            "status": "conflict",
            "success": False,
            "action_result": "conflict",
            "provider": "zoho_books",
            "operation": "create_estimate",
            "remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "conflicts": verification["conflicts"],
            "verification": verification,
            "data": readback,
            "provider_receipt": receipt,
            "read_receipt": _receipt(
                "zoho_books", "get_estimate", resource_id=remote_id,
                coverage="single", account_id=org, kind="estimate",
                fields=readback if isinstance(readback, dict) else []),
        }
    if verification["status"] == "incomplete":
        return {
            **_error(
                "zoho_books", "create_estimate", "provider_error",
                "The estimate was created but the readback is incomplete; "
                "reconcile the same remote object without a second create.",
                action_result="uncertain"),
            "success": False,
            "remote_id": remote_id,
            "payload_sha256": payload_sha256,
            "verification": verification,
            "data": readback,
            "provider_receipt": receipt,
        }
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": "zoho_books",
        "operation": "create_estimate",
        "remote_id": remote_id,
        "payload_sha256": payload_sha256,
        "verification": verification,
        "provider_receipt": receipt,
        "data": readback,
        "read_receipt": _receipt(
            "zoho_books", "get_estimate", resource_id=remote_id,
            coverage="single", account_id=org, kind="estimate",
            fields=readback if isinstance(readback, dict) else []),
    }


@register_action(
    "brennan.workdrive.sync_page",
    description="Read, index and checkpoint one WorkDrive page. Restart resumes from the stored cursor; revocation is a typed error.",
    parameters_schema={"type": "object",
                       "properties": {"folder_id": {"type": "string"},
                                      "provider_workspace_id": {"type": "string"},
                                      "team_id": {"type": "string"},
                                      "cursor": {"type": "string"},
                                      "page_size": {"type": "integer"},
                                      "fresh": {"type": "boolean"},
                                      "max_rows": {"type": "integer"}}},
    effects=[{"effect": "read"}],
)
async def workdrive_sync_page(args: Dict[str, Any], context: Dict[str, Any]):
    from core.drive_sync_checkpoints import sync_drive_page

    ids = _ids(args, context)
    return await sync_drive_page(
        provider="zoho_workdrive",
        user_id=ids["user_id"],
        workspace_id=ids["workspace_id"] or "default",
        tenant_id=ids["tenant_id"],
        folder_id=args.get("folder_id") or "root",
        provider_workspace_id=args.get("provider_workspace_id")
        or ids["workspace_id"] or None,
        team_id=args.get("team_id"),
        cursor=args.get("cursor"),
        page_size=int(args.get("page_size") or 100),
        fresh=bool(args.get("fresh")),
        max_rows=int(args.get("max_rows") or 500),
    )


@register_action(
    "brennan.onedrive.sync_page",
    description="Read, index and checkpoint one OneDrive/SharePoint page with explicit drive/site identity.",
    parameters_schema={"type": "object",
                       "properties": {"folder_id": {"type": "string"},
                                      "drive_id": {"type": "string"},
                                      "site_id": {"type": "string"},
                                      "cursor": {"type": "string"},
                                      "page_size": {"type": "integer"},
                                      "fresh": {"type": "boolean"},
                                      "max_rows": {"type": "integer"}}},
    effects=[{"effect": "read"}],
)
async def onedrive_sync_page(args: Dict[str, Any], context: Dict[str, Any]):
    from core.drive_sync_checkpoints import sync_drive_page

    ids = _ids(args, context)
    return await sync_drive_page(
        provider="onedrive",
        user_id=ids["user_id"],
        workspace_id=ids["workspace_id"] or "default",
        tenant_id=ids["tenant_id"],
        folder_id=args.get("folder_id"),
        drive_id=args.get("drive_id"),
        site_id=args.get("site_id"),
        cursor=args.get("cursor"),
        page_size=int(args.get("page_size") or 100),
        fresh=bool(args.get("fresh")),
        max_rows=int(args.get("max_rows") or 500),
    )


@register_action(
    "brennan.knowledge.sync_status",
    description="Report durable drive-sync coverage, cursor, last success, stale age, revocation and remote deletions.",
    parameters_schema={"type": "object",
                       "properties": {"provider": {"type": "string"},
                                      "folder_id": {"type": "string"},
                                      "provider_workspace_id": {"type": "string"},
                                      "drive_id": {"type": "string"},
                                      "site_id": {"type": "string"},
                                      "max_age_seconds": {"type": "integer"}},
                       "required": ["provider"]},
    effects=[{"effect": "read"}],
)
async def knowledge_sync_status(args: Dict[str, Any], context: Dict[str, Any]):
    from core.drive_sync_checkpoints import checkpoint_scope, coverage_status

    ids = _ids(args, context)
    provider = str(args.get("provider") or "").strip().lower()
    if provider not in ("zoho_workdrive", "onedrive"):
        return _error("knowledge", "sync_status", "invalid_request",
                      "provider must be zoho_workdrive or onedrive.")
    scope = checkpoint_scope(
        provider, folder_id=args.get("folder_id"),
        drive_id=args.get("drive_id"), site_id=args.get("site_id"),
        provider_workspace_id=args.get("provider_workspace_id")
        or ids["workspace_id"] or None)
    result = coverage_status(
        provider, scope, workspace_id=ids["workspace_id"] or "default",
        tenant_id=ids["tenant_id"],
        max_age_seconds=int(args.get("max_age_seconds") or
                            24 * 60 * 60))
    result["operation"] = "sync_status"
    return result


@register_action(
    "brennan.books.resolve_vendor",
    description="Resolve a supplier name to exact vendor IDs from the complete vendor list; same-name IDs are ambiguous.",
    parameters_schema={"type": "object",
                       "properties": {"name": {"type": "string"},
                                      "organization_id": {"type": "string"}},
                       "required": ["name"]},
    effects=[{"effect": "read"}],
)
async def books_resolve_vendor(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    name = str(args.get("name") or "").strip()
    if not name:
        return _error("zoho_books", "resolve_vendor", "invalid_request",
                      "name is required.")
    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_books", "resolve_vendor", "auth_unavailable",
                      "No Zoho Books token for this user.", reconnect=True)
    org = str(args.get("organization_id") or "")
    if not org:
        try:
            orgs = await service.get_organizations_strict(token)
        except Exception as exc:  # noqa: BLE001
            return _write_failure(
                "zoho_books", "get_organizations", exc, may_have_landed=False)
        org = str((orgs[0] if orgs else {}).get("organization_id") or "")
    if not org:
        return _error("zoho_books", "resolve_vendor", "auth_unavailable",
                      "No Zoho Books organization is available.")
    rows: List[Dict[str, Any]] = []
    page = 1
    try:
        while True:
            batch, info = await service.get_contacts_page(
                token, org, page=page, per_page=200, contact_type="vendor")
            rows.extend(batch)
            if not info.get("has_more"):
                break
            page += 1
            if page > 50:
                return _error(
                    "zoho_books", "resolve_vendor", "unavailable",
                    "Vendor sweep exceeded its bounded page limit.")
    except Exception as exc:  # noqa: BLE001
        return _write_failure(
            "zoho_books", "get_vendors", exc, may_have_landed=False)
    wanted = name.casefold()
    exact = [
        {"id": str(row.get("contact_id") or row.get("id") or ""),
         "name": str(row.get("contact_name") or row.get("name") or ""),
         "email": row.get("email") or "",
         "currency_code": row.get("currency_code") or ""}
        for row in rows
        if str(row.get("contact_name") or row.get("name") or "").strip().casefold()
        == wanted
    ]
    status = ("resolved" if len(exact) == 1
              else "ambiguous" if len(exact) > 1 else "missing")
    return {
        "status": "success",
        "provider": "zoho_books",
        "operation": "resolve_vendor",
        "match_status": status,
        "candidates": exact,
        "read_receipt": _receipt(
            "zoho_books", "get_vendors", resource_id=org,
            coverage="complete", account_id=org, kind="vendor_candidates",
            customer_id=None, fields={"requested_name": name,
                                      "match_status": status,
                                      "candidate_count": len(exact)},
        ),
    }


@register_action(
    "brennan.books.list_accounts",
    description="List the complete chart of accounts with exact IDs for proposal mapping.",
    parameters_schema={"type": "object",
                       "properties": {"organization_id": {"type": "string"},
                                      "query": {"type": "string"}},
                       "required": ["organization_id"]},
    effects=[{"effect": "read"}],
)
async def books_list_accounts(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_books", "list_accounts", "auth_unavailable",
                      "No Zoho Books token for this user.", reconnect=True)
    org = str(args["organization_id"])
    rows: List[Dict[str, Any]] = []
    page = 1
    try:
        while True:
            batch, info = await service.get_chart_of_accounts_page(
                token, org, page=page, per_page=200)
            rows.extend(batch)
            if not info.get("has_more"):
                break
            page += 1
            if page > 50:
                return _error(
                    "zoho_books", "list_accounts", "unavailable",
                    "Chart of accounts exceeded its bounded page limit.")
    except Exception as exc:  # noqa: BLE001
        return _write_failure(
            "zoho_books", "get_chart_of_accounts", exc,
            may_have_landed=False)
    query = str(args.get("query") or "").strip().casefold()
    if query:
        rows = [row for row in rows
                if query in str(row.get("account_name") or row.get("name")
                                or "").casefold()]
    accounts = [
        {"account_id": str(row.get("account_id") or row.get("id") or ""),
         "name": row.get("account_name") or row.get("name"),
         "type": row.get("account_type") or row.get("type"),
         "code": row.get("account_code") or row.get("code")}
        for row in rows
    ]
    return {
        "status": "success",
        "provider": "zoho_books",
        "operation": "list_accounts",
        "accounts": accounts,
        "read_receipt": _receipt(
            "zoho_books", "get_chart_of_accounts", resource_id=org,
            coverage="complete", account_id=org, kind="chart_of_accounts",
            fields={"count": len(accounts), "query": query},
        ),
    }


@register_action(
    "brennan.outlook.read_attachments",
    description="List or download invoice/receipt attachments from one Outlook message with binary evidence; never sends.",
    parameters_schema={"type": "object",
                       "properties": {"message_id": {"type": "string"},
                                      "attachment_id": {"type": "string"},
                                      "max_bytes": {"type": "integer"},
                                      "evidence_kind": {"type": "string"},
                                      "customer_id": {"type": "string"},
                                      "typed_fields": {"type": "object"}},
                       "required": ["message_id"]},
    effects=[{"effect": "read"}],
)
async def outlook_read_attachments(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    message_id = str(args.get("message_id") or "").strip()
    if not message_id:
        return _error("outlook", "read_attachments", "invalid_request",
                      "message_id is required.")
    from integrations.outlook_service import OutlookService

    service = OutlookService(ids["tenant_id"], {})
    token = context.get("access_token") or args.get("access_token")
    if not token:
        try:
            token = await service._get_access_token(ids["user_id"])
        except Exception:
            token = None
    if not token:
        return _error("outlook", "read_attachments", "auth_unavailable",
                      "No Outlook token for this user.", reconnect=True)
    attachments = await service.get_attachment_metadata(
        ids["user_id"], message_id, token=token)
    if service.last_error:
        return service.last_error
    attachment_id = str(args.get("attachment_id") or "").strip()
    if not attachment_id:
        return {
            "status": "success",
            "provider": "outlook",
            "operation": "read_attachments",
            "attachments": attachments,
            "read_receipt": _receipt(
                "outlook", "get_attachment_metadata",
                resource_id=message_id, coverage="complete",
                kind="attachment_index",
                fields={"count": len(attachments),
                        "attachments": attachments}),
        }
    content = await service.download_attachment(
        ids["user_id"], message_id, attachment_id, token=token)
    if content is None:
        return service.last_error or _error(
            "outlook", "read_attachments", "provider_error",
            "Outlook returned no attachment content.")
    if len(content) > int(args.get("max_bytes") or _MAX_FILE_BYTES):
        return _error("outlook", "read_attachments", "too_large",
                      "Outlook attachment exceeds the bounded read size.")
    meta = next((item for item in attachments
                 if str(item.get("id")) == attachment_id), {})
    digest = hashlib.sha256(content).hexdigest()
    return {
        "status": "success",
        "provider": "outlook",
        "operation": "read_attachments",
        "attachment": meta or {"id": attachment_id},
        "content_b64": base64.b64encode(content).decode("ascii"),
        "sha256": digest,
        "bytes": len(content),
        "read_receipt": _receipt(
            "outlook", "get_attachment_content",
            resource_id=attachment_id, coverage="complete",
            kind=args.get("evidence_kind") or "supplier_document",
            customer_id=args.get("customer_id"),
            fields=args.get("typed_fields") or {
                "name": (meta or {}).get("name"),
                "content_type": (meta or {}).get("contentType"),
                "size": len(content),
                "sha256": digest,
                "message_id": message_id,
            },
            evidence=[{"kind": "attachment", "id": attachment_id,
                       "sha256": digest, "message_id": message_id}]),
    }


# ---------------------------------------------------------------------------
# Business-independent action names.
#
# The implementations above are provider capabilities, not Brennan policy.
# A deployment (industrial sales, services, procurement, non-sales) selects
# these generic names through its plan/config; the ``brennan.*`` names remain
# as aliases for plans created during the reference campaign.
# ---------------------------------------------------------------------------
_GENERIC_ALIASES = {
    "connected.workdrive.list_page": "brennan.workdrive.list_page",
    "connected.workdrive.read_file": "brennan.workdrive.read_file",
    "connected.workdrive.sync_page": "brennan.workdrive.sync_page",
    "connected.onedrive.list_page": "brennan.onedrive.list_page",
    "connected.onedrive.read_file": "brennan.onedrive.read_file",
    "connected.onedrive.sync_page": "brennan.onedrive.sync_page",
    "connected.knowledge.sync_status": "brennan.knowledge.sync_status",
    "connected.crm.get_record": "brennan.crm.get_record",
    "connected.crm.search_records": "brennan.crm.search_records",
    "connected.inventory.check_stock": "brennan.inventory.check_stock",
    "connected.inventory.get_item": "brennan.inventory.get_item",
    "connected.books.get_bill": "brennan.books.get_bill",
    "connected.books.get_estimate": "brennan.books.get_estimate",
    "connected.books.resolve_vendor": "brennan.books.resolve_vendor",
    "connected.books.list_accounts": "brennan.books.list_accounts",
    "connected.books.propose_bill": "brennan.books.propose_bill",
    "connected.books.create_bill": "brennan.books.create_bill",
    "connected.books.create_estimate": "brennan.books.create_estimate",
    "connected.outlook.create_draft": "brennan.outlook.create_draft",
    "connected.outlook.read_attachments": "brennan.outlook.read_attachments",
}

for _generic, _legacy in _GENERIC_ALIASES.items():
    _action = action_registry.get_action(_legacy)
    if _action is not None:
        action_registry.register(
            _generic, _action.handler, _action.description,
            _action.parameters_schema, _action.preconditions, _action.effects)
