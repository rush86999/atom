"""Business-discovery step: build a draft sales decision catalog from real emails.

Scans the Outlook inbox, classifies each email with the free opencode-go
models (fallback chain + retries), aggregates the classifications into the
(Situation -> Action -> Human?) decision table, and writes:

  docs/sales/DECISION_CATALOG.md          — human-readable catalog
  docs/sales/email_classifications.json   — raw per-email classifications

Usage (from the repo root):

    PYTHONPATH=".;./backend" python backend/scripts/build_decision_catalog.py [--limit 40]

The email fetch uses the same OAuth token as the Outlook service (the one
fixed in the two-DB split session). Emails that fail classification (free
gateway flaky) are skipped and reported — rerun to fill gaps.
"""

import argparse
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, "backend", ".env"))
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, ".env.local"), override=True)

from core.sales_decision_catalog import (  # noqa: E402
    aggregate_catalog,
    classify_email,
)
from integrations.outlook_routes import outlook_service  # noqa: E402


def _render_markdown(rows, total, classified) -> str:
    lines = [
        "# Brennan Machinery — Sales Decision Catalog (draft)",
        "",
        f"> Auto-generated {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')} "
        f"from {classified} classified customer emails (of {total} scanned). "
        "Learn the business before automating it — review each row, correct the "
        "rules, and this becomes the agent's business-knowledge base.",
        "",
        "| Situation (rule) | # | Action(s) | Human? | Systems | Exceptions | Examples |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        actions = ", ".join(f"{a} ({n})" for a, n in sorted(
            r["actions"].items(), key=lambda kv: -kv[1]
        ))
        human = "YES" if r["needs_human"] else "no"
        systems = ", ".join(r["systems"]) or "-"
        exceptions = "; ".join(r["exceptions"]) or "-"
        examples = "; ".join(r["examples"]) or "-"
        lines.append(
            f"| {r['rule']} | {r['count']} | {actions} | {human} | "
            f"{systems} | {exceptions} | {examples} |"
        )
    lines.append("")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Build the sales decision catalog")
    parser.add_argument("--limit", type=int, default=40, help="max emails to classify")
    parser.add_argument("--resume", action="store_true",
                        help="skip fetching/classifying; rebuild the catalog markdown "
                             "from the existing email_classifications.json checkpoint")
    args = parser.parse_args()

    out_dir = os.path.join(ROOT, "docs", "sales")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "email_classifications.json")

    if args.resume:
        if not os.path.exists(json_path):
            print(f"No checkpoint at {json_path} — run without --resume first.")
            return 1
        with open(json_path, encoding="utf-8") as f:
            classifications = json.load(f)
        rows = aggregate_catalog(classifications)
        md_path = os.path.join(out_dir, "DECISION_CATALOG.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(_render_markdown(rows, len(classifications), len(classifications)))
        print(f"Resumed from checkpoint: {len(classifications)} classifications -> "
              f"{len(rows)} rules in {md_path}")
        return 0

    print("Fetching inbox emails (Outlook, via the connected token)...")
    emails = await outlook_service.get_user_emails(
        user_id="default_user", folder="inbox", max_results=max(args.limit, 10) * 2
    )
    if not emails:
        print("No emails returned — is Outlook connected (token active)?")
        return 1
    print(f"Fetched {len(emails)} emails; classifying up to {args.limit}...")

    classifications = []
    skipped = 0
    for i, email in enumerate(emails[: args.limit]):
        cls = None
        for attempt in range(2):
            cls = await classify_email(email)
            if cls.get("intent") != "unknown":
                break
            await asyncio.sleep(0.4)
        if not cls or cls.get("intent") == "unknown":
            skipped += 1
            print(f"  [{i + 1}/{args.limit}] SKIP {email.get('subject', '')[:60]}")
            continue
        classifications.append(cls)
        # Checkpoint after every email so a slow/failed run never loses progress.
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(classifications, f, indent=2, default=str)
        print(
            f"  [{i + 1}/{args.limit}] {cls.get('intent', '?'):<16} "
            f"-> {cls.get('sales_action', '?'):<20} "
            f"{'HUMAN' if cls.get('needs_human') else 'auto'}"
        )

    if not classifications:
        print("No emails could be classified (free gateway down?). Rerun later.")
        return 1

    rows = aggregate_catalog(classifications)

    md_path = os.path.join(out_dir, "DECISION_CATALOG.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_render_markdown(rows, len(emails), len(classifications)))

    print()
    print("=" * 72)
    print(f"DECISION CATALOG ({len(rows)} rules from {len(classifications)} emails, "
          f"{skipped} skipped)")
    print("=" * 72)
    for r in rows:
        actions = ", ".join(f"{a} ({n})" for a, n in sorted(
            r["actions"].items(), key=lambda kv: -kv[1]
        ))
        print(f"  {r['count']:>2}x  {r['rule']:<45} {'HUMAN' if r['needs_human'] else 'auto':<6} {actions}")
    print()
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
