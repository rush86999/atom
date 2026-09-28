# Published supported scope — C16 combined candidate

Candidate export `c0b02bcd7966ac76f4d733184d0c48a7` (world `c16_fin`, port 8078).
Candidate = the committed tree at the freeze commit; see `CANDIDATE_FREEZE.json`
for the sha256 of every included product file and the 173 uncommitted paths that
are deliberately excluded as other streams' work.

## Supported and verified

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

This is NOT a provider failure. OpenRouter was verified available (HTTP 200 on
`openai/gpt-4o-mini`); the earlier 402 was a per-model credit ceiling on
expensive models, not an outage. The world log shows the planner was reached and
answered, and the failure is a genuine contract problem in its output:

    core.chat_canvas_editor: canvas edit: plan wants_edit=False but carries 1 op(s)
    and no declared content -- self-inconsistent, taking one bounded repair

The model emitted a self-contradictory plan (`wants_edit=False` alongside a
populated `ops` array). The editor detected the inconsistency and took its
bounded repair, which also did not produce an applicable plan, so it declined.
A controlled accepting plan cannot substitute for this, so the controlled
results above establish the effect path only.

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
