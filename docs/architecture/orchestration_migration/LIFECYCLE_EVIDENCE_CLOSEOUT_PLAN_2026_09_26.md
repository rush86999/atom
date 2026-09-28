# Lifecycle evidence and public-boundary closeout implementation plan

Date: 2026-09-26. Status: implementation work order; not acceptance certification.

## 1. Assignment

The receiving agent owns this plan end to end. There are no separate presumed identifier, integration, or harness owners. Implement the evidence fix, repair necessary harness prerequisites, launch an isolated server, run all required cases, diagnose failures, and produce the completion package. Coordination notes record work; they do not substitute for execution.

This plan continues the lifecycle work. It is separate from `AGENT_SEARCH_WORK_ORDER_2026_09_26.md`: do not expand this closeout into retrieval-ranking improvements, framework migration, or classifier redesign.

Read `AGENTS.md`, `CLAUDE.md`, this directory's lifecycle/workbook work orders, recent git history, and `notes/AGENT_COORDINATION.md`. Revalidate current code before editing. Follow the actual function names, not historical line numbers.

## 2. Baseline: established versus still unverified

The current repository HEAD at plan creation is `6995c7e27`, the transport projection/status fix. The agent reported export `e35e5765c8` and 219 passing tests. These identifiers describe the reported baseline, not a guarantee that the present working tree or next server is identical.

Reported structured evidence contains value-cell bindings for the six previously failing targets, but no exact identity-cell bindings. Examples include U-22 value C26/List Price/1777 and TK 1624 value D101/Price/8040. Treat these as fixture observations to independently verify, never production constants. The earlier identity check falsely matched A101 inside AA101.

Reported boundary evidence with M2 enabled proves one delivery ledger entry bound to the retrieve operation, exact assistant message, and matching answer hash. It does not establish every lane or restart behavior.

Reported keyed-request coverage: first send, same-key/same-payload replay, and same-key/different-payload HTTP 409. Restart survival remains unexercised. The runner previously omitted request_id entirely.

Unexercised boundary areas: token streaming, restart, denial/no-apply, overlap, operation-claim races, crash reconciliation, and actual mutation counts. Integration tests remain valuable but must not be relabeled as public-boundary coverage.

## 3. Non-negotiable operating rules

- Never use the live development DB for tests, destructive fixtures, or schema preparation. Use explicit isolated paths and verify opened database identity. Use the backup API when snapshotting active SQLite data.
- Export required tracked and untracked source into a fresh world. Do not rebuild the code under a running process. Resolve symlinks during verification.
- Start your own isolated server; do not reuse an existing listener. Preserve live development server and user data.
- Record exact loaded-module paths/hashes, process identity, launch identity, effective lifecycle/finalization flags, schema preparation and fixture hashes. Read effective server configuration, not client intentions.
- Preserve concurrent edits; coordinate with an actually active agent when necessary. No arbitrary commit/stage of unrelated changes.
- Use existing lifecycle, transport, finalizer, invocation-event, and isolation machinery. Do not introduce another finalizer or production keyword classifier.
- Keep all machine names, expected prices, and test faults in fixtures/test controls. Production code must remain generic.

## 4. Implement exact identity evidence

### 4.1 Trace before editing

Follow the identity-producing data through both live workbook scanning and saved/materialized reading in `backend/core/workbook_read_artifact.py`, structured-record construction in `backend/core/chat_tool_planner.py`, serialization/reload, and rendering in `backend/core/answer_presentation.py`. Audit all callers and compatibility paths.

Identify where a match is discovered, where the actual matched cell coordinate and content exist, and where they are lost. Do not assume identity lives in column A. Models, descriptions, aliases, or variant labels may occupy multiple cells or merged regions.

### 4.2 Contract

Extend the versioned artifact contract with identity evidence attached to each candidate, independent of its value evidence. Reuse equivalent existing fields if available; document exact serialization names before implementation.

Each identity reference must carry source identity/revision, sheet, exact cell/range reference, observed value, and the role of that evidence in matching the requested identity. Preserve multiple references when identity depends on several cells. Keep the requested label and matched source label distinct.

Each value reference retains its actual cell, value, basis/header, and units/currency when known. Identity evidence never stands in for value evidence. A compact display such as `LINMAC!R26` is a row locator, not an exact identity-cell reference and not proof of a price column.

Use parsed coordinates and exact comparisons. A101 must not match AA101; R26 row-display notation must not be confused with spreadsheet column R. Handle sheet-name quoting/case normalization deliberately and preserve source spelling for display.

For merged cells, identify the actual anchor/range from workbook metadata. For materialized data that lacks identity coordinates, retain an explicit unknown/unverified identity-binding status. Never reconstruct a cell coordinate from an item's position or invent one to satisfy acceptance.

