"""Thin integration router for stripe.

Auto-generated to expose the existing StripeAdapter service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
stripe_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.connection_service import connection_service
from core.database import get_db
from core.integrations.adapters.stripe import StripeAdapter
from accounting.invoice_provider_binding import (
    InvoiceProviderBindingConflict,
    InvoiceProviderBindingInvoiceNotFound,
    bind_invoice_to_provider,
)
from accounting.models import (
    Invoice,
    InvoiceProviderBinding,
    InvoiceProviderBindingRevision,
)
from core.models import Tenant, User, UserRole, Workspace
from core.security.rbac import user_meets_role


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/stripe", tags=["stripe"])

_STRIPE_ACCOUNT_URL = "https://api.stripe.com/v1/account"
_STRIPE_TIMEOUT_SECONDS = 10.0
_STRIPE_INTEGRATION_ID = "stripe"
_RESTRICTED_KEY_RE = re.compile(r"rk_(test|live)_[A-Za-z0-9_]+")
_STRIPE_ACCOUNT_ID_RE = re.compile(r"acct_[A-Za-z0-9]+")

# Currencies Stripe accepts today.  Unknown three-letter codes are refused
# before any provider request so a bad durable value can never broaden intent.
_SUPPORTED_CURRENCIES = frozenset(
    """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND
    BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU
    CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS
    GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR ISK JMD JOD
    JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL
    MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR
    NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG
    SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY
    TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XCD
    XOF XPF YER ZAR ZMW ZWL
    """.lower().split()
)

# Stripe documents these as zero-decimal: the API amount is the whole unit.
_ZERO_DECIMAL_CURRENCIES = frozenset(
    "bif clp djf gnf jpy kmf krw mga pyg rwf ugx vnd vuv xaf xof xpf".split()
)

# ISK and UGX are zero-decimal currencies, but Stripe represents their API
# amount in hundredths (for example, 1 ISK is sent as 100).
_SPECIAL_TWO_DECIMAL_CURRENCIES = frozenset({"isk", "ugx"})

# Stripe only supports two decimal places for these currencies, even though
# their smallest unit is 1/1000 (amount must be a multiple of ten).
_THREE_DECIMAL_CURRENCIES = frozenset({"bhd", "jod", "kwd", "omr", "tnd"})

_PREVIEW_FACT_FIELDS = (
    "account_id",
    "invoice_id",
    "currency",
    "total_minor_units",
    "livemode",
    "invoice_number",
)

_CREDENTIAL_BODY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "credentials",
        "restricted_key",
        "secret_key",
        "token",
    }
)


@dataclass(frozen=True)
class _WorkspaceScope:
    user_id: str
    tenant_id: str
    workspace_id: str


@dataclass(frozen=True)
class _SetupInput:
    restricted_key: str
    account_id: str
    mode: str


@dataclass(frozen=True)
class _InvoiceLinkInput:
    local_invoice_id: str
    connection_id: str
    external_invoice_id: str
    expected_revision: Optional[int] = None
    reason: Optional[str] = None
    expected_preview: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class _InvoiceLinkSnapshot:
    user_id: str
    tenant_id: str
    workspace_id: str
    local_invoice_id: str
    connection_id: str
    account_id: str
    mode: str
    livemode: bool
    currency: str
    total_minor_units: int
    external_invoice_id: str
    restricted_key: str = field(repr=False)


@dataclass(frozen=True)
class _PaymentEvidenceSnapshot:
    """Binding-scoped snapshot used to prove no authority or credential drift."""

    link: _InvoiceLinkSnapshot
    binding_id: str
    binding_revision: int


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _current_user_id(current_user: Any) -> str:
    """Read the actor only from the authenticated principal, never from input."""
    if isinstance(current_user, dict):
        raw_id = current_user.get("id")
    else:
        raw_id = getattr(current_user, "id", None)
    if not _nonempty_str(raw_id):
        raise HTTPException(status_code=401, detail="Authentication required")
    return raw_id.strip()


def _resolve_active_workspace_admin_scope(
    db: Session, user_id: str
) -> _WorkspaceScope:
    """Resolve the actor's current active tenant/workspace admin scope from DB rows."""
    user = db.query(User).filter(User.id == user_id).first()
    if (
        user is None
        or not bool(getattr(user, "is_active", False))
        or getattr(user, "status", None) != "active"
        or not user_meets_role(user, UserRole.WORKSPACE_ADMIN)
    ):
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    tenant_id = getattr(user, "tenant_id", None)
    workspace_id = getattr(user, "workspace_id", None)
    if not _nonempty_str(tenant_id) or not _nonempty_str(workspace_id):
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )
    tenant_id = tenant_id.strip()
    workspace_id = workspace_id.strip()

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None or not bool(getattr(tenant, "is_active", False)):
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.tenant_id == tenant_id,
    ).first()
    if workspace is None or getattr(workspace, "status", None) != "active":
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    return _WorkspaceScope(
        user_id=user_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )


