"""Local eval site for the computer-use operator (stdlib only).

A tiny http.server app that is the curriculum program's first mutable
environment (docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md, Phases 1b-3).

State model — the rev 2 hardening:
- WORLD   mutable content the agent interacts with (page copy, codes,
          credentials, search results, form labels). Mutation setup layers
          write here and ONLY here.
- EVIDENCE append-only execution facts owned by the verifiers (submissions,
          error counts, logins, visit order). The mutation API structurally
          cannot write it; verifiers read it plus WORLD ground truth.

A `Rules` engine implements upstream `Rules`-layer semantics: observation
filters (hide a link, redact text) applied at render time, action
interceptors (block a path, fail the first N posts) applied at request time.

`EvalSite.request()` is a pure-Python dispatch (no socket needed) so tests,
canaries, and the adapter can drive the site in-process; the HTTP handler is
a thin wrapper over it. Control endpoints (/control/*) require a per-run
token; agent-facing pages never do.

Run via run_eval.py (never imported by the backend).
"""

import copy
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# World schema: every legal WORLD key. /control/load_world rejects anything
# else — this is the world/evidence firebreak.
# ---------------------------------------------------------------------------

WORLD_SCHEMA = {
    "headline",            # str, index page
    "docs",                # {"1"/"2"/"3": {"title", "text", "secret_word"?, "api_code"?}}
    "creds",               # {"user", "pass"} shown on the login page
    "longpage_code",       # str, bottom of /long
    "search_results",      # [{"title", "href"}] rendered for any query
    "form_fields",         # [{"name", "label"}] — labels render; names are contract
    "form_error_message",  # str shown when a submission is incomplete
}

OBSERVE_RULE_KINDS = {
    # params: href — drop anchors pointing at href from rendered pages
    "hide_link": {"href"},
    # params: text — replace literal text occurrences with "[redacted]"
    "redact_text": {"text"},
}
ACTION_RULE_KINDS = {
    # params: path, status=404 — short-circuit matching requests
    "block_path": {"path"},
    # params: method, path, n, status=500 — fail the first n matching requests
    "fail_first_n": {"method", "path", "n"},
}


def default_world() -> dict:
    """The unmutated base world (the original hardcoded site content)."""
    return {
        "headline": "OPERATOR EVAL DAILY",
        "docs": {
            "1": {
                "title": "Onboarding",
                "text": "Welcome to the operator eval site. Start with the "
                        "form page linked from the index.",
            },
            "2": {
                "title": "Pricing",
                "text": "Plan A is $10/mo. Plan B is $25/mo. Enterprise is "
                        "custom. The pricing secret word is '{secret_word}'.",
                "secret_word": "quokka",
            },
            "3": {
                "title": "Reference",
                "text": "The API secret code is {api_code}. Handle with care.",
                "api_code": "ATOM-7741",
            },
        },
        "creds": {"user": "operator", "pass": "hunter2"},
        "longpage_code": "LONGPAGE-99",
        "search_results": [
            {"title": "Result: pricing plans", "href": "/docs/2"},
            {"title": "Result: getting started", "href": "/docs/1"},
        ],
        "form_fields": [
            {"name": "name", "label": "Name"},
            {"name": "email", "label": "Email"},
            {"name": "company", "label": "Company"},
        ],
        "form_error_message": "All fields are required.",
    }


def fresh_evidence() -> dict:
    return {
        "form": None,             # last complete form submission (dict)
        "form_submissions": 0,
        "form_errors": 0,
        "last_form_error": None,  # the message shown at the last rejected submit
        "logged_in": False,
        "logins": 0,
        "visited": [],            # ordered page visits (excluding /state, /control)
    }


STYLE = ("<style>body{font-family:system-ui;margin:40px;max-width:720px}"
         "a,button{font-size:18px;padding:6px}</style>")

_UNPROTECTED_PATHS = {"/state"}          # tracked paths exempt from visit log


class RuleError(ValueError):
    """Invalid rule kind/params submitted to /control/rules."""


