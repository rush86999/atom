#!/usr/bin/env python3
"""Build the core-release readiness ledger from the whole-app ledger.

The 2026-10-27 product decision replaced the whole-app finish line with the
core company-data + trained-agent workspace. This script does not rescore
anything: it *classifies* each existing item against the agreed core surface,
marks deferred items with the explicit product disposition, and adds the new
core-release checks (surface enforcement, domain independence, materials).

Outputs:
  docs/acceptance/CORE_RELEASE_LEDGER_2026-10-27.json
  docs/acceptance/CORE_RELEASE_LEDGER_2026-10-27.md
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "acceptance"
SOURCE = OUT / "WHOLE_APP_READINESS_LEDGER_2026-10-27.json"
EVIDENCE = "docs/acceptance/evidence/whole_app_20261027"

DEFERRED_ACTIONS = {
    "tasks": "Task tracking is deferred; work and results stay in Activity.",
    "boards": "Kanban is deferred; task definitions live in the accepted task.",
    "workflows": "Workflow builder/scheduling/unattended automation is deferred; the core work loop is directed, reviewed work.",
    "marketplace": "Marketplace is deferred; agents are created and taught in Agents.",
    "command_centers": "Command-center dashboards are deferred.",
    "business": "Business dashboards are deferred; business rules come from teaching.",
    "productivity": "Calendar/health/voice are deferred.",
    "governance": "Admin/governance/self-healing tools are deferred from the core release.",
    "search": "Unified search is deferred; document search remains in Data.",
    "platform": "Deferred platform surface (connectors/team chat/system status).",
    "connectors": "Broad connector management is deferred; provider keys stay in Settings.",
    "team_chat": "Team chat is deferred.",
}

# Individual whole-app items that belong to a deferred capability even though
# their ledger area is shared (platform/breadth).
DEFERRED_ID_HINTS = {
    "WA-073": "connectors", "WA-074": "connectors",
    "WA-076": "governance", "WA-077": "productivity",
    "WA-078": "team_chat", "WA-082": "connectors",
}

MIXED_PLATFORM_CORE = {"WA-075", "WA-079", "WA-080", "WA-081"}


def classify(item: dict) -> str | None:
    """Return the deferred capability name, or None for a core item."""
    if item["id"] in DEFERRED_ID_HINTS:
        return DEFERRED_ID_HINTS[item["id"]]
    if item["id"] in MIXED_PLATFORM_CORE:
        return None
    area = item.get("area", "")
    return area if area in DEFERRED_ACTIONS else None


def main() -> None:
    source = json.loads(SOURCE.read_text())
    items = []
    deferred_count = 0
    for item in source["items"]:
        deferred = classify(item)
        row = dict(item)
        if deferred:
            row["status"] = "deferred_scope"
            row["first_failed_transition"] = None
            row["next_action"] = DEFERRED_ACTIONS[deferred]
            row["notes"] = (
                (row.get("notes") or "")
                + " Deferred by the 2026-10-27 core-release product decision; "
                  "code and recorded data are retained."
            ).strip()
            row["deferred_capability"] = deferred
            deferred_count += 1
        items.append(row)

    core_additions = [
        {
            "id": "CR-001",
            "area": "surface",
            "feature": "One capability configuration",
            "action": "Serve /api/product/profile and use it for navigation, dashboard links and direct-page access",
            "candidate_bound": True,
            "config": "whole-app-world-20261027",
            "status": "verified",
            "evidence": [{
                "kind": "browser",
                "path": f"{EVIDENCE}/browser-core-surface.json",
                "detail": "admin: 13 core routes loaded, sidebar showed only core labels, 23 deferred routes rendered the scope page; member: six core labels, Approvals hidden, direct /approvals showed the supervisor-required state; no page errors or 5xx. Production build repeated the same check.",
            }],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "ATOM_PRODUCT_PROFILE=core (default); full restores the wider surface.",
        },
        {
            "id": "CR-002",
            "area": "surface",
            "feature": "Deferred direct links",
            "action": "Open each deferred route directly and confirm the explicit scope page",
            "candidate_bound": True,
            "config": "whole-app-world-20261027",
            "status": "verified",
            "evidence": [{
                "kind": "browser",
                "path": f"{EVIDENCE}/browser-core-surface.json",
                "detail": "23/23 deferred routes showed 'not part of this release'",
            }],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "",
        },
        {
            "id": "CR-003",
            "area": "surface",
            "feature": "Core worker defaults",
            "action": "Assert the core profile disables autonomous scheduling, external ingestion sync and agent evolution by default",
            "candidate_bound": True,
            "config": "unit test",
            "status": "verified",
            "evidence": [{"kind": "test", "path": "backend/tests/test_product_profile.py", "detail": "test_core_worker_defaults_are_disabled"}],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "Explicit operator settings still win; the isolated world may enable a worker for a specific check.",
        },
        {
            "id": "CR-004",
            "area": "calculation",
            "feature": "General spreadsheet operations",
            "action": "Run line_total, sum and count through the same provenance/gap discipline, without a quantity x price assumption",
            "candidate_bound": True,
            "config": "unit test",
            "status": "verified",
            "evidence": [{"kind": "test", "path": "backend/tests/test_core_domain_independence.py", "detail": "6 tests: sum/count, unstated currency, classification vocabulary"}],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "Missing required inputs are named gaps; no column is guessed when the measure is not named.",
        },
        {
            "id": "CR-005",
            "area": "trained-agent",
            "feature": "Task-owned decisions",
            "action": "Accept decisions from the accepted task in three unrelated domains and reject a decision outside the taught set",
            "candidate_bound": True,
            "config": "unit test",
            "status": "verified",
            "evidence": [{"kind": "test", "path": "backend/tests/test_core_domain_independence.py", "detail": "Process/Escalate, Fund/Decline/Hold, Close/Reassign; rogue decision rejected"}],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "",
        },
        {
            "id": "CR-006",
            "area": "trained-agent",
            "feature": "Subject identity",
            "action": "Accept codes, references and human labels as review subjects; no fixed ID regex",
            "candidate_bound": True,
            "config": "unit test",
            "status": "verified",
            "evidence": [{"kind": "test", "path": "backend/tests/test_core_domain_independence.py", "detail": "0007, O-1001, GR-2026-014, HD-88 and 'Acme renewal'"}],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "",
        },
        {
            "id": "CR-007",
            "area": "data",
            "feature": "Imported email",
            "action": "Upload an .eml file and preserve participants, date, subject, body and attachment names",
            "candidate_bound": True,
            "config": "unit test",
            "status": "partial",
            "evidence": [{"kind": "test", "path": "backend/tests/test_eml_parsing.py", "detail": "headers/body/attachment names preserved; attachment bytes not dumped"}],
            "first_failed_transition": "The .eml upload has not been exercised through the browser and a durable document row on this successor.",
            "next_action": "Upload a representative .eml through Data, search its body, and reload.",
            "blocking": False,
            "notes": "A connected mailbox remains a separate capability.",
        },
        {
            "id": "CR-008",
            "area": "trained-agent",
            "feature": "Teaching UI",
            "action": "Teach through chat or the canvas Training tab; inspect, edit and delete teaching points; keep global/goal scope",
            "candidate_bound": False,
            "config": "existing candidate evidence + component tests",
            "status": "partial",
            "evidence": [{"kind": "code", "path": "frontend-nextjs/components/canvas/TrainingPanel.tsx", "detail": "Training panel + teaching-point edit/delete; /teach chat channel"}, {"kind": "test", "path": "frontend-nextjs/components/canvas/__tests__/TrainingPanel.test.tsx", "detail": "component tests"}],
            "first_failed_transition": "No teach -> unfamiliar task -> correct -> restart loop was executed on this successor with a configured model.",
            "next_action": "Run the trained-employee acceptance loop with an authorized model configuration.",
            "blocking": True,
            "notes": "Storage/injection is not the gate; measurable improvement on later work is.",
        },
        {
            "id": "CR-009",
            "area": "trained-agent",
            "feature": "Trained-employee loop",
            "action": "Teach through the UI, run an unfamiliar task, inspect deliverable/sources, correct, run a different task, restart, verify scoped persistence",
            "candidate_bound": False,
            "config": "requires a configured provider",
            "status": "unproven",
            "evidence": [],
            "first_failed_transition": "Not executed on this successor.",
            "next_action": "Run the loop with an authorized provider; record per-stage evidence and a restart.",
            "blocking": True,
            "notes": "This is the core acceptance gate. Prior order-review evidence is one building block, not this claim.",
        },
        {
            "id": "CR-010",
            "area": "workspace",
            "feature": "Deliverable formats",
            "action": "Produce and reopen an email draft, document, calculated table and presentation in Workspace",
            "candidate_bound": False,
            "config": "isolated world",
            "status": "partial",
            "evidence": [{"kind": "code", "path": "backend/core/office_service.py", "detail": "pptx/docx/xlsx create+revise paths"}, {"kind": "code", "path": "frontend-nextjs/pages/canvas/[id].tsx", "detail": "canvas editor"}, {"kind": "test", "path": "backend/tests/test_pptx_parsing.py", "detail": "slide text, tables and notes parsed with provenance"}],
            "first_failed_transition": "No browser deliverable check for email/presentation on this successor.",
            "next_action": "Create one of each in Workspace, reopen after reload and verify content survives.",
            "blocking": True,
            "notes": "",
        },
        {
            "id": "CR-011",
            "area": "release",
            "feature": "Production build",
            "action": "Build the shipping frontend and run the core browser breadth against that build",
            "candidate_bound": False,
            "config": "successor tree, NEXT_PUBLIC_ALLOW_LOOPBACK=1 (isolated build)",
            "status": "verified",
            "evidence": [
                {"kind": "build", "path": "frontend-nextjs/.next/BUILD_ID", "detail": "next build --webpack compiled successfully; 139/139 static pages generated"},
                {"kind": "browser", "path": f"{EVIDENCE}/browser-core-surface-prod.json", "detail": "production server on :3002 passed the same core/scope/member checks"},
            ],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "Turbopack refuses the worktree's node_modules symlink; the build was repeated from a hardlinked copy with real node_modules. Loopback is an explicit opt-in for this isolated build only.",
        },
    ]
    items.extend(core_additions)

    statuses = Counter(i["status"] for i in items)
    summary = {
        "total": len(items),
        "by_status": dict(sorted(statuses.items())),
        "core_statuses": {
            k: v for k, v in sorted(statuses.items())
            if k not in {"deferred_scope", "not_authorized"}
        },
        "deferred_items": deferred_count,
        "core_release_ready": False,
        "reason": (
            "The core surface is configured and browser-enforced, and the "
            "domain-independent calculation/decision contracts pass. The "
            "trained-employee loop, deliverable formats and the production "
            "build remain open; deferred surfaces are an explicit product "
            "decision, not failures."
        ),
    }
    doc = {
        "schema_version": "core-release-1",
        "title": "Atom core-release readiness ledger — 2026-10-27",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "supersedes": "WHOLE_APP_READINESS_LEDGER_2026-10-27",
        "decision": "docs/acceptance/CORE_RELEASE_SCOPE_2026-10-27.md",
        "candidate": source["candidate"],
        "environment": source.get("environment", {}),
        "status_legend": {
            **source.get("status_legend", {}),
            "deferred_scope": "Excluded from the core release by the 2026-10-27 product decision; code and data retained.",
        },
        "summary": summary,
        "items": items,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "CORE_RELEASE_LEDGER_2026-10-27.json").write_text(
        json.dumps(doc, indent=2) + "\n")

    lines = [
        "# Atom core-release readiness ledger — 2026-10-27",
        "",
        f"Candidate: `{doc['candidate']['commit']}` (tree `{doc['candidate']['tree']}`), branch `{doc['candidate']['branch']}`.",
        "",
        f"Generated: {doc['generated_at']}",
        "",
        "Supersedes `WHOLE_APP_READINESS_LEDGER_2026-10-27` for launch "
        "scope. The whole-app ledger remains history. Product decision: "
        "`docs/acceptance/CORE_RELEASE_SCOPE_2026-10-27.md`.",
        "",
        "Machine-readable source: `docs/acceptance/CORE_RELEASE_LEDGER_2026-10-27.json`.",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|---|---|",
    ]
    for status, count in summary["by_status"].items():
        lines.append(f"| {status} | {count} |")
    lines += [
        "",
        f"**Core release ready: no.** {summary['reason']}",
        "",
        "## Items",
        "",
        "| ID | Area | Action | Status | First failed transition | Next action |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        action = item["action"].replace("|", "\\|")
        failed = (item.get("first_failed_transition") or "—").replace("|", "\\|")
        nxt = (item.get("next_action") or "—").replace("|", "\\|")
        lines.append(
            f"| {item['id']} | {item['area']} | {action} | "
            f"**{item['status']}** | {failed} | {nxt} |")
    lines += ["", "Status meanings: `verified` = executed end-to-end on the named "
              "candidate/config; `failed` = reproduced failure at the user-visible "
              "boundary; `partial` = an early transition passed, a later one did "
              "not; `unproven` = no candidate-bound execution; "
              "`environment_limited` = needs credentials/a worker this world "
              "intentionally disables; `blocked_external` = needs a real external "
              "account; `not_authorized` = would deploy/spend/contact outside the "
              "sandbox; `deferred_scope` = excluded by the product decision, not a "
              "failure."]
    (OUT / "CORE_RELEASE_LEDGER_2026-10-27.md").write_text("\n".join(lines) + "\n")
    print(
        f"core ledger: {len(items)} items, {deferred_count} deferred, "
        f"statuses={dict(sorted(statuses.items()))}"
    )


if __name__ == "__main__":
    main()
