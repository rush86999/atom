#!/usr/bin/env python3
"""Mock Microsoft identity + Graph server for end-to-end user-journey tests.

Stands in for `login.microsoftonline.com` (OAuth authority) AND
`graph.microsoft.com/v1.0` (data plane) at the HTTP boundary — nothing else
in the stack is faked: the Atom backend runs for real (real OAuth callback,
real token storage, real connection-status aggregation, real Outlook data
routes). Wire it up with:

    MICROSOFT_AUTHORITY_BASE = <mock base>              (consent + token)
    MICROSOFT_GRAPH_BASE_URL  = <mock base>/graph/v1.0  (data plane)

Endpoints served (paths mirror the real Microsoft APIs the backend calls):

  Authority (/{tenant}/oauth2/v2.0/*)
    GET  /{tenant}/oauth2/v2.0/authorize   consent page (Approve & Connect)
    POST /{tenant}/oauth2/v2.0/token       code/refresh exchange -> tokens

  Graph (Authorization: Bearer <access-token> required)
    GET  /graph/v1.0/me
    GET  /graph/v1.0/me/messages
    GET  /graph/v1.0/me/mailFolders/inbox/messages   (+ sentitems/drafts)
    GET  /graph/v1.0/me/mailFolders/inbox            (folder stats)
    GET  /graph/v1.0/me/events
    GET  /graph/v1.0/me/contacts
    GET  /graph/v1.0/me/todo/lists/tasks/tasks
    POST /graph/v1.0/me/sendMail                    (202, no body)

Usage:
    python microsoft_mock_server.py [--port N] [--host 127.0.0.1]
"""

import argparse
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CLIENT_ID = "mock-ms-client-id"
CLIENT_SECRET = "mock-ms-client-secret"
ACCESS_TOKEN = "mock-ms-access-token-123"
REFRESH_TOKEN = "mock-ms-refresh-token-456"

ME = {
    "id": "mock-ms-user-001",
    "displayName": "Rish Parikh",
    "mail": "rish@brennan.ca",
    "userPrincipalName": "rish@brennan.ca",
    "jobTitle": "Operations Lead",
    "officeLocation": "42 Maple Ave",
    "businessPhones": ["+1-555-0100"],
    "mobilePhone": "+1-555-0199",
}

MESSAGES = [
    {
        "id": "AAMkMOCKMSG1",
        "subject": "Q3 renovation schedule update",
        "bodyPreview": "Attached the updated schedule for the Maple Ave project.",
        "body": {
            "contentType": "html",
            "content": "<p>Attached the updated schedule for the Maple Ave project.</p>",
        },
        "from": {"emailAddress": {"name": "Dana White", "address": "dana@brennan.ca"}},
        "sender": {"emailAddress": {"name": "Dana White", "address": "dana@brennan.ca"}},
        "toRecipients": [
            {"emailAddress": {"name": "Rish Parikh", "address": "rish@brennan.ca"}}
        ],
        "receivedDateTime": "2026-08-28T14:03:00Z",
        "sentDateTime": "2026-08-28T14:02:00Z",
        "hasAttachments": False,
        "importance": "normal",
        "isRead": False,
        "webLink": "https://outlook.office365.com/owa/?ItemID=AAMkMOCKMSG1",
        "conversationId": "MOCKCONV1",
        "parentFolderId": "inbox",
    },
    {
        "id": "AAMkMOCKMSG2",
        "subject": "Invoice INV-1001 payment received",
        "bodyPreview": "Payment for INV-1001 has been received in full.",
        "body": {
            "contentType": "html",
            "content": "<p>Payment for INV-1001 has been received in full.</p>",
        },
        "from": {"emailAddress": {"name": "Acme Corp", "address": "ap@acme.example"}},
        "sender": {"emailAddress": {"name": "Acme Corp", "address": "ap@acme.example"}},
        "toRecipients": [
            {"emailAddress": {"name": "Rish Parikh", "address": "rish@brennan.ca"}}
        ],
        "receivedDateTime": "2026-08-27T09:30:00Z",
        "sentDateTime": "2026-08-27T09:29:00Z",
        "hasAttachments": False,
        "importance": "normal",
        "isRead": True,
        "webLink": "https://outlook.office365.com/owa/?ItemID=AAMkMOCKMSG2",
        "conversationId": "MOCKCONV2",
        "parentFolderId": "inbox",
    },
]

