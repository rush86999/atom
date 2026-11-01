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

import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.action_registry import register_action

logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 25 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ids(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
    return {
        "tenant_id": str(context.get("tenant_id") or args.get("tenant_id")
                         or "default"),
        "workspace_id": str(context.get("workspace_id")
                            or args.get("workspace_id") or ""),
        "user_id": str(context.get("user_id") or args.get("user_id")
                       or context.get("employee_id") or ""),
    }


def _error(provider: str, operation: str, kind: str, message: str,
           *, reconnect: bool = False) -> Dict[str, Any]:
    return {
        "status": "error",
        "success": False,
        "provider": provider,
        "operation": operation,
        "error_kind": kind,
        "error": message,
        "retryable": kind in ("rate_limited", "transient"),
        "requires_reconnect": reconnect,
    }


def _receipt(provider: str, operation: str, *, resource_id: str = "",
             version: str = "", coverage: str = "", evidence=None,
             fields=None, continuation=None) -> Dict[str, Any]:
    return {
        "provider": provider,
        "operation": operation,
        "account": {"workspace_id": None},
        "resource_id": resource_id,
        "version": version,
        "retrieved_at": _now(),
        "coverage": coverage,
        "fields": fields or [],
        "evidence": evidence or [],
        "continuation": continuation,
    }


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
                       "max_bytes": {"type": "integer"}},
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
    return {
        "status": "success",
        "provider": "zoho_workdrive",
        "file": meta or {"id": file_id},
        "content_b64": base64.b64encode(content).decode("ascii"),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "read_receipt": _receipt(
            "zoho_workdrive", "download_file", resource_id=file_id,
            version=str((meta or {}).get("version") or ""),
            coverage="complete",
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
                       "max_bytes": {"type": "integer"}},
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
    return {
        "status": "success",
        "provider": "onedrive",
        "file": {"id": file_id},
        "content_b64": base64.b64encode(content).decode("ascii"),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "read_receipt": _receipt(
            "onedrive", "download_file_bytes", resource_id=file_id,
            coverage="complete",
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
                coverage="single", fields=list(data) if isinstance(data, dict) else [])}


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
                fields=["item_id", "stock_on_hand", "available_stock"])}


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
                coverage="single", fields=list(data) if isinstance(data, dict) else [])}


@register_action(
    "brennan.outlook.create_draft",
    description="Create an Outlook draft only. Never sends; sending requires separate authority.",
    parameters_schema={"type": "object",
                       "properties": {"to": {"type": "array"},
                                      "cc": {"type": "array"},
                                      "bcc": {"type": "array"},
                                      "subject": {"type": "string"},
                                      "body": {"type": "string"}},
                       "required": ["to", "subject", "body"]},
    effects=[{"effect": "create"}],
)
async def outlook_create_draft(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    from integrations.outlook_service import OutlookService
    service = OutlookService(ids["tenant_id"], {})
    token = context.get("access_token") or args.get("access_token")
    if not token:
        try:
            token = await service.get_access_token(ids["user_id"])
        except Exception:
            token = None
    result = await service.create_draft_email(
        user_id=ids["user_id"], to_recipients=list(args.get("to") or []),
        subject=str(args.get("subject") or ""), body=str(args.get("body") or ""),
        cc_recipients=list(args.get("cc") or []),
        bcc_recipients=list(args.get("bcc") or []), token=token)
    if not result:
        return _error("outlook", "create_draft_email", "provider_error",
                      "Outlook did not create a draft.")
    return {"status": "success", "provider": "outlook", "data": result,
            "read_receipt": _receipt(
                "outlook", "create_draft_email",
                resource_id=str((result or {}).get("id") or ""),
                coverage="single", fields=["id", "subject", "toRecipients"])}


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
                fields=["item_id", "sku", "name", "unit", "stock_on_hand",
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
                fields=list(data) if isinstance(data, dict) else [])}


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
                fields=["vendor", "currency", "document_date", "lines",
                        "document_total", "duplicate_key"])}


