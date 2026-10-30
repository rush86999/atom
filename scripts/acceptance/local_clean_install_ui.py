#!/usr/bin/env python3
"""Browser acceptance for the documented local install.

This is an acceptance harness, not a product surface. It signs in through the
normal form, uploads a CSV through Data, starts a deterministic assignment
through the Assignments panel, downloads the artifact, and records console /
asset failures. Run it before and after a restart; the second run verifies the
same assignment and artifact remain available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def _read_password(path: Path) -> str:
    return path.read_text().strip()


def _login(page, base: str, email: str, password: str) -> None:
    page.goto(f"{base}/login", wait_until="domcontentloaded")
    page.get_by_test_id("login-email-input").fill(email)
    page.get_by_test_id("login-password-input").fill(password)
    page.get_by_test_id("login-submit-button").click()
    page.wait_for_url("**/dashboard", timeout=45000)
    # A fresh workspace opens the onboarding wizard. It is not a gate; the
    # host's own dismissal key hides it for this browser session.
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed', '1')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1000)


def _artifact_text(path: Path) -> str:
    try:
        import docx

        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    except Exception:
        return ""


def _download(page, out_dir: Path, stem: str) -> dict:
    button = page.locator('[data-testid^="assignment-download-"]').first
    button.wait_for(timeout=30000)
    with page.expect_download(timeout=30000) as info:
        button.click()
    download = info.value
    target = out_dir / f"{stem}-{download.suggested_filename}"
    download.save_as(str(target))
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "text": _artifact_text(target)[:2000],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--measure", required=True)
    ap.add_argument("--expected", required=True)
    ap.add_argument("--mode", choices=("create", "verify"), default="create")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    password = _read_password(Path(args.password_file))
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_assets: list[dict] = []
    failed_requests: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("console", lambda msg: console_errors.append(msg.text)
                if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        def on_response(response):
            url = response.url
            if response.status >= 400:
                failed_requests.append({"url": url, "status": response.status})
            if (response.status >= 400
                    and any(token in url for token in
                            ("/_next/static/", ".css", ".js", "/public/"))):
                failed_assets.append({"url": url, "status": response.status})

        page.on("response", on_response)
        _login(page, args.frontend, args.email, password)

        if args.mode == "create":
            page.goto(f"{args.frontend}/documents", wait_until="domcontentloaded")
            page.set_input_files("#file-upload", args.csv)
            page.get_by_text("Successfully uploaded", exact=False).wait_for(
                timeout=90000)

            page.goto(f"{args.frontend}/assignments", wait_until="domcontentloaded")
            page.get_by_test_id("assignment-source-select").wait_for(timeout=30000)
            page.get_by_text("Refresh data", exact=False).click()
            source = page.get_by_test_id("assignment-source-select")
            deadline = time.time() + 60
            selected = False
            while time.time() < deadline and not selected:
                options = source.locator("option").all_inner_texts()
                for option in options:
                    if Path(args.csv).name.lower() in option.lower():
                        source.select_option(label=option)
                        selected = True
                        break
                if not selected:
                    page.wait_for_timeout(1000)
            if not selected:
                raise SystemExit(
                    "REFUSED: uploaded CSV did not appear in the source picker: "
                    f"{source.locator('option').all_inner_texts()}")

            page.get_by_test_id("assignment-objective-input").fill(args.objective)
            page.get_by_test_id("assignment-measure-select").select_option(
                label=f"Sum {args.measure}")
            page.get_by_test_id("assignment-start-button").click()
            page.get_by_test_id("assignment-detail").wait_for(timeout=30000)
        else:
            page.goto(f"{args.frontend}/assignments", wait_until="domcontentloaded")
            page.get_by_text(args.objective, exact=False).first.click()
            page.get_by_test_id("assignment-detail").wait_for(timeout=30000)

        detail = page.get_by_test_id("assignment-detail")
        detail.get_by_text("completed", exact=True).wait_for(timeout=120000)
        result = detail.get_by_test_id("assignment-results").inner_text()
        if args.expected not in result:
            raise SystemExit(
                f"REFUSED: expected {args.expected!r} in result {result!r}")
        artifact = _download(page, out_dir, args.mode)
        page.screenshot(path=str(out_dir / f"{args.mode}-assignment.png"),
                        full_page=True)
        browser.close()

    record = {
        "schema": "atom-local-clean-install-ui-1",
        "status": "passed",
        "mode": args.mode,
        "frontend": args.frontend,
        "objective": args.objective,
        "expected": args.expected,
        "result_text": result,
        "artifact": artifact,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_assets": failed_assets,
        "failed_requests": failed_requests,
    }
    (out_dir / f"{args.mode}.json").write_text(
        json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if not page_errors and not failed_assets else 1


if __name__ == "__main__":
    raise SystemExit(main())
