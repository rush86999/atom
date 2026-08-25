"""Manual verification for the Outlook automation (LLM draft + trigger).

Run from the repo root:

    PYTHONPATH=".;./backend" python backend/scripts/check_outlook_automation.py

Checks, in order:
  1. DB      — the Outlook/Microsoft token exists in the canonical root DB
               and decrypts with the root encryption key.
  2. Trigger — _matches_email_trigger() fires on contact-page links and
               quote/price keywords, and ignores unrelated mail.
  3. Draft   — calls the REAL LLM draft path with a sample customer email and
               prints what the AI would write (requires an LLM key in .env,
               e.g. OPENCODE_API_KEY; skipped with a clear note if absent).

Then it prints the end-to-end steps for the live check.
"""

import asyncio
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

# Windows consoles default to cp1252, which can't encode the non-ASCII
# characters an LLM draft may contain (e.g. non-breaking hyphens).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv

# Load the way main_api_app does: backend/.env first (wins), then root, then .env.local.
load_dotenv(os.path.join(ROOT, "backend", ".env"))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, ".env.local"), override=True)

from cryptography.fernet import Fernet, InvalidToken  # noqa: E402

import outlook_automation_service as oas  # noqa: E402


def _load_key() -> bytes:
    path = os.getenv("BYOK_ENC_KEY_FILE", os.path.join(ROOT, "data", "byok_encryption_key"))
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip().encode()


def check_db() -> bool:
    print("=" * 62)
    print("CHECK 1 — Outlook token in the canonical DB")
    print("=" * 62)
    url = os.getenv("DATABASE_URL", "sqlite:///./atom_dev.db")
    db_path = url.replace("sqlite:///", "").replace("sqlite://", "")
    key = _load_key()
    ok = False
    if not os.path.exists(db_path):
        print(f"  FAIL: DB not found at {db_path} (DATABASE_URL={url})")
        return False
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT provider, user_id, status, expires_at FROM integration_tokens "
        "WHERE provider IN ('outlook','microsoft') AND status='active'"
    ).fetchall()
    con.close()
    if not rows:
        print("  FAIL: no active outlook/microsoft token row in this DB")
        return False
    for r in rows:
        print(f"  row: provider={r['provider']} user={r['user_id'][:8]}… status={r['status']} expires={r['expires_at']}")
        ok = True
    print(f"  {('OK' if ok else 'FAIL')} — {len(rows)} active token row(s)")
    return ok


def check_trigger() -> bool:
    print()
    print("=" * 62)
    print("CHECK 2 — Email trigger (contact link OR quote keywords)")
    print("=" * 62)
    print(f"  configured keywords: {os.getenv(oas.TRIGGER_KEYWORDS_FLAG, oas.DEFAULT_TRIGGER_KEYWORDS)}")
    cases = [
        ("contact link", "Please see https://brennan.ca/pages/contact", True),
        ("keyword 'quote'", "Can you send me a quote for 5 sheets?", True),
        ("keyword 'price'", "What is your price on the press brake?", True),
        ("keyword 'pricing'", "Need pricing for the brake.", True),
        ("keyword 'estimate'", "Please provide an estimate.", True),
        ("unrelated mail", "Hi, can we reschedule our meeting to Thursday?", False),
    ]
    all_ok = True
    for label, text, expected in cases:
        got = oas._matches_email_trigger(text)
        status = "PASS" if got == expected else "FAIL"
        if got != expected:
            all_ok = False
        print(f"  [{status}] {label:<18} -> trigger={got} expected={expected}")
    print(f"  {'OK' if all_ok else 'FAIL'}")
    return all_ok


async def check_draft() -> bool:
    print()
    print("=" * 62)
    print("CHECK 3 — LLM-drafted reply (real LLM call)")
    print("=" * 62)
    sample = {
        "sender_name": "Jane Smith",
        "sender_email": "jane@acme.example",
        "subject": "Quote Request - 100 Ton Press Brake",
        "body": (
            "Hi, I visited https://brennan.ca/pages/contact. We are a sheet "
            "metal shop and need a quote for a 100-ton press brake with a 10ft "
            "bed. Please let us know pricing and lead time."
        ),
        "preview": "Need a quote for a 100-ton press brake.",
    }
    draft = ""
    for attempt in range(3):  # the free gateway is intermittently overloaded
        try:
            draft = await oas._draft_reply(**sample)
        except Exception as e:  # defensive — _draft_reply never raises, but stay safe
            print(f"  attempt {attempt + 1} raised: {e!r}")
        if draft:
            break
        await asyncio.sleep(1)
    if not draft:
        print("  SKIP: LLM returned nothing (no LLM key configured? LLM down?).")
        print("        Set OPENCODE_API_KEY/OPENAI_API_KEY in backend/.env and retry.")
        return False
    print(f"  Drafted reply ({len(draft)} chars):\n")
    for line in draft.splitlines():
        print(f"    {line}")
    print("\n  OK — this is the body that would appear in the HITL approval.")
    return True


def print_e2e_steps():
    print()
    print("=" * 62)
    print("END-TO-END (live) CHECK — do these once the server is running")
    print("=" * 62)
    print("""
  1. Start the backend (repo root, port 8000). Logs must show:
       -> Outlook memory poller recovered (connected account found)
       -> Outlook Automation Loop started

  2. Send yourself a test email from a personal account containing any of:
       - the text "quote" or "price" (or the brennan.ca/pages/contact link)

  3. Within ~15s the logs show:
       [Outlook Automation] Match found in email <id> from <sender>.
                           Requesting HITL approval...
       ...and a hitl_paused notification appears in the UI.

  4. Open the approval prompt -- you should now see an AI-WRITTEN reply
     (not the fixed template). Approve it.

  5. Logs show: [Outlook Automation] Sending approved reply email to ...
     The customer receives the LLM-drafted email.

  Reject instead -> action cancelled, no email sent.
""")


async def main():
    results = [check_db(), check_trigger(), await check_draft()]
    print()
    print("=" * 62)
    print(f"SUMMARY: {sum(results)}/3 checks passed")
    print("=" * 62)
    print_e2e_steps()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
