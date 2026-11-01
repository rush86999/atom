#!/usr/bin/env python3
"""Upload one campaign source through the ordinary Data surface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="http://127.0.0.1:3130")
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    password = Path(args.password_file).read_text().strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{args.frontend}/login", wait_until="domcontentloaded")
        page.get_by_test_id("login-email-input").fill("admin@example.com")
        page.get_by_test_id("login-password-input").fill(password)
        page.get_by_test_id("login-submit-button").click()
        page.wait_for_url("**/dashboard", timeout=45000)
        page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed', '1')")
        page.goto(f"{args.frontend}/documents", wait_until="domcontentloaded")
        page.set_input_files("#file-upload", args.file)
        page.get_by_text("Successfully uploaded", exact=False).wait_for(
            timeout=90000)
        print(json.dumps({"status": "uploaded", "file": str(args.file)}))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
