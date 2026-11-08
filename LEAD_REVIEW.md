# Lead review — exact repeated external reply identity (implemented)

**IMPLEMENTED-NOTRUN.** This branch contains an authorized finite runtime
repair. No native test, app, server, model, provider, browser, credential or
live-data action was executed by the author. Root owns execution and
acceptance. No test here is claimed as passing.

Source lineage:

- baseline production: `c97dada13`;
- author-only test/review: `bf1d9bbd9`;
- root test-scaffold correction: `336f374f5`;
- root behavior probe: `a68d8e30a`;
- this repair commit: `codex/assignment-reply-identity-20261108` (exact hash in
  the handoff).

Only these files were changed by this repair:

- `backend/api/assignment_routes.py`
- `backend/core/assignment_executor.py`
- `backend/core/goals/goal_run_events.py` (existing event caller)
- `backend/tests/test_assignment_external_reply_identity.py`
- `LEAD_REVIEW.md`

No new table, store, engine, migration or parallel ledger was added.

## Implemented contract

### 1. Optional opaque `reply_id` reaches the shared executor

`AssignmentExternalResponse` now has `reply_id: Optional[str] = None`. The
public route passes it unchanged to `AssignmentExecutor.record_external_response`.
The value is never stripped, case-folded, Unicode-normalized or collapsed; two
IDs that differ only by case, leading/trailing space, or composing/decomposing
Unicode remain distinct. IDs are identity only, never authentication or
authority.

The event caller (`goal_run_events._resume_woken_run`) also passes an explicit
`event["reply_id"]` when present, and preserves the omitted-ID path when absent.

### 2. Explicit identity is strict

Every direct step-wait reply is evaluated inside one `mutate_assignment` CAS
callback. The callback re-reads the fresh assignment on every retry, then:

- binds an explicit ID to `run_id` / correlation / fact / subject scope;
- computes the canonical material digest from the complete submitted material;
- if the same ID + same material already produced an outcome, returns that
  outcome without a write, conflict entry, decision, wake or effect;
- if the same ID carries different material, returns `reply_conflict` before
  any state transition (the route maps it to HTTP 409);
- if the same explicit ID appears on another correlation/fact/subject, returns
  a scope conflict before any transition;
- if the wait is already settled and the identity is new/changed, refuses
  rather than certifying a replay.

An exact previously accepted reply is `already_applied` (explicit ID). A legacy
accepted replay keeps the historical `resumed` result while the job is still
in flight, or `already_applied` once terminal, but always sets
`replayed: true`. The route and event caller return immediately for
`already_applied` / `replayed`, so a duplicate never triggers a second
`execute`/`advance`.

### 3. Material digest

`_external_reply_material_sha256` hashes a canonical JSON object containing:

- correlation id, fact, subject, expected party;
- typed-binding flag and expected answer type;
- exact `response`, `source` and `evidence` text;
- `value`, with numeric values in explicitly typed numeric waits passed through
  the existing `_canonical_fact_value` (`5.0` and `5` compare equal); every
  other value is preserved as supplied.

The digest is never supplied by the caller and never built from the bounded
display projection. Presentation/conflict fields remain bounded separately.
Unsupported or oversized material fails closed as a typed `reply_conflict`
rather than hashing a truncated representation. Existing typed validation,
source-party validation and fresh source-fact resolution are preserved.

### 4. Omitted-ID compatibility

Omitted IDs are not a fixed per-correlation identity. A legacy reply derives
its identity from the exact material digest + wait scope. Therefore:

- an identical unkeyed retry matches the existing receipt and replays the prior
  outcome without another event;
- a changed unkeyed reply while the wait is open is a new event, so a legitimate
  partial reply followed by a corrected/full reply still completes the same job;
- after the wait has already been accepted, a changed unkeyed reply is not new
  authority: it reports the prior accepted outcome (`already_applied` when
  terminal, `resumed` + `replayed` while still in flight) and creates no second
  effect. This preserves the existing procurement-campaign replay contract.

