# Goal 9 — atomic hard-stop reservation (candidate)

Date: 2026-11-10. Branch: `codex/goal9-atomic-cap-20261110`, based on
`df3b7747b` (PR832 durable settlement) with the later identity/success runtime
fixes integrated on this branch. This is a bounded candidate for root review,
not Goal 9 acceptance and not a universal concurrency claim.

## Design: one ledger, one transaction

`TokenUsage` remains the single durable ledger. A paid dispatch writes a
reservation row before the provider call:

- exact server-owned binding: request/attempt, provider/model,
  agent/workspace/tenant/execution/chain;
- `pricing_status="unknown"`, `cost_usd=NULL`, `billed=False`;
- `reserved_cost_usd` = conservative configured upper bound,
  `reservation_status="active"`.

The reservation transaction then sums actual `cost_usd` plus active/uncertain
`reserved_cost_usd` for the tenant/window. On configured hard-stop, the
reservation is refused (row rolled back) when the bound would exceed the
limit. SQLite acquires the single write lock with `BEGIN IMMEDIATE` **before**
the read/sum, so a concurrent reservation waits and then sees the committed
row; a deferred read-then-write would keep a stale snapshot. PostgreSQL uses
the existing tenant row with `SELECT ... FOR UPDATE`; that path is implemented
but **not runtime qualified** here.

No second budget store/router/engine is introduced.

## Settlement and liability

The success path settles the exact pre-dispatch row once via the existing
`record_llm_usage` helper. Known usage/cost becomes `billed=true`,
`priced`/`free`, actual tokens; missing usage or pricing becomes
`reservation_status="uncertain"` with the reserved bound retained and
`cost_usd=NULL`, never a fabricated 0. The conditional-UPDATE CAS matches the
immutable binding and the pending/active/uncertain state; a stale writer
cannot overwrite an actual settlement or reassign scope. A settlement write
failure leaves the active reservation/intent in place; hard-stop continues to
count it and refuses after restart. Timeout/uncertain work is never
auto-released; only authoritative reconciliation settles it.

The ordinary success path now settles the exact pre-dispatch intent (the
prior root negative showed two visible answers but two pending rows). The
success settlement uses `record_llm_usage` directly, so the existing inline
cache/rate/feedback/tracker surfaces are not duplicated.

## Conservative bound / policy

The bound uses the existing token counter (exact when available; UTF-8 byte
length is the fallback upper bound), plus explicit message/schema overhead,
the request's completion cap, the pricing contract, and a configurable margin
(`ATOM_LLM_RESERVATION_MARGIN`, default 1.25). Unknown pricing returns no
bound; configured hard-stop refuses instead of silently under-reserving.

The strict billing-policy reader rejects malformed JSON, invalid types,
negative/non-finite caps, and invalid modes as `BUDGET_STATUS_UNAVAILABLE`;
it does not collapse them to 0/unlimited. A genuinely absent policy is
intentional no-limit/observe. The single-tenant `default` scope without a
Tenant row remains intentional no-limit; a missing **non-default** tenant is
an unresolved scope and fails closed. The existing c3 durable
settlement/upgrade gate is preserved.

## Upgrade

`reserved_cost_usd` and `reservation_status` are added through the existing
supported SQLite startup repair path, preserving pre-upgrade rows, FKs,
custom columns and custom indexes; `migration.sql` records the reversible
PostgreSQL equivalent and is **not applied**. Existing old rows default to
`reservation_status="none"` / no reservation.

## Controls (scratch SQLite, doubled transport)

- two real concurrent reservations at 90/100 with 7-bound attempts: one
  succeeds, one refuses; one charged attempt; committed 97; no overspend;
- real structured **and** ordinary `generate_response` consumer races with
  90 + 7 + 7: loser zero provider calls, winner one settled 7, ledger 97;
- single 7 -> 97, second 7 refuses; actual less than reservation releases the
  difference; known free 0 allowed;
- duplicate attempt/binding idempotent; route/scope/execution contradictions
  refuse; restart reads the active reservation; caller pending work is not
  committed by the reservation session;
- DB read failure, reservation write failure, unknown pricing, malformed/
  negative/non-finite policy fail closed; intentional no-limit/observe and
  the `default` scope remain allowed;
- success settlement: two ordinary calls -> two settled 0.25 rows, 10/5
  tokens each, ledger 0.5; exact replay once; missing usage -> uncertain
  liability; settlement failure retains the active reservation and hard-stop
  across restart;
- existing supported upgrade preserves old rows/FKs/custom indexes.

Gates:

- atomic + ordinary consumer controls: **30 passed** (`gates/consumer.log`)
- focused atomic/durable/upgrade/CI-lane/ordinary CI files:
  **142 passed** (`gates/focused.log`)
- affected budget selection: **379 passed** (`gates/affected.log`)
- additive CI lane contract: **27 passed** (`gates/ci-lane.log`)
- root ordinary success probe on this branch: **2 passed**
  (`gates/root-probe-fixed.log`, `gates/root-probe-observation.json`)

The additive ledger (`backend/tests/fixtures/ci_backend_additions.json`) now
declares both the durable settlement step and the atomic reservation step
exactly; the immutable baseline fixture is unchanged.

## Research anchors

- LiteLLM budget reservation:
  `https://github.com/BerriAI/litellm/blob/main/litellm/proxy/spend_tracking/budget_reservation.py`
  — reserve a maximum estimate before the request, reconcile actual, fail
  closed when the reservation cannot be written, reconcile cancellation to
  input cost rather than refunding to zero.
- SQLAlchemy 2.0 UPDATE and affected-row count:
  `https://docs.sqlalchemy.org/en/20/tutorial/data_update.html` — conditional
  `UPDATE ... WHERE` with rowcount is the CAS primitive.
- SQLite transactions:
  `https://www.sqlite.org/lang_transaction.html` — one writer; immediate
  transactions acquire the write lock before the first read.
- PostgreSQL UPDATE / row locking:
  `https://www.postgresql.org/docs/current/sql-update.html` — `WHERE`,
  `RETURNING`, and row locks are the DB-level serialization primitives. The
  PostgreSQL path is not runtime qualified in this slice.

## Retained negatives / boundaries

- `retained_negative/atomic_cap_gap.py` + `.log`: pre-fix check-only
  admissions both allowed at 90 and two 7 settlements reached 104.
- `retained_negative/root-success-review.json` + `.log`: pre-fix ordinary
  success left pending rows (billed false, cost NULL, tokens 0); fixed and
  now covered by the 0.5/10/5 twin.
- Prior CI-repair identities and 0472/1aa evidence remain unchanged.

No live DB/provider/model/credential/send/spend/deploy/dependency action.
PostgreSQL concurrency, multi-process SQLite, and universal atomicity are not
claimed. 143 claims / 18 goals historical scores are unchanged; no claim that
all Goal 9 is complete beyond these bounded controls. Root owns independent
acceptance and merge.
