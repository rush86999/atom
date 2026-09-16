# Provider reliability — bounded replay

_Generated 2026-09-16T13:59:15.790592+00:00 · mode `stream` · budget 3 calls · executed 3._

## 1. What this run measured

- Attempts: **3** · distinct generations: **2** · distinct `(provider, model)` pairs: **2**
- Effective caps: `{'budget_calls': 3, 'retry_cap': 1, 'spend_cap_usd': 0.05}` (retries used: 1, blocked: 0 by retry cap, 0 by spend cap)
- Transport success: **66.7% (2/3)** · contract pass: **50.0% (1/2)** (denominator excludes `unsupported_by_fixture` attempts)
- Zero output: 0.0% (0/3) · rate limited: 0.0% (0/3) · every provider attempt failed: 33.3% (1/3)
- Non-answer-looking replies (apology/refusal phrases): 33.3% (1/3)

## 2. Answer contracts (per probe)

| probe | contract | supported by fixture | unsupported expectations |
|---|---|---|---|
| `planning_short` | reply contains the sentinel token 'ok' (must be the only content) | yes | — |
| `grounded_medium` | unsupported_by_fixture: the medium fixture never links its rows to the identifier F-5216, so no list price for it can be verified | no | list_price_of_F-5216 |
| `derivation_large` | reply states the value 7519 and cites R235 | yes | formula_chain_derives_7519 |

## 3. Fixture limitations

- medium fixture: its 40 rows bind every value to 'machine <i>' (e.g. 'quote line for machine 7 | list=5007'); no row carries or links the identifier 'F-5216' (fixture-wide regex hits for F-5216: 0). An expected list price for the F-5216 is therefore NOT justified by this fixture — the probe's contract is unsupported_by_fixture and it is excluded from the contract pass rate (it still counts in the transport denominators).
- large fixture: row R235 does state 'LIST Price=7519.0' (and '$7,519.00'), so the list-price expectation IS checkable and is checked. Its formula string 'G235==F235*0.9 | I235==H235+700' is NOT checkable: the fixture never defines F235 or H235, and 5350*0.9=4815 != 7519, so 'the formula chain that derives it' is unsupported_by_fixture and is excluded from the contract pass rate rather than counted either way.

## 4. Observed outcomes by transport

| outcome | attempts |
|---|---|
| `ok` | 2 |
| `provider_error` | 1 |

### By prompt size

| tier | outcomes |
|---|---|
| medium | {'ok': 1} |
| small | {'provider_error': 1, 'ok': 1} |

## 5. Contract results and per-pair telemetry

| provider/model | attempts | transport ok | contract pass | mean first-visible ms | mean completion ms | cost unknown |
|---|---|---|---|---|---|---|
| `unknown/unknown` | 1 | 0 | 0.0% (0/1) | 2474.9 | 2475.0 | 1 |
| `openrouter/glm-5.3-flash` | 1 | 1 | 100.0% (1/1) | 1683.8 | 1697.7 | 1 |
| `deepseek/deepseek-reasoner` | 1 | 1 | n/a (no denominator) | 24702.1 | 24793.4 | 1 |

## 6. Latency

- First visible (streamed): mean 9620.3 ms / min 1683.8 / max 24702.1 over **3** attempts — stamped on the first streamed chunk with non-empty content
- Completion: mean 9655.4 ms / max 24793.4 over **3** attempts

## 7. Cost

- Provider-reported total: **0.0** · harness-estimated total: **0.0** · attempts with no reported cost: **3** (of which no usable estimate: 3 — the spend cap cannot see those)
- Cost per contract-satisfying answer: **None** (denominator 1)
- no provider-reported cost on this path: every attempt is flagged cost_unknown and the estimated total is a harness estimate from name-keyed pricing (provider-blind)
- Spend cap basis: provider-reported cost when present, else the harness estimate; an attempt with neither cannot be charged

## 8. Fallback topology

