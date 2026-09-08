"""Data-backed context for the email send policy gate.

Loads the workspace's machine catalog + known customers so the gate's
alternatives / customer-intro rules can be verified against REAL data
instead of only the agent's self-declared params.

Both tables are deliberately empty in fresh installs; until seeded, this
loader returns empty context and the gate keeps its param-contract behavior
(no behavior change on unseeded workspaces). Any DB failure also returns
empty context — the gate hook is fail-open, so a data-layer error can never
block a send.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def load_send_policy_context(
    workspace_id: str = "default",
    tenant_id: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Return {catalog, known_customers} for a workspace/tenant.

    Catalog models from ``business_product_services.name`` scoped by
    ``workspace_id``; customers from ``ecommerce_customers.email`` scoped by
    ``tenant_id`` (falls back to workspace_id when no separate tenant is
    supplied — single-tenant installs keep both at "default").
    """
    empty: Dict[str, List[str]] = {"catalog": [], "known_customers": []}
    try:
        from core.database import get_db_session
        from core.models import BusinessProductService, EcommerceCustomer
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("email policy data context unavailable: %s", e)
        return empty

    tenant = tenant_id or workspace_id
    try:
        with get_db_session() as db:
            catalog = [
                str(row.name).strip()
                for row in db.query(BusinessProductService).filter(
                    BusinessProductService.workspace_id == workspace_id,
                    BusinessProductService.type == "product",
                ).all()
                if str(row.name or "").strip()
            ]
            customers = [
                str(row.email).strip()
                for row in db.query(EcommerceCustomer).filter(
                    EcommerceCustomer.tenant_id == tenant,
                ).all()
                if str(row.email or "").strip()
            ]
        return {"catalog": catalog, "known_customers": customers}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("email policy data context load failed (%s)", e)
        return empty
