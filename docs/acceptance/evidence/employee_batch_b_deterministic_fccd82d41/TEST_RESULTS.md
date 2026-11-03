# Employee Batch B deterministic campaign — results

Executed source: `fccd82d41` (clean worktree at the integrated run).

## Two-domain campaign

`two-domain-campaign.log` — **4 passed**:

| Case | Observed |
|---|---|
| industrial quote positive | eligibility wait, price/quantity revisions, delivery failure, approved equivalence, final **494.75**, artifact + draft with no send |
| industrial quote negative | 7-day equivalent vs 5-day limit: 494.75 calculated but **no artifact, no completion** |
| procurement positive | invoice/receiving mismatch wait, independent checks, restart, old-correlation refusal, corrected 270.00 invoice, one approved bill, duplicate reply terminal |
| procurement negative | closed period refuses bill creation; **zero bill effects** |

The campaign uses independent `Decimal` arithmetic; it does not import the
production calculator as its own expected-result oracle.

## G3/G4 focused controls

`g3-g4-focused-controls.log` — **7 passed**:

- bounded plan rewiring (inputs/dependencies) after invalidation;
- replay of an observation returns `already_applied` and does not reopen work;
- an executed job reopened by a source change re-runs only the affected
  branch; the independent receipt keeps its operation id/result;
- uncertain external effect blocks dependents, survives restart without a
  resend, and reconciles the original operation;
- provider-accepted-then-worker-lost reconciles without a second effect;
- blank-currency clarification survives restart and resolves once;
- the public patch route adopts a provenance-bearing fact and refuses a stale
  base.

## Integrated and probes

| Log | Result |
|---|---|
| `backend-integrated.log` | **544 passed** |
| `frontend-integrated.log` | **54 passed** |
| `evidence-and-g0-probes.log` | **9 passed** |
| `assignment-employee-suite.log` | **295 passed** |
| `two-domain-campaign.log` | **4 passed** |
| `g3-g4-focused-controls.log` | **7 passed** |

`evidence-and-g0-probes.log` contains the independent six-case evidence probe,
both G0 boundary probes and the public blocked-readiness route.

## Pre-existing failures

`pre-existing-task-lifecycle-at-base.log` and
`pre-existing-task-lifecycle-at-source.log` record the same four
`test_task_lifecycle.py` failures. They are disclosed, not counted as passing
evidence, and are outside the campaign's affected selection.

## Boundaries

Deterministic level only. The served-model adaptive-choice matrix and
ordinary-product two-domain journey are not run. No live provider action or
model inference; historical denominators and tags unchanged.
