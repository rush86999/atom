# Accepted-information recovery: current actor authority

Executed source: `5dfb58a85c6e80b458b203103ec83058c5378f3c` on
`codex/generic-recovery-authority-20261107` (base `e0430f9ff`). The supplied
lead probe now reports **2 passed**, actual exit0. Native wait/recovery/
admission/HITL consumers report **82 passed**, actual exit0. The real-process
restart consumer reports **6 passed**, actual exit0.

## Defect

An accepted information answer and its admission receipt were treated as
perpetual authority. Startup recovery checked only actor active/status, and the
shared normal-answer resume claimed the waiting job before building the frozen
execution namespace. Moving the original actor to another same-tenant workspace
after the answer was accepted therefore still dispatched the real Generic run in
the old scope (one `BoardTask`, job `success`). The supplied probe captured that
negative before the repair as 1 failed / 1 passed.

## Repair

`core.information_wait` now owns one current-authority contract reused by both
the startup selector and the normal resume path:

- the current `User` must exist, be active, keep tenant scope, still resolve to
  the admitted workspace (personal `None` resolves to the supported `default`
  twin), and retain RBAC `AGENT_RUN`;
- `_validate_recovery_target` refuses accepted startup work before the resume
  consumer;
- `resume_information_wait_action` performs the same check before claiming;
- `_claim_waiting_job_for_resume` binds the identical predicate as an `EXISTS`
  in the existing conditional `AgentJob` UPDATE, so a move/deactivation
  committed before the claim loses the CAS even when a preceding read passed;
- `_trusted_execution_context` rechecks the current actor against the frozen
  namespace before descendants dispatch.

The original admitted actor remains the execution authority; an admin answerer
cannot replace it. A change committed **before** the claim is refused. A
change committed **after** a successful claim is honestly in flight: the
packet does not claim physical cancellation of running work. The approved wait
receipt and waiting job/execution are retained for truthful blocked/refused
recovery.

## Controls

New permanent tests cover: moved workspace, moved tenant, deactivated actor,
lost `AGENT_RUN`, personal/null/default positive, tenant-absence positive,
unchanged-actor positive, direct normal-resume refusal, admin answerer, a forced
move between the precheck read and the claim, and a real public-admission
Generic/registered `tasks.create` positive/negative twin.

The real Generic twin controls only model transport; admission, Generic loop,
job/execution rows, registered `tasks.create` and the default oracle are
production. The process packet uses real child processes and the production
startup driver.

## Reproduction

- Private supplied probe:
  `LEAD_PROBES/recovery_actor_workspace/test_lead_information_recovery_actor_workspace.py`
  (SHA-256 `7235e97155b18d8367ceb524953f1c5c05d6a68a2ef179a02f64f9531bd3e386`,
  not staged).
- Project interpreter:
  `/Users/rushiparikh/projects/atom/backend/venv314/bin/python`.
- Every run used `TESTING=1`, an explicit synthetic `SECRET_KEY`, and a fresh
  owned scratch `DATABASE_URL`/data/Lance/office/basetemp. No live DB/world.
- Native selection: the new authority file plus
  `test_generic_information_wait_recovery.py`,
  `test_agent_generic_information_wait.py`,
  `test_agent_run_outcome_join_contract.py`,
  `test_boot_recovery_not_gated_by_scheduler.py`, `test_hitl_resume.py`,
  `test_generic_information_recovery_batch_contract.py`.
- Process selection: `test_agent_generic_information_wait_process.py`.

## Boundaries and artifacts

Logs and JUnit XML are preserved from the actual runs above without
regeneration; the supplied private probe directory itself is not staged. No
live app model/provider/credential, spend, send, download or deployment was
used. No raw tokens appear in this packet. This is not a full ordinary-login
browser/model campaign; the real Generic twin deliberately controls model
transport while exercising the production registered effect and oracle.
