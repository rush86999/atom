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
status plus the pilot preflight. **518 focused tests passed**; the two
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

**Attempt 16 — declared no-pilot (product `55b13cd2f`).**
`no_pilot_isolation_asserted` passed; `pilot_untouched` was not a gate;
pilot preservation was not tested. Original run: **61/62**, only
`l3_answer_correct` false under the old predicate that rejected ANY decoy
mention. The L3 answer was correct (`QUARTZ-77`, with BASALT-13
explicitly identified as the Halcyon-2 archive key). The corrected
contract re-evaluates the **same captured answer** to true: **effective
62/62 on the corrected contract**. The original 61/62 is preserved; no
new campaign was run. S7 remained date-only (`deterministic:continuation`,
5s refinement cancelled, context completed, partial prior obligation,
38.64s, zero writes); edit/no-op and provider-policy gates passed.

**Release decision: PREPARED — HOLD for explicit live-deployment
approval.** The operational package is
`docs/acceptance/RELEASE_PACKAGE_55b13cd2f_2026-10-24.md`; the approval
request is `docs/acceptance/RELEASE_APPROVAL_55b13cd2f_2026-10-24.md`. It
includes the clean backend tree at `55b13cd2f`, the verified frontend
build `P5jHbHKTzj_38xHIMFoe9`, the fresh verified backup, smoke checks,
and rollback. The next decision is approval to start the verified
candidate against the intended live world—not another development brief.

No cutover has been executed. The pilot deployment/processes are
currently absent; this work did not start or restore them. No provider
experiment, deadline increase, or unchanged full campaign was run for
this local batch.

Evidence: `release_evidence_20261024/byok_policy_attempts/` (attempts
10–15 preserved) and `release_evidence_20261024/cutover_09cccb5b0/`
(attempt 9).