- Primary: `opencode-go/gpt-5.3-codex-spark`
- Ranked candidates: 129 · providers: `{'opencode-go': 11, 'openrouter': 9, 'deepseek': 109}`
- Fallback models (production API returns NAMES only): `['glm-5.3-flash', 'glm-5.3']`
- Fallback `(provider, model)` pairs: `[{'provider': 'opencode-go', 'model': 'glm-5.3-flash'}, {'provider': 'opencode-go', 'model': 'glm-5.3'}]`
- **Topology state: `all_shared_fallbacks`** → every fallback shares the primary's upstream provider — the ladder adds no provider diversity for the top candidate
- Legacy boolean `fallbacks_share_primary_upstream=True` (shared providers: `['opencode-go']`)

> A fallback sharing a gateway (e.g. OpenRouter) is a **common gateway dependency**, not independent capacity. Observing a 429 through that gateway does **not** prove every downstream route behind it was affected — and it does not prove they were healthy either.

## 9. Fallback independence (request boundary)

| provider | key resolvable | in ladder (rank) | authenticated (contract) | representative pair |
|---|---|---|---|---|
| `deepseek` | True (byok_store_or_env) | True (5) | True | `deepseek/deepseek-reasoner` |
| `ollama` | True (client_initialized) | False (None) | None | `None/None` |
| `opencode-go` | True (byok_store_or_env) | True (0) | False | `opencode-go/gpt-5.3-codex-spark` |
| `openrouter` | True (byok_store_or_env) | True (4) | True | `openrouter/z-ai/glm-5.3-flash` |

- Forced primary failure: `opencode-go/__atom_reliability_invalid_model__` · primary failure observed: **True**
- Fallback answered a contract-satisfying reply: **True** via `{'provider': 'openrouter', 'model': 'glm-5.3-flash', 'fallback': True, 'fallback_provider': 'opencode-go'}`
- Attempt sequence: `[{'provider': 'opencode-go', 'model': '__atom_reliability_invalid_model__', 'success': False, 'latency_ms': 101.9, 'output_chunks': 0, 'input_tokens': 0, 'fallback': False, 'fallback_provider': None, 'error': "Error code: 401 - {'type': 'error', 'error': {'type': 'ModelError', 'message': 'Model __atom_reliability_invalid_model__ is not supported'}}"}, {'provider': 'openrouter', 'model': '__atom_reliability_invalid_model__', 'success': False, 'latency_ms': 35.1, 'output_chunks': 0, 'input_tokens': 0, 'fallback': True, 'fallback_provider': 'opencode-go', 'error': "Error code: 400 - {'error': {'message': '__atom_reliability_invalid_model__ is not a valid model ID', 'code': 400}, 'user_id': 'org_3GHnwWcCSxGbfMG64iL8q70qPkK'}"}, {'provider': 'opencode-go', 'model': 'glm-5.3-flash', 'success': False, 'latency_ms': 257.5, 'output_chunks': 0, 'input_tokens': 0, 'fallback': False, 'fallback_provider': None, 'error': "Error code: 401 - {'type': 'error', 'error': {'type': 'AuthError', 'message': 'Invalid API key.'}}"}, {'provider': 'openrouter', 'model': 'glm-5.3-flash', 'success': False, 'latency_ms': 10674.2, 'output_chunks': 0, 'input_tokens': 0, 'fallback': True, 'fallback_provider': 'opencode-go', 'error': 'openrouter/glm-5.3-flash streamed no visible content (chunks=0, finish_reason=length)'}, {'provider': 'openrouter', 'model': 'glm-5.3-flash', 'success': True, 'latency_ms': 1730.7, 'output_chunks': 1, 'input_tokens': 0, 'fallback': True, 'fallback_provider': 'opencode-go', 'error': None}]`

## 10. What this does and does not establish

- Establishes: the observed outcome mix and contract results for the routes configured at replay time, with first-visible latency measured from real streamed output, per-attempt telemetry, and the ladder's provider-sharing topology.
- Does NOT establish: a provider-wide failure rate. The sample is bounded by the caps above and by the account's own quota.
- Does NOT establish: that a fallback is independent capacity. The topology state above is a statement about the configured ladder (and about shared gateway dependencies), not about behaviour under load.
