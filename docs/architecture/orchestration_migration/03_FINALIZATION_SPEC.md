# Slice-1 Specification: Unified Finalization (Discovery Artifact 3)

References at baseline `39d6532d5`. Scope: replace response finalization for
the chat path behind the existing API. Finalization = the step that turns an
authoritative execution-outcome record into everything the user sees (final
text, streamed tokens, pending/background status) and into durable delivery
state. Anti-goal, stated up front: **this is not a relocation of the claim
regexes.** Prose-level guards are demoted to defense-in-depth; the source of
truth is the record.

## 1. In scope

All 13 terminal outcome classes of `process_chat_message` (01 §4 enumeration:
deterministic redeliveries, direct reads, planner-delegated replies,
canvas-edit results incl. no-apply, cancellations, CRM write, normal reply,
error/budget) route through ONE finalization contract. Background
continuation completions (`async_turn_continuation._apply_effects`) join the
same contract. The finalization layer absorbs the four scattered side effects
(`_update_session`, `_emit_agent_status`, `_finish_chat_execution`,
pending-task delivered-marking) and preserves the
`chat_token_done`-before-return ordering constraint.

## 2. Outcome record: four separated dimensions

One **execution-outcome record** per operation (02 §3), versioned, with
independent dimensions — a single tri-state cannot represent these, and each
dimension has its own producer and state machine:

| Dimension | Values (initial set) | Producer | Existing vocabulary mapped in |
|---|---|---|---|
| `execution_status` | `not_started → running → succeeded \| failed \| timeout \| superseded` | Execution layer, per operation | tool outcomes; continuation `failure_stage`; recovery stamps |
| `evidence_sufficiency` | `sufficient \| partial{missing_fields} \| insufficient \| contradictory` | Evidence layer | `evidence_ledger` keys; `workbook_read_artifact` coverage (found/ambiguous/absent/incomplete, `coverage.complete`) |
| `result_verification` | `verified \| unverified \| unsupported` — **per operation** | Verifier registry (02 §1) recompute; exact operation binding (02 §4); readback through the **canonical audit-first resolver** (`read_canvas`, canvas_crud_tool.py:121 — NOT `Canvas.content`); `review_status` tracked as a separate field | canvas `result_verified`→verified; `write_recorded`→unverified (with execution-proof note); claim-without-record→unsupported; `readback_matched` |
| `delivery_status` | `streaming → delivered \| partial_pending{operation_ids} \| failed_delivery \| pending_continuation{continuation_id}` | Delivery layer (this spec) | pending-task delivered/served; continuation outcome vocabulary; `derive_success_kinds.delivery_success` |

Rules:
- `unsupported` = a completion claim exists but the record contradicts it —
  this drives claim rewriting BEFORE delivery, never a post-hoc append.
- Dimensions are never folded into one task verdict inside the record;
  folding happens only in the derived contract-v2 projection (learning).
- Unknown stays unknown (tri-state discipline from `criteria_verdict`).
- `write_recorded ≠ verified` is preserved as execution_status=succeeded ∧
  result_verification=unverified.

## 3. Streaming pre-gate (claims are gated before tokens)

Current defect (01 §5): claim correction runs once, post-stream, on the
non-streaming return; streamed tokens can carry an unsupported completion
claim while only the HTTP final message gets corrected.

Specification:
1. **Interim events** (`agent_step_update`, `chat_heartbeat`) may state
   execution facts only (stage, tool, elapsed) — never completion claims.
2. **Executable strategy (slice 1): buffer–validate–stream.** The complete
   narrated answer is generated FIRST; the finalization gate validates the
   whole text against the closed operation records (every completion/change
   claim must map to a record verdict that supports it); only then are
   tokens released to the stream, chunked from the validated buffer.
   Prompt-side composition from the record is necessary but **not
   sufficient** — feeding an authoritative outcome into a prompt cannot
   guarantee generated claims respect it. The post-generation whole-text
   assertion check IS the guarantee: no token is released that has not
   passed it.
3. **Latency tradeoff (recorded, enforced)**: time-to-first-token becomes
   ~full generation latency (the old path streamed during generation).
   Limits live in `acceptance/thresholds.json` (TTFT ≤ old-path P50 + 2.0s;
   total ≤ 1.5× old-path P50, measured on the frozen cases). If the limits
   cannot be met, the response is NOT to trust the prompt — it is to design
   Option B before authority is granted.
