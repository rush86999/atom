# Employee strict proof-schema repair — source 28afe7248

Status: **new product source submitted for independent verification.** Batch A
acceptance and served adaptive employee capability remain unclaimed.

This source completes the strict proof-profile schema requested in the
`c6ac292f3` review: Sent Items now requires both governed-operation correlation
and an observed message identity, and every explicit coverage flag is
type-validated before completeness is evaluated.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `28afe7248` (full SHA in `MANIFEST.json`) |
| Prior reviewed source | `c6ac292f3` / evidence `caff5f350` |
| Transport | controlled local service/DB; no live provider |

## Strict schema repairs

### Sent Items minimum proof

A Sent Items observation requires, at minimum:

1. an explicit boolean presence observation;
2. a governed operation/request correlation identity; and
3. an observed stable message identity (provider or message reference).

Every expected identity in its own namespace must be present and match. A
matching operation with no observed message is unknown; a matching message with
no operation correlation is unknown; a wrong message refutes even when the
operation matches. Account/mailbox is validated when expected. Bare booleans,
boolean `sent_items`, caller assertions and model-supplied facts are not proof.

### Strict coverage validation

Every explicit `complete`, `known` and `truncated` field must be an actual
boolean before completeness is evaluated. A malformed or explicit-`None` field
invalidates the profile; a valid `complete=true` cannot rescue a malformed
sibling flag. Population counts must be finite, integral, nonnegative, paired
and fully accepted. Missing proof stays unknown; contradiction/incompleteness
does not release dependent work. Coverage is an observed property of the
durable result/receipt, not a claim the verification envelope may assert alone.

### Generated matrix

The repository now contains a generated omission/type/identity matrix covering:

- each required source field omitted, `None`, wrong type or wrong value;
- supported complete/known/truncated variants and omission combinations;
- malformed, non-boolean, non-finite, unpaired, negative and partial population
  counts;
- Sent Items required-field omissions, wrong types, wrong identities, swapped
  namespaces and boolean shortcuts;
- real-executor negatives with zero dependent calls and retained independent
  work, plus valid twins that complete.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **618 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Focused affected suites | **270 passed** |
| Proof-binding matrix | **14 passed** |
| Generated schema matrix | **39 passed** |
| Two-domain deterministic campaign | **4 passed** |
| Patch invariants | **8 passed** |
| Independent schema/binding/evidence/G0 probes | **15 passed** |
| Corrected patch-freshness probe | **3 passed** |

The independent probe set includes the four `c6ac292f3` minima (operation-only
Sent Items, message-only Sent Items, and both malformed-coverage examples) and
the original three `a770ced10` binding cases.

## Remaining boundaries

- Served-model adaptive-choice G5, held-out model campaign and ordinary-product
  two-domain journey are not run; adaptive employee capability remains
  unqualified.
- Batch A acceptance remains withheld pending this independent review.
- Four `test_task_lifecycle.py` controls fail identically to the parent/base;
  disclosed, not counted.
- No model inference or live provider action/send/credential/consent/spend;
  planner 5/5, goal router 1/2, alignment gap 3.0 and historical `111/123`
  unchanged.