async def _parse_setup_input(request: Request) -> _SetupInput:
    """Validate manually so rejected secrets never reach validation error bodies."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid request")

    raw_key = payload.get("restricted_key")
    raw_account_id = payload.get("account_id")
    if not isinstance(raw_key, str) or not isinstance(raw_account_id, str):
        raise HTTPException(status_code=400, detail="Invalid request")

    restricted_key = raw_key.strip()
    account_id = raw_account_id.strip()
    if not _RESTRICTED_KEY_RE.fullmatch(restricted_key):
        raise HTTPException(status_code=400, detail="Invalid request")
    if not _STRIPE_ACCOUNT_ID_RE.fullmatch(account_id):
        raise HTTPException(status_code=400, detail="Invalid request")

    # The mode is pinned solely by the restricted-key prefix. No provider
    # permissions or write scope are inferred from the key.
    mode = "test" if restricted_key.startswith("rk_test_") else "live"
    return _SetupInput(
        restricted_key=restricted_key,
        account_id=account_id,
        mode=mode,
    )


async def _fetch_stripe_account(restricted_key: str) -> Dict[str, Any]:
    """Perform exactly one fixed Stripe GET; never follow redirects."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=_STRIPE_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                _STRIPE_ACCOUNT_URL,
                headers={"Authorization": f"Bearer {restricted_key}"},
            )
    except Exception as exc:
        logger.warning(
            "Stripe account verification request failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )

    if response.status_code != 200:
        logger.warning(
            "Stripe account verification failed with status %s",
            response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )

    try:
        data = response.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )
    return data


