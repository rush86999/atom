# Lane 3 — Acceptance, integration and one usable preview

Date: 2026-09-27. Assigned to the coordinating agent. This lane owns combined verification and environment lifecycle, not concurrent edits to Lane 1/2 production files.

## Objective

Combine backend task correctness and frontend streaming into one verified candidate while keeping a usable preview available. Finish independent harness work in parallel; serialize final world creation, restart, browser testing and promotion.

Read `CHAT_ORCHESTRATOR_APP_READINESS_PLAN_2026_09_26.md`, `LIFECYCLE_EVIDENCE_CLOSEOUT_PLAN_2026_09_26.md`, `AGENT_SEARCH_WORK_ORDER_2026_09_26.md`, and `RESUMED_AGENT_REVIEW_2026_09_27.md`. Existing detailed gates remain in force; this document defines coordination and execution order.

## File ownership

Own general acceptance cases/evaluator support, test providers and effect sinks, result reports, browser drivers and candidate-specific artifacts. Lane 1 currently owns `task_correction_acceptance.py`: review it and send exact changes, or accept an explicit transfer after its writer stops. Do not edit it concurrently.

Storage-guard work is already active in `run_isolated.py`, `preview_stack.py`, `preview_server.py`, `preview_launch.py`, `world_storage_guard.py` and drive diagnostics. Treat these as shared/claimed until the writer confirms a handoff. Proposed launcher changes must be coordinated; do not overwrite storage protection to get a run started.

Do not edit Lane 1 planner/orchestrator files or Lane 2 hooks. If acceptance exposes a defect, provide the failing boundary trace to that lane. If its agent is no longer active, explicitly record ownership transfer before repairing it yourself.

## Work that can run immediately in parallel

1. Inventory current previews, fingerprints, support lists and launch descriptors without exposing secrets. Mark historical results as historical; no combined readiness claim across worlds.
2. Review evaluator contracts. Required IDs must be independent, checks Boolean, and missing/duplicate cases explicit. Exact execution-bound artifact lookup is mandatory.
3. Correct measurement designs: actual calls versus attempt stamps; role/identity-aware history checks; nonempty expected-list matching; absence-aware replacement outcomes; negative controls for stale text plus stale artifacts.
4. Prepare token-bearing provider fixtures, controlled failure injection, durable mutation sink, restart scripts and event correlation without starting another heavyweight world unnecessarily.
5. Verify credential scrubbing covers file stores as well as DB tables. Configured model credentials are intentional exceptions that must be scoped and recorded without secret values.
6. Plan all remaining C00–C26 cases and map existing test evidence to them. Do not rerun successful suites indiscriminately or invent replacement case IDs that hide missing coverage.

## Candidate integration protocol

1. Obtain Lane 1/2 changed-file lists, hashes, test results and known limitations. Check the actual combined diff; avoid wholesale staging/resetting.
2. Freeze one immutable candidate export including required untracked files. Record source, fixture, schema, model/provider configuration and effective flags. Do not rebuild a running world's export.
3. Launch one isolated backend and an independently built frontend farm/distDir. Verify process identity, loaded-module hashes, open DB path, HTTP/proxy/WS destinations, CORS and authentication. Preserve :3000/:8001 and the current measured preview.
4. Run HTTP task-correction acceptance first. If it passes, browser-test normal real-model chat, eight-item read, correction, formatting, re-search, reload and retry.
5. Verify token streaming, finalization and overlap with Lane 2's event contract. Test provider shims establish protocol behavior; real-model smoke establishes configured-model liveness. Report them separately.
6. Execute authorization/no-apply, actual mutation counts, same-key races, crashes before/after mutation, uncertainty/reconciliation, pin persistence failure, restart and access-scope cases from the existing plan.
7. Re-fingerprint production changes. The final complete matrix must run on one final candidate; do not splice green cases from incompatible snapshots.

## Non-negotiable assertion rules

- Same-key replay: original answer and identity, zero additional execution/effect, survives restart. Different payload under same key: conflict, no additional effect.
- Corrected objective: independently expected entities/order match durable revision, retrieval plan, evidence and displayed list. A failure message is not a successful correction.
- Evidence failure: unreadable source cannot be called absent; top-k results cannot prove exhaustive absence.
- Mutation safety: count real changes at the isolated artifact/sink, not only claim rows. Confirm worker loss; timeout alone cannot permit duplicate execution.
- Delivery: exact assistant-message/execution/operation/evidence binding, prior history unchanged, finalized text consistent across HTTP, final events, pin and reload.
- Streaming: foreign/stale frames cannot mutate another turn; burst frames are not silently dropped; deterministic no-token turns have correct completion semantics.
- Security: no unrelated inherited credentials, denied actions cannot fall through, retrieved instructions cannot create authorization.

## Coordination rules

Maintain a compact current-state table in coordination: lane, agent, owned files, source hash, tests, blocker and next action. Link detailed reports rather than adding another contradictory narrative. Each lane writes only its own status entry; one coordinator owns the overall support table.

One writer per shared file. No `git add -A`, broad reset, or history rewrite to untangle concurrent work. Prefer scoped commits once the user/request and repo workflow permit; preserve all unrelated changes.

Only this lane creates/rebuilds/restarts the final candidate. Unit tests use scratch stores. Storage relocation remains a separate scheduled operation; do not stop all servers, delete worlds, or swap paths while any acceptance writer is active. Honor the shared maintenance interlock. Disk pressure is reported and resolved deliberately, not through opportunistic deletion.

## Promotion and user handoff

Promote after the advertised manual workflows pass in the actual browser. Keep replacement excluded until its full chain passes. A preview may be useful before full readiness, but list excluded streaming/actions/recovery accurately.

Publish one current URL with a quickstart: login instructions without secret disclosure, fixture prompts, expected outcomes, limitations, safe restart instructions and feedback format. Leave it running where feasible. Preserve the previous preview until the new one is verified.

Readiness completion requires all critical required cases exercised and passing on the final fingerprint. Unexercised cases remain incomplete even if unit suites are green. Ranking optimizations beyond the measured correctness scope can remain documented follow-up work; do not let them delay the working preview.

## Completion package

- Final manifest and lane handoff hashes.
- Independent required-case accounting with per-case PASS/FAIL/ERROR/BLOCKED/NOT RUN and raw evidence references.
- Actual tool/effect counts, crash/restart records, message/evidence/pin associations and sanitized stream traces.
- Browser results and readable conversations from the same candidate.
- Test results, scoped changes, known limitations and rollback instructions.
- One short user-facing handoff stating what works now, where to open it, and what is still excluded.

Do not finish with assignments to nonexistent owners. If a lane finishes or disappears, explicitly transfer its remaining work and continue the authorized closeout.
