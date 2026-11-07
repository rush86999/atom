# TASK-WAIT-01 source-answer baseline

This is a failure-first checkpoint, not a repair or a passing release candidate.
Executed source: `bc4970f97`. The tracked two-case test starts an objective through
`/api/assignments/from-objective`, reads a genuine missing-invoice question and
answers it through the same run's authorized `/sources` route.

The source-only case settles the question but leaves the task blocked with zero
new adaptation calls and no reconciliation. The otherwise-identical explicit
`/advance` twin passes: the real compiler/executor produces a verified 140.25
reconciliation and completes the same task. No expected total, formula or plan
is supplied through the API or to the controlled proposal transport.

The result is 1 failed / 1 passed; actual pytest exit code 1. The negative is the
new user requirement's missing behavior. It must become green through the
existing shared continuation path, without another harness advance or a new task
engine. Do not merge the failing test into a passing release before its repair.

## Test boundary and command

Public FastAPI routes, existing assignment compiler/executor and durable scratch
records are real. The existing route fixture overrides authentication identity;
discovery and adaptation proposals are controlled. This is not ordinary-login,
UI, served-model, provider, multi-worker or PostgreSQL qualification.

Project Python 3.14 ran `python -m pytest
 tests/test_task_wait_source_trigger_contract.py -q --tb=short` with TESTING=1,
a fresh scratch DATABASE_URL/data/Lance root, and a newly owned pytest basetemp.
The full stdout/stderr is retained unchanged in baseline.log. The checkout was
clean at execution; this evidence-only packet was added afterward.

The eleven separate existing wait/response/restart/idle-budget controls passed
at their recorded predecessor source; those are not claimed to prove this new
source-only behavior. Original employee episodes and known negatives remain
unchanged. No live model, account, provider, spend or deployment action occurred.
