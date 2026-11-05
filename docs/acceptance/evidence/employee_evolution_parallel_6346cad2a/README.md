# ORACLE-01 — tool-mutation sandbox lineage/freshness repair

Status: **submitted for independent verification.** This is the bounded repair
of the verifier's three parallel-sandbox probes on the submitted tool-mutation
review family. The decision-route controls, exact-material review CAS, audit
receipts and replay from `eaba0cb8f`/`e4816e59c`/`5dc4f1b0f` remain.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-evolution-review-20261105` |
| Prior submitted product | `eaba0cb8f` |
| Prior submitted tests | `e4816e59c` |
| Prior evidence | `5dc4f1b0f` |
| Executed repair source | `6346cad2a` |
| Accepted base | `95f7bcac1a0375b4f0465a77e15130f68fc9665d` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions and doubled sandbox |
| Live sandbox/model/provider calls | none |

## Verifier findings and repair

### 1. Sandbox result certified a changed lineage

The sandbox result CAS omitted `parent_tool_id`. A peer could change lineage
while `execute_raw_python` ran; the writer still matched the old
id/tenant/status/tool/code/error and committed `passed`, certifying the new
generation it did not execute.

The repair binds the exact nullable `parent_tool_id` in the result CAS, together
with id, tenant, prior status, tool name, code and prior execution error. A
lineage change matches zero rows, preserves the peer lineage/status/error,
returns `skipped` with `stale_mutation`, and never reports success for the new
lineage.

### 2. Stale session dispatched code after a committed review

`AlphaEvolverEngine.sandbox_execute_mutation` queried the caller's identity map
first. A session that loaded `pending` before another session committed
`approved`/`rejected` reused the stale object and called `execute_raw_python`
once; the later guarded UPDATE correctly preserved the review, but only after
code had run.

The repair releases only a clean caller transaction, then reads authoritative
executable material from a fresh session before constructing the dispatch
snapshot. A review committed before the invocation causes zero sandbox calls.
The caller's unrelated pending work is not rolled back or expired. The sandbox
is acquired only after a real executable target is resolved.

### Precise boundary

A review that arrives **while an already-started worker is running** still wins
the result CAS: the worker's update matches zero rows, the review is preserved,
and the result is skipped. This repair does not claim to physically stop an
in-flight worker and adds no distributed cancellation engine.

## Finite controls

- The three supplied verifier probes pass (`verifier-probes-314.log`).
- In-repo `tests/test_evolution_sandbox_parallel_contract.py` covers:
  - valid pending and failed twins (one dispatch, passed, error cleared);
  - changed lineage during the worker (skipped, peer lineage/status preserved);
  - unchanged/null lineage twin (passed);
  - changed code and changed prior-error during the worker (skipped, peer
    material preserved);
  - stale-session approved/rejected before dispatch (zero calls, review
    preserved);
  - reviewer during the worker (one call, review wins the CAS, lineage/error
    preserved);
  - missing/foreign target (zero calls).

## Controls

- **Focused gate: 58 passed on Python 3.14 and 3.11**
  (`focused-314.log`, `focused-311.log`): the original 47 decision/route/
  sandbox-gap controls plus 11 new parallel-writer controls.
- **Affected review/audit selection: 104 passed on both versions**
  (`affected-review-audit-314.log`, `affected-review-audit-311.log`).
- **Affected evolution selection: 304 passed, 29 skipped, 1 exact baseline
  failure on both versions** (`affected-evolution-314.log`,
  `affected-evolution-311.log`). The failure is
  `tests/test_auto_dev/test_reflection_engine.py::TestReflectionEnginePatternDetection::test_identifies_repeated_failure_patterns`,
  identical at the accepted base (`baseline-evolution-314.log`,
  `baseline-evolution-311.log`).

## Boundaries

- No live code sandbox, Docker, model, provider, credential, spend, send,
  download or deployment operation.
- No new status/operation/cancellation engine; the existing guarded DML and
  `ToolMutation` material are reused.
- Approval remains review only, not deployment or automatic application.
- PostgreSQL runtime/soak, multi-worker qualification and whole-app ORACLE-01
  remain open.
- Accepted admin/auth-2FA/canvas/feedback/wait/employee/ORCH-01 scopes and the
  submitted scoped-memory family remain independent.

## Artifacts

`focused-*.log`, `affected-*.log`, `baseline-evolution-*.log`,
`verifier-probes-314.log`, `source-tree.txt`, `README.md`, `TEST_RESULTS.md`,
`verification.json`, `routes.json`. `MANIFEST.json` records the SHA-256 of every
artifact and source file.
