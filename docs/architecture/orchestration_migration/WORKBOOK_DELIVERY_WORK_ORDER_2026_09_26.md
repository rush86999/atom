# Workbook answer delivery: implementation and acceptance work order

Prepared 2026-09-26 from the current working tree. Starting HEAD observed: `2cdc2f98b`; relevant changes are uncommitted. This is a source review and implementation directive, not a certification of the live server. Two database-free reproductions were run; the full acceptance suite was not rerun for this review.

## Objective and authority

Complete the existing workbook presentation work. The original request must produce exactly the requested items, preserve evidence meaning, honor presentation changes, and deliver consistent finalized text through HTTP, actual streaming, saved history, and transport retries.

Implement the steps below in order. Do not replace implementation work with more handoff documentation. Preserve other streams' changes. The integration owner owns the complete result, including resolving dependencies with the harness owner; an ownership handoff is not completion.

The required original ask is:

> find the prices of these 8 machines in Consolidated Price List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16

Its ordered item list is authoritative. `GSL24-16`, `SLE16-8`, and `U-38` are not substitutes. Put these specific names only in fixtures/tests, never in production routing or rendering rules.

## Verified findings that must drive the changes

Line numbers are navigation hints for the reviewed tree; locate by symbol before editing.

1. `integrations/chat_orchestrator.py`, presentation branch around 4206–4255: the code calls `present_from_record`, then chooses `_pinned_serve or _re_core`. Therefore an explicit formatting follow-up can discard the newly rendered answer. `test_renderer_drift_serves_pin` in `tests/test_workbook_structured_delivery.py` explicitly requires this incorrect behavior for the message “make it cleaner.”
2. `core/answer_presentation.py::_find_target` first matches normalized labels, then accepts substring matches. A database-free reproduction confirmed `_find_target([{"item":"381mm","aliases":[]}], "381")` returns the wrong target. The stricter behavior of `resolve_requested_items` does not protect this later lookup.
3. `chat_orchestrator.py::_update_session`, around 13697–13725: it derives the execution ID from the response/current turn, then unconditionally overwrites it with `session['_last_execution_id']` when present. That session field is assigned elsewhere, around 4922. This is a concrete possible cause of incorrect row attribution. It is not yet a proven cause of the frozen incident.
4. Ask/direct lanes call `mark_delivered` before returning to `chat_routes.py`. The route subsequently calls `_finalize_chat_response` and `_persist_finalized_outcome` around 1782. Comments claiming “pin after finalization” do not change this order.
5. Production already has `chat_routes.py::_persist_finalized_outcome` around 1271. It scans up to 50 assistant rows, selects an exact execution ID from parsed metadata, updates content, and commits. Missing rows return silently. It does not synchronize the nested pending-result delivery pin or the in-memory projection. Do not design the fix as though this writer does not exist.
6. The overlay is different: `m1_overlay/apply.py` uses metadata `LIKE '%execution_id%'`, selects the first match, silently accepts no match, and skips updates based only on a marker. Its presentation guard can change the response after the history/pin update. It is not an exact-message implementation and cannot certify production.
7. `ChatMessageRequest` currently has no explicit request identity. The inspected chat route/orchestrator does not provide a demonstrated keyed transport-idempotency path. The helper test called “transport retry” sends the new message “go”; the runner resends `RESEARCH` without a key. These test conversation redelivery or repeated asks, not transport identity.
8. The latest `pending_file_task.py` has replaced the word detector with `is_represent_request`: absence of a file, extracted targets, question mark, or selected actions is treated as presentation. This is still inference by exclusion, not positive presentation intent. Removing presentation keywords did not establish correct classification.
9. `_build_workbook_structured_record` defaults `retrieval_observed=True`; its caller infers observation from nonempty records, artifact existence, or file entries. Successful empty reads and actual invocation counts require boundary evidence, not object existence. `unobserved` must not automatically mean `read_failed`.
10. `build_targets_from_scan` groups every candidate by sheet/row and pools its values at target level. `_render_target` shows an unlabeled first candidate value for ambiguous products. `present_from_record` carries presentation intent in metadata but does not use it to select a rendering format. Requested fields are reported in metadata but the renderer does not use them to select values.

