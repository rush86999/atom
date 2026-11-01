#!/usr/bin/env python3
"""Ambiguous instruction -> targeted clarification -> bounded answer.

The agent holds document/email lessons that require `qualification=licensed`.
A request that names the quote/document protocol but omits qualification must
produce a question for that one field, not an invented value. The answer is
merged and the same turn is replayed.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def login(page, frontend: str, password: str) -> None:
    page.goto(f"{frontend}/login", wait_until="domcontentloaded")
    page.get_by_test_id("login-email-input").fill("admin@example.com")
    page.get_by_test_id("login-password-input").fill(password)
    page.get_by_test_id("login-submit-button").click()
    page.wait_for_url("**/dashboard", timeout=60000)
    page.evaluate("sessionStorage.setItem('atom.onboarding.dismissed', '1')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(800)


def send(page, text: str) -> dict:
    page.get_by_test_id("agent-chat-input").fill(text)
    with page.expect_response(
            lambda r: "/api/chat/message" in r.url, timeout=120000) as info:
        page.get_by_test_id("send-message-button").click()
    return info.value.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--request", default=(
        "Apply the campaign A quote document protocol to this sales quote at "
        "standard scope and prepare the document."))
    ap.add_argument("--answer", default="licensed")
    args = ap.parse_args()
    password = Path(args.password_file).read_text().strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        login(page, args.frontend, password)
        page.goto(f"{args.frontend}/chat?agent_id={args.agent_id}",
                  wait_until="domcontentloaded")
        page.get_by_test_id("agent-chat-input").wait_for(timeout=60000)
        first = send(page, args.request)
        text = page.get_by_test_id("message-list").inner_text()
        clarification = (first.get("metadata") or {}).get(
            "teaching_clarification") or {}
        required = [row.get("key") for row in
                    clarification.get("required_context") or []]
        asked = "qualification" in text.lower()
        invented = "licensed" in (first.get("message") or "").lower() and not asked

        second = send(page, args.answer)
        after = page.get_by_test_id("message-list").inner_text()
        page.screenshot(path=str(Path(args.out).with_suffix(".png")),
                        full_page=True)
        record = {
            "schema": "atom-teaching-clarification-1",
            "request": args.request,
            "first_message": first.get("message"),
            "required_context": required,
            "clarification_state": clarification.get("state"),
            "clarification_authority": clarification.get("authority"),
            "asked_qualification_in_visible_text": asked,
            "invented_qualification": invented,
            "first_outcome": first.get("outcome"),
            "answer": args.answer,
            "second_outcome": second.get("outcome"),
            "second_visible_contains_licensed": "licensed" in after.lower(),
            "clarification_meta": clarification,
            "sampled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        Path(args.out).write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record, indent=2)[:2000])
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
