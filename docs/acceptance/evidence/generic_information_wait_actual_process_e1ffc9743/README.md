# Generic information wait — actual-OS-process restart checkpoint

Executed test source: `e1ffc9743f9085d7cd1f965216107f5d2f5e0ae7`
(base integration `d922601050546364560474a2e6d0388a34c2a974`, which carries the
root namespace repair and current main). Production source was not modified.

## What this proves

A real admitted Generic job in one OS process selects an information wait
through the unpatched ``GenericAgent._react_step`` consumer (only
``LLMService.generate_structured`` is scripted), persists job/execution/wait
and prior history, and is hard-killed. A fresh OS process starts, runs the same
execution-recovery helper the production lifespan calls, keeps the **same**
job and execution, accepts the exact authorized answer through the normal
public ``/api/agents/{id}/jobs/{job}/answer`` route using the server-owned
correlation, and completes through a real registered ``tasks.create`` whose
board row is independently verified by the default oracle. A byte-identical
replay is idempotent and a different late answer is refused, so neither repeats
the effect.

Two independent captures are retained:

- `standalone-process.log` / `standalone-process-state.json`: the prepared
  `.probe/generic_wait_restart/drive.py` probe executed against the
  integrated base `d92260105` with real uvicorn processes. It recorded two
  distinct PIDs (durable owner 45708 for the first process; successor server
  45778), recovery `agent_recovered=0`, the same job/execution across restart,
  3 scripted model calls, the resumed prompt containing
  `AUTHORIZED INFORMATION ANSWER`, and one verified `board_tasks` row. The
  committed test records the first PID before the kill directly; this legacy
  probe's final `first_pid` field actually names the successor.
- `process-gate.log` / `process-gate-junit.xml`: the committed process test
  plus the relevant wait/exact-event/resume-namespace controls on
  `e1ffc9743`, **14 passed**, actual exit 0 (31.05s). The process test alone is
  `process-single.log` / `process-single-junit.xml`, 1 passed.

`pre-runs-evidence.json` preserves the earlier `96159a36c` probe receipts
(two runs) instead of regenerating them.

## First checkpoint attempt

The first scaffold run failed in the parent harness before any child process
spawned: the parent opened the child log before creating its fresh scratch
directory (`FileNotFoundError`). That is a harness-path defect, not a product
seam failure; the test now creates the unique owned run directory first. No
product/boundary negative was suppressed or relabelled.

## Honest seams / scope

- Authentication uses the repository's existing FastAPI dependency override
  for a seeded principal. This is controlled API scope, not an ordinary
  login/browser session.
- The successor invokes the same `core.execution_recovery` helper the
  production `main_api_app` lifespan calls; the full application lifespan/boot
  is deliberately **not** claimed by this checkpoint.
- Only the structured model transport is scripted. Prompt/schema/validation,
  lifecycle, registry, oracle and durable rows are real. No live
  model/provider, network, credential, spend, send or deploy was used.
- Assignment-only continuation/recovery remains at its separate accepted
  scope. Ordinary UI, general model judgment, automatic external
  information-event input mapping and whole-app TASK-WAIT-01 remain open.
- No replacement objective, injected plan, model-authored authority, direct
  resume-state DB write, new engine/table/daemon or app-wide polling was used.
