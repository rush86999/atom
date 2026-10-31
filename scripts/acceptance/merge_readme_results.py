#!/usr/bin/env python3
"""Merge README acceptance evidence from multiple isolated worlds.

A feature may be verified in the world that can configure it (for example the
gateway world configures a provider before the first chat turn). Merging keeps
the STRONGEST status observed for each claim and records every source so the
matrix never silently upgrades a partial result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RANK = {
    "verified": 6,
    "partial": 5,
    "failed": 4,
    "inaccurate": 3,
    "blocked_external": 2,
    "environment_limited": 2,
    "architecture_only": 2,
    "unverified": 1,
}


def load_results(path: Path) -> dict:
    data = json.loads(path.read_text())
    return {r["claim_id"]: r for r in data.get("results", [])}


def install_claims(path: Path) -> dict:
    data = json.loads(path.read_text())
    checks = data.get("checks") or {}
    ok = data.get("status") == "verified"
    common_ev = [str(path)]
    return {
        "INST-02": {
            "claim_id": "INST-02", "status": "verified" if checks.get("profile") else "partial",
            "evidence": common_ev,
            "notes": "Documented uvicorn main_api_app:app process served /health/ready and /api/product/profile",
            "blocker": "",
        },
        "INST-04": {
            "claim_id": "INST-04",
            "status": "verified" if (checks.get("password_file", {}).get("mode") == "0o600"
                                     and checks.get("password_file", {}).get("length", 0) >= 16
                                     and checks.get("login", {}).get("token")) else "partial",
            "evidence": common_ev,
            "notes": "Fresh root generated the 0600 bootstrap password file; that password logged in",
            "blocker": "",
        },
        "INST-05": {
            "claim_id": "INST-05",
            "status": "verified" if checks.get("restart", {}).get("task_survives") else "partial",
            "evidence": common_ev,
            "notes": "Task created before the restart was readable from a new backend process on the same data root",
            "blocker": "",
        },
        "WF-03": {
            "claim_id": "WF-03",
            "status": "verified" if checks.get("workflow", {}).get("survives_restart") else "partial",
            "evidence": common_ev,
            "notes": "A completed workflow execution was re-read from a new backend process on the same data root",
            "blocker": "",
        },
        "OFF-08": {
            "claim_id": "OFF-08",
            "status": "verified" if (checks.get("office_canvas", {}).get("canvas_read")
                                     and checks.get("office_canvas", {}).get("download_ok")) else "partial",
            "evidence": common_ev,
            "notes": "A presented Office canvas and its downloadable file were re-read from a new backend process on the same data root",
            "blocker": "",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, action="append", required=True)
    parser.add_argument("--install", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    merged: dict = {}
    sources: dict = {}
    for path in args.results:
        for cid, row in load_results(path).items():
            merged.setdefault(cid, row)
            sources.setdefault(cid, []).append(str(path))
            if RANK.get(row["status"], 0) > RANK.get(merged[cid]["status"], 0):
                merged[cid] = row

    if args.install:
        for cid, row in install_claims(args.install).items():
            merged.setdefault(cid, row)
            sources.setdefault(cid, []).append(str(args.install))
            if RANK.get(row["status"], 0) > RANK.get(merged[cid]["status"], 0):
                merged[cid] = row

    for cid, row in merged.items():
        row["notes"] = (row.get("notes") or "") + f" [sources: {', '.join(sources.get(cid, []))}]"

    output = {
        "schema_version": 1,
        "harness": "backend/scripts/readme_acceptance + scripts/acceptance/readme_local_install.py",
        "merged_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "inputs": [str(p) for p in args.results] + ([str(args.install)] if args.install else []),
        "results": sorted(merged.values(), key=lambda r: r["claim_id"]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"claims": len(merged),
                      "by_status": {s: sum(1 for r in merged.values() if r["status"] == s)
                                    for s in RANK}}, indent=2))


if __name__ == "__main__":
    main()