EVENTS = [
    {
        "id": "AAMkMOCKEVT1",
        "subject": "Site walkthrough — 42 Maple Ave",
        "body": {"contentType": "html", "content": "<p>Weekly site walkthrough.</p>"},
        "start": {"dateTime": "2026-09-02T14:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-09-02T15:00:00.0000000", "timeZone": "UTC"},
        "location": {"displayName": "42 Maple Ave"},
        "attendees": [
            {
                "emailAddress": {
                    "name": "Dana White",
                    "address": "dana@brennan.ca",
                },
                "type": "required",
            }
        ],
        "organizer": {
            "emailAddress": {"name": "Rish Parikh", "address": "rish@brennan.ca"}
        },
        "isAllDay": False,
        "showAs": "busy",
        "createdDateTime": "2026-08-25T10:00:00Z",
        "lastModifiedDateTime": "2026-08-25T10:00:00Z",
    }
]

CONTACTS = [
    {
        "id": "AAMkMOCKCNT1",
        "displayName": "Dana White",
        "givenName": "Dana",
        "surname": "White",
        "emailAddresses": [
            {"name": "Dana White", "address": "dana@brennan.ca"}
        ],
        "businessPhones": ["+1-555-0177"],
        "mobilePhone": None,
        "homePhones": [],
        "companyName": "BrennanCA",
        "jobTitle": "Site Supervisor",
        "officeLocation": None,
        "createdDateTime": "2026-07-01T08:00:00Z",
        "lastModifiedDateTime": "2026-07-01T08:00:00Z",
    }
]

TASKS = [
    {
        "id": "AAMkMOCKTSK1",
        "subject": "Approve vendor quote for kitchen fit-out",
        "body": {"contentType": "text", "content": "Quote from Vendor #7 needs sign-off."},
        "importance": "normal",
        "status": "notStarted",
        "createdDateTime": "2026-08-26T11:00:00Z",
        "lastModifiedDateTime": "2026-08-26T11:00:00Z",
        "dueDateTime": {"dateTime": "2026-09-04T17:00:00.0000000", "timeZone": "UTC"},
        "completedDateTime": None,
        "categories": ["Projects"],
    }
]

_AUTH_PATH = re.compile(r"^/([^/]+)/oauth2/v2\.0/(authorize|token)$")
_GRAPH_PATH = re.compile(r"^/graph/v1\.0(/.*)$")


class MicrosoftMockHandler(BaseHTTPRequestHandler):
    server_version = "MicrosoftMock/1.0"

    # ------------------------------------------------------------------ #
    # Plumbing
    # ------------------------------------------------------------------ #

    def log_message(self, fmt, *args):  # quiet by default
        sys.stderr.write("[ms-mock] %s\n" % (fmt % args))

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

    def _auth_ok(self) -> bool:
        return (self.headers.get("Authorization") or "") == f"Bearer {ACCESS_TOKEN}"

    # ------------------------------------------------------------------ #
    # OAuth authority
    # ------------------------------------------------------------------ #

    def _consent_page(self, qs: dict):
        redirect_uri = (qs.get("redirect_uri") or [""])[0]
        state = (qs.get("state") or [""])[0]
        client_id = (qs.get("client_id") or [""])[0]
        if client_id != CLIENT_ID or not redirect_uri:
            self._send(400, {"error": "invalid_client"})
            return
        html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Microsoft Mock Consent</title></head>