@router.post("/invoice-connection")
async def create_invoice_connection(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a scoped Stripe connection from a verified account restricted key."""
    actor_id = _current_user_id(current_user)

    # Resolve the scope before provider I/O, then prove it is still the same
    # active scope afterwards. None of these values come from the request body.
    initial_scope = _resolve_active_workspace_admin_scope(db, actor_id)
    setup = await _parse_setup_input(request)

    account = await _fetch_stripe_account(setup.restricted_key)
    returned_account_id = account.get("id")
    if returned_account_id != setup.account_id:
        raise HTTPException(
            status_code=400,
            detail="Stripe account verification failed",
        )

    # Force a fresh read so a role/tenant/workspace change committed while the
    # provider request was in flight cannot be hidden by the identity map.
    try:
        db.expire_all()
    except Exception as exc:
        logger.warning(
            "Stripe scope revalidation freshness check failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to verify workspace admin authorization",
        )
    rechecked_scope = _resolve_active_workspace_admin_scope(db, actor_id)
    if rechecked_scope != initial_scope:
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    connection_id = str(uuid.uuid4())
    credentials = {
        "restricted_key": setup.restricted_key,
        "account_id": setup.account_id,
        "mode": setup.mode,
        "auth_type": "restricted_key",
    }

    try:
        created = connection_service.create_scoped_connection(
            user_id=initial_scope.user_id,
            tenant_id=initial_scope.tenant_id,
            workspace_id=initial_scope.workspace_id,
            integration_id=_STRIPE_INTEGRATION_ID,
            name=f"Stripe invoice connection ({setup.account_id})",
            credentials=credentials,
            connection_id=connection_id,
        )
    except Exception as exc:
        logger.warning(
            "Stripe scoped connection persistence failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to store Stripe connection",
        )

    if not created:
        raise HTTPException(
            status_code=409,
            detail="Unable to store Stripe connection",
        )

    return {
        "connection_id": connection_id,
        "account": setup.account_id,
        "mode": setup.mode,
    }


def _get_service(db: Session = None) -> StripeAdapter:
    """Build a StripeAdapter instance."""
    return StripeAdapter(db, workspace_id="default")


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the stripe integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "stripe service available (no health_check method)"}
    except Exception as exc:
        logger.warning("stripe health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this stripe service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


def _required_body_text(payload: Dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="Invalid request")
    value = value.strip()
    if not value or len(value) > 255:
        raise HTTPException(status_code=400, detail="Invalid request")
    return value


def _normalize_currency(value: Any) -> str:
    if not isinstance(value, str):
        raise HTTPException(
            status_code=400,
            detail="Invoice currency is not supported",
        )
    currency = value.strip().lower()
    if (
        not re.fullmatch(r"[a-z]{3}", currency)
        or currency not in _SUPPORTED_CURRENCIES
    ):
        raise HTTPException(
            status_code=400,
            detail="Invoice currency is not supported",
        )
    return currency


def _currency_exponent(currency: str) -> int:
    if currency in _SPECIAL_TWO_DECIMAL_CURRENCIES:
        return 2
    if currency in _ZERO_DECIMAL_CURRENCIES:
        return 0
    if currency in _THREE_DECIMAL_CURRENCIES:
        return 3
    return 2


def _to_integer_minor_units(currency: str, amount: Any) -> int:
    """Convert a durable Decimal amount exactly, refusing fractional input."""
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
        raise HTTPException(status_code=400, detail="Invoice amount is not supported")

    exponent = _currency_exponent(currency)
    scaled = amount * (Decimal(10) ** exponent)
    if not scaled.is_finite():
        raise HTTPException(status_code=400, detail="Invoice amount is not supported")

    integral = scaled.to_integral_value()
    if scaled != integral:
        raise HTTPException(
            status_code=400,
            detail="Invoice amount cannot be represented exactly",
        )

    minor_units = int(integral)
    if exponent == 3 and minor_units % 10 != 0:
        raise HTTPException(
            status_code=400,
            detail="Invoice amount cannot be represented exactly",
        )
    return minor_units


def _parse_expected_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Require the exact six canonical preview facts echoed for confirmation."""
    facts = payload.get("expected_preview")
    if not isinstance(facts, dict) or set(facts) != set(_PREVIEW_FACT_FIELDS):
        raise HTTPException(status_code=400, detail="Invalid request")

    account_id = facts.get("account_id")
    invoice_id = facts.get("invoice_id")
    if not _nonempty_str(account_id) or not _nonempty_str(invoice_id):
        raise HTTPException(status_code=400, detail="Invalid request")

    total_minor_units = facts.get("total_minor_units")
    if (
        isinstance(total_minor_units, bool)
        or not isinstance(total_minor_units, int)
        or total_minor_units < 0
    ):
        raise HTTPException(status_code=400, detail="Invalid request")

    livemode = facts.get("livemode")
    if not isinstance(livemode, bool):
        raise HTTPException(status_code=400, detail="Invalid request")

    invoice_number = facts.get("invoice_number")
    if invoice_number is not None and (
        not isinstance(invoice_number, str) or not invoice_number
    ):
        raise HTTPException(status_code=400, detail="Invalid request")

    return {
        "account_id": account_id,
        "invoice_id": invoice_id,
        "currency": _normalize_currency(facts.get("currency")),
        "total_minor_units": total_minor_units,
        "livemode": livemode,
        "invoice_number": invoice_number,
    }


async def _parse_invoice_link_input(
    request: Request,
    *,
    path_invoice_id: str,
    include_binding_fields: bool,
) -> _InvoiceLinkInput:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid request")

    # Credentials are read only from the scoped connection record.  Rejecting
    # these keys makes an accidental secret-bearing client call fail closed.
    if any(key in payload for key in _CREDENTIAL_BODY_KEYS):
        raise HTTPException(status_code=400, detail="Invalid request")

    connection_id = _required_body_text(payload, "connection_id")
    external_invoice_id = _required_body_text(payload, "external_invoice_id")

    expected_revision: Optional[int] = None
    reason: Optional[str] = None
    expected_preview: Optional[Dict[str, Any]] = None

    if include_binding_fields:
        raw_revision = payload.get("expected_revision")
        if raw_revision is not None:
            if (
                isinstance(raw_revision, bool)
                or not isinstance(raw_revision, int)
                or raw_revision < 0
            ):
                raise HTTPException(status_code=400, detail="Invalid request")
            expected_revision = raw_revision

        raw_reason = payload.get("reason")
        if raw_reason is not None:
            if not isinstance(raw_reason, str):
                raise HTTPException(status_code=400, detail="Invalid request")
            raw_reason = raw_reason.strip()
            if len(raw_reason) > 500:
                raise HTTPException(status_code=400, detail="Invalid request")
            reason = raw_reason or None

        expected_preview = _parse_expected_preview(payload)

    return _InvoiceLinkInput(
        local_invoice_id=path_invoice_id,
        connection_id=connection_id,
        external_invoice_id=external_invoice_id,
        expected_revision=expected_revision,
        reason=reason,
        expected_preview=expected_preview,
    )


def _resolve_invoice_link_snapshot(
    db: Session,
    actor_id: str,
    link_input: _InvoiceLinkInput,
) -> _InvoiceLinkSnapshot:
    """Read the invoice, connection, and expected facts from durable rows."""
    scope = _resolve_active_workspace_admin_scope(db, actor_id)

    if Invoice is None:
        raise HTTPException(
            status_code=503,
            detail="Invoice storage is unavailable",
        )

    invoice = db.query(Invoice).filter(
        Invoice.id == link_input.local_invoice_id,
        Invoice.workspace_id == scope.workspace_id,
    ).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    currency = _normalize_currency(getattr(invoice, "currency", None))
    total_minor_units = _to_integer_minor_units(
        currency,
        getattr(invoice, "amount", None),
    )

    try:
        credentials = connection_service.get_scoped_connection_credentials(
            user_id=scope.user_id,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            connection_id=link_input.connection_id,
            integration_id=_STRIPE_INTEGRATION_ID,
        )
    except Exception as exc:
        logger.warning(
            "Stripe scoped connection read failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to read Stripe connection",
        )

    if not isinstance(credentials, dict) or not credentials:
        raise HTTPException(status_code=404, detail="Stripe connection not found")

    restricted_key = credentials.get("restricted_key")
    account_id = credentials.get("account_id")
    mode = credentials.get("mode")
    if (
        not _nonempty_str(restricted_key)
        or not _nonempty_str(account_id)
        or mode not in ("test", "live")
    ):
        raise HTTPException(
            status_code=403,
            detail="Stripe connection is not usable",
        )

    restricted_key = restricted_key.strip()
    account_id = account_id.strip()
    if not _STRIPE_ACCOUNT_ID_RE.fullmatch(account_id):
        raise HTTPException(
            status_code=403,
            detail="Stripe connection is not usable",
        )

    return _InvoiceLinkSnapshot(
        user_id=scope.user_id,
        tenant_id=scope.tenant_id,
        workspace_id=scope.workspace_id,
        local_invoice_id=link_input.local_invoice_id,
        connection_id=link_input.connection_id,
        account_id=account_id,
        mode=mode,
        livemode=(mode == "live"),
        currency=currency,
        total_minor_units=total_minor_units,
        external_invoice_id=link_input.external_invoice_id,
        restricted_key=restricted_key,
    )


def _invoice_preview_adapter(
    db: Session,
    snapshot: _InvoiceLinkSnapshot,
) -> StripeAdapter:
    """Build the existing adapter and bind only the durable connection secret."""
    adapter = StripeAdapter(db, workspace_id=snapshot.workspace_id)
    setattr(adapter, "_access_token", snapshot.restricted_key)
    return adapter


def _safe_preview_facts(
    preview: Any,
    snapshot: _InvoiceLinkSnapshot,
) -> Dict[str, Any]:
    """Require the provider output to be exactly the six canonical facts."""
    if not isinstance(preview, dict) or set(preview) != set(_PREVIEW_FACT_FIELDS):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice preview does not match expected facts",
        )

    invoice_number = preview["invoice_number"]
    if (
        preview["account_id"] != snapshot.account_id
        or preview["invoice_id"] != snapshot.external_invoice_id
        or preview["currency"] != snapshot.currency
        or isinstance(preview["total_minor_units"], bool)
        or not isinstance(preview["total_minor_units"], int)
        or preview["total_minor_units"] != snapshot.total_minor_units
        or not isinstance(preview["livemode"], bool)
        or preview["livemode"] != snapshot.livemode
        or (
            invoice_number is not None
            and (not isinstance(invoice_number, str) or not invoice_number)
        )
    ):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice preview does not match expected facts",
        )

    return {
        "account_id": snapshot.account_id,
        "invoice_id": snapshot.external_invoice_id,
        "currency": snapshot.currency,
        "total_minor_units": snapshot.total_minor_units,
        "livemode": snapshot.livemode,
        "invoice_number": invoice_number,
    }


