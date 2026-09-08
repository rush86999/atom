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
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def load_send_policy_context(workspace_id: str = "default") -> Dict[str, List[str]]:
    """Return {catalog: [model ids], known_customers: [emails]} for a workspace.

    Catalog models come from ``business_product_services.name`` (the machine
    model code, e.g. SR48P). Known customers come from
    ``ecommerce_customers.email``.
    """
    empty: Dict[str, List[str]] = {"catalog": [], "known_customers": []}
    try:
        from core.database import get_db_session
        from core.models import BusinessProductService, EcommerceCustomer
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("email policy data context unavailable: %s", e)
        return empty

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
                    EcommerceCustomer.tenant_id == workspace_id,
                ).all()
                if str(row.email or "").strip()
            ]
        return {"catalog": catalog, "known_customers": customers}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("email policy data context load failed (%s)", e)
        return empty
