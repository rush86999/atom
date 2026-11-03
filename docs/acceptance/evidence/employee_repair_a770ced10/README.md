# Employee repair — durable verified proof and Sent Items readback

Status: **submitted for independent verification; deterministic only. Served
adaptive choice (G5 level 2) and Batch A acceptance remain unclaimed.**

This successor closes the execution-path half of both evidence-strength
contracts. The adapter's explicit `verification`/`coverage` and correlated
Sent Items `readback` were previously dropped from the durable step result, so
dependent readiness and outcome verification could not see the proof that a
real operation returned.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `a770ced10` (full SHA in `MANIFEST.json`) |
| Parent repair | `a770ced10` / `employee_repair_1135fd00d` |
| Transport | controlled local service/DB; no live provider |

## Repairs

The prior five findings remain closed: verified-receipt strength, provider vs
Sent Items separation, full affected-closure protection, authoritative
`task_version` bases with CAS recheck, and canonical material-digest
idempotence/conflict.

This source additionally:

- preserves `verification`, `coverage` and `readback` on the durable step
  result;
- lets readiness fall back to the operation receipt's
  `remote_identity.verification` and `source.coverage` for restarted results;
- proves through the real executor that absent/conflict/missing-field/
  truncated verified proof leaves the dependent action uncalled while the
  independent branch completes, and that a complete explicit twin executes;
- proves through the real executor that provider acceptance alone leaves
  Sent Items unresolved, while an explicit correlated readback satisfies it;
- requires a stable identity for established patch facts and refuses an old
  patch after an authority change advances `task_version` without a plan
  revision.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **683 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Focused affected suites | **211 passed** |
| Patch invariants | **8 passed** |
| Two-domain deterministic campaign | **4 passed** |
| Evidence/G0/blocked-route probes | **9 passed** |
| Corrected patch probe | **3 passed** |

## Version-field note

The original independent patch probe's helper builds `base_task_version` from
`task_revision.revision`, the obsolete objective revision. On this source its
first apply is correctly refused as stale, so its changed-content setup cannot
run. The corrected probe changes only that helper to `record.task_version` and
passes 3/3. No product fallback accepts the obsolete field.

## Boundaries

- Deterministic mechanisms only; no served-model adaptive choice or raw model
  traces.
- Four `test_task_lifecycle.py` controls fail identically at the parent/base;
  disclosed, not counted.
- No live provider action/send/credential/consent/spend; planner 5/5, goal
  router 1/2, alignment gap 3.0 and historical `111/123` unchanged.
