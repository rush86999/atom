# Brennan release manifest — fixed six-case suite (2026-10-06)

Per `BRENNAN_FIRST_PRODUCT_COMPLETION_PLAN_2026_10_06.md`: the cases and
expected outcomes are recorded BEFORE further fixes; the suite runs only
after the browser submission blocker is resolved, against a frozen
candidate. Three trials per case, same candidate; every trial reported.

## Frozen candidate (fill at freeze time)

| Field | Value |
| --- | --- |
| Commit | (pending — after backend owners finish; carries e7cc7c893 + credit-failure detector + attach-or-create) |
| Serving source | (pid, start time, restart script output) |
| Configuration | ATOM_TASK_LIFECYCLE_ENABLED=1, model flags, provider pool state at run time |
| Database | (dev DB identity + pre-run snapshot id) |
| Fixtures | disposable fork canvas (not the original), trained agent 9837ec71, lessons: BurrKing basis / Tennsmith basis / Service estimate |

## Case definitions

### Case 1 — Full quote investigation + explicitly authorized drafting
- Input: owner asks (ordinary language) to investigate ALL requested
  quotation items on the disposable fork using taught sources; then, after
  the comparison exists, explicitly authorizes drafting.
- Expected: every item accounted for with draft value / source value +
  identity / date-freshness / discrepancy / decision-needed; queued reads
  complete without "continue"; drafting applies teaching + verified
  correspondence, preserves approved manual prices, leaves unresolved
  commitments unasserted, does NOT send; all of it survives reload.
- Verdict: [ ] [ ] [ ]

### Case 2 — Subset request + "other machinery" follow-up
- Input: owner names a SUBSET of items; follow-up asks about "the other
  machinery".
- Expected: the subset does not expand to the whole canvas; the follow-up
  resolves to the remaining items (or asks precisely which); scope stays
  the owner's requested scope throughout.
- Verdict: [ ] [ ] [ ]

### Case 3 — Taught formula, missing input, answer, changed-input recalc
- Input: "Estimate this service job using our taught rates." (no inputs);
  owner answers "17.5 hours, no materials"; then "recalculate — 12 hours".
- Expected: ONE precise question for the missing inputs; computation via
  the engine ($2,625 then $1,800); each recorded as its OWN operation with
  inputs + content-derived policy version; distinctions preserved.
- Verdict: [ ] [ ] [ ]

### Case 4 — Ambiguous item, conflicting source versions, approved manual value
- Input: an item code carried by multiple files/versions; one row holds an
  approved manual price.
- Expected: ambiguity → clarification (never first-match); conflicting
  versions → coherent-version or explicit conflict; the approved manual
  value is PRESERVED and marked; only real decisions block.
- Verdict: [ ] [ ] [ ]

### Case 5 — Provider failure then another message (browser leg)
- Input (UI): successful message → controlled provider failure (isolated
  stub or exhausted-test route, never the real account) → another ordinary
  message after failure → provider recovered.
- Expected: truthful terminal error (success=False, error_code, remedy);
  rows persisted with quality=error; the NEXT message dispatches (Send
  button AND Enter recorded separately); recovered provider succeeds;
  reload preserves history WITHOUT duplicates. A prior failed message
  must not permanently disable a new request.
- Verdict: [ ] [ ] [ ]
- Status (2026-10-04 update): composer submission boundary RESOLVED —
  the composer was never broken. Live evidence: Send-button click and
  Enter keypress each dispatched exactly one POST (button: 30-hour
  estimate → $4,500; Enter: 31-hour estimate → $4,650); two reloads
  preserved every turn exactly once (no duplicates). The earlier
  zero-request traces were automation artifacts (CUA coordinates
  ~22px below the composer; transient post-HMR relayout hid the
  textarea). One real boundary defect found and fixed at this seam:
  the canvas page's `no_llm_provider` branch replaced the backend's
  truthful credit-exhaustion message with static "No AI provider
  configured" text (wrong cause, wrong remedy) — now renders the
  backend message with the static text as fallback only
  (`pages/canvas/[id].tsx`, parity with `useChatInterface`), locked by
  a component regression that also proves the next message dispatches
  after a failed turn (`tests/pages/canvas-detail.test.tsx`). Still
  PENDING for this case: a live provider-failure turn and
  recovered-provider success in the browser — requires the isolated
  stub against the frozen candidate (the live pool's fallback provider
  keeps serving; forcing failure would touch the real account or
  Codex-owned backend code). Backend recovery remains
  regression-proven in-process only.

### Case 6 — Restart during queued work + second conversation isolation
- Input: queued research in flight → server restart; then a second
  conversation with similar wording but different inputs.
- Expected: the interrupted job resumes without duplicate effects;
  the second conversation's calculation uses ITS OWN inputs (no
  cross-job evidence, no reused record).
- Verdict: [ ] [ ] [ ]

## Trial conventions

- No invisible retries; operator rephrase/seed/tool-select/state-repair/
  manual delivery ⇒ mark the trial ASSISTED. Genuine business
  clarifications allowed and counted separately.
- Result file rows: candidate identity, case/trial id, expected vs actual,
  job/operation/source ids, timings, cost when available, interventions,
  evidence link, verdict.
- One current support table; earlier artifacts remain as history only.

## Known state at manifest creation

- Transient test failure on record: `TestRound72VersionCoherence::
  test_dropped_cross_sheet_is_version_conflict` failed once in a full-file
  run and passed on rerun — INTERMITTENT, unexplained; do not treat the
  rerun as closure.
- Recovery claim scope: credit-failure recovery is proven at the BACKEND
  boundary (in-process regression); the browser submission path is the
  open blocker.
