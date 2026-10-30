#!/usr/bin/env python3
"""Fresh-browser normal authentication and completed-assignment smoke.

There is NO session injection here: the browser starts with a fresh context,
uses the real /login form, signs out through the application control, verifies
the token is refused, and signs in again through the same form.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--artifact-sha256", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--headless", action="store_true", default=True)
    args = ap.parse_args()
    frontend = args.frontend.rstrip("/")
    api_base = args.api_base.rstrip("/")
    password = Path(args.password_file).read_text().strip()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def rec(name: str, ok: bool, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()

        page.goto(f"{frontend}/login", wait_until="domcontentloaded")
        rec("fresh_context_login_form",
            page.get_by_test_id("login-email-input").is_visible()
            and page.get_by_test_id("login-password-input").is_visible())
        page.get_by_test_id("login-email-input").fill(args.email)
        page.get_by_test_id("login-password-input").fill(password)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url("**/dashboard", timeout=30000)
        page.wait_for_timeout(1000)
        token = page.evaluate("() => localStorage.getItem('auth_token')")
        rec("normal_form_login", bool(token))
        rec("workspace_profile_visible",
            page.get_by_test_id("dashboard-user-profile-button").is_visible())
        page.screenshot(path=str(out / "signed-in-dashboard.png"), full_page=True)

        page.goto(f"{frontend}/assignments", wait_until="domcontentloaded")
        page.get_by_text(args.objective).first.wait_for(timeout=30000)
        page.screenshot(path=str(out / "signed-in-assignments.png"), full_page=True)
        rec("authenticated_workspace_access", True)
        page.get_by_role("button").filter(has_text=args.objective).first.click()
        detail = page.get_by_test_id("assignment-detail")
        detail.wait_for(state="visible", timeout=30000)
        detail.get_by_text("completed", exact=True).wait_for(timeout=30000)
        body = detail.inner_text()
        rec("existing_assignment_completed", "completed" in body)
        rec("artifact_listed", "Artifacts" in body)
        page.screenshot(path=str(out / "assignment-open.png"), full_page=True)

        response = context.request.get(
            f"{api_base}/api/assignments?include_terminal=true",
            headers={"Authorization": f"Bearer {token}"})
        rows = response.json()
        match = None
        for row in rows:
            assignment = row.get("assignment") or row
            if assignment.get("objective") == args.objective:
                match = row
                break
        if not match:
            raise SystemExit("REFUSED: assignment not visible through authenticated API")
        run_id = match.get("run_id")
        detail_resp = context.request.get(
            f"{api_base}/api/assignments/{run_id}",
            headers={"Authorization": f"Bearer {token}"})
        durable = detail_resp.json()["assignment"]
        documents = [d for d in durable.get("deliverables", [])
                     if d.get("kind") == "document" and d.get("artifact_path")]
        artifact = Path(documents[0]["artifact_path"])
        artifact_ok = artifact.is_file()
        artifact_hash = sha256(artifact) if artifact_ok else ""
        rec("artifact_present_and_openable", artifact_ok,
            {"path": str(artifact), "sha256": artifact_hash})
        if args.artifact_sha256:
            rec("artifact_hash_agrees", artifact_hash == args.artifact_sha256,
                {"expected": args.artifact_sha256, "actual": artifact_hash})

        page.goto(f"{frontend}/dashboard", wait_until="domcontentloaded")
        page.get_by_test_id("dashboard-logout-button").wait_for(timeout=30000)
        page.get_by_test_id("dashboard-logout-button").click()
        page.wait_for_timeout(1500)
        remaining = page.evaluate(
            "() => ({auth: localStorage.getItem('auth_token'),"
            " token: localStorage.getItem('token')})")
        rec("logout_clears_storage", not remaining.get("auth") and not remaining.get("token"),
            remaining)
        me = context.request.get(
            f"{api_base}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"})
        rec("old_token_refused_after_logout", me.status == 401,
            {"status": me.status})
        page.screenshot(path=str(out / "signed-out.png"), full_page=True)

        page.goto(f"{frontend}/login", wait_until="domcontentloaded")
        page.get_by_test_id("login-email-input").fill(args.email)
        page.get_by_test_id("login-password-input").fill(password)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url("**/dashboard", timeout=30000)
        page.wait_for_timeout(1000)
        rec("second_normal_form_login",
            bool(page.evaluate("() => localStorage.getItem('auth_token')")))
        page.goto(f"{frontend}/assignments", wait_until="domcontentloaded")
        page.get_by_text(args.objective).first.wait_for(timeout=30000)
        page.screenshot(path=str(out / "signed-in-again.png"), full_page=True)
        rec("second_session_workspace_access", True)

        browser.close()

    status = {"schema": "atom-assignment-release-auth-smoke-1",
              "status": "passed" if all(c["ok"] for c in checks) else "failed",
              "checks": checks,
              "session_injected": False,
              "normal_login_form_used": True,
              "screenshots": sorted(p.name for p in out.glob("*.png"))}
    (out / "auth-smoke.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    raise SystemExit(0 if status["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
