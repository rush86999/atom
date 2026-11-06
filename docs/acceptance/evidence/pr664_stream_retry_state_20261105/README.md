# PR #664 streaming retry-state repair — evidence

Branch: `codex/pr659-backend-ci-fix-20261105`
Base: `71f9e22b4` (current main)
Code checkpoint: `70d38bef5`
Prior PR #664 head: `929b7c6e6`

This package closes the two runtime streaming probes that were withheld after
the fixture/CI repair. The original backend CI closure remains intact.

## Probes before and after

Exact external probe file:
`/private/tmp/test_verifier_pr664_stream_boundaries.py`

Before (`probes-before-311.log`):

```
2 failed
- test_paid_retry_partial_failure_never_dispatches_another_route
  PAID PARTIALDUPLICATE FALLBACK
  calls: deepseek-v4-flash-free, deepseek-v4-flash, gpt-4o
- test_sweep_budget_survives_ranked_fallback_recursion
  calls: model-z, model-a, model-b, model-a
```

After (`probes-after-311.log`):

```
2 passed in 3.71s
```

The same 25-test matrix-plus-probes gate passes on Python 3.14
(`matrix-and-probes-314.log`).

## One request-owned state

`backend/core/llm/byok_handler.py` now defines `_StreamRequestState`, shared
by the initial attempt, the paid free->paid retry, the self-heal retry, every
ranked-route hop and the catalogue sweep.

- `visible_yielded`: every actual visible delta sets it. After it is true, no
  later frame may dispatch another generation attempt; the partial answer is
  returned under the existing interruption contract. This covers the paid
  retry's nested try (which previously yielded text without setting the flag)
  and the self-heal inline retry.
- `attempted_pairs`: every pair that reaches transport is recorded. Ranked
  fallback routes and catalogue sweep candidates skip pairs already attempted
  in the request, not just the current frame's `(provider_id, model)`.
- `sweep_consumed`: the catalogue sweep is one-shot per request. The ranked
  fallback recursion now propagates `_allow_ladder_sweep`, and the sweep
  itself checks the request-wide flag.
- `self_heal_used` / `paid_retry_used`: explicit bounded repairs are counted
  separately. The self-heal budget is one repair per request (not per
  recursive frame) and cannot restart the sweep. A free->paid retry is
  allowed once per free pair.
- `attempts`: per-pair dispatch counter for attribution/evidence.

Nested retries now also reject reasoning-only/empty streams instead of
recording a success, and a failed paid retry is attributed to the paid model
that actually ran. A transport-interrupted partial is recorded as failure,
never as synthetic success.

## Generated matrix

`backend/tests/test_stream_retry_state_contract.py` contains a generated
table across:

- failure location: initial, paid retry, self-heal, provider fallback,
  ranked fallback, catalogue sweep;
- content stage: zero visible, reasoning-only, visible partial;
- exhaustion: one, two or three automatic routes.

It includes the two exact external probes plus a request-wide self-heal
repair-limit regression as named cases, plus undiscovered-catalogue and
local-only negative controls. The per-case
attempt counters are in `attempt-counters.json`; every automatic pair is
tried once, while the explicit self-heal repair is the only same-pair count
of 2. The matrix is added to the CI backend selection.

## Commands and environment

Interpreter: CPython 3.11.16 (CI interpreter) and 3.14.7 (repo venv).
Scratch SQLite files under `backend/data/`; no live provider or network.

Updated exact CI selection (31 files, matrix added):