def _require_expected_match(
    expected: Optional[Dict[str, Any]],
    facts: Dict[str, Any],
) -> None:
    if expected != facts:
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice preview does not match expected facts",
        )


async def _fetch_invoice_identity_preview(
    db: Session,
    snapshot: _InvoiceLinkSnapshot,
) -> Dict[str, Any]:
    adapter = _invoice_preview_adapter(db, snapshot)

    try:
        preview = await adapter.get_invoice_identity_preview(
            expected_account_id=snapshot.account_id,
            invoice_id=snapshot.external_invoice_id,
            currency=snapshot.currency,
            expected_total_minor_units=snapshot.total_minor_units,
            expected_livemode=snapshot.livemode,
        )
    except ValueError as exc:
        logger.warning(
            "Stripe invoice identity preview rejected (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice preview does not match expected facts",
        )
    except Exception as exc:
        logger.warning(
            "Stripe invoice identity preview failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Stripe invoice preview failed",
        )

    return _safe_preview_facts(preview, snapshot)


def _resolve_payment_evidence_snapshot(
    db: Session,
    actor_id: str,
    invoice_id: str,
) -> _PaymentEvidenceSnapshot:
    """Resolve the persisted Stripe binding; provider identity never comes from input."""
    scope = _resolve_active_workspace_admin_scope(db, actor_id)

    if Invoice is None:
        raise HTTPException(
            status_code=503,
            detail="Invoice storage is unavailable",
        )

    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == scope.workspace_id,
    ).first()
    if invoice is None:
        # A foreign or unknown invoice id is indistinguishable from missing.
        raise HTTPException(status_code=404, detail="Invoice not found")

    binding = db.query(InvoiceProviderBinding).filter(
        InvoiceProviderBinding.workspace_id == scope.workspace_id,
        InvoiceProviderBinding.invoice_id == invoice.id,
        InvoiceProviderBinding.provider == "stripe",
    ).first()
    if binding is None:
        raise HTTPException(
            status_code=404,
            detail="Stripe invoice binding not found",
        )

    connection_id = getattr(binding, "connection_id", None)
    external_invoice_id = getattr(binding, "external_invoice_id", None)
    binding_account_id = getattr(binding, "provider_account_id", None)
    binding_mode = getattr(binding, "provider_mode", None)
    binding_revision = getattr(binding, "revision", None)
    if (
        not _nonempty_str(connection_id)
        or not _nonempty_str(external_invoice_id)
        or not _nonempty_str(binding_account_id)
        or binding_mode not in ("test", "live")
        or isinstance(binding_revision, bool)
        or not isinstance(binding_revision, int)
        or binding_revision < 1
    ):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice binding is not usable",
        )

    connection_id = connection_id.strip()
    external_invoice_id = external_invoice_id.strip()
    binding_account_id = binding_account_id.strip()

    # Reuse the durable snapshot resolver, but feed it only persisted binding
    # identifiers. The caller cannot supply an account, invoice, or connection.
    link_snapshot = _resolve_invoice_link_snapshot(
        db,
        actor_id,
        _InvoiceLinkInput(
            local_invoice_id=invoice.id,
            connection_id=connection_id,
            external_invoice_id=external_invoice_id,
        ),
    )

    if (
        link_snapshot.account_id != binding_account_id
        or link_snapshot.mode != binding_mode
        or link_snapshot.connection_id != connection_id
        or link_snapshot.external_invoice_id != external_invoice_id
        or link_snapshot.workspace_id != scope.workspace_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice binding is stale",
        )

    return _PaymentEvidenceSnapshot(
        link=link_snapshot,
        binding_id=binding.id,
        binding_revision=binding_revision,
    )


