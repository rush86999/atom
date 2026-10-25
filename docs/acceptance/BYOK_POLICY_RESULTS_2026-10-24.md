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
| 12 | automatic / full configured store on final BYOK code | **52/62**; **edit failed again** (`edit_not_applied`), re-ask failed, comparison interpretation route not DeepSeek | DeepSeek, Ollama, OpenCode Go, OpenRouter |

Attempt 10 proves the hard policy boundary works: with all 13 keys present,
OpenCode Go/OpenRouter received **zero** POSTs. The failure is functional:
the allowed edit/no-op planner could not produce the required result.

Attempt 11 admitted OpenCode Go to recover the attempt-9 planning shape and
still excluded OpenRouter; the edit planner declined, so the workflow did
not pass.

## Conclusion

- The policy boundary itself works (attempt 10: zero forbidden POSTs; attempt
  11: zero OpenRouter POSTs).
- The **edit/no-op planner is the blocker** on the final code: it failed in
  attempts 11 and 12 with `edit_not_applied`/planner decline. Attempt 12 ran
  the full configured profile with policy `automatic`; the failure is not a
  policy escape.
- Attempt 9's 59/61 is historical evidence for `09cccb5b0` (before the BYOK
  code). It cannot be transferred to `a729df5f5` after two final-code
  functional failures.
- No final-code profile currently has a passing full workflow.

## Current status

The edit/no-op repair and the S7 date-only behavior are closed on their
narrow scopes; see `EDIT_NOOP_REPAIR_2026-10-24.md` and
`S7_CONTINUATION_REPAIR_2026-10-24.md`. The final local batch
(`55b13cd2f`) closes the two review residuals — unresolved mixed sources
surviving every completion path, and additional mutation/insertion/send
clauses blocking read-only completion — and adds explicit refinement
status plus the pilot preflight. **421 focused tests passed**; the two
`test_fallback_honesty` receipt fixtures remain pre-existing failures on
parent `73bcae400`.

Attempt 15 (product `a7b17bb38`, before the final local batch) is
preserved as **functional verification passed; original
pilot-preservation assertion not established**. It is **not 62/62**. Every
functional, scope, write, settlement, restart and provider-policy check
passed; the sole failure was `pilot_untouched`, because the pilot backend
:8001 and frontend :3000 were already down before the rehearsal (both
identity captures null, connection refused). The candidate ran on
isolated :8121.

The provider contract is now policy-derived: `automatic` authorizes the
configured DeepSeek/Ollama/OpenCode Go/OpenRouter set; historical
Ollama/DeepSeek intended-route observations are recorded but no longer
gate the pass. `provider_policy_declared`, `provider_policy_respected`,
`provider_reply_authorized` and `provider_structured_authorized` passed.

**Release decision: HOLD.** Still open:

- verify the pilot's actual listener/process/store state before any
  operational action; restore/authorize it only with the verified
  launcher/configuration and run one fresh `final4` campaign (the default
  required-pilot preflight stops before launch while it is absent); or
- explicitly declare a no-pilot environment with
  `ATOM_REHEARSAL_NO_PILOT_ASSERTION` and accept the different
  `no_pilot_isolation_asserted` gate.
- No cutover has been executed. The pilot deployment/processes are
  currently absent; this work did not start or restore them.

No provider experiment, deadline increase, or unchanged full campaign was
run for this local batch.

Evidence: `release_evidence_20261024/byok_policy_attempts/` (attempts
10–15 preserved) and `release_evidence_20261024/cutover_09cccb5b0/`
(attempt 9).
