# TASK-WAIT-01 recovery claim generation repair + second-crash takeover

This packet is source-bound to `223a286a4`
(`test(tasks): wake a crashed successor after its recovery claim expires`),
with the runtime repair from `c3e695ff4`
(`fix(tasks): bind accepted-evidence recovery to its claim generation`).
It preserves the original failure packet and the earlier actual-process
packets unchanged; it only adds this packet.

## Defect and repair

The withheld defect was reproduced independently at source `c0d85d7dc`
(runtime `1f4001dcb`) with the supplied probe: an older recovery claim's late
`_finish_evidence_recovery` could overwrite a successor claim that held the
SAME accepted-evidence key. The next boot then treated unconsumed accepted
input as already attempted and stranded it. The retained negative is
`root-original-negative.log` / `root-original-negative-exit.json`:
`1 failed (expired-old) / 1 passed (current)`, actual exit code `1`.

The repair keeps the existing lifecycle/claim/receipt owner and adds no table,
daemon, engine or live authority:

- `_claim_evidence_recovery` stores an opaque per-claim `claim_token` and the
  recorded owner process alongside the existing bounded assignment-plan marker.
- `_finish_evidence_recovery` and `_retain_evidence_recovery` require that
  exact token. A key-only or stale-generation call performs no write.
- `_evidence_recovery_plan` / `_evidence_recovery_takeover_ready` use the
  existing process-liveness probe: an elapsed lease never displaces a LIVE
  owner; a dead/unknown owner may be taken over only after the bounded lease.
- A boot that sees a fresh claim left by a dead process leaves one bounded
  wake at lease expiry, routed through the SAME recovery owner. No hot model
  polling and no source `/sources` replay.

## Supplied root gate (only at `223a286a4`)

The root-supplied gate was executed by root at exactly source
`223a286a4`, not at this branch's later packaging state and not at an earlier
repair source:

- source: `223a286a4038c7a7c22efb68fd42e92943f121dc`
- command: `python -m pytest -p no:cacheprovider --basetemp=<fresh> \
  /private/tmp/test_lead_evidence_recovery_generation.py \
  tests/test_task_wait_process_recovery.py \
  tests/test_task_wait_source_continuation_regressions.py -q --tb=short`
- result: **22 passed**, actual exit code **0**, 60.80s
- retained unchanged: `root22-gate.log`, `root22-gate-spec.json`,
  `root22-gate-exit.json`
- the supplied probe itself is retained verbatim under `probe/`.

The 22 cases include the two supplied generation probes, all three actual
OS-process recovery cases (restart-while-missing, accept-then-crash recovery,
and a successor that crashes after claiming followed by a later boot that wakes
at the lease), and the 17 source-continuation/recovery regressions.

## Second-crash takeover (actual OS processes)

`test_actual_process_successor_crash_after_recovery_claim_wakes_at_lease`
proves the event order with real child processes on one scratch store:

1. `start` creates the objective and reaches the genuine missing-invoice wait.
2. `source-interrupt` accepts/reads/settles the authorized invoice and hard
   exits with status **17** before adaptation.
3. `startup-claim-crash` runs the real startup owner, CAS-claims the accepted
   evidence, then hard exits with status **17** before continuation; its
   checkpoint retains the `claimed` marker and token.
4. `startup-recover-deferred` starts BEFORE that claim's lease expires. The
   one-shot boot observes the fresh claim, makes **0** adaptation calls and
   leaves a bounded wake.
5. At lease expiry the SAME recovery owner takes over with a NEW token and
   completes once: one adaptation, one `invoice.reconcile`, verified `140.25`.

The test asserts the successor start time is earlier than the dead claim's
expiry, the deferred completion is later, and the original run/objective are
preserved. No second `/sources` POST, `/advance`, new objective, injected
plan/result or manual advance is used.

## What this packet does not claim

- The root gate ran in root's clean tree. This packaging worktree has only the
  same tracked source plus untracked worker guidance; the tracked tree is
  unmodified. The gate is not re-run merely to package it.
- Scope remains the employee-objective `/sources` + restart-recovery seam.
  Generic/GenericAgent, workflow/long-running-task and other TASK-WAIT-01
  entrypoints remain OPEN.
- This packet does not promote the broader acceptance matrix. It proves the
  claim-generation authority boundary and the dead-claim lease wake only.
- No live provider/model, network, credential, account, send, spend, download,
  guest or deployment action occurred. Proposal transport was the repository's
  controlled fixture and storage was a private scratch SQLite/data/Lance root.
- Frontend Jest was not executable here (`frontend-nextjs/node_modules`
  absent); no frontend assertion is claimed.

## Preserved prior packets

- `docs/acceptance/evidence/task_wait_process_recovery_baseline_a966bca18/`
- `docs/acceptance/evidence/task_wait_process_recovery_repair_e9e43ea60/`
- `docs/acceptance/evidence/task_wait_source_continuation_6d08b1c4b/`
- `docs/acceptance/evidence/task_wait_source_trigger_baseline_bc4970f97/`

Their bytes and historical logs are untouched. `MANIFEST.json` pins this
packet's source files, artifacts and the preserved packet files it references.
