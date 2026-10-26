# S7 degraded continuation repair — 2026-10-24

**Product:** `a7b17bb380e59be806db62febdd94e9f69704e78`
**Harness:** `ae5f500e3`
**Rehearsal:** attempt 15, `attempt15_final3`
**Status:** S7 repair verified. Full-workflow pass is **held** by an
environmental pilot-guard failure, not by a product check. No cutover.

## Attempt 13 vs 14: the allocation did not shrink

Both attempts gave S7 the same effective interpretation budget:

```
bounded wait=59.9s (remaining=94.9s reserve=35.0s)
```

- **Attempt 13:** the pinned DeepSeek interpretation completed in
  ~21.7s, bound `approved_records_q2026_114.txt`, and the date-only
  comparison completed (59.71s total).
- **Attempt 14:** the pinned `deepseek/deepseek-v4-pro` response was
  `The output is incomplete due to a max_tokens length limit` at the
  5,500-token cap. The fallback chain then attempted
  `opencode-go/beam-free` (400: `logprobs` unsupported) and
  `opencode-go/qwen3.8-flash` (cancelled after 15.6s); OpenRouter was
  on quota cooldown after a 402. The outer 59.9s wait expired and
  recorded `stage_budget_exhausted`.

Result: the request stayed date-only, but the degraded path lost the
source (`sources=[]`, identity `kind_only`), inherited
`broader_comparison=true` from the message shape, and settled
`unconfirmed` even though the sentence was correct.

**Diagnosis:** this is interpretation-budget exhaustion caused by a
failed pinned response plus a slow fallback chain, not a smaller S7
allocation and not a generic continuation regression.

## Repair

1. **Durable named-source resolution.** A source named by the request
   ("the approved record") is resolved against the conversation's
   OBSERVED evidence using the existing reference collector. Prior
   requirement carriers are never evidence; several candidates stay
   ambiguous; a non-match stays unresolved.
2. **Bounded refinement, not a model requirement.** The bounded shape
   (one named, uniquely observed source; one canonical field;
   comparison-shaped; no mutation/send obligation) gets at most a
   **5s optional** model refinement. A resolved proposal (identifier,
   exclusion) still wins. Timeout, unresolved origin, or a schema-valid
   record with no source falls back to the explicit
   `deterministic:continuation` record / deterministic fill. The 59.9s
   S7 wait can no longer be consumed by this shape.
3. **Scope from the request, not the prior turn.** Degraded/direct
   requirements derive `broader_comparison` from the request's own
   canonical fields. A date-only ask stays narrow; a genuinely broad
   follow-up keeps its whole-document obligation; a prior broad S3
   carrier is not imported.
4. **No arbitrary source.** A generic floor `document` capture is a
   nomination, refined by the named reference. A specific floor file
   plus a different named record becomes an unresolved mixed marker,
   not a one-source completion. `verified_comparison_reply` refuses
   ambiguous/unresolved identities.
5. **Provider contract frozen.** The rehearsal gate derives the
   authorized provider set from the declared policy: `automatic`
   authorizes all configured providers; `selected` authorizes only its
   non-empty subset; invalid/empty authorizes nothing. Every POST,
   reply route, and structured route must be inside that set. Historical
   Ollama/DeepSeek intended-route observations are recorded but no longer
   decide the pass.

## Verification

- **414 focused backend tests passed** (continuation, comparison,
  provider contract, edit/no-op, orchestrator). Two
  `test_fallback_honesty` receipt fixtures fail identically on parent
  `73bcae400`; they are pre-existing and outside this slice.
- **Attempt 15: 61/62 checks.** Every functional, scope, write, route,
  settlement, restart and policy check passed. The sole failure is
  `pilot_untouched` (see below).
- **S7 attempt 15:** `deterministic:continuation`; one research action;
  a 5s DeepSeek refinement was attempted and did not resolve; source
  `approved_records_q2026_114.txt` resolved with a file id; fields
  exactly `["expiration_date"]`; `broader_comparison=false`; context
  fulfillment `completed`; zero canvas writes; response, settlement and
  fresh history agree; outcome `partial` because the captured prior
  outlook obligation remains open; `success=true`; total 28.67s.
- **Provider policy:** `automatic`, authorized
  DeepSeek/Ollama/OpenCode Go/OpenRouter; `provider_policy_declared`,
  `provider_policy_respected`, `provider_reply_authorized` and
  `provider_structured_authorized` all passed. Historical
  `allowlist_clean` is recorded `false` (OpenCode Go/OpenRouter POSTs)
  and `reply_parity` `true`; neither is a gate.

## Pilot guard failure (environmental)

The pilot backend `:8001` and frontend `:3000` were **already absent
before** the rehearsal launched. The declared config captured:

```
pilot_before: backend_8001_listening=false,
              frontend_3000_listening=false,
              health_error="ConnectError('[Errno 61] Connection refused')"
```

Both `pilot_before` and `pilot_after` identity captures are null; the
pilot pids from the earlier checkpoint (16055/16488) no longer exist.
The candidate ran on its isolated `:8121` world. The guard therefore
cannot pass: `pilot_untouched` requires a live pilot identity and
listening ports. This is not evidence that the rehearsal touched the
pilot, and it is not a product-check failure — but the workflow is not a
clean pass until the pilot is restored or its absence is explicitly
accepted.

**No cutover was executed.** The pilot code/configuration was not
changed by this work. Restoring the pilot is a separate owner decision.

## Known out-of-path residuals (review comments)

- A mixed floor-file + named-record requirement has an unresolved
  identity, but that real-turn case can still settle `completed` through
  the fallback path rather than `_context_backed_fulfillment`. It cannot
  affect the captured S7 date-only ask (no floor file); follow up if
  mixed floor-file completion matters generally.
- Determinerless `insert client name` is not vetoed (the requested
  `insert the client name` is). Outside the captured S7 shape.
- An uncaptured refinement dispatch is indistinguishable from no
  dispatch in the log-derived route check; logged unauthorized POSTs are
  still caught by the policy allowlist.

## Evidence

`docs/acceptance/release_evidence_20261024/byok_policy_attempts/attempt15_final3/`
(config, summary, result, console, predeclared config, checksums) and
`attempt13_final/` / `attempt14_final2/` for the comparison.
