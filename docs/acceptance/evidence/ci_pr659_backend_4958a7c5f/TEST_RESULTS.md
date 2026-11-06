# PR #659 backend CI repair — test results

Executed fix source: `4958a7c5fa80c276f53c13b5fb33ee295f4bc5f5`  
Follow-up PR: #663 (`codex/ci659-backend-repair-20261105` from main `71f9e22b4`)  
Observed failing PR: #659 run `42149250267`, job `127668163932`.

## Exact CI environment

```sh
cd backend
DATABASE_URL="sqlite://</absolute/unique>/test_ci.db" \
SECRET_KEY="ci-test-secret-key" \
ENVIRONMENT="development" \
PYTEST_CURRENT_TEST=1 \
TESTING=1 \
PYTHONPATH=$PWD \
python3.11 -B -m pytest <CI_SELECTION> \
  -q --tb=line --timeout=300 --timeout-method=thread
```

`CI_SELECTION` is the exact 30-file list from `.github/workflows/ci.yml`
backend-tests.

## Results

| Run | Result | Log |
|---|---|---|
| Hosted PR #659 backend job | 39 failed, 522 passed, 1 skipped | `hosted-failed-job.log` |
| Current main before fix | 39 failed, 522 passed, 1 skipped | `repro-311.log` |
| PR base `60a1171b8`, seven affected files | 39 failed, 173 passed | `base-seven-311.log` |
| Seven affected files after fix | 212 passed | `seven-files-311.log` |
| Exact CI selection after fix, 3.11 | **561 passed, 1 skipped** | `final-311.log` |
| Exact CI selection after fix, 3.14 | **561 passed, 1 skipped** | `final-314.log` |
| Memory eval gate | recall 1.0, no missed | `memory-eval-311.log` |
| E2E journey API file after fixture fix | 6 passed | `e2e-journey-fixed-local.log` |

## Follow-up PR checks

`pr663-checks-final.log` records the final green GitHub check run:

| Check | Result |
|---|---|
| backend-tests | **pass** (4m42s) |
| syntax-gate | pass |
| frontend-typecheck | pass |
| full-app-boots | pass |
| quickstart | pass |
| docker-build | pass |
| GitGuardian Security Checks | pass |
| e2e-journey | **pass** after the privileged journey fixture fix (12m23s) |

The original e2e failure was `TestSkillsJourney::test_skill_lifecycle`: the
journey user is registered as a normal member, while the accepted
community-skill delete contract requires TEAM_LEAD+. The fixture now creates an
isolated team_lead user against the backend DB; the test asserts member 403 and
team_lead 200/204. Final checks are all green.

## Changed files

- `backend/tests/test_routing_feedback_endpoint.py`
- `backend/tests/core/test_oracle_and_two_tier_confidence.py`
- `backend/tests/test_opencode_go_provider.py`
- `backend/tests/test_covpush_w27_opencode_retry.py`
- `backend/tests/test_covpush_w57_byok_handler_a.py`
- `backend/tests/test_covpush_w57_byok_handler_d.py`
- `backend/tests/test_deepseek_harness_gaps.py`
- `backend/tests/e2e_ui/fixtures/journey_fixtures.py`
- `backend/tests/e2e_ui/tests/test_journey_api_features.py`

No runtime file changed. No test was removed, skipped or xfailed.