Old records remain readable through a version-aware compatibility path, labeled with their limited evidence. Do not rewrite old delivered pins or imply an old record acquired evidence without a new read. Version any schema changes explicitly and document reader behavior for old versions.

### 4.3 Required regressions

- Original six targets: exact identity and value bindings verified independently from fixture cells.
- Identity in a non-A column; A101 versus AA101; merged identity cell; multiple identity cells.
- Multiple value bases in one row, including equal values; zero versus blank; ambiguous multi-row candidates.
- Two distinct variants on one row remain distinguishable when the source supports them.
- Structured serialization, reload, formatting reuse, and explicit re-search preserve references.
- Legacy record without identity coordinates stays explicitly limited rather than fabricated.

The renderer may keep compact row citations. Evidence disclosure must expose exact identity/value references. No extra diagnostic dump in the main answer is required.

## 5. Preserve evaluator integrity

Do not change frozen expected cells merely to make current output pass. Once production carries identity evidence, update the evaluator to inspect identity bindings and value/basis bindings separately, while also checking that the user-visible answer makes no unsupported claims.

Accept semantically equivalent bullet/table presentation without treating text parsing as stronger evidence than the artifact. Preserve raw answers. Include negative controls for wrong identity cell, wrong value cell, wrong basis/value, same suffix in another column, and missing evidence. Run baseline and candidate with the same evaluator version when comparing results.

Record failures by assertion. Do not label all target failures as one cause unless each failing assertion is mapped to that cause.

## 6. Verify and harden delivery/transport behavior

Inspect `backend/core/chat_transport.py` (`replay_projection`, `complete`, `stored_response`) and route callers. The projection fix is present, but current `complete` still catches persistence errors and logs them. Trace what the caller does on that failure: do not assume durable pin guarantees from a successful response alone.

Define the replay contract explicitly: immutable user-visible answer plus required response identity/status fields; metadata may be referenced by exact message/delivery identity instead of duplicated. If clients require metadata on retry, hydrate it from an immutable/versioned source or retain the required projection. Do not fetch “latest message” or permit later re-finalization to change the original retry response.

The projection is bounded by field selection, not necessarily by serialized byte size: message/reasoning fields may still be large. Test large and multibyte content, valid JSON, persistence, restart, and parsing. Never truncate serialized JSON or silently truncate the promised answer. If the store has a real size limit, use an immutable payload reference or an explicit pre-delivery failure policy.

Test pin-persistence failure after execution. The system must preserve/reconcile the operation and must not execute it again because the pin was unavailable. Return an explicit incomplete/uncertain completion state where needed; do not claim successful durable replay protection when persistence failed. Do not repeat external effects to reconstruct a response.

Keep intentional HTTP statuses, especially 409, intact. Verify first response and replay through the same public response schema. Ledger records remain `persisted_for_delivery` unless a bound acknowledgement is actually received. Re-finalization appends a distinct event without overwriting the original transport pin.

## 7. Build the fresh-world run

Use `backend/scripts/orchestration_acceptance/run_isolated.py`, its provider shim, and the existing acceptance runner. Extend rather than create a competing launcher.

Preflight must refuse execution if required modules/tables are absent, source hashes disagree with the launch manifest, the requested production flag is ineffective, or the process/database identity is wrong. Include M2/finalization configuration as well as lifecycle configuration, since the earlier zero-ledger observation was flag-dependent.

Record any fixture schema preparation using supported repository schema mechanisms and dialect-correct SQL; never silently reseed missing data. Schema setup belongs before measurement and is included in the manifest.

Supply relaunch configuration and a test-only token-bearing provider/shim response. A shim verifies transport behavior, not real-model quality; label that scope. Deterministic workbook turns may legitimately emit no tokens, so test their final events separately from token-bearing generation.

Fault injection must be isolated, explicit and scoped to one operation. Use barriers/events rather than timing guesses for concurrency and crash points. Never kill a shared server or mutate a live canvas to simulate a fault.

## 8. Required public-boundary matrix

Maintain the runner's existing independently defined required-case list and map every old case to the cases below. Add missing coverage; do not drop failures or redefine completeness from results supplied. Use stable IDs. All cases run despite previous failures, except genuinely dependent cases which must name their unmet prerequisite.

