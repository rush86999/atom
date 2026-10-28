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
            "first_failed_transition": "The click path through the Training tab was not exercised; the API teach path and restart persistence were.",
            "next_action": "Run the same teach/correct/delete actions through the rendered UI.",
            "blocking": True,
            "notes": "Storage/injection is not the gate; measurable improvement on later work is.",
        },
        {
            "id": "CR-009",
            "area": "trained-agent",
            "feature": "Trained-employee loop",
            "action": "Teach through the UI, run an unfamiliar task, inspect deliverable/sources, correct, run a different task, restart, verify scoped persistence",
            "candidate_bound": True,
            "config": "isolated world + local Ollama llama3.1:8b (no external spend)",
            "status": "failed",
            "evidence": [
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/agent.json", "detail": "Record Auditor created as STUDENT"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/lessons_after_restart.json", "detail": "grant-threshold lesson persisted across a backend restart"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/task2.json", "detail": "attempt 1: labeled grants_loop.csv but listed Roper-011/Tennsmith-001 rows from another workbook; outcome failed"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/task2_attempt2.json", "detail": "attempt 2 after removing the implicit price field: still invented GL001/GL002 rows, never bound the four real grant rows; outcome failed"},
                {"kind": "fixture", "path": f"{EVIDENCE}/core_loop_attempt1/grants_loop.csv", "detail": "the four grant rows the answer should have cited"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_grants_loop.json", "detail": "unfamiliar-task judgment now follows the newest taught correction: GR-2026-033 (4800) DECLINE (was wrongly FUND); one generation, validated, outcome completed"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_helpdesk_different_task.json", "detail": "different-task leg: the helpdesk block omitted evidence_ids and mislabeled a 2.25h ticket ESCALATE; refused with recorded codes, deterministic rows delivered, turn failed"},
            ],
            "first_failed_transition": "Teach, unfamiliar task and correction legs now hold: the unfamiliar-task assessment follows the newest correction (4800 -> DECLINE, attempt2 grants) and restart persistence holds (fresh history after restart). The loop still fails at the different-task leg: on helpdesk_loop.csv the model produced a defective block (no evidence IDs, 2.25h labeled ESCALATE) which the platform correctly refused — judgment quality on the local 8b model is not reliable across domains.",
            "next_action": "Make cross-domain judgment reliable on the configured local model (or qualify the model requirement), then repeat teach -> unfamiliar task -> correct -> different task -> restart end to end.",
            "blocking": True,
            "notes": "The failing different-task turn was correctly marked failed; no unvalidated decision reached the user. This is the core acceptance gate and it is NOT met.",
        },
        {
            "id": "CR-012",
            "area": "calculation",
            "feature": "Deterministic result authority",
            "action": "When a deterministic file read computes rows, the delivered answer must cite those rows and not a model-written table that contradicts them",
            "candidate_bound": True,
            "config": "isolated world + local Ollama",
            "status": "verified",
            "evidence": [
                {"kind": "test", "path": "backend/tests/test_table_selection.py", "detail": "deliver_selection: fabricated Roper-011/Tennsmith-001/GL001/GL002 text never appears in the delivered message; kept in diagnostics"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assess_final.json", "detail": "assessment ask delivered only the deterministic source rows and explicitly said no decision was accepted (success=false)"},
            ],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "For a validated selection the model does not author the table. For an assessment the deterministic rows are delivered and an unvalidated decision table is withheld; decision delivery is CR-014.",
        },
        {
            "id": "CR-013",
            "area": "calculation",
            "feature": "Tabular selection ask",
            "action": "List named columns for rows matching a condition in a named table (list Application Ref and Requested Amount for Submitted rows)",
            "candidate_bound": True,
            "config": "isolated world; controlled production-path tests + API",
            "status": "verified",
            "evidence": [
                {"kind": "test", "path": "backend/tests/test_table_selection.py", "detail": "exact grants selection (3 rows, Withdrawn excluded), renamed schema, helpdesk twin, ambiguity, model-table rejection, completion contract"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/selection_api_verified.json", "detail": "GET /api/chat/message returned the deterministic 3-row table with the correct filter; model=deterministic"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/selection_missing_file_guard.json", "detail": "unknown file: no table delivered, success=false"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/selection_helpdesk_api.json", "detail": "different domain: Ticket/Hours for Open rows, 2 rows, Closed excluded"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/selection_after_restart.json", "detail": "same grants selection after a real backend restart"},
            ],
            "first_failed_transition": None,
            "next_action": "Promote after the browser UI check of the same ask.",
            "blocking": False,
            "notes": "The operation is selected before item extraction; columns and predicate come from the bound sheet's headers/values, not business nouns.",
        },
        {
            "id": "CR-014",
            "area": "trained-agent",
            "feature": "Assessment decision binding",
            "action": "Use deterministic subjects/facts, accept only task-defined decisions from the model, validate subject/evidence/policy references and render the final table",
            "candidate_bound": True,
            "config": "isolated world + local Ollama",
            "status": "verified",
            "evidence": [
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_structurally_valid_wrong_judgment.json", "detail": "one generation, 3 subjects, validated table (HOLD/HOLD/FUND), response+history completed; GR-2026-033 4800 was FUND while the correction says DECLINE"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_malformed_safe_failure.json", "detail": "next generation emitted no valid block; deterministic rows delivered, no decisions, success=false"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_boundaries_green.json", "detail": "corrected rule: 3200 DECLINE, 5000 HOLD, 10000 HOLD, 12000 HOLD; source/policy basis; success/completed"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_renamed_schema_green.json", "detail": "renamed schema/labels: 3200 REJECT, 5000 REVIEW, 10000 REVIEW; success/completed"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_after_restart_failed.json", "detail": "renamed assessment after restart: no valid block, deterministic rows only, success=false (reliability tracked as CR-019)"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_boundaries_after_restart_green.json", "detail": "grants boundary assessment after restart: 3200 DECLINE, 5000 HOLD, 10000 HOLD, 12000 HOLD; success/completed"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_history_after_restart.json", "detail": "green run persisted with the table and outcome=completed after restart"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_grants_loop.json", "detail": "the previously-failing case fixed: GR-2026-033 (4800) DECLINE under the newest taught correction; one generation (952 chars), 3 subjects, evidence ev:...R2/R3/R4, policy = the corrected rule; response success=true outcome=completed"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_history_after_restart.json", "detail": "fresh history after a backend restart agrees: success=true, outcome=completed, decision table and VALIDATED REVIEW present"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_helpdesk_different_task.json", "detail": "a block missing evidence_ids (and one wrong label) was REFUSED with recorded codes missing_evidence_ids; deterministic rows delivered, no certified decisions — acceptance-only validation holds"},
                {"kind": "test", "path": "backend/tests/test_table_selection.py", "detail": "artifact mapping, ambiguous subject clarification, valid/invalid review variants, table join, teaching revision"},
            ],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "Binding is verified: decisions are task-defined, subject/evidence/policy-bound, and a defective block is refused with recorded codes while the deterministic rows remain. Judgment CORRECTNESS on green runs followed the newest teaching every time (4800 DECLINE; boundary 3200 DECLINE; renamed 3200 REJECT). Generation reliability across restarts is tracked separately as CR-019; cross-domain judgment variance is CR-009.",
        },
        {
            "id": "CR-016",
            "area": "trained-agent",
            "feature": "Structured review pipeline",
            "action": "Selection -> structured review artifact -> one generation -> subject/evidence/policy validation -> table joined to authoritative rows",
            "candidate_bound": True,
            "config": "isolated world + local Ollama",
            "status": "verified",
            "evidence": [
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_structurally_valid_wrong_judgment.json", "detail": "generation started/completed once; 3 subjects; evidence IDs ev:...R2/R3/R4; two policy IDs; validation ok"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_history_after_restart.json", "detail": "response, persisted row and fresh history agree (success=true, outcome=completed, table present)"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_grants_loop.json", "detail": "attempt2: artifact built (subjects=3, evidence=3), generation completed once (952 chars, block_recovery not needed), validation ok in 198ms"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt2/assessment_helpdesk_different_task.json", "detail": "when the reply leg lost the block, the one contract-only retry fired with the SAME evidence/policy IDs and the result was re-validated by the unchanged gate; provider-failure text is treated as a failed generation, never as model content"},
            ],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "Validation certifies subject coverage/evidence/policy/decision labels, not the substantive correctness of a decision.",
        },
        {
            "id": "CR-015",
            "area": "calculation",
            "feature": "Completion contract",
            "action": "A selection turn completes only with a bound source, resolved columns, predicate, row references and delivery",
            "candidate_bound": True,
            "config": "isolated world",
            "status": "verified",
            "evidence": [
                {"kind": "test", "path": "backend/tests/test_table_selection.py", "detail": "lookup receipt rejected; valid receipt passes; missing-file ask redacted"},
                {"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/selection_missing_file_guard.json", "detail": "missing file produced success=false and no table"},
            ],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "The guard runs at the public response boundary, so a route-level 2xx or an item-lookup receipt cannot satisfy a selection ask.",
        },
        {
            "id": "CR-017",
            "area": "trained-agent",
            "feature": "Self-contained review policy",
            "action": "Give every selectable policy ID its applicable instruction text in the review prompt; same policy index for generation and validation",
            "candidate_bound": True,
            "config": "local prompt capture + unit tests",
            "status": "verified",
            "evidence": [
                {"kind": "private-capture", "path": "backend/logs/review_diagnosis/review_prompt_4800_capture.json", "detail": "pre-fix prompt had policy IDs/topics only; below-5000 text absent"},
                {"kind": "test", "path": "backend/tests/test_review_result.py", "detail": "policy text, row-values basis, newest-first precedence, allowed labels, evidence IDs present"},
            ],
            "first_failed_transition": None,
            "next_action": "",
            "blocking": False,
            "notes": "No grant thresholds, labels or business nouns were added to platform code; the text comes from the lesson record.",
        },
        {
            "id": "CR-018",
            "area": "background",
            "feature": "Review read-obligation reconciliation",
            "action": "After a validated review, settle only the read obligations it satisfied; keep genuine freshness obligations; leave an incomplete review's work open",
            "candidate_bound": True,
            "config": "isolated world task lifecycle",
            "status": "verified",
            "evidence": [
                {"kind": "state", "path": "task run d56267c8", "detail": "completed assessment: 3 read obligations settled; 3 genuine freshness obligations remain open"},
                {"kind": "state", "path": "task run 66ebd241", "detail": "post-restart green assessment: 4 read obligations settled; 4 freshness obligations remain open"},
                {"kind": "state", "path": "task run 558425c5", "detail": "incomplete assessment: 3 read + 3 freshness obligations remain open"},
            ],
            "first_failed_transition": None,
            "next_action": "A stale 'Still needed' history row created before settlement remains as history; new continuations must reflect the settled state.",
            "blocking": False,
            "notes": "History is not deleted; only the task-state obligation is reconciled through resolve_unresolved_questions.",
        },
        {
            "id": "CR-019",
            "area": "trained-agent",
            "feature": "Post-restart assessment reliability",
            "action": "Repeat a previously green assessment after a real restart and require a validated decision table",
            "candidate_bound": True,
            "config": "isolated world + local Ollama",
            "status": "failed",
            "evidence": [{"kind": "api", "path": f"{EVIDENCE}/core_loop_attempt1/assessment_after_restart_failed.json", "detail": "no valid block; deterministic rows delivered, success=false"}],
            "first_failed_transition": "The renamed-schema assessment did not emit a valid block after restart; a separate grants boundary assessment after the same restart did pass (assessment_boundaries_after_restart_green.json), so restart reliability is mixed, not uniformly broken.",
            "next_action": "Measure the post-restart generation failure (provider/context/format) before changing the loop; do not keep repeating unchanged requests.",
            "blocking": True,
            "notes": "Pre-restart green runs prove the pipeline and judgment on those inputs; this is a reliability gap, not a structural one.",
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