<body style="font-family:sans-serif;padding:40px;text-align:center">
<h1>Microsoft Mock</h1><p>Sign in as <b>rish@brennan.ca</b></p>
<p>Atom (Mock) requests access to Mail, Calendar, Contacts, To-Do, Files</p>
<button id="approve" onclick="window.location.href='{redirect_uri}?code=mock_ms_auth_code&state={state}'"
 style="padding:12px 32px;font-size:16px;cursor:pointer;background:#0078d4;color:#fff;border:0;border-radius:6px">Approve &amp; Connect</button></body></html>"""
        self._send(200, html, content_type="text/html")

    def _token_exchange(self, body: bytes):
        form = parse_qs(body.decode())
        grant_type = (form.get("grant_type") or [""])[0]
        client_id = (form.get("client_id") or [""])[0]
        if client_id != CLIENT_ID:
            self._send(401, {"error": "invalid_client", "error_description": "AADSTS700016"})
            return
        if grant_type not in ("authorization_code", "refresh_token"):
            self._send(400, {"error": "unsupported_grant_type"})
            return
        self._send(200, {
            "access_token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "https://graph.microsoft.com/Mail.ReadWrite "
                     "https://graph.microsoft.com/Calendars.ReadWrite "
                     "https://graph.microsoft.com/Files.ReadWrite.All "
                     "https://graph.microsoft.com/User.Read offline_access",
        })

    # ------------------------------------------------------------------ #
    # Graph data plane
    # ------------------------------------------------------------------ #

    def _graph(self, sub_path: str, method: str, payload: dict):
        if not self._auth_ok():
            self._send(401, {"error": {
                "code": "InvalidAuthenticationToken",
                "message": "Access token is empty or invalid.",
            }})
            return

        if method == "GET":
            if sub_path == "/me":
                return self._send(200, ME)
            if sub_path == "/me/messages":
                return self._send(200, {"value": MESSAGES})
            if sub_path == "/me/mailFolders/inbox/messages":
                return self._send(200, {"value": MESSAGES})
            if sub_path == "/me/mailFolders/sentitems/messages":
                return self._send(200, {"value": []})
            if sub_path == "/me/mailFolders/drafts/messages":
                return self._send(200, {"value": []})
            if sub_path == "/me/mailFolders/inbox":
                return self._send(200, {
                    "id": "inbox",
                    "displayName": "Inbox",
                    "totalItemCount": len(MESSAGES),
                    "unreadItemCount": sum(1 for m in MESSAGES if not m["isRead"]),
                })
            if sub_path == "/me/events":
                return self._send(200, {"value": EVENTS})
            if sub_path == "/me/contacts":
                return self._send(200, {"value": CONTACTS})
            if sub_path == "/me/todo/lists/tasks/tasks":
                return self._send(200, {"value": TASKS})
        elif method == "POST":
            if sub_path == "/me/sendMail":
                # Graph documents 202 Accepted with an empty body.
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if sub_path in (
                "/me/messages", "/me/events", "/me/contacts",
                "/me/todo/lists/tasks/tasks",
            ):
                created = dict(payload or {})
                created.setdefault("id", "AAMkMOCKNEW1")
                return self._send(201, created)

        return self._send(404, {"error": {"code": "NotFound", "message": sub_path}})

    # ------------------------------------------------------------------ #
    # HTTP dispatch
    # ------------------------------------------------------------------ #

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = self._qs()

        auth_match = _AUTH_PATH.match(path)
        if auth_match:
            if auth_match.group(2) == "authorize":
                return self._consent_page(qs)
            return self._send(405, {"error": "method_not_allowed"})

        # The OAuth callback 302s to FRONTEND_URL/oauth/success?provider=...
        # (the mock stands in for the pilot's frontend so the browser lands
        # on a real page in the self-contained journey).
        if path == "/oauth/success":
            return self._send(
                200,
                f"<!doctype html><html><body><h1>OAuth success</h1>"
                f"<pre>{qs}</pre></body></html>",
                content_type="text/html",
            )

        graph_match = _GRAPH_PATH.match(path)
        if graph_match:
            return self._graph(graph_match.group(1), "GET", None)

        return self._send(404, {"error": f"not_found: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        auth_match = _AUTH_PATH.match(path)
        if auth_match and auth_match.group(2) == "token":
            length = int(self.headers.get("Content-Length") or 0)
            return self._token_exchange(self.rfile.read(length))

        graph_match = _GRAPH_PATH.match(path)
        if graph_match:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {}
            return self._graph(graph_match.group(1), "POST", payload)

        return self._send(404, {"error": f"not_found: {path}"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MicrosoftMockHandler)
    print(
        f"Microsoft mock server listening on http://{args.host}:{server.server_address[1]}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