async def _fetch_payment_allocation_evidence(
    db: Session,
    snapshot: _PaymentEvidenceSnapshot,
) -> Dict[str, Any]:
    """Call the existing read-only adapter with the persisted binding facts."""
    adapter = _invoice_preview_adapter(db, snapshot.link)

    try:
        evidence = await adapter.get_invoice_payment_allocation_evidence(
            expected_account_id=snapshot.link.account_id,
            invoice_id=snapshot.link.external_invoice_id,
            currency=snapshot.link.currency,
            expected_amount_minor_units=snapshot.link.total_minor_units,
            expected_livemode=snapshot.link.livemode,
        )
    except ValueError as exc:
        logger.warning(
            "Stripe invoice payment allocation rejected (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice payment allocation is not verified",
        )
    except Exception as exc:
        logger.warning(
            "Stripe invoice payment allocation failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Stripe invoice payment evidence failed",
        )

    return evidence


def _safe_payment_allocation_evidence(
    evidence: Any,
    snapshot: _PaymentEvidenceSnapshot,
) -> Dict[str, Any]:
    """Return only verified allocation facts; never raw provider output."""
    link = snapshot.link
    if (
        not isinstance(evidence, dict)
        or evidence.get("evidence_type") != "stripe_invoice_payment_allocation"
    ):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice payment allocation is not verified",
        )

    payment_ids = evidence.get("invoice_payment_ids")
    if (
        not isinstance(payment_ids, list)
        or not payment_ids
        or any(not _nonempty_str(payment_id) for payment_id in payment_ids)
        or len(set(payment_ids)) != len(payment_ids)
    ):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice payment allocation is not verified",
        )

    payment_count = evidence.get("invoice_payment_count")
    amount_minor_units = evidence.get("amount_minor_units")
    paid_subtotal = evidence.get("paid_allocation_subtotal_minor_units")
    evidence_livemode = evidence.get("livemode")
    api_version = evidence.get("stripe_api_version")
    if (
        not isinstance(payment_count, int)
        or isinstance(payment_count, bool)
        or payment_count != len(payment_ids)
        or not isinstance(amount_minor_units, int)
        or isinstance(amount_minor_units, bool)
        or amount_minor_units != link.total_minor_units
        or not isinstance(paid_subtotal, int)
        or isinstance(paid_subtotal, bool)
        or paid_subtotal != link.total_minor_units
        or not isinstance(evidence_livemode, bool)
        or evidence_livemode != link.livemode
        or evidence.get("account_id") != link.account_id
        or evidence.get("invoice_id") != link.external_invoice_id
        or evidence.get("currency") != link.currency
        or not _nonempty_str(api_version)
    ):
        raise HTTPException(
            status_code=409,
            detail="Stripe invoice payment allocation is not verified",
        )

    return {
        "invoice_id": link.local_invoice_id,
        "provider": "stripe",
        "connection_id": link.connection_id,
        "account_id": link.account_id,
        "provider_account_id": link.account_id,
        "provider_mode": link.mode,
        "external_invoice_id": link.external_invoice_id,
        "provider_invoice_id": link.external_invoice_id,
        "currency": link.currency,
        "amount_minor_units": link.total_minor_units,
        "livemode": link.livemode,
        "binding_revision": snapshot.binding_revision,
        "evidence_type": "stripe_invoice_payment_allocation",
        "evidence_scope": "payment_allocation_only",
        "allocation_only": True,
        "invoice_payment_ids": list(payment_ids),
        "invoice_payment_count": len(payment_ids),
        "paid_allocation_subtotal_minor_units": link.total_minor_units,
        "stripe_api_version": api_version.strip(),
    }


