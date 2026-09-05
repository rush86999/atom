"""Provider bindings for core.fact_watch — the integrations side of the
registry. core never imports this module; the app lifespan imports it
once, which is what makes an app's facts watchable.

Adding an app = one checker + one extractor + a register call here. First
provider: Zoho Inventory stock — the WG-350DSAV quote went out grounded on
stock_on_hand = 1 (live 2026-09-04); one sale later the draft is wrong and
nothing notices. The extractor reads the tool-evidence block the chat
planner already produces (zoho_inventory.search_items slim items), so
grounding a draft on stock automatically arms the watch.

Good next candidates (same seam): quickbooks/xero invoice status,
zoho_crm deal stage, stripe payment status, shopify product availability.
"""
import logging
import re
from typing import List, Optional, Tuple

from core.fact_watch import (
    register_checker,
    register_extractor,
)

logger = logging.getLogger(__name__)

# zoho_inventory.search_items renders slim item dicts into the evidence
# block (str(data)); item ids are numeric strings.
_ITEM_ID_RE = re.compile(r"['\"]?item_id['\"]?\s*[:=]\s*['\"]?(\d+)")


def _register() -> None:
    async def _check_inventory_item(entity_id: str, user_id: Optional[str]) -> Optional[float]:
        from integrations.zoho_inventory_service import ZohoInventoryService

        svc = ZohoInventoryService(tenant_id="default")
        result = await svc.check_stock(entity_id, user_id=user_id)
        if "stock_on_hand" not in result:
            return None
        return result.get("stock_on_hand")

    def _extract_inventory_items(evidence_text: str) -> List[Tuple[str, str, str]]:
        out: List[Tuple[str, str, str]] = []
        for item_id in _ITEM_ID_RE.findall(evidence_text or ""):
            key = ("inventory_item", item_id, "stock_on_hand")
            if key not in out:
                out.append(key)
        return out

    register_checker("zoho_inventory", "inventory_item", _check_inventory_item)
    register_extractor("zoho_inventory", _extract_inventory_items)
    logger.info("fact watch providers registered: zoho_inventory/inventory_item")


_register()
