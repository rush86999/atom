# Minimal-input judgment diagnosis — 2026-10-28

This is a **diagnosis**, not a green acceptance run and not a replacement for
the preserved failed UI evidence in
`docs/acceptance/evidence/whole_app_20261027/core_release_ui_loop_20261028/`.
That directory is unchanged.

## Question

The preserved post-restart case assessed `IN-7301` (Invoice Amount **3200**)
as `HOLD` even though its own basis said the policy requires `DECLINE`. Was
that caused by context interference, or can the model not follow the simple
rule even with minimal complete inputs?

Decision labels have **no inherent safety ranking**. The only authority is the
applicable teaching. The expected label in this report is read from that
lesson's own thresholds (`below 5000 → DECLINE`, `5000–9999 → HOLD`,
`at or above 10000 → HOLD for CFO review`), never from an ordering such as
HOLD > DECLINE.

## Inputs

- `preserved_full_request.json` — the exact 14-message request captured by the
  review-diagnosis seam for the failed post-restart turn
  (execution `605af591-153e-4428-a62d-44a0f8f58987`).
- `preserved_full_response.json` — the exact response preserved from that turn.
- Policy ID `044d2b537b4d4a2593dbaca52c64b8da`, the single current corrected
  lesson.
- Decision vocabulary `FUND`, `HOLD`, `DECLINE`, unchanged.

The minimal request keeps only the same output contract, the single
authoritative row (`vendor_loop!R2`, `Invoice Amount=3200`, `State=Open`), the
single applicable policy, and the same task-owned vocabulary. The fixed
boundary set adds unfamiliar values and the policy's own boundaries:
`4321.25`, `4999.99`, `5000`, `9999`, `10000`.

## Settings (identical for both shapes)

`ollama/llama3.1:8b`, temperature `0.7`, `max_tokens=6000`,
`ATOM_REVIEW_STRUCTURED=0`, `ATOM_LOCAL_ONLY=true`, non-streaming.

## Results

`results.json` is the one-shot run; `analysis.json` separates the decision the
model actually wrote from the product validator's certification. No decision
was rewritten or re-ranked.

| Case | Amount | Policy says | Raw decision | Substance | Certified |
|---|---:|---|---|---:|---:|
| Preserved full context (IN-7301) | 3200 | DECLINE | HOLD | no | yes |
| Preserved row, minimal (IN-7301) | 3200 | DECLINE | DECLINE | yes | no |
| Unfamiliar (IN-8801) | 4321.25 | DECLINE | DECLINE | yes | yes |
| Boundary (IN-8802) | 4999.99 | DECLINE | DECLINE | yes | no |
| Boundary (IN-8803) | 5000 | HOLD | DECLINE | **no** | no |
| Boundary (IN-8804) | 9999 | HOLD | HOLD | yes | yes |
| Boundary (IN-8805) | 10000 | HOLD | HOLD | yes | yes |

Summary: minimal substance **5/6**, minimal certification **3/6**; full-context
substance **0/1**, full-context certification **1/1**.

The preserved 3200 case flips from the full-context `HOLD` to the minimal
`DECLINE`, so context interference is a real contributor for that row. But the
minimal run still contradicts the policy at the exact `5000` boundary
(`DECLINE` where the lesson says `HOLD`). Its two uncertified cases are format
failures: the model copied the whole evidence line into `evidence_ids`, and in
one case used an unlabelled code fence. Format repair cannot certify the
`5000` decision.

## Conclusion

**Stop prompt patching.** Even with the smallest complete input, the local 8B
model does not reliably apply the taught thresholds. Structured output may
improve schema compliance; it cannot certify that `HOLD` follows a
`below-5000 → DECLINE` rule. Parsing the word `DECLINE` out of `basis` and
replacing the decision would be an unsafe shortcut and was not done.

This is a measured capability limitation of the local route, not proof that
the review contract or the decision vocabulary is wrong.

## Proposed bounded comparison (not executed)

Keep the local-only restriction unchanged. If the owner authorizes one bounded
comparison, run this same fixed 6-case harness once under the already-authorized
`deepseek/deepseek-v4-pro` route (or another route the owner names), with the
same contract, vocabulary and thresholds. Do not change the policy or the
expected labels, and do not repeat until green. The purpose is to measure
whether the limitation is the local 8B model or the contract itself.

## Pilot preserved separately

`pilot_incomplete_input/` is the first pass. Its minimal prompt omitted the
row values (the output contract lists evidence IDs, not amounts), so the model
could not see `3200` and hallucinated values. It is preserved for audit but is
**not** used for the capability conclusion above. The corrected run above
adds only the authoritative row values and was executed once.
