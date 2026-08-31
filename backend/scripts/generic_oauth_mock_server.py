#!/usr/bin/env python3
"""Generic OAuth mock for end-to-end user-journey tests — any provider.

Stands in for every OAuth provider's identity domain (accounts.google.com,
slack.com, github.com, …) at the HTTP boundary. Atom's unified OAuth flow is
provider-agnostic (api/oauth_routes.py): initiate mints a signed state and
307s to the provider's authorize URL; the callback exchanges a code at the
provider's token URL and stores tokens. This mock honours exactly that
contract for all providers at once, so one journey test can walk
connect → tokens → status → disconnect for the whole catalog.

Wire it up per provider with the OAuthConfig env overrides:

    GOOGLE_AUTHORIZE_URL = <mock>/google/authorize
    GOOGLE_TOKEN_URL     = <mock>/google/token
    GOOGLE_CLIENT_ID     = mock-google-client-id   (etc.)

Endpoints served:
  GET  /{provider}/authorize   consent page (Approve & Connect)
  POST /{provider}/token       code exchange -> tokens
  GET  /oauth/success          callback landing page (FRONTEND_URL stand-in)
  GET  /alive                  liveness

Known providers: google, slack, github, asana, notion, dropbox, box,
salesforce, linkedin, whatsapp, trello.

Usage:
    python generic_oauth_mock_server.py [--port N] [--host 127.0.0.1]
"""

import argparse
import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PROVIDERS = (
    "google",
    "slack",
    "github",
    "asana",
    "notion",
    "dropbox",
    "box",
    "salesforce",
    "linkedin",
    "whatsapp",
    "trello",
)


def client_id_for(provider: str) -> str:
    return f"mock-{provider}-client-id"


class GenericOAuthMockHandler(BaseHTTPRequestHandler):
    server_version = "GenericOAuthMock/1.0"

    # ------------------------------------------------------------------ #
    # Plumbing
    # ------------------------------------------------------------------ #

    def log_message(self, fmt, *args):  # quiet by default
        sys.stderr.write("[oauth-mock] %s\n" % (fmt % args))

    def _send(self, status: int, payload, content_type: str = "application/json"):
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

    def _qs(self) -> dict:
        return parse_qs(urlparse(self.path).query)

    # ------------------------------------------------------------------ #
    # OAuth
    # ------------------------------------------------------------------ #

    def _consent_page(self, provider: str, qs: dict):
        redirect_uri = (qs.get("redirect_uri") or [""])[0]
        state = (qs.get("state") or [""])[0]
        client_id = (qs.get("client_id") or [""])[0]
        if (
            provider not in PROVIDERS
            or client_id != client_id_for(provider)
            or not redirect_uri
        ):
            self._send(400, {"error": "invalid_client"})
            return
        html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{provider} Mock Consent</title></head>
<body style="font-family:sans-serif;padding:40px;text-align:center">
<h1>{provider} Mock</h1><p>Sign in as <b>journey-user@example.com</b></p>
<p>Atom (Mock) requests access to your {provider} account</p>
<button id="approve" onclick="window.location.href='{redirect_uri}?code=mock_oauth_auth_code&state={state}'"
 style="padding:12px 32px;font-size:16px;cursor:pointer;background:#2a7de1;color:#fff;border:0;border-radius:6px">Approve &amp; Connect</button></body></html>"""
        self._send(200, html, content_type="text/html")

    def _token_exchange(self, provider: str, body: bytes):
        form = parse_qs(body.decode())
        grant_type = (form.get("grant_type") or [""])[0]
        client_id = (form.get("client_id") or [""])[0]
        if provider not in PROVIDERS or client_id != client_id_for(provider):
            self._send(401, {"error": "invalid_client"})
            return
        if grant_type not in ("authorization_code", "refresh_token"):
            self._send(400, {"error": "unsupported_grant_type"})
            return
        # Unique per grant: oauth_tokens.refresh_token_hash is UNIQUE, and
        # real providers never issue the same refresh token to two grants.
        self._send(200, {
            "access_token": f"mock-{provider}-access-{uuid.uuid4().hex[:12]}",
            "refresh_token": f"mock-{provider}-refresh-{uuid.uuid4().hex[:12]}",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "mockScope",
        })

    # ------------------------------------------------------------------ #
    # HTTP dispatch
    # ------------------------------------------------------------------ #

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]

        # /{provider}/authorize
        if len(parts) == 2 and parts[1] == "authorize":
            return self._consent_page(parts[0], self._qs())

        if parsed.path == "/oauth/success":
            return self._send(
                200,
                "<!doctype html><html><body><h1>OAuth success</h1></body></html>",
                content_type="text/html",
            )
        if parsed.path == "/alive":
            return self._send(200, {"ok": True})

        return self._send(404, {"error": f"not_found: {parsed.path}"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 2 and parts[1] == "token":
            length = int(self.headers.get("Content-Length") or 0)
            return self._token_exchange(parts[0], self.rfile.read(length))
        return self._send(404, {"error": "not_found"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), GenericOAuthMockHandler)
    print(
        f"Generic OAuth mock server listening on http://{args.host}:{server.server_address[1]}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
