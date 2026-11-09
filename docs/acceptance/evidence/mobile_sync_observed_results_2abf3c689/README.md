# Mobile sync reporting — observed results

Source freeze: `2abf3c689`. The final controlled captures ran with uncommitted
changes over their recorded base; every one of 250 captured input hashes matches
this Git freeze. This is byte identity, not a claim of a clean served app run.

## Repaired producer and consumer

- Cached zero counts no longer hide retained pending, syncing or failed actions.
  Unreadable or unknown queue status refuses instead of certifying an empty queue.
- The existing `sync_state` carries the local pass identity, exact selected IDs,
  observed per-entity counters and terminal `SyncResult`. No parallel store,
  operation engine, provider receipt or review lifecycle was introduced.
- In-flight results are null; failed-only retained work cannot return success or
  be redispatched. One transport failure plus a status-write failure counts once.
- The modal renders actual counters, bytes and duration. Percent, inactivity and
  a cancellation request cannot manufacture completion. There are no production
  fixed entity totals or `synced * 1024` byte estimates.
- Matching cycle, selected identities and aggregate counts are checked. Stale
  observed cycles and contradictory summaries refuse. Completion callbacks are
  once per newly observed successful pass, not replayed on opening history.
- Committed queue changes notify the UI; stale async notifications cannot erase
  a newer observation. New queued work removes the old all-complete presentation.

## Evidence

Four negative captures are unchanged at their own sources: stale queue summary
(3 failures), false modal completion (4), missing producer result (3), and double
counting a single failed action (1). All six capture input sets bind to Git,
249/250 files each, zero mismatches, no source reconstruction.

The final selected regression passes 965/965 across 25 actual files with zero
skips/pending cases. It includes the real serialized queue/service joined to the
mounted modal under controlled native storage and API transport: one actual
selected test action becomes the exact displayed result; a transport refusal
stays incomplete; repeated close does not repeat the callback; new work cannot
retain the prior complete state. This is not a physical MMKV persistence test or
an actual remote business effect.

Old renderer fixtures expected invented totals. They now explicitly supply
observed cycle/result data and keep progress, log, cancellation, summary and
callback assertions. No test was removed. Fixture wiring errors and intermediate
runs are not promoted as product-negative proof. The original joined test's
navigation-context error was diagnostic serialization of a surviving stale
complete view; the producer notification was repaired rather than bypassing it.

## Remaining gates

Strict full-project compilation still fails with 402 diagnostics. Native build,
keychain/MMKV migration, real process/device restart, complete app bootstrap,
queue account binding, full retained-row validation, served API protocol and
unknown external-effect reconciliation remain open. Local pass IDs are scoped
to the service lifetime, not qualified global/provider identities. A local sync
result does not prove a remote business outcome or physical worker cancellation.

The Flash proposal is retained with its exact predecessor input source and root
adjudication. Extra phase engines, guessed confirmation-loss fields and automatic
restart/retry policy were not adopted. No new provider, credential, model
download, live account action, deployment or native OS permission was used.

References: https://github.com/react-native-netinfo/react-native-netinfo#addeventlistener
and https://react.dev/reference/react/useEffect .
