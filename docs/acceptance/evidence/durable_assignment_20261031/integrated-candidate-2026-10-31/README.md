# Integrated candidate — merge identity and affected regressions

One product branch now contains the employee-execution work and the final
README-readiness fixes.

- Merge commit: `f2e809ba5`
- Parents: `5b72c6f6d` (employee execution) + `a666c83ba` (README readiness)
- Configuration: local, single worker, `ATOM_PRODUCT_PROFILE=core`, controlled
  transport; hosted deployment and publication remain owner-deferred.

## Conflict resolution (by contract, not by branch)

Two files conflicted in the LLM credential path. Both sides implemented the
same contract (detect a Settings key change and rebuild the cached handler), so
the resolution kept one mechanism:

- `key_store_signature()` is the canonical revision and is now
  **content-derived** (runtime manager credential fingerprint) rather than
  file-stat only, so a same-size rewrite inside one mtime tick is still
  detected;
- `BYOKHandler.credential_signature` is the attribute, with
  `_credential_signature` as a compatibility alias; `credentials_changed()` is
  a thin view over it;
- `LLMService` rebuilds on policy OR credential change and invalidates provider
  failures (cooldowns, circuit breaker, discovery backoff) before rebuilding;
- the dispatch-time backstop skips partially-constructed handlers (the
  `BYOKHandler.__new__` test pattern) instead of assuming a full runtime object.

## Regressions on the merged source

| Run | Result |
|---|---|
| Affected integration (BYOK/LLM, assignment executor+routes, all four canvas-assessment suites, gateway bug-hunt) | **155 passed** (`merged-affected.log`) |
| Office/workbook regression (24-sheet ingestion, aggregation, office core/binding/ownership, PPTX) | **101 passed** (`office-regression.log`) |
| Pre-merge baseline of the 4 graduation/shell failures | **4 failed at `5b72c6f6d`** (`premerge-baseline.log`) — pre-existing, not merge-introduced |

## Not established here

- Live Microsoft connector ingestion (goal 4/5) — authorization-dependent.
- Substantive judgment (goal 7) — the served configuration failed qualification.
- Real transport send (goal 8/11) — controlled outbox only.
- Multi-worker/soak — outside the declared single-worker topology.

See `docs/acceptance/REMAINING_WORK_2026-10-31.md`.
