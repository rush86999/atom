# Test results — integrated remaining G5 behaviors

Executed source: `7ee05df3ad54beb7581b7055d472e66caf93c572` (clean,
`source_id=7ee05df3ad54`).

## Focused backend suite

The same 305-test set used for the remaining-behavior bundle was run on this
source: **305 passed, 617 warnings in 65.79s**. Full log:
`focused-tests.log`.

It covers assignment routes/executor, employee proposal/adaptation/work
requests, retained authorized source scope, prerequisite eligibility, patch
invariants, proof binding, campaign guard, document freshness, and the prior
verifier probes. The approval-wake regression control is
`tests/test_assignment_executor.py::test_approval_clears_the_matching_human_input_wait`.

## UI artifact journey

Harness: `ui/harness.py` (committed successor `7b6f39a1f`).

Result: **10/10 checks passed** (exit 0). Exact run
`bfed4e47-2570-4704-9aac-24a30598375e`.

Checks: captured exact run; selected source scope; assignment completed;
artifact applied; artifact criterion met; download OK; sha256 matches;
artifact contains `370.00`; artifact contains source and both lines; the
exact-run UI detail shows completion and `370.00`.

Files: `ui/capture.json`, `ui/final.json`, `ui/detail.txt`,
`ui/customer-quote.docx`, `ui/start-form.png`, `ui/exact-run-final.png`,
`ui/harness-run.log`.

## Normal-app API campaign

Harness: `api/harness.py` (committed successor `55eb68aa3`).

Result: **18/18 checks passed** (exit 0). Runs:

- artifact `142e523f-664b-42d7-b127-5a364cc3684a`;
- wait/branches/cancel `72076abf-ffb4-42f6-8a5a-6d602108df12`;
- controlled uncertainty `b1cd916b-232e-4d8f-ac81-94146490c0ff`.

Files: `api/report.json`, `api/REPORT.md`, `api/harness-run.log`,
`api/server.log`, `api/customer-quote.docx`, `api/outbox.jsonl`.

## Independent byte checks

- API artifact sha256
  `9db7930a22a0c9bbb3624ca9641cd0bdde1ec3c66d81b96dfa80c5365d98d809`
  equals the deliverable recorded in `api/report.json`.
- UI artifact sha256
  `8605b8a82265ef7670936846244938a9d9d3e8305eead6704fea32c3112411ea`
  equals the deliverable recorded in `ui/final.json`.
- Outbox sha256
  `46f37510fc3dc914c1988fdfaebc77d9c066cfb7987ef5db1c623f602fbd6aaf`
  is identical before and after restart/reconciliation; exactly one effect
  exists.
