# TASK-WAIT-01 E1 — two sequential missing facts in one assignment

Source `e10a689c9c62f1e9b8bdce05b689ccd4c56d5682`. The final controlled gate
reports **252 passed**, actual exit 0 (202.62s) on project Python 3.14.7 with
`TESTING=1`, fresh scratch SQLite/data/Lance/office paths and an owned pytest
basetemp.

## Defect and repair

A normal objective authorizes only the purchase order. Invoice and receiving
are both absent, so `invoice_reconciliation` declares both roles missing. At
baseline `dff775b8f`, the first clarification persisted
`inputs.missing=['invoice','receiving']` even though the controlled model asked
only for the invoice. The invoice answer therefore could not settle the
question it answered and the same task remained blocked.

The repair scopes the durable obligation to the proposal's explicit typed
`clarification.missing_roles`, validated against the capability's declared
missing roles. `/sources` settles only the question whose named roles the
accepted source now supplies; the capability's other missing role remains
absent from the compiler role binding, so dependent execution stays blocked
and the same consumer asks for the next fact. Human wording is never parsed
for role names. Legacy broad questions keep whole-capability readiness.

## Failure-first evidence

`two_fact_failure_probe.py` is a **test-only** untyped probe added to a frozen
`git archive` of baseline `dff775b8f` (runtime tracked-clean; the archive has no
`.git`, so runtime identity logs `unknown`). Its exact sha256 is
`00c9091ba76e2e11a66bc29dcddedc1babdd7547809e6ac83275306462311c69`.
It fails at the role-scope assertion with `['invoice','receiving']` versus
`['invoice']`: 1 failed, actual exit 1. The probe is intentionally pre-repair
schema; the committed test bytes are not retroactively assigned to the
baseline.

## Repaired claim

The committed public-route probe starts with a PO-only scope and a normal
requested DOCX, then:

1. records exactly one actionable invoice question and no report bytes;
2. answers only the invoice through `/sources`; exactly that question resolves,
   no reconciliation/report appears, and the same task records a **distinct**
   receiving question;
3. answers the receiving record through `/sources`; the same task applies one
   verified `invoice.reconcile` result of `130.00`, then exactly one DOCX whose
   bytes/hash and `word/document.xml` (`130.00`, PO) are read back and whose
   artifact requires the verified reconciliation receipt.

No `/advance`, second objective, plan/facts injection or DB step injection is
used. The model fixture is a controlled proposal transport: it chooses the
missing fact/typed role and work; the existing compiler owns role binding and
arithmetic. A wrong-PO invoice negative cannot settle the invoice question or
advance the task.

## Scope boundary

This proves the employee-assignment source-answer mechanics for E1, including
the requested final output. It is **not** served-model/real-LLM quality,
automatic branch discovery, app-wide/general TASK-WAIT-01, PostgreSQL,
multi-worker/soak, E2 cross-job isolation or E3 revocation acceptance. No live
model, provider, credential, send, spend, guest or deployment action occurred.
Root owns CI, PR metadata and final acceptance.
