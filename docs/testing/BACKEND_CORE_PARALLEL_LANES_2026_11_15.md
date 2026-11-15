# Backend-core CI lane split — November 15, 2026
`backend-core` is partitioned into two explicit jobs, `backend-core` (35 steps, including the lane-preservation check) and `backend-core-extra` (31 test steps), both using the existing setup
pattern. The exact pre-parallel + additive step ledger is preserved by Counter
union: every command, env and intentional duplicate appears exactly once in its
original multiplicity. All `sqlite:///test_ci.db` / no-explicit-DB steps and the
two `:memory:` mini-app steps remain together in `backend-core`; the extra lane
contains only independently isolated DB/test steps. `backend-tests` now needs
all four backend lanes (`backend-core`, `backend-core-extra`, `backend-oracle`,
`backend-docker`) and succeeds only when every result is `success`.

The lane-preservation contract compares the full parsed steps (not names/
selectors only), verifies the extra-lane membership fixture, rejects removal/
duplication/env tampering/shared-DB movement, and exercises the real aggregate
shell over all four lane result combinations. Workflow-only change; the stable
product suite was not rerun. Contract result: **628 passed**.

Official basis: independent jobs can run concurrently, but walltime depends on
runner capacity; `needs.<job_id>.result` is `success|failure|cancelled|skipped`
and `if: always()` is required for an aggregate gate:
<https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs>,
<https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#needs-context>.
The theoretical serial-chain reduction is from 66 steps (including the preservation check) to at most
35 steps on the larger lane; no measured speedup is claimed until a real CI run.

Independent root verification: **628 passed in 70.96 seconds**. A separate
whole-workflow comparison confirmed all other jobs/top-level settings and the
three original ledgers are unchanged, per-lane order is preserved, and the
shared/missing/in-memory database cohort remains together. No runtime file
changes. Runner minutes and hosted latency remain unmeasured.


## First observed hosted comparison

Both exact-source PR workflows completed successfully: old run `43710961965`
at `fb67a5379`, split run `43713943649` at `5276657a2`. The old core lane took
110.07 minutes; the split critical lane took 69.62 minutes and the extra lane
45.32 minutes. The observed critical-path reduction is 36.75%. Total core job
elapsed runner time increased 4.42%; the sum over all CI jobs increased 0.26%.
The separate Docker workflow and GitGuardian are excluded from that sum.

This is one uncontrolled comparison, not a causal performance or billed-cost
claim. Runners, cache/network/queue effects and individual test durations vary;
the gate contract also expands from 125 to 625 combinations. All selectors,
environments, duplicates and original ledgers were independently compared.
The complete bundle merged through #958 as `519d06ef3` only after all 15
exact-head checks passed. Main post-merge CI `43720409849` and Docker `43720409769` both completed successfully; these results are separate from pre-merge checks.
