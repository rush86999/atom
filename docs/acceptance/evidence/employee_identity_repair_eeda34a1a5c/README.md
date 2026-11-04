# Exact namespaced business identity and report withholding — eeda34a1a5c

Status: focused completion-safety successor to
`employee_identity_repair_92e7c1f26`. The accepted employee episode remains
evidence at `70a74cd02b5`; no UI/model rerun was made for this repair.

## Defect

A required reconciliation for `PO-8841` was satisfied by `PO-88410`,
`PO-884`, or an `invoice_id` containing `PO-8841`. The prior matcher compared
alphanumeric-collapsed substrings across all identity fields.

## Repair

- Requirements persist a structured `subject_identity` map separate from the
  human label. The wait compiler binds exact `po_id` and any unambiguous known
  `invoice_id` from accepted evidence; ambiguous candidates bind nothing and
  remain unresolved.
- Completion compares every required namespace exactly after trimming outer
  whitespace. Case, punctuation, internal spacing and leading zeros are
  preserved; there is no substring, prefix/suffix, collapsed-alphanumeric or
  cross-namespace comparison. Missing identity is unknown; wrong identity
  refutes.
- Legacy subject-only requirements are fail-closed unless the profile's
  primary namespace can be bound exactly.
- Requested document/spreadsheet/presentation steps now refuse to render while
  any scoped business result is unresolved. A receipt for another PO cannot
  publish the objective's report; the step stays waiting with the
  requirement's next action and no artifact file is created.

## Source impact

The successful episode (`279a603f-...`, wait `await-c44df7cd...`, quote
`524e759f...`, reconciliation 270.00, artifact
`8d0d48773c7e1bca5ee587872f818e0738035d868fb95e7e9245a53f5f6b063e`) is
unchanged at source `70a74cd02b5` and evidence `4fd8951cc`. Its receipt bore
the exact required PO-8841; the defect was acceptance of *other* subjects, not
the correctness of this episode. The repaired compiler writes structured
identity for new requirements; the historical bundle is not re-attributed or
replayed.

## Controls

- Independent verifier subject probe: **3 passed** (long prefix, short prefix,
  swapped namespace).
- Focused affected suite: **405 passed** (includes the prior 402 plus three
  wrong-subject report twins).
- Added exact positive, prefix-long/short, swapped namespace, leading
  zero/punctuation, wrong invoice under the correct PO, missing identity,
  every-required-identity and ambiguous-candidate cases.
- Public status route negative/positive twins and fresh-session lifecycle reads
  preserve the structured requirement.
- Requested report: wrong `PO-88410`/`PO-884` receipts leave the requirement
  unresolved, the artifact step waiting and no file on disk; `PO-8841`
  publishes and completes.
- Frontend AssignmentPanel **9 passed**; `tsc --noEmit` exited 0.

## Boundaries

- No live/cloud provider, credential, consent, send, spend, download,
  deployment or new model authority.
- Full G5 and general model judgment remain unverified.
- Historical 111/123, planner 5/5, goal router 1/2 and alignment gap 3.0 are
  unchanged.
