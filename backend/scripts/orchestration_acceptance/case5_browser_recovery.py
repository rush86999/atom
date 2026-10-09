#!/usr/bin/env python3
"""Case 5 (browser leg): provider failure then another message, through the
REAL frontend and the REAL backend, on an isolated world.

Owner directive (2026-10-06): run the existing isolated case-5 fixture
through the real frontend and backend — controlled provider failure →
truthful visible error → next message dispatches → provider restored →
successful reply → reload — and verify durable history, session continuity
and no duplicate effects at the DB/API layer (a mocked browser response
alone cannot establish backend persistence).

Isolation model (unchanged from the acceptance rig):
  * world built by run_isolated --snapshot-working-tree: the backend code
    is a hash-pinned export of THIS working tree (the frozen candidate),
    the DB is a per-run atom.db seeded from the scrubbed fixture — the
    live dev database is never opened;
  * the provider is the LOCAL SHIM (127.0.0.1, dedicated port). The
    credit-exhaustion envelope is the verbatim string the backend
    regression stubs — no real account is ever touched;
  * the frontend is the real one (`.preview-instance` symlink farm →
    current sources) started with NEXT_PUBLIC_API_URL at this backend.

Failure/recovery phases use TWO shim scripts (the failure marker would
otherwise echo inside later turns' conversation history and hijack their
replies): phase 1 serves the credit envelope for the marked turn, phase 2
(default only) is the restored provider. The shim process is swapped
between phases; the backend keeps running.

Usage:
  venv314/bin/python scripts/orchestration_acceptance/case5_browser_recovery.py \
      [--world case5_browser_1010] [--port 8031] [--fe-port 3131]
      [--shim-port 8097] [--results <path.json>] [--keep-stack]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("SECRET_KEY", uuid.uuid4().hex + uuid.uuid4().hex)

from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402

RESULTS: List[Dict[str, Any]] = []

# The verbatim credit-exhaustion envelope the backend regression stubs
# (backend/tests/test_chat_orchestrator.py,
#  test_credit_exhaustion_is_terminal_truthful_persisted). Serving the same
# string through the shim keeps one canonical failure shape across the
# in-process and browser legs.
CREDIT = (
    "I couldn't generate a response — every configured provider is "
    "out of credits (opencode-go). The last provider error: 402. "
    "Top up the provider balances in Settings → Providers, then ask "
    "again — retrying without a top-up will fail the same way.")
FAIL_MARKER = "credx-probe-7741"
DEFAULT_REPLY = ("Pangolin reply from the isolated provider shim — "
                 "request {NONCE}.")

T1_ASK = "Summarize what this canvas covers, in one sentence."
T2_ASK = ("Also — what machines does this quote mention? "
          f"(reference {FAIL_MARKER})")
T3_ASK = "Thanks. And what are the delivery terms in this quote?"
T4_ASK = "One more: repeat the payment terms."

COMPOSER = 'textarea[placeholder="Ask the agent to edit…"]'
SEND_BTN = 'button[aria-label="Send message"]'

# teardown registry (the phase-2 shim is swapped mid-run)
_CLEANUP: List[Any] = []


def record(case: str, checks: Dict[str, Any],
           notes: Optional[List[str]] = None,
           details: Optional[Dict[str, Any]] = None) -> bool:
    ok = bool(checks) and all(v is True for v in checks.values())
    RESULTS.append({"case": case, "status": "PASS" if ok else "FAIL",
                    "checks": checks, "notes": notes or [],
                    "details": details or {}})
    print(f"[{'PASS' if ok else 'FAIL'}] {case}")
    for k, v in checks.items():
        print(f"    {'✓' if v is True else '✗'} {k}: {v}")
    for n in (notes or []):
        print(f"    note: {n}")
    return ok


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def ensure_port_free(port: int) -> None:
    import socket
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise RuntimeError(
            f"port :{port} already in use — a stale listener would be "
            f"attributed to this run") from exc
    finally:
        probe.close()


def wait_port_free(port: int, deadline_s: float = 30.0) -> None:
    """Wait until launch_shim could rebind :port.

    The probe sets SO_REUSEADDR exactly like launch_shim's own bind check:
    without it, TIME_WAIT peers from the killed shim's accepted
    connections fail the bind for ~60s on macOS even though a new
    listener would start fine."""
    import socket
    end = time.time() + deadline_s
    while time.time() < end:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return
        except OSError:
            s.close()
            time.sleep(0.5)
    raise RuntimeError(f"port :{port} did not free after shim termination")


def write_shim_script(world: Path, name: str,
                      responses: List[Dict[str, str]], default: str) -> Path:
    p = world / name
    p.write_text(json.dumps({"responses": responses, "default": default},
                            indent=2))
    return p


class NetWatch:
    """Browser-side error/origin capture. Response BODIES are read via
    expect_response in send_turn() — reading resp.text() inside a sync-API
    event handler silently loses the event (observed 2026-10-06: turn 1
    rendered + persisted while the handler recorded nothing), so handlers
    here only collect strings."""

    def __init__(self, page: Any, be_port: int, fe_port: int):
        self.console_errors: List[str] = []
        self.page_errors: List[str] = []
        self.foreign: List[str] = []
        self.chat_posts: List[str] = []
        self.be_port = be_port
        page.on("request", self._on_request)
        page.on("response", lambda r: self._check_foreign(r.url))
        page.on("console", lambda m: self.console_errors.append(str(m.text)[:200])
                if m.type == "error" else None)
        page.on("pageerror", lambda e: self.page_errors.append(str(e)[:200]))

    def _on_request(self, req: Any) -> None:
        try:
            url = str(req.url)
            if req.method == "POST" and "/api/chat/message" in url:
                self.chat_posts.append(f"{time.strftime('%FT%T')} {url}")
        except Exception:
            return
        self._check_foreign(url)

    def _foreign(self, url: str) -> bool:
        low = str(url).lower()
        if not low.startswith("http"):
            return False
        return any(f":{p}/" in low or low.endswith(f":{p}")
                   for p in (3000, 8001, 8000))

    def _check_foreign(self, url: str) -> None:
        if self._foreign(url):
            self.foreign.append(str(url))


def overlay_state(page: Any) -> Dict[str, Any]:
    """Describe (and do not touch) any full-screen modal overlay.

    A failed turn opened one live (2026-10-06: a `fixed inset-0 z-50`
    backdrop intercepting pointer events over the composer after the
    truthful terminal error). The case must RECORD what opened and prove
    a user can dismiss it — not silently work around it."""
    return page.evaluate("""() => {
        const overlays = Array.from(
            document.querySelectorAll('div.fixed.inset-0.z-50, [role="dialog"]'));
        const real = overlays.filter(o => {
            const r = o.getBoundingClientRect();
            const s = getComputedStyle(o);
            return r.width > 200 && r.height > 100
                && s.display !== 'none' && s.visibility !== 'hidden';
        });
        return {count: real.length,
                texts: real.map(o => (o.innerText || ''))};
    }""")


def dismiss_overlay(page: Any) -> Dict[str, Any]:
    """Dismiss a blocking overlay the way a user would: Escape first,
    then an explicit close/discard button if present. Returns what was
    found and whether it cleared."""
    found = overlay_state(page)
    if not found["count"]:
        return {"found": False, "cleared": True, "texts": []}
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    if not overlay_state(page)["count"]:
        return {"found": True, "cleared": True, "how": "Escape",
                "texts": found["texts"]}
    for label in ("Close", "Dismiss", "OK", "Cancel", "×"):
        try:
            btn = page.locator(
                f'div.fixed.inset-0.z-50 button:has-text("{label}"), '
                f'[role="dialog"] button:has-text("{label}")').first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=5000)
                page.wait_for_timeout(400)
                if not overlay_state(page)["count"]:
                    return {"found": True, "cleared": True,
                            "how": f"button:{label}", "texts": found["texts"]}
        except Exception:
            continue
    return {"found": True, "cleared": False, "how": "failed",
            "texts": found["texts"]}


def send_turn(page: Any, text: str, via: str,
              timeout_ms: int = 150_000) -> Dict[str, Any]:
    """Submit `text` through the real composer and return the POST
    /api/chat/message response body (plus status). `via` is recorded in
    the result: 'button' clicks Send, 'enter' presses Enter — the two
    paths the release suite requires recorded separately."""
    overlay = dismiss_overlay(page)
    with page.expect_response(
            lambda r: "/api/chat/message" in r.url
            and r.request.method == "POST",
            timeout=timeout_ms) as ri:
        page.fill(COMPOSER, text)
        if via == "button":
            page.click(SEND_BTN)
        else:
            page.press(COMPOSER, "Enter")
    resp = ri.value
    entry: Dict[str, Any] = {"via": via, "t": time.strftime("%FT%T"),
                             "status": resp.status,
                             "overlay_dismissed": overlay}
    try:
        body = resp.json()
        entry.update({
            "session_id": body.get("session_id"),
            "execution_id": body.get("execution_id"),
            "success": body.get("success"),
            "error_code": body.get("error_code"),
            # informational: under CHAT_FINALIZATION_M1/M2 the finalizer
            # (core/finalization.py) rebuilds the failure message from the
            # execution record and keeps error_code but drops the
            # failure_reason/recovery_url the ungated reply-assembly path
            # sets — a divergence recorded in the case findings, not a
            # driver failure
            "failure_reason": body.get("failure_reason"),
            "recovery_url": body.get("recovery_url"),
            "message_head": str(body.get("message") or "")[:400],
        })
    except Exception as exc:
        entry["body_error"] = f"{type(exc).__name__}: {exc}"
    return entry


def seed_session(page: Any, fe_base: str, token: str) -> None:
    """The app's own client-side session (mirrors backendAuth.ts
    persistBackendToken + middleware.ts cookies) — browser_verify's exact
    seeding, kept identical so the two rigs stay comparable."""
    page.add_init_script(
        "(() => {"
        f"  const token = {json.dumps(token)};"
        "  try {"
        "    localStorage.setItem('auth_token', token);"
        "    localStorage.setItem('token', token);"
        "    localStorage.setItem('user_email', 'admin@example.com');"
        "    localStorage.removeItem('atom_explicit_logout');"
        "  } catch (e) {}"
        "})();"
    )
    page.goto(f"{fe_base}/login", wait_until="domcontentloaded")
    page.evaluate(
        "([t]) => {"
        "  document.cookie = 'auth_token=' + t + '; path=/; max-age=86400; SameSite=Lax';"
        "  document.cookie = 'next-auth.session-token=' + t + '; path=/; max-age=86400; SameSite=Lax';"
        "}",
        arg=[token])


def panel_text(page: Any) -> str:
    return page.evaluate("() => document.body.innerText || ''")


def wait_text(page: Any, needle: str, timeout_s: float = 150.0) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        if needle in panel_text(page):
            return True
        time.sleep(1.0)
    return False


def db_rows(db_path: str, conversation: str) -> List[Dict[str, Any]]:
    import sqlite3
    # plain connect, SELECTs only: a file:?mode=ro URI silently read a
    # pre-WAL snapshot on this rig (rows existed but came back empty)
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content, metadata_json FROM "
            "chat_messages WHERE conversation_id=? ORDER BY created_at, rowid",
            (conversation,)).fetchall()
    finally:
        con.close()
    out = []
    for role, content, meta in rows:
        try:
            m = json.loads(meta) if meta else {}
        except Exception:
            m = {"_raw": str(meta)[:200]}
        out.append({"role": role, "content": str(content or ""), "meta": m})
    return out


def history_api(be_base: str, token: str, sid: str) -> List[Dict[str, Any]]:
    import httpx
    r = httpx.get(f"{be_base}/api/chat/history/{sid}",
                  headers={"Authorization": f"Bearer {token}"},
                  timeout=30, trust_env=False)
    doc = r.json()
    return [m for m in (doc.get("messages") or []) if m.get("role") == "assistant"]


def canvas_update_count(db_path: str, canvas_id: str) -> int:
    import sqlite3
    con = sqlite3.connect(db_path)
    try:
        n = con.execute(
            "SELECT count(*) FROM canvas_audit WHERE canvas_id=? AND "
            "action_type='update'", (canvas_id,)).fetchone()[0]
    finally:
        con.close()
    return n


def _code_identity() -> Dict[str, str]:
    """Identify the exact code under test: the driver runs against a world
    exported from THIS working tree, so record the commit + dirty state +
    driver hash with every run. A trial without code identity cannot be
    attributed to a candidate."""
    repo = BACKEND.parent

    def _run(*argv: str) -> str:
        try:
            out = subprocess.run(list(argv), cwd=str(repo),
                                 capture_output=True, text=True,
                                 timeout=15).stdout.strip()
            return out or "unknown"
        except Exception:
            return "unknown"

    try:
        driver_sha = sha256_file(Path(__file__))
    except Exception:
        driver_sha = "unknown"
    return {
        "commit": _run("git", "rev-parse", "HEAD"),
        "dirty_tracked": _run("git", "status", "--short", "--untracked-files=no"),
        "driver_sha256": driver_sha,
        "config": ("ATOM_TASK_LIFECYCLE_ENABLED=1, CHAT_FINALIZATION_M1=1, "
                   "CHAT_FINALIZATION_M2=1; provider=model shim only"),
    }


def terminate_proc(proc: Any) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def start_frontend_copy(backend_port: int, fe_port: int,
                        world_dir: Path) -> Any:
    """Run the real frontend from a REAL DIRECTORY COPY, not the symlink
    farm.

    Why: the `.preview-instance` symlink farm (preview_stack's mechanism)
    fails to REGISTER DYNAMIC ROUTES under Next 16 — observed live
    2026-10-06: /chat, /canvas and /login served 200 from the farm while
    EVERY dynamic route (/canvas/<id>, /documents/<id>) 404'd, and the
    same /canvas/<id> path returned 200 from the repo's own dev server.
    A case-5 run needs pages/canvas/[id], so the farm cannot host it. The
    copy lives INSIDE the world (deleted with it), excludes caches and
    .env.local (the farm excludes .env.local too — never inherit the dev
    stack's API URL), and symlinks only node_modules.
    """
    import shutil
    fe_src = BACKEND.parent / "frontend-nextjs"
    dst = world_dir / "frontend_snapshot"
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    print(f"[frontend] copying {fe_src} -> {dst} (excluding caches)")
    subprocess.run(
        ["rsync", "-a",
         "--exclude", "node_modules",
         "--exclude", ".next",
         "--exclude", ".next-preview",
         "--exclude", ".preview-instance",
         "--exclude", ".env.local",
         str(fe_src) + "/", str(dst) + "/"],
        check=True)
    os.symlink(str(fe_src / "node_modules"), str(dst / "node_modules"))
    env = dict(os.environ)
    env.update({
        "NEXT_PUBLIC_API_URL": f"http://localhost:{backend_port}",
        "PYTHON_API_SERVICE_BASE_URL": f"http://localhost:{backend_port}",
        "NEXTAUTH_URL": f"http://localhost:{fe_port}",
        "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
        "NODE_OPTIONS": "--max-old-space-size=4096",
    })
    log = (world_dir / "preview_frontend.log").open("ab")
    proc = subprocess.Popen(
        ["node", "node_modules/next/dist/bin/next", "dev", "--webpack",
         "-p", str(fe_port)],
        cwd=str(dst), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True)
    import httpx
    end = time.time() + 300
    while time.time() < end:
        if proc.poll() is not None:
            print(f"[frontend] exited early; see "
                  f"{world_dir / 'preview_frontend.log'}", file=sys.stderr)
            return None
        try:
            r = httpx.get(f"http://127.0.0.1:{fe_port}/login", timeout=5,
                          trust_env=False)
            if r.status_code == 200:
                # dynamic-route registration is the thing that broke on the
                # farm — prove it on THIS instance before trusting it
                probe = httpx.get(
                    f"http://127.0.0.1:{fe_port}/canvas/"
                    f"00000000-0000-4000-8000-000000000000",
                    cookies={"auth_token": "probe"}, timeout=60,
                    trust_env=False)
                if probe.status_code == 200:
                    return proc
                print(f"[frontend] dynamic-route probe returned "
                      f"{probe.status_code} (need 200) — not a usable "
                      f"frontend", file=sys.stderr)
                return None
        except Exception:
            pass
        time.sleep(3)
    print("[frontend] did not answer /login in 300s", file=sys.stderr)
    return proc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="case5_browser_1010")
    ap.add_argument("--port", type=int, default=8031)
    ap.add_argument("--fe-port", type=int, default=3131)
    ap.add_argument("--shim-port", type=int, default=8097)
    ap.add_argument("--results", default="")
    ap.add_argument("--keep-stack", action="store_true")
    args = ap.parse_args()

    world_dir = BACKEND / "data" / "acceptance_worlds" / args.world

    # ---- 1. world (built once; carries THIS working tree = candidate) ----
    if not (world_dir / "MANIFEST.json").exists():
        print(f"[world] building {args.world} from the working tree "
              f"(one-time; snapshot+freeze takes a few minutes)")
        subprocess.run(
            [str(R.VENV_PY),
             str(BACKEND / "scripts" / "orchestration_acceptance" /
                 "run_isolated.py"),
             "--name", args.world, "--rebuild-world",
             "--snapshot-working-tree"],
            check=False, cwd=str(BACKEND))
        if not (world_dir / "fixture" / "atom.db").exists():
            print("[world] build did not produce fixture/atom.db",
                  file=sys.stderr)
            return 2

    ensure_port_free(args.shim_port)
    ensure_port_free(args.port)
    ensure_port_free(args.fe_port)

    # ---- 2. shim phase 1: the broken provider ----
    shim_script_1 = write_shim_script(
        world_dir, "case5_shim_phase1.json",
        [{"match": FAIL_MARKER, "response": CREDIT}], DEFAULT_REPLY)
    shim_capture = world_dir / "case5_shim_capture.jsonl"
    shim1 = R.launch_shim(shim_script_1, args.shim_port, capture=shim_capture)
    _CLEANUP.append(shim1)
    print(f"[shim] phase-1 pid {shim1.pid} on :{args.shim_port} "
          f"(credit entry + default)")

    # CORS for the isolated frontend origin must ride the server env
    # (SERVER_ENV_WHITELIST passthrough — see run_isolated.py).
    os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = (
        f"http://localhost:{args.fe_port},http://127.0.0.1:{args.fe_port}")
    os.environ["ALLOWED_HOSTS"] = (
        f"localhost,127.0.0.1,localhost:{args.port},localhost:{args.fe_port}")

    # ---- 3. backend (gate flags: M1+M2+lifecycle, like finish_line) ----
    R.launch_server.gate = True
    proc = R.launch_server(args.port, world_dir, provider_shim=True,
                           shim_port=args.shim_port)
    run_dir = R.launch_server.last_run_dir
    db_path = str(run_dir / "data" / "atom.db")
    print(f"[stack] backend :{args.port} pid {proc.pid} db={db_path}")

    # ---- 4. seed admin + canvas via the app's own model path ----
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    from core.database import get_db_session
    from core.models import Canvas, CanvasAudit, User
    from core.admin_bootstrap import ensure_admin_user
    ensure_admin_user()
    canvas_content = json.dumps({
        "to": "steve@example.com", "cc": "", "subject": "Machinery quote",
        "body": ("Hi Steve,<br><br>Quote validity: 15 days.<br><br>"
                 "Payment terms: net 30.<br><br>Warranty: 12 months.<br>"
                 "<br>Delivery: 2 weeks.<br><br>Regards,")})
    with get_db_session() as db:
        user = db.query(User).filter(User.email == "admin@example.com").first()
        user_id = str(user.id)
        canvas_id = str(uuid.uuid4())
        db.add(Canvas(id=canvas_id, tenant_id="default",
                      workspace_id="default", created_by=user_id,
                      name="Case-5 canvas", canvas_type="email",
                      content=canvas_content, status="active"))
        db.add(CanvasAudit(canvas_id=canvas_id, tenant_id="default",
                           action_type="create", canvas_type="email",
                           user_id=user_id,
                           details_json={"content": json.loads(canvas_content)}))
        db.commit()

    from scripts.workbook_read_replay import mint_token
    token, uid = mint_token()
    assert token and uid == user_id, f"token mint failed ({uid} != {user_id})"

    # ---- 5. frontend (real sources via a directory copy in the world;
    #         the symlink farm 404s dynamic routes — see the function) ----
    fe_proc = start_frontend_copy(args.port, args.fe_port, world_dir)
    if not fe_proc:
        print("[stack] frontend failed to start", file=sys.stderr)
        return 3
    fe_pid = fe_proc.pid
    fe_base = f"http://localhost:{args.fe_port}"
    be_base = f"http://127.0.0.1:{args.port}"
    print(f"[stack] frontend {fe_base} pid {fe_pid}")

    db_identity = sha256_file(Path(db_path))
    audits_before = canvas_update_count(db_path, canvas_id)

    class _W:  # minimal handle for the browser-leg helpers
        pass
    wh = _W()
    wh.db_path = db_path
    wh.canvas_id = canvas_id

    exit_code = 0
    try:
        run_browser_leg(args, wh, token, fe_base, be_base, db_identity,
                        audits_before, shim1, world_dir)
    except Exception as exc:  # noqa: BLE001 — the stack must come down
        import traceback
        print(f"[case5] driver error: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    finally:
        out = args.results or str(
            world_dir / f"case5_results_{time.strftime('%Y%m%d_%H%M%S')}.json")
        Path(out).write_text(json.dumps({
            "candidate": {
                "world": args.world,
                "db_sha256_start": db_identity,
                "backend_port": args.port, "backend_pid": proc.pid,
                "frontend_port": args.fe_port, "frontend_pid": fe_pid,
                "shim_port": args.shim_port, "canvas_id": canvas_id,
                "user_id": user_id,
                "code": _code_identity(),
            },
            "results": RESULTS,
        }, indent=2))
        print(f"[case5] results -> {out}")
        if not args.keep_stack:
            print("[stack] tearing down")
            for p in _CLEANUP:
                terminate_proc(p)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
            try:
                os.kill(fe_pid, signal.SIGTERM)
            except Exception:
                pass
    return exit_code


def run_browser_leg(args: argparse.Namespace, wh: Any, token: str,
                    fe_base: str, be_base: str, db_identity: str,
                    audits_before: int, shim1: Any, world_dir: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        net = NetWatch(page, args.port, args.fe_port)
        seed_session(page, fe_base, token)

        # ---- canvas page (first hit compiles the route; be patient) ----
        try:
            page.goto(f"{fe_base}/canvas/{wh.canvas_id}",
                      wait_until="domcontentloaded", timeout=300_000)
            page.wait_for_selector(COMPOSER, timeout=240_000)
        except Exception as exc:
            shot = world_dir / "case5_page_failure.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
            except Exception:
                pass
            dump = {
                "error": f"{type(exc).__name__}: {exc}",
                "url": page.url,
                "panel_head": panel_text(page)[:600],
                "console_errors": net.console_errors[:20],
                "page_errors": net.page_errors[:10],
                "chat_posts": net.chat_posts,
                "screenshot": str(shot),
            }
            (world_dir / "case5_page_failure.json").write_text(
                json.dumps(dump, indent=2))
            print(f"[browser] canvas page failed — diagnostics at "
                  f"{world_dir / 'case5_page_failure.json'}", file=sys.stderr)
            raise
        print("[browser] canvas page up, composer present")

        # ================= TURN 1 — success, via Send BUTTON ==============
        t1 = send_turn(page, T1_ASK, "button")
        reply1 = wait_text(page, "Pangolin reply")
        record("T1_success_button", {
            "post_dispatched": "body_error" not in t1,
            "http_200": t1.get("status") == 200,
            "success_flag": t1.get("success") is True,
            "reply_visible": reply1 is True,
        }, details={"response": t1})
        sid = t1.get("session_id")
        if not sid or sid == "new":
            raise RuntimeError(
                f"no durable session id from turn 1 ({sid!r}) — cannot "
                f"bind DB checks")

        rows1 = db_rows(wh.db_path, sid)
        record("T1_db_persisted", {
            "user_row": any(r["role"] == "user" and T1_ASK[:30] in r["content"]
                            for r in rows1),
            "assistant_row": any(r["role"] == "assistant"
                                 and "Pangolin" in r["content"]
                                 for r in rows1),
        }, details={"rows": [(r["role"], r["content"][:60]) for r in rows1]})

        # ================= TURN 2 — controlled provider failure ===========
        # (Enter path — recorded separately from the button)
        t2 = send_turn(page, T2_ASK, "enter")
        credit_visible = wait_text(page, "out of credits")
        remedy_visible = wait_text(page, "Top up")
        static_lie = ("No AI provider configured. Add an API key"
                      in panel_text(page))
        record("T2_provider_failure_enter", {
            "post_dispatched": "body_error" not in t2,
            "http_200": t2.get("status") == 200,
            "terminal_success_false": t2.get("success") is False,
            "error_code": t2.get("error_code") == "no_llm_provider",
            "truthful_message_carried": "credit" in str(
                t2.get("message_head") or "").lower(),
            "error_visible_in_panel": credit_visible is True,
            "remedy_visible_in_panel": remedy_visible is True,
            "static_lie_not_shown": static_lie is False,
        }, details={"response": t2},
            notes=[f"failure_reason={t2.get('failure_reason')!r} "
                   f"recovery_url={t2.get('recovery_url')!r} — the M1/M2 "
                   f"finalizer rebuilds the message from the execution "
                   f"record and drops these machine fields (the ungated "
                   f"path sets provider_credits_exhausted + "
                   f"/settings/billing); recorded as a case finding, "
                   f"message text stays truthful"])

        rows2 = db_rows(wh.db_path, sid)
        asst2 = [r for r in rows2 if r["role"] == "assistant"
                 and "credits" in r["content"]]
        quality_error = bool(asst2) and any(
            (r["meta"].get("quality") == "error")
            or (r["meta"].get("error") is True)
            or "error" in str(r["meta"]).lower()
            for r in asst2)
        audits_after_fail = canvas_update_count(wh.db_path, wh.canvas_id)
        record("T2_db_terminal_persisted", {
            "assistant_row_persisted": bool(asst2),
            "quality_error_marked": quality_error is True,
            "no_canvas_effect": audits_after_fail == audits_before,
        }, details={"assistant_rows": [r["content"][:80] for r in asst2],
                    "meta": asst2[0]["meta"] if asst2 else None})

        # ================= TURN 3 — next message dispatches ===============
        # Sent while the provider is STILL broken (button path): the
        # composer must not be wedged by the failed turn.
        t3 = send_turn(page, T3_ASK, "button")
        again_failed_truthfully = (
            t3.get("success") is False
            and t3.get("error_code") == "no_llm_provider")
        ov = t3.get("overlay_dismissed") or {}
        record("T3_dispatch_after_failure_button", {
            "post_dispatched": "body_error" not in t3,
            "second_failure_truthful": again_failed_truthfully is True,
            "composer_reachable": ov.get("cleared", True) is True,
        }, details={"response": t3},
            notes=["sent while the provider was still broken — proves the "
                   "failed turn did not wedge the composer"]
                + ([f"post-failure overlay opened: {ov.get('texts')}; "
                    f"dismissed via {ov.get('how')}"]
                   if ov.get("found") else
                   ["no overlay after the failed turn"]))

        # ================= provider restored ==============================
        terminate_proc(shim1)
        _CLEANUP.remove(shim1)
        wait_port_free(args.shim_port)
        script2 = write_shim_script(world_dir, "case5_shim_phase2.json",
                                    [], DEFAULT_REPLY)
        shim2 = R.launch_shim(script2, args.shim_port, capture=None)
        _CLEANUP.append(shim2)
        print(f"[shim] phase-2 pid {shim2.pid} (default only — restored)")
        time.sleep(1.0)

        # ================= TURN 4 — recovered provider succeeds ===========
        # (Enter path again, so both input paths are proven post-recovery)
        t4 = send_turn(page, T4_ASK, "enter")
        # the nonce differs per request, so this is a NEW reply, not the
        # turn-1 bubble re-shown
        recovered = wait_text(page, "request shim-")
        record("T4_recovered_enter", {
            "post_dispatched": "body_error" not in t4,
            "success_flag": t4.get("success") is True,
            "reply_visible_after_recovery": recovered is True,
        }, details={"response": t4})

        # ================= RELOAD — durable history, no duplicates ========
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(COMPOSER, timeout=120_000)
        time.sleep(4)
        text = panel_text(page)
        record("reload_history", {
            "user_t1_once": text.count(T1_ASK) == 1,
            "user_t2_once": text.count(T2_ASK) == 1,
            "user_t3_once": text.count(T3_ASK) == 1,
            "user_t4_once": text.count(T4_ASK) == 1,
            "failure_error_visible": "out of credits" in text,
            "pangolin_replies_two": text.count("Pangolin reply") == 2,
        }, details={"counts": {
            "t1": text.count(T1_ASK), "t2": text.count(T2_ASK),
            "t3": text.count(T3_ASK), "t4": text.count(T4_ASK),
            "pangolin": text.count("Pangolin reply"),
            "credit": text.count("out of credits")}})

        # ================= DB + history API (assignment 3) =================
        rows = db_rows(wh.db_path, sid)
        users = [r for r in rows if r["role"] == "user"]
        assts = [r for r in rows if r["role"] == "assistant"]
        # execution ids live in the row metadata on this schema
        execs = {str(r["meta"].get("execution_id"))
                 for r in rows if r["meta"].get("execution_id")}
        hist = history_api(be_base, token, sid)
        record("durable_rows_and_api", {
            "user_rows_exactly_4": len(users) == 4,
            "assistant_rows_exactly_4": len(assts) == 4,
            "api_history_matches_db": len(hist) == 4,
            "no_canvas_effect_at_end":
                canvas_update_count(wh.db_path, wh.canvas_id)
                == audits_before,
        }, details={
            "db_roles": [r["role"] for r in rows],
            "api_texts": [str((h.get("response") or {}).get("message")
                              or h.get("content") or "")[:50] for h in hist],
            "execution_ids_in_meta": sorted(e[:12] for e in execs)})

        record("isolation", {
            "no_foreign_origin_hits": not net.foreign,
        }, details={"foreign": net.foreign[:5],
                    "console_errors": net.console_errors[:10],
                    "page_errors": net.page_errors[:10],
                    "db_sha256_start": db_identity})

        browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
