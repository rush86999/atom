# Release candidate — `ae0c2fda3` (deployment approval package)

**Prepared:** 2026-10-26
**Status:** frozen release candidate; **awaiting deployment approval**.
**Deployed pilot:** `c912375de` (unchanged).

## Candidate identity

| Item | Value |
|---|---|
| Candidate commit | `ae0c2fda340e9a85e840e310d84d4d0da4fedab8` |
| Candidate source directory | `/Users/rushiparikh/projects/atom-releases/ae0c2fda3` |
| Source archive | `git archive ae0c2fda3 backend` |
| Archive SHA-256 | `3b4caf8cf9fa0be9bc3ef20e7505eb62af3a73b4bc7e6c13698142e112cc5fc5` |
| Served review acceptance base | `c0c0d2e87` |
| Preserved failing predecessor | `d4d0576d1` |
| Documentation closeout | `ca90762bd` (this package adds the support/deployment docs) |
| Includes spreadsheet fix | `e14d3efdd` |
| Pilot to preserve | `c912375de` |

The candidate directory contains source only. It has **no live data, live
environment, or BYOK symlinks** and is not running.

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

This package does **not** deploy or restart the pilot. Approval is requested
for:

1. snapshot the live DB before any restart
   (`scripts/restart_backend.sh` already snapshots);
2. deploy the `ae0c2fda3` source over the pilot release path, preserving live
   data/env/venv links;
3. run the same served smoke against the deployed instance **only after**
   explicit approval;
4. rollback to `c912375de` if the post-deploy smoke disagrees.

The pilot remains `c912375de` until that approval.

## Limitations / backlog (visible)

- Confirmation-path only: no first-request or timeout-recovery claim.
- Five-order latency at the fixed 95s budget remains backlog.
- Unknown-header confirmation UX and required-input filters remain the
  disclosed spreadsheet limitation.
- General policy transfer beyond tested order/vendor controls is not claimed.
- The release candidate's smoke is scratch-world evidence, not a pilot soak.
- Decision-turn binding is explicit; read provenance is preserved via
  `source_execution_ids`/`resumed_read`.

## Approval requested

Approve deployment of `ae0c2fda3` with the configuration above and the
rollback boundary to `c912375de`.
