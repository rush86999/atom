# Private handoff — TASK-WAIT-01 reconciliation

- Isolated worktree: `/private/tmp/atom-task-wait-01-reconciliation-20261107`
- Branch: `codex/task-wait-01-reconciliation-20261107`
- Base/executed source: `2d251acdfddae2aca27c6b43dc3f0de97654a9cb`
  (current main; clean at execution, `dirty=False`)
- No runtime/product file changed: documentation/evidence only.
- Image worktree, root capture worktree and other owners' worktrees were not
  touched. No shared runtime files conflict with radio MEM07 or fulfillment.

## What ran

82 targeted TASK-WAIT contract controls on `2d251acdf`, actual exit 0:

1. 6 assignment public-route/negative controls:
   `test_task_wait_source_trigger_contract.py`,
   `test_task_wait_two_fact_events.py`,
   `test_task_wait_two_job_isolation.py`,
   `test_task_wait_source_revocation.py`.
2. 21 assignment restart/budget/replay controls:
   `test_task_wait_source_continuation_regressions.py`,
   `test_task_wait_process_recovery.py` (3 real-OS-process cases).
3. 55 Generic wait/answer/recovery/authority controls:
   `test_agent_generic_information_wait.py`,
   `test_agent_generic_information_wait_process.py`,
   `test_generic_information_exact_event_contract.py`,
   `test_generic_information_resume_namespace_contract.py`,
   `test_generic_information_wait_recovery.py`,
   `test_generic_information_wait_recovery_authority.py`,
   `test_information_wait_maturity_neutral.py`,
   `test_agent_job_wait_execution_contract.py`,
   `test_agent_job_wait_namespace_contract.py`,
   `test_agent_job_wait_scope_contract.py`.

Exact stdout is retained in the three `targeted-*.log` files. Each selection
used a fresh scratch SQLite/data/Lance root with `TESTING=1`; the live dev DB
was never opened. No browser, model, provider, account, credential, send,
spend, install, deploy, KVM or Linux action occurred.

## Evidence to read

- `README.md` — eight-case requirement-to-evidence matrix and gaps G1-G6.
- `source-identity.json` — per-packet `executed_source` and byte-equality to
  current main; key current-main source/test hashes.
- `browser-scenario.json`, `browser-durable.json`, `browser-README.md`,
  `browser-MANIFEST.json`, `browser-CAPTURE_MANIFEST.json` — copied read-only
  from the PR744 browser packet. The original remains at
  `/private/tmp/atom-browser-capture-frozen-20261107/docs/acceptance/evidence/generic_information_browser_d3f58d81d/`.
- `targeted-*.log` — actual current-main exits.

## Non-negotiable provenance note

The browser packet declares `d3f58d81d`, but its recorded runtime health
identity is `ec69e24f4385-dirty.d48cacd2123b`. The packet binds the episode by
comparing 7,730 exported backend files to Git blobs at `d3f58d81d`; do not
accept it from the health badge alone. Eight of eleven declared source files
are byte-equal to current main; the missing three are the PR744 harness/test.
No browser replay is justified solely by a successor commit.

## Scope boundaries

- TASK-WAIT-01 remains OPEN at framework/whole-app scope.
- G1: Generic active-vs-absolute budget kind is not evidenced.
- G2: changed source after acceptance/before consumption is not directly
  exercised.
- G3: Generic source upload/selection (vs answer) is not evidenced.
- G4: symmetric Generic two-job isolation is not evidenced.
- G5: browser health-badge provenance mismatch.
- G6: browser cancellation/deadline/revocation/long-idle/order breadth absent.
- PR744 (browser) and PR745 (positive maturity) remain pending/separate; this
  checkpoint does not replace them.
- Historical 111/123, 143 claims, all original negatives and packets remain
  unchanged.

## Handoff

Root independent acceptance owns this worktree after handoff. Do not merge this
docs/evidence checkpoint as a runtime repair. If a future bounded owner task
targets G1-G4 or G6, reproduce failure first under a fresh scratch
`TESTING=1` root and reuse the existing lifecycle/route/claim mechanisms.
