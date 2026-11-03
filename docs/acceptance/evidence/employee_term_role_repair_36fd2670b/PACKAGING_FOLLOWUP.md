# Packaging follow-up — term-role repair evidence at 36fd2670b

The independent review of `36fd2670b` closed both term defects but found the
submitted evidence at `f086d4999` was not checkout-verifiable:

- four manifest-listed logs were absent from Git;
- the manifest hash for the binding test file belonged to the local dirty
  working tree rather than the committed source.

This follow-up keeps the original README, TEST_RESULTS and MANIFEST unchanged
and adds the exact existing log bytes that the original manifest named. Their
hashes match the original manifest:

| Artifact | SHA-256 |
|---|---|
| `affected-suite.log` | `c0c91b6aa14c1cef287923fb74c8d6361e4ead692f2391ac1a46af60bb2947d3` |
| `focused-tests.log` | `21b242558f0e7ac8e2d368bb94b398224b5a2f6aa1fb5b168a4031e0da249c5f` |
| `independent-probes.log` | `108e9e48caf18ff717a3d583b3ad22f6b3add1b414048eeab7704fcccbee59b9` |
| `verifier-term-probe.log` | `ec48ff7956dcff902a3e4d9221f60ab3d2a83b6642af1b39f847ebfb1e1bd423` |

The four files are the exact bytes produced by the repair run; they were not
regenerated. `affected-suite.log` is the 789-passed/8-deselected run,
`focused-tests.log` the 179-passed focused run, `independent-probes.log` the
22-passed probe run, and `verifier-term-probe.log` the original independent
two-case probe log.

## Test-file hash correction

The original manifest recorded
`1d53f1e1991bb611a03fee49689f58a719e3e90b7e66323e728ea76986e59312` for
`backend/tests/test_employee_work_request_bindings.py`. That hash was taken
from a dirty working tree and is **not claimed** as the `36fd2670b` content.

The intended added controls (valid rate/amount executor twins and typed-receipt
tamper/missing-context controls) were committed with the next source
`c55cc9450`. That successor also adds explicit receipt-downgrade and
source/fingerprint hardening; its test file and runtime are bound separately
in `docs/acceptance/evidence/employee_term_contract_followup_c55cc9450/`.
The runtime accepted at `36fd2670b` is unchanged by this packaging follow-up.

No historical hash was altered and no log was regenerated.