4. **Option B (deferred, documented not improvised)**: incremental release
   of validated segments — non-assertion segments release as validated;
   assertion-bearing segments hold until their operations' records close.
   Requires a mid-stream assertion classifier with cross-segment claim
   tracking; the demoted regex chain is defense-in-depth and insufficient
   as that classifier. Option B is a designed follow-up gated on measured
   TTFT failure of Option A.
5. The existing sentence-regex chain (`_canvas_claim_correction`,
   unverified-confirmation, absence-claim guards) runs INSIDE the gate as a
   defense-in-depth assertion check, not after streaming.
6. `chat_token_done.content` is populated from the gated text; the
   empty-content fallback (frontend keeps streamed text) is removed for the
   new path because gated text is the only text that ever streamed.
7. Deterministic legs (direct reads, redeliveries) already compose from
   structured results — they pass through the same gate with
   model=`deterministic`.

## 4. Background completion binding

- Completion messages are constructed **from the persisted record of the
  bound continuation_id**, asserting only its outcome vocabulary
  (`applied | awaiting_approval | already_applied | conflict | failed |
  cancelled` — note `awaiting_approval` is a draft state, not completion).
- The message carries `{continuation_id, originating_execution_id, outcome,
  result_verification, delivery_status}`; `originating_execution_id` is
  already persisted (async_turn_continuation.py:353) — formalize it as the
  binding contract.
- Rows landing after the synchronous reply update the operation's record;
  the completion message reflects the record, not a re-scan heuristic.
- `notified=True` must be set only after delivery channels succeed (fixes
  the unconditional set at :418).
- **Close the loop with the frontend**: `chat_continuation` currently has **no
  confirmed non-test handler** (01 §5) — slice 1 includes a frontend
  consumer for the bound completion message.

### Durable delivery and crash recovery

- **Delivery identity**: a `delivery_id` (uuid) is minted and persisted with
  the operation record BEFORE any send. Retries reuse the same
  `delivery_id`; the client deduplicates by it.
- **What "delivered" means (three tiers, never conflated)**:
  `available` = persisted for retrieval (ChatMessage row written);
  `transport_accepted` = the send returned without error (WS send completed
  / HTTP response returned); `client_acknowledged` = the frontend acked
  citing the `delivery_id`. `delivery_status=delivered` requires ≥
  `transport_accepted`; background completions require at minimum durable
  `available` state plus one transport attempt, with acknowledgement as
  CONFIRMATION rather than a requirement (offline users are covered by the
  retry/offline rule below).
- **Retry, offline users, and the crash window**: bounded retries (3
  attempts, backoff, within a 5-minute window) with the same `delivery_id`;
  the client deduplicates by it. A crash between send and recording success
  leaves the delivery row un-acked; restart replays idempotently under the
  same id — the worst case is one duplicate transport, never a divergent
  claim, and client dedup makes it invisible. **Offline semantics**: the
  completion persistently remains available for later retrieval (durable
  row + session hydration), and a pending acknowledgement is NEVER treated
  as execution failure — the execution outcome settles independently of
  delivery progress. After the retry bound is exhausted the delivery
  settles as `delivered_retrievable` (persisted, surfaced on next session
  load); a later client pull or ack upgrades it to `client_acknowledged`.
  The `notified` boolean flag is REPLACED by this delivery record (fixes
  the unconditional set at async_turn_continuation.py:418).
- **Finalizer-version binding**: `finalizer_version` is stamped on the
  persisted execution at turn start and inherited by continuation records.
  Recovery, notification, and continuation-completion paths render through
  the stamped version — a restart or a background continuation can never
  switch finalizer versions mid-operation. Frontend work in this slice:
  ack emission and dedup by `delivery_id`.

### Historical evidence re-delivery (ruling)

Re-delivering persisted evidence does NOT require fresh retrieval when ALL
of: (1) the originating operation binding validates (the result's operation
record exists and matches), (2) the extraction-contract version matches the
current artifact contract, (3) the source scope matches the current ask
(same file/scope constraints). The delivery MUST disclose evidence age
(ingested/retrieved timestamp, content hash). **Refresh is a separate
operation** — its own operation record, triggered explicitly, never a
silent side effect of re-delivery. `allow_persisted_evidence=True` is legal
only under these validations; the pending-file-task redelivery path
(chat_orchestrator.py:4059–4182) adopts them, with its pinned tests updated
in the slice.

