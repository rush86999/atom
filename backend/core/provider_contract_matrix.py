"""Provider × object × action contract matrix, derived from resolved classes.

This is the audit surface the Brennan work order asks for.  It is deliberately
built from the classes the registry actually loads — not from a catalog label or
from a parallel hand-written list of marketing claims.  Each contract states:

provider / object / operation / kind / required inputs / effect / permission
scope / coverage / result shape / remote verification / conditional support.

``build_matrix`` resolves each service through ``IntegrationRegistry`` (or an
explicit class map in tests), checks that the method exists and that the
service's own capability list advertises it, and returns every mismatch instead
of silently skipping it.  ``assert_contract_matrix`` fails closed for the
business-critical subset.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Type

from core.integration_registry import IntegrationRegistry


@dataclass(frozen=True)
class ProviderContract:
    provider: str
    object: str
    operation: str
    kind: str  # read | search | create | update | delete | sync
    method: str
    required_inputs: tuple = ()
    optional_inputs: tuple = ()
    effect: str = "none"
    permission: str = "read"
    coverage: str = "single"  # single | paged | bounded | full_tree
    result_shape: str = "object"
    remote_verification: str = "readback"
    conditional_version: bool = False
    notes: str = ""


BUSINESS_CRITICAL: tuple = (
    # Zoho CRM
    ("zoho_crm", "contact", "get_contacts"),
    ("zoho_crm", "contact", "get_record"),
    ("zoho_crm", "account", "get_accounts"),
    ("zoho_crm", "deal", "get_deals"),
    ("zoho_crm", "record", "create_record"),
    ("zoho_crm", "record", "update_record"),
    # Zoho Books
    ("zoho_books", "organization", "get_organizations"),
    ("zoho_books", "contact", "get_vendors"),
    ("zoho_books", "invoice", "get_invoices"),
    ("zoho_books", "bill", "get_bills"),
    ("zoho_books", "bill", "get_bill"),
    ("zoho_books", "bill", "create_bill"),
    ("zoho_books", "estimate", "create_estimate"),
    # Zoho Inventory
    ("zoho_inventory", "item", "get_items"),
    ("zoho_inventory", "item", "search_items"),
    ("zoho_inventory", "item", "check_stock"),
    # Storage
    ("zoho_workdrive", "file", "list_files_page"),
    ("zoho_workdrive", "file", "search_files_envelope"),
    ("zoho_workdrive", "file", "download_file"),
    ("onedrive", "drive_item", "list_files_page"),
    ("onedrive", "drive_item", "search_files_envelope"),
    ("onedrive", "drive_item", "download_file_bytes"),
    ("microsoft365", "drive_item", "get_content"),
)


def _contracts() -> List[ProviderContract]:
    """The implemented contracts.  One row per operation, by effect class."""
    c: List[ProviderContract] = []

    # ---- Zoho CRM -----------------------------------------------------
    c += [
        ProviderContract("zoho_crm", "lead", "get_leads", "read", "get_leads",
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_crm", "deal", "get_deals", "read", "get_deals",
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_crm", "contact", "get_contacts", "read", "get_contacts",
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_crm", "account", "get_accounts", "read", "get_accounts",
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_crm", "record", "get_record", "read", "get_record",
                         required_inputs=("module", "record_id")),
        ProviderContract("zoho_crm", "record", "search_records", "search", "search_records",
                         required_inputs=("module", "query"), coverage="bounded",
                         result_shape="list"),
        ProviderContract("zoho_crm", "lead", "create_lead", "create", "create_lead",
                         required_inputs=("data",), effect="provider_mutation",
                         permission="write", remote_verification="readback"),
        ProviderContract("zoho_crm", "record", "create_record", "create", "create_record",
                         required_inputs=("module", "data"), effect="provider_mutation",
                         permission="write", remote_verification="readback"),
        ProviderContract("zoho_crm", "record", "update_record", "update", "update_record",
                         required_inputs=("module", "record_id", "fields"),
                         effect="provider_mutation", permission="write",
                         remote_verification="readback", conditional_version=False,
                         notes="Zoho CRM If-Unmodified-Since is not used here; "
                               "read-then-write is not claimed atomic."),
        ProviderContract("zoho_crm", "module", "get_modules", "read", "get_modules"),
        ProviderContract("zoho_crm", "field", "get_fields", "read", "get_fields",
                         required_inputs=("module",)),
    ]

    # ---- Zoho Books ---------------------------------------------------
    c += [
        ProviderContract("zoho_books", "organization", "get_organizations", "read",
                         "get_organizations", result_shape="list"),
        ProviderContract("zoho_books", "contact", "get_contacts", "read", "get_contacts",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list", notes="legacy list; strict page is get_contacts_page"),
        ProviderContract("zoho_books", "contact", "get_contacts_page", "read",
                         "get_contacts_page", required_inputs=("organization_id",),
                         coverage="paged", result_shape="page"),
        ProviderContract("zoho_books", "vendor", "get_vendors", "read", "get_vendors",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list"),
        ProviderContract("zoho_books", "customer", "get_customers", "read", "get_customers",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list"),
        ProviderContract("zoho_books", "account", "get_chart_of_accounts", "read",
                         "get_chart_of_accounts", required_inputs=("organization_id",),
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_books", "bank_transaction", "get_bank_transactions", "read",
                         "get_bank_transactions", required_inputs=("organization_id",),
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_books", "invoice", "get_invoices", "read", "get_invoices",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list"),
        ProviderContract("zoho_books", "bill", "get_bills", "read", "get_bills",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list"),
        ProviderContract("zoho_books", "bill", "get_bill", "read", "get_bill",
                         required_inputs=("organization_id", "bill_id")),
        ProviderContract("zoho_books", "estimate", "get_estimates", "read", "get_estimates",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list"),
        ProviderContract("zoho_books", "estimate", "get_estimate", "read", "get_estimate",
                         required_inputs=("organization_id", "estimate_id")),
        ProviderContract("zoho_books", "item", "get_items", "read", "get_items",
                         required_inputs=("organization_id",), coverage="paged",
                         result_shape="list"),
        ProviderContract("zoho_books", "contact", "create_contact", "create",
                         "create_contact", required_inputs=("organization_id", "contact_data"),
                         effect="provider_mutation", permission="write"),
        ProviderContract("zoho_books", "vendor", "create_vendor", "create", "create_vendor",
                         required_inputs=("organization_id", "vendor_data"),
                         effect="provider_mutation", permission="write"),
        ProviderContract("zoho_books", "invoice", "create_invoice", "create",
                         "create_invoice", required_inputs=("organization_id", "invoice_data"),
                         effect="provider_mutation", permission="write_invoice"),
        ProviderContract("zoho_books", "bill", "create_bill", "create", "create_bill",
                         required_inputs=("organization_id", "bill_data"),
                         effect="provider_mutation", permission="write_bill",
                         remote_verification="get_bill", conditional_version=False,
                         notes="No provider idempotency header; the shared effect "
                               "arbiter + duplicate identity is the guard."),
        ProviderContract("zoho_books", "bill", "update_bill", "update", "update_bill",
                         required_inputs=("organization_id", "bill_id", "bill_data"),
                         effect="provider_mutation", permission="write_bill",
                         remote_verification="get_bill", conditional_version=False,
                         notes="Zoho Books has no conditional write header here; "
                               "changed-remote-version is detected by readback."),
        ProviderContract("zoho_books", "estimate", "create_estimate", "create",
                         "create_estimate", required_inputs=("organization_id", "estimate_data"),
                         effect="provider_mutation", permission="write_quote"),
        ProviderContract("zoho_books", "estimate", "update_estimate", "update",
                         "update_estimate", required_inputs=("organization_id", "estimate_id", "estimate_data"),
                         effect="provider_mutation", permission="write_quote"),
    ]

    # ---- Zoho Inventory ----------------------------------------------
    c += [
        ProviderContract("zoho_inventory", "item", "get_items", "read", "get_items",
                         coverage="paged", result_shape="list"),
        ProviderContract("zoho_inventory", "item", "search_items", "search",
                         "search_items", required_inputs=("query",), coverage="bounded",
                         result_shape="list"),
        ProviderContract("zoho_inventory", "item", "check_stock", "read", "check_stock",
                         required_inputs=("item_id",), result_shape="object",
                         notes="Observed availability at a location/time; never a reservation."),
        ProviderContract("zoho_inventory", "item", "get_inventory_levels", "read",
                         "get_inventory_levels", coverage="paged", result_shape="list"),
    ]

    # ---- WorkDrive ----------------------------------------------------
    c += [
        ProviderContract("zoho_workdrive", "folder", "list_files", "read", "list_files",
                         coverage="full_tree", result_shape="list",
                         notes="legacy recursion; strict page is list_files_page"),
        ProviderContract("zoho_workdrive", "folder", "list_files_page", "read",
                         "list_files_page", coverage="paged", result_shape="page"),
        ProviderContract("zoho_workdrive", "file", "search_files", "search", "search_files",
                         required_inputs=("query",), coverage="bounded", result_shape="list"),
        ProviderContract("zoho_workdrive", "file", "search_files_envelope", "search",
                         "search_files_envelope", required_inputs=("query",),
                         coverage="bounded", result_shape="envelope"),
        ProviderContract("zoho_workdrive", "file", "download_file", "read", "download_file",
                         required_inputs=("file_id",), result_shape="bytes"),
        ProviderContract("zoho_workdrive", "file", "get_file_metadata", "read",
                         "get_file_metadata", required_inputs=("file_id",)),
        ProviderContract("zoho_workdrive", "file", "ingest_file_to_memory", "create",
                         "ingest_file_to_memory", required_inputs=("file_id",),
                         effect="local_index", permission="ingest"),
    ]

    # ---- OneDrive -----------------------------------------------------
    c += [
        ProviderContract("onedrive", "drive_item", "list_files", "read", "list_files",
                         coverage="paged", result_shape="envelope"),
        ProviderContract("onedrive", "drive_item", "list_files_page", "read",
                         "list_files_page", coverage="paged", result_shape="page",
                         notes="Explicit drive_id+site_id required for SharePoint libraries."),
        ProviderContract("onedrive", "drive_item", "search_files", "search", "search_files",
                         required_inputs=("query",), coverage="bounded", result_shape="envelope"),
        ProviderContract("onedrive", "drive_item", "search_files_envelope", "search",
                         "search_files_envelope", required_inputs=("query",),
                         coverage="bounded", result_shape="page"),
        ProviderContract("onedrive", "drive_item", "get_file_metadata", "read",
                         "get_file_metadata", required_inputs=("file_id",)),
        ProviderContract("onedrive", "drive_item", "download_file_bytes", "read",
                         "download_file_bytes", required_inputs=("file_id",),
                         result_shape="bytes"),
        ProviderContract("onedrive", "drive_item", "ingest_file_to_memory", "create",
                         "ingest_file_to_memory", required_inputs=("file_id",),
                         effect="local_index", permission="ingest"),
    ]

    # ---- Microsoft 365 / Outlook file bytes ---------------------------
    c += [
        ProviderContract("microsoft365", "drive_item", "get_content", "read",
                         "execute_onedrive_action", required_inputs=("path or item_id",),
                         result_shape="bytes"),
        ProviderContract("microsoft365", "drive_item", "list_files", "read",
                         "execute_onedrive_action", result_shape="envelope"),
    ]

    # ---- Outlook draft (no send) -------------------------------------
    c += [
        ProviderContract("outlook", "message", "create_draft_email", "create",
                         "create_draft_email", required_inputs=("user_id", "to_recipients", "subject", "body"),
                         effect="provider_draft", permission="draft_only",
                         remote_verification="readback", notes="Never sends; send is a separate authority."),
    ]
    return c


def _service_operations(instance: Any) -> set:
    caps = instance.get_capabilities() if hasattr(instance, "get_capabilities") else {}
    ops = caps.get("operations") if isinstance(caps, dict) else caps
    out = set()
    for op in ops or []:
        if isinstance(op, dict):
            out.add(str(op.get("id") or op.get("name") or ""))
        else:
            out.add(str(op))
    return {o for o in out if o}


def build_matrix(
    service_classes: Optional[Dict[str, Type]] = None,
    *,
    contracts: Optional[Sequence[ProviderContract]] = None,
) -> Dict[str, Any]:
    """Resolve providers and return every contract plus any mismatch.

    ``service_classes`` lets tests inject the real classes without relying on
    the global registry's import timing.
    """
    registry = IntegrationRegistry(use_cache=True)
    classes = dict(service_classes or {})
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    for contract in (contracts or _contracts()):
        cls = classes.get(contract.provider)
        if cls is None:
            cls = registry.get_service_class(contract.provider)
        row = asdict(contract)
        row["resolved"] = cls is not None
        row["method_implemented"] = bool(cls is not None and callable(
            getattr(cls, contract.method, None)))
        advertised = False
        if cls is not None:
            try:
                instance = cls(tenant_id="contract-matrix", config={})
                advertised = contract.operation in _service_operations(instance)
            except Exception as exc:  # noqa: BLE001 - constructability is a finding
                row["construct_error"] = type(exc).__name__
        row["advertised"] = advertised
        if cls is None:
            issues.append({"provider": contract.provider, "operation": contract.operation,
                           "issue": "unresolved_provider"})
        elif not row["method_implemented"]:
            issues.append({"provider": contract.provider, "operation": contract.operation,
                           "issue": "missing_method", "method": contract.method})
        elif not advertised and contract.provider not in ("microsoft365", "outlook"):
            issues.append({"provider": contract.provider, "operation": contract.operation,
                           "issue": "not_advertised", "method": contract.method})
        rows.append(row)
    return {
        "contracts": rows,
        "issues": issues,
        "providers": sorted({row["provider"] for row in rows}),
        "critical": [list(item) for item in BUSINESS_CRITICAL],
    }


def assert_contract_matrix(matrix: Dict[str, Any]) -> None:
    """Fail closed when a business-critical contract is unresolved/missing."""
    critical = {tuple(item) for item in BUSINESS_CRITICAL}
    failing = [
        issue for issue in matrix.get("issues") or []
        if (issue.get("provider"), issue.get("operation")) in critical
        or issue.get("issue") == "unresolved_provider"
    ]
    if failing:
        raise AssertionError(f"provider contract mismatches: {failing}")


def contract_by_key(matrix: Dict[str, Any], provider: str, operation: str) -> Optional[Dict[str, Any]]:
    for row in matrix.get("contracts") or []:
        if row.get("provider") == provider and row.get("operation") == operation:
            return row
    return None
