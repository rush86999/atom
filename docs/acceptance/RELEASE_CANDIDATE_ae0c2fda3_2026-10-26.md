# Release candidate — `ae0c2fda3` (deployment approval package)

**Prepared:** 2026-10-26
**Status:** three authorized attempts executed. The third reached the product
smoke and failed functional checks; automatic code rollback is healthy.
Candidate is **not deployed**. A fourth attempt requires new authorization.
**Deployed pilot:** `c912375de`, PID `19046`, healthy on `:8001`.

## Candidate identity

| Item | Value |
|---|---|
| Candidate commit | `ae0c2fda340e9a85e840e310d84d4d0da4fedab8` |
| Candidate source directory | `/Users/rushiparikh/projects/atom-releases/ae0c2fda3` |
| Canonical archive | `git archive --format=tar -o evidence/archive/atom-ae0c2fda3-backend.tar ae0c2fda3 backend` |
| Canonical archive SHA-256 | `33a317c2b981f5947f854056aad8b11ffce4ac8c0a6b908e96f998d5dca4f526` |
| Preserved original gzip | `evidence/archive/atom-ae0c2fda3-backend-original.tar.gz` |
| Original gzip SHA-256 | `3b4caf8cf9fa0be9bc3ef20e7505eb62af3a73b4bc7e6c13698142e112cc5fc5` |
| Served review acceptance base | `c0c0d2e87` |
| Preserved failing predecessor | `d4d0576d1` |
| Package docs | support statement, independent-review record, cutover runbook (this directory) |
| Includes spreadsheet fix | `e14d3efdd` |
| Pilot restored | `c912375de`, PID `19046` |
| First attempt | failed at smoke login 401; manual recovery |
| Second attempt | failed at guided-agent HTTP 201; automatic code rollback healthy |
| Third attempt | product smoke ran; functional checks failed; automatic code rollback healthy |
| Smoke-created records | second-attempt agent + third-attempt agent/canvas/uploads/chats/executions, preserved |

The candidate directory contains source, scripts, docs, and evidence. After
the failed attempt it is **prepared** with candidate-local data/env/venv links
and a config copy, but it is **not running**. Its original tracked
`backend/data` is preserved under
`evidence/cutover/attempt-20261026T221610Z/source-backend-data/`.

## Archive record correction

The earlier package recorded `3b4caf8cf9fa…cc5fc5` while documenting a plain
`git archive ae0c2fda3 backend`. That hash belongs to the gzip artifact created
at freeze time with `--format=tar.gz`; it is not the hash of the documented tar
command.

- Canonical artifact: `evidence/archive/atom-ae0c2fda3-backend.tar`, plain tar.
- Canonical SHA-256: `33a317c2b981f5947f854056aad8b11ffce4ac8c0a6b908e96f998d5dca4f526`.
- A second run of the exact command produced the same hash.
- The gzip and tar extract to identical trees (0 differences).
- The canonical tar extracts to the staged source tree with 0 differences.
- The original gzip is preserved with its own hash and manifest; nothing was
  relabeled.
- The served smoke evidence JSON was written before this correction; its
  embedded candidate identity still records the gzip hash and is preserved
  as-run, not rewritten. It is not the canonical archive record.

See `evidence/archive/README.md`, `checksums.txt`, and `verification.txt`.

## What is in the candidate

- Spreadsheet aggregation/role fixes through `e14d3efdd`.
- Saved-lookup continuation fixes through `c0c0d2e87`.
- Release blockers from independent review through `ae0c2fda3`:
  failed review forces a failed envelope; post-generation message replacement
  invalidates the review; source-execution provenance is explicit; precomputed
  results require schema/execution/subject/decision agreement; raw machine
  blocks are stripped on failure; uncertified assessments are not exposed.
- Live cutover gate: `scripts/smoke_release_candidate_ae0c2fda3.py` plus the
  validated workbook fixtures in `scripts/smoke_inputs/`. It failed the one
  authorized attempt at admin login (HTTP 401) before creating any smoke data.
  The stale-password and rollback defects are fixed; a second attempt has not
  run.

## Served smoke evidence

Canonical smoke: `served_release_candidate_20261026/evidence.json`
(source `ae0c2fda3`, scratch world, planner enabled, no supplied rows,
finalization/task lifecycle on). `checks_all_true: true`.

Covered:

- PO Register approved rows: CAD **8050.00** (3 rows, qty 10), USD **3999.96**
  (1 row, qty 4).
- Adjustments approved rows: known subtotal **−700.00 CAD**, gap **0055** at
  **C5**, complete/grand total withheld.
- O-1010 review: **Process** before correction; **Escalate** after correction,
  citing **M. Chen / 2026-10-25**; **Escalate** after a real restart.
- O-1001 positive twin: **Process**.
- Structured reviews valid/persisted; raw fenced blocks hidden; response,
  persistence and history agree.
