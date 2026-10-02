# Fresh-agent assignment: complete the chat-orchestrator preview

## Objective and authorization

Finish the remaining recovery, overlap, crash, and read-workflow acceptance work, then deliver a usable, explicitly scoped preview. This is an execution assignment, not a request for another plan. Work is already authorized. Do not stop to ask whether to proceed to the next listed case. Stop only for a concrete safety restriction or missing information that truly prevents progress; execute independent work meanwhile.

One writer owns this assignment through the final run. Coordinate file ownership before editing; do not create competing recovery implementations or parallel writers on the same harness/world. Read AGENTS.md and CLAUDE.md. Append only a short start/finish pointer to notes/AGENT_COORDINATION.md; it is large and contains contradictory historical conclusions. Do not read the entire log as current truth.

Scope: complete the existing mechanisms and fixed acceptance cases. No planner redesign, model comparison, new orchestration framework, storage relocation, broad cleanup, or replacement test framework. Prefer repairing the existing drivers. Commit only intended changes, preserving other staged/unstaged work. Direct pushes were authorized previously; this does not authorize sweeping other agents' changes into a commit.

## What to trust

Distinguish current source, exported source, serving process, configuration, fixture, and result identity. HEAD, a world name, and the checkout-derived runtime source_id do not prove what a process executes. The acceptance server runs a frozen export through backend_root. Editing the checkout does not update it; restarting alone may not rebuild it.

For each result record:
- code export tree SHA-256 and loaded application module paths/hashes;
- effective configuration, including provider pin, lifecycle/recovery flags, budgets and barriers;
- fixture identity and exact run database path;
- run ID, process ID/start identity, ports, execution/continuation/request/canvas IDs;
- timestamp, case preconditions, assertions, raw evidence paths and outcome.

Python closes source files after import: no open .py handles in lsof proves nothing. Verify the launch source and serving-module report, not open handles. Do not mutate an immutable export. If production changes are necessary, create a new candidate and rerun affected gates. Supporting evidence from another export remains supporting evidence, not a pass on the new one.

## Established evidence to preserve

| Area | Evidence/status to retain |
|---|---|
| Real-planner browser edits F06/F07 | write_verify_0928 / run-7240b4691cc1; recorded export f530c509948d947d; ports 8140/3140; disclosed ATOM_ASYNC_EDIT_PLAN_MODEL=deepseek/deepseek-v4-pro. Four successful body-edit runs, each 11/11; a second distinct payment-terms edit and legitimate decline. Preserve per-file provenance qualifications; later comparison was 15/16, not blanket serving equivalence. |
| F10 keyed replay/conflict/restart | Passing evidence exists on its recorded candidates. Correct field is metadata.replay_pin, not top-level replay_pin. Authoritative completed response is in chat_request_records. Do not reopen the corrected field-path bug. |
| Controlled F03/F04/F05/F08 | Passing reports/artifacts exist on earlier exports. Keep source-bound. A clean decline is not execution-time background failure; synchronous success is not a proven fork. |
| F02 | F02a historical wrong-field incident remains unexplained; evidence was lost. F02b current missing-target negative passed. Neither closes historical attribution. Keep widening-control coverage separate. |
| F09 | Public overlap passed on some earlier exports; current automatic post-lease recovery remains unverified in the latest assignment. Tests cover transaction-bound fencing and a two-process negative control. Integration tests do not replace the pending running-server proof. |
| F11 | Barrier-based passes and a later 6/7 partial exist on different exports. Retain both. Diagnose the exact failing candidate rather than combining results. |
| F12 | Final candidate's complete read workflow remains unexercised. An older preserved preview lost its database; do not reconstruct it in place. |

The unpinned model's decline cause remains undetermined. The verified pin supports a disclosed configuration, not all models. Use the pin for real-planner preview checks; use a declared controlled provider for crash-mechanism tests. Do not hunt credentials or copy secrets to a credential-free world. Use existing authorized provider configuration and normal product login.

## Immediate starting point: finish automatic recovery

Latest reported world: f09crash, export 7c0d299d2575…, latest run run-64a23e75fefd (earlier run run-8d5a96d2df88). Treat these as leads; verify files and live state before use.

What is already observed:
- recovery starts and repeats with ENABLE_SCHEDULER=false;
- background fork can be produced using the controlled planner/stall driver;
- continuation_after_claim parks after the claim and before terminal message persistence;
- the last attempt failed because the barrier timed out after 120 seconds while the driver waited. Delivery then completed normally. It was not a stranded-recovery test.