Explicit-ID semantics remain strict in all cases.

### 5. Durable receipt history

The authoritative identity history is the existing wait step JSON:

```text
step["reply_receipts"] = [
  {
    reply_id, identity_kind, material_sha256,
    correlation_id, fact, subject,
    outcome, reason, message, at,
    conflict?              # bounded display copy only
  },
  ...
]
```

`reply_receipts` is append-only. It survives a fresh SQLAlchemy session and is
not limited by the public conflict projection, which remains `conflicts[-10:]`.
A replayed or refused reply does not append a receipt. An old identity beyond
ten display entries can still replay its original outcome or be refused for
changed material; it cannot silently become a new authority. There is no
arbitrary cap that permanently prevents a same-job complete answer.

Accepted replies also carry the same identity/digest plus the original wait
scope (`fact`, `subject`, `party`, `typed_binding`, `expected_answer_type`) in
`step["external_response"]`. This lets an exact replay be re-hashed after
`waiting` has been cleared, including after completion and restart.

### 6. CAS and authority

- All step-wait identity checks, terminal checks, material checks and receipt
  writes happen inside `TaskLifecycle.mutate_assignment`, i.e. under the
  existing task-version CAS. A pre-read is not used as authority.
- A private `_ExternalReplyStop` carries a replay/refusal result out of the CAS
  callback, so no task-version bump, decision or effect is written for a replay
  or refusal.
- Two concurrent same-ID/different-material writers cannot both wake: the CAS
  loser re-runs the callback on fresh state and sees the winner's receipt.
- The waiting operation is superseded only after a successful accepted-reply
  CAS write, and `_wake_run` is called only for a new accepted reply.
- Route `_scoped_run` still refuses foreign workspace/tenant callers before the
  executor is reached.
- Cancellation/terminal work refuses new or changed late identities; the
  existing terminal-refusal decision is retained.

## Tests authored (not executed)

`backend/tests/test_assignment_external_reply_identity.py` now covers:

- the public changed-`r1` failure-first control;
- same explicit ID / same material idempotency, including canonical `5.0` -> `5`;
- new explicit ID resumes the same job once;
- late new identity after completion is refused, not `already_applied`;
- cancellation and foreign-workspace refusal with fresh-session readback;
- field-class contradictions: changed response, source, evidence and value
  under the same ID each refuse before transition;
- opaque-ID twins differing only by case, leading space or Unicode composition;
- omitted-ID partial -> corrected/full compatibility, with identical-retry
  idempotency;
- 12 conflict events: 10-entry display bound, full receipt history, replay of
  the old ID, changed-material conflict, and fresh-session readback;
- stale wait-scope conflict;
- deterministic CAS interleaving: a competing writer inserts a receipt between
  the outer read and the actual callback; the same-ID request must refuse.

Root also retains the independent behavior-only probe
`test_root_assignment_reply_material_probe.py`. No assertions were weakened to
fit the implementation.

## Established practice cited

- AWS EC2 API idempotency: a client token is bound to unchanged request
  parameters; reusing it with different parameters is an error.
  <https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html>
- Temporal message handling: duplicate delivery and interleavings are handled
  by deduplication/identity, not by trusting arrival order.
  <https://docs.temporal.io/handling-messages>

The implementation reuses the repository's SQLite lifecycle CAS rather than
adding Temporal or an in-memory lock as database authority.

## Remaining limitations / honest gaps

1. **Gap/question waits are not in this identity slice.** `record_external_response`
   still delegates unresolved-question replies to the existing `resolve_gap`
   path. Reply identity receipts apply to direct step waits. Full multi-fact
   coordination, including identity over question waits, remains open.