- Source workbook hashes unchanged; canvas audit setup-only;
  `task_operation_records=0`; `tasks=0`; no outbound/send/edit/approve.
- Teaching and correction stored; correction retrieval persisted across
  restart.

Attempt trail:

- `attempt1_harness_teachlog_gap.json` — all product checks passed; harness
  read the teach API response instead of the agent log.
- `evidence.json` — corrected smoke, `checks_all_true: true`.

## Configuration for deployment

Required (and captured in smoke):

```
CHAT_FINALIZATION_M1=1
CHAT_FINALIZATION_M2=1
ATOM_TASK_LIFECYCLE_ENABLED=1
# ATOM_DISABLE_TOOL_PLANNER intentionally unset
```

The root `.env.example` now uses `1` for the finalization flags to match the
code gate.

## Deployment boundary

This package does **not** deploy or restart the pilot. The generic
`scripts/restart_backend.sh` is deliberately not used: it stops every matching
Uvicorn process, continues after a snapshot failure, and resolves paths
relative to the script.

**One authorized attempt has been consumed and failed before product smoke.**
The pilot was manually restored. A second attempt requires new authorization;
the same command would be used after approval. The runbook is
[`CUTOVER_RUNBOOK_ae0c2fda3_2026-10-26.md`](CUTOVER_RUNBOOK_ae0c2fda3_2026-10-26.md):

```bash
ATOM_DEPLOY_APPROVED=ae0c2fda3 \
  ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
```

The script:

1. re-runs the read-only preflight (identities, archive, source, pilot
   PID/port/cwd, live paths, DB quick_check, backup space, live-smoke precheck);
2. snapshots the live DB and aborts before stopping anything if the snapshot,
   quick_check, gzip, or size check fails;
3. prepares candidate-local data/env/venv links and a candidate-local BYOK
   config copy **before** the stop;
4. stops only the recorded pilot PID (`5322` after manual recovery), verifies
   the port is free, and starts `ae0c2fda3` from its own versioned directory;
5. requires the new PID, cwd, and `ae0c2fda3/backend/data/atom.db` in
   `/api/health`;
6. runs the pre-restart live smoke:
   - sourced O-1001 answer with structured file/row evidence;
   - PO totals and Adjustments gap;
   - O-1010 Process → Escalate after correction;
   - repeated O-1001 as an identical no-op (same decision/evidence/outcome,
     zero new task/operation/canvas writes);
   - history/outcome agreement and zero unintended writes;
7. restarts only the candidate PID and requires matching health;
8. runs the post-restart smoke (same O-1010 session, Escalate, persisted
   pre-restart history/outcomes, correction lesson, zero new writes);
9. rechecks live DB `quick_check`;
10. on any failure, automatically rolls **code** back to untouched
    `c912375de`, preserves the post-cutover data, verifies rollback health, and
    publishes `SERVED_IDENTITY.json` with `status=rolled_back`;
11. on success, publishes `SERVED_IDENTITY.json` with the candidate PID,
    health, smoke evidence, and `database_restored=false`.

The database is **never restored automatically**. Restore only for
demonstrated corruption, after preserving the post-cutover DB/WAL/SHM.

The first authorized attempt stopped pilot PID `33426`, started candidate PID
`5188`, then failed at smoke login (HTTP 401) before creating smoke data. Its
automatic rollback exited before starting `c912375de` because `lsof` returns
`1` under `pipefail` when no listener remains. The pilot was manually restored
as PID `5322`. Evidence:
`evidence/cutover/attempt-20261026T221610Z/`.

The stale-password and rollback defects are fixed:

- smoke default is the live acceptance-admin password file, and
  `--check-only` verifies it against the admin bcrypt hash;
- all port probes treat “no listener” as valid;
- pilot PID is read from `evidence/cutover/pilot_pid.txt` (currently `19046`).

### Second attempt (2026-10-26T22:53:46Z)

The second authorized attempt ran after the confirmation parity and exit-guard
fixes. Preflight, snapshot, candidate start, and health passed. The pre-restart
smoke then failed at guided-agent creation because the endpoint returned
**HTTP 201 Created** while the smoke accepted only HTTP 200. The agent was
created; no canvas, upload, chat session, execution, task or canvas-audit record
was created.

Automatic code rollback succeeded: `c912375de` is serving as PID `13038`,
healthy on `:8001`, with `database_restored=false`. No repair or retry was
performed. Evidence:
`evidence/cutover/attempt-20261026T225346Z/`; smoke-created agent
`886b86b4-6917-4fec-831a-1f5a9ee22f4f` is preserved and recorded in
`smoke-created-records.json`.