## Step 0 — Establish a reproducible implementation snapshot

Owner: integration owner with harness owner.

- Read current coordination notes and diffs. Record commit SHA plus SHA-256 hashes for every changed production and harness file, including untracked files.
- Export the current reviewed working tree into a fresh isolated world. Do not silently combine an old exported revision, a new helper, and an old seam.
- Test production code directly for slice-2 acceptance. Retain the old overlay only for explicitly labelled historical-baseline tests. Do not inject a second finalizer into production exports.
- Record effective M1/M2/M3 flags at process startup, server instance identity, export path, database path and fixture hash. Verify flags from server-side state, not a client CLI assertion.
- Require the server's test-world identity to match the DB inspected by the runner. A DB pathname containing `acceptance_worlds` does not establish that the HTTP server uses it.
- Never direct mutation acceptance at the live development database or port 8001. Use a fresh isolated database and port. Follow repository restart/snapshot rules for any later development-server verification.

Exit: one manifest identifies precisely what source and state each test executes.

## Step 1 — Repair the acceptance runner before trusting its verdict

Owner: harness owner. File: `backend/scripts/orchestration_acceptance/live_integration_acceptance.py`.

Required changes:

1. Replace metadata-copy counting with test instrumentation at actual retrieval and renderer entry/exit boundaries. Include `request_id`, `execution_id`, unique invocation ID, start/end, outcome, and evidence revision where available. Keep raw private payloads out of event logs. Instrument scan execution and provider refresh separately; a catalog listing is not a content scan.
2. Distinguish retrieval attempts from low-level calls. One attempt may perform multiple calls. Repeated storage of the same artifact on multiple messages must never count as additional retrieval. Assert correlations using IDs, not timestamps or log phrases.
3. Remove the arithmetic `len(recs2) - recs_before`: it mixes per-window and cumulative populations. Remove or implement the ignored `since_ts` argument. Avoid one-second window tolerances as turn identity.
4. Bind all history reads to the returned assistant-message ID and execution ID. Remove `ORDER BY ... LIMIT 1` and metadata substring matching as acceptance selectors. Query the public history API as well as the DB; a direct SQL read alone is not reload verification.
5. Use a real request identity for step 4 after Step 3 below implements it. Repeating the same text without identity is a new user request and must remain eligible to run again.
6. Finalization-change assertions must compare captured pre-finalization content with post-finalization content. “Execution failed and a stock success phrase is absent” does not prove a transformation.
7. Fix step 5's overwritten `details` dictionary, and compare the exact selected message rather than calculating `hist_content` and then asserting against another row.
8. Fix `all_pass`: every required step must be exercised, have nonempty checks, have every check true, and have no error. Boundary verification must be true. Streaming text equality must participate. No skipped required step may pass. A database-free reproduction of the existing expression returned true with step 5 skipped and step 6 text equality false.
9. Separate status from explanatory notes. Constants such as `unchanged_revision_valid=True` are notes, not assertions. Continue independent steps after failures; mark dependent steps BLOCKED with prerequisite IDs rather than manufacturing misleading results.
10. Filter websocket events by the exact session/execution/request. `run_isolated.py::WSTap` currently concatenates user-channel token events without those filters. Await websocket subscription readiness; fixed sleeps are not a readiness handshake.

Add runner unit tests proving each false-positive case fails, including a skipped required step, missing instrumentation, failed streaming equality, duplicate metadata copies, unrelated websocket events, and the wrong server/DB pairing.

Exit: deliberately broken implementations produce deterministic failing reports.

## Step 2 — Correct identity and request semantics

Owner: integration owner. Primary files: `core/pending_file_task.py`, `core/chat_tool_planner.py`, `core/answer_presentation.py`, and the early continuation branch in `integrations/chat_orchestrator.py`.

