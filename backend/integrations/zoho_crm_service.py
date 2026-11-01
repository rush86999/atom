"""Zoho CRM adapter.

Contract fixes over the previous implementation:

* ``execute_operation('create_record', ...)`` passes the module and record
  data as the method expects.  The old branch passed a single dict and every
  generic create raised ``TypeError`` before dispatch.
* Reads that the business actions depend on (contacts, accounts, deals,
  single records) have real methods, not just Leads/Deals list calls.
* Failures raise :class:`ProviderRequestError` through ``*_strict`` helpers;
  the legacy list methods keep their historical ``[]`` for old callers but
  record ``last_error``.  The agent surface uses the strict methods.
* Refresh honors the connection's data-center ``accounts_base`` metadata
  instead of hard-coding ``accounts.zoho.com``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from core.database import SessionLocal
from core.integration_service import IntegrationService
from core.models import IntegrationToken
from integrations.provider_errors import (
    ProviderRequestError,
    classify_http_status,
    parse_error,
    unavailable,
)

logger = logging.getLogger(__name__)

ZOHO_CRM_DEFAULT_API_DOMAIN = "https://www.zohoapis.com"
ZOHO_CRM_DEFAULT_ACCOUNTS_BASE = "https://accounts.zoho.com"


class ZohoCRMService(IntegrationService):
    provider = "zoho_crm"

    _READ_OPERATIONS = (
        "get_leads",
        "get_deals",
        "get_contacts",
        "get_accounts",
        "get_record",
        "search_records",
        "get_modules",
        "get_fields",
    )
    _WRITE_OPERATIONS = (
        "create_lead",
        "create_record",
        "update_record",
    )

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        config = config or {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.accounts_base = self._resolve_accounts_base(config)
        api_domain = (
            config.get("api_domain")
            or os.getenv("ZOHO_DEFAULT_API_DOMAIN")
            or ZOHO_CRM_DEFAULT_API_DOMAIN
        ).rstrip("/")
        self.base_url = f"{api_domain}/crm/v2"
        self.access_token = config.get("access_token") or os.getenv("ZOHO_CRM_ACCESS_TOKEN")
        self.client_id = (
            config.get("client_id")
            or os.getenv("ZOHO_CRM_CLIENT_ID")
            or os.getenv("ZOHO_CLIENT_ID")
        )
        self.client_secret = (
            config.get("client_secret")
            or os.getenv("ZOHO_CRM_CLIENT_SECRET")
            or os.getenv("ZOHO_CLIENT_SECRET")
        )
        self.client = httpx.AsyncClient(timeout=30.0)
        self.last_error: Optional[ProviderRequestError] = None
        self.last_correlation_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Capabilities / health
    # ------------------------------------------------------------------
    def get_capabilities(self) -> Dict[str, Any]:
        operations = list(self._READ_OPERATIONS + self._WRITE_OPERATIONS)
        contracts = []
        for name in operations:
            kind = "read" if name.startswith("get_") or name == "search_records" else "write"
            contracts.append(
                {
                    "id": name,
                    "kind": kind,
                    "effect": "none" if kind == "read" else "provider_mutation",
                    "coverage": "paged" if name in {
                        "get_leads", "get_deals", "get_contacts", "get_accounts",
                        "search_records",
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
    # Token / refresh
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_accounts_base(config: Dict[str, Any]) -> str:
        configured = (
            config.get("accounts_base")
            or config.get("accounts_url")
            or os.getenv("ZOHO_ACCOUNTS_BASE")
            or ZOHO_CRM_DEFAULT_ACCOUNTS_BASE
        )
        return str(configured).rstrip("/")

    def _set_accounts_base_from(self, row: Any) -> None:
        metadata = getattr(row, "credential_metadata", None) or {}
        instance_url = getattr(row, "instance_url", None)
        accounts_base = (
            metadata.get("accounts_base")
            or metadata.get("accounts_url")
            or metrics_domain(instance_url)
            or metadata.get("api_domain")
        )
        if accounts_base:
            self.accounts_base = str(accounts_base).rstrip("/")

    @staticmethod
    def _collect_token_rows(db: Any, model: Any, filters: List[Any]) -> List[Any]:
        query = db.query(model).filter(*filters)
        try:
            ordered = query.order_by(model.updated_at.desc())
        except AttributeError:
            ordered = query
        try:
            return list(ordered.all() or [])
        except AttributeError:
            row = ordered.first()
            return [row] if row is not None else []

    async def _get_active_token(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[str]:
        tid = tenant_id or self.tenant_id
        if not tid and not user_id and not workspace_id:
            return self.access_token or os.getenv("ZOHO_CRM_ACCESS_TOKEN")

        db = SessionLocal()
        try:
            candidates: List[Any] = []
            if user_id:
                candidates = self._collect_token_rows(db, IntegrationToken, [
                    IntegrationToken.user_id == str(user_id),
                    IntegrationToken.provider.in_(("zoho_crm", "zoho")),
                    IntegrationToken.status == "active",
                ])
            if not candidates and workspace_id:
                candidates = self._collect_token_rows(db, IntegrationToken, [
                    IntegrationToken.workspace_id == str(workspace_id),
                    IntegrationToken.provider.in_(("zoho_crm", "zoho")),
                    IntegrationToken.status == "active",
                ])
            if not candidates:
                candidates = self._collect_token_rows(db, IntegrationToken, [
                    IntegrationToken.tenant_id == tid,
                    IntegrationToken.provider == "zoho_crm",
                ])
            token_record = candidates[0] if candidates else None
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
                    if new_tokens and new_tokens.get("access_token"):
                        token_record.access_token = encrypt_token(
                            new_tokens["access_token"])
                        token_record.expires_at = now + timedelta(
                            seconds=new_tokens.get("expires_in", 3600))
                        stamp_credential_metadata(token_record)
                        db.commit()
                        return decrypt_token(
                            token_record.access_token, allow_plaintext=True)
                return None

            from core.privsec.token_encryption import decrypt_token

            return decrypt_token(token_record.access_token, allow_plaintext=True)
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error retrieving Zoho CRM token for tenant %s: %s", tid, e)
            return None
        finally:
            db.close()

    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        try:
            if not self.client_id or not self.client_secret:
                logger.error("Zoho CRM client credentials missing in configuration")
                return None
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
                    "Zoho CRM refresh refused by provider (error=%r)",
                    (payload or {}).get("error") if isinstance(payload, dict) else None,
                )
                return None
            return payload
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to refresh Zoho CRM token: {e}")
            return None

    # ------------------------------------------------------------------
    # Request plumbing
    # ------------------------------------------------------------------
    async def _request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = access_token or self.access_token
        if not token:
            token = await self._get_active_token(tenant_id=tenant_id)
        if not token:
            raise unavailable(
                self.provider, operation,
                "No Zoho CRM access token is available for this account.",
            )
        headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await self.client.post(
                    url, headers=headers, params=params, json=json_body or {})
            elif method.upper() == "PUT":
                response = await self.client.put(
                    url, headers=headers, params=params, json=json_body or {})
            else:  # pragma: no cover
                raise ValueError(f"Unsupported method {method}")
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            self.last_error = unavailable(
                self.provider, operation,
                "Zoho CRM could not be reached; retry the request.",
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
            except Exception:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            self.last_error = parse_error(
                self.provider, operation,
                "Zoho CRM returned a success status with an unreadable body.",
                status_code=response.status_code,
            )
            raise self.last_error from exc
        if not isinstance(payload, dict):
            self.last_error = parse_error(self.provider, operation)
            raise self.last_error
        return payload

    @staticmethod
    def _records(payload: Dict[str, Any], operation: str) -> List[Dict[str, Any]]:
        records = payload.get("data") or []
        if not isinstance(records, list):
            raise parse_error(
                "zoho_crm", operation,
                "Zoho CRM returned 'data' in an unexpected shape.")
        return records

    async def _list_strict(
        self, operation: str, path: str, *, tenant_id: Optional[str] = None,
        page: int = 1, per_page: int = 200,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        params = {"page": max(1, int(page)), "per_page": max(1, min(int(per_page), 200))}
        params.update(extra_params or {})
        payload = await self._request(
            operation, "GET", path,
            access_token=self.access_token or "",
            params=params, tenant_id=tenant_id,
        )
        return self._records(payload, operation)

    async def _list_legacy(self, operation: str, path: str, **kwargs: Any) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            return await self._list_strict(operation, path, **kwargs)
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.warning("Zoho CRM %s failed [%s]: %s", operation, exc.kind, exc.message)
            return []

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def get_leads(self, limit: int = 200, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            payload = await self._request(
                "get_leads", "GET", "/Leads",
                access_token=active_token, params={"per_page": limit},
            )
            return self._records(payload, "get_leads")
        except HTTPException:
            raise
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to fetch Zoho CRM leads: %s", exc)
            return []
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch Zoho CRM leads: {e}")
            return []

    async def get_deals(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.last_error = None
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            payload = await self._request(
                "get_deals", "GET", "/Deals", access_token=active_token)
            return self._records(payload, "get_deals")
        except HTTPException:
            raise
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to fetch Zoho CRM deals: %s", exc)
            return []
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch Zoho CRM deals: {e}")
            return []

    async def get_contacts(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list_legacy("get_contacts", "/Contacts", tenant_id=tenant_id)

    async def get_accounts(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._list_legacy("get_accounts", "/Accounts", tenant_id=tenant_id)

    async def get_record(self, module: str, record_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        payload = await self._request(
            "get_record", "GET", f"/{module}/{record_id}",
            access_token="", tenant_id=tenant_id,
        )
        records = self._records(payload, "get_record")
        return records[0] if records else {}

    async def search_records(
        self, module: str, query: str, tenant_id: Optional[str] = None,
        *, page: int = 1, per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        return await self._list_strict(
            "search_records", f"/{module}/search",
            tenant_id=tenant_id, page=page, per_page=per_page,
            extra_params={"word": query},
        )

    async def get_modules(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                return []
            payload = await self._request(
                "get_modules", "GET", "/settings/modules",
                access_token=active_token)
            return payload.get("modules") or []
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to fetch Zoho CRM modules: %s", exc)
            return []
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch Zoho CRM modules: {e}")
            return []

    async def get_fields(self, module: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                return []
            payload = await self._request(
                "get_fields", "GET", f"/settings/fields?module={module}",
                access_token=active_token)
            return payload.get("fields") or []
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to fetch Zoho CRM fields for %s: %s", module, exc)
            return []
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch Zoho CRM fields for {module}: {e}")
            return []

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    async def create_lead(self, lead_data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            payload = await self._request(
                "create_lead", "POST", "/Leads",
                access_token=active_token, json_body={"data": [lead_data]})
            records = self._records(payload, "create_lead")
            return records[0] if records else {}
        except HTTPException:
            raise
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to create Zoho CRM lead: %s", exc)
            raise HTTPException(status_code=500, detail="Zoho CRM Lead creation failed")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to create Zoho CRM lead: {e}")
            raise HTTPException(status_code=500, detail="Zoho CRM Lead creation failed")

    async def create_record(self, module: str, data: Dict[str, Any], tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a record in ``module``.  The generic dispatcher MUST pass
        both arguments; a single dict is a contract violation."""
        if not module or not isinstance(module, str):
            raise ValueError("create_record requires a module name")
        if not isinstance(data, dict):
            raise ValueError("create_record requires a data object")
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            payload = await self._request(
                "create_record", "POST", f"/{module}",
                access_token=active_token, json_body={"data": [data]})
            records = self._records(payload, "create_record")
            return records[0] if records else {}
        except HTTPException:
            raise
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to create Zoho CRM record in %s: %s", module, exc)
            raise HTTPException(status_code=500, detail=f"Zoho CRM {module} creation failed")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to create Zoho CRM record in {module}: {e}")
            raise HTTPException(status_code=500, detail=f"Zoho CRM {module} creation failed")

    async def update_record(
        self, module: str, record_id: str, fields: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not module or not record_id:
            raise ValueError("update_record requires module and record_id")
        try:
            active_token = await self._get_active_token(tenant_id)
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            payload = await self._request(
                "update_record", "PUT", f"/{module}/{record_id}",
                access_token=active_token, json_body={"data": [fields]})
            records = self._records(payload, "update_record")
            return records[0] if records else {}
        except HTTPException:
            raise
        except ProviderRequestError as exc:
            self.last_error = exc
            logger.error("Failed to update Zoho CRM %s/%s: %s", module, record_id, exc)
            raise HTTPException(status_code=500, detail=f"Zoho CRM {module} update failed")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to update Zoho CRM {module}/{record_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Zoho CRM {module} update failed")

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
            advertised = set(self._READ_OPERATIONS + self._WRITE_OPERATIONS)
            if operation not in advertised:
                return {
                    "success": False,
                    "error_kind": "unsupported_operation",
                    "error": f"Unsupported operation: {operation}",
                    "supported": list(self._READ_OPERATIONS + self._WRITE_OPERATIONS),
                }
            tenant_id = context.get("tenant_id") or parameters.get("tenant_id")
            if operation == "get_leads":
                return {"success": True, "result": await self.get_leads(tenant_id=tenant_id)}
            if operation == "get_deals":
                return {"success": True, "result": await self.get_deals(tenant_id=tenant_id)}
            if operation == "get_contacts":
                return {"success": True, "result": await self.get_contacts(tenant_id=tenant_id)}
            if operation == "get_accounts":
                return {"success": True, "result": await self.get_accounts(tenant_id=tenant_id)}
            if operation == "get_modules":
                return {"success": True, "result": await self.get_modules(tenant_id=tenant_id)}
            if operation == "get_fields":
                return {"success": True, "result": await self.get_fields(
                    parameters.get("module") or parameters.get("module_api_name") or "Leads",
                    tenant_id=tenant_id)}
            if operation == "get_record":
                return {"success": True, "result": await self.get_record(
                    parameters["module"], parameters["record_id"], tenant_id=tenant_id)}
            if operation == "search_records":
                return {"success": True, "result": await self.search_records(
                    parameters.get("module") or "Leads",
                    parameters.get("query") or parameters.get("word") or "",
                    tenant_id=tenant_id)}
            if operation == "create_lead":
                return {"success": True, "result": await self.create_lead(
                    parameters.get("data") or parameters, tenant_id=tenant_id)}
            if operation == "create_record":
                module = parameters.get("module") or parameters.get("module_api_name")
                data = parameters.get("data") or parameters.get("record") or {}
                if not module:
                    return {
                        "success": False,
                        "error_kind": "invalid_request",
                        "error": "create_record requires 'module' and 'data'.",
                    }
                return {"success": True, "result": await self.create_record(
                    module, data, tenant_id=tenant_id)}
            if operation == "update_record":
                return {"success": True, "result": await self.update_record(
                    parameters["module"], parameters["record_id"],
                    parameters.get("data") or parameters.get("fields") or {},
                    tenant_id=tenant_id)}
            # Defensive: advertised but not dispatched would be a contract bug.
            return {
                "success": False,
                "error_kind": "unsupported_operation",
                "error": f"Operation advertised but not dispatched: {operation}",
            }
        except ProviderRequestError as exc:
            return exc.to_dict()
        except HTTPException:
            raise
        except KeyError as exc:
            return {
                "success": False,
                "error_kind": "invalid_request",
                "error": f"Missing required parameter: {exc}",
            }
        except Exception:  # noqa: BLE001 - never leak provider detail
            logger.exception("Zoho CRM operation %s failed", operation)
            return {
                "success": False,
                "error_kind": "provider_error",
                "error": "Zoho CRM operation failed",
                "operation": operation,
            }

    # ------------------------------------------------------------------
    # Cache sync (legacy)
    # ------------------------------------------------------------------
    async def sync_to_postgres_cache(self, workspace_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            from core.models import IntegrationMetric

            leads = await self.get_leads()
            deals = await self.get_deals()
            lead_count = len(leads)
            deal_count = len(deals)
            total_revenue = sum(float(d.get("Amount", 0) or 0) for d in deals)

            # Resolve through core.database at call time: the module-level
            # import is patchable for token tests, while metric sync must use
            # the session factory the application configured (and tests
            # patch the canonical module path).
            from core.database import SessionLocal as _SessionLocal

            db = _SessionLocal()
            metrics_synced = 0
            try:
                for key, value, unit in (
                    ("zoho_crm_lead_count", lead_count, "count"),
                    ("zoho_crm_deal_count", deal_count, "count"),
                    ("zoho_crm_total_revenue", total_revenue, "currency"),
                ):
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=workspace_id,
                        integration_type="zoho_crm",
                        metric_key=key,
                    ).first()
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        db.add(IntegrationMetric(
                            workspace_id=workspace_id,
                            integration_type="zoho_crm",
                            metric_key=key,
                            value=float(value),
                            unit=unit,
                        ))
                    metrics_synced += 1
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.error("Error saving Zoho CRM metrics to Postgres: %s", e)
                db.rollback()
                return {"success": False, "error": "Zoho CRM metrics sync failed"}
            finally:
                db.close()
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Zoho CRM PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Zoho CRM PostgreSQL cache sync failed"}

    async def full_sync(self, workspace_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        cache_result = await self.sync_to_postgres_cache(workspace_id)
        return {
            "success": bool(cache_result.get("success")),
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def metrics_domain(instance_url: Optional[str]) -> Optional[str]:
    """Derive the accounts host from a Zoho data-plane instance URL."""
    if not instance_url:
        return None
    text = str(instance_url).rstrip("/")
    if "zohoapis" in text:
        dc = text.split("zohoapis", 1)[-1].lstrip(".")
        return f"https://accounts.zoho.{dc}" if dc else None
    if "accounts.zoho" in text:
        return text
    return None