def _binding_conflict_details(exc: Exception) -> Dict[str, Any]:
    details: Dict[str, Any] = {"error": "Invoice provider binding conflict"}
    expected_revision = getattr(exc, "expected_revision", None)
    current_revision = getattr(exc, "current_revision", None)
    binding_id = getattr(exc, "binding_id", None)
    if expected_revision is not None:
        details["expected_revision"] = expected_revision
    if current_revision is not None:
        details["current_revision"] = current_revision
    if binding_id is not None:
        details["binding_id"] = binding_id
    return details


@router.post("/invoice-links/{invoice_id}/preview")
async def preview_invoice_link(
    invoice_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the exact read-only Stripe identity facts for one invoice link."""
    actor_id = _current_user_id(current_user)
    if not _nonempty_str(invoice_id):
        raise HTTPException(status_code=400, detail="Invalid request")

    link_input = await _parse_invoice_link_input(
        request,
        path_invoice_id=invoice_id,
        include_binding_fields=False,
    )
    snapshot = _resolve_invoice_link_snapshot(db, actor_id, link_input)
    return await _fetch_invoice_identity_preview(db, snapshot)


@router.put("/invoice-links/{invoice_id}")
async def confirm_invoice_link(
    invoice_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Confirm a previewed link after rechecking all authority and snapshots."""
    actor_id = _current_user_id(current_user)
    if not _nonempty_str(invoice_id):
        raise HTTPException(status_code=400, detail="Invalid request")

    link_input = await _parse_invoice_link_input(
        request,
        path_invoice_id=invoice_id,
        include_binding_fields=True,
    )
    initial_snapshot = _resolve_invoice_link_snapshot(db, actor_id, link_input)
    preview_facts = await _fetch_invoice_identity_preview(db, initial_snapshot)
    _require_expected_match(link_input.expected_preview, preview_facts)

    # Re-read after the awaited provider call.  Expiring first prevents the
    # identity map from hiding a role, invoice, or connection change.
    try:
        db.expire_all()
    except Exception as exc:
        logger.warning(
            "Stripe invoice link revalidation freshness check failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to verify invoice link authorization",
        )

    rechecked_snapshot = _resolve_invoice_link_snapshot(db, actor_id, link_input)
    if rechecked_snapshot != initial_snapshot:
        raise HTTPException(
            status_code=409,
            detail="Invoice or Stripe connection changed during preview",
        )
    _safe_preview_facts(preview_facts, rechecked_snapshot)

    reason = link_input.reason or "Stripe invoice link confirmed after identity preview"

    try:
        binding = bind_invoice_to_provider(
            db,
            invoice_id=rechecked_snapshot.local_invoice_id,
            workspace_id=rechecked_snapshot.workspace_id,
            provider="stripe",
            provider_account_id=rechecked_snapshot.account_id,
            provider_mode=rechecked_snapshot.mode,
            external_invoice_id=rechecked_snapshot.external_invoice_id,
            connection_id=rechecked_snapshot.connection_id,
            actor_id=rechecked_snapshot.user_id,
            reason=reason,
            expected_revision=link_input.expected_revision,
        )
        revision = getattr(binding, "revision", None)
        db.commit()
    except InvoiceProviderBindingConflict as exc:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=409,
            detail=_binding_conflict_details(exc),
        )
    except InvoiceProviderBindingInvoiceNotFound:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="Invoice not found")
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "Stripe invoice link persistence failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to link Stripe invoice",
        )

    return {
        "invoice_id": rechecked_snapshot.local_invoice_id,
        "provider": "stripe",
        "connection_id": rechecked_snapshot.connection_id,
        "account_id": preview_facts["account_id"],
        "provider_account_id": preview_facts["account_id"],
        "provider_mode": rechecked_snapshot.mode,
        "external_invoice_id": preview_facts["invoice_id"],
        "provider_invoice_id": preview_facts["invoice_id"],
        "currency": preview_facts["currency"],
        "total_minor_units": preview_facts["total_minor_units"],
        "livemode": preview_facts["livemode"],
        "invoice_number": preview_facts["invoice_number"],
        "revision": revision,
    }