2. **Legacy after-settlement compatibility is intentionally looser than explicit
   IDs.** A changed unkeyed reply after the wait is already accepted reports the
   prior accepted outcome rather than creating a new event. This preserves the
   existing procurement-campaign replay test and prevents a new effect; explicit
   IDs remain strict. While the wait is open, changed unkeyed material is still
   a new event.
3. **Oversized material fails closed.** The existing canonical fingerprint
   validator bounds string/depth/byte size. Material outside those bounds is
   refused as `reply_conflict`; it is never truncated into the digest.
4. **Receipt history growth is append-only.** Public conflict display remains
   bounded at ten, but the authoritative receipt list is not capped. A future
   compaction must preserve authoritative lookup (or otherwise fail closed) and
   must not silently evict an identity into new authority.
5. **Pre-repair accepted waits without receipts are not certified as exact
   replays.** A settled wait with no receipt gets terminal refusal for a new
   reply rather than a fabricated idempotent replay. This is a deliberate
   migration boundary.
6. No native test was run. Root must execute the focused file and the existing
   assignment suites, reproduce the original failure before repair evidence,
   and accept or reject the result.

## Verification status

**IMPLEMENTED-NOTRUN.** Root executes. The author makes no pass claim.


## Root independent verification and legacy follow-through

Frozen381 passed16 focused controls, including the original root public changed-explicit-ID negative. Root then tested the documented legacy terminal exception at70512246b: changed unkeyed material received HTTP200/already_applied on a completed assignment. This is not an exact replay and was misleading even though it did not create a second effect. The original failing log/spec/exit is retained at root-assignment-reply-legacy-negative. Root removed that exception: material-derived legacy identity must match the original digest just like any exact retry; changed late input reaches existing terminal refusal. Legitimate unkeyed partial->corrected answers while waiting remain allowed. No business-result, authority, artifact or source-readiness check is weakened. Retest/affected gates remain required. Direct gap/question resolution remains a separately open compatibility/integration row, not full coordination acceptance.


## Root verification at fa6a047f6

The seven-module affected assignment/executor/routes/durable-wait/source-
continuation/event selection passes 220/220 on Python 3.14 and 3.11. The
source remained fa6a047f67ad762b5c04e97ea3a8124ea323a004 for both runs.
This includes the permanent external reply identity and independent changed-
material probes, now added to the existing source-continuation CI step.
Raw logs/specs/exits remain at root-assignment-reply-fa6-affected (3.14) and
root-assignment-reply-fa6-affected-py311 (3.11) in retained scratch evidence.
The 3.14 completed world was byte-verified into the portable-drive archive
before removing its internal uncompressed copy.

Scope: direct-step replies only. The question/gap response path is under a
separate read-only review; no general repeated-partial or days-long coordination
claim follows from these controls. No live model/provider/effect was used.


## Question/gap reply identity — finite repair (authored, NOT RUN)

**IMPLEMENTED-NOTRUN.** Author baseline: `c329f295c` in the private standalone
worktree `/private/tmp/atom-assignment-gap-reply-identity-20261108` (Git root
and empty prefix verified before reading/editing). No pytest, Python/Node
runtime, provider, credential, browser, DB or app action was executed by the
author. Root owns execution and acceptance; no pass claim is made.

### Contract repaired

- `record_external_response` no longer delegates open question/gap replies to a
  pre-CAS `resolve_gap` call that dropped `reply_id`/`value`.
- Question and direct-step waits now share the append-only
  `step["reply_receipts"]` and the canonical material helpers; no parallel
  store, router, table or review engine was added.
- One `mutate_assignment_and_task` CAS commits the question resolution, reopened
  step, accepted receipt, `external_response` and (for the settlement only)
  the waiting-operation supersede together, or commits nothing.
- Ordering is exact receipt replay first, then terminal refusal for new/changed
  replies. A rejected/partial mapping answer retains a receipt, keeps the
  question open and neither reopens nor wakes.
- Same explicit ID with changed text/value/source/evidence conflicts; a new ID
  may resolve. A re-raised question keeps the old receipt authority for the
  same correlation/concept/subject scope; cross-correlation reuse refuses.
