"""Local eval site for the computer-use operator (stdlib only).

A tiny http.server app whose server-side STATE is ground truth for task
verification: forms record submissions, pages record visits, the login
flow records sessions. The operator drives it through a real Chromium
session exactly like it would the open web — the site is just
deterministic, free, and safe to click.

Run via run_eval.py (never imported by the backend).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATE = {
    "form": None,             # last form submission
    "form_submissions": 0,
    "form_errors": 0,
    "logged_in": False,
    "logins": 0,
    "visited": [],            # ordered page visits (excluding /state)
}

DOCS = {
    "1": ("Onboarding", "Welcome to the operator eval site. Start with the "
          "form page linked from the index."),
    "2": ("Pricing", "Plan A is $10/mo. Plan B is $25/mo. Enterprise is "
          "custom. The pricing secret word is 'quokka'."),
    "3": ("Reference", "The API secret code is ATOM-7741. Handle with care."),
}

CREDS = {"user": "operator", "pass": "hunter2"}

STYLE = ("<style>body{font-family:system-ui;margin:40px;max-width:720px}"
         "a,button{font-size:18px;padding:6px}</style>")


def _page(title, body):
    return (f"<html><head><title>{title}</title></head>{STYLE}"
            f"<body><h1>{title}</h1>{body}</body></html>").encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _track(self):
        path = urlparse(self.path).path
        if path != "/state":
            STATE["visited"].append(path)

    def do_GET(self):
        self._track()
        url = urlparse(self.path)
        path = url.path
        if path == "/state":
            return self._json(dict(STATE))
        if path == "/":
            body = ("<ul>"
                    "<li><a href='/form'>Form page</a></li>"
                    "<li><a href='/search?q=pricing'>Search: pricing</a></li>"
                    "<li><a href='/docs/1'>Docs 1</a> "
                    "<a href='/docs/2'>Docs 2</a> "
                    "<a href='/docs/3'>Docs 3</a></li>"
                    "<li><a href='/login'>Login</a></li>"
                    "<li><a href='/long'>Long page</a></li>"
                    "</ul><p>Top headline: OPERATOR EVAL DAILY</p>")
            return self._html(200, _page("Index", body))
        if path == "/form":
            body = ("<form method='post' action='/submit'>"
                    "<label>Name <input name='name'></label><br>"
                    "<label>Email <input name='email'></label><br>"
                    "<label>Company <input name='company'></label><br>"
                    "<button type='submit'>Submit</button></form>")
            return self._html(200, _page("Form", body))
        if path == "/login":
            body = (f"<p>Demo credentials: {CREDS['user']} / {CREDS['pass']}</p>"
                    "<form method='post' action='/do_login'>"
                    "<label>User <input name='user'></label><br>"
                    "<label>Pass <input name='pass' type='password'></label><br>"
                    "<button type='submit'>Log in</button></form>")
            return self._html(200, _page("Login", body))
        if path == "/dashboard":
            if not STATE["logged_in"]:
                return self._html(403, _page("Dashboard",
                                             "<p>Not logged in.</p>"))
            return self._html(200, _page("Dashboard",
                                         "<p>Welcome back! You are logged in."
                                         "</p>"))
        if path == "/long":
            paras = "".join(f"<p>Filler paragraph {i} about nothing at all."
                            f"</p>" for i in range(40))
            body = (f"{paras}<p id='code'>Bottom code: LONGPAGE-99</p>")
            return self._html(200, _page("Long page", body))
        if path.startswith("/docs/"):
            n = path.rsplit("/", 1)[-1]
            if n in DOCS:
                title, text = DOCS[n]
                return self._html(200, _page(title, f"<p>{text}</p>"))
        if path == "/search":
            q = (parse_qs(url.query).get("q") or [""])[0]
            links = ("<ol>"
                     "<li><a href='/docs/2'>Result: pricing plans</a></li>"
                     "<li><a href='/docs/1'>Result: getting started</a></li>"
                     "</ol>")
            return self._html(200, _page(f"Search: {q}",
                                         f"<p>2 results for '{q}'</p>{links}"))
        return self._html(404, _page("Not found", "<p>404</p>"))

    def do_POST(self):
        self._track()
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        fields = parse_qs(self.rfile.read(length).decode() or "")
        fields = {k: (v[0] if v else "") for k, v in fields.items()}
        if path == "/submit":
            if all(fields.get(k) for k in ("name", "email", "company")):
                STATE["form"] = fields
                STATE["form_submissions"] += 1
                return self._html(200, _page("Thanks!",
                                             "<p>Form submitted "
                                             "successfully.</p>"))
            STATE["form_errors"] += 1
            return self._html(200, _page("Form error",
                                         "<p>All fields are required.</p>"))
        if path == "/do_login":
            STATE["logins"] += 1
            if (fields.get("user") == CREDS["user"]
                    and fields.get("pass") == CREDS["pass"]):
                STATE["logged_in"] = True
                return self._redirect("/dashboard")
            return self._html(200, _page("Login failed",
                                         "<p>Wrong credentials.</p>"))
        return self._html(404, _page("Not found", "<p>404</p>"))

    # ------------------------------------------------------------- plumbing
    def _html(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.end_headers()


def start_site(port: int = 8907):
    """Start the site on a daemon thread; returns (base_url, stop)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop():
        server.shutdown()

    return f"http://127.0.0.1:{port}", stop
