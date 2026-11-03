# Claim/revision CAS — test results

## Interleaving matrix

| Interleaving | Assertion | Result |
|---|---|---|
| New review (changed instructions) committed at claim time | apply refuses; description/review revision 2 preserved; executions 0 | PASS |
| New review with identical material | older claim invalidated by revision CAS | PASS |
| Rejection committed at claim time | rejected state preserved; no execution | PASS |
| Employee moved to another workspace at claim time | `exists()` employee predicate yields 0 rows; no execution | PASS |
| Two applies of the same review | one skill/execution; second returns the original skill id | PASS |
| Failed apply then retry | no Active row/retrieval after failure; retry reuses package with one execution | PASS |
| Independent verifier CAS probe | exit 0 | PASS |

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend combined (30 files) | `TESTING=1 pytest <30 files> -q` | **487 passed** | `backend-tests.log` |
| Independent CAS probe | `pytest /private/tmp/test_verifier_review_claim_cas.py -q` | **1 passed** | `cas-probe.log` |
| Frontend canvas panels | `jest <3 canvas suites> --runInBand` | **7 passed** | `frontend-tests.log` |