class Rules:
    """Declarative observation filters + action interceptors."""

    def __init__(self):
        self.observe: list[dict] = []
        self.action: list[dict] = []
        self._counters: dict[int, int] = {}
        self._lock = threading.Lock()

    def set(self, observe: list[dict], action: list[dict]) -> None:
        for rule in observe:
            self._validate(rule, OBSERVE_RULE_KINDS)
        for rule in action:
            self._validate(rule, ACTION_RULE_KINDS)
        with self._lock:
            self.observe = list(observe)
            self.action = list(action)
            self._counters = {}

    def clear(self) -> None:
        with self._lock:
            self.observe = []
            self.action = []
            self._counters = {}

    @staticmethod
    def _validate(rule: dict, kinds: dict) -> None:
        kind = rule.get("kind")
        if kind not in kinds:
            raise RuleError(
                f"Unknown rule kind {kind!r}; known: {sorted(kinds)}")
        missing = kinds[kind] - set(rule)
        if missing:
            raise RuleError(f"Rule {kind!r} missing params {sorted(missing)}")

    # -- observation side ---------------------------------------------------

    def filter_html(self, html: str) -> str:
        """Apply observation filters to rendered HTML (render-time)."""
        for rule in self.observe:
            if rule["kind"] == "hide_link":
                html = _remove_links_to(html, rule["href"])
            elif rule["kind"] == "redact_text":
                html = html.replace(rule["text"], "[redacted]")
        return html

    # -- action side ---------------------------------------------------------

    def intercept(self, method: str, path: str) -> int | None:
        """Return a response status to short-circuit with, or None to pass."""
        with self._lock:
            for rule in self.action:
                if rule["kind"] == "block_path" and path == rule["path"]:
                    return int(rule.get("status", 404))
                if rule["kind"] == "fail_first_n" and path == rule["path"] \
                        and method.upper() == rule["method"].upper():
                    idx = self._counters.get(id(rule), 0)
                    if idx < int(rule["n"]):
                        self._counters[id(rule)] = idx + 1
                        return int(rule.get("status", 500))
        return None


def _remove_links_to(html: str, href: str) -> str:
    """Remove <a ...>...</a> elements whose href is exactly `href`."""
    out, i = [], 0
    while True:
        start = html.find("<a", i)
        if start == -1:
            out.append(html[i:])
            break
        end = html.find("</a>", start)
        if end == -1:
            out.append(html[i:])
            break
        tag_end = html.find(">", start)
        tag = html[start:tag_end]
        if f"href='{href}'" in tag or f'href="{href}"' in tag:
            out.append(html[i:start])
        else:
            out.append(html[i:end + 4])
        i = end + 4
    return "".join(out)