Do not repeat that attempt with a synchronous driver. Monitor barrier arrival concurrently with the public request.

### Procedure

1. Inspect existing driver entry points and their --help before constructing commands. Useful starting files:
   - backend/scripts/orchestration_acceptance/finish_line_cases.py
   - docs/architecture/orchestration_migration/acceptance/lane3/controlled_planner_c16.py
   - backend/scripts/orchestration_acceptance/run_isolated.py
   - backend/core/acceptance_barrier.py
   - backend/core/async_turn_continuation.py
2. Reuse the current small world if its exported code contains the required call site and barrier stage. Otherwise build a uniquely named small isolated candidate from the intended working tree. Snapshot mode may reuse an existing export; verify actual bytes. Do not rebuild a preserved world merely to refresh it.
3. Seed a fresh email canvas through the product API and supported update endpoint. Record audit counts after seed writes. An empty fixture does not require a full dev snapshot.
4. Launch a run-owned shim on a dedicated available port. Validate its instance/script identity, exact advertised tool selection, response envelope, parser acceptance, and actual consumption. A selected capture entry alone is insufficient. Use a valid ToolPlan response where requested.
5. Reuse the proven background configuration: the budget must allow the reserved reply leg; earlier 25-second budgets skipped editing entirely. Stall one exact CanvasEditPlan leg long enough to force a fork. Arm per-case, not a shared global counter. Do not rely on real-model latency or stall the reply leg.
6. Arm continuation_after_claim narrowly for the case session. Set ATOM_ACCEPTANCE_BARRIER_TIMEOUT above the bounded driver deadline. Choose a lease longer than measured kill/restart time, and a short recovery interval. The goal is restart BEFORE expiry, not a particular magic number.
7. Start the request asynchronously; watch the current run's arrival marker. Immediately query the server's exact run DB and verify: correct continuation/execution, active claim/token and expiry, no terminal message, worker alive, no barrier timeout/release. Record the baseline mutation audit count.
8. Kill only this run's recorded serving process/owned children while held. A timed-out barrier or pre-existing terminal message invalidates the attempt; do not relabel it a successful crash test.
9. Restart with the exact same run directory/database, no reseed, barrier disarmed, scheduling disabled. Verify startup occurs before claim expiry and the recurring recovery task is alive.
10. Leave this SAME process running. Observe recovery after expiry without a second restart or direct helper invocation. Require one correctly bound durable terminal message, truthful user-visible outcome, stable canvas audit count, and reload visibility. Record live notification/event evidence separately from durable history. Allow a bounded interval beyond expiry based on the configured scan interval.
11. Verify a later scan/restart adds no second durable row or canvas effect. Persist results immediately, including failed preconditions.

Do not confuse fork arbitration with terminal-delivery arbitration. Do not confuse restart-triggered takeover with recurring recovery. A lease permits takeover; the recurring caller supplies progress. A flag/claim does not prove delivery.

## Existing recovery code: inspect, do not duplicate

Checked in the checkout during this handoff:
- recover_missing_terminal_deliveries and start/stop_terminal_delivery_recovery exist in core/async_turn_continuation.py;
- main_api_app.py invokes recovery startup outside the scheduler gate;
- continuation_after_claim is present in the barrier module and delivery path;
- core/execution_recovery.py already has _recover_agent_executions and calls it from reconcile_orphaned_executions, including in commit d78613777.

CURRENT_SUPPORT_TABLE.md still says recovery covers only WorkflowExecution. That diagnosis is stale and must not drive a patch. If the F11 candidate leaves an AgentExecution running, inspect the loaded module, effective recovery flag, row status, owner metadata/verdict, query inclusion, exceptions and DB identity. Preserve verified-live and unknown-owner safety: only established dead owners are reconciled.

Reconcile any overlapping AsyncDeliveryLease and continuation claim fields through the existing design; do not add a third mechanism. The authoritative normal and recovery delivery path must use the same fence. Token validation and terminal-row insertion must be protected in one transaction. An expired original holder must not write after takeover. Preserve the two-real-process test whose disabled-arbitration control produces duplicates; worker crashes must fail the test, never masquerade as refused claims.

