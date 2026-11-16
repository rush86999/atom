# Sandbox lifecycle capacity — bounded verification, November 16

Concurrent mini-app calls could exceed their configured runtime capacity: both
runtime drivers released their permit before starting the guest. A factory also
creates fresh driver instances, so an instance-local semaphore was insufficient.

The Firecracker and explicit development Docker drivers now share a process-wide
capacity gate per backend, including across event loops and threads. A permit
covers startup, execution and confirmed teardown. Queued cancellation does not
consume capacity; repeated cancellation cannot release a permit before cleanup.
An uncertain process exit or container removal quarantines that backend for the
remaining process lifetime: queued and new work is rejected rather than retried.
Operators must reconcile owned resources before restarting a quarantined backend.
This is a per-process bound, not a distributed limit across multiple servers.
Production still requires Firecracker; Docker remains an explicit development path.

## Evidence and limits

Qualified implementation: `2d2d5de496f69df2d81a273844df7b8574614c13`.
The subsequent merge of main `ce346a68ab7d4e1c4c3202c3c2107e9de5d0f05e`
changed documentation only; the five qualified runtime/test files were unchanged.

- Independent six-call probe at capacity two: original peak six, fixed peak two.
  Two concurrent event loops also stayed at two. These use fake guest processes.
- Cancellation and uncertain cleanup probes verified that a second guest cannot
  start while cleanup is pending or after an unconfirmed exit/removal. Exact-target
  absence parsing rejects prefix, suffix, case and unrelated-error matches.
- Six selected test modules: **248 passed, five skipped** in 75.56 seconds on
  Python 3.12/macOS. The five skips are Docker integration tests. The gate allowed
  owned local sockets, denied external/model services, used scratch databases and
  an invalid Docker socket. It included the ordinary mini-app API record flow
  across two real backend processes; both owned processes exited afterward.
- A separate single real development-container smoke returned synthetic total ten
  and the matching state envelope. Its owned container was independently confirmed
  absent afterward. Network-none, read-only filesystem, dropped capabilities,
  nonroot user and resource flags remain unchanged.
- The argv unit now explicitly stubs image availability and rejects an actual
  image build, retaining its security assertions without relying on a warm cache.
  CI adds the lifecycle tests and this hermetic unit; existing selectors remain.

The first broad gate retained five failures: four from denied local sockets and
one from the pre-existing cache-dependent argv fixture. The final gate corrected
those test conditions. Backend startup also regenerated only timestamps in six
tracked demo templates; generated copies were preserved privately, content was
compared excluding those timestamps, and those six files alone were restored.

This evidence does not qualify real Firecracker execution, host-wide capacity,
all Docker integration scenarios, model quality, or whole-app readiness. Original
143 claim identities and 18 goals remain intact; no historical score is changed.

Private verifier receipts are retained under
`/private/tmp/atom-miniapp-root-localgate-20261116/`,
`/private/tmp/atom-miniapp-root-aa42-20261116/` and
`/private/tmp/atom-miniapp-final-dev-smoke-20261116/`.

## Real concurrent cleanup correction

A later six-call real Docker probe exposed a normal `--rm` race that the initial
single-container smoke missed: `docker rm -f` can report that removal of the
exact owned container is already in progress. The candidate was held and made
draft. That response is not treated as proof of absence. Teardown now polls the
exact target within a total cleanup deadline, retaining capacity until absence
is confirmed; persistent presence, malformed output, failed waits and daemon
errors still quarantine the backend. Docker's observed inspect absence response
is lowercase `error: no such object: <name>` with whitespace stdout. A separate
command-specific parser accepts that complete record while comparing the target
case-sensitively and rejecting unrelated targets or additional errors.

At corrected implementation `ac7256ff2dd688a60d11f12a1c9af0969c7ac93a`, an
independent real test created six fresh runtime instances and six DEV containers
at configured capacity two. All six succeeded; guest timestamp intervals showed
peak execution overlap **two**, and all six owned containers were absent after
completion. Each container retained the 128 MiB, one CPU, network-none,
read-only and dropped-capability posture. This demonstrates one-process DEV
Docker execution overlap; it does not establish Firecracker or distributed-host
capacity. No model calls or live app data were used.

Earlier failed real probes and exact Docker responses remain separately retained
under `/private/tmp/atom-miniapp-real-capacity-20261116/` and
`/private/tmp/atom-miniapp-real-capacity-recheck-20261116/`. The passing receipt is
`/private/tmp/atom-miniapp-real-capacity-final-20261116/result.json`.

The final independent CI-contract and runtime gate passed **870 checks**, with
five real-Docker integration cases explicitly deselected because the separate
six-container experiment supplied the bounded live evidence. The gate selected
the CI lane contract, shared-capacity, DEV-runtime and runner regression modules.