### Requested items

- Use the current resolved objective's explicit ordered item list as presentation authority. Probe tokens and historical aliases are subordinate search aids.
- Keep latest explicit replacement lists separate from older lists. Formatting and re-search follow-ups inherit the active objective; they do not union historical model mentions.
- Preserve user-facing names. Use stable item IDs and explicitly attached aliases for lookups. Remove `_find_target`'s substring fallback; unresolved correspondence stays unresolved.
- Preserve valid long names. Replace arbitrary word-count rejection with explicit list and turn boundaries; add tests for names exceeding both four and six words, lowercase names, quoted names, and multi-turn text contamination.
- Test `381` versus `381mm`, `U-2` versus `U-22`, distinct brands sharing a numeric suffix, and all eight original items.

### Presentation and retrieval intent

- Remove `is_represent_request` as an authoritative routing rule. “Not obviously something else” is not evidence of a formatting request.
- Extend the existing structured routing path (`ToolPlan` routing fields / `_intent_from_tool_plan` and the existing NLU fallback) with an explicit continuation decision. Resolve it before the early cached-result branch can return. Do not start speculative retrieval while awaiting that decision.
- Carry two independent fields: retrieval operation (`none`, `read`, `rerun`, `refresh`) and presentation preference (`default`, `compact`, `table`, plus existing supported options). Carry the referenced objective/evidence identity. A compound request can contain both `rerun` and `compact`.
- If classification is unavailable or ambiguous, use the established fallback/clarification flow. Do not intercept unrelated conversation and re-serve workbook results.
- Regression examples: “thanks,” “stop,” “that is wrong,” “explain the difference,” “use factory price,” “make it a table,” and a new unrelated statement. Specify each expected route in tests; none should be forced into presentation by absence of punctuation.

### New formatting turn versus transport retry

- A formatting follow-up is a NEW turn and delivery. Render from existing evidence, finalize, and create a new delivery pin. Preserve the previous message/pin unchanged.
- Delete `_pinned_serve or _re_core` from the formatting branch. Do not call `serve_on_transport_retry` there.
- Replace `test_renderer_drift_serves_pin`: for a formatting follow-up, an old pin and a deliberately different new render must yield the new finalized render, while the old message remains unchanged.
- Make presentation preferences affect rendering. A new presentation-action record alone is not proof that “make it a table” was honored.
- Use the pin only for a transport retry identified as the same request under Step 3.

Exit: original items are correct, formatting changes take effect, and compound requests preserve both intents.

## Step 3 — Implement actual transport request identity

Owner: integration owner, including the calling frontend.

The existing conversational redelivery branch is not transport idempotency. First verify whether an applicable shared idempotency mechanism exists beyond the reviewed chat files; reuse it if present. Otherwise add a backward-compatible optional `request_id` to the chat request contract and a durable chat request record.

Required semantics:

- Scope uniqueness by authenticated user, session, and request ID. Store a hash of the accepted request payload, execution/message IDs, state, and finalized response payload.
- Same identity + same payload after completion returns the stored finalized response without execution, retrieval, rendering, or duplicate history rows.
- Same identity + different payload returns a conflict. Same identity while in progress returns an explicit in-progress result; it must not launch a second execution.
- Identical text under a NEW request ID is a new request. Two intentional “search again” turns must perform two attempts.
- Clients create one ID per submitted turn and retain it only for network retries of that turn. Update the canvas client and any other chat sender using this contract. Keep old clients working; requests without IDs receive no claimed transport-dedup guarantee.
- Reserve the identity transactionally before running the orchestrator. Persist completion together with the finalized message/pin. Retain in-progress state across crashes; do not blindly repeat a possibly completed side effect.
- Add concurrency, payload-conflict, restart, and response-loss tests. A transport retry uses the entire original request, including context, not a reconstructed subset.

Exit: transport idempotency is proven independently of conversational intent.

## Step 4 — Establish one authoritative finalized delivery