def _exact_amount_text(value: Any) -> Optional[str]:
    """Render a durable numeric amount without float rounding."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        return format(value, "f")
    return str(value)


def _invoice_selection_facts(invoice: Invoice) -> Dict[str, Any]:
    """Return only the safe invoice facts needed to choose a link target."""
    raw_currency = getattr(invoice, "currency", None)
    currency = (
        raw_currency.strip().lower()
        if isinstance(raw_currency, str)
        else None
    )
    amount = getattr(invoice, "amount", None)

    total_minor_units: Optional[int] = None
    if currency is not None:
        try:
            currency = _normalize_currency(currency)
            total_minor_units = _to_integer_minor_units(currency, amount)
        except HTTPException:
            # A durable row with an unsupported currency remains selectable by
            # its exact amount text, but is not misrepresented as Stripe units.
            total_minor_units = None

    return {
        "invoice_id": invoice.id,
        "invoice_number": getattr(invoice, "invoice_number", None),
        "currency": currency,
        "amount": _exact_amount_text(amount),
        "total_minor_units": total_minor_units,
    }


def _current_binding_facts(
    binding: Optional[InvoiceProviderBinding],
) -> Optional[Dict[str, Any]]:
    """Expose the exact stored binding identity, never connection secrets."""
    if binding is None:
        return None
    return {
        "provider": binding.provider,
        "provider_account_id": binding.provider_account_id,
        "provider_mode": binding.provider_mode,
        "external_invoice_id": binding.external_invoice_id,
        "connection_id": binding.connection_id,
        "revision": binding.revision,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


def _revision_receipt_facts(
    receipt: InvoiceProviderBindingRevision,
) -> Dict[str, Any]:
    """Expose only the allowlisted receipt columns from the real model."""
    return {
        "revision": receipt.revision,
        "actor_id": receipt.actor_id,
        "reason": receipt.reason,
        "created_at": receipt.created_at,
        "prior_provider": receipt.prior_provider,
        "prior_provider_account_id": receipt.prior_provider_account_id,
        "prior_provider_mode": receipt.prior_provider_mode,
        "prior_external_invoice_id": receipt.prior_external_invoice_id,
        "prior_connection_id": receipt.prior_connection_id,
        "new_provider": receipt.new_provider,
        "new_provider_account_id": receipt.new_provider_account_id,
        "new_provider_mode": receipt.new_provider_mode,
        "new_external_invoice_id": receipt.new_external_invoice_id,
        "new_connection_id": receipt.new_connection_id,
    }


@router.get("/invoice-links")
async def list_invoice_links(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """List durable workspace invoices for choosing a Stripe link target."""
    actor_id = _current_user_id(current_user)
    scope = _resolve_active_workspace_admin_scope(db, actor_id)

    invoices = (
        db.query(Invoice)
        .filter(Invoice.workspace_id == scope.workspace_id)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    has_more = len(invoices) > limit
    page = invoices[:limit]

    binding_revisions: Dict[str, int] = {}
    if page:
        invoice_ids = [invoice.id for invoice in page]
        bindings = (
            db.query(InvoiceProviderBinding)
            .filter(
                InvoiceProviderBinding.workspace_id == scope.workspace_id,
                InvoiceProviderBinding.invoice_id.in_(invoice_ids),
                InvoiceProviderBinding.provider == "stripe",
            )
            .all()
        )
        binding_revisions = {
            binding.invoice_id: binding.revision for binding in bindings
        }

    items: List[Dict[str, Any]] = []
    for invoice in page:
        item = _invoice_selection_facts(invoice)
        item["binding_revision"] = binding_revisions.get(invoice.id)
        items.append(item)

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
    }


@router.get("/invoice-links/{invoice_id}")
async def get_invoice_link(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Read the current Stripe binding and bounded revision receipts."""
    actor_id = _current_user_id(current_user)
    if not _nonempty_str(invoice_id):
        raise HTTPException(status_code=400, detail="Invalid request")

    scope = _resolve_active_workspace_admin_scope(db, actor_id)

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id.strip(),
            Invoice.workspace_id == scope.workspace_id,
        )
        .first()
    )
    if invoice is None:
        # A foreign or unknown invoice id is indistinguishable from missing.
        raise HTTPException(status_code=404, detail="Invoice not found")

    binding = (
        db.query(InvoiceProviderBinding)
        .filter(
            InvoiceProviderBinding.workspace_id == scope.workspace_id,
            InvoiceProviderBinding.invoice_id == invoice.id,
            InvoiceProviderBinding.provider == "stripe",
        )
        .first()
    )

    receipts: List[InvoiceProviderBindingRevision] = []
    if binding is not None:
        receipts = (
            db.query(InvoiceProviderBindingRevision)
            .filter(
                InvoiceProviderBindingRevision.workspace_id == scope.workspace_id,
                InvoiceProviderBindingRevision.invoice_id == invoice.id,
                InvoiceProviderBindingRevision.binding_id == binding.id,
            )
            .order_by(InvoiceProviderBindingRevision.revision.asc())
            .offset(offset)
            .limit(limit + 1)
            .all()
        )
    has_more = len(receipts) > limit
    receipt_page = receipts[:limit]

    detail = _invoice_selection_facts(invoice)
    detail["binding_revision"] = binding.revision if binding is not None else None
    detail["binding"] = _current_binding_facts(binding)
    detail["receipts"] = [
        _revision_receipt_facts(receipt) for receipt in receipt_page
    ]
    detail["limit"] = limit
    detail["offset"] = offset
    detail["has_more"] = has_more
    detail["next_offset"] = offset + limit if has_more else None
    return detail