- `resolution_matches` now compares the exact structured `resolution_value`
  (legacy records fail closed to byte equality). The literal
  `"price 100 [subject to approval]"` twin no longer matches `"price 100"`.
- Direct `POST /gaps/{id}/resolve` behavior is preserved: identical answer is
  `already_resolved`, a different/prefix answer is 409, and the rejected
  candidate acknowledgement does not mutate.

### CAS/transition trust boundary

`apply_transition` itself remains a general task API. Operation supersede is
NOT honored generically: `mutate_assignment_and_task` runs
`_supersede_gap_settlement_operations` after the fresh assignment is known. It
only supersedes a named operation when all hold: transition kind is
`record_unresolved`, it resolves a question, the operation belongs to this
assignment, its step carries one of the questions resolved in that same
transition, and the operation is still `waiting`. Caller/model metadata cannot
name an arbitrary applied/foreign operation.

### Files

- `backend/core/assignment_executor.py`
- `backend/core/task_lifecycle.py` (shared CAS + narrow supersede validation)
- `backend/api/assignment_routes.py` (409/early-return caller wiring)
- `backend/core/goals/goal_run_events.py` (existing event caller passes value
  and treats partial/rejected as non-resuming)
- `backend/tests/test_assignment_gap_reply_identity.py` (new focused file)
- `.github/workflows/ci.yml` (adds the focused file to the existing source-
  continuation step; all previously listed modules preserved)
- `LEAD_REVIEW.md`

### Tests authored, NOT RUN

`backend/tests/test_assignment_gap_reply_identity.py` covers: partial/rejected
receipt retention; exact partial replay without version/decision/receipt
movement; same-ID changed response/source/evidence/value conflicts; new-ID
resolution; accepted receipt + `external_response`; post-closure
`already_applied`; changed terminal refusal; fresh-session restart readback;
cross-correlation scope refusal; re-raised-question exact replay that leaves
the new question open; CAS competitor recheck; literal-bracket vs audit-suffix
predicate; and direct `/gaps` exact-answer replay compatibility.

### Known limits / risks for root

1. No test was run; root must execute the focused file and the affected
   assignment suites.
2. The focused file is added to the existing CI step only; it was not inserted
   into any broader selection beyond that step.
3. `resolution_matches` deliberately fails closed for legacy records whose only
   stored answer is a bounded audit string. A legacy prefixed replay now
   conflicts rather than being inferred as identical.
4. No days-long/full-app qualification, provider effect or merge claim follows.


## Independent caller audit: two-domain campaign expectation

DeepSeek's read-only review identified a caller control outside the original
seven-module 220-test selection. Executing it unchanged at da280ff17 gives
1 failed / 3 passed: the procurement campaign calls a changed terminal answer
"exact replay" and expects already_applied. This contradicts the intentionally
repaired exact-material contract. The test now has both twins: original
accepted material must replay; changed material must return terminal while
keeping the completed assignment and one bill effect. No runtime guard was
relaxed. The campaign is added to the existing CI step. Earlier220 results
remain accurate for their named selection and are not expanded retroactively.


## Root independent first execution at349db796f

Focused new-gap plus preserved direct controls:24passed/3failed onPython3.14.
Two failures were author fixture defects: a call counter was compared with a
question dict, so the supposed second prerequisite never occurred. Both
fixtures now actually raise their second prerequisite on call2. The third
failure was a stale interleaving hook: direct reply settlement now enters
mutate_assignment_and_task, so the old mutate_assignment hook never inserted
the competing receipt. The hook now targets the actual entry and explicitly
asserts the competitor ran. Exact conflict/receipt assertions are retained.
No production logic was changed by this test-scaffold correction. Original
failed log/spec/exit remain root-assignment-gap-349-focused in retained
scratch evidence. Further semantic and affected verification remain pending.
