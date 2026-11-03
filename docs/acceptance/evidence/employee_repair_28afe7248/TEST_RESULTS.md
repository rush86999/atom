# Employee strict proof-schema repair — results

Executed source: `28afe7248` (clean worktree at the integrated run).

## Independent minima

`independent-probes.log` — **15 passed**, including the four c6ac minima:

| Control | Observed |
|---|---|
| Sent Items with only operation correlation | unknown |
| Sent Items with only message identity | unknown |
| coverage complete=true + known='unknown' | unknown; dependent not eligible |
| coverage complete=true + truncated='no' | unknown; dependent not eligible |

The original three a770 binding cases, six evidence-strength controls and two G0
controls also pass.

## Generated schema matrix

`generated-schema-matrix.log` — **39 passed**:

- each required source field omitted, `None`, wrong type and wrong value;
- supported coverage variants: complete-only, complete+known+truncated,
  known+truncated, complete with accepted counts;
- malformed/contradictory coverage: string/None/number flags, complete=false,
  known=false, truncated=true, non-finite/negative/unpaired/partial counts;
- Sent Items required-field omission, wrong type, wrong identity, swapped
  namespaces, bare booleans;
- real-executor malformed-coverage negative with dependent call count zero and
  independent branch retained;
- real-executor Sent Items missing-correlation negative with outcome unresolved.

`proof-binding-matrix.log` — **14 passed**, including the hand-built positive
twins for source/external/artifact/local profiles, fact scope, Sent Items
message/account identity and restart durability.

## Executor and outcome consumers

`focused-affected.log` — **270 passed**:

- verified receipt malformed/absent/conflicting/truncated proof: dependent not
  called; independent branch applied; assignment not completed;
- complete verified twin: dependent executes and completes, survives restart;
- provider acceptance only: Sent Items unresolved; not completed;
- operation-only and message-only Sent Items: criterion unresolved; not
  completed;
- matching operation+message readback: Sent Items true and completed, including
  after a fresh executor/session.

## Other matrices

| Log | Result |
|---|---|
| `backend-integrated.log` | **618 passed** |
| `frontend-integrated.log` | **54 passed** |
| `two-domain-campaign.log` | **4 passed** |
| `patch-invariants.log` | **8 passed** |
| `corrected-patch-invariant-probe.log` | **3 passed** |

## Pre-existing failures

`pre-existing-task-lifecycle-at-source.log` records the same four
`test_task_lifecycle.py` failures as the parent/base. They are disclosed, not
counted.

## Boundaries

Deterministic mechanisms only. Served adaptive choice and ordinary-product
two-domain journey remain unrun. No model inference or live provider action;
historical denominators unchanged.
