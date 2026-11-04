# Employee runtime successor — worker context and claim generations

2026-11-04, America/Toronto.

**Status: both verifier runtime defects are repaired and independently probed
locally. No model or UI replay was performed; the recorded fresh QH episodes
remain at their actual source `3ccad7a5a`.**

| Item | Value |
|---|---|
| Runtime successor source | `629dc632971543a7f75059e4f6a34623aa72b1c6` |
| Worker/context matrix | **14 passed**, including both verifier probes |
| Affected consumer regression | **197 passed** |
| Recorded episode source | `3ccad7a5a99afdcef7784f903b3744e36d86ea4b` (unchanged) |

## Defect 1 — caller context lost at the worker boundary

`_to_thread_safe` previously submitted directly to a `ThreadPoolExecutor`,
which does not propagate the calling task's ContextVars. Each submission now
takes `contextvars.copy_context()` in the calling task and runs
`_stop_iteration_safe(fn, ...)` through that fresh context. Concurrent jobs
each get their own copy; worker-local changes cannot leak back to the caller or
sideways to another job.

Controls in `backend/tests/test_worker_context_and_claims.py`:

- inherited workspace/trace scope is visible in the worker;
- two concurrent callers see their own distinct scopes;
- a worker's ContextVar mutation does not change the caller or a later worker;
- synchronous worker exceptions still propagate;
- cancellation cleanup still runs on the real worker exit, not when the
  awaiter is cancelled.

Verifier probe: `test_thread_bridge_preserves_callers_context` passes.

## Defect 2 — stale worker cleanup released a newer claim

Every claim now receives an opaque generation token. The token is stored under
the existing inflight lock with an explicit lease expiry. Release and retain
are conditional:

- a token that no longer owns the pair is a no-op;
- the legacy named-holder path can only release/retain the same holder's live
  claim;
- a stale worker whose lease expired cannot pop or extend a replacement
  worker's reservation;
- a claim that already exited is never resurrected by a late retain;
- explicit expiry represents a retained lease longer than the ordinary leak
  TTL correctly (`keep > TTL` does not silently become `TTL`).

The production call sites in `byok_handler.py` (text completion, structured
completion, the two streaming/completion ladders) capture their token and pass
it to release/retain. Worker completion cleanup is idempotent and bound to the
same token; cancellation retain is bound to the same generation.

Controls in `backend/tests/test_worker_context_and_claims.py`:

- A active → B refused;
- A lease expiry → B takeover;
- A late release (named holder or old token) cannot remove B;
- A stale retain cannot extend B;
- C is refused while B still owns the slot;
- release is idempotent and a released claim is not resurrected;
- a retained lease longer than the TTL remains in force;
- synchronous exception and cancellation-on-real-exit paths.

Verifier probe: `test_expired_old_worker_cleanup_cannot_release_new_claim`
passes.

## Test evidence

- `worker-contract-tests.log` — 14 passed, including
  `tests/test_worker_context_and_claims.py`, the existing structured
  cancellation controls and the two verifier probes.
- `successor-regression.log` — 197 passed across the employee adaptation,
  compact continuation, identity/completion, durable wait, work-request,
  capability routing, pinned planning, fallback-chain and budget-extension
  neighborhoods.

A separate legacy `tests/test_model_route_identity.py` run still fails 14 tests
on a pre-existing missing `byok_manager` attribute; that failure is outside the
worker/context/claim changes and was not used as a passing control.

## Boundaries

The runtime successor changes no episode state, artifact, objective,
authorization or expected result. The fresh two-order QH episodes, the
known-value recovery bundles and the original negative remain at their actual
source identities. Packaging/provenance and the missing independent procurement
source-selection row are Agent 1's lane; see
`/private/tmp/brennan-brief/AGENT1_FRESH_G5_PACKAGING_HANDOFF.md`.

No live/cloud provider, credential, spend, send, download or deployment
authority was used. Historical 111/123, planner 5/5, goal router 1/2 and
alignment gap 3.0 remain unchanged.
