#!/usr/bin/env python3
"""Mock Zoho server for end-to-end user-journey tests.

Stands in for `accounts.zoho.com` (OAuth) AND the Zoho data APIs
(www.zohoapis.com) at the HTTP boundary — nothing else in the stack is
faked: the Atom backend runs for real (real OAuth callbacks, real token
storage, real sync pipeline, real LanceDB/GraphRAG writes, real chat).

Endpoints served (paths mirror the real Zoho APIs the adapter calls):

  OAuth
    GET  /oauth/v2/auth       consent page (auto-style Approve button)
    POST /oauth/v2/token      code/refresh exchange -> tokens + api_domain

  Data (Authorization: Zoho-oauthtoken <access-token> required)
    GET  /crm/v2/Leads        {"data": [lead]}
    GET  /crm/v2/Deals        {"data": [deal]}
    GET  /books/v3/organizations   {"organizations": [...]}
    GET  /books/v3/invoices        {"invoices": [...]}
    GET  /inventory/v1/organizations
    GET  /inventory/v1/items       {"items": [...]}
    GET  /inventory/v1/salesorders {"salesorders": [...]}

Usage:
    python zoho_mock_server.py [--port N] [--host 127.0.0.1]

Env knobs: ZOHO_MOCK_CLIENT_ID / ZOHO_MOCK_CLIENT_SECRET (defaults below).
"""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CLIENT_ID = "1000.MOCKZOHOCLIENTID"
CLIENT_SECRET = "mock_zoho_client_secret"
ACCESS_TOKEN = "mock-zoho-access-token-123"
REFRESH_TOKEN = "mock-zoho-refresh-token-456"

ORGANIZATION_ID = "55500000123"
ORG_NAME = "brennan.ca (Mock)"

LEADS = [{
    "id": "3000000001",
    "Full_Name": "Rish Parikh",
    "Email": "rish@brennan.ca",
    "Company": "BrennanCA",
    "Lead_Status": "Qualified",
}]

DEALS = [{
    "id": "4000000001",
    "Deal_Name": "Renovation Project",
    "Amount": 12500.00,
    "Stage": "Negotiation",
    "Closing_Date": "2026-10-15",
}]

INVOICES = [{
    "invoice_id": "5000000001",
    "invoice_number": "INV-1001",
    "customer_name": "Acme Corp",
    "total": 499.99,
    "status": "sent",
    "due_date": "2026-09-01",
}]

ITEMS = [{
    "item_id": "6000000001",
    "name": "Widget Pro",
    "sku": "WID-PRO-1",
    "rate": 42.50,
    "stock_on_hand": 17,
    "unit": "unit(s)",
}]

SALES_ORDERS = [{
    "salesorder_id": "7000000001",
    "salesorder_number": "SO-0001",
    "customer_name": "Acme Corp",
    "total": 250.00,
    "status": "open",
    "date": "2026-08-10",
}]


class ZohoMockHandler(BaseHTTPRequestHandler):
    server_version = "ZohoMock/1.0"

    # ------------------------------------------------------------------ #
    # Plumbing
    # ------------------------------------------------------------------ #

    def log_message(self, fmt, *args):  # quiet by default
        sys.stderr.write("[zoho-mock] %s\n" % (fmt % args))

    def _send(self, status: int, payload: dict, content_type: str = "application/json"):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload).encode()
        elif isinstance(payload, str):
            body = payload.encode()
        else:
            body = payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _qs(self) -> dict:
        return parse_qs(urlparse(self.path).query)

    def _headers(self) -> dict:
        return {k.lower(): v for k, v in self.headers.items()}

    def _auth_ok(self) -> bool:
        return self._headers().get("authorization") == f"Zoho-oauthtoken {ACCESS_TOKEN}"

    # ------------------------------------------------------------------ #
    # OAuth
    # ------------------------------------------------------------------ #

    def do_GET_oauth_auth(self, qs: dict):
        """Serve the consent page; approve redirects back with code+state."""
        redirect_uri = (qs.get("redirect_uri") or [""])[0]
        state = (qs.get("state") or [""])[0]
        client_id = (qs.get("client_id") or [""])[0]
        if client_id != CLIENT_ID or not redirect_uri:
            self._send(400, {"error": "invalid_client"})
            return
        html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Zoho Mock Consent</title></head>
<body style="font-family:sans-serif;padding:40px;text-align:center">
<h1>Zoho Mock</h1><p>Sign in as <b>admin@brennan.ca</b></p>
<p>Atom (Mock) requests access to Books, Inventory, CRM, WorkDrive</p>
<button id="approve" onclick="window.location.href='{redirect_uri}?code=mock_auth_code&state={state}'"
 style="padding:12px 32px;font-size:16px;cursor:pointer;background:#2a7de1;color:#fff;border:0;border-radius:6px">Approve &amp; Connect</button></body></html>"""
        self._send(200, html, content_type="text/html")

    def do_POST_oauth_token(self, body: bytes):
        form = parse_qs(body.decode())
        grant_type = (form.get("grant_type") or [""])[0]
        client_id = (form.get("client_id") or [""])[0]
        if client_id != CLIENT_ID:
            self._send(401, {"error": "invalid_client"})
            return
        if grant_type not in ("authorization_code", "refresh_token"):
            self._send(400, {"error": "unsupported_grant_type"})
            return
        base = "http://%s" % self.headers.get("Host", "127.0.0.1")
        self._send(200, {
            "access_token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
            "api_domain": base,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "ZohoBooks.fullaccess.all ZohoInventory.fullaccess.all "
                     "ZohoCRM.fullaccess.all ZohoWorkDrive.files.READ "
                     "ZohoWorkDrive.teamfolders.READ",
        })

    # ------------------------------------------------------------------ #
    # Data APIs
    # ------------------------------------------------------------------ #

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = self._qs()
        path = parsed.path

        if path == "/oauth/v2/auth":
            return self.do_GET_oauth_auth(qs)
        if path == "/oauth/v2/token":
            return self._send(405, {"error": "method_not_allowed"})

        # The OAuth callback 302s to FRONTEND_URL/oauth/success?provider=...
        # (the pilot's frontend runs on :3001; the mock stands in for it in
        # the self-contained journey so the browser actually lands on a page).
        if path == "/oauth/success":
            return self._send(
                200,
                f"<!doctype html><html><body><h1>OAuth success</h1>"
                f"<pre>{qs}</pre></body></html>",
                content_type="text/html",
            )

        if not self._auth_ok():
            return self._send(401, {"error": "invalid_token"})

        if path == "/crm/v2/Leads":
            return self._send(200, {"data": LEADS})
        if path == "/crm/v2/Deals":
            return self._send(200, {"data": DEALS})
        if path == "/books/v3/organizations" or path == "/inventory/v1/organizations":
            return self._send(200, {"organizations": [
                {"organization_id": ORGANIZATION_ID, "name": ORG_NAME},
            ]})
        if path == "/books/v3/invoices":
            return self._send(200, {"invoices": INVOICES})
        if path == "/inventory/v1/items":
            return self._send(200, {"items": ITEMS})
        if path == "/inventory/v1/salesorders":
            return self._send(200, {"salesorders": SALES_ORDERS})

        return self._send(404, {"error": f"not_found: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/oauth/v2/token":
            length = int(self.headers.get("Content-Length") or 0)
            return self.do_POST_oauth_token(self.rfile.read(length))
        return self._send(404, {"error": "not_found"})

    do_PUT = do_POST
    do_DELETE = do_GET


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ZohoMockHandler)
    print(f"Zoho mock server listening on http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()