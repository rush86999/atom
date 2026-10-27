# Critical-path measurements — 2026-10-27

Source: preserved isolated-rehearsal server log (credential-bearing URLs
redacted; raw log not published). These are observations, not tuning targets.

## Observed stage ranges

| Stage | Observed |
|---|---|
| General interpretation | 26.8s – 57.6s |
| Accepted-confirmation fast path | 0.000s (general model skipped) |
| Tool plan (overlapped) | 8.6s – 51.8s |
| Tool execution / read | 4.7s – 15.2s |
| Reply generation (streaming) | 2.5s – 24.7s to first full text |
| Reply generation envelope | 12.2s – 85.5s |

The 95s budget is usually consumed by interpretation **plus** the overlapped
plan and reply. A 115.2s response is therefore not explained by one slow
provider call alone; it is the sum of stages that each fit under a per-stage
cap but not under the turn cap.

## What the new batch measures

- `[turn-interpretation] accepted pending-task confirmation; general
  interpretation skipped` + `[stage-timing] ... interpretation: 0.000s`.
- `[review-timing] contract_prompt_ms=... elapsed_s=... contract=...`.
- `[review-timing] validation_ms=... reviewed_at_s=... ok=... subjects=...`.
- `[stage-timing] turn finalization: elapsed_s=... review_at_s=... success=...
  outcome=... review_required=...`.

The final resolution uses `reviewed_at_elapsed_s` — the clock reading when the
assessment was created, not when finalization noticed it. A review after the
deadline is not promoted to success.

## Immediate reading

1. Exact confirmations already skip general interpretation; their remaining
   cost is tool planning + reply. Do not add a longer interpretation wait.
2. Review turns still pay a full reply generation envelope after the read.
   The next latency work should measure whether planning is still running
   after the accepted confirmation resolved the scope; if so, skip it the same
   way interpretation is skipped.
3. No deadline widening or provider rotation is justified by this evidence.