The guided-agent contract was then corrected in the smoke: accept only HTTP
201 with `success=true`, a `data` object and a non-empty string `agent_id`;
reject 202 pending approval, 200, malformed/failure payloads and missing ids.
Canvas create/attach, upload and teaching now validate bodies and identifiers.
A 51-test no-network setup battery passes against both helper copies and the
actual candidate guided route with the generation factory mocked. No
application code changed.

### Third attempt (2026-10-26T23:41:57Z)

Setup passed end to end: login/auth, guided-agent 201, canvas create/attach,
both uploads, and teaching. The product smoke then ran and failed:

- PO Register approved rows passed: CAD **8050.00**, USD **3999.96**.
- Adjustments content was correct (**−700.00 CAD**, gap **0055/C5**, total
  withheld), but its confirmed `go ahead` turn returned
  `success=false`, `outcome=unconfirmed`, `error_code=outcome_unconfirmed`.
- O-1010 before correction: first partial saved-lookup response, then two
  `turn_budget_exceeded` results; no structured review.
- O-1010 after correction: `turn_budget_exceeded`, then
  `turn_failed_no_result` (“no usable results”); no row citation or review.
- O-1001 sourced answer: `turn_budget_exceeded` on every attempt; no structured
  review.
- Repeated O-1001: first `turn_budget_exceeded`; second returned a deterministic
  workbook read with `success=true/completed` but no structured
  `review_result`, so the identical-no-op check failed.

History persisted, teaching policy/correction stored, workbook hashes unchanged,
`task_operation_records=0`, `tasks=0`, canvas actions setup-only, and health
identity passed.

Automatic code rollback succeeded: `c912375de` PID `19046`, healthy on `:8001`,
`database_restored=false`. No repair or retry was performed. Evidence:
`evidence/cutover/attempt-20261026T234157Z/`; all smoke-created records are
preserved in `smoke-created-records.json` (agent, canvas, 3 dataset entries,
5 sessions, 32 messages, 13 executions, 4 canvas-audit actions).

No fourth attempt has been executed or authorized.

## Checks after the failed attempts

- `bash -n` passes.
- `--preflight` on the prepared candidate passes with pilot PID `19046`,
  live-link/database match, DB `quick_check ok`, and live-smoke precheck `OK`.
- `smoke...py --check-only` passes with the live acceptance-admin password,
  including `admin_password_matches=true`; the stale bootstrap file fails
  `admin_password_matches=false` and exits `1`.
- Wrong approval token exits `1` before any snapshot/link/stop/start.
- Isolated self-tests of preparation, config copy, snapshot gzip/quick_check,
  health parsing, direct scoped PID/port stop under `set -euo pipefail`, and
  served-identity publication pass.
- The fake-release `rollback_after_failure` regression starts and
  health-checks the rollback release, writes failed/served identity, and exits
  nonzero as intended.
- Fake-release exit-guard tests pass: unexpected exit after shutdown preserves
  status and rolls back; stop-evidence write failure after shutdown rolls back
  and publishes failure identity; pre-shutdown failure does not restart the
  pilot; committed success does not roll back.
- Confirmation parity passes: ordinary confirmation and authorized retry both
  send exactly `go ahead` with the original session/agent/token; the
  no-network branch test passes against the development helper, the packaged
  helper, and the frozen candidate classifier (9 passed). Old verbose
  confirmations are rejected by the candidate.
- The third live attempt reached the product smoke, failed functional checks,
  and rolled back automatically. No fourth attempt has been executed or
  authorized.

## Limitations / backlog (visible)

- Confirmation-path only: no first-request or timeout-recovery claim.
- Five-order latency at the fixed 95s budget remains backlog.
- Unknown-header confirmation UX and required-input filters remain the
  disclosed spreadsheet limitation.
- General policy transfer beyond tested order/vendor controls is not claimed.
- The existing product smoke evidence is scratch-world. The live gate now
  completed some product turns: PO totals passed, Adjustments content passed but
  its confirmed turn was `outcome_unconfirmed`, and review turns returned
  `turn_budget_exceeded`/`turn_failed_no_result` without structured reviews.
  These are candidate-bound live smoke results; no broad product claim is made.
- The live smoke covers successful reviews; failure-path envelope and
  post-generation invalidation remain covered by focused local controls, not a
  served failure smoke.
- Live smoke creates and preserves a named agent/canvas/uploads/lessons and
  chat history in the live DB; rollback does not erase them.
- Decision-turn binding is explicit; read provenance is preserved via
  `source_execution_ids`/`resumed_read`.
- Database restore is manual and only for demonstrated corruption, after
  preserving the post-cutover database.

## Decision state

Three authorizations are consumed. No fourth attempt is authorized. The third
attempt reached the product smoke and failed functional checks; the candidate
is not deployed and `c912375de` is serving after automatic code rollback. The
smoke setup contract/battery remains frozen; application code is unchanged.
Database restore is not part of normal rollback; it requires demonstrated
corruption and a separate manual decision.