class EvalSite:
    """One isolated environment instance. Create one per run/concurrent arm.

    World/evidence discipline:
    - `load_world_updates` validates keys against WORLD_SCHEMA (deepcopy in),
      so mutation payloads cannot alias or reach evidence;
    - evidence is mutated only by request handlers (agent activity) and
      `reset()`.
    """

    def __init__(self, run_token: str | None = None,
                 base_world: dict | None = None):
        self.run_token = run_token or secrets.token_hex(16)
        self.base_world = copy.deepcopy(base_world or default_world())
        self.world = copy.deepcopy(self.base_world)
        self.evidence = fresh_evidence()
        self.rules = Rules()
        self._lock = threading.RLock()

    # -- control surface (token-checked; used by harness, never the agent) --

    def control_reset(self) -> None:
        with self._lock:
            self.world = copy.deepcopy(self.base_world)
            self.evidence = fresh_evidence()
            self.rules.clear()

    def load_world_updates(self, updates: dict) -> None:
        illegal = set(updates) - WORLD_SCHEMA
        if illegal:
            raise ValueError(
                f"load_world rejected non-world keys {sorted(illegal)} — "
                f"evidence/verifier state is not mutable via the control API."
            )
        with self._lock:
            _deep_update(self.world, copy.deepcopy(updates))

    def set_rules(self, observe: list[dict] | None = None,
                  action: list[dict] | None = None) -> None:
        self.rules.set(observe or [], action or [])

    # -- request dispatch (agent-facing; no token) ---------------------------

    def request(self, method: str, path: str, form: dict | None = None,
                query: str = "") -> tuple[int, str, bytes]:
        """Returns (status, content_type, body). Pure-Python, no socket."""
        method = method.upper()
        status = self.rules.intercept(method, path)
        if status is not None:
            return status, "text/html", _page("Blocked", "<p>Blocked.</p>")
        if method == "GET":
            status, ctype, body = self._get(path, query)
        elif method == "POST":
            status, ctype, body = self._post(path, form or {})
        else:
            status, ctype, body = 405, "text/html", _page("Error", "<p>405</p>")
        if ctype == "text/html":
            body = self.rules.filter_html(
                body.decode("utf-8", "replace")).encode()
        return status, ctype, body

    # -- GET routing ----------------------------------------------------------

    def _get(self, path: str, query: str) -> tuple[int, str, bytes]:
        self._track(path)
        if path == "/state":
            payload = {"world": self.world, "evidence": self.evidence}
            return 200, "application/json", json.dumps(payload).encode()
        if path == "/":
            items = "".join(
                f"<li><a href='{r['href']}'>{r['title']}</a></li>"
                for r in _index_links(self.world))
            body = (f"<ul>{items}</ul>"
                    f"<p>Top headline: {self.world['headline']}</p>")
            return 200, "text/html", _page("Index", body)
        if path == "/form":
            fields = "<br>".join(
                f"<label>{f['label']} <input name='{f['name']}'></label>"
                for f in self.world["form_fields"])
            body = (f"<form method='post' action='/submit'>{fields}<br>"
                    f"<button type='submit'>Submit</button></form>")
            return 200, "text/html", _page("Form", body)
        if path == "/login":
            c = self.world["creds"]
            body = (f"<p>Demo credentials: {c['user']} / {c['pass']}</p>"
                    f"<form method='post' action='/do_login'>"
                    f"<label>User <input name='user'></label><br>"
                    f"<label>Pass <input name='pass' type='password'></label><br>"
                    f"<button type='submit'>Log in</button></form>")
            return 200, "text/html", _page("Login", body)
        if path == "/dashboard":
            if not self.evidence["logged_in"]:
                return 403, "text/html", _page("Dashboard", "<p>Not logged in.</p>")
            return 200, "text/html", _page(
                "Dashboard", "<p>Welcome back! You are logged in.</p>")
        if path == "/long":
            paras = "".join(
                f"<p>Filler paragraph {i} about nothing at all.</p>"
                for i in range(40))
            body = f"{paras}<p id='code'>Bottom code: {self.world['longpage_code']}</p>"
            return 200, "text/html", _page("Long page", body)
        if path.startswith("/docs/"):
            n = path.rsplit("/", 1)[-1]
            doc = self.world["docs"].get(n)
            if doc:
                text = doc["text"]
                if "secret_word" in doc:
                    text = text.format(secret_word=doc["secret_word"])
                elif "api_code" in doc:
                    text = text.format(api_code=doc["api_code"])
                return 200, "text/html", _page(doc["title"], f"<p>{text}</p>")
        if path == "/search":
            q = (parse_qs(query).get("q") or [""])[0]
            items = "".join(
                f"<li><a href='{r['href']}'>{r['title']}</a></li>"
                for r in self.world["search_results"])
            body = (f"<p>{len(self.world['search_results'])} results for "
                    f"'{q}'</p><ol>{items}</ol>")
            return 200, "text/html", _page(f"Search: {q}", body)
        return 404, "text/html", _page("Not found", "<p>404</p>")

    # -- POST routing ----------------------------------------------------------

    def _post(self, path: str, fields: dict) -> tuple[int, str, bytes]:
        self._track(path)
        if path == "/submit":
            required = [f["name"] for f in self.world["form_fields"]]
            if all(fields.get(k) for k in required):
                self.evidence["form"] = dict(fields)
                self.evidence["form_submissions"] += 1
                return 200, "text/html", _page(
                    "Thanks!", "<p>Form submitted successfully.</p>")
            self.evidence["form_errors"] += 1
            msg = self.world["form_error_message"]
            self.evidence["last_form_error"] = msg
            return 200, "text/html", _page("Form error", f"<p>{msg}</p>")
        if path == "/do_login":
            self.evidence["logins"] += 1
            c = self.world["creds"]
            if (fields.get("user") == c["user"]
                    and fields.get("pass") == c["pass"]):
                self.evidence["logged_in"] = True
                return 302, "text/html", b""
            return 200, "text/html", _page("Login failed", "<p>Wrong credentials.</p>")
        return 404, "text/html", _page("Not found", "<p>404</p>")

    def _track(self, path: str) -> None:
        if path not in _UNPROTECTED_PATHS and not path.startswith("/control"):
            self.evidence["visited"].append(path)


