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

## Attempt 16 — declared no-pilot (product 55b13cd2f)

- Environment: `ATOM_REHEARSAL_PILOT_MODE=absent` with an explicit
  assertion. Before launch, `:8001`/`:3000` were not listening, pids
  16055/16488 were absent, no live-DB/WAL/SHM holder existed, `final4`
  did not exist, and the fresh backup was hash-recorded. The pilot's
  disappearance is **unexplained**; this work did not stop or restore it.
- The run used the pinned product `55b13cd2f` and the `a0c185e35` harness
  content. `no_pilot_isolation_asserted` passed; `pilot_untouched` was
  not a gate. Pilot preservation was **not tested**.
- **Original result: 61/62.** Only `l3_answer_correct` failed under the
  original predeclared gate (expected code, **no decoy mention**). The
  gate remains failed; this is **not** an automated 62/62.
- **Independent manual assessment:** the captured answer is semantically
  correct — QUARTZ-77 for Zephyr-9; BASALT-13 correctly attributed to
  Halcyon-2 as its archive key; no swapped or contradictory assignment;
  source named. This is a manual semantic assessment, not the gate
  passing. The earlier lenient predicate was withdrawn; no answer-scope
  contract change is requested. No new campaign was run.
- S7: `deterministic:continuation`; the 5s DeepSeek refinement was
  attempted and cancelled (`wait_timeout`); source
  `approved_records_q2026_114.txt`; fields exactly
  `["expiration_date"]`; `broader_comparison=false`; context
  `completed`; zero writes; outcome `partial` for the captured prior
  outlook obligation; `success=true`; **38.64s**.
- Edit applied exactly once; identical re-ask completed with zero writes;
  provider-policy gates passed. 518 focused tests passed.

## Verification

- **518 focused backend tests passed** on the final local batch
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

## Pilot environment: two distinct claims

- **Attempt 15:** functional verification passed; the **original
  pilot-preservation assertion was not established**. The pilot was
  already absent before launch; both identity captures were null; pids
  16055/16488 were gone. It is **not** 62/62.
- **Attempt 16:** a declared no-pilot run. `no_pilot_isolation_asserted`
  passed: the pilot remained absent before and after, no identity was
  claimed, the live DB was isolated, and the candidate ran on `:8121`.
  This is **not** pilot preservation and does not relabel attempt 15.

The pilot's disappearance is unexplained. No pilot was started or
restored. The new required-pilot preflight stops before world/candidate
launch while `:8001`/`:3000` are absent; a declared no-pilot run requires
the explicit assertion and uses the distinct isolation gate.

## Release decision

**PREPARED — HOLD for explicit live-deployment approval.** The S7
date-only path and the two false-completion residuals are closed on their
scopes. Attempt 16 establishes the declared no-pilot environment claim
and remains **61/62** under the original predeclared gate; the captured
L3 answer is semantically correct by independent manual assessment, but
that is not an automated gate pass and no answer-scope contract change is
requested. The operational release package and approval request are
prepared:

- `docs/acceptance/RELEASE_PACKAGE_55b13cd2f_2026-10-24.md`
- `docs/acceptance/RELEASE_APPROVAL_55b13cd2f_2026-10-24.md`

The next decision is **approval to start the verified candidate against
the intended live world**, with the prepared fresh backup, smoke checks,
and rollback. It is not another development brief. No cutover has been
executed; no provider experiment, deadline increase, or unchanged full
campaign was run.

## Known residuals (review comments, not false completions)

- The direct test harness's durable `AgentExecution` row carries
  `objective_met=false` for the mixed case but not always the detailed
  context-fulfillment gap; the response, settlement, and fresh history
  agree on partial. The gap field is additive for paths that supply it.
- The additional-action extractor records a primary edit such as
  "Update the draft for rows 1-5 with approved prices" as an
  `additional_action`; it does not create a marker for that non-seek
  edit, and the primary edit/no-op receipt suite passes.
- Refinement observability is explicit: `skipped` / `started` /
  `completed` / `failed` / `cancelled`; a missing status is **unknown**
  and fails the route/capture checks, and any attempted refinement
  requires captured authorized routes. Product BYOK policy enforcement
  remains immediately before transport.

## Evidence

`docs/acceptance/release_evidence_20261024/byok_policy_attempts/attempt15_final3/`
(config, summary, result, console, predeclared config, checksums) and
`attempt13_final/` / `attempt14_final2/` for the comparison.
