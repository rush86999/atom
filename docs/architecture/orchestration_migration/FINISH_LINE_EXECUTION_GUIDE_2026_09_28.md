# Finish-line execution guide: a correct browser edit and verified completion

Date: 2026-09-28. Status: assignment, not acceptance certification.

## 1. Finish line and responsibility

The receiving agent owns this closeout end to end. Finish the bounded work below without asking whether to continue after each case. Coordinate with an actually active writer before touching shared files; do not assign blockers to hypothetical owners.

Deliver one usable isolated preview where an ordinary, authorized canvas edit works through the real browser and real planner, changes only the intended content, persists once, reports its outcome truthfully, and survives reload. Preserve the existing read-oriented preview until the replacement is verified.

This is not a new framework project or a claim that every connector is certified. No ranking benchmark, cross-host workflow engine, broad UI redesign, or new storage migration belongs in this milestone. Existing full-matrix obligations remain visible, but do not invent new gates during closeout. An unexpected safety defect in the supported flow must be repaired; unrelated issues are documented follow-ups.

Read current `AGENTS.md`, `CLAUDE.md`, coordination and the existing lane plans. The repository inspected for this guide had HEAD `1a953b589`, with planner contract commit `6e34725c7` and many uncommitted product/harness changes. Recheck before starting. Neither HEAD nor a world name establishes what a running server executes.

## 2. Established evidence and current uncertainty

Earlier controlled C16 runs demonstrated synchronous success, background success and background failure on specific frozen exports. Those are valuable historical results, not automatic coverage of the current working tree or real-model interpretation.

The latest reported run applied a subject-line change while the request concerned quote validity in the body. The agent attributed this to a mismatched scripted `find` string. That attribution is **unproven**. A missing target cannot justify changing an unrelated field. A result marked `applied` establishes neither correct intent nor correct canvas selection.

Preserve that run as a negative case. Do not align the fixture and erase evidence of the unintended edit. Distinguish:

1. Controlled plan served.
2. Controlled plan accepted by production parsing.
3. Any repair/fallback plan selected.
4. Operation actually executed.
5. Exact persisted field changes.
6. User-visible claim.

The immediate goal is to locate where the unrelated subject edit entered this chain, then prove the corrected workflow.

## 3. Non-destructive setup

- No world deletion, SQLite sidecar removal, automatic retention apply, or portable-drive relocation during this assignment.
- Confirm the recorded live-backup protection gate remains valid before launching resource-heavy tests. Do not independently probe or mutate the live DB with ad-hoc scripts.
- Use one small API-seeded candidate. Reuse its fixture deliberately and reset only disposable test canvases through supported mechanisms. Do not repeatedly copy the full development DB.
- Honor storage preflight and maintenance interlock. On low space, stop and report; do not improvise cleanup.
- Do not restart the user's :3000/:8001 stack or the preserved read preview. Use assigned candidate ports and a separate frontend farm/distDir outside the checkout's frontend directory.
- Verify frontend-farm writes cannot follow symlinks into checkout files. Preserve pre-existing local configuration.
- Do not copy live credentials indiscriminately. Use only configured, authorized model access; no purchases or real outbound messages.
- Detailed evidence stays in controlled acceptance artifacts. Routine logs contain IDs, shapes, hashes and outcomes, not raw user messages, canvas bodies, tokens or secrets.

## 4. First deliverable: one current-state ledger

Create `acceptance/lane3/FINISH_LINE_STATUS.md` and use it as the only current status for this assignment. Link older evidence rather than rewriting its history.

Record:

- Base commit and exact included dirty-file hashes; named excluded changes.
- Export-tree hash and loaded-module paths/hashes from the serving process.
- Configuration identity: actual provider/model, budgets, lifecycle/finalization flags and network boundary.
- Fixture identity and schema setup, database resolved path and serving process identity.
- Frontend build identity, API/WS targets, ports and authentication method without secrets.
- Each required case below as NOT RUN/PASS/FAIL/INCONCLUSIVE, with evidence paths.

Preflight errors and missing hashes fail the gate. No writable export or import bleed into the working tree. Effective server configuration must match what the harness measures. Avoid ambiguous references such as “current code,” “same world” or “full suite” without the identity and exact command.