Owner: integration owner. Reconcile `_update_session`, `_finalize_chat_response`, `_persist_finalized_outcome`, existing M3 stream reconciliation, and the retry pin.

Implement this order for the affected paths:

`render → reconcile claims/finalize outcome → persist exact finalized message + pin + request completion → publish final response/event`

Do not move all finalization into the orchestrator merely because the overlay failed. Retain the existing route finalizer as the authoritative HTTP boundary for this slice; refactor its persistence step into a shared final-delivery function that streaming completion can also use. Earlier orchestrator records may exist as provisional records, but they are not final deliveries.

Required changes:

1. Allocate and propagate the exact assistant-message ID from the initial writer. Execution identity must be explicit per turn. Remove the overwrite by `_last_execution_id`; shared session fields cannot override response/turn identity.
2. Bind the final write by message ID, session, authenticated scope, and execution ID. A missing or mismatched row is an explicit failed persistence outcome, not successful no-op. Never select latest-in-session or use JSON `LIKE` as identity.
3. Write final text, content hash, finalization version, evidence/action references, and the delivery pin atomically with request completion. Update the nested pin used by the retry reader, not a different top-level location that the reader ignores.
4. Update the exact in-memory history entry and current-result projection only after commit. Do not rewrite prior completed turns. Ensure a later session save cannot reintroduce provisional text or an obsolete pin.
5. An idempotency marker is valid only when identity, finalization version and content hash agree. A marker alone does not authorize skipping a repair.
6. On commit failure, do not mark the request delivered/completed. Return a structured persistence error through fields actually serialized by `ChatMessageResponse`; an arbitrary response dictionary field may be dropped. Keep safe outcome information available and the request recoverable.
7. Capture the frozen case with pre-write hash, matched-row count, commit result, independent post-commit readback, and subsequent writes to that message ID. This proves whether the failure is skipped write, wrong identity, rollback, or overwrite.
8. Preserve existing feature-flag behavior and M1–M4 guarantees. Run the existing seam, outcome persistence, stream reconciliation, and continuation suites. Do not “fix” the frozen application exception to make failure-reporting acceptance pass.

Exit: the final HTTP message, the exact saved assistant row, the pin, and history API agree for both successful and transformed-failure outcomes, across restart and overlapping turns.

## Step 5 — Preserve evidence meaning and source freshness

Owner: scan/presentation owner.

- Instrument actual retrieval entry/exit. Remove the default `retrieval_observed=True`. A successful zero-match read is a completed read; failed I/O is a failed read; missing observation is unverified, not proof of failure.
- Allocate attempt identity before retrieval and bind all invocation outcomes to it. Persist failures as well as successes. A metadata copy is not a new attempt.
- Retain source mode separately from read outcome: a new read of a saved copy is not a live-source refresh. An unchanged hash is permitted after a real read.
- Copy structured records deeply or serialize on persistence so later mutations cannot alter historical evidence/actions.
- Preserve candidate-to-value association, sheet/row/cell references, original bases, raw values, and explicitly known currency/formula state. Do not flatten values across product candidates and show an unlabeled first value.
- Apply requested fields. Where selection is unresolved, show labelled alternatives or a focused clarification. Do not choose the first stored value simply because it comes first.
- Collapse same-row citations only when the source artifact establishes one product identity there. Keep distinct row variants separate.
- Fix the coverage key mismatch: the producer supplies `scanned_sheets`, while the renderer reads `scanned_entries`. Normalize the schema and test incomplete/truncated coverage explicitly.
- Keep full evidence available separately. The main answer should be a compact table or list with one row/entry per requested item and one useful source note. Hide execution IDs, hashes, record versions and re-render markers from ordinary prose.

Exit: concise output preserves identity, values, requested fields, and uncertainty. Character count alone is never a gate.

## Step 6 — Safe fixture lifecycle and actual streaming

Owner: harness owner with integration owner.

