# PR #659 backend CI repair — evidence

Branch: `codex/pr659-backend-ci-fix-20261105`
Base: `71f9e22b4` (`Codex/oracle01 chat 20261105 (#662)`, current main after
PR #659 merged at `baa695775`).

This is a separate follow-up to the accepted fleet repair. It does not change
the accepted ORCH-07/ORCH-02 scope, inference/employee/browser campaigns, or
any production provider policy, tenant scope, capability floor, oracle proof,
or strict pin.

## Observed boundary

Hosted run `42149250267`, backend job `127668163932`, Python 3.11.18:

- `39 failed, 522 passed, 1 skipped` in 80.76s
- full job log: `baseline-hosted-pr659.log`

Local reproduction on `71f9e22b4` under the CI selection and declared env:

- `39 failed, 522 passed, 1 skipped`
- full log: `baseline-local-main.log`

## Failure classes and fixes

| Class | Failures | Root cause at the CI boundary | Repair |
| --- | ---: | --- | --- |
| Routing-feedback hook | 4 | Hook fixtures had no `workspace_id`; the concrete-model service lambda rejected the current `tenant_id` argument. | Fixture state contract: `workspace_id="ws1"` and `lambda workspace_id=None, tenant_id=None`. |
| Oracle task-id proof | 1 | Mock `BoardTask` row lacked the fields the current verifier compares against the expected title. | Fixture supplies `title="do it"` and `board_id=None`; the verifier proof is unchanged. |
| OpenCode Go free/paid streaming | 7 | Old doubles only set `clients`/`async_clients`; the current route gate correctly refuses an undiscovered cloud catalogue. Exposing the real dispatch path also exposed a mid-stream replay/recursion path. | Explicit isolated catalogue for the doubled routes; any failure after visible tokens now keeps the partial answer; the catalogue sweep excludes the exhausted pair and is one-shot. |
| w27 OpenCode free/paid retry | 6 | Same undiscovered-catalogue fixture gap. | Explicit isolated catalogue covering the free model, its paid sibling, and the free-tier walk. |
| BYOK handler a/d | 5 | Constructor-bypassed handlers lacked `_local_routes` and `credential_signature`; cloud success/stream tests had no discovery catalogue. | Complete current fixture state plus explicit isolated catalogues. The stale hardcoded `gpt-4o-mini` fallback assertion now matches the documented configured-provider tier default. |
| DeepSeek harness gaps | 16 | Same catalogue gap, plus MagicMock completion doubles whose dynamic children are invisible to `_response_field`, plus the mid-stream/sweep replay paths above. | Explicit isolated catalogue; real-shaped `SimpleNamespace` completion responses; runtime partial-retention/sweep fixes; no-retry tests pin a single-model catalogue so they test the paid-sibling helper rather than the ladder sweep. |

## Runtime fixes (narrowly traced)

`backend/core/llm/byok_handler.py`:

1. `stream_completion`: after any mid-stream exception with visible tokens
   already yielded, return the partial answer. Previously only
   `_StreamInactivityError` did this; a generic/credits error after the first
   token could re-issue the request on a paid sibling, another provider, or the
   catalogue sweep, duplicating visible content.
2. Catalogue sweeps never re-issue the exact `(provider, model)` pair that
   just failed, and the streaming sweep is one-shot (`_allow_ladder_sweep=False`
   on its recursive call). Without this, a catalogue whose served models all
   fail could recurse through the same dead catalogue indefinitely.

Both changes are covered by the existing consumer regressions
`test_mid_stream_failure_does_not_duplicate_retry`,
`test_mid_stream_credits_error_does_not_retry_or_duplicate`, and the
single-model no-retry tests.

## Verification commands

Exact CI selection on Python 3.11, with a unique scratch SQLite file (the CI
declared env otherwise unchanged):

```sh
cd backend
DATABASE_URL="sqlite:////private/tmp/atom-ci-fix/backend/data/ci_full_final_311.db" \
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
  -q --tb=line --timeout=300 --timeout-method=thread
```

Standalone memory gate:

```sh
cd backend
DATABASE_URL="sqlite:////private/tmp/atom-ci-fix/backend/data/ci_memory_final_311.db" \
SECRET_KEY="ci-test-secret-key" \
ENVIRONMENT="development" \
EMBEDDING_PROVIDER="fastembed" \
FASTEMBED_MODEL="BAAI/bge-small-en-v1.5" \
PYTHONPATH=$PWD \
python3.11 -B -m core.memory_eval
```

## Results

| Gate | Before | After |
| --- | --- | --- |
| Exact CI backend selection, Python 3.11 | 39 failed, 522 passed, 1 skipped | **561 passed, 1 skipped, 0 failed** |
| Exact CI backend selection, Python 3.14 | not the hosted interpreter | **561 passed, 1 skipped, 0 failed** |
| Standalone memory gate, Python 3.11 | — | recall 1.0, recall_keyword 1.0, recall_paraphrase 1.0, total 7, missed `[]` |
| Streaming/fallback neighborhood, Python 3.11 | 98 failed, 505 passed, 6 skipped | 98 failed, 505 passed, 6 skipped; FAILED sets identical |

The streaming/fallback neighborhood failures are pre-existing baseline debt,
not in the CI selection; the before/after failure sets are byte-for-byte
identical (`streaming-baseline-diff.txt`). No failure was skipped, deleted,
xfailed, or converted into a pass.

## Controls preserved

- Production `evaluate_route` is unchanged: an undiscovered cloud catalogue
  still refuses dispatch. The test helper installs an explicit isolated
  discovery catalogue only for tests that exercise a doubled cloud route.
- Local-only negatives still refuse: `test_local_providers_serve_runtime_advertised_models`
  asserts `local_abc`/`vllm`/`lmstudio`/`local` serve nothing without a
  registration, and `test_gateway_providers_serve_from_discovered_catalog`
  asserts an undiscovered gateway serves nothing.
- Oracle proof, strict pins, tenant/workspace scope, capability floors and
  branch protection are untouched.
- No live model, provider, browser, sandbox, credential, spend, send,
  download or deployment operation was used.
