# Published supported scope — C16 combined candidate

Candidate export `c0b02bcd7966ac76f4d733184d0c48a7` (world `c16_fin`, port 8078).
Candidate = the committed tree at the freeze commit; see `CANDIDATE_FREEZE.json`
for the sha256 of every included product file and the 173 uncommitted paths that
are deliberately excluded as other streams' work.

## Addendum — the D5 browser write-path run (2026-09-28, after `6e34725c7`)

A real browser, a real canvas page, the **production** planner, no injected
plan. World `d5_browser_edit` (export `4f6844df5909d557…`, `source_id`
`6e34725c7017-dirty.*`), run dir `run-26ebe1ca462c`, backend `:8086`, frontend
`:3106`. Artifacts: `d5_browser_edit_run1/`.

**Editing stays EXCLUDED.** Nothing below promotes it.

### Now measured, and now supported (the read/write boundary of the composer)

| Capability | Evidence | Result |
|---|---|---|
| The `/canvas/{id}` composer posts the right canvas: id, type, page, content, session | `d5_browser_edit_run1/browser_canvas_edit_*.json` → `captured_request.post_data`, 9/9 V3 assertions, both configurations | pass |
| A canvas created through the supported endpoints opens in the real page and its composer is live | V1 + V2, `seeded_via: api` | pass |
| The turn's visible answer agrees with the durable store, in both directions | V5, both configurations | pass |
| The transcript and the durable canvas recover across a browser reload | V6, both configurations | pass |
| A DECLINE is refused cleanly: reservation released, **zero** update audit rows, nothing written | V4 + `planner_evidence_from_world_log.json` (unpinned) | pass |

### Still NOT supported — the exclusion is unchanged

**1. Canvas editing with the PRODUCTION (unpinned) planner.** 32/36 applicable.
The turn reached the planner, the planner answered with a well-formed
`CanvasEditPlan` in 0.9 s, and the answer was an **internally consistent
decline** — no `SCHEMA-BOUNDARY` violation, so the `6e34725c7` contract check
never fired and the bounded repair was never reached. Outcome
`updated=false, no_apply=true, reason=planner_declined`, no mutation, and a
truthful user-visible refusal. A decline is correct behaviour, not a
capability.

**2. Control: the same bytes DO apply when the model is pinned.** With
`ATOM_ASYNC_EDIT_PLAN_MODEL=deepseek/deepseek-flash` the identical request landed
(38/41 applicable): durable content changed, exactly one update audit row
attributed to the turn's `operation_id`, `review_status=accepted`,
`postcondition_verified=true`, a truthful reply, and a live canvas panel. This
is a **routing control, not a promotion**: model selection carries no authority
over whether a canvas may change, and a pinned run is not the production
configuration a user meets.

**3. The canvas panel does not render on load, and does not recover on reload.**
`CanvasPanel` applies its `lastMessage` prop only when the parent passes no
socket listener, and `/canvas/[id]` passes both — so the page loads the canvas
(its header shows the type) and then shows an **empty canvas area** until a
broadcast arrives. It renders after the agent's own edit broadcast, and is
blank again after F5. A user who opens a canvas by URL and reloads sees no
canvas. One root cause, two red assertions, in both configurations.

### Harness blockers found and worked around (the first two are why this run
### is the first browser evidence for editing at all)

- `frontend_farm.py` symlinks top-level entries, so the farm's `pages` is ONE
  symlink, and `next dev --webpack` then registers **no dynamic page route at
  all** (19 of them, including `/canvas/[id]`, silently 404; static routes
  still resolve, which is why the `/chat`-only read-path driver never saw it).
  Minimal reproduction and the working farm shape are in
  `frontend_farm_recursive.py` (this lane's own file; `frontend_farm.py` is
  another stream's and was **not** edited).
- `lib/pdf-worker-src.ts` uses a bare package specifier inside
  `new URL(..., import.meta.url)`, which webpack refuses — a compile error that
  takes the whole canvas page down (500). Worked around with a **declared farm
  shim** (one string, recorded with both sha256s, never called by an email
  canvas). The product file was accidentally overwritten once through the farm
  symlink, reverted immediately, and the write is now containment-guarded.
  **Not fixed** — the correct third-party asset resolution needs its own review.

## Supported and verified (C16 controlled cases, unchanged)

| Capability | Evidence | Result |
|---|---|---|
| Synchronous canvas edit, controlled planner | `c16_fin/c16_controlled_sync.json` | 15/15 |
| Background edit success, controlled planner | `c16_fin/c16_controlled_bg-success.json` | 28/28 |
| Background edit failure, controlled planner, empty notification channel | `c16_fin/c16_controlled_bg-failure.json` | 26/26 |
| Canvas created through the supported API is readable and editable | same runs, `canvas_seeded_via: api` | pass |
| Durable record survives interruption and is reconciled at boot | c16_d1 run, `Crash recovery: reconciled 1 agent execution` | pass |
| Reconciliation applies no second write | `reconciliation_wrote_nothing_additional`, 1 attributed audit row | pass |
| Readable terminal outcome, no bracketed diagnostic on reload | `history_has_no_raw_bracket_diagnostic` | pass |

All three cases ran on ONE export with separately recorded launches
(product-default budget for the synchronous case, 60s for the background
cases), each launch recording its run dir, fixture hash, export hash and
effective budget, and each cross-checking the measured database against the
server's own `DATABASE_URL`.

## NOT supported — do not represent as ready

**A real-planner edit does not work.** An ordinary edit request against an
API-created canvas with its context attached returns
`updated=False`, `no_apply_reason: planner_declined`, and changes nothing.
Confirmed again through a real browser on `6e34725c7`; see the addendum above
for the current mechanism (a consistent decline, not the earlier
self-contradictory plan the `6e34725c7` fix addressed).

This is NOT a provider failure. OpenRouter was verified available (HTTP 200 on
`openai/gpt-4o-mini`); the earlier 402 was a per-model credit ceiling on
expensive models, not an outage. The world log shows the planner was reached and
answered.

The repair belongs in the existing mechanism, not in per-prompt routing. That
work is not done.

## Excluded from scope

- **Origin-operation reconciliation, live.** Unit-verified against real recorded
  evidence and asserted in the harness, but not exercised end to end: whenever
  the fork is taken the interactive edit leg is abandoned, so the landed
  mutation is always the continuation's own. Tracked as a separate review item.
  Production scheduling was deliberately not altered to manufacture coverage.
  The duplicate-prevention regression is preserved and passing.
- **Artifact editing.** Correctly not promoted.
- **Preview `:3102` / backend `:8071`** — unchanged; promotion is not justified
  while the real-planner path declines.
- **The raw plan body for a clean decline.** The product logs a plan's shape
  only when the contract check fires, so a consistent decline is not quotable
  without a re-run. Closing that observability gap is a prerequisite for
  attributing the decline to the model rather than to the prompt.
