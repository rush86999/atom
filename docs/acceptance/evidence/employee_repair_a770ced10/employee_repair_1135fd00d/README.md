# Employee repair successor — durable verified proof

Status: **submitted for independent verification; deterministic only. Served
adaptive choice (G5 level 2) and Batch A acceptance remain unclaimed.**

This successor fixes the last execution-path gap in the verified-receipt
contract: the adapter's explicit `verification`/`coverage` was preserved on the
operation receipt but dropped from the durable **step result**, so a dependent
`require=verified` receipt could not be satisfied by a real operation even
though the pure predicate accepted a hand-built result.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `1135fd00d` (full SHA in `MANIFEST.json`) |
| Parent repair | `1135fd00d` / `employee_repair_b7ea53b31` |
| Transport | controlled local service/DB; no live provider |

## Repairs carried by this source

The five independent findings remain closed:

1. verified receipts require explicit proof, matching identity and complete
   coverage; unknown requirement names refuse;
2. provider acceptance never establishes Sent Items or recipient delivery;
3. full affected closure protects every step and durable operation, refusing
   running/uncertain descendants without clearing identity/result;
4. patch bases bind to lifecycle `task_version` with a CAS recheck;
5. canonical material digest gives idempotent replay and changed-content
   conflict.

This successor adds:

- durable step results retain `verification` and `coverage`;
- readiness also reads the operation receipt's
  `remote_identity.verification` and `source.coverage` for legacy/restarted
  results;
- an execution-level negative matrix proves a weak/absent/conflicting/
  truncated/field-missing verified receipt leaves the dependent action
  uncalled while the independent branch completes;
- a valid complete twin executes the dependent action and reaches completed;
- established patch facts require a stable source identity or authored
  authority, and an authority transition advancing task_version without a
  plan revision refuses the old patch.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **557 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Focused affected suites | **209 passed** |
| Patch invariants | **8 passed** |
| Two-domain deterministic campaign | **4 passed** |
| Evidence/G0/blocked-route probes | **9 passed** |
| Corrected patch probe | **3 passed** |

The 209 focused tests include five execution-level receipt controls (four
negative cases with zero dependent calls and one positive twin).

## Version-field note

The original independent patch probe's helper builds `base_task_version` from
`task_revision.revision`, the obsolete objective revision. On this source its
first apply is correctly refused as stale, so its changed-content setup cannot
run. `corrected-patch-invariant-probe.py` changes only that helper to
`record.task_version` and passes 3/3. No product fallback accepts the obsolete
field.

## Boundaries

- Deterministic mechanisms only; no served-model adaptive choice or raw model
  traces.
- Four `test_task_lifecycle.py` controls fail identically at the parent/base;
  disclosed, not counted.
- No live provider action/send/credential/consent/spend; planner 5/5, goal
  router 1/2, alignment gap 3.0 and historical `111/123` unchanged.
