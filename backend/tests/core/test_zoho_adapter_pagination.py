# -*- coding: utf-8 -*-
"""
Pagination tests for ZohoAdapter Books/Inventory fetchers.

The fetchers used to send one undocumented ``page_size`` request per sync,
so orgs with more than one page of invoices/items/sales orders only ever
had the first page ingested. The fetchers now page with ``page``/``per_page``
until ``page_context.has_more_page`` is false or ``limit`` is reached.
"""
import httpx
from unittest.mock import MagicMock, patch

from core.integrations.adapters.zoho import ZohoAdapter


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient, serving queued (status, json) pages."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None, params=None):
        self.requests.append({"url": url, "params": params})
        status, payload = self._pages.pop(0)
        return httpx.Response(status, json=payload, request=httpx.Request("GET", url))


def _adapter() -> ZohoAdapter:
    adapter = ZohoAdapter(db=None, workspace_id="ws-1")
    adapter._access_token = "tok"  # skip ensure_token/DB
    return adapter


def _invoice(i: int) -> dict:
    return {"invoice_id": f"inv-{i}", "invoice_number": f"INV-{i:03d}", "total": i}


def _item(i: int) -> dict:
    return {"item_id": f"itm-{i}", "name": f"Item {i}"}


def _sales_order(i: int) -> dict:
    return {"salesorder_id": f"so-{i}", "salesorder_number": f"SO-{i:03d}"}


def _page(key: str, records: list, has_more: bool) -> tuple:
    return (
        200,
        {
            key: records,
            "page_context": {"has_more_page": has_more},
        },
    )


async def test_invoices_follow_has_more_pages():
    client = _FakeAsyncClient([
        _page("invoices", [_invoice(i) for i in range(100)], has_more=True),
        _page("invoices", [_invoice(i) for i in range(100, 150)], has_more=False),
    ])
    with patch("core.integrations.adapters.zoho.httpx.AsyncClient", MagicMock(return_value=client)):
        out = await _adapter().get_invoices("org-1", limit=500)

    assert [r["id"] for r in out] == [f"inv-{i}" for i in range(150)]
    assert len(client.requests) == 2
    assert client.requests[0]["params"]["page"] == 1
    assert client.requests[1]["params"]["page"] == 2
    # per_page caps at the API maximum even when the caller asks for more
    assert client.requests[0]["params"]["per_page"] == 100
    assert client.requests[0]["params"]["organization_id"] == "org-1"
    assert client.requests[0]["url"].endswith("/books/v3/invoices")


async def test_stops_on_short_page_without_page_context():
    # Providers may omit page_context entirely; a short page means last page.
    client = _FakeAsyncClient([
        (200, {"invoices": [_invoice(0), _invoice(1)]}),
    ])
    with patch("core.integrations.adapters.zoho.httpx.AsyncClient", MagicMock(return_value=client)):
        out = await _adapter().get_invoices("org-1", limit=500)

    assert len(out) == 2
    assert len(client.requests) == 1


async def test_limit_caps_cross_page_collection():
    client = _FakeAsyncClient([
        _page("invoices", [_invoice(i) for i in range(100)], has_more=True),
        _page("invoices", [_invoice(i) for i in range(100, 200)], has_more=True),
    ])
    with patch("core.integrations.adapters.zoho.httpx.AsyncClient", MagicMock(return_value=client)):
        out = await _adapter().get_invoices("org-1", limit=120)

    assert len(out) == 120
    assert len(client.requests) == 2


async def test_items_paginate_from_inventory_base():
    client = _FakeAsyncClient([
        _page("items", [_item(i) for i in range(100)], has_more=True),
        _page("items", [_item(100)], has_more=False),
    ])
    with patch("core.integrations.adapters.zoho.httpx.AsyncClient", MagicMock(return_value=client)):
        out = await _adapter().get_items("org-2", limit=200)

    assert len(out) == 101
    assert client.requests[0]["url"].endswith("/inventory/v1/items")
    assert client.requests[0]["params"]["per_page"] == 100


async def test_sales_orders_paginate():
    client = _FakeAsyncClient([
        _page("salesorders", [_sales_order(i) for i in range(2)], has_more=False),
    ])
    with patch("core.integrations.adapters.zoho.httpx.AsyncClient", MagicMock(return_value=client)):
        out = await _adapter().get_sales_orders("org-2", limit=100)

    assert [r["id"] for r in out] == ["so-0", "so-1"]
    assert client.requests[0]["url"].endswith("/inventory/v1/salesorders")


async def test_provider_error_returns_empty_list():
    client = _FakeAsyncClient([
        (500, {"message": "boom"}),
        (500, {"message": "boom"}),
    ])
    with patch("core.integrations.adapters.zoho.httpx.AsyncClient", MagicMock(return_value=client)):
        out = await _adapter().get_invoices("org-1", limit=500)

    assert out == []
