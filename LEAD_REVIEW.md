# Lead review — Assignment repeated partial reply identity

**AUTHOR-ONLY-NOTRUN.** This branch is author-only. Nothing here was executed,
no test result is claimed, and no production file was changed. The only
deliverables are:

- `backend/tests/test_assignment_external_reply_identity.py`
- `LEAD_REVIEW.md`

Source baseline: `c97dada13` (`Bind canvas delete and undelete to current
authority and verified history (#763)`), branch
`codex/assignment-reply-identity-20261108`. Root owns all gates, reproduction,
acceptance and repair authorization.

## Contract under test

A durable typed wait must bind an external reply **identity** to its exact
**material**. For this slice:

1. Open the real typed `received_quantity` wait through the existing employee
   fixture (`test_employee_durable_wait_g5._start`), so the wait is compiled by
   the production work compiler and read by the production executor.
2. Submit a non-resolving reply under `reply_id = r1` (the source fact is
   already established as a different value, so the result is a durable
   conflict and the wait remains open).
3. Submit changed valid material under the **same** `r1`. Desired result is an
   exact material conflict (typed HTTP 409 or an explicit, identity-specific
   refusal). The wait stays unresolved and no dependent reconciliation or
   artifact appears.
4. Valid twins:
   - same `r1` / same material replays the same result without adding another
     conflict or decision event (including canonical `5.0` -> `5` typed
     equality);
   - new `r2` / full accepted answer resumes the same job exactly once;
   - a partial/conflicting reply never satisfies the business result;
   - cancellation and a foreign-workspace caller refuse the reply;
   - a new identity with changed material after completion is **not** reported
     as an exact replay.

The test also rebuilds an executor from a fresh SQLAlchemy session and reads the
durable wait step back. Identity receipts and material digests must survive that
readback. The intended durable home is the existing wait step JSON
(`step["reply_receipts"]`, `step["external_response"]`), not a new table/store.

## What the current code actually does (traced, not runtime-qualified)

### Omitted `reply_id` compatibility

- `backend/api/assignment_routes.py:125-129` — `AssignmentExternalResponse` has
  `response`, `source`, `evidence`, `value`; there is no `reply_id`.
  Pydantic's default extra-field behavior ignores an unknown JSON field, so the
  route accepts `reply_id` in the request body and silently drops it.
- `backend/api/assignment_routes.py:2525-2541` — the public route forwards only
  the four modelled fields into `record_external_response`; identity never
  reaches the executor.
- `backend/core/goals/goal_run_events.py:87-94` and
  `backend/core/assignment_executor.py:2741-2745` are the other production
  callers. They also have no reply identity: they pass correlation, response,
  source and evidence only. Any repair must live in the executor, not only in
  the route, or these event-driven callers stay unprotected.

**Compatibility position for repair:** add `reply_id: Optional[str] = None` to
`AssignmentExternalResponse` and to `record_external_response`. For legacy
callers that omit it, derive one stable per-wait identity, e.g.
`legacy:{sha256(correlation_id)}`. The first legacy receipt then binds its
material; an identical legacy retry is idempotent, while changed material under
the same omitted identity is an exact conflict. This preserves the current
one-reply event path without silently allowing a second, different legacy reply
to become authority. Callers that need to distinguish two independent answers
on one wait must send distinct `reply_id`s.

### Receipt material canonicalization

- `backend/core/assignment_executor.py:4398-4416` — matching is by
  `correlation_id` only. Wording, `source`, `evidence` and `value` are not part
  of any identity comparison.
- `backend/core/assignment_executor.py:4478-4537` — typed waits already
  canonicalize the answer with `Decimal` for the type/finite/nonnegative checks,
  but that parsed value is not retained as an identity.
- `backend/core/assignment_executor.py:4538-4639` — when the source fact is
  established/mixed/unavailable/incomplete, the reply is compared with
  `_response_agrees_fact`; a non-agreeing reply appends a conflict entry.
- `backend/core/assignment_executor.py:1150-1479` — `_source_fact_resolution`
  selects the source fact and its canonical values.
- `backend/core/assignment_executor.py:1482-1497` — `_canonical_fact_value`
  already normalizes numeric spellings (`5.0` and `5` both become `5`).