```sh
cd backend
TESTING=1 \
DATABASE_URL="sqlite:////private/tmp/atom-ci-fix/backend/data/ci_full_final2_311.db" \
SECRET_KEY="ci-test-secret-key" \
ENVIRONMENT="development" \
PYTEST_CURRENT_TEST="1" \
PYTHONPATH=$PWD \
python3.11 -B -m pytest \
  tests/test_integration_http.py tests/test_local_models.py \
  tests/test_routing_feedback_endpoint.py tests/test_phase_integration.py \
  tests/test_response_quality.py tests/test_routing_trainer_integration.py \
  tests/test_routing_db_persistence.py tests/test_round17b_fixes.py \
  tests/test_learning_routing.py tests/test_learning_llm_router.py \
  tests/test_workbook_runtime.py tests/test_canvas_crud.py \
  tests/test_openrouter_provider.py tests/test_provider_wiring.py \
  tests/api/test_a2a_routes.py tests/api/test_sso_oidc_routes.py \
  tests/api/test_scim_routes.py tests/core/test_observability_tracing.py \
  tests/core/test_oracle_and_two_tier_confidence.py tests/test_memory_p2.py \
  tests/test_memory_consolidator_llm.py tests/test_memory_eval_gate.py \
  tests/test_memory_backfill_unified.py tests/test_opencode_go_provider.py \
  tests/test_covpush_w27_opencode_retry.py \
  tests/test_covpush_w57_byok_handler_a.py \
  tests/test_covpush_w57_byok_handler_d.py \
  tests/unit/core/test_stage_router_wiring.py \
  tests/unit/core/test_traffic_split.py tests/test_deepseek_harness_gaps.py \
  tests/test_stream_retry_state_contract.py \
  -q --tb=line --timeout=300 --timeout-method=thread
```

Small gate:

```sh
python3.11 -B -m pytest \
  tests/test_stream_retry_state_contract.py \
  /private/tmp/test_verifier_pr664_stream_boundaries.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Standalone memory gate:

```sh
DATABASE_URL="sqlite:////private/tmp/atom-ci-fix/backend/data/ci_memory_final2_311.db" \
SECRET_KEY="ci-test-secret-key" \
ENVIRONMENT="development" \
EMBEDDING_PROVIDER="fastembed" \
FASTEMBED_MODEL="BAAI/bge-small-en-v1.5" \
PYTHONPATH=$PWD python3.11 -B -m core.memory_eval
```

## Results

| Gate | Result |
| --- | --- |
| External probes, Python 3.11 | **2/2 passed** (before: 2 failed) |
| Matrix + probes, Python 3.11 | **25 passed** |
| Matrix + probes, Python 3.14 | **25 passed** |
| Updated CI selection, Python 3.11 | **584 passed, 1 skipped, 0 failed** |
| Updated CI selection, Python 3.14 | **584 passed, 1 skipped, 0 failed** |
| Standalone memory gate | recall 1.0, keyword 1.0, paraphrase 1.0, 7/7 |
| Accepted fleet probes | **19/19 passed** |
| Streaming/fallback neighborhood | identical before/after failure set: 98 pre-existing failures, 505 passed, 6 skipped |

The neighborhood failures are pre-existing baseline debt outside the CI
selection; `neighborhood-before-after.txt` shows the empty FAILED-set diff.

## Git source / artifact hashes

Code checkpoint `70d38bef5250f8d1cacb274abde69ab8dd23e18b`:

| File | Git blob | SHA-256 |
| --- | --- | --- |
| `backend/core/llm/byok_handler.py` | `579df2756e8d1d854028921aab516af0eaa778d1` | `3db26a03f66a6d2f8ec330a3423314c3b42cabdab5cb392f7a82ed074c268feb` |
| `backend/tests/test_stream_retry_state_contract.py` | `bc2caf3fc1d3f1b04e11c4359fc79b99595d3c60` | `f6c610121fdd067e49e44066d8e330914e9e0efccf998704e288d59830d7dc20` |
| `.github/workflows/ci.yml` | `1202681bd5a16de3fee438efe9a4e97ce71aa4d8` | `5523145a904b7f27793df2b899a8f2b42b4c86d91e20981b649ab6b9d81c7a77` |

Evidence artifact hashes are in `verification.json`.

## Preserved boundaries

- Production route eligibility is unchanged: an undiscovered catalogue still
  refuses dispatch, and the local-only negative still refuses a cloud route.
- Strict pins, credentials, tenant/workspace scope, capability floors and
  branch protection are unchanged.
- No live model, provider, browser, sandbox, credential, spend, send,
  download or deployment operation was used.
- The skill-lifecycle 403 remains the same pre-existing main baseline; this
  package does not grant roles or weaken skill authority.

No merge or deployment was performed.
