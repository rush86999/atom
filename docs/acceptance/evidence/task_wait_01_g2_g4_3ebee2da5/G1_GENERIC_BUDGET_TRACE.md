# G1 — actual Generic run/job budget and deadline contract

Source: `3ebee2da5` (current main `36fa4ce39` merged; runtime unchanged from
main for this trace).

## What exists

| Contract | Actual fields/behavior | Is it a persisted wait budget/deadline? |
|---|---|---|
| `AgentRunRequest` (`backend/api/agent_routes.py:55-57`) | `agent_id: Optional[str]`; `parameters: Dict[str, Any]` | No. No wall budget, `timeout_seconds`, `max_wall_seconds`, deadline or expiry field exists. |
| `AgentJob` (`backend/core/models.py:945-959`) | `id`, `tenant_id`, `agent_id`, `status`, `start_time`, `end_time`, `logs`, `result_summary` | No. No deadline/expiry/budget columns. |
| `AgentExecution` (`backend/core/models.py:1120-1151`) | status, input/trigger, started/completed/duration, result/error/metadata | No. No wall budget or absolute deadline. |
| `GenericAgent.execute` (`backend/core/generic_agent.py:336-339, 807-817`) | `max_steps` and active-run `timeout_seconds` (default 300) wrap the in-process ReAct loop with `asyncio.wait_for` | Active execution only. The run returns when it requests a durable information wait; there is no persisted wait clock to extend. |
| `GenericAgent._check_budget_before_react` | Existing tenant spend-budget gate before an LLM call | A spend gate, not an active-wall/absolute-deadline contract. |
| `_wait_for_approval` / `_wait_for_all_approvals` (`generic_agent.py:3287-3334`) | `hitl_timeout` (default 600s) polls an in-run HITL approval | Synchronous approval polling inside one active execution, not a durable information-wait expiry. |

## Consequence

The Generic surface has **no configured wall budget or absolute deadline for a
persisted information wait**. There is nothing to enforce or silently extend;
adding one would be a new owner/budget contract, not a repair of existing code.
The employee-assignment executor's wall/idle ledger and absolute deadline are a
different surface and are not relabelled as Generic.

## New controlled-clock evidence

`backend/tests/test_generic_information_idle_contract.py`:

1. Starts a real admitted Generic job that reaches a durable information wait.
2. Asserts exactly one model call and a pending wait receipt.
3. Advances a controlled clock by two hours, then performs an authorized job
   read; the job remains `waiting`, the same wait id/correlation is returned,
   and the model call count is unchanged.
4. Advances another two hours, reads durable state, and asserts the same wait
   receipt, a pending `HITLAction`, and no new model call.

Existing actual-process tests (`test_agent_generic_information_wait_process.py`)
cover restart/recovery for the same wait. This proves idle no-poll/retention,
not production soak or a Generic absolute-deadline feature.

## Decision

No Generic budget engine, owner API, deadline field, scheduler or polling loop
was added. If a future product requirement defines a Generic absolute deadline,
it must be specified as a new contract and reviewed separately.