- `backend/core/assignment_executor.py:1500-1522` — `_response_agrees_fact`
  uses that canonical value; free-form prose is not substring-scanned when an
  explicit value is supplied.
- `backend/core/assignment_executor.py:8078-8091` — `resolution_matches` has
  the same replay idea for gap resolutions (byte-equal or stored text with an
  audit suffix), but it is not used by the external-reply path.

**Proposed material digest:** canonical JSON (sorted keys, UTF-8) over
`correlation_id`, `fact`, `subject`, the canonical typed `value` (or the
canonical response when no explicit value exists), normalized `response`,
normalized `evidence`, and normalized `source`. Normalize Unicode to NFC and
collapse insignificant whitespace for text. A `material_sha256` is stored with
the receipt. This is intentionally **not** a free-form comparison: the same
identity with a different digest is an exact conflict even if it would have
resolved the fact.

### Tenant / workspace authority

- `backend/api/assignment_routes.py:179-200` — `_scoped_run` loads the run
  through the current user's workspace/tenant and returns 404 when it is not
  visible. The route-level foreign-caller test therefore never reaches the
  executor.
- `backend/core/task_lifecycle.py:1352-1386` and `1406-1432` — the CAS write is
  also filtered by the lifecycle service's workspace id.
- The executor itself (`record_external_response`) does not take a user or
  workspace argument. Direct callers must therefore be trusted to have scoped
  the run first. The identity ledger belongs inside the run's assignment step,
  so it cannot leak across tenants even when the event path calls the executor
  directly. The test confirms a foreign-workspace caller gets 404 and leaves no
  receipt or conflict.

### Task revision / CAS

- `backend/core/task_lifecycle.py:1352-1386` — `_mutate` re-reads the task,
  runs `compute`, and writes only if `task_version` is unchanged; losers retry
  on fresh state. `mutate_assignment` (`1815-1852`) validates and writes the
  whole plan under that CAS.
- Current `record_external_response` performs the early replay scan
  (`4419-4435`), the terminal check (`4436-4455`), the typed checks
  (`4478-4537`) and the fact comparison (`4538-4589`) **before** entering a
  single `mutate_assignment` callback. Two concurrent replies can therefore both
  observe the same pre-mutation state. Only the eventual writer wins the CAS,
  and the other retry re-runs the callback, not the pre-checks.
- **Repair invariant:** replay, terminal, identity and material checks must be
  re-evaluated inside the `mutate_assignment` callback(s) on the fresh record.
  A pre-read may be retained as a fast path only if the callback repeats the
  check. The identity receipt is appended in the same CAS write as the conflict
  entry or the accepted `external_response`, so identity and outcome cannot
  fork.

### Terminal exact replay hazards

- `backend/core/assignment_executor.py:4419-4435` returns `already_applied` for
  any step whose `external_response.correlation_id` matches and whose status is
  `applied`. It does not compare `reply_id`, material, or assignment terminal
  state. Consequences:
  - a second, different reply under the same correlation but a new identity is
    falsely acknowledged as an exact replay;
  - changed material under the accepted identity is also falsely acknowledged;
  - the check runs before the terminal branch (`4436`), so a terminal assignment
    can answer as `already_applied` instead of performing a terminal refusal.
- The test locks both sides: exact `r2` replay is `already_applied` with no
  second effect; late `r3` with changed material is refused and is **not**
  `already_applied`.
- **Repair invariant:** exact replay means the tuple
  `(correlation_id, reply_id, material_sha256)` matches the stored accepted
  receipt. Same `reply_id` + different digest is an exact material conflict;
  different `reply_id` on terminal work is a terminal refusal (409 at the
  route).

### Bounded identity history

`backend/core/assignment_executor.py:4598-4604` keeps only the last ten
conflict entries (`conflicts[-10:]`). That is an evidence-history bound, not an
authority history. If a repair puts reply identities only in that list, an
evicted `r1` would look new and could become authority again.

**Finite retention/replay policy to implement (not implemented here):**

- Keep an append-only `step["reply_receipts"]` list of full receipts
  (`reply_id`, `material_sha256`, `outcome`, `reason`, `at`), capped at a
  finite `REPLY_RECEIPT_LIMIT` (proposal: 64).
