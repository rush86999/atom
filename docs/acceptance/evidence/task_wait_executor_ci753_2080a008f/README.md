# PR753 executor CI follow-up — 2080a008f

Executed source: `2080a008f` (based on `20946867e`).

## Finding

Hosted backend step `128505680150` (run `42406649096`, head `20946867e`) failed
12 cases in `backend/tests/test_assignment_executor.py`. All were fixture
regressions after the source-consumption gate became active, not consumer
contract regressions:

- commercial / eligibility / uncertain-effect / standing-authority fixtures
  built real `workbook.read` or `document.read` steps with a path but no typed
  `resource_binding`;
- planner quote/service/expense fixtures used `internal_fixture` sources
  without the authorized reader `access_scope`.

The fix is test-only. `tests/source_authority_fixtures.py` gained
`bind_path()` so an existing real file gets the same typed controlled binding
the production resolver emits. The affected executor fixtures now bind their
actual read file and planner sources carry the active `user-1/ws_assign/
tenant_assign` reader scope. The executor still re-resolves the binding,
re-reads the file and refuses missing/changed authority; no check was
weakened, no source default inferred, no test skipped/deleted and no seeded
row was relabelled as parser/upload proof.

## Evidence

| Case | Result | Raw |
|---|---|---|
| Hosted 12 at `20946867e` | 12 failed | `hosted-backend-209-failure.log` |
| Exact 12 locally, before fix | 12 failed / exit 1 | `before-12-fail.log` |
| Exact 12 locally, after fix | 12 passed / exit 0 | `after-12-pass.log` |
| Prior 9 + root 13 + broader executor 13 | 35 passed / exit 0 | `after-35-pass.log` |

All local runs used `/private/tmp/atom-agent-cli/run_bounded_test_gate.py`
(`--profile bounded`), existing `venv314`, fresh unique `TESTING=1`
DB/data/Lance/output/basetemp, and a synthetic `SECRET_KEY`. No dependency
install, live model/provider/account/send/spend/deploy, or runtime change.

`RUNS.json` records the exact commands and exit codes. `MANIFEST.json` is
verified by `scripts/acceptance/evidence_git_check.py --strict` against
`executed_source` and the evidence ref.