def _index_links(world: dict) -> list[dict]:
    """Index-page nav (static structure, distinct from /search results)."""
    return [
        {"title": "Form page", "href": "/form"},
        {"title": "Search: pricing", "href": "/search?q=pricing"},
        {"title": "Docs 1", "href": "/docs/1"},
        {"title": "Docs 2", "href": "/docs/2"},
        {"title": "Docs 3", "href": "/docs/3"},
        {"title": "Login", "href": "/login"},
        {"title": "Long page", "href": "/long"},
    ]


def _deep_update(base: dict, updates: dict) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def _page(title: str, body: str) -> bytes:
    return (f"<html><head><title>{title}</title></head>{STYLE}"
            f"<body><h1>{title}</h1>{body}</body></html>").encode()


# ---------------------------------------------------------------------------
# HTTP wrapper — thin over EvalSite.request(); the token gates /control only.
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    @property
    def site(self) -> EvalSite:
        return self.server.eval_site

    def _authorized(self) -> bool:
        return self.headers.get("X-Run-Token") == self.site.run_token

    def do_GET(self):
        url = urlparse(self.path)
        self._send(*self.site.request("GET", url.path, query=url.query))

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        if path.startswith("/control"):
            if not self._authorized():
                return self._send(403, "application/json",
                                  b'{"error": "invalid or missing X-Run-Token"}')
            try:
                payload = json.loads(raw) if raw else {}
                status, body = self._control(path, payload)
                return self._send(status, "application/json",
                                  json.dumps(body).encode())
            except (ValueError, RuleError) as exc:
                return self._send(400, "application/json",
                                  json.dumps({"error": str(exc)}).encode())
        fields = {k: (v[0] if v else "") for k, v in parse_qs(raw).items()}
        self._send(*self.site.request("POST", path, form=fields))

    def _control(self, path: str, payload: dict) -> tuple[int, dict]:
        if path == "/control/reset":
            self.site.control_reset()
            return 200, {"ok": True, "reset": "full"}
        if path == "/control/load_world":
            self.site.load_world_updates(payload.get("updates") or {})
            return 200, {"ok": True,
                         "world": self.site.world}
        if path == "/control/rules":
            self.site.set_rules(payload.get("observe"),
                                payload.get("action"))
            return 200, {"ok": True}
        if path == "/control/state":
            return 200, {"world": self.site.world,
                         "evidence": self.site.evidence}
        return 404, {"error": f"unknown control path {path}"}

    def _send(self, status: int, ctype: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        if body:
            self.wfile.write(body)


def start_site(port: int = 0, run_token: str | None = None,
               base_world: dict | None = None) -> tuple[EvalSite, callable]:
    """Start one isolated site instance. port=0 → ephemeral (concurrent runs
    never share STATE, because there is no module-global STATE anymore).
    Returns (site, stop); `site` carries the token and control helpers."""
    site = EvalSite(run_token=run_token, base_world=base_world)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.eval_site = site
    site.port = server.server_address[1]
    site.base_url = f"http://127.0.0.1:{site.port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop():
        # shutdown() stops serve_forever; server_close() releases the
        # socket — without it every eval run leaks the port.
        server.shutdown()
        server.server_close()

    return site, stop
