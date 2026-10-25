# S7 degraded continuation repair — 2026-10-24

**Product (final local batch):** `55b13cd2fcab67ba8436618f7032339649cbdffc`
**Harness:** `a0c185e35`
**S7 functional evidence:** attempt 15 on `a7b17bb38` (preserved)
**Status:** S7 date-only behavior and the two false-completion paths are
locally verified. Full-workflow release remains **HOLD**: attempt 15 is
functional verification passed with the original pilot-preservation
assertion **not established**, and no new full campaign was run on the
final local batch. No cutover.

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

**Diagnosis:** interpretation-budget exhaustion caused by a failed pinned
response plus a slow fallback chain, not a smaller S7 allocation and not a
generic continuation regression.

## Repair

1. **Durable named-source resolution.** A source named by the request
   ("the approved record") is resolved against the conversation's
   OBSERVED evidence using the existing reference collector. Prior
   requirement carriers are never evidence; several candidates stay
   ambiguous; a non-match stays unresolved.
2. **Bounded refinement, not a model requirement.** The bounded shape
   (one named, uniquely observed source; one canonical field;
   comparison-shaped; no mutation/send obligation) gets at most a **5s
   optional** model refinement. A resolved proposal (identifier,
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
   plus a different named record becomes an unresolved mixed marker, not
   a one-source completion. `verified_comparison_reply` refuses
   ambiguous/unresolved identities.
5. **Provider contract frozen.** The rehearsal gate derives the
   authorized provider set from the declared policy: `automatic`
   authorizes all configured providers; `selected` authorizes only its
   non-empty subset; invalid/empty authorizes nothing. Every POST, reply
   route, and structured route must be inside that set. Historical
   Ollama/DeepSeek intended-route observations are recorded but no longer
   decide the pass.

## Final local batch (product 55b13cd2f)

Two review residuals were closed locally; neither required a provider
experiment, a deadline change, or another full campaign.

1. **Unresolved sources survive every completion path.** The
   request-bound `_context_backed_fulfillment` verdict now checks an
   unresolved/ambiguous identity BEFORE observations. A valid workbook
   result can no longer erase the unresolved named record even when the
   current execution retrieved nothing. The mixed floor-file case is
   traced through the real resolver, builder, finalizer, response,
   persisted `objective_met=false`, and fresh history, with zero writes.
   A durable task-outcome gap is added when the path supplies the
   verdict; the direct harness row still carries the non-completion in
   `objective_met` even when the detailed gap is absent.
2. **Additional actions are obligations, not a phrase blacklist.** The
   existing `extract_request_assignments` obligation table records other
   mutation/send/insertion clauses as `additional_actions`. The read-only
   continuation fast path refuses them; the degraded fill composes an
   unresolved `additional_action` marker; the finalizer names the open
   work. The PRIMARY edit path is not blocked: the edit/no-op receipt
   suite still passes. A date read plus "insert client name" settles
   partial, not completed, with zero writes.
3. **Refinement observability is explicit.** The accepted interpretation
   carries `skipped` / `started` / `completed` / `failed` / `cancelled`;
   the runner prefers the accepted deterministic apply record over the
   model-unresolved event and treats a missing status as **unknown**, not
   "no dispatch". Any attempted refinement route must still be
   authorized. Product BYOK policy enforcement remains immediately before
   transport.
4. **Pilot preflight.** `ATOM_REHEARSAL_PILOT_MODE=required` (default)
   stops BEFORE creating the scratch world or launching the candidate if
   `:8001`/`:3000` are not listening. `ATOM_REHEARSAL_PILOT_MODE=absent`
   requires an explicit `ATOM_REHEARSAL_NO_PILOT_ASSERTION` and uses the
   distinct `no_pilot_isolation_asserted` gate; it is never reported as
   `pilot_untouched`.

## Verification

- **421 focused backend tests passed** on the final local batch
  (continuation, comparison, provider contract, pilot preflight,
  edit/no-op, orchestrator). Two `test_fallback_honesty` receipt fixtures
  fail identically on parent `73bcae400`; they are pre-existing and
  outside this slice.
- **Attempt 15** (product `a7b17bb38`, before this local batch): 61/62.
  Every functional, scope, write, settlement, restart and provider-policy
  check passed. The sole failure is `pilot_untouched` (see below).
- **S7 attempt 15:** `deterministic:continuation`; a 5s DeepSeek
  refinement was attempted and did not resolve; source
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

## Pilot guard: functional verification passed, preservation not established

The pilot backend `:8001` and frontend `:3000` were **already absent
before** attempt 15 launched. The declared config captured:

```
pilot_before: backend_8001_listening=false,
              frontend_3000_listening=false,
              health_error="ConnectError('[Errno 61] Connection refused')"
```

Both identity captures are null; the pilot pids from the earlier
checkpoint (16055/16488) no longer exist. The candidate ran on isolated
`:8121`. The guard therefore cannot pass: `pilot_untouched` requires a
live pilot identity and listening ports.

**Preserve attempt 15 as: functional verification passed; original
pilot-preservation assertion not established.** It is **not** 62/62.
No cutover was executed; this work did not start or restore the pilot.
The pilot's actual listener/process/store state should be verified before
any operational action; restore it only with established authorization
and the verified launcher/configuration.

The new preflight stops a required-pilot run before launch while the
pilot is absent. A declared no-pilot environment is a different,
explicitly asserted isolation run, not a pilot-preservation pass.

## Release decision

**HOLD.** The S7 date-only path is closed on its narrow scope, and the two
false-completion residuals are locally verified. The full workflow is not
called clean because the original pilot-preservation assertion is not
established and no new full campaign was run on the final local batch.
The owner decision is:

1. restore/authorize the pilot and run one fresh campaign on the `final4`
   world with the required-pilot preflight; or
2. explicitly declare a no-pilot environment, supply the isolation
   assertion, and accept the different `no_pilot_isolation_asserted`
   gate.

Neither option is a cutover. No provider experiment, deadline increase,
or unchanged full campaign is justified here.

## Known residuals (review comments, not false completions)

- The direct test harness's durable `AgentExecution` row carries
  `objective_met=false` for the mixed case but not always the detailed
  context-fulfillment gap; the response, settlement, and fresh history
  agree on partial. The gap field is additive for paths that supply it.
- The additional-action extractor records a primary edit such as
  "Update the draft for rows 1-5 with approved prices" as an
  `additional_action`; it does not create a marker for that non-seek
  edit, and the primary edit/no-op receipt suite passes.
- An uncaptured refinement dispatch is indistinguishable from no attempt
  in the log-derived route check; logged unauthorized POSTs are still
  caught by `provider_policy_respected`.

## Evidence

`docs/acceptance/release_evidence_20261024/byok_policy_attempts/attempt15_final3/`
(config, summary, result, console, predeclared config, checksums) and
`attempt13_final/` / `attempt14_final2/` for the comparison.
