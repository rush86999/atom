#!/usr/bin/env python3
"""Apply the manual claim audit to a merged acceptance result.

The merge step deliberately keeps the strongest observed status. The audit is
the separate, explicit decision that a strong-but-weak assertion (status-only,
source-string, existence-only) does not establish the claim. Downgrades are
applied here so they are visible and reviewable, never silently rescored.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.results.read_text())
    audit = json.loads(args.audit.read_text())
    rows = {r["claim_id"]: r for r in payload.get("results", [])}
    applied = []
    for item in audit.get("downgrades", []):
        cid = item["claim_id"]
        if cid not in rows:
            raise SystemExit(f"audit references unknown claim {cid}")
        current = rows[cid].get("status")
        rows[cid]["status"] = item["to"]
        reason = f" [audit {item['from']}->{item['to']}: {item['reason']}]"
        rows[cid]["notes"] = (rows[cid].get("notes") or "") + reason
        applied.append({"claim_id": cid, "from": current, "to": item["to"],
                        "reason": item["reason"]})
    payload["results"] = sorted(rows.values(), key=lambda r: r["claim_id"])
    payload["audit"] = {
        "audit_file": str(args.audit),
        "policy": audit.get("policy"),
        "applied": applied,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"downgrades": len(applied), "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
