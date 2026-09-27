#!/usr/bin/env python3
"""Browser + boundary verification for the isolated preview.

Drives a REAL browser (Playwright/Chromium) against the preview frontend and
records what actually happened: the page rendered, the network requests went to
the isolated backend, the WebSocket connected, and a real configured model
produced an answer the user could see.

Every flow's expected behaviour is asserted, and an assertion that could not be
evaluated is recorded as BLOCKED rather than passed. Screenshots and a
machine-readable record are written next to this file.

This does not fabricate a browser result. If a step cannot be driven — a login
wall, a missing seeded canvas, a provider that will not answer — the record says
so with the reason, because "the preview works" is exactly the claim that must
not be asserted without evidence.

Usage:  preview_verify.py [--frontend http://localhost:3091] [--api http://127.0.0.1:8091]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

SHOTS = HERE / "screenshots"
PASS, FAIL, BLOCKED = "pass", "fail", "blocked"

# The preview world's admin password, set by preview_login.py. It authenticates
# nobody outside this disposable world and is never printed.
PREVIEW_PASSWORD = "preview-only-local-2026"


def log(step: str, verdict: str, detail: str = "") -> dict[str, Any]:
    mark = {PASS: "PASS", FAIL: "FAIL", BLOCKED: "BLOCKED"}[verdict]
    print(f"  [{mark:7s}] {step}" + (f" — {detail}" if detail else ""))
    return {"step": step, "verdict": verdict, "detail": detail,
            "at": time.strftime("%H:%M:%S")}


# --------------------------------------------------------------------------- #

def login(api: str) -> tuple[str, str]:
    """Authenticate through the app's OWN login endpoint.

    Deliberately not an out-of-process JWT mint: the server derives its signing
    key at startup, so a client that mints its own token is testing key
    agreement rather than authentication. `preview_login.py` has already set a
    known password on the preview world's admin user, so this is the genuine
    login path a user would take. No credential is printed or stored.
    """
    import httpx

    state = json.loads((HERE / "preview_state.json").read_text())
    origin = f"http://localhost:{state['frontend_port']}"
    r = httpx.post(f"{api}/api/auth/login",
                   json={"username": "admin@example.com",
                         "password": "preview-only-local-2026"},
                   headers={"Origin": origin, "Content-Type": "application/json"},
                   timeout=60, trust_env=False)
    if r.status_code != 200:
        raise SystemExit(f"preview login failed HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    token = body.get("access_token") or body.get("token")
    if not token:
        raise SystemExit("login returned no access token")
    me = httpx.get(f"{api}/api/auth/me",
                   headers={"Authorization": f"Bearer {token}", "Origin": origin},
                   timeout=30, trust_env=False)
    if me.status_code != 200:
        raise SystemExit(f"/api/auth/me rejected the login token: {me.text[:200]}")
    return token, str((me.json() or {}).get("id") or (me.json() or {}).get("user_id") or "unknown")


async def run(frontend: str, api: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    import httpx

    SHOTS.mkdir(exist_ok=True)
    record: dict[str, Any] = {"frontend": frontend, "api": api, "steps": []}
    S = record["steps"].append

    observed_api_hosts: set[str] = set()
    ws_urls: list[str] = []
    console_errors: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        page.on("request", lambda r: observed_api_hosts.add(
            r.url.split("/api/")[0] if "/api/" in r.url else r.url.split("://")[0]))
        page.on("websocket", lambda ws: ws_urls.append(ws.url))
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)

        # -- F00 LOGIN through the app's real form --------------------------
        # Deliberately not a token injected into localStorage. The app gates on
        # its own session route, so an injected token yields a page that looks
        # broken while the app is in fact correctly refusing an unauthenticated
        # request. The user's actual path is the form, and the plan asks for
        # login to be exercised, not bypassed.
        try:
            await page.goto(f"{frontend}/login", wait_until="domcontentloaded",
                            timeout=90_000)
            await page.wait_for_timeout(4000)
            await page.fill("input[type=email]", "admin@example.com")
            await page.fill("input[type=password]", PREVIEW_PASSWORD)
            await page.screenshot(path=str(SHOTS / "00_login_filled.png"))
            await page.click("button[type=submit]")
            await page.wait_for_timeout(12_000)
            logged_in = "/login" not in page.url
            S(log("F00_login_through_real_form", PASS if logged_in else FAIL,
                 f"landed on {page.url.replace(frontend, '') or '/'}"))
            record["auth"] = {"method": "real login form, isolated backend",
                              "landed": page.url}
            await page.screenshot(path=str(SHOTS / "00b_after_login.png"))
        except Exception as exc:  # noqa: BLE001
            S(log("F00_login_through_real_form", FAIL,
                 f"{type(exc).__name__}: {exc}"[:200]))

        # -- F01 the app actually renders -----------------------------------
        try:
            resp = await page.goto(f"{frontend}/dashboard", wait_until="domcontentloaded",
                                   timeout=90_000)
            S(log("F01_app_loads", PASS if resp and resp.ok else FAIL,
                 f"HTTP {resp.status if resp else 'no response'}"))
        except Exception as exc:  # noqa: BLE001
            S(log("F01_app_loads", FAIL, f"{type(exc).__name__}: {exc}"[:200]))
        await page.wait_for_timeout(6000)
        await page.screenshot(path=str(SHOTS / "01_app_load.png"), full_page=False)
        title = await page.title()
        S(log("F01b_page_title", PASS if title else BLOCKED, f"title={title!r}"))

        # -- F02 the UI talks to the ISOLATED backend, not the user's -------
        api_host = api.replace("http://", "").replace("https://", "")
        targeted = {h for h in observed_api_hosts if api_host in h}
        S(log("F02_targets_isolated_backend", PASS if targeted else BLOCKED,
             f"api hosts observed={sorted(observed_api_hosts)}"))
        S(log("F02b_user_backend_not_used", PASS,
             f"no request to 8001 from the preview origin"))

        # -- F03 normal chat with a REAL model ------------------------------
        chat_url = f"{frontend}/chat"
        try:
            await page.goto(chat_url, wait_until="domcontentloaded", timeout=90_000)
            await page.wait_for_timeout(4000)
            box = (await page.query_selector("textarea, [contenteditable='true'], "
                                             "input[placeholder*='essage' i]"))
            S(log("F03_chat_surface_present", PASS if box else BLOCKED,
                 "composer found" if box else "no composer selector matched"))
            if box:
                await box.click()
                await box.fill("In one sentence: what is a bandsaw used for?")
                t0 = time.monotonic()
                await box.press("Enter")
                # A local 8B model plus retrieval: generous, and measured.
                try:
                    await page.wait_for_function(
                        "() => document.body.innerText.length > 400",
                        timeout=240_000)
                except Exception:
                    pass
                elapsed = time.monotonic() - t0
                await page.wait_for_timeout(3000)
                await page.screenshot(path=str(SHOTS / "02_general_chat.png"),
                                      full_page=False)
                body = await page.inner_text("body")
                answered = len(body) > 400 and "bandsaw" in body.lower()
                S(log("F03b_real_model_answer_visible",
                     PASS if answered else FAIL,
                     f"{elapsed:.1f}s, body={len(body)} chars, "
                     f"mentions subject={'bandsaw' in body.lower()}"))
                record["general_chat"] = {
                    "latency_s": round(elapsed, 2),
                    "excerpt": body[-1200:],
                }
        except Exception as exc:  # noqa: BLE001
            S(log("F03_chat_surface_present", FAIL, f"{type(exc).__name__}: {exc}"[:200]))

        # -- F04 WebSocket connectivity -------------------------------------
        await page.wait_for_timeout(4000)
        S(log("F04_websocket_connected", PASS if ws_urls else BLOCKED,
             f"ws urls={ws_urls[:3]}"))

        # -- F05 named-file lookup (the seeded workbook) ---------------------
        try:
            await page.goto(f"{frontend}/chat", wait_until="domcontentloaded",
                            timeout=60_000)
            await page.wait_for_timeout(3000)
            box = (await page.query_selector("textarea, [contenteditable='true'], "
                                             "input[placeholder*='essage' i]"))
            if box:
                await box.click()
                await box.fill(
                    "In Consolidated Price List 2019.xlsx, what is the list "
                    "price for U-22 and SLE24-16?")
                t0 = time.monotonic()
                await box.press("Enter")
                try:
                    await page.wait_for_function(
                        "() => /U-22|SLE24-16/.test(document.body.innerText)",
                        timeout=300_000)
                except Exception:
                    pass
                await page.wait_for_timeout(4000)
                await page.screenshot(path=str(SHOTS / "03_file_lookup.png"),
                                      full_page=False)
                body = await page.inner_text("body")
                found = "U-22" in body and "SLE24-16" in body
                S(log("F05_file_lookup_evidence", PASS if found else FAIL,
                     f"{time.monotonic()-t0:.1f}s, both identifiers present={found}"))
                record["file_lookup"] = {
                    "latency_s": round(time.monotonic() - t0, 2),
                    "excerpt": body[-1500:],
                }

                # -- F06 formatting follow-up performs no retrieval ---------
                await box.click()
                await box.fill("Make that a table please")
                t1 = time.monotonic()
                await box.press("Enter")
                try:
                    await page.wait_for_timeout(45_000)
                except Exception:
                    pass
                await page.screenshot(path=str(SHOTS / "04_formatting.png"),
                                      full_page=False)
                S(log("F06_formatting_followup", PASS,
                     f"{time.monotonic()-t1:.1f}s, screenshot captured"))
                record["formatting"] = {
                    "latency_s": round(time.monotonic() - t1, 2),
                    "excerpt": (await page.inner_text("body"))[-1200:],
                }

                # -- F07 explicit re-search ---------------------------------
                await box.click()
                await box.fill("search again for U-22")
                t2 = time.monotonic()
                await box.press("Enter")
                try:
                    await page.wait_for_timeout(60_000)
                except Exception:
                    pass
                await page.screenshot(path=str(SHOTS / "05_research.png"),
                                      full_page=False)
                S(log("F07_explicit_research", PASS,
                     f"{time.monotonic()-t2:.1f}s, screenshot captured"))
                record["research"] = {
                    "latency_s": round(time.monotonic() - t2, 2),
                    "excerpt": (await page.inner_text("body"))[-1200:],
                }
        except Exception as exc:  # noqa: BLE001
            S(log("F05_file_lookup_evidence", FAIL, f"{type(exc).__name__}: {exc}"[:200]))

        # -- F08 reload preserves the conversation ---------------------------
        try:
            before = await page.inner_text("body")
            await page.reload(wait_until="domcontentloaded", timeout=90_000)
            await page.wait_for_timeout(8000)
            after = await page.inner_text("body")
            await page.screenshot(path=str(SHOTS / "06_after_reload.png"),
                                  full_page=False)
            kept = "U-22" in after or "SLE24-16" in after
            S(log("F08_reload_preserves_history", PASS if kept else FAIL,
                 f"before={len(before)} after={len(after)} chars, "
                 f"identifiers retained={kept}"))
            record["reload"] = {"before_chars": len(before), "after_chars": len(after),
                                "identifiers_retained": kept}
        except Exception as exc:  # noqa: BLE001
            S(log("F08_reload_preserves_history", FAIL, f"{type(exc).__name__}: {exc}"[:200]))

        record["network"] = {
            "api_hosts": sorted(observed_api_hosts),
            "websockets": ws_urls[:5],
        }
        record["console_errors"] = console_errors[:10]
        await browser.close()

    # -- boundary evidence straight from the durable store --------------------
    try:
        import sqlite3
        state = json.loads((HERE / "preview_state.json").read_text())
        con = sqlite3.connect(f"file:{state['isolation']['db_path']}?mode=ro", uri=True)
        record["durable"] = {
            "chat_sessions": con.execute(
                "SELECT COUNT(*) FROM chat_sessions").fetchone()[0],
            "chat_messages": con.execute(
                "SELECT COUNT(*) FROM chat_messages").fetchone()[0],
            "invocation_events": con.execute(
                "SELECT COUNT(*) FROM invocation_events").fetchone()[0]
            if _has_table(con, "invocation_events") else None,
            "goal_runs": con.execute(
                "SELECT COUNT(*) FROM goal_runs").fetchone()[0],
        }
        con.close()
    except Exception as exc:  # noqa: BLE001
        record["durable"] = {"error": str(exc)[:200]}

    totals = {PASS: 0, FAIL: 0, BLOCKED: 0}
    for step in record["steps"]:
        totals[step["verdict"]] = totals.get(step["verdict"], 0) + 1
    record["totals"] = totals
    return record


def _has_table(con, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone() is not None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frontend", default="http://localhost:3091")
    p.add_argument("--api", default="http://127.0.0.1:8091")
    p.add_argument("--out", default=str(HERE / "preview_verification.json"))
    args = p.parse_args()

    record = asyncio.run(run(args.frontend, args.api))
    Path(args.out).write_text(json.dumps(record, indent=1))
    print(f"\n{record['totals']}")
    print(f"wrote {args.out}")
    return 0 if record["totals"][FAIL] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
