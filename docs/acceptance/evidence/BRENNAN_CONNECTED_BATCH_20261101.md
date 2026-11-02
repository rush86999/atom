# Brennan connected batch — review handoff

Status: **submitted for independent verification; not self-accepted.**
Historical 111/123 scope is unchanged. No live provider lookup, refresh, write
or send occurred.

## Candidate

| Item | Value |
|---|---|
| Branch | `codex/brennan-joint-review-20261101` |
| Executed source head | `6431bcb7857fd43dffc1ed685fffe47044669e5c` |
| Tree at execution | clean (`dirty=false`) |
| Base candidate | `c442cd9d7eeba44e17feada5e452c0c46fc9be13` |
| Integration worktree | `/private/tmp/atom-brennan-review` |
| Clean executed checkout | `/private/tmp/atom-brennan-clean` (detached at the source head) |

## Canonical manifest

Use:

`docs/acceptance/evidence/brennan_connected_browser_20261101_final/MANIFEST.json`

It binds the executed source and hashes, provider substitutions, exact command
shape, 25/25 browser checks, test totals (312/284/279/178/32), process
identities, four run identities, effect counts and explicit exclusions.

An independent clean run on the same source is preserved at
`docs/acceptance/evidence/brennan_connected_browser_20261101/` (also 25/25,
PID `65057` -> `65066`). Earlier 24-check and dirty attempts are preserved in
history and are not acceptance evidence.

## What the gate proves

- The backend serves and attests its own boot source: revision, clean source
  id, instance id, PID, process start, repository/backend tree and
  world/database. An occupied port is refused, not reused.
- The persisted executable bound counts the actual JSON representation
  (`ensure_ascii=True`, default separators): exact 4,194,304 bytes accepted,
  limit-plus-one and escaping/multibyte/many-short-value/nested-receipt
  overflows refused. Read overflow is typed; post-dispatch mutation overflow
  is uncertain with the original remote identity and reconciles without a
  resend.
- The real Assignments page completes: qualification wait, leave, real backend
  restart, v1 calculation `362.50` before correction, source v2 invalidation,
  corrected `376.75`, v2 receipts/hashes, v1 only in `prior_results`, estimate
  readback, Outlook draft, zero send attempts, reload.
- Recovery: two-page duplicate resume is a no-op; cancellation refuses a late
  correlated response, resume and gap resolution; provider acceptance with lost
  readback is uncertain, the dependent draft stays blocked, a real restart
  preserves the effect/call counts and does not resend, reconciliation settles
  the original estimate, and only then the draft completes without a send.
- Public-route qualification controls cover missing/ambiguous discounts,
  stale/duplicate answers, source-change invalidation, reassessment,
  cancellation, duplicate resume and uncertainty. Bookkeeping controls cover
  vendor/CoA/period resolution, one create, full readback and the refusal/
  reconciliation cases. OneDrive XLSX uses the production registered
  action/parser through the public route.

## Exclusions

- Standalone acceptance server; not full-app authentication/profile/navigation
  proof.
- No live Zoho/Microsoft credentials, refresh, write or send.
- No universal mini-app/canvas runtime claim.
- Evidence commits are docs-only after the executed source head and were not
  served.
- Historical 111/123 is unchanged; this is additional workflow qualification.

## Next

Continue the user-authored-canvas successor on a separate branch under
`docs/engineering/USER_AUTHORED_CANVASES.md` after independent verification.