@router.get("/invoice-links/{invoice_id}/payment-evidence")
async def get_invoice_payment_evidence(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return verified Stripe payment-allocation evidence for one bound invoice.

    Provider identity is resolved only from the persisted binding and scoped
    connection. The response is allocation evidence only; it makes no payout
    claim and changes no invoice, ledger, or receipt state.
    """
    actor_id = _current_user_id(current_user)
    if not _nonempty_str(invoice_id):
        raise HTTPException(status_code=400, detail="Invalid request")
    invoice_id = invoice_id.strip()

    initial_snapshot = _resolve_payment_evidence_snapshot(db, actor_id, invoice_id)
    evidence = await _fetch_payment_allocation_evidence(db, initial_snapshot)

    # Re-read after the awaited provider call. Expiring first prevents the
    # identity map from hiding a role, invoice, binding, or credential change.
    try:
        db.expire_all()
    except Exception as exc:
        logger.warning(
            "Stripe payment evidence revalidation freshness check failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to verify invoice payment evidence authorization",
        )

    rechecked_snapshot = _resolve_payment_evidence_snapshot(db, actor_id, invoice_id)
    if rechecked_snapshot != initial_snapshot:
        raise HTTPException(
            status_code=409,
            detail="Invoice or Stripe binding changed during payment verification",
        )

    # The proof escapes only after authority, binding revision, invoice facts,
    # and credential identity have all been re-proved above.
    return _safe_payment_allocation_evidence(evidence, rechecked_snapshot)