| ID | Scenario | Required evidence |
|---|---|---|
| C00 | Launch preflight | Exact process/source/schema/flags/database identity |
| C01 | Original eight-item ask | Ordered identities, exact identity and value/basis bindings, observed retrieval, operation and delivery linkage |
| C02 | Distractor history | Original/current task targets preserved without historical union |
| C03 | Formatting | Zero retrieval calls, new presentation action/delivery, exact previous message/hash unchanged in DB and public history |
| C04 | Explicit re-search | Actual new retrieval, new attempt, observed outcome; unchanged revision allowed |
| C05 | Same text/new request ID | A new intended request executes; no text-based dedup |
| C06 | Same key/same payload | Original answer/identity replay; zero additional execution/effect |
| C07 | Same key/different payload | HTTP 409; zero additional operation/effect |
| C08 | Large replay payload | Parseable pin and correct replay with large/multibyte metadata/answer; no slicing |
| C09 | Restart replay | Stop own server, restart same durable world from same source, clear process caches, replay original key unchanged |
| C10 | Finalization transform | Controlled failed execution; captured pre/post differ appropriately; final delivery/history/pin agree |
| C11 | Token-bearing stream | Connection readiness, execution-bound tokens/final event, reconstructed final answer equals HTTP/history contract |
| C12 | Deterministic completion | No tokens is valid; correct execution-bound completion and persisted answer |
| C13 | Overlapping reads | Distinct turn/execution/message bindings; no latest-session identity substitution |
| C14 | Denied/unpersistable edit | Zero edit/action/background mutation calls across all fallbacks; distinct public reasons |
| C15 | Declined/no-apply edit | Zero effects; claim not stranded; correct terminal state and honest answer |
| C16 | Single authorized edit | One observed mutation, operation reservation before effect, finalized persisted result |
| C17 | Concurrent same-key edit | Two requests/processes, one execution claim and one actual mutation; loser waits/replays |
| C18 | Concurrent conflicting payload | One accepted claim and one conflict; no second effect |
| C19 | Crash after claim/before effect | Confirmed worker loss, zero effects, explicit uncertainty and evidence-based reconciliation |
| C20 | Crash after effect/before completion | Exactly one effect; durable evidence reconciliation; retry does not duplicate |
| C21 | Slow live worker | Timeout alone cannot mark worker lost, release claim, or authorize duplicate mutation |
| C22 | Corrupt/partial source | Failed/partial retrieval distinguished from absence; failed outcome recorded; healthy evidence preserved |
| C23 | Legitimate absent/unknown source | No fabricated evidence; absence bounded to actual search coverage |
| C24 | Pin persistence failure | No blind effect replay; explicit recoverable/uncertain outcome; restored persistence reconciles safely |
| C25 | Cache-loss identifier inheritance | Original identifiers reach extraction after cache loss/restart, not merely no exception |
| C26 | Non-workbook task | Existing invoice or other generic fixture exercises evidence/delivery without workbook-specific rules |

For C19/C20, observe the real mutation at a controlled durable test sink or isolated canvas revision store, not merely an operation status. Reconciliation must use an operation-linked durable marker; incidental equality of canvas text is insufficient proof. Confirm worker identity/death, not a caller-supplied assertion alone. Do not send real outbound messages.

## 9. Execution order and completion gates

1. Baseline audit and trace; publish verified gaps and effective configuration.
2. Implement exact identity evidence plus schema compatibility and evaluator guards.
3. Validate transport projection, intentional statuses, and persistence-failure handling.
4. Prepare complete harness matrix, stream fixture, restart configuration, and actual-effect instrumentation.
5. Run targeted unit/integration tests and relevant neighboring suites on isolated stores.
6. Freeze combined source and launch fresh acceptance world. Execute all cases; preserve raw evidence and hashes.
7. Fix reproduced defects, create a new fingerprint for changed production code, and rerun affected cases. The final full matrix must use one final frozen implementation; do not assemble a green report from incompatible snapshots.

Pass requires every required case exercised and passing, correct original identities with exact evidence, no unsupported claims, no duplicated mutation, immutable retry pins, truthful failure/uncertainty, and consistent final delivery/history. Missing token provider, restart arguments, or request IDs are harness gaps to fix, not product limitations to declare indefinitely.

If a true external dependency prevents a case, name it and retain acceptance-incomplete status while finishing independent work. Do not call a partial case PASS because one safety subcheck succeeded.

## 10. Completion package

Place artifacts in the existing acceptance structure and link them from a closeout report:

- Source commit, dirty/untracked hashes if any, export archive hash, fixture/schema hashes, loaded module hashes, process/launch identities and effective flags.
- Versioned artifact contract and compatibility notes; before/after identity-evidence examples.
- Complete required-case accounting, per-case Boolean checks, errors, blocked reasons and raw public request/response references with secrets redacted.
- Actual invocation/effect counts, operation transitions, message/delivery/pin associations, restart/crash evidence, and stream events keyed by execution.
- Readable original eight-item conversation plus formatting, re-search, failure, and restart demonstrations.
- Exact test results and scoped changes; rollback instructions and unresolved limitations.

No completion claim based solely on test totals, one successful retrieval, a singular operation row, or a coordination note. The final result must demonstrate the app behavior through its public boundary.
