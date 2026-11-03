# Employee proof-binding repair — results

Executed source: `c6ac292f3` (clean worktree at the integrated run).

## Independent withheld controls

`evidence-g0-binding-probes.log` — **12 passed**, including the exact
three-case independent binding probe:

| Control | Observed |
|---|---|
| verified source with status only | unknown; dependent not eligible |
| Sent Items presence with no correlation | unknown |
| correct operation id + wrong message id | refuted |

## Typed proof matrix

`proof-binding-matrix.log` — **11 passed**:

- source profile valid complete twin; status-only, missing identity, missing
  version, missing observed coverage;
- wrong requested resource/version, declared operation id and subject;
- external profile valid twin; missing operation, missing remote identity;
  wrong provider/message/account identity;
- artifact profile valid twin; missing artifact, revision or sha256; durable
  artifact proof without a verification envelope;
- local-calculation valid twin; missing material result; durable value proof;
- non-finite, malformed, paired-missing and partial-population coverage;
- fact qualification: bare/note evidence refused, accepted source ref matched,
  authored authority accepted;
- Sent Items: missing correlation, missing message, wrong message, swapped
  namespaces, boolean shortcuts, nested durable receipt readback, message id
  and account mismatch, present=false.

## Executor and outcome consumers

`focused-affected.log` — **225 passed**. Real executor controls:

- weak verified receipt: dependent call count zero, independent branch applied,
  assignment not completed;
- complete verified twin: dependent executes and completes, and remains
  readable after restart;
- provider acceptance only: Sent Items unresolved, assignment not completed;
- matching explicit readback: Sent Items true and completed, including after a
  fresh executor/session.

## Other matrices

| Log | Result |
|---|---|
| `backend-integrated.log` | **573 passed** |
| `frontend-integrated.log` | **54 passed** |
| `two-domain-campaign.log` | **4 passed** |
| `patch-invariants.log` | **8 passed** |
| `corrected-patch-invariant-probe.log` | **3 passed** |

The deterministic two-domain campaign remains: industrial quote 494.75
feasible and 5-day-limit infeasible; procurement corrected 270.00 bill and
closed-period negative.

## Pre-existing failures

`pre-existing-task-lifecycle-at-source.log` records the same four
`test_task_lifecycle.py` failures as the parent/base. They are disclosed, not
counted.

## Boundaries

Deterministic mechanisms only. Served adaptive choice and ordinary-product
two-domain journey remain unrun. No model inference or live provider action;
historical denominators unchanged.
