# Exact namespaced business identity — 92e7c1f26

Status: focused completion-safety repair. The previously accepted employee
episode remains evidence at its original source; no UI/model rerun was made for
this repair.

## Defect

A required invoice reconciliation for `PO-8841` was satisfied by a receipt
whose `po_id` was `PO-88410`, `PO-884`, or whose `invoice_id` happened to contain
`PO-8841`. The prior matcher compared normalized substrings across every
business identity field.

## Repair

- Requirements persist a structured `subject_identity` map separate from the
  human-readable subject label.
- The wait compiler binds exact `po_id` and any known `invoice_id` from unique
  accepted evidence identities into their own namespaces. Ambiguous or
  conflicting candidates persist no identity and remain unresolved.
- Completion compares each required namespace with exact opaque equality after
  trimming only outer whitespace. Punctuation, case, internal spacing and
  leading zeros are preserved; there is no substring, prefix/suffix, universal
  alphanumeric collapse or cross-namespace comparison.
- Missing observed identity is unknown; wrong identity refutes. Every known
  required identity must match.
- Legacy requirements that carry only a human subject remain fail-closed if no
  structured identity can be bound.

## Source impact

The successful episode is frozen at source `70a74cd02b5` and evidence
`4fd8951cc`. It remains valid at that source. This repair changes the identity
matcher/compiler and adds tests; it does not alter the recorded episode,
artifact bytes, operation IDs or the original manifest. A fresh UI/model
episode is not claimed for this repair.

## Controls

- Independent verifier probe: `/private/tmp/test_verifier_employee_subject_70a.py`
  now passes all three wrong-identity cases.
- Added exact positive, prefix-long, prefix-short, swapped-namespace,
  leading-zero/punctuation, missing-identity, multiple-required-identity and
  ambiguous-candidate controls.
- Public status route: wrong PO receipts leave the requirement unresolved and
  the job non-terminal; the exact PO completes.
- Fresh-session lifecycle reads preserve the structured requirement and its
  unresolved/satisfied state.
- Durable wait compiler asserts the bound `po_id`/`invoice_id` values.

## Boundaries

- No live/cloud provider, credential, consent, send, spend, download,
  deployment or new model authority.
- Full G5 and general model judgment remain subject to independent acceptance.
- Historical 111/123, planner 5/5, goal router 1/2 and alignment gap 3.0 are
  unchanged.