- **Never evict silently.** When the cap is reached, refuse a new distinct
  `reply_id` with a typed identity-capacity refusal (409) until the wait is
  resolved/cancelled or an owner explicitly resets the wait. Existing receipts
  still replay idempotently. This is fail-closed and preserves the rule that an
  evicted identity cannot become new authority, at the cost of wedging a wait
  that accepts an unbounded number of distinct replies.
- The existing `waiting["conflicts"]` slice of ten remains presentation/evidence
  only. It may carry `reply_id`/`material_sha256` for explanation, but it is not
  the authoritative replay record.
- Do not invent a new store or engine. This is all assignment-step/lifecycle
  JSON, carried by the existing CAS write.

## Finite proposed production change (do not implement yet)

1. **API model** (`backend/api/assignment_routes.py:125`): add
   `reply_id: Optional[str] = None`; pass it through at `2535-2541`.
2. **Executor signature** (`backend/core/assignment_executor.py:4398`): add
   `reply_id: Optional[str] = None`; derive the legacy identity when omitted.
3. **New pure helpers** in the executor: canonical material digest and receipt
   lookup. Reuse `_canonical_fact_value`; no new persistence.
4. **Fold checks into CAS:** inside the `mutate_assignment` callback, read
   `step["reply_receipts"]` and `step["external_response"]` from the fresh
   record. Apply the replay/terminal/identity rules before changing `waiting`,
   `status`, `external_response` or `budget`. On a non-resolving reply, append
   the receipt and the conflict entry in the same write. On an accepted reply,
   append the receipt and set `external_response` with the same identity/digest
   in the same write.
5. **Route mapping** (`backend/api/assignment_routes.py:2542-2553`): map
   exact-identity conflict and identity-capacity refusal to HTTP 409 with a
   typed detail. Keep ordinary non-resolving conflict/partial/unavailable/
   incomplete replies at 200 with the wait open, as today.
6. **Legacy callers:** omitted `reply_id` becomes one derived per-wait identity
   as above. First use binds material; exact replay is idempotent; changed
   material conflicts. Event-driven callers (`goal_run_events.py:87`) keep
   working without a new required field.
7. **No production change in this slice.** Root must reproduce the failure with
   the authored test before authorizing repair.

## Test assumptions and limitations

- The test is **not run**. It is labeled AUTHOR-ONLY-NOTRUN and must not be
  cited as passing.
- It uses the existing `route_env` fixture (scratch SQLite, workspace `ws-1`,
  tenant `tenant-1`) and the existing controlled reasoning fixture in
  `test_employee_durable_wait_g5`. No provider, network, credential, live data,
  browser, server, model install, or external message is involved.
- The wait is the real compiler-produced typed `received_quantity` wait, not a
  hand-built wait. The only controlled part is the existing model-proposal
  transport required by that fixture.
- The test asserts the proposed durable shape `step["reply_receipts"]` and
  `step["external_response"]["reply_id"]/["material_sha256"]`. If root authorizes
  an equivalent representation inside the existing wait step, the test should be
  reconciled by the lead before repair; it should not be weakened to
  behavioral-only assertions.
- The main control should fail on current code by resolving changed material
  under `r1`. The exact point of failure may be the missing receipt fields or
  the changed-material acceptance; root should capture the actual failure
  before editing production.
- Root-only gates: run this single test file against `c97dada13`, preserve the
  failure output as evidence, then rerun after an authorized repair. Do not
  accept a green run that only removes assertions.

## Deliverable pointer

`backend/tests/test_assignment_external_reply_identity.py` is the authored,
failure-first test. `LEAD_REVIEW.md` is this review. Nothing else was authored
or changed.


## Root fixture correction before product diagnosis

Root executed bf1 on unchanged main production:3 failed/1 passed. Two controls stopped before the target behavior because an empty artifacts/ws-1 directory was treated as an artifact; a third compared a missing pre-repair receipt field (None) with an empty list. These are test-contract issues, not three product failures. Root corrected the artifact assertion to reject actual files recursively and normalized only the absent optional list in the comparison. All wait/business-result/effect/identity assertions remain. The original log/spec/exit is retained at root-assignment-reply-bf1-baseline. Production remains unchanged; the corrected controls must still demonstrate the actual gap independently before repair.
