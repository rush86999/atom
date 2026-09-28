# Outcome Contract Gap Analysis (Discovery Artifact 2)

References at baseline `39d6532d5`. Subject: whether
`core/task_outcome_contract.py` (v2) can serve as the execution-state model
for the migration, per the approved plan's five verification points:
objective revisions, operation identity, concurrency, recovery, compatibility.

## 1. What contract v2 already provides (stronger than assumed)

- **Trusted-provenance verifier registry** (`register_criteria_verifier`,
  :318; `TRUSTED_*_ORIGINS` :330–336): claimed criterion results count only
  when a registered verifier **recomputes agreement from raw evidence**
  (`_cross_check_results` :339–370, `criteria_verdict` :373–431). Registered
  kinds: retrieval, calculation, source_comparison, mutation/scheduling.
  A model assertion of "met" is never trusted. This is exactly the mechanism
  a unified verification layer needs — **reuse it, do not rebuild it**.
- **Mutation verifier with readback** (`_mutation_verifier` :501–521):
  requested-fields vs `mutation.readback.fields` equality;
  `readback_matched` short-circuit. This is requested-change verification
  semantics, already code-enforced.
- **Evidence ledger** (`_normalise_evidence_ledger` :181; known/missing/
  conflicting/incomparable/unverified/covered/total) and coverage statuses in
  `workbook_read_artifact.py` — evidence-sufficiency semantics exist.
- **Independent success kinds** (`derive_success_kinds` :564–641):
  `task_success` / `tool_success` / `delivery_success` tri-states with
  explicit bases — already refuses to collapse execution, evidence,
  verification, and delivery into one value.
- **Versioning precedent**: `CONTRACT_VERSION = 2`; `attach_to_execution`
  (:765) persists atomically with `learning_event` metadata.

## 2. Gap analysis — the five required points

### 2.1 Objective revisions — GAP
`objective_state` (:94–114: goal, target_entities, requested_attributes,
source_constraints, authorized_actions) is a per-turn snapshot. There is no
lineage: when turn N refines/supersedes turn N−1's objective (the
"original-objective replay" lane), nothing in the contract records
derivation. `supersedes` exists only in `pending_file_task` (:403–408), a
different record. The new model needs an objective-revision chain
(objective_id, supersedes_objective_id, basis for refinement).

### 2.2 Operation identity — GAP
One contract per `execution_id`/`turn_id`. But the canvas lane already runs
on **two** operation identities: the turn's execution id AND the
continuation id stamped as `operation_id` on background writes
(async_turn_continuation.py:996, binding map chat_orchestrator.py:6500–6521).
A turn with multiple mutations (and a background continuation landing after
the reply) cannot be represented; the canvas guard's whole-turn single
verdict is a direct symptom. The new model needs per-operation records:
`(operation_id, class, requested_change, execution_id, continuation_id?)`.

### 2.3 Concurrency — GAP
The only exclusion mechanism in the system is `AsyncContinuationClaim`
(session-scoped atomic insert). Nothing models **overlapping executions on
the same session/canvas** (two live turns racing): audit binding by exact id
is correct under overlap (the round-5 fix removed proximity binding), but
verdict computation, served-revision comparison, and `metadata_json` writes
have no concurrency semantics (read-modify-write of `metadata_json` in
`attach_to_execution` :779–787 is last-writer-wins).

### 2.4 Recovery — GAP
The contract is written once at turn end. It is unaware of: the startup
recovery sweep (`execution_recovery.py` converts RUNNING→FAILED with
`recovery.crashed` stamps), continuations that die at restart (deliberately
not resumed; user notified once via the `notified` flag), and
retrieved-but-undelivered pending-file results that re-render on a later
turn. The new model needs a lifecycle that can be re-opened by recovery and
by continuation completion, with each transition stamped by who/when.

### 2.5 Compatibility — CONDITIONAL
Learning consumers are mid-frozen-evaluation (coordination log 2026-09-24:
frozen evaluation executed, negative result retained; learning-loop freeze).
Changing v2 semantics in place risks contaminating that experiment. v2 also
persists into the contended `metadata_json` implicit schema (01 §2.2).
Compatibility is best preserved by NOT extending v2's semantics at all.

## 3. Recommendation: COMPOSE, don't extend

Introduce a separate **execution-outcome record** (per operation, versioned,
its own storage keys) as the authoritative execution-state model; contract v2
remains the turn-level reporting/learning projection, **derived** from the
new record by the existing builder path, its semantics unchanged:

- The new record owns the four dimensions (03 §2) and the five gap points.
- Verdicts inside the new record are computed through the **existing verifier
  registry** (registered kinds already match; add kinds rather than new
  verifier machinery).
- `_build_turn_task_outcome` gains a derivation step from the new record —
  additive, mechanically reviewable, no consumer change.
- v2 stays at version 2 for the duration of the learning freeze.

## 4. Canvas-guard audit (candidate producer — NOT authoritative by recency)

The operation-scoped canvas guard (`_canvas_write_for_operation` :6467,
`_canvas_claim_correction` :6412) is the only existing component producing an
execution-bound, DB-evidenced requested-result verdict on the chat path.
Audit results:

**Sound**: binding is exact field equality (`details.operation_id ∈
operation_ids OR details.execution_id == execution_id`, :6543–6548; the
docstring's "same session, at/after" wording is stale — code no longer does
that); pending-review writes stay `write_recorded` (:6565–6567); header
comment :6396–6403 needs updating to match.

**REJECTED premise (review correction, 2026-09-25)**: the guard's readback
treats fresh `Canvas.content` as the served revision (:6571–6586). The
canonical reader is **audit-first**: `read_canvas`
(tools/canvas_crud_tool.py:121–189) resolves content from the latest
`CanvasAudit` row carrying a body ("the audit trail IS the source of
truth"), and its own comments record that reading the `Canvas.content`
column served creation-era snapshots (observed 2026-08-31). `Canvas.content`
is a mirror that can lag the audit trail — comparing against it can verify
against a revision the user never sees, or miss one they do. **Corrected
discipline**: verify requested changes by resolving the user-visible
revision through the canonical audit-first resolver and comparing the bound
operation's payload against THAT resolution; review status (pending_review)
is tracked as a separate field, never folded into `verified`.

**Blind spots** (must be fixed by the new layer, not inherited):
1. Readback oracle is the wrong table: compares against `Canvas.content`
   instead of the audit-first canonical resolution (see rejected premise
   above) — verification can pass/fail against a revision the user never
   sees.
2. Non-canvas writes (email, CRM, tasks): zero coverage, no audit binding.
3. Streaming leg bypasses the guard entirely (single call site on the
   non-streaming return, 10466–10471).
4. Whole-turn single verdict; first bound audit row wins (:6530–6589) —
   wrong under multi-write turns.
5. Continuation rows landing after the reply cannot affect the verdict.
6. Verdicts are computed then discarded into prose rewrites — no persistence.
7. Vocabulary is canvas-specific (`result_verified/write_recorded/unverified`)
   and needs unification with `tool_outcome_verifier`'s
   `verified/unverified/failed_verification` (agent-stack, self-attested —
   noted, not adopted).

Verdict: adopt its **binding discipline** (exact id equality,
pending-review exclusion) and the corrected **canonical-resolver readback**
(§4 rejected-premise paragraph — NOT `Canvas.content` equality) as the
producer pattern inside the new execution-outcome record; do not lift the
implementation as-is.
