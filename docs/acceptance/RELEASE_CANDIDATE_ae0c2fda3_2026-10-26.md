# Release candidate — `ae0c2fda3` (deployment approval package)

**Prepared:** 2026-10-26
**Status:** frozen release candidate; **awaiting deployment approval**.
**Deployed pilot:** `c912375de` (unchanged).

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
| Pilot to preserve | `c912375de` |

The candidate directory contains source, docs, and evidence only. It has **no
live data, live environment, or BYOK links** and is not running. The cutover
creates those links and a candidate-local config copy.

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

Approval is requested for the candidate-specific, fail-closed cutover in
[`CUTOVER_RUNBOOK_ae0c2fda3_2026-10-26.md`](CUTOVER_RUNBOOK_ae0c2fda3_2026-10-26.md):

```bash
ATOM_DEPLOY_APPROVED=ae0c2fda3 \
  ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
```

The script:

1. re-runs the read-only preflight (identities, archive, source, pilot
   PID/port/cwd, live paths, DB quick_check, backup space);
2. snapshots the live DB and aborts before stopping anything if the snapshot,
   quick_check, gzip, or size check fails;
3. prepares candidate-local data/env/venv links and a candidate-local BYOK
   config copy **before** the stop;
4. stops only recorded PID `33426`, verifies the port is free, and starts
   `ae0c2fda3` from its own versioned directory;
5. requires the new PID, cwd, and `ae0c2fda3/backend/data/atom.db` in
   `/api/health`;
6. on candidate start/health failure, starts the untouched `c912375de`
   release and verifies its health, then exits nonzero.

`c912375de` is never used as the candidate source and is never overwritten. A
post-deploy served smoke is a separate approved step; a failure there is a
separate rollback decision using the same pinned PID/port rules.

The pilot remains `c912375de` until that approval.

## Cutover checks already performed

- `bash -n` passes.
- `--preflight` passes: candidate source matches the canonical archive
  (0 differences), pilot PID `33426`/cwd/database match, DB quick_check `ok`.
- Wrong approval token exits `1` before any snapshot/link/stop/start; the
  pilot remained healthy and the candidate remained source-only.
- An isolated self-test of candidate preparation, config copy, snapshot
  gzip/quick_check, and health parsing (including wrong-database rejection)
  passed. The cutover itself has **not** been executed.

## Limitations / backlog (visible)

- Confirmation-path only: no first-request or timeout-recovery claim.
- Five-order latency at the fixed 95s budget remains backlog.
- Unknown-header confirmation UX and required-input filters remain the
  disclosed spreadsheet limitation.
- General policy transfer beyond tested order/vendor controls is not claimed.
- The release candidate's smoke is scratch-world evidence, not a pilot soak.
- The served smoke covers successful reviews; failure-path envelope and
  post-generation invalidation are covered by focused local controls, not a
  served failure smoke.
- Decision-turn binding is explicit; read provenance is preserved via
  `source_execution_ids`/`resumed_read`.

## Approval requested

Approve deployment of `ae0c2fda3` with the configuration above and the
rollback boundary to `c912375de`.
