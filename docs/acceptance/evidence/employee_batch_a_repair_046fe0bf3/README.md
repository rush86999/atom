# Employee Batch A evidence-strength repair

Status: **submitted for independent re-verification of the two withheld
evidence contracts; Batch A acceptance is not self-asserted and adaptive
employee capability remains unqualified.**

This source integrates the already-landed blocked-readiness/projection repair
(`9b7c033f7`) with the two evidence-strength repairs identified by the
independent Batch A review. Later Batch B work remains a separate successor
and is not attributed to the frozen `27f256177` submission.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Combined repair source | `046fe0bf3` (full SHA in `MANIFEST.json`) |
| Original Batch A source | `27f256177` / evidence `acfa8a078` |
| Integrated status repair | `9b7c033f7` / evidence `8ec0b5164` |
| Batch B core retained | `52e0919b1`, `dfd05cbfc`, `93650be55` |
| Transport | controlled local service/DB; no live provider |

## Repaired contracts

### Verified receipts are explicit material proof

`core/assignment_readiness.py` now defines a finite receipt vocabulary
(`applied`, `verified`). Unknown names refuse normalization; there is no
silent downgrade. A `verified` prerequisite requires:

- an explicit structured verification with a verified/confirmed status;
- no missing, mismatched, conflicting or refuted fields;
- a declared operation/resource/subject/version/hash binding that matches the
  receipt (or stays unknown when the receipt lacks the identity);
- complete, non-truncated, known coverage when coverage is declared.

Empty/absent proof, refutation and truncated coverage stay ineligible; the
dependent action receives zero dispatch. `applied` remains useful for weaker
prerequisites but cannot satisfy `verified`.

### Provider acceptance is not Sent Items confirmation

`core/task_outcome_contract.py` exposes `sent_record_confirmed_evidence`: only
an explicit correlated authoritative readback (or an explicit test/controlled
readback seam) may establish Sent Items. A readback bound to a different
operation/reference is unsatisfied, absent readback is unresolved, and
`provider_state=accepted/applied` sets only `provider_accepted`.

Recipient delivery is a separate unclaimed observation. It is no longer
asserted false merely because delivery was not observed; it remains unresolved
unless genuine evidence exists. `employee_result` recognizes a material
artifact, draft or provider result without promoting a weaker stage to a
stronger criterion.

### Blocked readiness and OR projections

The integrated `9b7c033f7` repair persists blocked readiness and reports a
non-running state when no work is ready. Eligible `any` branches no longer
project demands that did not block the chosen outcome.

## Results

| Scope | Result |
|---|---|
| Combined integrated backend selection | **536 passed** |
| Combined frontend assignment/goal/approvals | **54 passed** |
| Independent six-case evidence probe | **6/6 passed** |
| G0 material/projection probes + blocked route | **3 passed** |
| Assignment affected suite | **288 passed** |
| Evidence-strength positive/negative controls | **38 passed** |

## Known pre-existing failures (not silenced)

Four `tests/test_task_lifecycle.py` controls fail identically at base
`93650be55` and at this repair source. They are outside this repair's affected
selection and are recorded in `pre-existing-task-lifecycle-at-base.log` and
`pre-existing-task-lifecycle-at-repair.log`. No claim is made that they pass.

## Boundaries

- Batch A acceptance remains withheld until independent re-verification.
- G3 atomic patch adoption, G4 full event/reassessment/uncertain-effect
  recovery and G5 two-domain adaptive employee acceptance remain unqualified.
- No model inference was run; planner 5/5, goal router 1/2 and alignment gap
  3.0 remain unchanged.
- No live provider action/send/credential/consent/spend/reseed/deployment;
  historical `111/123` and accepted tags are unchanged.