- Give each run a fresh database directory. Create consistent fixture snapshots with SQLite's backup API. Verify database integrity before and after the run.
- Do not delete WAL/SHM beside a live database. If reusing a disposable world, stop and confirm termination of every process using it before replacing the entire database set. A checkpoint while the server remains active is not a guarantee against subsequent writes.
- Remove the claim that SIGKILL alone explains corruption. Record the observed cause and integrity evidence; preserve failed worlds for diagnosis.
- Use a token-bearing fixture for streaming. Collect exact turn-scoped token and completion events. Compare the client-assembled final message with HTTP, history, and the pin.
- If the protocol uses final replacement events, replay those events through the client's assembly semantics; concatenating all raw chunks is not equivalent. Also assert that unsupported claims are not leaked before replacement where the existing M3 contract requires holdback.
- Zero tokens means NOT EXERCISED, never streaming PASS. Include an unrelated simultaneous stream to prove event isolation.

## Mandatory acceptance matrix

| Case | Required proof |
|---|---|
| Exact original eight-machine ask | Exact ordered identity list; actual scan events; durable structured evidence; eight readable entries; no substitute products |
| Same case with historical distractors | Previous different item lists and alias mentions cannot alter the active eight |
| Formatting follow-up, new request ID | Zero retrieval invocations; renderer invocation; new presentation action/delivery; old pin unchanged; requested format honored |
| Compound re-search + clean, new request ID | Actual retrieval; new attempt; both intents preserved; unchanged evidence revision allowed |
| Same completed request ID and payload | Original finalized response; zero execution/retrieval/render calls; no duplicate messages |
| Same text, different request ID | New explicit search executes; no text-based transport dedup |
| Finalization transforms failure | Captured before/after differ; correct failure; exact message ID; HTTP/history/pin hashes equal |
| Restart then history/retry | Public history and retry retain original finalized text and evidence association |
| Two overlapping turns in one session | No execution-ID overwrite, row cross-update, or cross-turn pin use |
| Token-bearing stream | Correct turn selected; final assembled text equals persisted delivery; claim holdback contract retained |
| Forced retrieval/persistence failure | Honest outcome; no fabricated new-read/delivered stamp; explicit error; no false all-pass |

## Completion package — deliver this, not another progress summary

1. Source/runtime manifest and exact commands for reproducing the isolated run.
2. Corrected runner JSON with every mandatory case PASS; no skipped or unobservable required checks.
3. The actual readable eight-item answer from the public endpoint, plus the formatting and compound follow-up answers.
4. Turn-scoped invocation events, IDs, and hashes proving retrieval, rendering, finalization, persistence, retry, and stream claims.
5. Appropriate regression suite results with existing failures distinguished from new ones.
6. A UI check on the requested canvas once its separate network error is resolved; verify displayed answer and reload. Report that gate open if it remains inaccessible.
7. Scoped diff/commit references and updated coordination status. Do not stage unrelated files or include credentials/private exports.

The overall task stays OPEN until this package demonstrates the required behavior. Helper tests, compact output, comments, and handoff ownership are supporting evidence only.

## Research basis and limits

- [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests) documents keyed replay of the stored response and rejection of mismatched parameters. Apply that pattern to chat request identity; do not infer identity from repeated natural language.
- [SQLAlchemy: session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) describes transaction framing and session identity-map behavior. Commit and independent readback are distinct evidence; absence of an exception does not prove the desired row changed.
- [SQLite: online backup API](https://www.sqlite.org/backup.html) provides consistent snapshots of active databases. Use it instead of copying a potentially active main DB file.
- [SQLite: WAL](https://www.sqlite.org/wal.html) states that WAL is part of persistent database state. Do not detach it from its database or delete it while live connections depend on it.
- [Anthropic: building effective agents](https://www.anthropic.com/engineering/building-effective-agents) describes routing as explicit classification into appropriate downstream paths. This supports using the existing structured routing mechanism; it does not prove any particular classifier is accurate. Evaluate the repository's concrete follow-up cases.

These are design references, not evidence that Atom currently satisfies the guarantees. The boundary tests above supply that evidence.