Fail-open arbitration intentionally permits duplicates when unavailable. Document that limit; do not claim unconditional exactly-once across DB, WebSocket and notification service. A canvas hash difference alone does not attribute a mutation to a continuation: use operation-linked audit evidence and postconditions, or report uncertainty.

## Remaining execution order

### F09 public overlap and delivery
Run on the updated candidate after automatic recovery. Both turns must actually fork when testing background overlap. Correlate terminal events and history by exact execution/continuation ID. Both must terminate, with truthful applied/failed/cancelled outcomes. A missing target after the competing edit can legitimately fail; silence cannot. Verify reload, no cross-turn substitution, no duplicate canvas effects, and duplicate terminal-event consumption separately from duplicate keyed requests.

### F11 after-effect crash
Use continuation_after_effect on a dedicated run. Prove operation-linked effect committed AND terminal completion unrecorded, kill while held, restart same DB disarmed. Require no repeated mutation, owner-aware reconciliation, and a terminal message that does not imply a verified landed effect never happened. Preserve original acknowledgment; append the correctly bound terminal outcome. If the sweep refuses an owner, diagnose the exact verdict; do not weaken it to satisfy the test.

### F12 read regression and manual preview
Seed the required workbook parquets and dataset index using existing fixture mechanisms, hash-check them, and start an isolated frontend/backend pair. Run the actual browser flows: login/general chat with an authorized real provider; eight-item lookup in requested order with evidence; replacement with honest absence where applicable; formatting without altering prior messages; explicit re-search with an observed new attempt; reload retaining the conversation. A canvas GET is not this test. Count retrieval from observed operations/stamps under the documented contract, not merely changed text.

Repair only a demonstrated failing boundary. Do not touch a dead preserved preview's DB. Keep PDF rendering, token streaming, cross-host claims and unrelated preferences bugs excluded unless already explicitly required for the advertised preview. Historical F02a is disclosed, not a new reconstruction project.

## Storage, processes and database safety

- Preserve :3000/:8001 and named previews :3102/:8071/:3140/:8140. Verify current ownership/status without restarting or recreating their data.
- Use world_storage_guard preflight/interlock and small API-seeded fixtures. No world deletion, cache purge, rollback deletion, portable-drive move or emergency cleanup under this assignment. If space is insufficient, stop new allocation and report inventory.
- Never remove WAL/SHM or use immutable=1 on a live WAL database. No ad-hoc code connects to the dev database.
- TESTING=1 can redirect DATABASE_URL; verify resolved engine URL before any fixture write. Use supported run-scoped provisioning and a separate read connection to confirm committed state.
- Read-only identity checks must not silently create a missing SQLite file. Missing DB means stop that probe.
- Record PID plus start/instance identity for every launched process. Cleanup must verify this run's ownership; matching script path or world cwd alone is insufficient. Refuse foreign listeners. Never kill all users of a shared port.
- Retain previous captures. Use unique per-run capture files and exact IDs rather than truncating evidence from other runs.

## Result accounting and completion

Use one current table with one row per case/candidate/artifact. PASS requires all mandatory preconditions and assertions. NOT REACHED/INCONCLUSIVE is not PASS. Never weaken an assertion to accommodate a discovered defect. Distinguish a scenario count from assertions per scenario. Save atomic per-case JSON under the persistent acceptance directory, not only /tmp or a disposable world.

Each case records required branch proof, before/after state, exact bindings, effect deltas, terminal text, restart behavior where relevant, source/config/fixture identity, and failures. Redact secrets and avoid dumping full user content into logs. Keep raw evidence sufficient to audit conclusions.

After the three remaining groups pass, run relevant changed-code tests and affected controlled smoke cases. Do not repeat every historical test without a reason. For a final preview advertising editing, exercise at least one real-planner browser edit and reload on that final export/configuration, or explicitly withhold that claim; preserved F06/F07 evidence remains valid on its original candidate.

Deliver:
1. one current support table and manifest with links to durable results;
2. working preview URL and existing isolated login procedure (no secrets in tracked docs);
3. exact disclosed planner configuration, supported workflows and exclusions;
4. short manual steps the user can follow immediately;
5. changed-file list, tests, unresolved limits and a clear promotion decision.

If interrupted, persist the last completed case, current owned process identities, and the single next command/action. Resume at the first unfinished case. Do not end a session merely because the next step is identified. No additional framework research, model comparisons, or status-only documents are needed to finish this assignment.
