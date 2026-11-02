"""Environment-gated controlled Zoho Books transport for acceptance runs.

This module is imported only when ``ATOM_BOOKS_CONTROLLED_TRANSPORT=1``. It
replaces the provider service with a deterministic local ledger so the normal
application can exercise the registered Books actions without a live account,
credential or spend. It is not a production sender.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _state_path() -> Path:
    return Path(os.getenv(
        "ATOM_BOOKS_CONTROLLED_STATE",
        "/tmp/atom-books-controlled-state.json"))


def _load() -> Dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"bills": {}, "creates": 0, "readbacks": 0, "calls": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    data.setdefault("bills", {})
    data.setdefault("creates", 0)
    data.setdefault("readbacks", 0)
    data.setdefault("calls", [])
    return data


def _save(state: Dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str))


def controlled_state() -> Dict[str, Any]:
    return _load()


def _money(value: Any) -> str:
    return str(Decimal(str(value or "0")).quantize(Decimal("0.01")))


class ControlledBooksService:
    """Deterministic provider fixture with durable local bill identities."""

    async def _get_active_token(self, *args, **kwargs):
        return "controlled"

    async def get_organizations_strict(self, token):
        return [{"organization_id": "org-1", "name": "Controlled Org"}]

    async def get_contacts_page(
        self, token, org, page=1, per_page=200, contact_type=None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return ([{
            "contact_id": "vendor-1", "contact_name": "Acme",
            "email": "ap@acme.invalid", "currency_code": "USD",
        }], {"has_more": False})

    async def get_chart_of_accounts_page(
        self, token, org, page=1, per_page=200,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return ([
            {"account_id": "acct-1", "account_name": "Parts",
             "account_type": "expense", "account_code": "5001"},
            {"account_id": "acct-2", "account_name": "Freight",
             "account_type": "expense", "account_code": "5002"},
        ], {"has_more": False})

    async def get_bills_page(
        self, token, org, page=1, per_page=200,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        state = _load()
        return (list(state["bills"].values()), {"has_more": False})

    async def create_bill(self, token, org, payload: Dict[str, Any]):
        state = _load()
        external = str(
            payload.get("bill_number") or payload.get("reference_number")
            or "controlled-bill")
        bill_id = f"bill-controlled-{len(state['bills']) + 1}"
        payload = dict(payload)
        payload["bill_id"] = bill_id
        payload["organization_id"] = org
        state["bills"][external] = payload
        state["creates"] = int(state.get("creates") or 0) + 1
        state["calls"].append({"operation": "create_bill",
                               "bill_id": bill_id,
                               "external_id": external})
        _save(state)
        return {"bill_id": bill_id, "bill_number": payload.get("bill_number")}

    async def get_bill(self, token, org, bill_id: str):
        state = _load()
        for payload in state["bills"].values():
            if payload.get("bill_id") != bill_id:
                continue
            lines = []
            subtotal = Decimal("0.00")
            for line in payload.get("line_items") or []:
                qty = Decimal(str(line.get("quantity") or "1"))
                rate = Decimal(str(line.get("rate") or "0"))
                amount = qty * rate
                subtotal += amount
                lines.append({
                    "line_item_id": f"{bill_id}-line-{len(lines) + 1}",
                    "name": line.get("name"),
                    "description": line.get("description"),
                    "quantity": str(qty),
                    "rate": _money(rate),
                    "account_id": line.get("account_id"),
                })
            state["readbacks"] = int(state.get("readbacks") or 0) + 1
            state["calls"].append({"operation": "get_bill",
                                   "bill_id": bill_id})
            _save(state)
            return {
                "bill_id": bill_id,
                "bill_number": payload.get("bill_number"),
                "reference_number": payload.get("reference_number"),
                "vendor_id": payload.get("vendor_id"),
                "date": payload.get("date"),
                "due_date": payload.get("due_date"),
                "currency_code": payload.get("currency_code"),
                "total": _money(subtotal),
                "sub_total": _money(subtotal),
                "tax_total": "0.00",
                "discount_total": "0.00",
                "line_items": lines,
            }
        return None


async def _controlled_books_service(ids: Dict[str, str]):
    return ControlledBooksService()


def install() -> None:
    import core.connected_actions as connected_actions

    connected_actions._books_service = _controlled_books_service


install()