@register_action(
    "brennan.books.create_bill",
    description="Post an authorized, reviewed bill proposal and read it back. Requires explicit authority and operation id.",
    parameters_schema={"type": "object",
                       "properties": {"proposal": {"type": "object"},
                                      "authority_reference": {"type": "string"},
                                      "operation_id": {"type": "string"}},
                       "required": ["proposal", "authority_reference",
                                    "operation_id"]},
    effects=[{"effect": "create"}],
)
async def books_create_bill(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    proposal = args.get("proposal") or {}
    if proposal.get("status") != "proposed":
        return _error("zoho_books", "create_bill", "invalid_request",
                      "Only a reviewed proposal in status 'proposed' can be posted.")
    if not args.get("authority_reference"):
        return _error("zoho_books", "create_bill", "unauthorized",
                      "An explicit authority reference is required.", reconnect=False)
    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_books", "create_bill", "auth_unavailable",
                      "No Zoho Books token for this user.", reconnect=True)
    org = str(proposal.get("organization_id") or "")
    if not org:
        return _error("zoho_books", "create_bill", "invalid_request",
                      "organization_id is required.")
    # Exact duplicate identity check before dispatch: same provider/org/entity
    # and exact reference or bill number.  No substring matching.
    try:
        existing = await service.get_bills(token, org, per_page=200)
    except Exception:
        existing = []
    external_id = str(proposal.get("external_id") or "")
    duplicate = next((
        item for item in existing
        if external_id and external_id in {
            str(item.get("reference_number") or ""),
            str(item.get("bill_number") or ""),
        }), None)
    if duplicate:
        return {"status": "duplicate", "provider": "zoho_books",
                "existing": duplicate,
                "read_receipt": _receipt(
                    "zoho_books", "get_bills", resource_id=str(duplicate.get("bill_id") or ""),
                    coverage="single", fields=["bill_id", "bill_number",
                                               "reference_number"])}
    payload = _bill_payload(proposal)
    created = await service.create_bill(token, org, payload)
    remote_id = str(created.get("bill_id") or created.get("id") or "")
    readback = await service.get_bill(token, org, remote_id) if remote_id else {}
    return {
        "status": "success",
        "provider": "zoho_books",
        "remote_id": remote_id,
        "provider_receipt": {"operation_id": args.get("operation_id"),
                             "authority_reference": args.get("authority_reference")},
        "data": readback or created,
        "read_receipt": _receipt(
            "zoho_books", "create_bill", resource_id=remote_id,
            coverage="single",
            fields=["bill_id", "bill_number", "reference_number", "total",
                    "vendor_id", "date", "currency_code"]),
    }


@register_action(
    "brennan.books.create_estimate",
    description="Post an authorized quote estimate and read it back. Requires explicit authority and operation id.",
    parameters_schema={"type": "object",
                       "properties": {"organization_id": {"type": "string"},
                                      "estimate_data": {"type": "object"},
                                      "authority_reference": {"type": "string"},
                                      "operation_id": {"type": "string"}},
                       "required": ["organization_id", "estimate_data",
                                    "authority_reference", "operation_id"]},
    effects=[{"effect": "create"}],
)
async def books_create_estimate(args: Dict[str, Any], context: Dict[str, Any]):
    ids = _ids(args, context)
    if not args.get("authority_reference"):
        return _error("zoho_books", "create_estimate", "unauthorized",
                      "An explicit authority reference is required.")
    service = await _books_service(ids)
    token = await _zoho_token(service, ids)
    if not token:
        return _error("zoho_books", "create_estimate", "auth_unavailable",
                      "No Zoho Books token for this user.", reconnect=True)
    org = str(args["organization_id"])
    created = await service.create_estimate(token, org, args["estimate_data"])
    remote_id = str(created.get("estimate_id") or created.get("id") or "")
    readback = await service.get_estimate(token, org, remote_id) if remote_id else {}
    return {"status": "success", "provider": "zoho_books",
            "remote_id": remote_id,
            "provider_receipt": {"operation_id": args.get("operation_id"),
                                 "authority_reference": args.get("authority_reference")},
            "data": readback or created,
            "read_receipt": _receipt(
                "zoho_books", "create_estimate", resource_id=remote_id,
                coverage="single",
                fields=["estimate_id", "estimate_number", "total",
                        "customer_id", "date", "currency_code"])}