## 5. Single finalizer, authority, rollback, deletion

- **Single-finalizer invariant**: exactly one finalization path executes per
  turn. Dispatch reads the capability flag ONCE at turn entry
  (`core/feature_flags.py`, e.g. `CHAT_FINALIZATION_V2`). No mid-turn
  fallback: if the new path fails, it produces a structured
  `failed_delivery` outcome THROUGH the new path. Two simultaneous
  finalizers is a defect class, not a transitional state.
- **Authority**: threshold-gated, not time-gated. The new path becomes
  authoritative for a capability when the frozen acceptance suite
  (`acceptance/cases.json` + `acceptance/thresholds.json` — all five case
  classes, sample counts, zero-tolerance rules, and latency limits) passes
  on the pinned inputs AND zero old-path invocations occur for that
  capability after ramp. Elapsed clean time (14 days) is **supplementary**
  evidence, never the primary gate.
- **Rollback**: flag off at turn granularity. The execution-outcome record
  is additive (new storage keys, no migration of existing rows), so rollback
  requires no data change. Shadow-read (not shadow-write) comparisons may
  run during ramp: read-only paths only.
- **Deletion**: old-branch code (the outcome-class returns it replaces, the
  post-streaming guard chain for those classes) is deleted per capability
  after authority, in the same commit as its tests moving to the new path.
  Retire with the branch — no permanent dual maintenance.

## 6. Acceptance for slice 1

1. Original incident verbatim (`acceptance/cases.json`, TRUE-EIGHT target
   set with frozen per-target ground truth): completion claims in the final
   text match record verdicts exactly; no claim reaches tokens that the
   record does not support.
2. Unrelated domains (≥2 non-workbook): same gate behavior, no
   workbook-specific branching in the finalization layer.
3. Overlapping executions (constructed): per-operation verdicts; no
   cross-verification between concurrent turns on one session/canvas.
4. Restart recovery: continuation killed mid-write → honest terminal state,
   one bound completion notification, no duplicate delivery.
5. Partial failures: write-recorded-but-unverified, evidence-partial, and
   budget-timeout turns each produce their distinct honest delivery class.
6. Regression: existing pinned tests for pending-task resume, continuation
   idempotency, and canvas no-apply pass unchanged (or with test moves
   justified in the PR).

### M1 scope limit (review round 19)

M1 is FINALIZATION ONLY. Its structural additions are limited to the
operation identity and lifecycle information the finalizer needs
(operation records with parsed/validated/applied/rejected/discarded
transitions and delivery evidence). Objective-resolution and
revision-lineage migration belong to LATER slices unless a concrete
finalization dependency requires them now — none is currently identified.
Acceptance: cross-domain cases must be MEASURABLE on the old path (not
necessarily passing — known failures are frozen as evidence); the NEW path
must meet the acceptance criteria.

## 6a. Two-tier evidence model (review rounds 13–14)

Sequencing rule: the OLD-PATH baseline must never require events that only
the new implementation emits — migration readiness cannot depend on
completing the migration.

- **Old path (baseline)**: measure OBSERVABLE criteria only — user-visible
  output, canonical readback (audit-first resolver), persistence, and
  duplicate-delivery effects. Internal processing remains UNKNOWN where
  instrumentation is absent; that is a documented limitation, not a blocker.
- **New path**: additionally requires exact execution/response-bound
  lifecycle events (see below). Both paths are COMPARED on the same
  user-visible outcome criteria.
- Lifecycle statuses `parsed | validated | applied | rejected | discarded`
  are TRANSITIONS — different stages, never interchangeable forms of
  success. They are recorded as a transition sequence per response;
  DELIVERY has its own separate evidence (the delivery tiers of section 4).

## 7. Non-goals

- No change to contract v2 semantics (learning freeze preserved).
- No new orchestration framework; no workflow-stack reuse beyond patterns.
- Incident-domain vocabulary stays in fixtures, never in this layer.
- Not migrating task resolution, retrieval, or mutation execution in this
  slice — only the finalization seam that consumes their outputs.
