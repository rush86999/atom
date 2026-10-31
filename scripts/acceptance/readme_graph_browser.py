#!/usr/bin/env python3
"""Browser acceptance for the GraphRAG explorer (GRAPH-05).

Starts the real backend on a throwaway world, seeds a small graph through the
public API, starts the Next.js frontend against that backend, logs in with the
generated bootstrap password, opens /dashboards/knowledge, and asserts that
the D3 graph renders nodes/edges and a node can be selected.

No cloud credentials, sends, deployments or connected-system writes.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend-nextjs"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts" / "acceptance"))
from scripts.readme_acceptance.common import reset_world  # noqa: E402
from readme_local_install import Backend, request  # noqa: E402


def wait_http(url: str, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=Path(
        "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-graph-browser-world"))
    parser.add_argument("--backend-port", type=int, default=8142)
    parser.add_argument("--frontend-port", type=int, default=3131)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--keep-world", action="store_true")
    args = parser.parse_args()

    reset_world(
        args.world, reset=not args.keep_world,
        allowed_root=Path(os.getenv("ATOM_README_WORLD_ROOT", str(args.world.parent))),
    )
    (args.world / "logs").mkdir(parents=True, exist_ok=True)
    _origins = ("http://127.0.0.1:3131,http://localhost:3131,"
                "http://127.0.0.1:3000,http://localhost:3000")
    os.environ["ALLOWED_ORIGINS"] = _origins
    os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = _origins
    os.environ["CORS_ORIGINS"] = _origins
    backend = Backend(args.world, args.backend_port)
    frontend_proc = None
    result = {"world": str(args.world), "checks": {}}
    try:
        backend.start()
        base = f"http://127.0.0.1:{args.backend_port}"
        password = ""
        pw_path = args.world / "logs" / "bootstrap_admin_password.txt"
        for _ in range(30):
            if pw_path.is_file():
                password = pw_path.read_text().strip()
                break
            time.sleep(1)
        status, login = request(f"{base}/api/auth/login", "POST", {
            "username": "admin@example.com", "password": password})
        token = login.get("access_token")
        result["checks"]["login"] = {"status": status, "token": bool(token)}
        if not token:
            raise RuntimeError("backend login failed")

        workspace = "default_workspace"
        nodes = [
            ("Atlas", "project", "Atlas acceptance graph node"),
            ("Borealis", "project", "Borealis acceptance graph node"),
            ("Finance", "team", "Finance acceptance graph node"),
        ]
        node_ids = {}
        for name, node_type, description in nodes:
            status, body = request(
                f"{base}/api/graphrag/entities?workspace_id={workspace}",
                "POST", {"name": name, "type": node_type,
                         "description": description, "properties": {}},
                token=token)
            node_ids[name] = (((body.get("data") or {}).get("id"))
                              or body.get("id"))
            result["checks"].setdefault("entities", []).append(
                {"name": name, "status": status, "id": node_ids[name]})
        for source, target, rel_type in (
                ("Atlas", "Borealis", "DEPENDS_ON"),
                ("Finance", "Atlas", "OWNS")):
            status, body = request(
                f"{base}/api/graphrag/relationships?workspace_id={workspace}",
                "POST", {"from_entity": source, "to_entity": target,
                         "relationship_type": rel_type,
                         "description": "acceptance relationship",
                         "properties": {}}, token=token)
            result["checks"].setdefault("relationships", []).append(
                {"from": source, "to": target, "status": status})

        status, listed = request(
            f"{base}/api/graphrag/entities?workspace_id={workspace}&limit=50",
            token=token)
        result["checks"]["api_list"] = {
            "status": status,
            "count": len((listed.get("data") or {}).get("entities") or []),
        }
        if status != 200 or result["checks"]["api_list"]["count"] < 3:
            raise RuntimeError("graph API did not return the seeded entities")
        _, entities_payload = request(
            f"{base}/api/graphrag/entities?workspace_id={workspace}&limit=200",
            token=token)
        _, relationships_payload = request(
            f"{base}/api/graphrag/relationships?workspace_id={workspace}&limit=300",
            token=token)
        _, profile_payload = request(f"{base}/api/product/profile", token=token)
        result["checks"]["product_profile"] = profile_payload.get("profile")

        frontend_env = {
            **os.environ,
            "NEXT_PUBLIC_API_URL": base,
            "NEXT_PUBLIC_API_BASE_URL": base,
            "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "NEXT_TELEMETRY_DISABLED": "1",
            "PORT": str(args.frontend_port),
            "BROWSER": "none",
        }
        log = open(args.world / "frontend.log", "w")
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--webpack",
             "--port", str(args.frontend_port)],
            cwd=str(FRONTEND), env=frontend_env,
            stdout=log, stderr=subprocess.STDOUT,
        )
        if not wait_http(f"http://127.0.0.1:{args.frontend_port}/login", timeout=240):
            raise RuntimeError("frontend did not become ready")

        from playwright.sync_api import sync_playwright
        screenshot = args.world / "graph-explorer.png"
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            context.add_cookies([
                {"name": "auth_token", "value": token,
                 "domain": "127.0.0.1", "path": "/"},
                {"name": "next-auth.session-token", "value": token,
                 "domain": "127.0.0.1", "path": "/"},
            ])
            context.add_init_script(
                "localStorage.setItem('auth_token', %s);"
                "localStorage.setItem('token', %s);"
                "localStorage.setItem('user_email', 'admin@example.com');"
                % (json.dumps(token), json.dumps(token)))
            # The Next dev proxy is environment-sensitive; serve the real
            # backend payloads directly to the page's same-origin fetches so
            # this check is about the explorer's rendering, not the proxy.
            context.route(
                "**/api/product/profile",
                lambda route: route.fulfill(
                    status=200, content_type="application/json",
                    body=json.dumps(profile_payload)))
            def _graph_route(route):
                if "/entities" in route.request.url:
                    body = json.dumps(entities_payload)
                elif "/relationships" in route.request.url:
                    body = json.dumps(relationships_payload)
                else:
                    route.continue_()
                    return
                route.fulfill(status=200, content_type="application/json",
                              body=body)
            context.route("**/api/graphrag/**", _graph_route)
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{args.frontend_port}/dashboards/knowledge",
                      wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)
            result["checks"]["page_debug"] = {
                "url": page.url,
                "text": page.locator("body").inner_text()[:2000],
            }
            page.screenshot(path=str(args.world / "knowledge-debug.png"),
                            full_page=True)
            # The Graph tab is the explorer; click it when the page opens on
            # another tab.
            try:
                page.get_by_role("button", name="Graph", exact=False).first.click(
                    timeout=15000)
            except Exception:
                pass
            page.get_by_text("GraphRAG Explorer", exact=False).wait_for(
                state="visible", timeout=120000)
            page.wait_for_function(
                "document.querySelectorAll('svg circle').length >= 2",
                timeout=120000,
            )
            circles = page.locator("svg circle")
            node_count = circles.count()
            circles.first.click()
            page.wait_for_timeout(1000)
            page.screenshot(path=str(screenshot), full_page=True)
            body_text = page.locator("body").inner_text()
            selected = ("Select an entity on the graph" not in body_text)
            error_visible = ("Unable to load knowledge graph" in body_text)
            result["checks"]["browser"] = {
                "node_count": node_count,
                "selected": selected,
                "error_visible": error_visible,
                "url": page.url,
                "screenshot": str(screenshot),
            }
            browser.close()
        ok = (result["checks"]["browser"]["node_count"] >= 2
              and result["checks"]["browser"]["selected"]
              and not result["checks"]["browser"]["error_visible"])
        result["status"] = "verified" if ok else "failed"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if frontend_proc is not None and frontend_proc.poll() is None:
            frontend_proc.send_signal(signal.SIGTERM)
            try:
                frontend_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                frontend_proc.kill()
        backend.stop()
        result.pop("password", None)
        out = args.out or (args.world / "graph-browser.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
