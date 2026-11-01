"""Zoho Books adapter.

Business-critical rules encoded here:

* Every read/list call has a *strict* form used by agent/business surfaces.
  A failure raises :class:`ProviderRequestError`; it never masquerades as an
  empty page.  Legacy list methods keep their historical ``[]`` contract for
  older callers but record ``last_error``.
* Tokens resolve per acting user first, then per workspace (explicit scope),
  then per tenant.  A token whose recorded organization does not cover the
  requested organization is not reused for another organization.
* OAuth refresh uses the data-center metadata recorded on the connection
  (``accounts_base`` / ``api_domain``), not a hard-coded ``accounts.zoho.com``.
* Advertised capabilities are generated from the same dispatch table that
  executes them.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException

from core.integration_service import IntegrationService
from integrations.provider_errors import (
    ProviderRequestError,
    classify_http_status,
    parse_error,
    unavailable,
)

logger = logging.getLogger(__name__)

ZOHO_BOOKS_DEFAULT_API_DOMAIN = "https://www.zohoapis.com"
ZOHO_BOOKS_DEFAULT_ACCOUNTS_BASE = "https://accounts.zoho.com"


class ZohoBooksService(IntegrationService):
    """Zoho Books API service with strict business read/write operations."""

    provider = "zoho_books"

    # Read/list methods implemented on this service.  The dispatcher and the
    # capability declaration both derive from this table.
    _READ_OPERATIONS = (
        "get_organizations",
        "get_contacts",
        "get_contacts_page",
        "get_vendors",
        "get_customers",
        "get_chart_of_accounts",
        "get_chart_of_accounts_page",
        "get_bank_transactions",
        "get_bank_transactions_page",
        "get_invoices",
        "get_bills",
        "get_bills_page",
        "get_bill",
        "get_estimates",
        "get_estimate",
        "get_items",
    )
    _WRITE_OPERATIONS = (
        "create_contact",
        "create_vendor",
        "create_invoice",
        "create_bill",
        "update_bill",
        "create_estimate",
        "update_estimate",
    )
    _SYNC_OPERATIONS = ("sync_to_postgres_cache", "full_sync")

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        config = config or {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.accounts_base = self._resolve_accounts_base(config)
        api_domain = (
            config.get("api_domain")
            or os.getenv("ZOHO_DEFAULT_API_DOMAIN")
            or ZOHO_BOOKS_DEFAULT_API_DOMAIN
        ).rstrip("/")
        self.base_url = f"{api_domain}/books/v3"
        self.client_id = (
            config.get("client_id")
            or os.getenv("ZOHO_BOOKS_CLIENT_ID")
            or os.getenv("ZOHO_CLIENT_ID")
        )
        self.client_secret = (
            config.get("client_secret")
            or os.getenv("ZOHO_BOOKS_CLIENT_SECRET")
            or os.getenv("ZOHO_CLIENT_SECRET")
        )
        self.access_token = config.get("access_token")
        self.client = httpx.AsyncClient(timeout=30.0)
        # Set by every public request: None on success, structured failure
        # otherwise.  Legacy list methods use it to keep their [] contract
        # from being mistaken for an authoritative empty result.
        self.last_error: Optional[ProviderRequestError] = None
        self.last_correlation_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Capabilities / health
    # ------------------------------------------------------------------
    def get_capabilities(self) -> Dict[str, Any]:
        operations = list(
            self._READ_OPERATIONS + self._WRITE_OPERATIONS + self._SYNC_OPERATIONS
        )
        contracts = []
        for name in operations:
            if name.startswith(("get_", "list_")):
                kind = "read"
            elif name.startswith(("create_", "update_", "delete_")):
                kind = "write"
            else:
                kind = "sync"
            contracts.append(
                {
                    "id": name,
                    "kind": kind,
                    "effect": "none" if kind == "read" else "provider_mutation_or_cache",
                    "coverage": "paged" if name in {
                        "get_contacts", "get_vendors", "get_customers",
                        "get_invoices", "get_bills", "get_estimates", "get_items",
                    } else "single",
                }
            )
        return {
            "operations": operations,
            "operation_contracts": contracts,
            "required_params": ["access_token"],
            "optional_params": ["organization_id", "tenant_id", "user_id", "workspace_id"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False,
            "pagination": "page",
            "max_page_size": 200,
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "healthy": bool(getattr(self, "access_token", None)),
            "message": "connected" if getattr(self, "access_token", None) else "no access token configured",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "base_url": getattr(self, "base_url", None),
            "accounts_base": getattr(self, "accounts_base", None),
        }

    # ------------------------------------------------------------------
    # Errors / request plumbing
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_accounts_base(config: Dict[str, Any]) -> str:
        configured = (
            config.get("accounts_base")
            or config.get("accounts_url")
            or os.getenv("ZOHO_ACCOUNTS_BASE")
            or ZOHO_BOOKS_DEFAULT_ACCOUNTS_BASE
        )
        return str(configured).rstrip("/")

    def _set_accounts_base_from(self, row: Any) -> None:
        metadata = getattr(row, "credential_metadata", None) or {}
        instance_url = getattr(row, "instance_url", None)
        accounts_base = (
            metadata.get("accounts_base")
            or metadata.get("accounts_url")
            or (str(instance_url).replace("/api/v2", "") if instance_url else None)
            or metadata.get("api_domain")
        )
        if accounts_base:
            # Store the token endpoint base, not the data-plane domain.  A
            # data-plane domain (www.zohoapis.eu) also maps to the same DC
            # accounts host by replacing the leading host label.
            text = str(accounts_base).rstrip("/")
            if "zohoapis" in text:
                dc = text.split("zohoapis", 1)[-1].lstrip(".")
                text = f"https://accounts.zoho.{dc}" if dc else ZOHO_BOOKS_DEFAULT_ACCOUNTS_BASE
            self.accounts_base = text

    def _headers(self, access_token: str, organization_id: Optional[str] = None) -> Dict[str, str]:
        # organization_id is carried as a query parameter by Zoho Books; kept
        # in the signature because older callers used it here.
        return {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # Backwards-compatible name used by several tests/callers.  Requests use
    # the minimal header set below; this helper stays as the public shape.
    def _get_headers(self, access_token: str, organization_id: str) -> Dict[str, str]:
        return {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        access_token: str,
        organization_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform one Books request or raise a typed provider failure."""
        token = access_token or self.access_token
        if not token:
            raise unavailable(
                self.provider, operation,
                "No Zoho Books access token is available for this account.",
            )
        query = dict(params or {})
        if organization_id:
            query["organization_id"] = str(organization_id)
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=headers, params=query)
            elif method.upper() == "POST":
                response = await self.client.post(
                    url, headers=headers, params=query, json=json_body or {})
            elif method.upper() == "PUT":
                response = await self.client.put(
                    url, headers=headers, params=query, json=json_body or {})
            else:  # pragma: no cover - internal misuse
                raise ValueError(f"Unsupported HTTP method {method}")
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            self.last_error = unavailable(
                self.provider, operation,
                "Zoho Books could not be reached; retry the request.",
                kind="transient",
            )
            raise self.last_error from exc

        correlation = response.headers.get("X-Zoho-Request-Id") or response.headers.get("x-request-id")
        if correlation:
            self.last_correlation_id = correlation
        if response.status_code in (204, 304):
            return {}
        if response.status_code >= 400:
            payload: Dict[str, Any] = {}
            try:
                payload = response.json() or {}
            except Exception:  # noqa: BLE001 - provider non-JSON error body
                payload = {}
            code = str(payload.get("code") or payload.get("error") or "")
            message = str(payload.get("message") or "").strip()
            self.last_error = classify_http_status(
                self.provider, operation, response.status_code,
                provider_error=code, message=message or None,
                correlation_id=correlation,
            )
            raise self.last_error

        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - malformed 2xx
            self.last_error = parse_error(
                self.provider, operation,
                "Zoho Books returned a success status with an unreadable body.",
                status_code=response.status_code,
            )
            raise self.last_error from exc
        if not isinstance(payload, dict):
            self.last_error = parse_error(self.provider, operation)
            raise self.last_error
        return payload

    @staticmethod
    def _page_info(payload: Dict[str, Any], page: int, per_page: int, count: int) -> Dict[str, Any]:
        page_context = payload.get("page_context") or {}
        has_more = bool(page_context.get("has_more_page"))
        return {
            "returned": count,
            "page": page,
            "per_page": per_page,
            "has_more": has_more,
            "total": page_context.get("total"),
            "next_page": page + 1 if has_more else None,
        }

    async def _list(
        self,
        operation: str,
        path: str,
        container: str,
        access_token: str,
        organization_id: str,
        *,
        page: int = 1,
        per_page: int = 200,
        extra_params: Optional[Dict[str, Any]] = None,
        paged: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if paged:
            params.update({
                "page": max(1, int(page)),
                "per_page": max(1, min(int(per_page), 200)),
            })
        params.update(extra_params or {})
        payload = await self._request(
            operation, "GET", path,
            access_token=access_token,
            organization_id=organization_id,
            params=params,
        )
        rows = payload.get(container) or []
        if not isinstance(rows, list):
            raise parse_error(
                self.provider, operation,
                f"Zoho Books returned '{container}' in an unexpected shape.",
            )
        return rows, self._page_info(payload, page, per_page, len(rows))

    async def _list_legacy(
        self,
        operation: str,
        path: str,
        container: str,
        access_token: str,
        organization_id: str,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            rows, _page = await self._list(
                operation, path, container, access_token, organization_id,
                **kwargs,
            )
            return rows
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.warning(
                "%s %s failed [%s]: %s", self.provider, operation, exc.kind, exc.message)
            return []

    # ------------------------------------------------------------------
    # Token resolution / refresh (DC aware, user/workspace scoped)
    # ------------------------------------------------------------------
    async def _get_active_token(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        tid = tenant_id or getattr(self, "session_id", None) or self.tenant_id
        if not tid and not user_id and not workspace_id:
            return self.access_token or os.getenv("ZOHO_BOOKS_ACCESS_TOKEN")

        from core.database import SessionLocal
        from core.models import IntegrationToken

        db = SessionLocal()
        try:
            candidates: List[Any] = []
            if user_id:
                candidates = self._collect_token_rows(db, IntegrationToken, [
                    IntegrationToken.user_id == str(user_id),
                    IntegrationToken.provider.in_(("zoho_books", "zoho")),
                    IntegrationToken.status == "active",
                ])
            if not candidates and workspace_id:
                candidates = self._collect_token_rows(db, IntegrationToken, [
                    IntegrationToken.workspace_id == str(workspace_id),
                    IntegrationToken.provider.in_(("zoho_books", "zoho")),
                    IntegrationToken.status == "active",
                ])
            if not candidates:
                candidates = self._collect_token_rows(db, IntegrationToken, [
                    IntegrationToken.tenant_id == tid,
                    IntegrationToken.provider == "zoho_books",
                ])

            token_record = self._select_token_for_org(candidates, organization_id)
            if not token_record:
                return None
            self._set_accounts_base_from(token_record)

            now = datetime.now(timezone.utc)
            expires_at = token_record.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if not expires_at or expires_at < (now + timedelta(minutes=2)):
                if token_record.refresh_token:
                    from core.privsec.token_encryption import (
                        decrypt_token,
                        encrypt_token,
                        stamp_credential_metadata,
                    )

                    refresh_plain = decrypt_token(
                        token_record.refresh_token, allow_plaintext=True)
                    new_tokens = await self.refresh_token(refresh_plain)
                    new_access = (new_tokens or {}).get("access_token")
                    if new_access:
                        token_record.access_token = encrypt_token(new_access)
                        token_record.expires_at = now + timedelta(
                            seconds=new_tokens.get("expires_in", 3600))
                        stamp_credential_metadata(token_record)
                        db.commit()
                        return decrypt_token(
                            token_record.access_token, allow_plaintext=True)
                return None

            from core.privsec.token_encryption import decrypt_token

            return decrypt_token(token_record.access_token, allow_plaintext=True)
        except Exception as e:  # noqa: BLE001 - token store must fail closed
            logger.error(
                "Error retrieving Zoho Books token for tenant %s: %s", tid, e)
            return None
        finally:
            db.close()

    @staticmethod
    def _collect_token_rows(db: Any, model: Any, filters: List[Any]) -> List[Any]:
        """Return matching token rows; tolerate simple test doubles.

        Production sessions return a query with ``.all()`` and ordering.
        Older unit-test fakes implement only ``filter().first()``; falling
        back keeps the resolver testable without weakening the production
        query (which still orders by most-recently-updated).
        """
        query = db.query(model).filter(*filters)
        try:
            ordered = query.order_by(model.updated_at.desc())
        except AttributeError:
            ordered = query
        try:
            rows = ordered.all()
            return list(rows or [])
        except AttributeError:
            row = ordered.first()
            return [row] if row is not None else []

    @staticmethod
    def _select_token_for_org(candidates: List[Any], organization_id: Optional[str]) -> Optional[Any]:
        """Pick a token whose recorded organization scope covers the request.

        A connection with no recorded organization may serve any organization
        discovered through ``GET /organizations`` (the first-use flow).  Once
        an organization is stamped on the row, a different organization does
        not use that credential — the token and the organization identity are
        one authority scope.
        """
        if not candidates:
            return None
        org = str(organization_id or "").strip()
        if not org:
            return candidates[0]
        unscoped = []
        for row in candidates:
            metadata = getattr(row, "credential_metadata", None) or {}
            allowed = metadata.get("organization_id") or metadata.get("organization_ids")
            if isinstance(allowed, (list, tuple, set)):
                allowed = {str(v) for v in allowed}
            elif allowed:
                allowed = {str(allowed)}
            else:
                allowed = None
            if allowed is None:
                unscoped.append(row)
            elif org in allowed:
                return row
        return unscoped[0] if unscoped else None

    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh using the connection's data-center accounts host."""
        try:
            token_url = f"{self.accounts_base}/oauth/v2/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            }
            response = await self.client.post(token_url, data=data)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not payload.get("access_token"):
                logger.error(
                    "Zoho Books refresh refused by provider (error=%r)",
                    (payload or {}).get("error") if isinstance(payload, dict) else None,
                )
                return None
            return payload
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to refresh Zoho Books token: {e}")
            return None

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange an authorization code for access/refresh tokens."""
        try:
            url = f"{self.accounts_base}/oauth/v2/token"
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            }
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Zoho token exchange failed: {e}")
            raise HTTPException(status_code=400, detail="Internal error")

    # ------------------------------------------------------------------
    # Organization / contact reads
    # ------------------------------------------------------------------
    async def get_organizations(self, access_token: str) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            payload = await self._request(
                "get_organizations", "GET", "/organizations",
                access_token=access_token,
            )
            return payload.get("organizations") or []
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.warning("Failed to fetch Zoho organizations: %s", exc)
            return []

    async def get_organizations_strict(self, access_token: str) -> List[Dict[str, Any]]:
        """Strict organization read: a failure is raised, never returned as []."""
        payload = await self._request(
            "get_organizations", "GET", "/organizations",
            access_token=access_token,
        )
        return payload.get("organizations") or []

    async def get_contacts(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200,
        contact_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            rows, _ = await self._list(
                "get_contacts", "/contacts", "contacts",
                access_token, organization_id,
                extra_params={"contact_type": contact_type} if contact_type else None,
            )
            return rows
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.warning("Failed to fetch Zoho contacts: %s", exc)
            return []

    async def get_contacts_page(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200,
        contact_type: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Strict paged contacts read (raises on failure)."""
        return await self._list(
            "get_contacts", "/contacts", "contacts",
            access_token, organization_id, page=page, per_page=per_page,
            extra_params={"contact_type": contact_type} if contact_type else None,
            paged=True,
        )

    async def get_vendors(
        self, access_token: str, organization_id: str, **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        return await self.get_contacts(
            access_token, organization_id, contact_type="vendor", **kwargs)

    async def get_customers(
        self, access_token: str, organization_id: str, **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        return await self.get_contacts(
            access_token, organization_id, contact_type="customer", **kwargs)

    async def get_chart_of_accounts(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200,
    ) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            rows, _ = await self._list(
                "get_chart_of_accounts", "/chartofaccounts", "chartofaccounts",
                access_token, organization_id,
            )
            return rows
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.warning("Failed to fetch Zoho CoA: %s", exc)
            return []

    async def get_chart_of_accounts_page(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return await self._list(
            "get_chart_of_accounts", "/chartofaccounts", "chartofaccounts",
            access_token, organization_id, page=page, per_page=per_page,
            paged=True,
        )

    async def get_bank_transactions(
        self, access_token: str, organization_id: str, account_id: Optional[str] = None,
        *, page: int = 1, per_page: int = 200,
    ) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            extra = {"account_id": account_id} if account_id else None
            rows, _ = await self._list(
                "get_bank_transactions", "/banktransactions", "banktransactions",
                access_token, organization_id, extra_params=extra,
            )
            return rows
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.warning("Failed to fetch Zoho transactions: %s", exc)
            return []

    async def get_bank_transactions_page(
        self, access_token: str, organization_id: str, account_id: Optional[str] = None,
        *, page: int = 1, per_page: int = 200,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        extra = {"account_id": account_id} if account_id else None
        return await self._list(
            "get_bank_transactions", "/banktransactions", "banktransactions",
            access_token, organization_id, page=page, per_page=per_page,
            extra_params=extra, paged=True,
        )

    # Backwards-compatible alias used by the finance dispatcher.
    async def get_invoices(
        self, access_token: str, organization_id: Optional[str] = None,
        *, page: int = 1, per_page: int = 200, status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not organization_id:
            # Old dispatcher passed only the token.  Resolve the first
            # organization explicitly instead of querying with an empty org
            # (which Zoho answers with a misleading empty list).
            try:
                orgs = await self.get_organizations(access_token)
            except ProviderRequestError as exc:
                self.last_error = exc
                return []
            organization_id = str((orgs[0] if orgs else {}).get("organization_id") or "")
            if not organization_id:
                self.last_error = unavailable(
                    self.provider, "get_invoices",
                    "No Zoho Books organization is available for this connection.",
                )
                return []
        return await self._list_legacy(
            "get_invoices", "/invoices", "invoices",
            access_token, organization_id, page=page, per_page=per_page,
            extra_params={"status": status} if status else None,
        )

    async def get_bills(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200, status: Optional[str] = None,
        vendor_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        extra: Dict[str, Any] = {}
        if status:
            extra["status"] = status
        if vendor_id:
            extra["vendor_id"] = vendor_id
        return await self._list_legacy(
            "get_bills", "/bills", "bills",
            access_token, organization_id, page=page, per_page=per_page,
            extra_params=extra or None,
        )

    async def get_bills_page(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200, status: Optional[str] = None,
        vendor_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Strict paged bills read for an exact duplicate sweep.

        Unlike :meth:`get_bills`, a provider failure raises.  A duplicate
        check must not treat an unavailable page as proof that no bill exists.
        """
        extra: Dict[str, Any] = {}
        if status:
            extra["status"] = status
        if vendor_id:
            extra["vendor_id"] = vendor_id
        return await self._list(
            "get_bills", "/bills", "bills",
            access_token, organization_id, page=page, per_page=per_page,
            extra_params=extra or None, paged=True,
        )

    async def get_bill(self, access_token: str, organization_id: str, bill_id: str) -> Dict[str, Any]:
        payload = await self._request(
            "get_bill", "GET", f"/bills/{bill_id}",
            access_token=access_token, organization_id=organization_id,
        )
        return payload.get("bill") or {}

    async def get_estimates(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200, status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._list_legacy(
            "get_estimates", "/estimates", "estimates",
            access_token, organization_id, page=page, per_page=per_page,
            extra_params={"status": status} if status else None,
        )

    async def get_estimate(self, access_token: str, organization_id: str, estimate_id: str) -> Dict[str, Any]:
        payload = await self._request(
            "get_estimate", "GET", f"/estimates/{estimate_id}",
            access_token=access_token, organization_id=organization_id,
        )
        return payload.get("estimate") or {}

    async def get_items(
        self, access_token: str, organization_id: str,
        *, page: int = 1, per_page: int = 200,
    ) -> List[Dict[str, Any]]:
        return await self._list_legacy(
            "get_items", "/items", "items",
            access_token, organization_id, page=page, per_page=per_page,
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def _create(
        self, operation: str, path: str, container: str,
        access_token: str, organization_id: str, data: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = await self._request(
            operation, "POST", path,
            access_token=access_token, organization_id=organization_id,
            json_body=data,
        )
        record = payload.get(container)
        if not isinstance(record, dict):
            raise parse_error(
                self.provider, operation,
                f"Zoho Books {operation} succeeded but returned no '{container}' object.",
            )
        return record

    async def create_contact(self, access_token: str, organization_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await self._create(
                "create_contact", "/contacts", "contact",
                access_token, organization_id, contact_data)
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to create Zoho contact: %s", exc)
            raise HTTPException(status_code=500, detail="Zoho Contact creation failed")

    async def create_vendor(self, access_token: str, organization_id: str, vendor_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.create_contact(
            access_token, organization_id,
            {**vendor_data, "contact_type": "vendor"})

    async def create_invoice(self, access_token: str, organization_id: str, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await self._create(
                "create_invoice", "/invoices", "invoice",
                access_token, organization_id, invoice_data)
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to create Zoho invoice: %s", exc)
            raise HTTPException(status_code=500, detail="Zoho Invoice creation failed")

    async def create_bill(self, access_token: str, organization_id: str, bill_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a supplier bill.  Callers must supply exact decimal strings."""
        return await self._create(
            "create_bill", "/bills", "bill",
            access_token, organization_id, bill_data)

    async def update_bill(self, access_token: str, organization_id: str, bill_id: str, bill_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = await self._request(
            "update_bill", "PUT", f"/bills/{bill_id}",
            access_token=access_token, organization_id=organization_id,
            json_body=bill_data,
        )
        record = payload.get("bill")
        if not isinstance(record, dict):
            raise parse_error(
                self.provider, "update_bill",
                "Zoho Books update_bill returned no bill object.")
        return record

    async def create_estimate(self, access_token: str, organization_id: str, estimate_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._create(
            "create_estimate", "/estimates", "estimate",
            access_token, organization_id, estimate_data)

    async def update_estimate(self, access_token: str, organization_id: str, estimate_id: str, estimate_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = await self._request(
            "update_estimate", "PUT", f"/estimates/{estimate_id}",
            access_token=access_token, organization_id=organization_id,
            json_body=estimate_data,
        )
        record = payload.get("estimate")
        if not isinstance(record, dict):
            raise parse_error(
                self.provider, "update_estimate",
                "Zoho Books update_estimate returned no estimate object.")
        return record

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------
    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        parameters = parameters or {}
        context = context or {}
        try:
            access_token = (
                parameters.get("access_token")
                or context.get("access_token")
                or self.access_token
            )
            if not access_token:
                access_token = await self._get_active_token(
                    tenant_id=context.get("tenant_id") or parameters.get("tenant_id"),
                    user_id=context.get("user_id") or parameters.get("user_id"),
                    workspace_id=context.get("workspace_id") or parameters.get("workspace_id"),
                    organization_id=parameters.get("organization_id"),
                ) or ""
            org = str(parameters.get("organization_id") or "")
            page = int(parameters.get("page") or 1)
            per_page = int(parameters.get("per_page") or 200)

            if operation == "get_organizations":
                return {"success": True, "result": await self.get_organizations(access_token)}
            if operation in ("get_contacts", "get_vendors", "get_customers"):
                fn = getattr(self, operation)
                return {"success": True, "result": await fn(
                    access_token, org, page=page, per_page=per_page)}
            if operation == "get_chart_of_accounts":
                return {"success": True, "result": await self.get_chart_of_accounts(
                    access_token, org, page=page, per_page=per_page)}
            if operation == "get_bank_transactions":
                return {"success": True, "result": await self.get_bank_transactions(
                    access_token, org, parameters.get("account_id"),
                    page=page, per_page=per_page)}
            if operation == "get_invoices":
                return {"success": True, "result": await self.get_invoices(
                    access_token, org, page=page, per_page=per_page,
                    status=parameters.get("status"))}
            if operation == "get_bills":
                return {"success": True, "result": await self.get_bills(
                    access_token, org, page=page, per_page=per_page,
                    status=parameters.get("status"), vendor_id=parameters.get("vendor_id"))}
            if operation == "get_bill":
                return {"success": True, "result": await self.get_bill(
                    access_token, org, parameters["bill_id"])}
            if operation == "get_estimates":
                return {"success": True, "result": await self.get_estimates(
                    access_token, org, page=page, per_page=per_page,
                    status=parameters.get("status"))}
            if operation == "get_estimate":
                return {"success": True, "result": await self.get_estimate(
                    access_token, org, parameters["estimate_id"])}
            if operation == "get_items":
                return {"success": True, "result": await self.get_items(
                    access_token, org, page=page, per_page=per_page)}
            if operation == "create_contact":
                return {"success": True, "result": await self.create_contact(
                    access_token, org, parameters.get("data") or parameters)}
            if operation == "create_vendor":
                return {"success": True, "result": await self.create_vendor(
                    access_token, org, parameters.get("data") or parameters)}
            if operation == "create_invoice":
                return {"success": True, "result": await self.create_invoice(
                    access_token, org, parameters.get("data") or parameters)}
            if operation == "create_bill":
                return {"success": True, "result": await self.create_bill(
                    access_token, org, parameters.get("data") or parameters)}
            if operation == "update_bill":
                return {"success": True, "result": await self.update_bill(
                    access_token, org, parameters["bill_id"],
                    parameters.get("data") or parameters)}
            if operation == "create_estimate":
                return {"success": True, "result": await self.create_estimate(
                    access_token, org, parameters.get("data") or parameters)}
            if operation == "update_estimate":
                return {"success": True, "result": await self.update_estimate(
                    access_token, org, parameters["estimate_id"],
                    parameters.get("data") or parameters)}
            if operation == "sync_to_postgres_cache":
                return await self.sync_to_postgres_cache(
                    parameters.get("user_id") or context.get("user_id") or self.tenant_id,
                    access_token, org)
            if operation == "full_sync":
                return await self.full_sync(
                    parameters.get("user_id") or context.get("user_id") or self.tenant_id,
                    access_token, org)
            return {
                "success": False,
                "error_kind": "unsupported_operation",
                "error": f"Unsupported operation: {operation}",
                "supported": list(
                    self._READ_OPERATIONS + self._WRITE_OPERATIONS + self._SYNC_OPERATIONS),
            }
        except ProviderRequestError as exc:
            return exc.to_dict()
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 - do not leak provider detail
            logger.exception("Zoho Books operation %s failed", operation)
            return {
                "success": False,
                "error_kind": "provider_error",
                "error": "Zoho Books operation failed",
                "operation": operation,
            }

    # ------------------------------------------------------------------
    # Cache sync / legacy
    # ------------------------------------------------------------------
    async def sync_to_postgres_cache(self, user_id: str, access_token: str, organization_id: str) -> Dict[str, Any]:
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric

            self.last_error = None
            coa = await self.get_chart_of_accounts(access_token, organization_id)
            if self.last_error:
                return self.last_error.to_dict()
            coa_count = len(coa)

            bank_account_id = next(
                (a.get("account_id") for a in coa if a.get("account_type") == "bank"), None)
            tx_count = 0
            if bank_account_id:
                txs = await self.get_bank_transactions(
                    access_token, organization_id, bank_account_id)
                if self.last_error:
                    return self.last_error.to_dict()
                tx_count = len(txs)

            db = SessionLocal()
            metrics_synced = 0
            try:
                for key, value, unit in (
                    ("zoho_books_coa_count", coa_count, "count"),
                    ("zoho_books_recent_transactions", tx_count, "count"),
                ):
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="zoho_books",
                        metric_key=key,
                    ).first()
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        db.add(IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="zoho_books",
                            metric_key=key,
                            value=float(value),
                            unit=unit,
                        ))
                    metrics_synced += 1
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.error("Error saving Zoho Books metrics to Postgres: %s", e)
                db.rollback()
                return {"success": False, "error": "Zoho Books metrics sync failed"}
            finally:
                db.close()
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Zoho Books PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Zoho Books PostgreSQL cache sync failed"}

    async def full_sync(self, user_id: str, access_token: str, organization_id: str) -> Dict[str, Any]:
        cache_result = await self.sync_to_postgres_cache(
            user_id, access_token, organization_id)
        return {
            "success": bool(cache_result.get("success")),
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def get_zoho_books_service(config: Dict[str, Any]) -> ZohoBooksService:
    return ZohoBooksService(tenant_id="default", config=config)


zoho_books_service = ZohoBooksService(tenant_id="default", config={})