## 5. Phase A — Reproduce and explain the wrong-field change

Use an API-created disposable email canvas with a valid JSON body and known subject/body fields. Establish a post-seed baseline containing canvas ID, revision, canonical content, audit identities and mutation count.

First reproduce the reported mismatch without modifying the failure conditions. The controlled plan targets text not present in the body. Keep the subject fixed and observable. Capture the exact user request, context canvas identity/revision, tool-call request schema/name, served response, parser result, bounded repair and any provider fallback.

Trace `plan_canvas_edit` / `plan_contract_violation` / `apply_canvas_edit` in `backend/core/chat_canvas_editor.py`, their orchestrator caller, continuation plan/execution and `canvas_crud_tool` persistence. Record the first divergent boundary, not merely the final failure.

Determine which explanation is supported:

- Wrong canvas or stale revision selected.
- Script not consumed and another provider supplied the subject plan.
- Contract repair generated a different target/action.
- Mutation code applied the wrong field or used an unintended fallback.
- Evaluator read a sibling/prior operation or misinterpreted the outcome.

Do not assume any of these from an empty channel or a status string. Repair the smallest demonstrated general mechanism. Do not hardcode quote-validity phrases or suppress all canvas edits.

Expected negative behavior: missing/ambiguous target produces a truthful no-apply/clarification outcome, zero unrelated mutation and no success claim. An allowed repair must remain within the user's requested field/action and current authorization; it cannot choose a convenient unrelated edit. Never flip a declined plan into acceptance merely because it contains operations.

## 6. Phase B — Controlled positive and negative proof

Use the same supported API creation path and exact matching field content for the positive case. Inject only planning; keep authentication, authorization, reservation, execution claim, store, audit, read-back, verification and finalization real.

Required controls:

- Correct body replacement: intended old text gone from that field, new text present there, subject and unrelated fields unchanged.
- Missing target: zero mutation and honest no-apply.
- New text already exists elsewhere: does not satisfy verification of the requested field change.
- Wrong canvas/revision: no accepted mutation of another artifact; conflict is explicit.
- Store reports success without persistence: no final success claim.

Count **all** mutation audit rows on that exact canvas after the post-seed baseline, regardless of operation ID, and also verify expected operation/audit attribution. Read canonical durable content; transcript echoes are not evidence. Never manufacture audit rows as fixture prerequisites; API-created canvases must be readable/editable naturally.

If the formerly passing C16 script is reused, validate the exact nested response envelope through the actual parser first. Match stalls by exact tool name, not prompt substrings. Record the effective budget and prove the background leg actually forks. Do not turn a failed injection into a product diagnosis.

## 7. Phase C — Make the actual browser path work

Repair the canvas page's real build/runtime blockers if still present. For PDF worker loading, verify the resulting worker URL, page load and actual PDF rendering under this Next/Webpack configuration; a proposed one-line import is not sufficient evidence by itself. Verify authentication catch-all routes from the built farm and actual session/composer availability.

Then, with **no accepting-plan injection**:

1. Login through the real UI.
2. Create or open the API-created canvas through the actual canvas page.
3. Inspect the outgoing composer request: correct canvas ID/type/content or revision reference, session, new request ID and candidate backend.
4. Submit the supported body edit. Record the model actually selected and any repair/fallback. A provider availability probe does not identify the model used for this call.
5. Verify intended durable field change, unchanged subject, exactly one total mutation and operation-linked audit.
6. Verify the DOM reports the observed outcome honestly.
7. Reload/reopen and read the artifact again. Compare actual content and history identities, not whether the request's words appear in a transcript.

Run at least a second distinct supported field edit and one legitimate decline/clarification case. Use existing planner/schema mechanisms if failures reproduce. Do not add per-prompt routing, hide model pinning, or count clean decline as successful completion of a supported edit.

An explicitly configured provider/model may define the supported preview if disclosed and repeatably verified. Hidden fallback or a controlled shim cannot establish real-planner readiness. If every authorized provider is unavailable, finish independent cases and report that exact external blocker without claiming the browser edit passed.

## 8. Phase D — Completion, retry and recovery

Reverify readable D5 outcomes on the resulting source, not merely an earlier artifact:

- Connected success and failure: subscribe before starting the request, bind the terminal event/message to continuation/execution/session/canvas.
- Disconnected/empty channel: persist outcome, reconnect/reload, recover it once, and perform no extra mutation.
- Duplicate terminal event and overlapping turns: no duplicate message/effect and no cross-turn replacement.
- Persistence failure: no claim of durable delivery when the durable message was not stored. Notification stage ordering alone is not proof of successful persistence.
- Zero-effect wording: use “nothing changed” only when verified, not because retries expired. Post-commit failure or unknown outcome stays uncertain/reconciled.
- Same-key replay: original response semantics, no extra execution/effect; changed payload conflicts; restart preserves the pin.
- Effect-before-kill: use the existing confined test barrier after committed effect and before terminal persistence. Kill the recorded worker externally, restart the same durable run, verify reconciliation and no duplicate effect. Do not chase a 20 ms window with polling.

Keep the barrier test-only and disarmed on restart. Preserve verified-live ownership, reconcile verified-dead owners, and leave unknown ownership visible/non-destructive. No cross-host redesign.

## 9. Fixed finish-line checklist

These are the required closeout cases. Map existing C00–C26 evidence to them; do not invent parallel conflicting definitions.

| ID | Required result |
|---|---|
| F01 | Current source/config/fixture/process/frontend provenance and safe isolated launch |
| F02 | Wrong-field mismatch reproduced or conclusively explained; missing target cannot mutate subject |
| F03 | Controlled synchronous correct edit, one intended durable mutation |
| F04 | Controlled background success, actual fork and truthful terminal completion |
| F05 | Controlled background failure, actual execution failure and honest terminal outcome |
| F06 | Real-planner browser body edit, unchanged unrelated fields, one write, reload |
| F07 | Second real-planner edit plus legitimate no-apply/clarification |
| F08 | Connected, disconnected and empty-channel completion recovery |
| F09 | Overlap/duplicate terminal events cannot mix identities or repeat effects |
| F10 | Keyed retry, payload conflict and restart pin survival |
| F11 | Effect-before-kill reconciliation without another write |
| F12 | Read preview regressions: chat, lookup, replacement, formatting, re-search and reload |

Retain assertion-level results with PASS/FAIL/NOT APPLICABLE and explicit reasons. A scenario that never reaches its required branch is INCONCLUSIVE, not a pass. Unknown coverage cannot be removed from a denominator to create readiness.

During development run affected focused tests, not broad suites after every edit. Once implementations stabilize, run the final relevant matrix on one immutable combined candidate. Any production change after freezing needs a new fingerprint and affected reruns; final promotion must not splice incompatible exports.

## 10. Work division and completion discipline

One writer owns planner/apply/orchestrator corrections. A second may own D5/frontend consumption after checking actual file overlap. One coordinator owns candidate launch, fixture, source freeze and final browser run. Use explicit file-section handoffs where shared files are unavoidable. Direct pushes are user-authorized, but inspect the staged diff and preserve unrelated work; no stash/reset roulette in a shared checkout.

Do not stop after code inspection, fixture alignment, the next passing case, or a historical summary. Continue through the checklist. When blocked, report the exact command/boundary and observed error, then complete independent work. Do not claim “not my scope” for ordinary harness repair needed to finish your assigned verification; coordinate real ownership conflicts explicitly.

If a hard session limit interrupts execution, save a unique resume checkpoint containing next command, first failing assertion, run identity, evidence paths and file hashes. Do not overwrite another stream's `RESUME.md`, restart completed diagnosis, or invent an estimate of remaining hours.

## 11. Final delivery

Update the single status ledger and publish:

- Current preview URL and exact supported model/configuration/workflows.
- Short manual guide that the agent has actually performed in the browser.
- F01–F12 accounting, linked existing-matrix coverage, and remaining unrelated exclusions.
- Frozen source/config/fixture hashes, test commands/results, before/after content and audit/effect evidence, sanitized event traces and screenshots.
- Scoped changes, rollback instructions and exact unverified limitations.

Promote editing only after the real-planner browser and safety cases pass. Keep broader streaming/ranking/connector claims limited to measured evidence. The user-facing message should lead with what the user can open and do now. The finish line is a demonstrated supported workflow, not another statement that the infrastructure is ready.
