# BYOK policy results — profile decision required

**Date:** 2026-10-24
**Candidate:** product `a729df5f572ac254eac0ae0d4180818c67916eba`,
launch `9cbd029d883f`
**Status:** BYOK policy/UX implemented and reviewed; **no selected-provider
policy has a passing full workflow**. Live cutover remains held.

## What is complete

- Installation provider policy: `automatic` / `selected`, allowed provider
  ids, preferred pair; unset preserves legacy behavior, empty selected means
  no routes, malformed/unknown/unreadable values fail closed.
- Enforcement before ranking and immediately before every dispatch, including
  streaming, non-streaming, structured, pins, fallback, vision,
  transcription, embeddings, and local-only composition.
- Settings → AI: allowed vs preferred, selected-set fallback text,
  env-managed read-only state, truthful key/check status, actual answering
  provider/model in chat, failed-save restoration.
- Tests: **323 backend focused passed**, **42 frontend component tests
  passed**, production webpack build passed.
- Independent review: **APPROVE WITH COMMENTS**; blocking comments addressed
  (spec-mock guard, global check invalidation, positive auxiliary controls).

## Rehearsal results

| Run | Policy | Functional result | Provider POSTs |
|---|---|---|---|
| 9 | full configured store (automatic/legacy) | **59/61; 59/59 functional pass** | DeepSeek, Ollama, OpenCode Go, OpenRouter |
| 10 | selected `ollama`, `deepseek` | **56/61**; edit passed, **re-ask failed** (`reask_not_a_noop`, planner unavailable) | **DeepSeek, Ollama only — zero forbidden POSTs** |
| 11 | selected `ollama`, `deepseek`, `opencode-go` | **54/61**; **edit failed** (`edit_not_applied`, planner declined) | DeepSeek, Ollama, OpenCode Go — **zero OpenRouter POSTs** |

Attempt 10 proves the hard policy boundary works: with all 13 keys present,
OpenCode Go/OpenRouter received **zero** POSTs. The failure is functional:
the allowed edit/no-op planner could not produce the required result.

Attempt 11 admitted OpenCode Go to recover the attempt-9 planning shape and
still excluded OpenRouter; the edit planner declined, so the workflow did
not pass.

## Conclusion

- The only profile with a passing functional workflow is the **full
  configured store** (attempt 9): OpenCode Go/OpenRouter/DeepSeek replies,
  DeepSeek interpretation, OpenCode Go edit/tool planning.
- Strict Ollama/DeepSeek containment is enforced correctly but currently
  fails the identical re-ask.
- Adding OpenCode Go fixes neither reliably; the edit planner remains
  nondeterministic under the selected policy.

## Decision required

1. **Accept the tested full profile**: cut over with BYOK policy
   `automatic` (or unset) and the attempt-9 functional evidence; declare the
   actual routes in the support statement. The selected-provider controls
   ship but are not the pilot's active profile.
2. **Hold for planner/no-op work**: keep the selected policy and fix the
   allowed edit planner (a separate functional change), then re-rehearse.

No cutover has been executed. The pilot remains `8c593e57031e`.

Evidence: `release_evidence_20261024/byok_policy_attempts/` (both failed
attempts preserved) and `release_evidence_20261024/cutover_09cccb5b0/`
(attempt 9).
